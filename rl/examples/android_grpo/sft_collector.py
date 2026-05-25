"""Collects successful trajectories for SFT training.

During GRPO training, trajectories where the task is completed successfully
(outcome_reward=1.0) are saved as multi-turn conversation data for later SFT.
"""

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


class SFTTrajectoryCollector:
    """Saves successful trajectories as SFT training data."""

    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.collected_count = 0

    def collect_from_trajectories(self, trajectories: list[dict]) -> int:
        """Collect successful trajectories after a GRPO rollout batch.

        Args:
            trajectories: list from AndroidGRPOTrainer.run_rollout_batch()

        Returns:
            Number of trajectories saved.
        """
        saved = 0
        for traj in trajectories:
            if traj["outcome_reward"] > 0:
                self._save_trajectory(traj)
                saved += 1

        self.collected_count += saved
        if saved > 0:
            logger.info(f"SFT collector: saved {saved} trajectories (total: {self.collected_count})")
        return saved

    def _save_trajectory(self, traj: dict):
        """Save a single successful trajectory as JSONL."""
        task_id = traj["task_id"]
        idx = self.collected_count

        # Convert to multi-turn conversation format
        conversation = self._to_conversation(traj)

        output_path = os.path.join(self.output_dir, f"sft_traj_{idx:06d}_{task_id}.jsonl")
        with open(output_path, "w") as f:
            f.write(json.dumps(conversation, ensure_ascii=False) + "\n")

    @staticmethod
    def _to_conversation(traj: dict) -> dict:
        """Convert trajectory to multi-turn conversation format.

        Output format (compatible with verl SFT trainer):
        {
            "task_id": str,
            "task_type": str,
            "messages": [
                {"role": "system", "content": "..."},
                {"role": "user", "content": "...(instruction)"},
                {"role": "user", "content": "[screenshot]"},
                {"role": "assistant", "content": "Thought: ...\\nAction: ..."},
                {"role": "user", "content": "[screenshot]"},
                {"role": "assistant", "content": "..."},
                ...
            ]
        }

        Note: screenshots are referenced by path rather than inlined as base64
        to keep the file sizes manageable. The SFT dataloader should resolve them.
        """
        messages = []
        for pair in traj["train_pairs"]:
            # prompt_messages contain the full history up to the screenshot
            # We only need to add the last user message (screenshot) + assistant response
            # to build the incremental conversation
            messages.append({
                "role": "assistant",
                "content": pair["response_text"],
                "step_idx": pair["step_idx"],
            })

        return {
            "task_id": traj["task_id"],
            "task_type": traj["task_type"],
            "outcome_reward": traj["outcome_reward"],
            "num_steps": traj["num_steps"],
            "messages": messages,
        }
