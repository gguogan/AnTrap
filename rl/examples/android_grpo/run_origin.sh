#!/bin/bash
# Launch GRPO training on standard (origin) AndroidWorld environment.
#
# Prerequisites:
#   1. Remote emulator server running (default port 29101)
#   2. SSH tunnel active (localhost:29101 -> remote:29101)
#   3. conda activate verl

set -x

ACTOR_MODEL_PATH="/path/to/hf/hub/models--ByteDance-Seed--UI-TARS-1.5-7B"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

export PYTHONUNBUFFERED=1

cd "$PROJECT_DIR"
python examples/android_grpo/main_grpo.py \
    --config-path="$SCRIPT_DIR/config" \
    --config-name='android_grpo_origin' \
    actor_rollout_ref.model.path=${ACTOR_MODEL_PATH} \
    "$@"
