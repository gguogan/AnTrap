#!/bin/bash
# Claude Sonnet 4.6 parallel runner for AndroidWorld.
#
# API key + endpoint are read (in order): `--api_key`/`--endpoint` flag >
# shell `CLAUDE_API_KEY` / `ANTHROPIC_API_KEY` (and `CLAUDE_ENDPOINT` /
# `ANTHROPIC_BASE_URL`) > `<repo>/.env`.
#
# By default the wrapper auto-detects the API style from the endpoint host:
#   api.anthropic.com -> /v1/messages   (anthropic native)
#   anything else     -> /v1/chat/completions  (openai-compat)
# Override explicitly with API_STYLE=anthropic|openai.

MODEL="${MODEL:-claude-sonnet-4-6}"
NUM_WORKERS="${NUM_WORKERS:-4}"
PERFORM_EMULATOR_SETUP="${PERFORM_EMULATOR_SETUP:-False}"

# Claude sampling defaults.
TEMPERATURE="${TEMPERATURE:-1.0}"
MAX_TOKENS="${MAX_TOKENS:-4096}"
THINKING_BUDGET_TOKENS="${THINKING_BUDGET_TOKENS:-0}"
API_STYLE="${API_STYLE:-}"

mkdir -p log/origin/${MODEL} trajectory/origin/${MODEL}

RESUME_LOG="$1"

if [ -n "$RESUME_LOG" ]; then
    echo "Resuming from: $RESUME_LOG"
    current_time=$(date +"%Y-%m-%d_%H-%M-%S")
    LOG="log/origin/${MODEL}/log_${MODEL}_parallel_resume_${current_time}.log"

    python scripts/origin/parallel/run_claude_parallel.py \
      --suite_family=android_world \
      --model=$MODEL \
      --num_workers=$NUM_WORKERS \
      --task_random_seed=30 \
      --temperature=$TEMPERATURE \
      --max_tokens=$MAX_TOKENS \
      --thinking_budget_tokens=$THINKING_BUDGET_TOKENS \
      --api_style="$API_STYLE" \
      --max_history_images=${MAX_HISTORY_IMAGES:-3} \
      --console_ports=5554,5556,5558,5560,5562,5564,5566,5568 \
      --grpc_ports=8554,8556,8558,8560,8562,8564,8566,8568 \
      --perform_emulator_setup=$PERFORM_EMULATOR_SETUP \
      --resume_log="$RESUME_LOG" 2>&1 | tee "$LOG"
else
    current_time=$(date +"%Y-%m-%d_%H-%M-%S")
    LOG="log/origin/${MODEL}/log_${MODEL}_parallel_${current_time}.log"
    TRAJ_OUTPUT_PATH="trajectory/origin/${MODEL}/traj_${MODEL}_parallel_${current_time}"

    python scripts/origin/parallel/run_claude_parallel.py \
      --suite_family=android_world \
      --model=$MODEL \
      --traj_output_path=$TRAJ_OUTPUT_PATH \
      --num_workers=$NUM_WORKERS \
      --task_random_seed=30 \
      --temperature=$TEMPERATURE \
      --max_tokens=$MAX_TOKENS \
      --thinking_budget_tokens=$THINKING_BUDGET_TOKENS \
      --api_style="$API_STYLE" \
      --max_history_images=${MAX_HISTORY_IMAGES:-3} \
      --console_ports=5554,5556,5558,5560,5562,5564,5566,5568 \
      --grpc_ports=8554,8556,8558,8560,8562,8564,8566,8568 \
      --perform_emulator_setup=$PERFORM_EMULATOR_SETUP 2>&1 | tee "$LOG"
fi
