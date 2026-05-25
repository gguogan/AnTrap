"""Gemini 3 agent for AndroidWorld — qwen3vl-style (no SoM, raw screenshots).

This is a *close port* of ``qwen3vl.Qwen3VLAgent`` with the LLM call swapped
to ``Gemini3RestWrapper``. The action space is the qwen-vl ``mobile_use``
tool catalog at 0-999 normalized coordinates, which happens to match Google's
own 1000x1000 grid used for Gemini computer-use, so coordinate handling is
identical. No Set-of-Marks annotations, no UI tree — model gets the raw
screenshot and a text history of prior actions, exactly like qwen3vl.
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
from android_world.agents import infer_gemini3
from android_world.agents import mobile_agent_utils_new as mobile_agent_utils
from android_world.agents import new_json_action as json_action
from android_world.agents import seeact_utils
from android_world.agents.coordinate_resize import update_image_size_
from android_world.env import actuation
from android_world.env import adb_utils
from android_world.env import interface
from PIL import Image


# Same tool schema as qwen3vl / gui_owl_1_5. The 1000x1000 grid is a natural
# fit for Gemini — Google's own computer-use models (Gemini 2.5 CU, Gemini 3
# agentic) use the same normalized coordinate convention. We keep the XML
# `<tool_call>` convention rather than switching to Gemini's native function
# calling so the parsing + coordinate-conversion pipeline is shared with
# qwen3vl byte-for-byte.
_SYSTEM_PROMPT = '''# Tools

You may call one or more functions to assist with the user query.

You are provided with function signatures within <tools></tools> XML tags:
<tools>
{"type": "function", "function": {"name_for_human": "mobile_use", "name": "mobile_use", "description": "Use a touchscreen to interact with a mobile device, and take screenshots.\\n* This is an interface to a mobile device with touchscreen. You can perform actions like clicking, typing, swiping, etc.\\n* Some applications may take time to start or process actions, so you may need to wait and take successive screenshots to see the results of your actions.\\n* The screen's resolution is 1000x1000.\\n* Make sure to click any buttons, links, icons, etc with the cursor tip in the center of the element. Don't click boxes on their edges unless asked.", "parameters": {"properties": {"action": {"description": "The action to perform. The available actions are:\\n* `key`: Perform a key event on the mobile device.\\n    - This supports adb's `keyevent` syntax.\\n    - Examples: \\"volume_up\\", \\"volume_down\\", \\"power\\", \\"camera\\", \\"clear\\".\\n* `click`: Click the point on the screen with coordinate (x, y).\\n* `long_press`: Press the point on the screen with coordinate (x, y) for specified seconds.\\n* `swipe`: Swipe from the starting point with coordinate (x, y) to the end point with coordinates2 (x2, y2).\\n* `type`: Input the specified text into the activated input box.\\n* `answer`: Terminate the current task and output the answer.\\n* `system_button`: Press the system button.\\n* `open`: Open an app on the device.\\n* `wait`: Wait specified seconds for the change to happen.\\n* `terminate`: Terminate the current task and report its completion status.", "enum": ["key", "click", "long_press", "swipe", "type", "answer", "system_button", "open", "wait", "terminate"], "type": "string"}, "coordinate": {"description": "(x, y): The x (pixels from the left edge) and y (pixels from the top edge) coordinates to move the mouse to. Required only by `action=click`, `action=long_press`, and `action=swipe`.", "type": "array"}, "coordinate2": {"description": "(x, y): The x (pixels from the left edge) and y (pixels from the top edge) coordinates to move the mouse to. Required only by `action=swipe`.", "type": "array"}, "text": {"description": "Required only by `action=key`, `action=type`, `action=answer`, and `action=open`.", "type": "string"}, "time": {"description": "The seconds to wait. Required only by `action=long_press` and `action=wait`.", "type": "number"}, "button": {"description": "Back means returning to the previous interface, Home means returning to the desktop, Menu means opening the application background menu, and Enter means pressing the enter. Required only by `action=system_button`", "enum": ["Back", "Home", "Menu", "Enter"], "type": "string"}, "status": {"description": "The status of the task. Required only by `action=terminate`.", "type": "string", "enum": ["success", "failure"]}}, "required": ["action"], "type": "object"}, "args_format": "Format the arguments as a JSON object."}}
</tools>

For each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:
<tool_call>
{"name": <function-name>, "arguments": <args-json-object>}
</tool_call>

# Response format

Respond every step with exactly two parts, in this order:
1) `Action:` followed by one short imperative sentence describing what to do.
2) A single `<tool_call>...</tool_call>` block containing only the JSON: {"name": <function-name>, "arguments": <args-json-object>}.

Rules:
- Output Action first, then the <tool_call>. Nothing else outside these two parts.
- Coordinates are normalized to the 0-999 grid described in the tool schema.
- When using `action=open`, the `text` argument must be one of the canonical AndroidWorld app names listed below.
- Finish the task with action=terminate (status="success" or "failure").

Available apps for `action=open` (use these exact names, lowercase):
''' + gui_owl.all_apps_str


class Gemini3Agent(base_agent.EnvironmentInteractingAgent):
    """Gemini 3 agent using the qwen3vl action surface + raw screenshots."""

    def __init__(
        self,
        env: interface.AsyncEnv,
        llm: 'infer_gemini3.Gemini3RestWrapper',
        name: str = 'Gemini3',
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
        self.tmp_prefix = ''  # e.g. "w0_" for parallel /tmp isolation
        self.trap_controller = None

    # ------------------------------------------------------------------ reset
    def reset(self, go_home: bool = False) -> None:
        super().reset(go_home)
        self.env.hide_automation_ui()
        self._actions.clear()
        self._screenshots.clear()
        self.cur_user_messages.clear()

        # Mirror ui_tars: press home + swipe-up so every task starts from the
        # app drawer. Gives the model a consistent entrypoint.
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
            logging.warning('Gemini3 initial swipe-up failed: %s', e)

    def get_task_name(self, suite) -> None:
        for _, instances in suite.items():
            self.task_name[instances[0].goal] = instances[0].name

    # ------------------------------------- history window / history rendering
    # Copied from qwen3vl so semantics match byte-for-byte.
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
        new_messages = copy.deepcopy(messages[:1])
        history = []
        for i, msg in enumerate(messages):
            if msg.get('role') == 'user' and (
                msg['content'] == []
                or (len(msg['content']) == 1 and 'text' in msg['content'][0])
            ):
                history.append(
                    messages[i + 1]['content'][0]['text']
                    .split('Action:')[-1]
                    .split('<tool_call>')[0]
                    .strip()
                )

            if i != 1 and msg.get('role') == 'user' and msg['content'] != []:
                if len(history) == 0:
                    new_messages = copy.deepcopy(messages)
                    new_messages[1]['content'][0]['text'] = (
                        'Please generate the next move according to the UI '
                        'screenshot, instruction and previous actions.\n\n'
                        f'Instruction: {goal}\n\n'
                        'Previous actions:\nNo previous action.'
                    )
                    return new_messages
                history_string = ''
                for j, h in enumerate(history):
                    history_string += f'Step{j + 1}: {h}\n'
                history_string = history_string[:-1]
                new_messages.append({
                    'role': 'user',
                    'content': [
                        {
                            'text': (
                                'Please generate the next move according to '
                                'the UI screenshot, instruction and previous '
                                f'actions.\n\nInstruction: {goal}\n\n'
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

        # Pick where to dump the screenshot (per-task dir if we have one, else
        # tmp so the wrapper can still read the file).
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
        else:
            screenshot_file = (
                f'/tmp/gemini3_{self.tmp_prefix}screenshot_{step_idx}.png'
            )
            screenshot.save(screenshot_file)

        self._screenshots.append(screenshot)

        # Build / extend persistent message history.
        if step_idx == 0:
            self.cur_user_messages = [
                {'role': 'system', 'content': [{'text': _SYSTEM_PROMPT}]},
                {
                    'role': 'user',
                    'content': [
                        {
                            'text': (
                                'Please generate the next move according to '
                                'the UI screenshot, instruction and previous '
                                f'actions.\n\nInstruction: {goal}\n\n'
                                'Previous actions:\nNo previous action.'
                            )
                        },
                        {'image': screenshot_file},
                    ],
                },
            ]
        else:
            self.cur_user_messages.append({
                'role': 'user',
                'content': [{'image': screenshot_file}],
            })

        self.cur_user_messages = self.cut_current_messages(
            self.cur_user_messages, self.last_image
        )
        input_messages = self.convert_format(goal, self.cur_user_messages)

        # Trap Mode B: feed the tampered screenshot only to the model input.
        if (self.trap_controller
                and not np.array_equal(model_pixels, history_pixels)):
            tampered_file = screenshot_file.replace('.png', '_trap.png')
            Image.fromarray(model_pixels).save(tampered_file)
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
        print('========== gemini3 response ==========')
        pprint.pprint(action_response)

        # Coordinate conversion: qwen-vl (0-999) -> abs_origin
        scr_width, scr_height = screenshot.size
        current_image_ele = update_image_size_({
            'image': screenshot_file,
            'width': scr_width,
            'height': scr_height,
        })

        dummy_action = None
        action = None
        try:
            dummy_action = (
                action_response.split('<tool_call>')[-1]
                .split('</tool_call>')[0]
                .strip()
            )
            dummy_action = json.loads(dummy_action)
            dummy_action['arguments']['action'] = (
                dummy_action['arguments']['action'].replace('tap', 'click')
            )
            # If the previous action was `answer`, auto-terminate this step.
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
                    src_format='qwen-vl',
                    tgt_format='abs_origin',
                )
            )
            result['dummy_action'] = dummy_action
            result['dummy_action_translated'] = dummy_action_translated
            result['action'] = action

            # Trap hook: rewrite action (A-layer)
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
            print(f'[WARN] Gemini3 action parse failed '
                  f'({type(e).__name__}): {e}')
            action = json_action.JSONAction(action_type=json_action.UNKNOWN)
            result['action'] = action
        else:
            # Trap hook: block execution (State Deadlock)
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
