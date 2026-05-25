"""End-to-end test: UI-TARS model + remote Android emulator.

Runs a single task on 1 emulator with real model inference.
Uses vLLM offline inference (no server needed, just GPU).

Usage:
    conda activate verl
    python test_e2e_with_model.py
    python test_e2e_with_model.py --emu_id 2 --max_steps 5
"""

import argparse
import base64
import io
import sys
import time

sys.path.insert(0, ".")

from android_env_client import AndroidEnvClient
from android_worker import parse_action, prepare_system_prompt, AndroidGRPOWorker


def image_to_base64_uri(img):
    """Convert PIL Image to base64 data URI for vLLM."""
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/jpeg;base64,{b64}"


def build_vllm_messages(history_messages):
    """Convert our internal message format to vLLM chat format.

    Converts PIL Images to base64 URIs for the vLLM API.
    """
    vllm_messages = []
    for msg in history_messages:
        role = msg["role"]
        content_parts = msg["content"]
        new_content = []
        for part in content_parts:
            if part["type"] == "text":
                new_content.append({"type": "text", "text": part["text"]})
            elif part["type"] == "image":
                img = part["image"]
                uri = image_to_base64_uri(img)
                new_content.append({"type": "image_url", "image_url": {"url": uri}})
        vllm_messages.append({"role": role, "content": new_content})
    return vllm_messages


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server_url", default="http://localhost:29101")
    parser.add_argument("--model_path", default="/path/to/hf/hub/models--ByteDance-Seed--UI-TARS-1.5-7B")
    parser.add_argument("--emu_id", type=int, default=2)
    parser.add_argument("--max_steps", type=int, default=5)
    parser.add_argument("--task", default="ClockStopWatchRunning")
    parser.add_argument("--task_idx", type=int, default=0)
    args = parser.parse_args()

    # --- 1. Initialize vLLM ---
    print(f"Loading model from {args.model_path}...")
    from vllm import LLM, SamplingParams

    llm = LLM(
        model=args.model_path,
        tensor_parallel_size=1,
        max_model_len=8192,
        gpu_memory_utilization=0.8,
        trust_remote_code=True,
        limit_mm_per_prompt={"image": 5},
    )
    sampling_params = SamplingParams(
        temperature=0.7,
        max_tokens=512,
        stop=["<|im_end|>"],
    )
    print("Model loaded.")

    # --- 2. Connect to emulator ---
    client = AndroidEnvClient(args.server_url, emu_id=args.emu_id)
    print(f"Using emulator {args.emu_id}")

    # --- 3. Reset + init task ---
    print(f"\nResetting emu {args.emu_id}...")
    client.reset(go_home=True)
    client.initialize_task(args.task, args.task_idx)
    goal = client.get_goal()
    print(f"Task: {args.task}, Goal: {goal}")

    # --- 4. Build initial messages ---
    initial_screenshot = client.screenshot()
    print(f"Initial screenshot: {initial_screenshot.size}")

    user_prompt = prepare_system_prompt(goal)
    history = [
        {"role": "system", "content": [{"type": "text", "text": "You are a helpful assistant."}]},
        {"role": "user", "content": [{"type": "text", "text": user_prompt}]},
        {"role": "user", "content": [{"type": "image", "image": initial_screenshot}]},
    ]

    # --- 5. Multi-step interaction ---
    for step in range(args.max_steps):
        print(f"\n--- Step {step} ---")

        # Convert to vLLM format
        vllm_messages = build_vllm_messages(history)

        # Generate
        t0 = time.time()
        outputs = llm.chat(vllm_messages, sampling_params=sampling_params)
        response_text = outputs[0].outputs[0].text
        dt = time.time() - t0
        print(f"Model response ({dt:.1f}s):\n{response_text[:200]}")

        # Parse action
        action = parse_action(response_text)
        print(f"Parsed action: {action}")

        # Check if done
        if action["action_type"] == "finished":
            print("Agent says finished.")
            history.append({"role": "assistant", "content": [{"type": "text", "text": response_text}]})
            break

        # Convert to server format and execute
        worker = AndroidGRPOWorker.__new__(AndroidGRPOWorker)
        action_dict = worker._action_to_server_format(action)
        print(f"Server action: {action_dict}")

        try:
            client.execute_action(action_dict)
        except Exception as e:
            print(f"Action failed: {e}")
            break

        # Append to history
        history.append({"role": "assistant", "content": [{"type": "text", "text": response_text}]})

        time.sleep(2)

        # Get new screenshot
        new_screenshot = client.screenshot()
        print(f"New screenshot: {new_screenshot.size}")
        history.append({"role": "user", "content": [{"type": "image", "image": new_screenshot}]})

    # --- 6. Evaluate ---
    print(f"\n--- Evaluation ---")
    score = client.score_task()
    print(f"Task successful: {score}")

    client.tear_down_task()
    print("Done!")


if __name__ == "__main__":
    main()
