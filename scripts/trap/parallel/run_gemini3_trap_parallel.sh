#!/bin/bash
# ============================================================================
# Gemini 3 Parallel Runner with Trap Injection
# ============================================================================
#
# API key + endpoint come from <repo>/.env (GEMINI_API_KEY, GEMINI_ENDPOINT).
# If you exported them in the shell those take precedence.
#
# Usage:
#   # Baseline (no trap, results -> log/origin/)
#   bash scripts/trap/parallel/run_gemini3_trap_parallel.sh
#
#   # Specific trap (results -> log/trap/)
#   TRAP_CATEGORY=a_layer TRAP_TYPE=grounding_error \
#     bash scripts/trap/parallel/run_gemini3_trap_parallel.sh
#
#   # Custom probability + extra params
#   TRAP_CATEGORY=s_layer TRAP_TYPE=visual_obscuration \
#     TRAP_PROBABILITY=0.5 TRAP_PARAMS='{"blur_radius": 20}' \
#     bash scripts/trap/parallel/run_gemini3_trap_parallel.sh
#
#   # Resume from previous log
#   TRAP_CATEGORY=a_layer TRAP_TYPE=grounding_error \
#     bash scripts/trap/parallel/run_gemini3_trap_parallel.sh log/trap/gemini-3-pro-preview/a_layer/log_xxx.log
#
# ----------------------------------------------------------------------------
# TRAP_CATEGORY & TRAP_TYPE — each run picks ONE category + ONE type.
# Values identical to the qwen3vl runner; see that script for the full table.
# ============================================================================

MODEL="${MODEL:-gemini-3-pro-preview}"
NUM_WORKERS="${NUM_WORKERS:-4}"
PERFORM_EMULATOR_SETUP="${PERFORM_EMULATOR_SETUP:-False}"

# Gemini 3 recommended defaults for agentic / screenshot use.
TEMPERATURE=1.0
THINKING_LEVEL=high
MEDIA_RESOLUTION=media_resolution_high
MAX_OUTPUT_TOKENS=4096

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

    python scripts/trap/parallel/run_gemini3_trap_parallel.py \
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

    python scripts/trap/parallel/run_gemini3_trap_parallel.py \
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
      --perform_emulator_setup=$PERFORM_EMULATOR_SETUP \
      --trap_category=$TRAP_CATEGORY \
      --trap_type=$TRAP_TYPE \
      --trap_probability=$TRAP_PROBABILITY \
      --trap_seed=$TRAP_SEED \
      --trap_params="$TRAP_PARAMS" \
      --max_traps=$MAX_TRAPS 2>&1 | tee "$LOG"
fi
