"""MAI-UI Agent for Android World.

Based on Tongyi-MAI/MAI-UI (Qwen3-VL backbone).
Uses <thinking> + <tool_call> output format with navigation system prompt.
Coordinate system: [0, 999] normalized.

Reference: https://github.com/Tongyi-MAI/MAI-UI
"""

import copy
import json
import os
import pprint
import traceback

import numpy as np
from android_world.agents import base_agent
from android_world.agents import seeact_utils
from android_world.agents import mobile_agent_utils_new as mobile_agent_utils
from android_world.agents import new_json_action as json_action
from android_world.agents.coordinate_resize import update_image_size_
from android_world.env import actuation
from android_world.env import interface
from PIL import Image


_SYSTEM_PROMPT = '''You are a GUI agent. You are given a task and your action history, with screenshots. You need to perform the next action to complete the task.

## Output Format
For each function call, return the thinking process in <thinking> </thinking> tags, and a json object with function name and arguments within <tool_call></tool_call> XML tags:
<thinking>
...
</thinking>
<tool_call>
{"name": "mobile_use", "arguments": <args-json-object>}
</tool_call>

## Action Space

{"action": "click", "coordinate": [x, y]}
{"action": "long_press", "coordinate": [x, y]}
{"action": "type", "text": ""}
{"action": "swipe", "direction": "up or down or left or right", "coordinate": [x, y]}
{"action": "open", "text": "app_name"}
{"action": "drag", "start_coordinate": [x1, y1], "end_coordinate": [x2, y2]}
{"action": "system_button", "button": "button_name"} # Options: back, home, menu, enter
{"action": "wait"}
{"action": "terminate", "status": "success or fail"}
{"action": "answer", "text": "xxx"}

## Note
- Write a small plan and finally summarize your next action (with its target element) in one sentence in <thinking></thinking> part.
- Available Apps: `["Camera","Chrome","Clock","Contacts","Dialer","Files","Settings","Markor","Tasks","Simple Draw Pro","Simple Gallery Pro","Simple SMS Messenger","Audio Recorder","Pro Expense","Broccoli APP","OSMand","VLC","Joplin","Retro Music","OpenTracks","Simple Calendar Pro"]`.
You should use the `open` action to open the app as possible as you can, because it is the fast way to open the app.
- You must follow the Action Space strictly, and return the correct json object within <thinking> </thinking> and <tool_call></tool_call> XML tags.'''

# Swipe distance in [0,999] coordinate space (~30% of screen)
_SWIPE_DISTANCE = 300


def _direction_to_coordinates(direction, coordinate=None):
    """Convert MAI-UI swipe direction to start/end coordinates.

    Args:
        direction: 'up', 'down', 'left', 'right'
        coordinate: optional [x, y] center point (0-999 scale)

    Returns:
        (start_coord, end_coord) as [x, y] lists
    """
    cx, cy = coordinate if coordinate else [500, 500]
    d = _SWIPE_DISTANCE
    if direction == 'up':
        return [cx, cy], [cx, max(0, cy - d)]
    elif direction == 'down':
        return [cx, cy], [cx, min(999, cy + d)]
    elif direction == 'left':
        return [cx, cy], [max(0, cx - d), cy]
    elif direction == 'right':
        return [cx, cy], [min(999, cx + d), cy]
    return [cx, cy], [cx, cy]


def _normalize_action(dummy_action):
    """Normalize MAI-UI specific actions to the format expected by
    convert_mobile_agent_action_to_json_action.

    - swipe with direction → swipe with coordinate/coordinate2
    - drag with start/end → swipe with coordinate/coordinate2
    """
    args = dummy_action.get('arguments', {})
    action = args.get('action', '')

    if action == 'swipe' and 'direction' in args:
        direction = args['direction']
        coord = args.get('coordinate')
        start, end = _direction_to_coordinates(direction, coord)
        args['coordinate'] = start
        args['coordinate2'] = end
        args.pop('direction', None)

    elif action == 'drag':
        args['action'] = 'swipe'
        args['coordinate'] = args.pop('start_coordinate', [500, 500])
        args['coordinate2'] = args.pop('end_coordinate', [500, 500])

    elif action == 'terminate':
        status = args.get('status', 'fail')
        if status == 'success':
            args['status'] = 'success'
        else:
            args['status'] = 'failure'

    elif action == 'system_button':
        button = args.get('button', 'back').lower()
        button_map = {'back': 'Back', 'home': 'Home', 'menu': 'Menu', 'enter': 'Enter'}
        args['button'] = button_map.get(button, button.capitalize())

    dummy_action['arguments'] = args
    return dummy_action


