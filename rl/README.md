# AnTrap RL (UI-TARS GRPO)

GRPO training for GUI agent on AnTrap. Built on
[verl](https://github.com/volcengine/verl).


## 1. Environments

### Training machine

```bash
conda create -n antrap_rl python=3.11 -y
conda activate antrap_rl
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt
```

### Emulator machine

Use the same Docker image as the `androidworld_test` repo (see the parent
README §1). After the container is up, start the emulator pool + FastAPI
server inside it:

```bash
# inside the emulator container
cd /app/workspace/rl/remote_deploy
bash start_emulators.sh        # boots 8 emulators on ports 5554..5568
python android_grpo_server.py  # FastAPI on :29101
```

### SSH tunnel (training machine)

```bash
ssh -L 29101:localhost:29101 user@emulator-host -N &
```

The training process talks to `http://localhost:29101`.

---

## 2. Origin training (no trap)

```bash
bash examples/android_grpo/run_origin.sh
```

This launches `main_grpo.py` with `config/android_grpo_origin.yaml`:
UI-TARS-1.5-7B, 8 GPUs FSDP2, vLLM rollout, 8 emulators, 8 trajectories
per task (GRPO group size = 8).

To override the model path:

```bash
ACTOR_MODEL_PATH=/path/to/UI-TARS-1.5-7B bash examples/android_grpo/run_origin.sh
```

To override any Hydra config field directly:

```bash
bash examples/android_grpo/run_origin.sh \
    env.trajectories_per_task=4 \
    trainer.total_epochs=20
```

---

## 3. Trap training

```bash
bash examples/android_grpo/run_trap.sh env.trap.category=s_layer  env.trap.trap_type=visual_obscuration
bash examples/android_grpo/run_trap.sh env.trap.category=s_layer  env.trap.trap_type=external_interruption
bash examples/android_grpo/run_trap.sh env.trap.category=t_layer  env.trap.trap_type=temporal_conflict
bash examples/android_grpo/run_trap.sh env.trap.category=t_layer  env.trap.trap_type=visual_hallucination
bash examples/android_grpo/run_trap.sh env.trap.category=a_layer  env.trap.trap_type=grounding_error
bash examples/android_grpo/run_trap.sh env.trap.category=a_layer  env.trap.trap_type=type_mismatch
bash examples/android_grpo/run_trap.sh env.trap.category=a_layer  env.trap.trap_type=intent_deviation
bash examples/android_grpo/run_trap.sh env.trap.category=overall  env.trap.trap_type=state_deadlock
bash examples/android_grpo/run_trap.sh env.trap.category=overall  env.trap.trap_type=context_disruption
bash examples/android_grpo/run_trap.sh env.trap.category=overall  env.trap.trap_type=loop
```

Tweakable trap params: `env.trap.trigger_probability` (default `0.3`),
`env.trap.max_traps` (default `0`, unlimited), `env.trap.seed`.
