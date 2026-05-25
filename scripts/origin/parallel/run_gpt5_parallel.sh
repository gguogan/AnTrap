#!/bin/bash
# GPT (gpt-5.4 / gpt-5.4-mini) parallel runner for AndroidWorld.
#
# Hits {endpoint}/v1/chat/completions with `Authorization: Bearer sk-...`.
# API key is read (in order): `--api_key` flag > shell `OPENAI_API_KEY` >
# `<repo>/.env`. `OPENAI_BASE_URL` in .env can point at the proxy.
#
# Switch model with:
#   MODEL=gpt-5.4      bash scripts/origin/parallel/run_gpt5_parallel.sh
#   MODEL=gpt-5.4-mini bash scripts/origin/parallel/run_gpt5_parallel.sh

MODEL="${MODEL:-gpt-5.4-mini}"
NUM_WORKERS="${NUM_WORKERS:-4}"
PERFORM_EMULATOR_SETUP="${PERFORM_EMULATOR_SETUP:-False}"

# Sampling. Leave TEMPERATURE/TOP_P unset to use provider defaults.
MAX_OUTPUT_TOKENS=4096

mkdir -p log/origin/${MODEL} trajectory/origin/${MODEL}

RESUME_LOG="$1"

EXTRA_FLAGS=""
if [ -n "$TEMPERATURE" ]; then
    EXTRA_FLAGS="$EXTRA_FLAGS --temperature=$TEMPERATURE"
fi
if [ -n "$TOP_P" ]; then
    EXTRA_FLAGS="$EXTRA_FLAGS --top_p=$TOP_P"
fi

if [ -n "$RESUME_LOG" ]; then
    echo "Resuming from: $RESUME_LOG"
    current_time=$(date +"%Y-%m-%d_%H-%M-%S")
    LOG="log/origin/${MODEL}/log_${MODEL}_parallel_resume_${current_time}.log"

    python scripts/origin/parallel/run_gpt5_parallel.py \
      --suite_family=android_world \
      --model=$MODEL \
      --num_workers=$NUM_WORKERS \
      --task_random_seed=30 \
      --max_output_tokens=$MAX_OUTPUT_TOKENS \
      --max_history_images=${MAX_HISTORY_IMAGES:-3} \
      $EXTRA_FLAGS \
      --console_ports=5554,5556,5558,5560,5562,5564,5566,5568 \
      --grpc_ports=8554,8556,8558,8560,8562,8564,8566,8568 \
      --perform_emulator_setup=$PERFORM_EMULATOR_SETUP \
      --resume_log="$RESUME_LOG" 2>&1 | tee "$LOG"
else
    current_time=$(date +"%Y-%m-%d_%H-%M-%S")
    LOG="log/origin/${MODEL}/log_${MODEL}_parallel_${current_time}.log"
    TRAJ_OUTPUT_PATH="trajectory/origin/${MODEL}/traj_${MODEL}_parallel_${current_time}"

    python scripts/origin/parallel/run_gpt5_parallel.py \
      --suite_family=android_world \
      --model=$MODEL \
      --traj_output_path=$TRAJ_OUTPUT_PATH \
      --num_workers=$NUM_WORKERS \
      --task_random_seed=30 \
      --max_output_tokens=$MAX_OUTPUT_TOKENS \
      --max_history_images=${MAX_HISTORY_IMAGES:-3} \
      $EXTRA_FLAGS \
      --console_ports=5554,5556,5558,5560,5562,5564,5566,5568 \
      --grpc_ports=8554,8556,8558,8560,8562,8564,8566,8568 \
      --perform_emulator_setup=$PERFORM_EMULATOR_SETUP 2>&1 | tee "$LOG"
fi
