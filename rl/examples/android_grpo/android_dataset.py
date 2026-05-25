"""Task dataset for Android GRPO training.

Loads AndroidWorld task configurations and assigns them to emulators
with GRPO grouping (N trajectories per task).
"""

import json
import logging
import random
from typing import Any

import requests
from torch.utils.data import Dataset

logger = logging.getLogger(__name__)


class AndroidWorldTaskDataset(Dataset):
    """Dataset of AndroidWorld task configurations.

    Each item represents a task that can be initialized on a remote emulator.
    Tasks are repeated based on trajectories_per_task for GRPO grouping.
    """

    def __init__(
        self,
        task_list: list[dict[str, Any]] | None = None,
        server_url: str = "http://localhost:29101",
        trajectories_per_task: int = 4,
        seed: int = 42,
    ):
        """
        Args:
            task_list: Pre-defined list of {"task_type": str, "task_idx": int}.
                       If None, fetches from server.
            server_url: URL of the remote Android server.
            trajectories_per_task: N trajectories per task for GRPO.
            seed: Random seed for shuffling.
        """
        self.trajectories_per_task = trajectories_per_task

        if task_list is not None:
            self.tasks = task_list
        else:
            self.tasks = self._fetch_tasks(server_url)

        self.rng = random.Random(seed)
        logger.info(f"AndroidWorldTaskDataset: {len(self.tasks)} unique tasks, N={trajectories_per_task}")

    def _fetch_tasks(self, server_url: str) -> list[dict]:
        """Fetch available tasks from remote server."""
        try:
            resp = requests.get(f"{server_url}/suite/task_list", timeout=30)
            resp.raise_for_status()
            data = resp.json()
            task_types = data["task_list"]

            tasks = []
            for task_type in task_types:
                # Get task count for this type
                # Default to index 0 (single combination)
                tasks.append({"task_type": task_type, "task_idx": 0})

            return tasks
        except Exception as e:
            logger.error(f"Failed to fetch tasks from server: {e}")
            raise

    def __len__(self) -> int:
        return len(self.tasks)

    def __getitem__(self, idx: int) -> dict:
        task = self.tasks[idx]
        return {
            "task_type": task["task_type"],
            "task_idx": task["task_idx"],
            "task_id": f"{task['task_type']}_{task['task_idx']}",
        }

    def get_batch(self, num_envs: int) -> list[dict]:
        """Get a batch of task assignments for all emulators.

        Returns a list of length num_envs, where each element is a task config.
        Every trajectories_per_task consecutive entries share the same task.

        Example with num_envs=8, trajectories_per_task=4:
            [TaskA, TaskA, TaskA, TaskA, TaskB, TaskB, TaskB, TaskB]
        """
        tasks_per_batch = num_envs // self.trajectories_per_task
        assert num_envs % self.trajectories_per_task == 0, (
            f"num_envs ({num_envs}) must be divisible by trajectories_per_task ({self.trajectories_per_task})"
        )

        # Sample tasks
        selected = self.rng.sample(
            range(len(self.tasks)),
            min(tasks_per_batch, len(self.tasks)),
        )

        # If not enough unique tasks, allow repeats
        while len(selected) < tasks_per_batch:
            selected.append(self.rng.randint(0, len(self.tasks) - 1))

        # Expand: each task repeated N times
        batch = []
        for task_idx in selected:
            task = self[task_idx]
            for _ in range(self.trajectories_per_task):
                batch.append(task.copy())

        return batch
