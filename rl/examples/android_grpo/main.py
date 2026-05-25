"""Main entry point for Android GRPO training.

Follows verl's main_ppo.py structure but with a custom training loop
that interleaves multi-step Android environment interaction with GRPO updates.

Usage:
    conda activate verl
    python -m examples.android_grpo.main \
        --config-path=examples/android_grpo/config \
        --config-name=android_grpo_origin \
        actor_rollout_ref.model.path=/path/to/UI-TARS-1.5-7B

Or via the shell scripts:
    bash examples/android_grpo/run_origin.sh
"""

import base64
import io
import os
import socket
import sys
import time
import uuid
from collections import defaultdict
from copy import deepcopy
from pprint import pprint

import hydra
import numpy as np
import ray
import torch
from omegaconf import OmegaConf

sys.path.insert(0, os.path.dirname(__file__))

from android_dataset import AndroidWorldTaskDataset
from android_env_client import AndroidEnvClientPool
from android_worker import AndroidGRPOWorker, parse_action, prepare_system_prompt
from reward_fn import assign_trajectory_rewards
from sft_collector import SFTTrajectoryCollector


# ---------------------------------------------------------------------------
# Tokenization helpers
# ---------------------------------------------------------------------------

def pil_to_base64_uri(img):
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"


def messages_to_vllm_chat(history_messages):
    """Convert internal message format to vLLM chat format."""
    out = []
    for msg in history_messages:
        parts = []
        for p in msg["content"]:
            if p["type"] == "text":
                parts.append({"type": "text", "text": p["text"]})
            elif p["type"] == "image":
                parts.append({"type": "image_url", "image_url": {"url": pil_to_base64_uri(p["image"])}})
        out.append({"role": msg["role"], "content": parts})
    return out


# ---------------------------------------------------------------------------
# Main training function
# ---------------------------------------------------------------------------