class MAIUIAgent(base_agent.EnvironmentInteractingAgent):
    """MAI-UI agent for Android World.

    Uses persistent conversation history with <thinking> + <tool_call> format.
    Coordinate system: [0, 999] (qwen-vl format, same as GUI-Owl-1.5).
    """

    def __init__(
        self,
        env: interface.AsyncEnv,
        vllm,
        name: str = 'MAIUI',
        max_history_images: int = 3,
        output_path: str = '',
        task_name: dict = None,
        api_key: str = None,
        url: str = None,
    ):
        super().__init__(env, name)
        self._actions = []
        self._screenshots = []
        self.cur_user_messages = []
        self.output_path = output_path
        if self.output_path and not os.path.exists(self.output_path):
            os.mkdir(self.output_path)
        self.vllm = vllm
        self.url = url
        self.api_key = api_key
        self.task_name = task_name or {}
        self.last_image = max_history_images
        self.tmp_prefix = ""
        self.trap_controller = None

    def reset(self, go_home: bool = False) -> None:
        super().reset(go_home)
        self.env.hide_automation_ui()
        self._actions.clear()
        self._screenshots.clear()
        self.cur_user_messages.clear()

    def cut_current_messages(self, messages, last_image=2):
        """Keep images only in the last `last_image` user turns."""
        non_empty_user_indices = []
        for i, msg in enumerate(messages):
            if msg.get('role') == 'user' and msg.get('content') and len(msg['content']) > 0:
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
        """Rebuild input messages with action-history text."""
        new_messages = copy.deepcopy(messages[:1])
        history = []
        for i, msg in enumerate(messages):
            if msg.get('role') == 'user' and (
                msg['content'] == []
                or (len(msg['content']) == 1 and 'text' in msg['content'][0])
            ):
                # Extract action summary from <thinking> or plain text
                resp = messages[i + 1]['content'][0]['text']
                # Try to extract from <thinking> tags
                if '<thinking>' in resp:
                    think = resp.split('<thinking>')[-1].split('</thinking>')[0].strip()
                    # Take last sentence as action summary
                    sentences = [s.strip() for s in think.split('.') if s.strip()]
                    summary = sentences[-1] if sentences else think[:100]
                else:
                    summary = resp.split('<tool_call>')[0].strip()[:100]
                history.append(summary)

            if i != 1 and msg.get('role') == 'user' and msg['content'] != []:
                if len(history) == 0:
                    new_messages = copy.deepcopy(messages)
                    new_messages[1]['content'][0]['text'] = (
                        f'{goal}\n\nPrevious actions:\nNo previous action.'
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
                                f'{goal}\n\n'
                                f'Previous actions:\n{history_string}'
                            )
                        },
                        msg['content'][0],  # {"image": path}
                    ],
                })
                new_messages += copy.deepcopy(messages[i + 1:])
                return new_messages

        return copy.deepcopy(messages)

    def get_task_name(self, suite) -> None:
        for name, instances in suite.items():
            self.task_name[instances[0].goal] = name

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

        # Trap hook: modify screenshot (S-Layer / T-Layer)
        model_pixels = state.pixels
        history_pixels = state.pixels
        if self.trap_controller:
            model_pixels, history_pixels = self.trap_controller.on_screenshot(
                state.pixels, step_idx, state.ui_elements
            )

        screenshot = Image.fromarray(history_pixels)

        # Save screenshot to disk
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
            if not os.path.exists(task_output_dir):
                os.mkdir(task_output_dir)
            screenshot_file = os.path.join(task_output_dir, f'screenshot_{step_idx}.png')
            screenshot.save(screenshot_file)
            with open(os.path.join(task_output_dir, 'action.jsonl'), 'w', encoding='utf-8') as f:
                for item in self._actions:
                    f.write(json.dumps(item, ensure_ascii=False) + '\n')
        else:
            screenshot_file = f'/tmp/mai_ui_{self.tmp_prefix}screenshot_{step_idx}.png'
            screenshot.save(screenshot_file)

        self._screenshots.append(screenshot)

        # Build / extend persistent message history
        if step_idx == 0:
            self.cur_user_messages = [
                {
                    'role': 'system',
                    'content': [{'text': _SYSTEM_PROMPT}],
                },
                {
                    'role': 'user',
                    'content': [
                        {
                            'text': (
                                f'{goal}\n\n'
                                f'Previous actions:\nNo previous action.'
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

        # Trap Mode B: use tampered screenshot for model input only (T-Layer)
        if self.trap_controller and not np.array_equal(model_pixels, history_pixels):
            tampered_file = screenshot_file.replace('.png', '_trap.png')
            Image.fromarray(model_pixels).save(tampered_file)
            for msg in reversed(input_messages):
                if msg.get('role') == 'user' and msg.get('content'):
                    for item in msg['content']:
                        if 'image' in item:
                            item['image'] = tampered_file
                            break
                    break

        action_response, _, _ = self.vllm.predict_mm(None, None, messages=input_messages)

        self.cur_user_messages.append({
            'role': 'assistant',
            'content': [{'text': action_response}],
        })

        result['action_gen_response'] = action_response
        print('========== mai_ui response ==========')
        pprint.pprint(action_response)

        # Coordinate conversion: qwen-vl (0-999) → abs_origin
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

            # If previous action was 'answer', auto-terminate now
            if (
                len(self._actions) > 0
                and self._actions[-1]['arguments']['action'] == 'answer'
            ):
                dummy_action = {
                    'name': 'mobile_use',
                    'arguments': {'action': 'terminate', 'status': 'success'},
                }
                self.env.interaction_cache = self._actions[-1]['arguments']['text']

            # Normalize MAI-UI specific actions (swipe direction, drag, etc.)
            dummy_action = _normalize_action(dummy_action)

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

            # Trap hook: modify action (A-Layer)
            original_action_type = action.action_type
            if self.trap_controller:
                action, dummy_action = self.trap_controller.on_action(action, dummy_action, step_idx)
                if action.action_type != original_action_type:
                    _replace_map = {
                        'click': ['click', 'clicked', 'tap', 'tapped', 'pressing'],
                        'long_press': ['long press', 'long-press', 'long pressed', 'long-pressed'],
                        'double_tap': ['double tap', 'double-tap', 'double tapped', 'double-tapped'],
                    }
                    new_words = _replace_map.get(action.action_type, [action.action_type])
                    stored_text = self.cur_user_messages[-1]['content'][0]['text']
                    for old_type, old_words in _replace_map.items():
                        if old_type == action.action_type:
                            continue
                        for w in old_words:
                            if w in stored_text.lower():
                                stored_text = stored_text.replace(w, new_words[0])
                                stored_text = stored_text.replace(w.capitalize(), new_words[0].capitalize())
                                break
                    self.cur_user_messages[-1]['content'][0]['text'] = stored_text
                    print(f'========== ACTUAL EXECUTION ==========')
                    print(f'  Model intended: {original_action_type}')
                    print(f'  Trap executed:  {action.action_type} at ({action.x}, {action.y})')
                elif hasattr(action, '_trap_info'):
                    trap_info = action._trap_info
                    print(f'========== ACTUAL EXECUTION ==========')
                    print(f'  Model intended: {trap_info.get("original")}')
                    print(f'  Trap executed:  {action.action_type} at {trap_info.get("offset")}')

        except (seeact_utils.ParseActionError, json.JSONDecodeError, KeyError, TypeError) as e:
            print(f'[WARN] Action parse failed ({type(e).__name__}): {e}')
            action = json_action.JSONAction(action_type=json_action.UNKNOWN)
            result['action'] = action
        else:
            # Trap hook: block execution (State Deadlock)
            if self.trap_controller and self.trap_controller.should_block_execution(step_idx):
                print(f'========== ACTUAL EXECUTION ==========')
                print(f'  [TRAP] Execution BLOCKED (State Deadlock)')
            else:
                actuation.execute_adb_action(
                    action,
                    [],
                    self.env.logical_screen_size,
                    self.env.controller,
                )
            self._actions.append(dummy_action)

        if task_output_dir:
            with open(os.path.join(task_output_dir, 'action.jsonl'), 'w', encoding='utf-8') as f:
                for item in self._actions:
                    f.write(json.dumps(item, ensure_ascii=False) + '\n')

        return base_agent.AgentInteractionResult(
            done=action.action_type == json_action.STATUS,
            data=result,
        )
