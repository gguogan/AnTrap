#!/bin/bash

# UI-TARS Agent Test Script
# This script runs the UI-TARS agent on the Android World benchmark

MODEL_SHORT="UI-TARS-1.5-7B"
mkdir -p log/${MODEL_SHORT} trajectory/${MODEL_SHORT}

current_time=$(date +"%Y-%m-%d_%H-%M-%S")
LOG="log/${MODEL_SHORT}/log_uitars_"$current_time".log"

# Model configuration
MODEL_NAME="ui_tars"
# MODEL="/root/.cache/modelscope/hub/models/iic/UI-TARS-1.5-7B"
# MODEL="/root/.cache/modelscope/UI-TARS-1.5-7B"
MODEL="/path/to/hf/hub/models--ByteDance-Seed--UI-TARS-1.5-7B/snapshots/683d002dd99d8f95104d31e70391a39348857f4e"
API_KEY="EMPTY"
BASE_URL="${BASE_URL:-http://localhost:9001/v1}"
TRAJ_OUTPUT_PATH="trajectory/${MODEL_SHORT}/traj_uitars_"$current_time

# Example for running specific tasks:
python scripts/origin/serial/run_uitars.py \
  --suite_family=android_world \
  --agent_name=$MODEL_NAME \
  --model=$MODEL \
  --api_key=$API_KEY \
  --base_url=$BASE_URL \
  --traj_output_path=$TRAJ_OUTPUT_PATH \
  --grpc_port=8554 \
  --perform_emulator_setup=$PERFORM_EMULATOR_SETUP \
  --console_port=5554 2>&1 | tee "$LOG"
# --tasks=NotesTodoItemCount \
# Run UI-TARS agent
# python scripts/origin/serial/run_uitars.py \
#   --suite_family=android_world \
#   --agent_name=$MODEL_NAME \
#   --model=$MODEL \
#   --api_key=$API_KEY \
#   --base_url=$BASE_URL \
#   --traj_output_path=$TRAJ_OUTPUT_PATH \
#   --grpc_port=8554 \
#   --perform_emulator_setup=$PERFORM_EMULATOR_SETUP \
#   --console_port=5554 2>&1 | tee "$LOG"

# Note:
# 1. Make sure the vLLM server is running before executing this script
#    You can start it with: bash run_vllm.sh (modify the model path for UI-TARS)
# 2. Set perform_emulator_setup=True only for the first run
# 3. You can specify specific tasks with --tasks=TaskName1,TaskName2

