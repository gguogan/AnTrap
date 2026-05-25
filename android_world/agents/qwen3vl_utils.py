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

"""Qwen3-VL Agent utility functions for prompt building and action parsing."""

import json
import re
from typing import Optional


QWEN3VL_SYSTEM_PROMPT = (
    "\n\n# Tools\n\nYou may call one or more functions to assist with the user"
    " query.\n\nYou are provided with function signatures within <tools></tools>"
    " XML tags:\n<tools>\n{\"type\": \"function\", \"function\": {\"name\":"
    " \"mobile_use\", \"description\": \"Use a touchscreen to interact with a"
    " mobile device, and take screenshots.\\n* This is an interface to a mobile"
    " device with touchscreen. You can perform actions like clicking, typing,"
    " swiping, etc.\\n* Some applications may take time to start or process"
    " actions, so you may need to wait and take successive screenshots to see"
    " the results of your actions.\\n* The screen's resolution is 999x999.\\n*"
    " Make sure to click any buttons, links, icons, etc with the cursor tip in"
    " the center of the element. Don't click boxes on their edges unless"
    " asked.\", \"parameters\": {\"properties\": {\"action\": {\"description\":"
    " \"The action to perform. The available actions are:\\n* `click`: Click"
    " the point on the screen with coordinate (x, y).\\n* `long_press`: Press"
    " the point on the screen with coordinate (x, y) for specified"
    " seconds.\\n* `swipe`: Swipe from the starting point with coordinate (x,"
    " y) to the end point with coordinates2 (x2, y2).\\n* `type`: Input the"
    " specified text into the activated input box.\\n* `answer`: Output the"
    " answer.\\n* `system_button`: Press the system button.\\n* `wait`: Wait"
    " specified seconds for the change to happen.\\n* `terminate`: Terminate"
    " the current task and report its completion status.\", \"enum\": [\"click\","
    " \"long_press\", \"swipe\", \"type\", \"answer\", \"system_button\","
    " \"wait\", \"terminate\"], \"type\": \"string\"}, \"coordinate\":"
    " {\"description\": \"(x, y): The x (pixels from the left edge) and y"
    " (pixels from the top edge) coordinates to move the mouse to. Required"
    " only by `action=click`, `action=long_press`, and `action=swipe`.\","
    " \"type\": \"array\"}, \"coordinate2\": {\"description\": \"(x, y): The x"
    " (pixels from the left edge) and y (pixels from the top edge) coordinates"
    " to move the mouse to. Required only by `action=swipe`.\", \"type\":"
    " \"array\"}, \"text\": {\"description\": \"Required only by `action=type`"
    " and `action=answer`.\", \"type\": \"string\"}, \"time\": {\"description\":"
    " \"The seconds to wait. Required only by `action=long_press` and"
    " `action=wait`.\", \"type\": \"number\"}, \"button\": {\"description\":"
    " \"Back means returning to the previous interface, Home means returning to"
    " the desktop, Menu means opening the application background menu, and Enter"
    " means pressing the enter. Required only by `action=system_button`\","
    " \"enum\": [\"Back\", \"Home\", \"Menu\", \"Enter\"], \"type\": \"string\"},"
    " \"status\": {\"description\": \"The status of the task. Required only by"
    " `action=terminate`.\", \"type\": \"string\", \"enum\": [\"success\","
    " \"failure\"]}}, \"required\": [\"action\"], \"type\": \"object\"}}}\n"
    "</tools>\n\nFor each function call, return a json object with function name"
    " and arguments within <tool_call></tool_call> XML tags:\n<tool_call>\n"
    "{\"name\": <function-name>, \"arguments\": <args-json-object>}\n"
    "</tool_call>\n\n# Response format\n\nResponse format for every step:\n"
    "1) Thought: one concise sentence explaining the next move (no multi-step"
    " reasoning).\n2) Action: a short imperative describing what to do in the"
    " UI.\n3) A single <tool_call>...</tool_call> block containing only the"
    " JSON: {\"name\": <function-name>, \"arguments\": <args-json-object>}.\n\n"
    "Rules:\n- Output exactly in the order: Thought, Action, <tool_call>.\n"
    "- Be brief: one sentence for Thought, one for Action.\n"
    "- Do not output anything else outside those three parts.\n"
    "- If finishing, use action=terminate in the tool call."
)


def build_user_query(goal: str, history_text: str) -> str:
    """Build the user query string with goal and history.

    Args:
        goal: The task goal/instruction.
        history_text: Text summary of all previous steps.

    Returns:
        Formatted user query string.
    """
    return (
        f"The user query: {goal}.\n"
        f"Task progress (You have done the following operation on the current"
        f" device): {history_text}\n"
    )


def parse_qwen3vl_response(response_text: str) -> Optional[dict]:
    """Extract and parse JSON from <tool_call>...</tool_call> block.

    Args:
        response_text: The model's raw text response.

    Returns:
        Parsed dict with "name" and "arguments" keys, or None on failure.
    """
    match = re.search(r'<tool_call>\s*(.*?)\s*</tool_call>', response_text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    return None


def rescale_coord(coord: int, dimension: int) -> int:
    """Rescale a coordinate from 0-999 range to pixel dimension.

    Args:
        coord: Coordinate in 0-999 range.
        dimension: Target dimension in pixels.

    Returns:
        Pixel coordinate.
    """
    return round(coord / 999 * dimension)


def convert_qwen3vl_action_to_json_action(
    action_dict: dict, width: int, height: int
) -> tuple[str, dict, dict]:
    """Convert Qwen3VL action dict to JSONAction compatible format.

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
        coord = args.get("coordinate", [499, 499])
        x = rescale_coord(coord[0], width)
        y = rescale_coord(coord[1], height)
        action_type = json_action.CLICK
        json_action_dict = {"action_type": action_type, "x": x, "y": y}

    elif action_name == "long_press":
        coord = args.get("coordinate", [499, 499])
        x = rescale_coord(coord[0], width)
        y = rescale_coord(coord[1], height)
        action_type = json_action.LONG_PRESS
        json_action_dict = {"action_type": action_type, "x": x, "y": y}

    elif action_name == "swipe":
        coord = args.get("coordinate", [499, 499])
        coord2 = args.get("coordinate2", [499, 499])
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
        else:  # Menu or unknown button
            action_type = json_action.NAVIGATE_HOME
            json_action_dict = {"action_type": action_type}

    elif action_name == "wait":
        action_type = json_action.WAIT
        json_action_dict = {"action_type": action_type}

    else:
        action_type = json_action.UNKNOWN
        json_action_dict = {"action_type": action_type}

    return action_type, action_inputs, json_action_dict
