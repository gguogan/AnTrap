"""Android GRPO trainer.

Orchestrates multi-step environment interaction with N remote Android
emulators and GRPO-based policy updates. Built on top of verl's PPO
machinery (RayPPOTrainer-style components) but with the data source
replaced by a live env loop.

High-level flow per training step
---------------------------------
1. Sample ``tasks_per_batch`` tasks from the task dataset; each task is
   replicated ``trajectories_per_task`` times so that ``num_envs`` Ray env
   workers run in parallel (groups of ``N`` per task feed GRPO advantage).
2. Reset all envs.
3. For each of ``max_steps`` rounds:
   a. Build a vLLM-ready DataProto from currently-active env histories
      (``prepare_policy_logits_input(..., response_text=None)``).
   b. ``actor_rollout_wg.generate_sequences`` to produce one response per
      active env.
   c. Decode responses, dispatch ``.step(response)`` to each env.
4. Evaluate every env (``client.score_task()``) for outcome reward.
5. Collect step-level ``(prompt_messages, response_text)`` pairs from each
   worker (``get_policy_train_dict``), tokenize them with
   ``prepare_policy_logits_input`` into a verl DataProto, attach MC step
   rewards, GRPO uids, and ``response_mask``.
6. Compute GRPO advantage (``compute_grpo_outcome_advantage``), call
   ``actor_rollout_wg.compute_log_prob`` and ``update_actor`` exactly as the
   reference ``RayPPOTrainer`` does.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import numpy as np
import ray
import torch
from omegaconf import DictConfig

from android_dataset import AndroidWorldTaskDataset
from android_worker import AndroidGRPOWorker
from reward_fn import assign_trajectory_rewards, compute_grpo_index
from vlm_tokenization import prepare_policy_logits_input

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _stack_dataproto(rows: list[dict[str, Any]]):
    """Collate per-step rows into the format verl's DataProto expects.

    Returns a dict with stacked tensors + non-tensor side-channels. Caller
    converts to DataProto via ``DataProto.from_single_dict``."""
    from verl.utils.dataset.rl_dataset import collate_fn  # type: ignore

    return collate_fn(rows)


# ---------------------------------------------------------------------------
# Trainer
# ---------------------------------------------------------------------------
class AndroidGRPOTrainer:
    """GRPO trainer for the GUI agent with remote Android environments."""

    def __init__(
        self,
        config: DictConfig,
        actor_rollout_wg,
        tokenizer,
        processor,
        task_dataset: Optional[AndroidWorldTaskDataset] = None,
    ):
        self.config = config
        self.actor_rollout_wg = actor_rollout_wg
        self.tokenizer = tokenizer
        self.processor = processor
        self.task_dataset = task_dataset

        self.env_config = config.env
        self.num_envs = self.env_config.num_envs
        self.trajectories_per_task = self.env_config.trajectories_per_task
        self.tasks_per_batch = self.num_envs // self.trajectories_per_task
        self.max_steps = self.env_config.max_steps
        self.reward_discount = self.env_config.get("reward_discount", 1.0)
        self.server_url = self.env_config.server_url
        self.trap_mode = self.env_config.get("mode", "origin") == "trap"
        self.max_prompt_length = config.data.max_prompt_length
        self.max_response_length = config.data.max_response_length
        self.max_pixels = config.data.get("max_pixels", 1270180)
        self.min_pixels = config.data.get("min_pixels", 256)

        self.env_workers: list = []

        logger.info(
            "AndroidGRPOTrainer: num_envs=%d trajectories_per_task=%d "
            "tasks_per_batch=%d max_steps=%d discount=%g trap_mode=%s",
            self.num_envs,
            self.trajectories_per_task,
            self.tasks_per_batch,
            self.max_steps,
            self.reward_discount,
            self.trap_mode,
        )

    # ------------------------------------------------------------------
    # Env-worker lifecycle
    # ------------------------------------------------------------------
    def _create_envs(self) -> list:
        trap_config = None
        if self.trap_mode:
            tc = self.env_config.get("trap", {})
            trap_config = {
                "category": tc.get("category", "none"),
                "trap_type": tc.get("trap_type", "none"),
                "trigger_probability": tc.get("trigger_probability", 0.3),
                "seed": tc.get("seed", 42),
                "max_traps": tc.get("max_traps", 0),
            }
        workers: list = []
        for i in range(self.num_envs):
            w = AndroidGRPOWorker.remote(
                worker_idx=i,
                server_url=self.server_url,
                emu_id=i,
                max_steps=self.max_steps,
                max_pixels=self.max_pixels,
                min_pixels=self.min_pixels,
                trap_mode=self.trap_mode,
                trap_config=trap_config,
            )
            workers.append(w)
        logger.info("Created %d env workers", len(workers))
        return workers

    # ------------------------------------------------------------------
    # Task batching
    # ------------------------------------------------------------------
    def _sample_task_batch(self, step: int) -> list[dict]:
        """Return ``num_envs`` task configs (``tasks_per_batch`` unique tasks,
        each replicated ``trajectories_per_task`` times)."""
        assert self.task_dataset is not None, "task_dataset must be set before training"
        rng = np.random.default_rng(seed=step)
        task_indices = rng.choice(
            len(self.task_dataset), size=self.tasks_per_batch, replace=False
        )
        batch: list[dict] = []
        for idx in task_indices:
            task = self.task_dataset[int(idx)]
            for _ in range(self.trajectories_per_task):
                batch.append(dict(task))
        return batch

    # ------------------------------------------------------------------
    # Inner loops
    # ------------------------------------------------------------------
    def _build_gen_batch(self, env_outputs: list[dict], active_indices: list[int]):
        """Tokenize current histories of active envs into a vLLM-ready
        ``DataProto`` for ``actor_rollout_wg.generate_sequences``."""
        from verl.protocol import DataProto  # type: ignore

        rows = []
        for idx in active_indices:
            messages = env_outputs[idx]["obs_messages"]
            row = prepare_policy_logits_input(
                messages,
                processor=self.processor,
                tokenizer=self.tokenizer,
                max_prompt_length=self.max_prompt_length,
                max_response_length=None,
                response_text=None,
            )
            rows.append(row)
        return DataProto.from_single_dict(_stack_dataproto(rows))

    def _build_train_batch(self, trajectories: list[dict]):
        """Tokenize all step-level (prompt, response) pairs in this episode
        batch into a single DataProto suitable for GRPO advantage + actor
        update."""
        from verl.protocol import DataProto  # type: ignore

        rows: list[dict[str, Any]] = []
        uids: list[str] = []
        for traj in trajectories:
            task_uid = str(traj["task_id"])
            for pair, reward in zip(traj["train_pairs"], traj["step_rewards"]):
                row = prepare_policy_logits_input(
                    pair["prompt_messages"],
                    processor=self.processor,
                    tokenizer=self.tokenizer,
                    max_prompt_length=self.max_prompt_length,
                    max_response_length=self.max_response_length,
                    response_text=pair["response_text"],
                )
                # Attach step-level outcome reward; will be turned into a
                # token-level advantage by compute_grpo_outcome_advantage.
                row["token_level_scores"] = (
                    row["response_attention_mask"][0].to(torch.float32) * reward
                )
                # Carry the task uid through as the GRPO group key.
                row["uid"] = task_uid
                rows.append(row)
                uids.append(task_uid)

        batch_dict = _stack_dataproto(rows)
        batch = DataProto.from_single_dict(batch_dict)
        batch.non_tensor_batch["uid"] = np.array(uids, dtype=object)
        # response_mask is what verl downstream advantage / actor expect.
        batch.batch["response_mask"] = batch.batch["response_attention_mask"]
        return batch

    # ------------------------------------------------------------------
    # One outer training step
    # ------------------------------------------------------------------
    def step(self, global_step: int) -> dict[str, float]:
        """Run one outer training step: rollout, score, build batch, update."""
        from verl.trainer.ppo.core_algos import compute_grpo_outcome_advantage  # type: ignore

        t0 = time.time()
        if not self.env_workers:
            self.env_workers = self._create_envs()

        task_batch = self._sample_task_batch(global_step)
        assert len(task_batch) == self.num_envs

        # --- Reset envs ---
        env_outputs = ray.get([
            w.reset.remote(t["task_type"], t["task_idx"])
            for w, t in zip(self.env_workers, task_batch)
        ])

        # --- Multi-step rollout ---
        for step_idx in range(self.max_steps):
            active_indices = [i for i, o in enumerate(env_outputs) if not o["is_done"]]
            if not active_indices:
                break

            gen_batch = self._build_gen_batch(env_outputs, active_indices)
            gen_output = self.actor_rollout_wg.generate_sequences(gen_batch)
            responses = self.tokenizer.batch_decode(
                gen_output.batch["responses"], skip_special_tokens=True
            )

            step_futures = [
                self.env_workers[idx].step.remote(resp)
                for idx, resp in zip(active_indices, responses)
            ]
            step_results = ray.get(step_futures)
            for idx, result in zip(active_indices, step_results):
                env_outputs[idx] = result

        # --- Evaluate ---
        outcome_rewards = ray.get([
            w.evaluate.remote() for w in self.env_workers
        ])
        train_data_per_worker = ray.get([
            w.get_policy_train_dict.remote() for w in self.env_workers
        ])
        step_counts = ray.get([
            w.get_step_count.remote() for w in self.env_workers
        ])

        trajectories: list[dict] = []
        for i, (pairs, reward, task, n_steps) in enumerate(zip(
            train_data_per_worker, outcome_rewards, task_batch, step_counts,
        )):
            step_rewards = assign_trajectory_rewards(
                outcome_reward=reward,
                num_steps=n_steps,
                reward_discount=self.reward_discount,
            )
            trajectories.append({
                "task_id": task["task_id"],
                "task_type": task["task_type"],
                "outcome_reward": reward,
                "num_steps": n_steps,
                "step_rewards": step_rewards,
                "train_pairs": pairs,
            })

        # --- GRPO batch + advantage + actor update ---
        batch = self._build_train_batch(trajectories)

        # GRPO advantage: group by uid (task_id) and centre / norm the
        # outcome reward across the trajectories_per_task replicas.
        norm_adv_by_std = self.config.algorithm.get("norm_adv_by_std_in_grpo", True)
        advantages, returns = compute_grpo_outcome_advantage(
            token_level_rewards=batch.batch["token_level_scores"],
            response_mask=batch.batch["response_mask"],
            index=batch.non_tensor_batch["uid"],
            norm_adv_by_std_in_grpo=norm_adv_by_std,
        )
        batch.batch["advantages"] = advantages
        batch.batch["returns"] = returns

        # old log probs (for PPO-style clip in GRPO)
        old_log_prob = self.actor_rollout_wg.compute_log_prob(batch)
        batch = batch.union(old_log_prob)

        # actor update
        actor_output = self.actor_rollout_wg.update_actor(batch)

        # --- Metrics ---
        n_success = sum(1 for t in trajectories if t["outcome_reward"] > 0)
        total_steps = sum(t["num_steps"] for t in trajectories)
        metrics = {
            "train/global_step": global_step,
            "train/success_rate": n_success / max(len(trajectories), 1),
            "train/avg_traj_len": total_steps / max(len(trajectories), 1),
            "train/wall_clock_sec": time.time() - t0,
        }
        if isinstance(actor_output, dict) and "metrics" in actor_output:
            metrics.update({f"actor/{k}": v for k, v in actor_output["metrics"].items()})
        return metrics

    # ------------------------------------------------------------------
    # Outer training loop
    # ------------------------------------------------------------------
    def fit(self, task_dataset: AndroidWorldTaskDataset, total_steps: int) -> None:
        self.task_dataset = task_dataset
        for global_step in range(total_steps):
            metrics = self.step(global_step)
            logger.info(
                "step=%d success_rate=%.3f avg_traj_len=%.2f wall=%.1fs",
                metrics.get("train/global_step", global_step),
                metrics.get("train/success_rate", 0.0),
                metrics.get("train/avg_traj_len", 0.0),
                metrics.get("train/wall_clock_sec", 0.0),
            )
