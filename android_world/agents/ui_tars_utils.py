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

"""UI-TARS Agent utility functions for prompt building and action parsing."""

import re
from typing import Any, Optional, Tuple


# UI-TARS System Prompt Template (matching reference implementation)
SYSTEM_PROMPT_FORMAT = """
You are a GUI agent. You are given a task and your action history, with screenshots. You need to perform the next action to complete the task.

## Output Format

Thought: ...
Action: ...


## Action Space

click(start_box='[x1, y1, x2, y2]')
long_press(start_box='<|box_start|>(x1,y1)<|box_end|>')
type(content='xxx')
scroll(start_box='<|box_start|>(x1,y1)<|box_end|>', end_box='<|box_start|>(x2,y2)<|box_end|>')
open_app(app_name='')
drag(start_box='<|box_start|>(x1,y1)<|box_end|>', end_box='<|box_start|>(x2,y2)<|box_end|>')
press_home()
press_back()
finished(content='') # Submit the task regardless of whether it succeeds or fails.

## Note
- Use English in Thought part.

- Write a small plan and finally summarize your next action (with its save target element) in one sentence in Thought part.

## User Instruction
{instruction}
"""


def build_system_prompt(instruction: str) -> str:
    """Build the system prompt with the task instruction.

    Args:
        instruction: The task instruction/goal.

    Returns:
        The formatted system prompt.
    """
    return SYSTEM_PROMPT_FORMAT.format(instruction=instruction)


def build_ui_tars_messages(
    goal: str,
    screenshot,
    history_images: list,
    history_responses: list,
    system_prompt: Optional[str] = None,
) -> list[dict]:
    """Build UI-TARS format messages for API call.

    Args:
        goal: The task goal/instruction.
        screenshot: Current screenshot (PIL Image or numpy array).
        history_images: List of historical screenshots (last 4).
        history_responses: List of historical model responses.
        system_prompt: Optional custom system prompt.

    Returns:
        List of message dicts in OpenAI-compatible format.
    """
    if system_prompt is None:
        system_prompt = build_system_prompt(goal)

    messages = [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": "You are a helpful assistant."
                }
            ]
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": system_prompt,
                }
            ]
        },
    ]

    # Add current screenshot
    messages.append({
        "role": "user",
        "content": [
            {
                "type": "image",
                "image": screenshot,
            }
        ]
    })

    # Add history (responses from assistant and next screenshots from user)
    for i, (response, img) in enumerate(zip(history_responses, history_images)):
        # Add assistant's previous response
        messages.append({
            "role": "assistant",
            "content": [
                {
                    "type": "text",
                    "text": response,
                }
            ]
        })
        # Add the next screenshot
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "image": img,
                }
            ]
        })

    return messages


def parse_ui_tars_action_with_official_parser(
    response: str,
    width: int = 1080,
    height: int = 2400,
    factor: int = 1000,
    model_type: str = "qwen25vl"
) -> dict:
    """Parse UI-TARS format response using official parser.

    Args:
        response: The model's raw text response.
        width: Screen width in pixels.
        height: Screen height in pixels.
        factor: Normalization factor (default 1000 for UI-TARS).
        model_type: Model type for parser.

    Returns:
        A dict with keys:
            - thought: The thought text
            - action_type: The action type (click, type, etc.)
            - action_inputs: Dict of action parameters
            - raw_response: The original response
    """
    from ui_tars.action_parser import parse_action_to_structure_output

    try:
        parsed_action_dict = parse_action_to_structure_output(
            response,
            factor=factor,
            origin_resized_height=height,
            origin_resized_width=width,
            model_type=model_type
        )[0]

        return {
            "thought": parsed_action_dict.get("thought"),
            "action_type": parsed_action_dict.get("action_type"),
            "action_inputs": parsed_action_dict.get("action_inputs", {}),
            "raw_response": response,
        }
    except Exception as e:
        # Fallback to default action on parsing error
        print(f"Error parsing action with official parser: {e}")
        return {
            "thought": "Error parsing action",
            "action_type": "wait",
            "action_inputs": {},
            "raw_response": response,
        }


