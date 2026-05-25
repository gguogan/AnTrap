"""T-Layer (Thinking) traps.

- Temporal Conflict: replace current screenshot with a stale/historical one.
- Visual Hallucination: rewrite text labels of UI elements with antonym
  replacements (or fallback char permutations) so the rendered screenshot
  contradicts the underlying app state.
"""

from __future__ import annotations

import os
import random
from typing import Optional

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from android_world.disturbances.trap_config import TrapConfig


def apply_temporal_conflict(
    pixels: np.ndarray,
    step_idx: int,
    screenshot_history: list[np.ndarray],
    config: TrapConfig,
    task_name: str = '',
) -> Optional[np.ndarray]:
    """Replace current screenshot with a historical or preloaded one.

    Args:
        pixels: Current screenshot (unused if replacement found).
        step_idx: Current step index.
        screenshot_history: List of past screenshots (before current step).
        config: TrapConfig with temporal params.
        task_name: Task class name. When config.temporal_source == 'preloaded'
            and config.preloaded_screenshot_dir is empty, we fall back to
            `<repo_root>/screenshot_photo/<task_name>/screenshot_*.png`.

    Returns:
        Historical screenshot pixels, or None if not enough history.
    """
    if config.temporal_source == 'same_episode':
        # Use screenshot from N steps ago
        target_idx = step_idx + config.temporal_offset  # offset is negative
        if target_idx < 0 or target_idx >= len(screenshot_history):
            return None  # Not enough history yet
        return screenshot_history[target_idx].copy()

    elif config.temporal_source == 'preloaded':
        directory = config.preloaded_screenshot_dir
        if not directory:
            directory = _default_preloaded_dir(task_name)
        result = _load_preloaded_screenshot(directory, pixels.shape)
        if result is not None:
            return result
        # Fallback: behave like same_episode if the preloaded pool is missing.
        target_idx = step_idx + config.temporal_offset
        if target_idx < 0 or target_idx >= len(screenshot_history):
            return None
        return screenshot_history[target_idx].copy()

    return None


def _default_preloaded_dir(task_name: str) -> str:
    """Resolve `<repo_root>/screenshot_photo/<task_name>/`.

    repo_root is two levels above this file (android_world/disturbances/).
    """
    if not task_name:
        return ''
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, '..', '..'))
    return os.path.join(repo_root, 'screenshot_photo', task_name)


def _load_preloaded_screenshot(directory: str, target_shape) -> Optional[np.ndarray]:
    """Load a random screenshot from pre-collected directory."""
    if not directory or not os.path.isdir(directory):
        return None

    files = [f for f in os.listdir(directory) if f.lower().endswith('.png')]
    if not files:
        return None

    chosen = random.choice(files)
    img = Image.open(os.path.join(directory, chosen)).convert('RGB')
    # Resize to match current screenshot dimensions
    h, w = target_shape[:2]
    img = img.resize((w, h))
    return np.array(img)


