#!/bin/bash
# ============================================================================
# Claude Sonnet 4.6 Parallel Runner with Trap Injection
# ============================================================================
#
# API key + endpoint come from <repo>/.env (CLAUDE_API_KEY/ANTHROPIC_API_KEY,
# CLAUDE_ENDPOINT/ANTHROPIC_BASE_URL). If exported in the shell, those win.
#
# By default the wrapper auto-detects the API style from the endpoint host:
#   api.anthropic.com -> /v1/messages   (anthropic native)
#   anything else     -> /v1/chat/completions  (openai-compat)
# Override explicitly with API_STYLE=anthropic|openai.
#
# Usage:
#   # Baseline (no trap, results -> log/origin/)
#   bash scripts/trap/parallel/run_claude_trap_parallel.sh
#
#   # Specific trap (results -> log/trap/)
#   TRAP_CATEGORY=a_layer TRAP_TYPE=grounding_error \
#     bash scripts/trap/parallel/run_claude_trap_parallel.sh
#
#   # Hit Anthropic native API directly
#   API_STYLE=anthropic CLAUDE_ENDPOINT=https://api.anthropic.com \
#     bash scripts/trap/parallel/run_claude_trap_parallel.sh
# ============================================================================

MODEL="${MODEL:-claude-sonnet-4-6}"
NUM_WORKERS="${NUM_WORKERS:-4}"
PERFORM_EMULATOR_SETUP="${PERFORM_EMULATOR_SETUP:-False}"

# Claude sampling defaults.
TEMPERATURE="${TEMPERATURE:-1.0}"
MAX_TOKENS="${MAX_TOKENS:-4096}"
THINKING_BUDGET_TOKENS="${THINKING_BUDGET_TOKENS:-0}"
API_STYLE="${API_STYLE:-}"

# Trap configuration
TRAP_CATEGORY="${TRAP_CATEGORY:-none}"
TRAP_TYPE="${TRAP_TYPE:-none}"
TRAP_PROBABILITY="${TRAP_PROBABILITY:-0.3}"
TRAP_SEED="${TRAP_SEED:-42}"
MAX_TRAPS="${MAX_TRAPS:-0}"
TRAP_PARAMS="${TRAP_PARAMS:-{}}"

# Output routing: baseline -> log/origin/<model>/, trap -> log/trap/<model>/<category>/
if [ "$TRAP_CATEGORY" = "none" ] || [ -z "$TRAP_CATEGORY" ]; then
    OUTPUT_GROUP="origin"
    TRAP_SUBDIR=""
else
    OUTPUT_GROUP="trap"
    TRAP_SUBDIR="${TRAP_CATEGORY}"
fi

if [ -n "$TRAP_SUBDIR" ]; then
    mkdir -p log/${OUTPUT_GROUP}/${MODEL}/${TRAP_SUBDIR} trajectory/${OUTPUT_GROUP}/${MODEL}/${TRAP_SUBDIR}
else
    mkdir -p log/${OUTPUT_GROUP}/${MODEL} trajectory/${OUTPUT_GROUP}/${MODEL}
fi

RESUME_LOG="$1"

if [ -n "$RESUME_LOG" ]; then
    echo "Resuming from: $RESUME_LOG"
    current_time=$(date +"%Y-%m-%d_%H-%M-%S")
    if [ -n "$TRAP_SUBDIR" ]; then
        LOG="log/${OUTPUT_GROUP}/${MODEL}/${TRAP_SUBDIR}/log_${MODEL}_${TRAP_CATEGORY}_${TRAP_TYPE}_resume_${current_time}.log"
    else
        LOG="log/${OUTPUT_GROUP}/${MODEL}/log_${MODEL}_${TRAP_CATEGORY}_${TRAP_TYPE}_resume_${current_time}.log"
    fi

    python scripts/trap/parallel/run_claude_trap_parallel.py \
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
      --trap_category=$TRAP_CATEGORY \
      --trap_type=$TRAP_TYPE \
      --trap_probability=$TRAP_PROBABILITY \
      --trap_seed=$TRAP_SEED \
      --trap_params="$TRAP_PARAMS" \
      --max_traps=$MAX_TRAPS \
      --resume_log="$RESUME_LOG" 2>&1 | tee "$LOG"
else
    current_time=$(date +"%Y-%m-%d_%H-%M-%S")
    if [ -n "$TRAP_SUBDIR" ]; then
        LOG="log/${OUTPUT_GROUP}/${MODEL}/${TRAP_SUBDIR}/log_${MODEL}_${TRAP_CATEGORY}_${TRAP_TYPE}_${current_time}.log"
        TRAJ_OUTPUT_PATH="trajectory/${OUTPUT_GROUP}/${MODEL}/${TRAP_SUBDIR}/traj_${MODEL}_${TRAP_CATEGORY}_${TRAP_TYPE}_${current_time}"
    else
        LOG="log/${OUTPUT_GROUP}/${MODEL}/log_${MODEL}_${TRAP_CATEGORY}_${TRAP_TYPE}_${current_time}.log"
        TRAJ_OUTPUT_PATH="trajectory/${OUTPUT_GROUP}/${MODEL}/traj_${MODEL}_${TRAP_CATEGORY}_${TRAP_TYPE}_${current_time}"
    fi

    python scripts/trap/parallel/run_claude_trap_parallel.py \
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
      --perform_emulator_setup=$PERFORM_EMULATOR_SETUP \
      --trap_category=$TRAP_CATEGORY \
      --trap_type=$TRAP_TYPE \
      --trap_probability=$TRAP_PROBABILITY \
      --trap_seed=$TRAP_SEED \
      --trap_params="$TRAP_PARAMS" \
      --max_traps=$MAX_TRAPS 2>&1 | tee "$LOG"
fi
