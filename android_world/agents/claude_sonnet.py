"""Claude Sonnet agent for AndroidWorld.

Structurally mirrors ``gemini3.Gemini3Agent`` (raw screenshots, persistent
``cur_user_messages`` with sliding-image window, qwen-vl 1000x1000
coordinate grid, ``<tool_call>``-style action parsing) so trap hooks and
the coordinate-conversion pipeline are shared. The Claude-specific bits:

  - System prompt is rewritten in Claude-friendly plain-English style
    rather than Qwen's tool-schema dump. Claude reliably follows
    explicit natural-language instructions and outputs the requested
    XML-wrapped JSON.
  - Inference goes through ``ClaudeRestWrapper.predict_mm(messages=...)``,
    which auto-routes to ``/v1/messages`` (Anthropic native) or
    ``/v1/chat/completions`` (OpenAI-compatible proxy).
  - Reasoning is encouraged inside ``<reasoning>...</reasoning>`` (Claude
    pattern), kept in the assistant turn so subsequent steps can
    self-reflect on prior decisions when the sliding window holds them.
"""

import copy
import json
import logging
import os
import pprint
import time

import numpy as np
from android_world.agents import base_agent
from android_world.agents import gui_owl
from android_world.agents import infer_claude
from android_world.agents import mobile_agent_utils_new as mobile_agent_utils
from android_world.agents import new_json_action as json_action
from android_world.agents import seeact_utils
from android_world.agents.coordinate_resize import update_image_size_
from android_world.env import actuation
from android_world.env import adb_utils
from android_world.env import interface
from PIL import Image


# Claude-tailored system prompt. Uses ABSOLUTE pixel coordinates rather
# than a normalized 0-999 grid because Claude's training (computer-use)
# is anchored on real pixel positions; forcing 0-999 made the model flip
# back and forth between conventions mid-episode. The exact screen
# resolution is supplied in each user turn so the model can lock onto
# the right space, and the coordinate-conversion pipeline now runs in
# `abs_origin -> abs_origin` (i.e. pass-through) for this agent.
_SYSTEM_PROMPT = '''You are an AI agent that operates an Android phone by looking at screenshots and choosing one action per turn. Your job is to make steady progress toward the user's goal: never repeat a stuck action, never invent UI elements that aren't visible, and finish with action=terminate (status="success" or "failure") once the goal is achieved or impossible.

# Coordinate system
All coordinates are absolute pixel positions in the screenshot you receive. (0, 0) is the top-left corner; the bottom-right corner equals the screen resolution that will be stated in each user turn. Aim the cursor at the center of the target element, not its edge. Always use the exact pixel coordinates you can read off the screenshot — do not rescale them to any other range.

# Action vocabulary
You may emit exactly one of the following actions per turn:

- click — tap a single point.
  arguments: {"action": "click", "coordinate": [x, y]}
- long_press — press and hold a point for `time` seconds.
  arguments: {"action": "long_press", "coordinate": [x, y], "time": <seconds>}
- swipe — drag from one point to another (use for scrolling lists, dismissing sheets, opening the app drawer, etc.).
  arguments: {"action": "swipe", "coordinate": [x1, y1], "coordinate2": [x2, y2]}
- type — type text into the currently focused input box. The text appears as-is; the IME does not interpret tabs or newlines.
  arguments: {"action": "type", "text": "<string>"}
- key — issue a hardware/keyevent (adb keyevent name, e.g. "volume_up", "power", "clear").
  arguments: {"action": "key", "text": "<keyevent>"}
- system_button — press one of the soft system buttons.
  arguments: {"action": "system_button", "button": "Back" | "Home" | "Menu" | "Enter"}
- open — launch an app by name. The name MUST be from the canonical app list at the bottom of this prompt.
  arguments: {"action": "open", "text": "<app name>"}
- wait — pause and let the UI settle (use after a navigation that takes a moment to load).
  arguments: {"action": "wait", "time": <seconds>}
- answer — submit a textual answer to the user's question. Use this for tasks whose goal is information retrieval.
  arguments: {"action": "answer", "text": "<answer>"}
- terminate — end the task. Always emit this once the goal is fulfilled or judged infeasible.
  arguments: {"action": "terminate", "status": "success" | "failure"}

# How to think
Before acting, briefly reason about: (1) what is on the screen now, (2) whether your previous action achieved its intended effect, and (3) what single concrete step moves the goal forward. Keep reasoning under ~80 words; do not narrate every UI element.

If the prior action did not have the expected effect (e.g. a popup is still there, the keyboard didn't appear, the app didn't launch), do NOT immediately retry the same action. Diagnose first: dismiss the popup, scroll, switch apps, or pick a different target.

# Response format
Respond every step with EXACTLY two XML blocks, in this order, and nothing else:

<reasoning>
[Brief reasoning, see "How to think" above.]
</reasoning>
<tool_call>
{"name": "mobile_use", "arguments": {"action": "<action>", ...}}
</tool_call>

The <tool_call> block must contain ONLY a single valid JSON object — no markdown fences, no commentary.

# Available apps for action=open
Use these exact names (lowercase):
''' + gui_owl.all_apps_str


