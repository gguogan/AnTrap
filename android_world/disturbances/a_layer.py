"""A-Layer (Action) traps.

- Grounding Error: add random pixel offset to action coordinates.
- Type Mismatch: rewrite action type (click ↔ long_press ↔ double_tap; swipe
  reversed).
- Intent Deviation: silently retarget the action to a different element
  (preferring antonym-labelled neighbours) or substitute typed text.

All A-Layer traps intercept the parsed action between model output and ADB
execution. The model's recorded reasoning + intent stays unchanged so that
the deviation is only observable through the next post-execution screenshot.
"""

import copy
import math
import random

from android_world.agents import new_json_action as json_action
from android_world.disturbances.trap_config import TrapConfig


def apply_grounding_error(action, dummy_action, config: TrapConfig, rng: random.Random):
    """Add random coordinate offset to click/long_press/swipe actions.

    Returns:
        (modified_action, modified_dummy_action)
        action._trap_info is set with original/offset coords for logging.
    """
    action = copy.copy(action)
    dummy_action = copy.deepcopy(dummy_action)

    lo, hi = config.offset_range

    def _random_offset():
        magnitude = rng.randint(lo, hi)
        sign = rng.choice([-1, 1])
        return magnitude * sign

    # Save original coords for logging
    orig_x, orig_y = action.x, action.y

    # Offset JSONAction coordinates
    if action.action_type in ('click', 'long_press', 'double_tap') and action.x is not None:
        dx, dy = _random_offset(), _random_offset()
        action.x = max(0, action.x + dx)
        action.y = max(0, action.y + dy)

    if action.action_type == 'swipe' and action.x is not None:
        dx, dy = _random_offset(), _random_offset()
        action.x = max(0, action.x + dx)
        action.y = max(0, action.y + dy)

    # Attach trap info for logging (original → offset)
    action._trap_info = {
        'original': (orig_x, orig_y),
        'offset': (action.x, action.y),
    }

    # Also offset dummy_action (for history logging)
    args = dummy_action.get('arguments', {})
    if 'coordinate' in args and args['coordinate'] is not None:
        coord = list(args['coordinate'])
        if len(coord) >= 2:
            coord[0] = max(0, coord[0] + _random_offset())
            coord[1] = max(0, coord[1] + _random_offset())
            args['coordinate'] = coord

    if 'coordinate2' in args and args['coordinate2'] is not None:
        coord2 = list(args['coordinate2'])
        if len(coord2) >= 2:
            coord2[0] = max(0, coord2[0] + _random_offset())
            coord2[1] = max(0, coord2[1] + _random_offset())
            args['coordinate2'] = coord2

    return action, dummy_action


# Actions that can be swapped with each other
_TOUCH_ACTIONS = ('click', 'long_press', 'double_tap')


def apply_type_mismatch(action, dummy_action, config: TrapConfig, rng: random.Random = None):
    """Randomly replace touch action type with another touch type, or reverse a
    swipe. Coordinates and target intent are preserved; only the action verb
    changes. The model's response text in history retains the original action
    type so the mismatch is only visible after execution."""
    action = copy.copy(action)
    dummy_action = copy.deepcopy(dummy_action)
    if rng is None:
        rng = random.Random()

    original_type = action.action_type
    args = dummy_action.get('arguments', {})
    dummy_type = args.get('action', '')

    # Touch actions: randomly pick one of the other two
    if original_type in _TOUCH_ACTIONS:
        alternatives = [t for t in _TOUCH_ACTIONS if t != original_type]
        new_type = rng.choice(alternatives)
        action.action_type = new_type
        if dummy_type in _TOUCH_ACTIONS:
            args['action'] = new_type

    # Swipe: reverse direction (swap start/end coordinates)
    elif original_type == 'swipe':
        if hasattr(action, 'x2') and action.x2 is not None:
            action.x, action.x2 = action.x2, action.x
            action.y, action.y2 = action.y2, action.y
        if 'coordinate' in args and 'coordinate2' in args:
            args['coordinate'], args['coordinate2'] = args['coordinate2'], args['coordinate']

    action._trap_info = {
        'original_type': original_type,
        'new_type': action.action_type,
    }
    return action, dummy_action


# ----------------------------------------------------------------------------
# Intent Deviation
# ----------------------------------------------------------------------------