def parse_ui_tars_action(response: str) -> dict:
    """Parse UI-TARS format response into structured action dict.

    Simple fallback parser for basic cases.

    Args:
        response: The model's raw text response.

    Returns:
        A dict with keys:
            - thought: The thought text
            - action_type: The action type (click, type, etc.)
            - action_inputs: Dict of action parameters
            - raw_response: The original response
    """
    result = {
        "thought": None,
        "action_type": None,
        "action_inputs": {},
        "raw_response": response,
    }

    # Extract Thought
    thought_match = re.search(r'Thought:\s*(.*?)(?=Action:|$)', response, re.DOTALL)
    if thought_match:
        result["thought"] = thought_match.group(1).strip()

    # Extract Action
    action_match = re.search(r'Action:\s*(\w+)\s*\((.*?)\)\s*$', response, re.DOTALL)
    if action_match:
        result["action_type"] = action_match.group(1).strip()
        params_str = action_match.group(2).strip()
        result["action_inputs"] = parse_action_params(params_str)
    else:
        # Try to match action without proper format
        action_match = re.search(r'(\w+)\s*\((.*?)\)', response)
        if action_match:
            result["action_type"] = action_match.group(1).strip()
            params_str = action_match.group(2).strip()
            result["action_inputs"] = parse_action_params(params_str)

    return result


def parse_action_params(params_str: str) -> dict:
    """Parse action parameters from string.

    Args:
        params_str: The parameters string.

    Returns:
        Dict of parameter names to values.
    """
    params = {}

    # Pattern to match key='value' or key="value"
    pattern = r"(\w+)\s*=\s*['\"]([^'\"]*?)['\"]"
    matches = re.findall(pattern, params_str)

    for key, value in matches:
        params[key] = value

    return params


def convert_ui_tars_action_to_json_action(
    parsed_action: dict,
    width: int,
    height: int,
    factor: int = 1000
) -> Tuple[str, dict, dict]:
    """Convert UI-TARS parsed action to JSONAction compatible format.

    The official parser returns normalized coordinates (0-1 range) as strings
    in format "[x, y, x, y]". We need to parse and convert back to pixels.

    Args:
        parsed_action: The parsed action dict from parse_ui_tars_action.
        width: Screen width in pixels.
        height: Screen height in pixels.
        factor: Not used (kept for compatibility).

    Returns:
        Tuple of (action_type, action_params, json_action_dict) where:
            - action_type: The JSONAction action type
            - action_params: Parameters for the action
            - json_action_dict: Dict suitable for JSONAction construction
    """
    import ast
    from android_world.agents import new_json_action as json_action

    action_type_mapping = {
        "click": json_action.CLICK,
        "long_press": json_action.LONG_PRESS,
        "type": json_action.INPUT_TEXT,
        "scroll": json_action.SWIPE,
        "drag": json_action.SWIPE,
        "open_app": json_action.OPEN_APP,
        "press_home": json_action.NAVIGATE_HOME,
        "press_back": json_action.NAVIGATE_BACK,
        "finished": json_action.STATUS,
        "wait": json_action.WAIT,
    }

    ui_tars_type = parsed_action.get("action_type", "")
    action_inputs = parsed_action.get("action_inputs", {})

    # Map action type
    json_action_type = action_type_mapping.get(ui_tars_type, json_action.UNKNOWN)

    json_action_dict = {
        "action_type": json_action_type,
    }

    def get_pixel_coords(box_value):
        """Convert normalized coordinates string to pixel (x, y).

        The official parser returns string like "[0.5, 0.6, 0.5, 0.6]".
        This matches the reference _get_coords function behavior.
        """
        if box_value is None:
            return width // 2, height // 2

        # Parse string to list
        if isinstance(box_value, str):
            try:
                coords = ast.literal_eval(box_value)
            except:
                return width // 2, height // 2
        elif isinstance(box_value, (list, tuple)):
            coords = box_value
        else:
            return width // 2, height // 2

        coords = list(coords)

        if len(coords) == 2:
            # [x, y] format - normalized, multiply by screen size
            x = int(coords[0] * width)
            y = int(coords[1] * height)
            return x, y
        elif len(coords) == 4:
            # [x1, y1, x2, y2] format - return center point
            x1, y1, x2, y2 = coords
            center_x = int((x1 + x2) / 2 * width)
            center_y = int((y1 + y2) / 2 * height)
            return center_x, center_y
        else:
            return width // 2, height // 2

    if json_action_type == json_action.CLICK:
        box = action_inputs.get("start_box")
        x, y = get_pixel_coords(box)
        json_action_dict["x"] = x
        json_action_dict["y"] = y

    elif json_action_type == json_action.LONG_PRESS:
        box = action_inputs.get("start_box")
        x, y = get_pixel_coords(box)
        json_action_dict["x"] = x
        json_action_dict["y"] = y

    elif json_action_type == json_action.INPUT_TEXT:
        text = action_inputs.get("content", "")
        json_action_dict["text"] = text

    elif json_action_type == json_action.SWIPE:
        start_box = action_inputs.get("start_box")
        end_box = action_inputs.get("end_box")

        start_x, start_y = get_pixel_coords(start_box)
        end_x, end_y = get_pixel_coords(end_box)

        json_action_dict["direction"] = [start_x, start_y, end_x, end_y]

    elif json_action_type == json_action.OPEN_APP:
        app_name = action_inputs.get("app_name", "")
        # Look up the package name first; fall back to fuzzy matching if not found
        package_name = get_app_package(app_name)
        if package_name:
            # Keep only the package portion (without the activity)
            json_action_dict["app_name"] = package_name.split('/')[0]
        else:
            # Fuzzy match: pick the closest app
            closest_match = find_closest_app(app_name, APP_PACKAGE_MAP)
            if closest_match:
                json_action_dict["app_name"] = closest_match.split('/')[0]
            else:
                json_action_dict["app_name"] = app_name

    elif json_action_type == json_action.STATUS:
        json_action_dict["goal_status"] = "task_complete"

    return json_action_type, action_inputs, json_action_dict


