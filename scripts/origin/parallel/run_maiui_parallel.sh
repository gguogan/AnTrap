#!/bin/bash
MODEL="${MODEL:-MAI-UI-8B}"
mkdir -p log/origin/${MODEL} trajectory/origin/${MODEL}

API_KEY="EMPTY"
BASE_URL="${BASE_URL:-http://localhost:9001/v1}"
NUM_WORKERS=8
PERFORM_EMULATOR_SETUP="${PERFORM_EMULATOR_SETUP:-False}"

# MAI-UI default sampling: deterministic decoding
TEMPERATURE="${TEMPERATURE:-0.0}"
TOP_P="${TOP_P:-1.0}"
TOP_K="${TOP_K:--1}"
MAX_TOKENS="${MAX_TOKENS:-2048}"
PRESENCE_PENALTY="${PRESENCE_PENALTY:-0.0}"

# Resume mode: pass a previous log file as first argument
RESUME_LOG="$1"

if [ -n "$RESUME_LOG" ]; then
    echo "Resuming from: $RESUME_LOG"
    current_time=$(date +"%Y-%m-%d_%H-%M-%S")
    LOG="log/origin/${MODEL}/log_${MODEL}_parallel_resume_${current_time}.log"

    python scripts/origin/parallel/run_maiui_parallel.py \
      --suite_family=android_world \
      --model=$MODEL \
      --api_key=$API_KEY \
      --base_url=$BASE_URL \
      --num_workers=$NUM_WORKERS \
      --task_random_seed=30 \
      --temperature=$TEMPERATURE \
      --top_p=$TOP_P \
      --top_k=$TOP_K \
      --max_tokens=$MAX_TOKENS \
      --presence_penalty=$PRESENCE_PENALTY \
      --console_ports=5554,5556,5558,5560,5562,5564,5566,5568 \
      --grpc_ports=8554,8556,8558,8560,8562,8564,8566,8568 \
      --perform_emulator_setup=$PERFORM_EMULATOR_SETUP \
      --resume_log="$RESUME_LOG" 2>&1 | tee "$LOG"
else
    current_time=$(date +"%Y-%m-%d_%H-%M-%S")
    LOG="log/origin/${MODEL}/log_${MODEL}_parallel_${current_time}.log"
    TRAJ_OUTPUT_PATH="trajectory/origin/${MODEL}/traj_${MODEL}_parallel_${current_time}"

    python scripts/origin/parallel/run_maiui_parallel.py \
      --suite_family=android_world \
      --model=$MODEL \
      --api_key=$API_KEY \
      --base_url=$BASE_URL \
      --traj_output_path=$TRAJ_OUTPUT_PATH \
      --num_workers=$NUM_WORKERS \
      --task_random_seed=30 \
      --temperature=$TEMPERATURE \
      --top_p=$TOP_P \
      --top_k=$TOP_K \
      --max_tokens=$MAX_TOKENS \
      --presence_penalty=$PRESENCE_PENALTY \
      --console_ports=5554,5556,5558,5560,5562,5564,5566,5568 \
      --grpc_ports=8554,8556,8558,8560,8562,8564,8566,8568 \
      --perform_emulator_setup=$PERFORM_EMULATOR_SETUP 2>&1 | tee "$LOG"
fi
