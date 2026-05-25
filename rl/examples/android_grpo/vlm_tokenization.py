"""VLM tokenization for UI-TARS / Qwen2.5-VL step-level GRPO training.

Ported from ``androidcoach/verl/trainer/ppo/android.py``
``prepare_policy_logits_input``. Given the conversation history up to a
particular step and (optionally) the assistant response at that step,
returns the DataProto-ready tensor tuple that verl's actor expects:

    input_ids, attention_mask, position_ids,
    response_ids, response_attention_mask,
    pixel_values, image_grid_thw, raw_prompt_ids

The function deliberately lives outside the Ray worker so a single
Qwen2.5-VL processor instance can serve all parallel envs (the processor
itself holds ~1 GB of state and is expensive to instantiate).
"""

from __future__ import annotations

from typing import Any, Optional

import torch

from qwen_vl_utils import process_vision_info

import verl.utils.torch_functional as VF
from verl.models.transformers.qwen2_vl import get_rope_index
from verl.utils.torch_functional import get_response_mask, pad_2d_list_to_length


def _flatten_content(content: Any) -> str:
    """Render a message content (list of dicts | str) into the flat string the
    Qwen2.5-VL chat template expects, substituting ``<|image_pad|>`` for each
    image placeholder."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(_flatten_content(c) for c in content)
    if isinstance(content, dict):
        if "text" in content:
            return content["text"]
        if "image" in content:
            return "<|vision_start|><|image_pad|><|vision_end|>"
    raise ValueError(f"Unknown message content type: {type(content)!r}")


def prepare_policy_logits_input(
    messages: list[dict],
    processor,
    tokenizer,
    *,
    max_prompt_length: int,
    max_response_length: Optional[int] = None,
    response_text: Optional[str] = None,
) -> dict[str, Any]:
    """Tokenize a single (history + optional response) sample for verl.

    Args:
        messages: Conversation up to and including the screenshot the model
            is about to act on. The last entry is expected to be a user-role
            screenshot.
        processor: Hugging Face Qwen2.5-VL processor (from ``hf_processor``).
        tokenizer: Matching tokenizer (from ``hf_tokenizer``).
        max_prompt_length: Pad/truncate prompt to this length (left-pad).
        max_response_length: When ``response_text`` is provided, pad/truncate
            the response to this length (right-pad). Mandatory in training
            mode.
        response_text: The assistant turn at this step. When ``None``, the
            function returns rollout-input tensors only (no response part).

    Returns:
        Dict containing tensors and optional multi-modal inputs ready to drop
        into a verl ``DataProto.from_single_dict``.
    """
    image_inputs, _video_inputs, _video_kwargs = process_vision_info(
        messages, return_video_kwargs=True
    )

    # --- Prompt segment -----------------------------------------------------
    input_ids: list[torch.Tensor] = []
    attention_mask: list[torch.Tensor] = []
    pixel_values: list[torch.Tensor] = []
    image_grid_thw: list[torch.Tensor] = []
    image_cursor = 0

    for turn_idx, msg in enumerate(messages):
        role = msg["role"]
        text = _flatten_content(msg["content"])
        prompt = f"<|im_start|>{role}\n{text}<|im_end|>\n"
        cur_image_count = prompt.count("<|image_pad|>")
        # Append the generation-prompt marker only on the final user turn so
        # the model conditions on the latest screenshot.
        if turn_idx == len(messages) - 1:
            prompt += "<|im_start|>assistant\n"
        if cur_image_count > 0:
            slice_ = image_inputs[image_cursor : image_cursor + cur_image_count]
            result = processor(slice_, [prompt], add_special_tokens=False, return_tensors="pt")
            image_cursor += cur_image_count
        else:
            result = processor(None, [prompt], add_special_tokens=False, return_tensors="pt")
        input_ids.append(result.pop("input_ids")[0])
        attention_mask.append(result.pop("attention_mask")[0])
        if "pixel_values" in result:
            pixel_values.append(result["pixel_values"])
        if "image_grid_thw" in result:
            image_grid_thw.append(result["image_grid_thw"])

    input_ids_t = torch.cat(input_ids, dim=0)
    attention_mask_t = torch.cat(attention_mask, dim=0)
    pixel_values_t = torch.cat(pixel_values, dim=0) if pixel_values else None
    image_grid_thw_t = torch.cat(image_grid_thw, dim=0) if image_grid_thw else None

    position_ids_t = get_rope_index(
        processor,
        input_ids=input_ids_t,
        image_grid_thw=image_grid_thw_t,
        attention_mask=attention_mask_t,
    )

    input_ids_t, attention_mask_t, position_ids_t = VF.postprocess_data(
        input_ids=input_ids_t,
        attention_mask=attention_mask_t,
        position_ids=position_ids_t,
        max_length=max_prompt_length,
        pad_token_id=tokenizer.pad_token_id,
        left_pad=True,
        truncation="right",
    )

    row: dict[str, Any] = {
        "input_ids": input_ids_t,
        "attention_mask": attention_mask_t,
        "position_ids": position_ids_t,
        "raw_prompt_ids": tokenizer.encode(
            processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            ),
            add_special_tokens=False,
        ),
        "multi_modal_data": {"image": image_inputs},
    }
    if pixel_values_t is not None:
        row["multi_modal_inputs"] = {
            "pixel_values": pixel_values_t,
            "image_grid_thw": image_grid_thw_t,
        }
    else:
        row["multi_modal_inputs"] = {}

    if response_text is None:
        return row

    # --- Response segment ---------------------------------------------------
    assert max_response_length is not None, (
        "max_response_length must be provided when response_text is set"
    )
    response = response_text + "<|im_end|>\n"
    enc_response = processor(None, [response], add_special_tokens=False, return_tensors="pt")
    response_ids = pad_2d_list_to_length(
        enc_response["input_ids"],
        tokenizer.pad_token_id,
        max_length=max_response_length,
    )
    response_attention_mask = get_response_mask(
        response_id=response_ids,
        eos_token=tokenizer.eos_token_id,
        dtype=attention_mask_t.dtype,
    )

    # Concatenate prompt + response for full-sequence training tensors.
    full_attention_mask = torch.cat(
        (attention_mask_t, response_attention_mask[0]), dim=-1
    )
    full_input_ids = torch.cat((input_ids_t, response_ids[0]), dim=-1)
    full_position_ids = get_rope_index(
        processor,
        input_ids=full_input_ids,
        image_grid_thw=image_grid_thw_t,
        attention_mask=full_attention_mask,
    )
    full_input_ids, full_attention_mask, full_position_ids = VF.postprocess_data(
        input_ids=full_input_ids,
        attention_mask=full_attention_mask,
        position_ids=full_position_ids,
        max_length=max_prompt_length + max_response_length,
        pad_token_id=tokenizer.pad_token_id,
        left_pad=False,
        truncation="right",
    )

    row["input_ids"] = full_input_ids
    row["attention_mask"] = full_attention_mask
    row["position_ids"] = full_position_ids[:, : full_input_ids.size(0)]
    row["responses"] = response_ids[:, :max_response_length][0]
    row["response_attention_mask"] = response_attention_mask[:, :max_response_length]
    return row


def assign_step_rewards(
    rows: list[dict[str, Any]],
    outcome_reward: float,
    *,
    gamma: float = 1.0,
    outcome_scale: float = 1.0,
) -> list[dict[str, Any]]:
    """In-place add ``step_return_label`` to each row using an MC discount.

    ``step_t_return = outcome_reward * gamma^(T - 1 - t) / outcome_scale``
    where ``T = len(rows)`` and ``t = row['step_idx']``. The label is masked
    to the response tokens so non-response positions get 0.
    """
    horizon = len(rows)
    for row in rows:
        step_idx = row.get("step_idx", 0)
        discounted = outcome_reward * (gamma ** (horizon - 1 - step_idx)) / outcome_scale
        label = torch.tensor(discounted, dtype=torch.float32)
        if "response_attention_mask" in row:
            mask = row["response_attention_mask"][0].to(torch.float32)
            row["step_return_label"] = mask * label
        else:
            row["step_return_label"] = label
    return rows
