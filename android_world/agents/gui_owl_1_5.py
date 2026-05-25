# Copyright 2025 The android_world Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""GUI-Owl-1.5 for Android.

Aligned with mobileagent_official/android_world/agents/gui_owl.py:
- Persistent cur_user_messages with cut_current_messages + convert_format
- src_format='qwen-vl' coordinate conversion (/ 999)
- No date info in user query
- System prompt without 'interact' action
- reset() without extra press_home / swipe
- answer action does NOT terminate immediately; next step auto-terminates
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


_SYSTEM_PROMPT = '''# Tools

You may call one or more functions to assist with the user query.

You are provided with function signatures within <tools></tools> XML tags:
<tools>
{"type": "function", "function": {"name_for_human": "mobile_use", "name": "mobile_use", "description": "Use a touchscreen to interact with a mobile device, and take screenshots.\n* This is an interface to a mobile device with touchscreen. You can perform actions like clicking, typing, swiping, etc.\n* Some applications may take time to start or process actions, so you may need to wait and take successive screenshots to see the results of your actions.\n* The screen\'s resolution is 1000x1000.\n* Make sure to click any buttons, links, icons, etc with the cursor tip in the center of the element. Don\'t click boxes on their edges unless asked.", "parameters": {"properties": {"action": {"description": "The action to perform. The available actions are:\n* `key`: Perform a key event on the mobile device.\n    - This supports adb\'s `keyevent` syntax.\n    - Examples: \\"volume_up\\", \\"volume_down\\", \\"power\\", \\"camera\\", \\"clear\\".\n* `click`: Click the point on the screen with coordinate (x, y).\n* `long_press`: Press the point on the screen with coordinate (x, y) for specified seconds.\n* `swipe`: Swipe from the starting point with coordinate (x, y) to the end point with coordinates2 (x2, y2).\n* `type`: Input the specified text into the activated input box.\n* `system_button`: Press the system button.\n* `open`: Open an app on the device.\n* `wait`: Wait specified seconds for the change to happen.\n* `answer`: Terminate the current task and output the answer.\n* `terminate`: Terminate the current task and report its completion status.", "enum": ["key", "click", "long_press", "swipe", "type", "system_button", "open", "wait", "answer", "terminate"], "type": "string"}, "coordinate": {"description": "(x, y): The x (pixels from the left edge) and y (pixels from the top edge) coordinates to move the mouse to. Required only by `action=click`, `action=long_press`, and `action=swipe`.", "type": "array"}, "coordinate2": {"description": "(x, y): The x (pixels from the left edge) and y (pixels from the top edge) coordinates to move the mouse to. Required only by `action=swipe`.", "type": "array"}, "text": {"description": "Required only by `action=key`, `action=type`, `action=open`, `action=answer`.", "type": "string"}, "time": {"description": "The seconds to wait. Required only by `action=long_press` and `action=wait`.", "type": "number"}, "button": {"description": "Back means returning to the previous interface, Home means returning to the desktop, Menu means opening the application background menu, and Enter means pressing the enter. Required only by `action=system_button`", "enum": ["Back", "Home", "Menu", "Enter"], "type": "string"}, "status": {"description": "The status of the task. Required only by `action=terminate`.", "type": "string", "enum": ["success", "failure"]}}, "required": ["action"], "type": "object"}, "args_format": "Format the arguments as a JSON object."}}
</tools>

For each function call, return a json object with function name and arguments within <tool_call></tool_call> XML tags:
<tool_call>
{"name": <function-name>, "arguments": <args-json-object>}
</tool_call>

# Response format

Response format for every step:
1) Action: a short imperative describing what to do in the UI.
2) A single <tool_call>...</tool_call> block containing only the JSON: {"name": <function-name>, "arguments": <args-json-object>}.

Rules:
- Output exactly in the order: Action, <tool_call>.
- Be brief: one for Action.
- Do not output anything else outside those two parts.
- If finishing, use action=terminate in the tool call.'''


class GUIOwl15Agent(base_agent.EnvironmentInteractingAgent):
    """GUI-Owl-1.5 agent aligned with mobileagent_official gui_owl.py."""

    def __init__(
        self,
        env: interface.AsyncEnv,
        vllm,
        name: str = 'GUIOwl15',
        max_history_images: int = 5,
        output_path: str = '',
        task_name: dict = None,
        api_key: str = None,
        url: str = None,
    ):
        # Match gui_owl.py: do not pass transition_pause to super (default 1.0,
        # main script sets it to None for android_world)
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
        self.trap_controller = None  # Set externally for trap experiments

    def reset(self, go_home: bool = False) -> None:
        """Reset matching gui_owl.py: no extra press_home / swipe."""
        super().reset(go_home)
        self.env.hide_automation_ui()
        self._actions.clear()
        self._screenshots.clear()
        self.cur_user_messages.clear()

    def cut_current_messages(self, messages, last_image=2):
        """Keep images only in the last `last_image` user turns (same as gui_owl.py)."""
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
                # Keep only the text item (drop the image) for the first user turn
                messages[index]['content'] = [messages[index]['content'][0]]
            else:
                messages[index]['content'] = []

        return messages

    def convert_format(self, goal, messages):
        """Rebuild input messages with action-history text in the oldest visible turn.

        Adapted from gui_owl.py for {"image": path} / {"text": ...} format instead
        of the OpenAI {"type": "image_url", ...} format.
        """
        new_messages = copy.deepcopy(messages[:1])
        history = []
        for i, msg in enumerate(messages):
            # Identify pruned user turns: empty content OR text-only (index 1 after cut)
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
                # First non-index-1 user turn that still has an image
                if len(history) == 0:
                    new_messages = copy.deepcopy(messages)
                    new_messages[1]['content'][0]['text'] = (
                        f'Please generate the next move according to the UI screenshot, '
                        f'instruction and previous actions.\n\n'
                        f'Instruction: {goal}\n\n'
                        f'Previous actions:\nNo previous action.'
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
                                f'Please generate the next move according to the UI screenshot, '
                                f'instruction and previous actions.\n\n'
                                f'Instruction: {goal}\n\n'
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

        screenshot = Image.fromarray(history_pixels)  # History / file save

        # Determine screenshot file path (must be on disk for {"image": path} format)
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
            screenshot_file = f'/tmp/gui_owl_1_5_screenshot_{step_idx}.png'
            screenshot.save(screenshot_file)

        self._screenshots.append(screenshot)

        # Build / extend the persistent message history
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
                                f'Please generate the next move according to the UI screenshot, '
                                f'instruction and previous actions.\n\n'
                                f'Instruction: {goal}\n\n'
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
            # Replace the last image in input_messages (current step's screenshot)
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
        input_messages.append({
            'role': 'assistant',
            'content': [{'text': action_response}],
        })

        result['action_gen_response'] = action_response
        print('========== gui_owl_1_5 response ==========')
        pprint.pprint(action_response)

        # Screen dimensions for qwen-vl -> abs_origin coordinate conversion
        # Use actual PIL screenshot dims + update_image_size_ (same as gui_owl.py's
        # fetch_resized_image) so resized_width/height match what the model sees.
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
            # If the previous action was 'answer', auto-terminate now (same as gui_owl.py)
            if (
                len(self._actions) > 0
                and self._actions[-1]['arguments']['action'] == 'answer'
            ):
                dummy_action = {
                    'name': 'mobile_use',
                    'arguments': {'action': 'terminate', 'status': 'success'},
                }
                self.env.interaction_cache = self._actions[-1]['arguments']['text']

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
                    # Silent word replacement in history response
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
