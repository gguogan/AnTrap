#!/bin/bash

# Qwen3-VL Agent Test Script
# This script runs the Qwen3-VL agent on the Android World benchmark

MODEL_SHORT="Qwen3-VL-8B"
mkdir -p log/${MODEL_SHORT} trajectory/${MODEL_SHORT}

current_time=$(date +"%Y-%m-%d_%H-%M-%S")
LOG="log/${MODEL_SHORT}/log_qwen3vl_"$current_time".log"

# Model configuration
MODEL_NAME="qwen3vl"
MODEL="/path/to/hf/hub/models--Qwen--Qwen3-VL-8B-Instruct/snapshots/0c351dd01ed87e9c1b53cbc748cba10e6187ff3b"
API_KEY="EMPTY"
BASE_URL="${BASE_URL:-http://localhost:9001/v1}"
TRAJ_OUTPUT_PATH="trajectory/${MODEL_SHORT}/traj_qwen3vl_"$current_time

# Run Qwen3-VL agent
python scripts/origin/serial/run_qwen3vl.py \
  --suite_family=android_world \
  --agent_name=$MODEL_NAME \
  --model=$MODEL \
  --api_key=$API_KEY \
  --base_url=$BASE_URL \
  --traj_output_path=$TRAJ_OUTPUT_PATH \
  --n_task_combinations=1 \
  --task_random_seed=30 \
  --grpc_port=8554 \
  --perform_emulator_setup=$PERFORM_EMULATOR_SETUP \
  --console_port=5554 \
  --max_history_images=4 2>&1 | tee "$LOG"
# --tasks=NotesTodoItemCount \

# Note:
# 1. Make sure the vLLM server is running before executing this script
#    You can start it with: bash run_vllm.sh (modify the model path for Qwen3-VL)
# 2. Set perform_emulator_setup=True only for the first run
# 3. You can specify specific tasks with --tasks=TaskName1,TaskName2