def run_android_grpo(config):
    """Run the Android GRPO training loop.

    Architecture:
    1. Initialize vLLM for inference (generate actions from screenshots)
    2. Multi-step rollout: model generates actions → remote env executes → new screenshot → repeat
    3. Collect trajectories, assign MC-discounted rewards
    4. GRPO update: compute advantage within task groups, update policy

    For now, we use vLLM offline inference. Full verl hybrid_engine integration
    (FSDP training + vLLM inference weight sync) is the next step.
    """
    from vllm import LLM, SamplingParams

    print(f"Host: {socket.gethostname()}, PID: {os.getpid()}")
    pprint(OmegaConf.to_container(config, resolve=True))
    OmegaConf.resolve(config)

    # --- Config ---
    env_config = config.env
    num_envs = env_config.num_envs
    trajectories_per_task = env_config.trajectories_per_task
    tasks_per_batch = num_envs // trajectories_per_task
    max_steps = env_config.max_steps
    reward_discount = env_config.get("reward_discount", 1.0)
    server_url = env_config.server_url
    trap_mode = env_config.get("mode", "origin") == "trap"
    model_path = config.actor_rollout_ref.model.path
    total_epochs = config.trainer.total_epochs

    print(f"\n=== Android GRPO Training ===")
    print(f"Model: {model_path}")
    print(f"Envs: {num_envs}, N={trajectories_per_task}, tasks/batch={tasks_per_batch}")
    print(f"Max steps: {max_steps}, reward_discount: {reward_discount}")
    print(f"Mode: {'trap' if trap_mode else 'origin'}")
    print(f"Server: {server_url}")
    print(f"Epochs: {total_epochs}")

    # --- Initialize vLLM ---
    print(f"\nLoading model...")
    llm = LLM(
        model=model_path,
        tensor_parallel_size=config.actor_rollout_ref.rollout.get("tensor_model_parallel_size", 1),
        max_model_len=config.data.get("max_prompt_length", 8192),
        gpu_memory_utilization=config.actor_rollout_ref.rollout.get("gpu_memory_utilization", 0.8),
        trust_remote_code=True,
        limit_mm_per_prompt={"image": max_steps + 1},
    )
    sampling_params = SamplingParams(
        temperature=config.actor_rollout_ref.rollout.get("temperature", 0.7),
        max_tokens=config.data.get("max_response_length", 512),
        stop=["<|im_end|>"],
    )
    print("Model loaded.")

    # --- Initialize environment clients ---
    print(f"\nConnecting to {num_envs} emulators...")
    pool = AndroidEnvClientPool(server_url, num_emulators=num_envs)
    health = pool.health_check()
    n_healthy = sum(health.values())
    print(f"Healthy: {n_healthy}/{num_envs}")
    assert n_healthy == num_envs, f"Not all emulators healthy: {health}"

    # --- Initialize task dataset ---
    task_dataset = AndroidWorldTaskDataset(
        server_url=server_url,
        trajectories_per_task=trajectories_per_task,
    )
    print(f"Tasks available: {len(task_dataset)}")

    # --- Trap config ---
    trap_config = None
    if trap_mode:
        trap_cfg = env_config.get("trap", {})
        trap_config = {
            "category": trap_cfg.get("category", "none"),
            "trap_type": trap_cfg.get("trap_type", "none"),
            "trigger_probability": trap_cfg.get("trigger_probability", 0.3),
            "seed": trap_cfg.get("seed", 42),
            "max_traps": trap_cfg.get("max_traps", 0),
        }

    # --- SFT collector ---
    sft_dir = os.path.join("checkpoints", config.trainer.experiment_name, "sft_data")
    sft_collector = SFTTrajectoryCollector(sft_dir)

    # --- Training loop ---
    global_step = 0
    for epoch in range(total_epochs):
        # Get batch of tasks (with GRPO grouping)
        task_batch = task_dataset.get_batch(num_envs)
        print(f"\n{'='*60}")
        print(f"Epoch {epoch}, Step {global_step}")
        unique_tasks = list({t["task_id"] for t in task_batch})
        print(f"Tasks: {unique_tasks}")

        # ------ Phase 1: Multi-step Rollout ------
        # Each emulator runs an independent trajectory
        histories = [None] * num_envs   # conversation histories
        is_done = [False] * num_envs
        step_responses = [[] for _ in range(num_envs)]  # model responses per env

        # Reset all envs
        print(f"\nResetting {num_envs} envs...")
        for i in range(num_envs):
            client = pool[i]
            task = task_batch[i]
            client.reset(go_home=True)
            if trap_mode and trap_config:
                client.configure_trap(**trap_config)
                client.trap_reset()
            client.initialize_task(task["task_type"], task["task_idx"])
            goal = client.get_goal()

            # Get initial screenshot
            if trap_mode:
                screenshot, _ = client.trap_screenshot(step_idx=0)
            else:
                screenshot = client.screenshot()

            # Build initial messages
            histories[i] = [
                {"role": "system", "content": [{"type": "text", "text": "You are a helpful assistant."}]},
                {"role": "user", "content": [{"type": "text", "text": prepare_system_prompt(goal)}]},
                {"role": "user", "content": [{"type": "image", "image": screenshot}]},
            ]
        print("All envs reset.")

        # Multi-step interaction
        for step_idx in range(max_steps):
            active = [i for i in range(num_envs) if not is_done[i]]
            if not active:
                break

            # Batch generate for all active envs
            vllm_inputs = []
            for i in active:
                vllm_inputs.append(messages_to_vllm_chat(histories[i]))

            t0 = time.time()
            outputs = llm.chat(vllm_inputs, sampling_params=sampling_params)
            gen_time = time.time() - t0

            # Process responses and execute actions
            n_finished = 0
            for idx, i in enumerate(active):
                response_text = outputs[idx].outputs[0].text
                step_responses[i].append(response_text)

                # Parse action
                action = parse_action(response_text)

                # Append assistant response
                histories[i].append({"role": "assistant", "content": [{"type": "text", "text": response_text}]})

                if action["action_type"] == "finished":
                    is_done[i] = True
                    n_finished += 1
                    continue

                # Execute action
                worker_tmp = AndroidGRPOWorker.__new__(AndroidGRPOWorker)
                action_dict = worker_tmp._action_to_server_format(action)
                try:
                    pool[i].execute_action(action_dict)
                except Exception as e:
                    print(f"  Emu {i} action failed: {e}")
                    is_done[i] = True
                    continue

                time.sleep(1)

                # Get new screenshot
                try:
                    if trap_mode:
                        new_ss, _ = pool[i].trap_screenshot(step_idx)
                    else:
                        new_ss = pool[i].screenshot()
                    histories[i].append({"role": "user", "content": [{"type": "image", "image": new_ss}]})
                except Exception as e:
                    print(f"  Emu {i} screenshot failed: {e}")
                    is_done[i] = True

            n_active = sum(1 for d in is_done if not d)
            print(f"  Step {step_idx}: gen={gen_time:.1f}s, active={n_active}, finished={n_finished}")

            # Mark envs that hit max_steps as done
            if step_idx == max_steps - 1:
                for i in range(num_envs):
                    is_done[i] = True

        # ------ Phase 2: Evaluate ------
        print(f"\nEvaluating...")
        outcome_rewards = []
        for i in range(num_envs):
            try:
                score = pool[i].score_task()
                outcome_rewards.append(1.0 if score else 0.0)
            except Exception:
                outcome_rewards.append(0.0)
            try:
                pool[i].tear_down_task()
            except Exception:
                pass

        n_success = sum(1 for r in outcome_rewards if r > 0)
        print(f"Results: {n_success}/{num_envs} successful")
        print(f"Rewards: {outcome_rewards}")

        # ------ Phase 3: Build GRPO training data ------
        # Collect step-level data with MC-discounted rewards
        all_step_data = []
        for i in range(num_envs):
            n_steps = len(step_responses[i])
            rewards = assign_trajectory_rewards(outcome_rewards[i], n_steps, reward_discount)
            task_id = task_batch[i]["task_id"]

            for s, (resp, rew) in enumerate(zip(step_responses[i], rewards)):
                all_step_data.append({
                    "env_idx": i,
                    "task_id": task_id,
                    "step_idx": s,
                    "response": resp,
                    "reward": rew,
                    "outcome": outcome_rewards[i],
                })

        # GRPO grouping
        task_ids = [d["task_id"] for d in all_step_data]
        rewards_arr = np.array([d["reward"] for d in all_step_data])

        # Group by task_id for GRPO advantage
        task_to_idx = {}
        for d in all_step_data:
            tid = d["task_id"]
            if tid not in task_to_idx:
                task_to_idx[tid] = len(task_to_idx)

        index = np.array([task_to_idx[d["task_id"]] for d in all_step_data])

        # Compute GRPO advantage (per-trajectory, not per-step)
        # Group trajectories by task, compute mean/std of trajectory rewards
        traj_rewards = defaultdict(list)
        for i in range(num_envs):
            tid = task_batch[i]["task_id"]
            traj_rewards[tid].append(outcome_rewards[i])

        traj_advantages = {}
        for tid, rews in traj_rewards.items():
            mean_r = np.mean(rews)
            std_r = np.std(rews) + 1e-6
            traj_advantages[tid] = {
                i: (r - mean_r) / std_r for i, r in enumerate(rews)
            }

        # Assign advantage to each step
        # Track which trajectory index within a task group each env is
        task_traj_counter = defaultdict(int)
        env_to_traj_idx = {}
        for i in range(num_envs):
            tid = task_batch[i]["task_id"]
            env_to_traj_idx[i] = task_traj_counter[tid]
            task_traj_counter[tid] += 1

        for d in all_step_data:
            tid = d["task_id"]
            traj_idx = env_to_traj_idx[d["env_idx"]]
            d["advantage"] = traj_advantages[tid][traj_idx]

        # ------ Phase 4: Log metrics ------
        total_steps = len(all_step_data)
        mean_reward = np.mean(outcome_rewards)
        mean_adv = np.mean([d["advantage"] for d in all_step_data])

        metrics = {
            "epoch": epoch,
            "global_step": global_step,
            "success_rate": n_success / num_envs,
            "mean_outcome_reward": mean_reward,
            "total_step_samples": total_steps,
            "mean_advantage": mean_adv,
        }
        for tid, rews in traj_rewards.items():
            metrics[f"reward/{tid}"] = np.mean(rews)

        print(f"\nMetrics: {metrics}")

        # ------ Phase 5: GRPO Policy Update ------
        # TODO(P5): Integrate with verl's FSDP actor training
        # This requires:
        # 1. Tokenize all step-level (prompt, response) pairs using the VLM processor
        # 2. Build DataProto with input_ids, attention_mask, position_ids, multi_modal_inputs
        # 3. Compute old_log_probs via actor forward pass
        # 4. Compute ref_log_probs via reference model forward pass
        # 5. Apply GRPO advantage and run policy gradient update
        #
        # For now, we log the collected data. The training update will be added
        # once the rollout loop is validated end-to-end.
        print(f"\n[TODO] GRPO policy update with {total_steps} step-level samples")
        print(f"  Advantages distribution: min={min(d['advantage'] for d in all_step_data):.3f}, "
              f"max={max(d['advantage'] for d in all_step_data):.3f}")

        # ------ Collect SFT data ------
        trajectories_for_sft = []
        for i in range(num_envs):
            if outcome_rewards[i] > 0:
                trajectories_for_sft.append({
                    "task_id": task_batch[i]["task_id"],
                    "task_type": task_batch[i]["task_type"],
                    "outcome_reward": outcome_rewards[i],
                    "num_steps": len(step_responses[i]),
                    "train_pairs": [
                        {"response_text": r, "step_idx": s}
                        for s, r in enumerate(step_responses[i])
                    ],
                })
        sft_collector.collect_from_trajectories(trajectories_for_sft)

        global_step += 1

    print(f"\n{'='*60}")
    print(f"Training complete. {global_step} steps, {sft_collector.collected_count} SFT trajectories saved.")


# ---------------------------------------------------------------------------
# Hydra entry point
# ---------------------------------------------------------------------------

@hydra.main(config_path="config", config_name="android_grpo_origin", version_base=None)
def main(config):
    run_android_grpo(config)


if __name__ == "__main__":
    main()
