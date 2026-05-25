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

"""GUI-Owl-1.5 Agent utility functions for prompt building and action parsing.

Based on Mobile-Agent-v3.5 format:
https://github.com/X-PLUG/MobileAgent/tree/main/Mobile-Agent-v3.5
"""

import json
import re
from datetime import datetime
from typing import Optional


SYSTEM_PROMPT = '''# Tools

You may call one or more functions to assist with the user query.

You are provided with function signatures within <tools></tools> XML tags:
<tools>
{"type": "function", "function": {"name_for_human": "mobile_use", "name": "mobile_use", "description": "Use a touchscreen to interact with a mobile device, and take screenshots.\\n* This is an interface to a mobile device with touchscreen. You can perform actions like clicking, typing, swiping, etc.\\n* Some applications may take time to start or process actions, so you may need to wait and take successive screenshots to see the results of your actions.\\n* The screen's resolution is 1000x1000.\\n* Make sure to click any buttons, links, icons, etc with the cursor tip in the center of the element. Don't click boxes on their edges unless asked.", "parameters": {"properties": {"action": {"description": "The action to perform. The available actions are:\\n* `key`: Perform a key event on the mobile device.\\n    - This supports adb's `keyevent` syntax.\\n    - Examples: \\"volume_up\\", \\"volume_down\\", \\"power\\", \\"camera\\", \\"clear\\".\\n* `click`: Click the point on the screen with coordinate (x, y).\\n* `long_press`: Press the point on the screen with coordinate (x, y) for specified seconds.\\n* `swipe`: Swipe from the starting point with coordinate (x, y) to the end point with coordinates2 (x2, y2).\\n* `type`: Input the specified text into the activated input box.\\n* `system_button`: Press the system button.\\n* `open`: Open an app on the device.\\n* `wait`: Wait specified seconds for the change to happen.\\n* `answer`: Terminate the current task and output the answer.\\n* `interact`: Resolve the blocking window by interacting with the user.\\n* `terminate`: Terminate the current task and report its completion status.", "enum": ["key", "click", "long_press", "swipe", "type", "system_button", "open", "wait", "answer", "interact", "terminate"], "type": "string"}, "coordinate": {"description": "(x, y): The x (pixels from the left edge) and y (pixels from the top edge) coordinates to move the mouse to. Required only by `action=click`, `action=long_press`, and `action=swipe`.", "type": "array"}, "coordinate2": {"description": "(x, y): The x (pixels from the left edge) and y (pixels from the top edge) coordinates to move the mouse to. Required only by `action=swipe`.", "type": "array"}, "text": {"description": "Required only by `action=key`, `action=type`, `action=open`, `action=answer`,and `action=interact`.", "type": "string"}, "time": {"description": "The seconds to wait. Required only by `action=long_press` and `action=wait`.", "type": "number"}, "button": {"description": "Back means returning to the previous interface, Home means returning to the desktop, Menu means opening the application background menu, and Enter means pressing the enter. Required only by `action=system_button`", "enum": ["Back", "Home", "Menu", "Enter"], "type": "string"}, "status": {"description": "The status of the task. Required only by `action=terminate`.", "type": "string", "enum": ["success", "failure"]}}, "required": ["action"], "type": "object"}, "args_format": "Format the arguments as a JSON object."}}
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


def build_user_query(goal: str, history_text: str) -> str:
    """Build the user query string with goal, date context, and history.

    Args:
        goal: The task goal/instruction.
        history_text: Text summary of previous actions.

    Returns:
        Formatted user query string.
    """
    today = datetime.today()
    weekday_names = [
        "Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday",
    ]
    formatted_date = today.strftime("%Y-%m-%d") + " " + weekday_names[today.weekday()]
    date_info = f"Today's date is: {formatted_date}. "

    previous_actions = history_text if history_text else "None"

    return (
        f"Please generate the next move according to the UI screenshot, "
        f"instruction and previous actions.\n\n"
        f"Instruction: {date_info}{goal}\n\n"
        f"Previous actions:\n{previous_actions}"
    )


def parse_gui_owl_1_5_response(response_text: str) -> Optional[dict]:
    """Extract and parse JSON from <tool_call>...</tool_call> block.

    Args:
        response_text: The model's raw text response.

    Returns:
        Parsed dict with "name" and "arguments" keys, or None on failure.
    """
    match = re.search(r'<tool_call>\s*(.*?)\s*</tool_call>', response_text, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group(1))
            # Handle nested string arguments
            if isinstance(parsed.get("arguments"), str):
                parsed["arguments"] = json.loads(parsed["arguments"])
            return parsed
        except json.JSONDecodeError:
            pass

    # Fallback: try splitting on <tool_call>\n and }}\n
    try:
        tool_call_block = response_text.split("<tool_call>\n")[1]
        json_str = tool_call_block.split("}}\n")[0] + "}}"
        parsed = json.loads(json_str)
        if isinstance(parsed.get("arguments"), str):
            parsed["arguments"] = json.loads(parsed["arguments"])
        return parsed
    except (IndexError, json.JSONDecodeError):
        pass

    return None


def extract_action_summary(response_text: str) -> str:
    """Extract the 'Action: ...' text from model response for history.

    Args:
        response_text: The model's raw text response.

    Returns:
        The action summary text, or the full response if parsing fails.
    """
    if "Action:" in response_text and "<tool_call>" in response_text:
        return response_text.split("Action:")[1].split("<tool_call>")[0].strip()
    if "<tool_call>" in response_text:
        return response_text.split("<tool_call>")[0].strip()
    return response_text.strip()[:200]


def rescale_coord(coord: int, dimension: int) -> int:
    """Rescale a coordinate from 0-1000 range to pixel dimension.

    Args:
        coord: Coordinate in 0-1000 range.
        dimension: Target dimension in pixels.

    Returns:
        Pixel coordinate.
    """
    return round(coord / 1000 * dimension)


def convert_gui_owl_1_5_action_to_json_action(
    action_dict: dict, width: int, height: int
) -> tuple[str, dict, dict]:
    """Convert GUI-Owl-1.5 action dict to JSONAction compatible format.

    Args:
        action_dict: Parsed dict with "name" and "arguments" keys.
        width: Screen width in pixels.
        height: Screen height in pixels.

    Returns:
        Tuple of (action_type, action_inputs, json_action_dict).
    """
    from android_world.agents import new_json_action as json_action

    args = action_dict.get("arguments", {})
    action_name = args.get("action", "")
    action_inputs = dict(args)

    if action_name == "click":
        coord = args.get("coordinate", [500, 500])
        x = rescale_coord(coord[0], width)
        y = rescale_coord(coord[1], height)
        action_type = json_action.CLICK
        json_action_dict = {"action_type": action_type, "x": x, "y": y}

    elif action_name == "long_press":
        coord = args.get("coordinate", [500, 500])
        x = rescale_coord(coord[0], width)
        y = rescale_coord(coord[1], height)
        action_type = json_action.LONG_PRESS
        json_action_dict = {"action_type": action_type, "x": x, "y": y}

    elif action_name == "swipe":
        coord = args.get("coordinate", [500, 500])
        coord2 = args.get("coordinate2", [500, 500])
        x = rescale_coord(coord[0], width)
        y = rescale_coord(coord[1], height)
        x2 = rescale_coord(coord2[0], width)
        y2 = rescale_coord(coord2[1], height)
        action_type = json_action.SWIPE
        json_action_dict = {"action_type": action_type, "direction": [x, y, x2, y2]}

    elif action_name == "type":
        text = args.get("text", "")
        action_type = json_action.INPUT_TEXT
        json_action_dict = {"action_type": action_type, "text": text}

    elif action_name == "answer":
        text = args.get("text", "")
        action_type = json_action.STATUS
        json_action_dict = {"action_type": action_type, "goal_status": "success", "text": text}

    elif action_name == "terminate":
        status = args.get("status", "success")
        action_type = json_action.STATUS
        json_action_dict = {"action_type": action_type, "goal_status": status}

    elif action_name == "system_button":
        button = args.get("button", "")
        if button == "Back":
            action_type = json_action.NAVIGATE_BACK
            json_action_dict = {"action_type": action_type}
        elif button == "Home":
            action_type = json_action.NAVIGATE_HOME
            json_action_dict = {"action_type": action_type}
        elif button == "Enter":
            action_type = json_action.KEYBOARD_ENTER
            json_action_dict = {"action_type": action_type}
        else:  # Menu or unknown
            action_type = json_action.NAVIGATE_HOME
            json_action_dict = {"action_type": action_type}

    elif action_name == "open":
        app_name = args.get("text", "")
        action_type = json_action.OPEN_APP
        json_action_dict = {"action_type": action_type, "app_name": app_name}

    elif action_name == "wait":
        action_type = json_action.WAIT
        json_action_dict = {"action_type": action_type}

    elif action_name == "key":
        # Map key events to appropriate actions
        key_text = args.get("text", "")
        if key_text.lower() in ("enter", "return"):
            action_type = json_action.KEYBOARD_ENTER
            json_action_dict = {"action_type": action_type}
        elif key_text.lower() in ("home",):
            action_type = json_action.NAVIGATE_HOME
            json_action_dict = {"action_type": action_type}
        elif key_text.lower() in ("back",):
            action_type = json_action.NAVIGATE_BACK
            json_action_dict = {"action_type": action_type}
        else:
            # Generic key event - treat as wait (best effort)
            action_type = json_action.WAIT
            json_action_dict = {"action_type": action_type}

    elif action_name == "interact":
        # User interaction request - treat as wait
        action_type = json_action.WAIT
        json_action_dict = {"action_type": action_type}

    else:
        action_type = json_action.UNKNOWN
        json_action_dict = {"action_type": action_type}

    return action_type, action_inputs, json_action_dict
