"""Vendored UI-TARS action parser.

Mirrors ``ui_tars.action_parser.parse_action_to_structure_output`` from the
upstream ByteDance UI-TARS repo, so traptrain does not have to import the
external ``ui_tars`` package.

Input  : raw text emitted by the model, e.g.::

    Thought: I should tap the Send button.
    Action: click(start_box='<|box_start|>(420,1280)<|box_end|>')

Output : ``[{"action_type": str, "action_inputs": dict, "thought": str}]``.

The model emits coordinates in a normalised ``0-factor`` range (factor=1000
for Qwen2.5-VL based UI-TARS). When ``factor`` and image dimensions are
provided, coordinates are rescaled into pixel space so downstream ADB
execution can consume them directly.
"""

from __future__ import annotations

import ast
import math
import re
from typing import Any


# UI-TARS action verbs that we know how to parse. Anything else falls through
# untouched so the worker can decide what to do.
_KNOWN_ACTIONS = (
    "click",
    "long_press",
    "double_tap",
    "type",
    "scroll",
    "drag",
    "open_app",
    "press_home",
    "press_back",
    "finished",
    "wait",
    "answer",
)


def _extract_thought_and_action(text: str) -> tuple[str, str]:
    """Pull out the Thought + Action segments. Be permissive with case and
    leading whitespace -- some checkpoints emit "Thought:" lower-cased or
    glue multiple newlines."""
    thought = ""
    action = ""

    m = re.search(r"Thought:\s*(.+?)(?=Action:|$)", text, re.DOTALL | re.IGNORECASE)
    if m:
        thought = m.group(1).strip()

    m = re.search(r"Action:\s*(.+)", text, re.DOTALL | re.IGNORECASE)
    if m:
        action = m.group(1).strip()
    else:
        # Sometimes the model skips "Action:" and emits the call directly.
        m = re.search(r"\b(" + "|".join(_KNOWN_ACTIONS) + r")\([^)]*\)", text)
        if m:
            action = m.group(0).strip()

    return thought, action


def _split_top_level_args(arg_str: str) -> list[str]:
    """Split arguments on top-level commas only, respecting paired quotes and
    parentheses. ``"a='b,c', d='e'"`` -> ``["a='b,c'", "d='e'"]``."""
    parts: list[str] = []
    depth_paren = 0
    quote: str | None = None
    buf: list[str] = []
    for ch in arg_str:
        if quote:
            buf.append(ch)
            if ch == quote and (not buf or len(buf) < 2 or buf[-2] != "\\"):
                quote = None
        elif ch in ("'", '"'):
            quote = ch
            buf.append(ch)
        elif ch == "(":
            depth_paren += 1
            buf.append(ch)
        elif ch == ")":
            depth_paren -= 1
            buf.append(ch)
        elif ch == "," and depth_paren == 0:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def _parse_kv(kv: str) -> tuple[str, str]:
    if "=" not in kv:
        return "", kv
    key, value = kv.split("=", 1)
    key = key.strip()
    value = value.strip()
    # Strip surrounding quotes
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    return key, value


def _parse_box(box_str: str) -> tuple[float, ...] | None:
    """Extract a 2- or 4-tuple of floats from one of:

        <|box_start|>(x1,y1)<|box_end|>
        <|box_start|>(x1,y1,x2,y2)<|box_end|>
        (x1,y1)
        [x1,y1]
        x1,y1
    """
    if not box_str:
        return None
    inner = box_str
    box_match = re.search(r"<\|box_start\|>\(([^)]+)\)<\|box_end\|>", inner)
    if box_match:
        inner = box_match.group(1)
    # Now inner should be of form 'x,y' or 'x,y,x2,y2' (possibly bracketed).
    inner = inner.strip().strip("()[]")
    nums = [s.strip() for s in inner.split(",") if s.strip()]
    try:
        return tuple(float(x) for x in nums)
    except ValueError:
        return None


def _rescale(box: tuple[float, ...] | None, factor: int, width: int, height: int) -> tuple[int, ...] | None:
    """Map model-space coordinates [0, factor) to pixel space [0, W/H)."""
    if box is None:
        return None
    if not factor or factor <= 0:
        return tuple(int(round(v)) for v in box)
    out: list[int] = []
    for i, v in enumerate(box):
        scale = width if (i % 2 == 0) else height
        out.append(int(round(v / factor * scale)))
    return tuple(out)


def parse_action_to_structure_output(
    text: str,
    factor: int = 1000,
    origin_resized_height: int = 2400,
    origin_resized_width: int = 1080,
    model_type: str = "qwen25vl",
    max_pixels: int | None = None,
    min_pixels: int | None = None,
) -> list[dict[str, Any]]:
    """Parse a single model output into a list of structured actions.

    The upstream signature returns a list because some legacy UI-TARS
    checkpoints emit multiple actions in one turn. We return a list of length
    1 for the standard one-action format.

    Coordinates in the returned dict are already rescaled to pixels for the
    declared ``origin_resized_width x origin_resized_height`` viewport.
    """
    _ = (model_type, max_pixels, min_pixels)  # accepted for signature parity
    thought, action_str = _extract_thought_and_action(text)
    if not action_str:
        return [{"action_type": "wait", "action_inputs": {}, "thought": thought}]

    m = re.match(r"\s*([A-Za-z_]\w*)\s*\((.*)\)\s*$", action_str, re.DOTALL)
    if not m:
        return [{"action_type": "wait", "action_inputs": {}, "thought": thought}]

    action_type = m.group(1).strip()
    raw_args = m.group(2).strip()

    inputs: dict[str, Any] = {}
    if raw_args:
        for part in _split_top_level_args(raw_args):
            key, value = _parse_kv(part)
            if not key:
                continue
            if key in ("start_box", "end_box", "box"):
                box = _parse_box(value)
                rescaled = _rescale(
                    box, factor, origin_resized_width, origin_resized_height
                )
                if rescaled is not None:
                    inputs[key] = list(rescaled)
                    # Keep the raw form for logging in case downstream cares.
                    inputs[f"{key}_raw"] = value
                else:
                    inputs[key] = value
            else:
                inputs[key] = value

    # Normalise a few aliases to the names the AndroidWorld JSONAction wrapper
    # expects further down the pipeline.
    if action_type == "type":
        # Some checkpoints emit content='...', others text='...'.
        if "content" not in inputs and "text" in inputs:
            inputs["content"] = inputs.pop("text")

    return [{
        "action_type": action_type,
        "action_inputs": inputs,
        "thought": thought,
    }]