# 40 unordered "intent" antonym pairs. Larger than the 24-pair visual
# hallucination dictionary so the retargeting heuristic has wider coverage.
_INTENT_PAIRS = [
    ('Save', 'Delete'),
    ('OK', 'Cancel'),
    ('Confirm', 'Cancel'),
    ('Yes', 'No'),
    ('Done', 'Undo'),
    ('Back', 'Next'),
    ('Next', 'Previous'),
    ('Continue', 'Back'),
    ('Send', 'Discard'),
    ('Accept', 'Reject'),
    ('Allow', 'Deny'),
    ('Enable', 'Disable'),
    ('On', 'Off'),
    ('Start', 'Stop'),
    ('Add', 'Remove'),
    ('Open', 'Close'),
    ('Pause', 'Resume'),
    ('Show', 'Hide'),
    ('Expand', 'Collapse'),
    ('Lock', 'Unlock'),
    ('Mute', 'Unmute'),
    ('Submit', 'Reset'),
    ('Apply', 'Reset'),
    ('Sign in', 'Sign out'),
    ('Log in', 'Log out'),
    ('Login', 'Logout'),
    ('Subscribe', 'Unsubscribe'),
    ('Follow', 'Unfollow'),
    ('Like', 'Dislike'),
    ('Mark as read', 'Mark as unread'),
    ('Mark read', 'Mark unread'),
    ('Archive', 'Restore'),
    ('Block', 'Unblock'),
    ('Buy', 'Cancel'),
    ('Pay', 'Cancel'),
    ('Install', 'Uninstall'),
    ('Update', 'Skip'),
    ('Download', 'Pause'),
    ('Upload', 'Cancel'),
    ('Print', 'Cancel'),
    ('Share', 'Copy'),
    ('Reply', 'Forward'),
    ('Edit', 'Cancel'),
    ('Save', 'Discard'),
]


def _build_intent_table(pairs):
    table = {}
    for a, b in pairs:
        table.setdefault(a.lower(), b)
        table.setdefault(b.lower(), a)
    return table


_INTENT_TABLE = _build_intent_table(_INTENT_PAIRS)


# Wrong text replacements for type_text. Each key matches a substring of the
# original text (case-insensitive); value is the replacement.
_WRONG_TEXT_DICT = {
    'name': 'Anonymous',
    'email': 'spam@example.invalid',
    'phone': '0000000000',
    'address': '123 Nowhere St',
    'password': 'wrong_password',
    'subject': 'Untitled',
    'title': 'Untitled',
    'note': 'placeholder note',
    'message': 'placeholder message',
    'todo': 'placeholder task',
    'task': 'placeholder task',
    'reminder': 'placeholder reminder',
    'amount': '0',
    'date': '1970-01-01',
    'time': '00:00',
    'city': 'Atlantis',
    'country': 'Nowhereland',
    'zip': '00000',
    'username': 'unknown_user',
    'url': 'about:blank',
}


def _bbox_center(bb):
    return ((bb.x_min + bb.x_max) / 2.0, (bb.y_min + bb.y_max) / 2.0)


def _bbox_contains(bb, x, y):
    return bb.x_min <= x <= bb.x_max and bb.y_min <= y <= bb.y_max


def _clickable_elements(ui_elements):
    """Return list of (elem, center) for elements that look clickable."""
    out = []
    if not ui_elements:
        return out
    for elem in ui_elements:
        bb = getattr(elem, 'bbox_pixels', None)
        if bb is None:
            continue
        if bb.x_max <= bb.x_min or bb.y_max <= bb.y_min:
            continue
        # Treat anything with text and a valid bbox as a candidate. Many a11y
        # trees do not surface "clickable" reliably, so we err on the side of
        # including elements rather than skipping them.
        out.append((elem, _bbox_center(bb)))
    return out


def _antonym_of(text):
    if text is None:
        return None
    return _INTENT_TABLE.get(text.strip().lower())


def _find_origin_element(ui_elements, x, y):
    """Return the smallest UIElement whose bbox contains (x, y), or None."""
    if ui_elements is None or x is None or y is None:
        return None
    best = None
    best_area = None
    for elem in ui_elements:
        bb = getattr(elem, 'bbox_pixels', None)
        if bb is None:
            continue
        if not _bbox_contains(bb, x, y):
            continue
        area = max(1, (bb.x_max - bb.x_min) * (bb.y_max - bb.y_min))
        if best_area is None or area < best_area:
            best = elem
            best_area = area
    return best


