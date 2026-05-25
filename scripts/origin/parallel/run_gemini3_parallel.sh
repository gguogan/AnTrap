#!/bin/bash
# Gemini 3 Pro Preview parallel runner for AndroidWorld.
#
# API key is read (in order): `--api_key` flag > shell `GEMINI_API_KEY` >
# `<repo>/.env`. Copy `.env.example` to `.env` and fill in keys.

MODEL="${MODEL:-gemini-3-pro-preview}"
NUM_WORKERS="${NUM_WORKERS:-4}"
PERFORM_EMULATOR_SETUP="${PERFORM_EMULATOR_SETUP:-False}"

# Gemini 3 recommended defaults for agentic / screenshot use.
TEMPERATURE=1.0
THINKING_LEVEL=high
MEDIA_RESOLUTION=media_resolution_high
MAX_OUTPUT_TOKENS=4096

mkdir -p log/origin/${MODEL} trajectory/origin/${MODEL}

RESUME_LOG="$1"

if [ -n "$RESUME_LOG" ]; then
    echo "Resuming from: $RESUME_LOG"
    current_time=$(date +"%Y-%m-%d_%H-%M-%S")
    LOG="log/origin/${MODEL}/log_${MODEL}_parallel_resume_${current_time}.log"

    python scripts/origin/parallel/run_gemini3_parallel.py \
      --suite_family=android_world \
      --model=$MODEL \
      --num_workers=$NUM_WORKERS \
      --task_random_seed=30 \
      --temperature=$TEMPERATURE \
      --thinking_level=$THINKING_LEVEL \
      --media_resolution=$MEDIA_RESOLUTION \
      --max_output_tokens=$MAX_OUTPUT_TOKENS \
      --max_history_images=${MAX_HISTORY_IMAGES:-3} \
      --console_ports=5554,5556,5558,5560,5562,5564,5566,5568 \
      --grpc_ports=8554,8556,8558,8560,8562,8564,8566,8568 \
      --perform_emulator_setup=$PERFORM_EMULATOR_SETUP \
      --resume_log="$RESUME_LOG" 2>&1 | tee "$LOG"
else
    current_time=$(date +"%Y-%m-%d_%H-%M-%S")
    LOG="log/origin/${MODEL}/log_${MODEL}_parallel_${current_time}.log"
    TRAJ_OUTPUT_PATH="trajectory/origin/${MODEL}/traj_${MODEL}_parallel_${current_time}"

    python scripts/origin/parallel/run_gemini3_parallel.py \
      --suite_family=android_world \
      --model=$MODEL \
      --traj_output_path=$TRAJ_OUTPUT_PATH \
      --num_workers=$NUM_WORKERS \
      --task_random_seed=30 \
      --temperature=$TEMPERATURE \
      --thinking_level=$THINKING_LEVEL \
      --media_resolution=$MEDIA_RESOLUTION \
      --max_output_tokens=$MAX_OUTPUT_TOKENS \
      --max_history_images=${MAX_HISTORY_IMAGES:-3} \
      --console_ports=5554,5556,5558,5560,5562,5564,5566,5568 \
      --grpc_ports=8554,8556,8558,8560,8562,8564,8566,8568 \
      --perform_emulator_setup=$PERFORM_EMULATOR_SETUP 2>&1 | tee "$LOG"
fi
