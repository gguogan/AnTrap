#!/bin/bash
# Launch GRPO training on trap (disturbed) AndroidWorld environment.
#
# Pin one trap subcategory per run (paper protocol -- ten independent runs):
#   bash run_trap.sh env.trap.category=s_layer env.trap.trap_type=visual_obscuration
#   bash run_trap.sh env.trap.category=s_layer env.trap.trap_type=external_interruption
#   bash run_trap.sh env.trap.category=t_layer env.trap.trap_type=temporal_conflict
#   bash run_trap.sh env.trap.category=t_layer env.trap.trap_type=visual_hallucination
#   bash run_trap.sh env.trap.category=a_layer env.trap.trap_type=grounding_error
#   bash run_trap.sh env.trap.category=a_layer env.trap.trap_type=type_mismatch
#   bash run_trap.sh env.trap.category=a_layer env.trap.trap_type=intent_deviation
#   bash run_trap.sh env.trap.category=overall env.trap.trap_type=state_deadlock
#   bash run_trap.sh env.trap.category=overall env.trap.trap_type=context_disruption
#   bash run_trap.sh env.trap.category=overall env.trap.trap_type=loop
#
# Random sub-type within the YAML-configured category (smoke testing):
#   bash run_trap.sh

set -x

ACTOR_MODEL_PATH="/path/to/hf/hub/models--ByteDance-Seed--UI-TARS-1.5-7B"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

export PYTHONUNBUFFERED=1

cd "$PROJECT_DIR"
python examples/android_grpo/main_grpo.py \
    --config-path="$SCRIPT_DIR/config" \
    --config-name='android_grpo_trap' \
    actor_rollout_ref.model.path=${ACTOR_MODEL_PATH} \
    "$@"
