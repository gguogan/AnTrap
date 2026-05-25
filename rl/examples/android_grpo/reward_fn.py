"""Reward functions for Android GRPO training.

Implements MC-return style reward assignment with configurable discount factor.
"""

import torch
import numpy as np


def assign_trajectory_rewards(
    outcome_reward: float,
    num_steps: int,
    reward_discount: float = 1.0,
) -> list[float]:
    """Assign trajectory-level outcome reward to each step with MC discount.

    Args:
        outcome_reward: 0.0 or 1.0 from AndroidWorld is_successful()
        num_steps: total number of steps in the trajectory
        reward_discount: gamma for MC return. 1.0 = equal weight, <1.0 = later steps get more.

    Returns:
        List of per-step rewards, length num_steps.
        step t gets: outcome_reward * gamma^(T - t), where T = num_steps - 1
    """
    if num_steps == 0:
        return []
    T = num_steps - 1
    return [outcome_reward * (reward_discount ** (T - t)) for t in range(num_steps)]


def build_token_level_rewards(
    step_rewards: list[float],
    response_lengths: list[int],
    max_response_length: int,
) -> torch.Tensor:
    """Build token-level reward tensor for a single trajectory.

    Places the step reward on the last valid token of each response.

    Args:
        step_rewards: per-step rewards from assign_trajectory_rewards()
        response_lengths: number of valid tokens in each step's response
        max_response_length: max response length for padding

    Returns:
        Tensor of shape (num_steps, max_response_length)
    """
    num_steps = len(step_rewards)
    rewards = torch.zeros(num_steps, max_response_length)
    for i, (r, length) in enumerate(zip(step_rewards, response_lengths)):
        if length > 0:
            rewards[i, length - 1] = r
    return rewards


def compute_grpo_index(
    task_ids: list,
    num_envs: int,
    trajectories_per_task: int,
) -> np.ndarray:
    """Compute GRPO grouping index from task assignments.

    All trajectories of the same task share the same index.

    Args:
        task_ids: list of task identifiers, one per trajectory
        num_envs: total number of environments
        trajectories_per_task: N trajectories per task

    Returns:
        numpy array of shape (total_steps_across_all_trajectories,)
        where steps from the same task share the same index value.
    """
    # Map task_ids to integer indices
    unique_tasks = list(dict.fromkeys(task_ids))  # preserve order
    task_to_idx = {task: idx for idx, task in enumerate(unique_tasks)}
    return np.array([task_to_idx[tid] for tid in task_ids])