class ClaudeSonnetAgent(base_agent.EnvironmentInteractingAgent):
    """Claude Sonnet agent — gemini3-shaped with Claude-tailored prompt."""

    def __init__(
        self,
        env: interface.AsyncEnv,
        llm: 'infer_claude.ClaudeRestWrapper',
        name: str = 'ClaudeSonnet',
        max_history_images: int = 3,
        output_path: str = '',
        task_name: dict | None = None,
    ):
        super().__init__(env, name)
        self.llm = llm
        self._actions: list[dict] = []
        self._screenshots: list[Image.Image] = []
        self.cur_user_messages: list[dict] = []
        self.output_path = output_path
        if self.output_path and not os.path.exists(self.output_path):
            os.makedirs(self.output_path, exist_ok=True)
        self.task_name = task_name or {}
        self.last_image = max_history_images
        self.tmp_prefix = ''
        self.trap_controller = None
        # Updated each step from the captured screenshot so convert_format
        # and the per-step user message can quote the exact pixel size.
        self._screen_resolution_str = ''
        # Scale factors mapping LLM-facing image space to device space.
        self._coord_scale_x = 1.0
        self._coord_scale_y = 1.0

    # ------------------------------------------------------------------ reset
    def reset(self, go_home: bool = False) -> None:
        super().reset(go_home)
        self.env.hide_automation_ui()
        self._actions.clear()
        self._screenshots.clear()
        self.cur_user_messages.clear()

        try:
            adb_utils.press_home_button(self.env.controller)
            time.sleep(1)
            screen_size = self.env.logical_screen_size
            width, height = screen_size if screen_size else (1080, 2400)
            swipe_cmd = (
                f'shell input swipe {width // 2} {int(height * 0.8)} '
                f'{width // 2} {int(height * 0.2)} 300'
            )
            adb_utils.issue_generic_request(swipe_cmd, self.env.controller)
            time.sleep(1)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging.warning('ClaudeSonnet initial swipe-up failed: %s', e)

    def get_task_name(self, suite) -> None:
        for _, instances in suite.items():
            self.task_name[instances[0].goal] = instances[0].name

    # ------------------------------------- history window / history rendering
    # Identical sliding-window logic to gemini3 / qwen3vl: keep at most
    # `last_image` user turns with their image attachments; older user turns
    # are reduced to text-only (or fully cleared from index 1).
    def cut_current_messages(self, messages, last_image=2):
        non_empty_user_indices = []
        for i, msg in enumerate(messages):
            if (msg.get('role') == 'user'
                    and msg.get('content') and len(msg['content']) > 0):
                non_empty_user_indices.append(i)

        if len(non_empty_user_indices) > last_image:
            indices_to_clear = non_empty_user_indices[:-last_image]
        else:
            indices_to_clear = []

        for index in indices_to_clear:
            if index == 1:
                messages[index]['content'] = [messages[index]['content'][0]]
            else:
                messages[index]['content'] = []
        return messages

    def convert_format(self, goal, messages):
        """Render the persistent message log into the prompt actually sent.

        Replays the running text-history (extracted from prior assistant
        <tool_call> blocks) into the *first* live user turn, then carries
        the most recent screenshots. Mirrors the gemini3 convention so
        the parsing path (Action: ... <tool_call>...) stays compatible.
        """
        new_messages = copy.deepcopy(messages[:1])
        history = []
        for i, msg in enumerate(messages):
            if msg.get('role') == 'user' and (
                msg['content'] == []
                or (len(msg['content']) == 1 and 'text' in msg['content'][0])
            ):
                # Pull the prior assistant's reasoning sentence as a history
                # bullet. Strip <reasoning>/<tool_call> wrappers if Claude
                # included them so the bullet stays compact.
                prior_text = (
                    messages[i + 1]['content'][0]['text']
                    if i + 1 < len(messages) else ''
                )
                cleaned = prior_text
                if '<reasoning>' in cleaned:
                    cleaned = cleaned.split('<reasoning>', 1)[1]
                if '</reasoning>' in cleaned:
                    cleaned = cleaned.split('</reasoning>', 1)[0]
                cleaned = cleaned.split('<tool_call>')[0].strip()
                if not cleaned:
                    cleaned = '(no reasoning recorded)'
                history.append(cleaned)

            if i != 1 and msg.get('role') == 'user' and msg['content'] != []:
                resolution_line = (
                    f'Screen resolution: {self._screen_resolution_str} pixels.\n\n'
                    if self._screen_resolution_str else ''
                )
                if len(history) == 0:
                    new_messages = copy.deepcopy(messages)
                    new_messages[1]['content'][0]['text'] = (
                        'Please pick the next action based on the screenshot, '
                        'goal, and previous-action history.\n\n'
                        f'{resolution_line}'
                        f'Goal: {goal}\n\n'
                        'Previous actions:\nNo previous action.'
                    )
                    return new_messages
                history_string = ''
                for j, h in enumerate(history):
                    history_string += f'Step {j + 1}: {h}\n'
                history_string = history_string[:-1]
                new_messages.append({
                    'role': 'user',
                    'content': [
                        {
                            'text': (
                                'Please pick the next action based on the '
                                'screenshot, goal, and previous-action '
                                f'history.\n\n{resolution_line}'
                                f'Goal: {goal}\n\n'
                                f'Previous actions:\n{history_string}'
                            )
                        },
                        msg['content'][0],  # {"image": path}
                    ],
                })
                new_messages += copy.deepcopy(messages[i + 1:])
                return new_messages
        return copy.deepcopy(messages)

    # --------------------------------------------------------------------- step
    def step(self, goal: str) -> base_agent.AgentInteractionResult:
        result = {
            'ui_elements': None,
            'screenshot': None,
            'action_gen_response': None,
            'dummy_action': None,
            'dummy_action_translated': None,
            'action': None,
        }

        step_idx = len(self._screenshots)
        state = self.get_post_transition_state()
        result['ui_elements'] = state.ui_elements
        result['screenshot'] = state.pixels.copy()

        # Trap hook: screenshot tampering (S/T-layer)
        model_pixels = state.pixels
        history_pixels = state.pixels
        if self.trap_controller:
            model_pixels, history_pixels = self.trap_controller.on_screenshot(
                state.pixels, step_idx, state.ui_elements
            )

        screenshot = Image.fromarray(history_pixels)
        scr_width, scr_height = screenshot.size

        # Anthropic's API silently resizes images whose long edge exceeds
        # 1568 px (Sonnet 4.x limit). We pre-resize ourselves so the image
        # Claude sees matches the resolution stated in the prompt; ADB
        # execution then scales the model's coordinates back up to the
        # original device space.
        long_edge_limit = 1568
        long_edge = max(scr_width, scr_height)
        if long_edge > long_edge_limit:
            scale = long_edge_limit / long_edge
            llm_w, llm_h = int(scr_width * scale), int(scr_height * scale)
            llm_image = screenshot.resize((llm_w, llm_h), Image.LANCZOS)
        else:
            llm_w, llm_h = scr_width, scr_height
            llm_image = screenshot

        self._coord_scale_x = scr_width / llm_w
        self._coord_scale_y = scr_height / llm_h
        self._screen_resolution_str = f'{llm_w}x{llm_h}'

        task_output_dir = None
        if self.output_path:
            if goal not in self.task_name:
                task_output_dir = os.path.join(
                    self.output_path, goal.replace(' ', '_')[:50]
                )
            else:
                task_output_dir = os.path.join(
                    self.output_path, self.task_name[goal]
                )
            os.makedirs(task_output_dir, exist_ok=True)
            screenshot_file = os.path.join(
                task_output_dir, f'screenshot_{step_idx}.png'
            )
            screenshot.save(screenshot_file)
            llm_screenshot_file = os.path.join(
                task_output_dir, f'screenshot_{step_idx}_llm.png'
            )
            llm_image.save(llm_screenshot_file)
        else:
            screenshot_file = (
                f'/tmp/claude_{self.tmp_prefix}screenshot_{step_idx}.png'
            )
            screenshot.save(screenshot_file)
            llm_screenshot_file = (
                f'/tmp/claude_{self.tmp_prefix}screenshot_{step_idx}_llm.png'
            )
            llm_image.save(llm_screenshot_file)

        self._screenshots.append(screenshot)

        if step_idx == 0:
            self.cur_user_messages = [
                {'role': 'system', 'content': [{'text': _SYSTEM_PROMPT}]},
                {
                    'role': 'user',
                    'content': [
                        {
                            'text': (
                                'Please pick the next action based on the '
                                'screenshot, goal, and previous-action '
                                'history.\n\n'
                                f'Screen resolution: {self._screen_resolution_str} pixels.\n\n'
                                f'Goal: {goal}\n\n'
                                'Previous actions:\nNo previous action.'
                            )
                        },
                        {'image': llm_screenshot_file},
                    ],
                },
            ]
        else:
            self.cur_user_messages.append({
                'role': 'user',
                'content': [{'image': llm_screenshot_file}],
            })

        self.cur_user_messages = self.cut_current_messages(
            self.cur_user_messages, self.last_image
        )
        input_messages = self.convert_format(goal, self.cur_user_messages)

        # Trap Mode B: feed the tampered screenshot only to the model input.
        # Resize the tampered frame to the same LLM-facing space so coords
        # remain consistent with what Claude sees.
        if (self.trap_controller
                and not np.array_equal(model_pixels, history_pixels)):
            tampered_file = screenshot_file.replace('.png', '_trap.png')
            tampered_img = Image.fromarray(model_pixels)
            if (llm_w, llm_h) != tampered_img.size:
                tampered_img = tampered_img.resize((llm_w, llm_h), Image.LANCZOS)
            tampered_img.save(tampered_file)
            for msg in reversed(input_messages):
                if msg.get('role') == 'user' and msg.get('content'):
                    for item in msg['content']:
                        if 'image' in item:
                            item['image'] = tampered_file
                            break
                    break

        action_response, _, _ = self.llm.predict_mm(
            None, None, messages=input_messages
        )

        self.cur_user_messages.append({
            'role': 'assistant',
            'content': [{'text': action_response}],
        })

        result['action_gen_response'] = action_response
        print('========== claude response ==========')
        pprint.pprint(action_response)

        # Coordinate pass-through: model already emits absolute pixel coords
        # in the screenshot's space, so no rescale is needed.
        current_image_ele = update_image_size_({
            'image': screenshot_file,
            'width': scr_width,
            'height': scr_height,
        })

        dummy_action = None
        action = None
        try:
            # Be lenient: Claude may wrap the JSON in ```json fences or add
            # whitespace inside the <tool_call> block.
            tc_block = (
                action_response.split('<tool_call>')[-1]
                .split('</tool_call>')[0]
                .strip()
            )
            if tc_block.startswith('```'):
                tc_block = tc_block.strip('`')
                if tc_block.startswith('json'):
                    tc_block = tc_block[len('json'):].strip()
            dummy_action = json.loads(tc_block)
            dummy_action['arguments']['action'] = (
                dummy_action['arguments']['action'].replace('tap', 'click')
            )

            # Scale model-emitted coordinates from the LLM-facing image
            # space back to the actual device pixel space.
            sx, sy = self._coord_scale_x, self._coord_scale_y
            if sx != 1.0 or sy != 1.0:
                args = dummy_action.get('arguments', {})
                if isinstance(args.get('coordinate'), list) and len(args['coordinate']) >= 2:
                    args['coordinate'] = [
                        int(args['coordinate'][0] * sx),
                        int(args['coordinate'][1] * sy),
                    ]
                if isinstance(args.get('coordinate2'), list) and len(args['coordinate2']) >= 2:
                    args['coordinate2'] = [
                        int(args['coordinate2'][0] * sx),
                        int(args['coordinate2'][1] * sy),
                    ]
            if (
                len(self._actions) > 0
                and self._actions[-1]['arguments']['action'] == 'answer'
            ):
                dummy_action = {
                    'name': 'mobile_use',
                    'arguments': {'action': 'terminate', 'status': 'success'},
                }
                self.env.interaction_cache = (
                    self._actions[-1]['arguments']['text']
                )

            action, dummy_action_translated = (
                mobile_agent_utils.convert_mobile_agent_action_to_json_action(
                    dummy_action,
                    current_image_ele,
                    src_format='abs_origin',
                    tgt_format='abs_origin',
                )
            )
            result['dummy_action'] = dummy_action
            result['dummy_action_translated'] = dummy_action_translated
            result['action'] = action

            # Trap A-layer hook
            original_action_type = action.action_type
            if self.trap_controller:
                action, dummy_action = self.trap_controller.on_action(
                    action, dummy_action, step_idx
                )
                if action.action_type != original_action_type:
                    print('========== ACTUAL EXECUTION ==========')
                    print(f'  Model intended: {original_action_type}')
                    print(f'  Trap executed:  {action.action_type} at '
                          f'({action.x}, {action.y})')
                elif hasattr(action, '_trap_info'):
                    trap_info = action._trap_info
                    print('========== ACTUAL EXECUTION ==========')
                    print(f'  Model intended: {trap_info.get("original")}')
                    print(f'  Trap executed:  {action.action_type} at '
                          f'{trap_info.get("offset")}')

        except (seeact_utils.ParseActionError, json.JSONDecodeError,
                KeyError, TypeError, IndexError) as e:
            print(f'[WARN] Claude action parse failed '
                  f'({type(e).__name__}): {e}')
            action = json_action.JSONAction(action_type=json_action.UNKNOWN)
            result['action'] = action
        else:
            if (self.trap_controller
                    and self.trap_controller.should_block_execution(step_idx)):
                print('========== ACTUAL EXECUTION ==========')
                print('  [TRAP] Execution BLOCKED (State Deadlock)')
            else:
                actuation.execute_adb_action(
                    action,
                    [],
                    self.env.logical_screen_size,
                    self.env.controller,
                )
            self._actions.append(dummy_action)

        if task_output_dir:
            with open(
                os.path.join(task_output_dir, 'action.jsonl'),
                'w', encoding='utf-8',
            ) as f:
                for item in self._actions:
                    f.write(json.dumps(item, ensure_ascii=False) + '\n')

        return base_agent.AgentInteractionResult(
            done=action.action_type == json_action.STATUS,
            data=result,
        )
