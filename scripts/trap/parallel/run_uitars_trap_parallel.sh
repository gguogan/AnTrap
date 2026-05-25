#!/bin/bash
# ============================================================================
# UI-TARS Parallel Runner with Trap Injection
# ============================================================================
#
# Usage:
#   # Baseline (no trap, results -> log/origin/)
#   bash scripts/trap/parallel/run_uitars_trap_parallel.sh
#
#   # Run with a specific trap (results -> log/trap/)
#   TRAP_CATEGORY=a_layer TRAP_TYPE=grounding_error \
#     bash scripts/trap/parallel/run_uitars_trap_parallel.sh
#
#   # Custom probability and extra params
#   TRAP_CATEGORY=s_layer TRAP_TYPE=visual_obscuration \
#     TRAP_PROBABILITY=0.5 TRAP_PARAMS='{"blur_radius": 20}' \
#     bash scripts/trap/parallel/run_uitars_trap_parallel.sh
#
#   # Resume from previous log
#   TRAP_CATEGORY=a_layer TRAP_TYPE=grounding_error \
#     bash scripts/trap/parallel/run_uitars_trap_parallel.sh log/trap/UI-TARS-1.5-7B/log_xxx.log
#
# ----------------------------------------------------------------------------
# TRAP_CATEGORY & TRAP_TYPE -- each run picks ONE category + ONE type:
#
#   TRAP_CATEGORY     TRAP_TYPE               Description
#   none              none                    Baseline, no disturbance
#   s_layer           visual_obscuration      Blur/patch over UI elements
#                     external_interruption   Popup via APK
#                     random                  Randomly pick from above
#   t_layer           temporal_conflict       Replace screenshot with stale one
#                     visual_hallucination   Modify text labels in screenshot
#                     random                  Randomly pick from above
#   a_layer           grounding_error         Random offset on click coordinates
#                     type_mismatch     Remap action types
#                     random                  Randomly pick from above
#   overall           state_deadlock          Block action execution for N steps
#                     context_disruption      Inject HOME/APP_SWITCH before step
#                     loop                    Inject BACK every N steps
#                     random                  Randomly pick from above
#
# TRAP_PROBABILITY  -- per-step trigger probability (0.0-1.0, default 0.3)
# TRAP_SEED         -- RNG seed (default 42)
# MAX_TRAPS         -- max traps per episode (0=unlimited, min 1 guaranteed)
# TRAP_PARAMS       -- JSON string for extra config overrides
# ============================================================================

MODEL="${MODEL:-UI-TARS-1.5-7B}"

API_KEY="EMPTY"
BASE_URL="${BASE_URL:-http://localhost:9001/v1}"
NUM_WORKERS=8
PERFORM_EMULATOR_SETUP="${PERFORM_EMULATOR_SETUP:-False}"

# Trap configuration
TRAP_CATEGORY="${TRAP_CATEGORY:-none}"
TRAP_TYPE="${TRAP_TYPE:-none}"
TRAP_PROBABILITY="${TRAP_PROBABILITY:-0.3}"
TRAP_SEED="${TRAP_SEED:-42}"
MAX_TRAPS="${MAX_TRAPS:-0}"
TRAP_PARAMS="${TRAP_PARAMS:-{}}"

# Determine output directory
if [ "$TRAP_CATEGORY" = "none" ] || [ -z "$TRAP_CATEGORY" ]; then
    OUTPUT_GROUP="origin"
    TRAP_SUBDIR=""
else
    OUTPUT_GROUP="trap"
    TRAP_SUBDIR="${TRAP_CATEGORY}"
fi

# Create directories with TRAP_CATEGORY subdirectory for trap runs
if [ -n "$TRAP_SUBDIR" ]; then
    mkdir -p log/${OUTPUT_GROUP}/${MODEL}/${TRAP_SUBDIR} trajectory/${OUTPUT_GROUP}/${MODEL}/${TRAP_SUBDIR}
else
    mkdir -p log/${OUTPUT_GROUP}/${MODEL} trajectory/${OUTPUT_GROUP}/${MODEL}
fi

# Resume mode
RESUME_LOG="$1"

if [ -n "$RESUME_LOG" ]; then
    echo "Resuming from: $RESUME_LOG"
    current_time=$(date +"%Y-%m-%d_%H-%M-%S")
    if [ -n "$TRAP_SUBDIR" ]; then
        LOG="log/${OUTPUT_GROUP}/${MODEL}/${TRAP_SUBDIR}/log_${MODEL}_${TRAP_CATEGORY}_${TRAP_TYPE}_resume_${current_time}.log"
    else
        LOG="log/${OUTPUT_GROUP}/${MODEL}/log_${MODEL}_${TRAP_CATEGORY}_${TRAP_TYPE}_resume_${current_time}.log"
    fi

    python scripts/trap/parallel/run_uitars_trap_parallel.py \
      --suite_family=android_world \
      --model=$MODEL \
      --api_key=$API_KEY \
      --base_url=$BASE_URL \
      --num_workers=$NUM_WORKERS \
      --task_random_seed=30 \
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

    python scripts/trap/parallel/run_uitars_trap_parallel.py \
      --suite_family=android_world \
      --model=$MODEL \
      --api_key=$API_KEY \
      --base_url=$BASE_URL \
      --traj_output_path=$TRAJ_OUTPUT_PATH \
      --num_workers=$NUM_WORKERS \
      --task_random_seed=30 \
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