# App name to package mapping (common Android apps)
APP_PACKAGE_MAP = {
    'google chrome': 'com.android.chrome',
    'chrome': 'com.android.chrome',
    'google chat': 'com.google.android.apps.dynamite/com.google.android.apps.dynamite.startup.StartUpActivity',
    'settings': 'com.android.settings',
    'system settings': 'com.android.settings',
    'youtube': 'com.google.android.youtube/com.google.android.apps.youtube.app.WatchWhileActivity',
    'yt': 'com.google.android.youtube/com.google.android.apps.youtube.app.WatchWhileActivity',
    'google play': 'com.android.vending/com.google.android.finsky.activities.MainActivity',
    'play store': 'com.android.vending/com.google.android.finsky.activities.MainActivity',
    'gps': 'com.android.vending/com.google.android.finsky.activities.MainActivity',
    'gmail': 'com.google.android.gm/.ConversationListActivityGmail',
    'gemail': 'com.google.android.gm/.ConversationListActivityGmail',
    'google mail': 'com.google.android.gm/.ConversationListActivityGmail',
    'google email': 'com.google.android.gm/.ConversationListActivityGmail',
    'google mail client': 'com.google.android.gm/.ConversationListActivityGmail',
    'google maps': 'com.google.android.apps.maps/com.google.android.maps.MapsActivity',
    'gmaps': 'com.google.android.apps.maps/com.google.android.maps.MapsActivity',
    'maps': 'com.google.android.apps.maps/com.google.android.maps.MapsActivity',
    'google map': 'com.google.android.apps.maps/com.google.android.maps.MapsActivity',
    'google photos': 'com.google.android.apps.photos',
    'gphotos': 'com.google.android.apps.photos',
    'photos': 'com.google.android.apps.photos',
    'google photo': 'com.google.android.apps.photos',
    'google pics': 'com.google.android.apps.photos',
    'google images': 'com.google.android.apps.photos',
    'google calendar': 'com.google.android.calendar',
    'gcal': 'com.google.android.calendar',
    'camera': 'com.android.camera2',
    'audio recorder': 'com.dimowner.audiorecorder',
    'google drive': 'com.google.android.apps.docs/.drive.startup.StartupActivity',
    'gdrive': 'com.google.android.apps.docs/.drive.startup.StartupActivity',
    'drive': 'com.google.android.apps.docs/.drive.startup.StartupActivity',
    'google keep': 'com.google.android.keep/.activities.BrowseActivity',
    'gkeep': 'com.google.android.keep/.activities.BrowseActivity',
    'keep': 'com.google.android.keep/.activities.BrowseActivity',
    'grubhub': 'com.grubhub.android/com.grubhub.dinerapp.android.splash.SplashActivity',
    'tripadvisor': 'com.tripadvisor.tripadvisor/com.tripadvisor.android.ui.launcher.LauncherActivity',
    'starbucks': 'com.starbucks.mobilecard/.main.activity.LandingPageActivity',
    'google docs': 'com.google.android.apps.docs.editors.docs/com.google.android.apps.docs.editors.homescreen.HomescreenActivity',
    'gdocs': 'com.google.android.apps.docs.editors.docs/com.google.android.apps.docs.editors.homescreen.HomescreenActivity',
    'docs': 'com.google.android.apps.docs.editors.docs/com.google.android.apps.docs.editors.homescreen.HomescreenActivity',
    'google sheets': 'com.google.android.apps.docs.editors.sheets/com.google.android.apps.docs.editors.homescreen.HomescreenActivity',
    'gsheets': 'com.google.android.apps.docs.editors.sheets/com.google.android.apps.docs.editors.homescreen.HomescreenActivity',
    'sheets': 'com.google.android.apps.docs.editors.sheets/com.google.android.apps.docs.editors.homescreen.HomescreenActivity',
    'google slides': 'com.google.android.apps.docs.editors.slides/com.google.android.apps.docs.editors.homescreen.HomescreenActivity',
    'gslides': 'com.google.android.apps.docs.editors.slides/com.google.android.apps.docs.editors.homescreen.HomescreenActivity',
    'slides': 'com.google.android.apps.docs.editors.slides/com.google.android.apps.docs.editors.homescreen.HomescreenActivity',
    'clock': 'com.google.android.deskclock',
    'Clock': 'com.google.android.deskclock',
    'google search': 'com.google.android.googlequicksearchbox/com.google.android.googlequicksearchbox.SearchActivity',
    'google': 'com.google.android.googlequicksearchbox/com.google.android.googlequicksearchbox.SearchActivity',
    'contacts': 'com.google.android.contacts',
    'Contacts': 'com.google.android.contacts',
    'facebook': 'com.facebook.katana/com.facebook.katana.LoginActivity',
    'fb': 'com.facebook.katana/com.facebook.katana.LoginActivity',
    'whatsapp': 'com.whatsapp/com.whatsapp.Main',
    'wa': 'com.whatsapp/com.whatsapp.Main',
    'instagram': 'com.instagram.android/com.instagram.mainactivity.MainActivity',
    'ig': 'com.instagram.android/com.instagram.mainactivity.MainActivity',
    'twitter': 'com.twitter.android/com.twitter.app.main.MainActivity',
    'tweet': 'com.twitter.android/com.twitter.app.main.MainActivity',
    'snapchat': 'com.snapchat.android/com.snap.mushroom.MainActivity',
    'sc': 'com.snapchat.android/com.snap.mushroom.MainActivity',
    'telegram': 'org.telegram.messenger/org.telegram.ui.LaunchActivity',
    'tg': 'org.telegram.messenger/org.telegram.ui.LaunchActivity',
    'linkedin': 'com.linkedin.android/com.linkedin.android.authenticator.LaunchActivity',
    'spotify': 'com.spotify.music/com.spotify.music.MainActivity',
    'spot': 'com.spotify.music/com.spotify.music.MainActivity',
    'netflix': 'com.netflix.mediaclient/com.netflix.mediaclient.ui.launch.UIWebViewActivity',
    'amazon shopping': 'com.amazon.mShop.android.shopping/com.amazon.mShop.home.HomeActivity',
    'amazon': 'com.amazon.mShop.android.shopping/com.amazon.mShop.home.HomeActivity',
    'amzn': 'com.amazon.mShop.android.shopping/com.amazon.mShop.home.HomeActivity',
    'tiktok': 'com.zhiliaoapp.musically/com.ss.android.ugc.aweme.splash.SplashActivity',
    'tt': 'com.zhiliaoapp.musically/com.ss.android.ugc.aweme.splash.SplashActivity',
    'discord': 'com.discord/com.discord.app.AppActivity$Main',
    'reddit': 'com.reddit.frontpage/com.reddit.frontpage.MainActivity',
    'pinterest': 'com.pinterest/com.pinterest.activity.PinterestActivity',
    'android world': 'com.example.androidworld/.MainActivity',
    'files': 'com.google.android.documentsui/com.android.documentsui.files.FilesActivity',
    'markor': 'net.gsantner.markor/net.gsantner.markor.activity.MainActivity',
    'clipper': 'ca.zgrs.clipper/ca.zgrs.clipper.Main',
    'messages': 'com.google.android.apps.messaging/com.google.android.apps.messaging.ui.ConversationListActivity',
    'simple sms messenger': 'com.simplemobiletools.smsmessenger/com.simplemobiletools.smsmessenger.activities.MainActivity',
    'simple sms': 'com.simplemobiletools.smsmessenger/com.simplemobiletools.smsmessenger.activities.MainActivity',
    'dialer': 'com.google.android.dialer',
    'phone': 'com.google.android.dialer',
    'Phone': 'com.google.android.dialer',
    'simple calendar pro': 'com.simplemobiletools.calendar.pro/com.simplemobiletools.calendar.pro.activities.MainActivity',
    'simple calendar': 'com.simplemobiletools.calendar.pro/com.simplemobiletools.calendar.pro.activities.MainActivity',
    'simple gallery pro': 'com.simplemobiletools.gallery.pro/com.simplemobiletools.gallery.pro.activities.MainActivity',
    'simple gallery': 'com.simplemobiletools.gallery.pro/com.simplemobiletools.gallery.pro.activities.MainActivity',
    'miniwob': 'com.google.androidenv.miniwob/com.google.androidenv.miniwob.app.MainActivity',
    'simple draw pro': 'com.simplemobiletools.draw.pro/com.simplemobiletools.draw.pro.activities.MainActivity',
    'pro expense': 'com.arduia.expense/com.arduia.expense.ui.MainActivity',
    'pro expense app': 'com.arduia.expense/com.arduia.expense.ui.MainActivity',
    'broccoli': 'com.flauschcode.broccoli/com.flauschcode.broccoli.MainActivity',
    'broccoli app': 'com.flauschcode.broccoli/com.flauschcode.broccoli.MainActivity',
    'broccoli recipe app': 'com.flauschcode.broccoli/com.flauschcode.broccoli.MainActivity',
    'recipe app': 'com.flauschcode.broccoli/com.flauschcode.broccoli.MainActivity',
    'caa': 'com.google.ccc.hosted.contextawareaccess.thirdpartyapp/.ChooserActivity',
    'caa test': 'com.google.ccc.hosted.contextawareaccess.thirdpartyapp/.ChooserActivity',
    'context aware access': 'com.google.ccc.hosted.contextawareaccess.thirdpartyapp/.ChooserActivity',
    'osmand': 'net.osmand/net.osmand.plus.activities.MapActivity',
    'tasks': 'org.tasks/com.todoroo.astrid.activity.MainActivity',
    'tasks app': 'org.tasks/com.todoroo.astrid.activity.MainActivity',
    'tasks.org:': 'org.tasks/com.todoroo.astrid.activity.MainActivity',
    'open tracks sports tracker': 'de.dennisguse.opentracks/de.dennisguse.opentracks.TrackListActivity',
    'activity tracker': 'de.dennisguse.opentracks/de.dennisguse.opentracks.TrackListActivity',
    'open tracks': 'de.dennisguse.opentracks/de.dennisguse.opentracks.TrackListActivity',
    'opentracks': 'de.dennisguse.opentracks/de.dennisguse.opentracks.TrackListActivity',
    'joplin': 'net.cozic.joplin/.MainActivity',
    'joplin app': 'net.cozic.joplin/.MainActivity',
    'vlc': 'org.videolan.vlc/.gui.MainActivity',
    'vlc app': 'org.videolan.vlc/.gui.MainActivity',
    'vlc player': 'org.videolan.vlc/.gui.MainActivity',
    'retro music': 'code.name.monkey.retromusic/.activities.MainActivity',
    'retro': 'code.name.monkey.retromusic/.activities.MainActivity',
    'retro player': 'code.name.monkey.retromusic/.activities.MainActivity',
}


def get_app_package(app_name: str) -> Optional[str]:
    """Get the package name for an app.

    Args:
        app_name: The app name (case-insensitive).

    Returns:
        The package name if found, None otherwise.
    """
    app_name_lower = app_name.lower().strip()
    return APP_PACKAGE_MAP.get(app_name_lower)


def find_closest_app(app_name: str, app_map: dict, threshold: float = 0.6) -> Optional[str]:
    """Find the closest matching app name using fuzzy matching.

    Args:
        app_name: The app name to match.
        app_map: The app name to package mapping.
        threshold: Minimum similarity score (0-1) to consider a match.

    Returns:
        The package name of the closest match, or None if no match found.
    """
    import difflib

    app_name_lower = app_name.lower().strip()
    best_score = 0.0
    best_match = None

    for app_key in app_map.keys():
        # Compute similarity
        score = difflib.SequenceMatcher(None, app_name_lower, app_key.lower()).ratio()
        if score > best_score:
            best_score = score
            best_match = app_map[app_key]

    if best_score >= threshold:
        return best_match
    return None