def apply_visual_hallucination(
    pixels: np.ndarray,
    ui_elements,
    config: TrapConfig,
    rng: random.Random,
) -> Optional[np.ndarray]:
    """Overwrite text labels with misleading replacements drawn from an antonym
    dictionary, falling back to a character-level permutation when no antonym
    matches.

    Per paper: for each text-bearing UI element identified via its accessibility-
    tree bounding box, the background color is estimated by median sampling
    along the bbox edges, the original region is overwritten with that color,
    and the replacement is rendered in DejaVu Sans using the contrast-inverted
    color.

    Args:
        pixels: Screenshot as numpy array (H, W, 3).
        ui_elements: List of UIElement objects.
        config: TrapConfig with semantic params.
        rng: Random instance.

    Returns:
        Modified pixels, or None if no suitable elements found.
    """
    if ui_elements is None or len(ui_elements) == 0:
        return None

    # Find elements with visible text
    text_elements = []
    for elem in ui_elements:
        if (elem.bbox_pixels is not None
                and elem.text
                and len(elem.text.strip()) > 0):
            bb = elem.bbox_pixels
            if bb.x_max > bb.x_min and bb.y_max > bb.y_min:
                text_elements.append(elem)

    if not text_elements:
        return None

    img = Image.fromarray(pixels)
    draw = ImageDraw.Draw(img)

    # Pick element(s) to modify
    if config.semantic_target == 'random_text':
        # Modify 1-2 random text elements
        n = min(rng.randint(1, 2), len(text_elements))
        targets = rng.sample(text_elements, n)
    else:
        targets = [rng.choice(text_elements)]

    for elem in targets:
        bb = elem.bbox_pixels
        x_min, y_min = int(bb.x_min), int(bb.y_min)
        x_max, y_max = int(bb.x_max), int(bb.y_max)
        original_text = elem.text.strip()

        # Get replacement text
        replacement = _get_replacement_text(original_text, config, rng)

        # Paint over: fill with background color estimate, then draw new text
        # Sample background color from the edges of the bbox
        bg_color = _estimate_bg_color(pixels, x_min, y_min, x_max, y_max)
        draw.rectangle([x_min, y_min, x_max, y_max], fill=bg_color)

        # Draw replacement text
        font_size = max(10, y_max - y_min - 4)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

        # Center text in bbox
        text_bbox = draw.textbbox((0, 0), replacement, font=font)
        tw = text_bbox[2] - text_bbox[0]
        th = text_bbox[3] - text_bbox[1]
        tx = x_min + max(0, (x_max - x_min - tw) // 2)
        ty = y_min + max(0, (y_max - y_min - th) // 2)

        # Text color: invert of background
        text_color = tuple(255 - c for c in bg_color[:3])
        draw.text((tx, ty), replacement, fill=text_color, font=font)

    return np.array(img)


# 24 unordered antonym pairs covering common UI verbs. Listed once each;
# the bidirectional lookup dict is materialized below. Paper claim: "a curated
# 24-pair antonym dictionary covering common UI verbs such as Save/Delete,
# Allow/Deny, and Confirm/Cancel".
_ANTONYM_PAIRS = [
    ('Save', 'Delete'),
    ('OK', 'Cancel'),
    ('Confirm', 'Cancel'),
    ('Yes', 'No'),
    ('Done', 'Cancel'),
    ('Back', 'Next'),
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
    ('Lock', 'Unlock'),
    ('Mute', 'Unmute'),
    ('Submit', 'Reset'),
    ('Sign in', 'Sign out'),
    ('Log in', 'Log out'),
    ('Upload', 'Download'),
    ('Subscribe', 'Unsubscribe'),
    ('Follow', 'Unfollow'),
]


def _build_confusion_table(pairs):
    table = {}
    for a, b in pairs:
        # First insertion wins on conflict so Confirm/Cancel stays paired even
        # though OK/Cancel also maps Cancel.
        table.setdefault(a, b)
        table.setdefault(b, a)
    return table


_CONFUSION_PAIRS = _build_confusion_table(_ANTONYM_PAIRS)


def _get_replacement_text(original: str, config: TrapConfig, rng: random.Random) -> str:
    """Get replacement text for a UI label."""
    if config.semantic_replacement:
        return config.semantic_replacement

    # Try exact match in confusion pairs
    if original in _CONFUSION_PAIRS:
        return _CONFUSION_PAIRS[original]

    # Try case-insensitive match
    for key, val in _CONFUSION_PAIRS.items():
        if original.lower() == key.lower():
            return val

    # Fallback: shuffle characters or append misleading suffix
    if len(original) <= 3:
        return original + '...'
    chars = list(original)
    rng.shuffle(chars)
    return ''.join(chars)


def _estimate_bg_color(pixels: np.ndarray, x_min, y_min, x_max, y_max) -> tuple:
    """Estimate background color from the edges of a bounding box."""
    h, w = pixels.shape[:2]
    samples = []

    # Sample from edges (1 pixel border)
    if y_min > 0:
        samples.extend(pixels[max(0, y_min - 1), x_min:x_max].tolist())
    if y_max < h:
        samples.extend(pixels[min(h - 1, y_max), x_min:x_max].tolist())
    if x_min > 0:
        samples.extend(pixels[y_min:y_max, max(0, x_min - 1)].tolist())
    if x_max < w:
        samples.extend(pixels[y_min:y_max, min(w - 1, x_max)].tolist())

    if not samples:
        return (255, 255, 255)

    # Median color
    arr = np.array(samples)
    median = np.median(arr, axis=0).astype(int)
    return tuple(median[:3])