def _pick_retarget(ui_elements, origin_x, origin_y, screen_size, config, rng):
    """Pick a different element to retarget the click to.

    Strategy:
      1. If the origin element has a text label with a known antonym, search
         all candidates for one whose text matches the antonym (preferring the
         closest one).
      2. Else, pick a random clickable candidate within
         intent_max_distance_frac * min(W, H) of the origin point.

    Returns:
        (target_elem, (new_x, new_y)) or (None, None) if no candidate found.
    """
    candidates = _clickable_elements(ui_elements)
    if not candidates:
        return None, None

    origin_elem = _find_origin_element(ui_elements, origin_x, origin_y)
    origin_text = getattr(origin_elem, 'text', None) if origin_elem else None
    antonym = _antonym_of(origin_text) if origin_text else None

    if antonym:
        antonym_lower = antonym.lower()
        match = None
        match_dist = None
        for elem, (cx, cy) in candidates:
            text = (getattr(elem, 'text', '') or '').strip().lower()
            if not text:
                continue
            if text == antonym_lower or antonym_lower in text or text in antonym_lower:
                dist = math.hypot(cx - origin_x, cy - origin_y)
                if match is None or dist < match_dist:
                    match = (elem, (cx, cy))
                    match_dist = dist
        if match:
            return match

    # Fallback: random nearby candidate, excluding the origin element.
    w, h = screen_size
    radius = config.intent_max_distance_frac * min(w, h)
    pool = []
    for elem, (cx, cy) in candidates:
        if origin_elem is not None and elem is origin_elem:
            continue
        if math.hypot(cx - origin_x, cy - origin_y) > radius:
            continue
        pool.append((elem, (cx, cy)))
    if not pool:
        # Widen to any clickable element that isn't the origin.
        pool = [(elem, c) for elem, c in candidates
                if origin_elem is None or elem is not origin_elem]
    if not pool:
        return None, None
    return rng.choice(pool)


def _wrong_text_for(original, rng):
    text = (original or '').strip().lower()
    if not text:
        return ''.join(rng.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(10))
    for key, replacement in _WRONG_TEXT_DICT.items():
        if key in text:
            return replacement
    # Char-level scramble fallback so the deviation is still observable.
    chars = list(original)
    if len(chars) > 1:
        rng.shuffle(chars)
        return ''.join(chars)
    return ''.join(rng.choice('abcdefghijklmnopqrstuvwxyz') for _ in range(8))


def apply_intent_deviation(action, dummy_action, ui_elements, screen_size,
                            config: TrapConfig, rng: random.Random = None):
    """Silently redirect an action away from the model's intended target.

    Args:
        action: parsed JSONAction.
        dummy_action: agent-facing intent dict (kept for history; we mutate the
            execution copy but NOT what is stored in the agent's history).
        ui_elements: list of UIElement at the current screen.
        screen_size: (width, height) of the screenshot in pixels.
        config: TrapConfig.
        rng: Random instance.

    Returns:
        (modified_action, modified_dummy_action). Per paper the model's history
        keeps the original reasoning, so we deliberately leave dummy_action's
        original text/coords untouched; only the executable JSONAction is
        rewritten. We still attach _trap_info for episode-level logging.
    """
    action = copy.copy(action)
    if rng is None:
        rng = random.Random()

    original_type = action.action_type
    original_x, original_y = getattr(action, 'x', None), getattr(action, 'y', None)
    original_text = getattr(action, 'text', None)

    info = {
        'original_type': original_type,
        'original_xy': (original_x, original_y),
        'original_text': original_text,
        'retargeted_xy': None,
        'retargeted_text': None,
        'retarget_label': None,
    }

    if original_type in _TOUCH_ACTIONS and original_x is not None and original_y is not None:
        target, center = _pick_retarget(
            ui_elements, original_x, original_y, screen_size, config, rng
        )
        if target is not None and center is not None:
            new_x, new_y = int(center[0]), int(center[1])
            action.x = new_x
            action.y = new_y
            info['retargeted_xy'] = (new_x, new_y)
            info['retarget_label'] = (
                getattr(target, 'text', None)
                or getattr(target, 'content_description', None)
                or getattr(target, 'class_name', None)
            )

    elif original_type == 'input_text' and original_text is not None:
        new_text = _wrong_text_for(original_text, rng)
        action.text = new_text
        info['retargeted_text'] = new_text

    elif original_type == 'swipe':
        # Treat swipe specially: flip direction so navigational intent (next/
        # back, scroll up/down) inverts.
        if hasattr(action, 'x2') and action.x2 is not None:
            action.x, action.x2 = action.x2, action.x
            action.y, action.y2 = action.y2, action.y
            info['retargeted_xy'] = (action.x, action.y)

    action._trap_info = info
    # Intentionally leave dummy_action unchanged so agent history retains the
    # original reasoning and intent.
    return action, dummy_action
