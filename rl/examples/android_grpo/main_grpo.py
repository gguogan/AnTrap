"""Entry point for UI-TARS GRPO training on Android(World).

Glues together:

* verl's standard FSDP2 actor + vLLM rollout RayWorkerGroup
  (no critic -- GRPO does not need one).
* ``AndroidGRPOTrainer`` from this directory, which drives the env loop
  and GRPO advantage / actor update on top of verl's worker group.

Hydra-driven; see ``config/android_grpo_origin.yaml`` /
``config/android_grpo_trap.yaml`` for hyper-parameters and
``run_origin.sh`` / ``run_trap.sh`` for the canonical launch commands.
"""

from __future__ import annotations

import os
import socket
import sys
from pprint import pprint

import hydra
import ray
from omegaconf import OmegaConf

sys.path.insert(0, os.path.dirname(__file__))


@hydra.main(config_path="config", config_name="android_grpo_origin", version_base=None)
def main(config) -> None:
    if not ray.is_initialized():
        from verl.trainer.constants_ppo import get_ppo_ray_runtime_env  # type: ignore

        default_env = get_ppo_ray_runtime_env()
        ray_init_kwargs = config.ray_kwargs.get("ray_init", {})
        runtime_env_kwargs = ray_init_kwargs.get("runtime_env", {})
        runtime_env = OmegaConf.merge(default_env, runtime_env_kwargs)
        ray_init_kwargs = OmegaConf.create({**ray_init_kwargs, "runtime_env": runtime_env})
        print(f"ray init kwargs: {ray_init_kwargs}")
        ray.init(**OmegaConf.to_container(ray_init_kwargs))
    runner = TaskRunner.remote()
    ray.get(runner.run.remote(config))


@ray.remote(num_cpus=1)
class TaskRunner:
    """Ray remote driver that builds the actor worker group and runs the
    AndroidGRPOTrainer fit loop."""

    def run(self, config):
        from omegaconf import OmegaConf
        from verl.protocol import DataProto  # noqa: F401  -- import warm-up
        from verl.single_controller.ray import RayWorkerGroup
        from verl.trainer.ppo.ray_trainer import ResourcePoolManager, Role
        from verl.utils.tokenizer import hf_processor, hf_tokenizer
        from verl.utils.fs import copy_to_local

        from android_dataset import AndroidWorldTaskDataset
        from android_grpo_trainer import AndroidGRPOTrainer

        print(f"Driver host: {socket.gethostname()}  PID: {os.getpid()}")
        pprint(OmegaConf.to_container(config, resolve=True))
        OmegaConf.resolve(config)

        # ------------------------------------------------------------------
        # Tokenizer + processor (shared across the trainer + workers via
        # function-call serialization).
        # ------------------------------------------------------------------
        model_local_path = copy_to_local(config.actor_rollout_ref.model.path)
        tokenizer = hf_tokenizer(
            model_local_path,
            trust_remote_code=config.data.get("trust_remote_code", True),
            use_fast=True,
        )
        processor = hf_processor(
            model_local_path,
            trust_remote_code=config.data.get("trust_remote_code", True),
            use_fast=True,
        )

        # ------------------------------------------------------------------
        # Actor / rollout worker group (FSDP2 + vLLM, no critic).
        # ------------------------------------------------------------------
        from verl.workers.fsdp_workers import (  # type: ignore
            ActorRolloutRefWorker,
            AsyncActorRolloutRefWorker,
        )

        actor_rollout_cls = (
            AsyncActorRolloutRefWorker
            if config.actor_rollout_ref.rollout.get("mode", "sync") == "async"
            else ActorRolloutRefWorker
        )

        role_worker_mapping = {Role.ActorRolloutRef: ray.remote(actor_rollout_cls)}
        global_pool_id = "global_pool"
        resource_pool_spec = {
            global_pool_id: [config.trainer.n_gpus_per_node] * config.trainer.nnodes,
        }
        mapping = {Role.ActorRolloutRef: global_pool_id}
        resource_pool_manager = ResourcePoolManager(
            resource_pool_spec=resource_pool_spec, mapping=mapping
        )
        resource_pool_manager.create_resource_pool()
        actor_rollout_wg = RayWorkerGroup(
            resource_pool=resource_pool_manager.get_resource_pool(Role.ActorRolloutRef),
            ray_cls_with_init=role_worker_mapping[Role.ActorRolloutRef].options(
                runtime_env={"env_vars": {}},
            ),
            config=config.actor_rollout_ref,
            name_prefix="actor_rollout",
        )
        actor_rollout_wg.init_model()

        # ------------------------------------------------------------------
        # Task dataset + trainer.
        # ------------------------------------------------------------------
        task_dataset = AndroidWorldTaskDataset(
            server_url=config.env.server_url,
            trajectories_per_task=config.env.trajectories_per_task,
        )
        trainer = AndroidGRPOTrainer(
            config=config,
            actor_rollout_wg=actor_rollout_wg,
            tokenizer=tokenizer,
            processor=processor,
            task_dataset=task_dataset,
        )

        total_outer_steps = (
            config.trainer.total_epochs
            * max(1, len(task_dataset) // trainer.tasks_per_batch)
        )
        trainer.fit(task_dataset=task_dataset, total_steps=total_outer_steps)


if __name__ == "__main__":
    main()
