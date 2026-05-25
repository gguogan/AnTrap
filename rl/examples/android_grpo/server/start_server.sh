#!/bin/bash
# Start 8 Android emulators and launch the GRPO training server.
#
# Usage:
#   bash start_server.sh                  # default port 29101
#   PORT=9001 bash start_server.sh        # custom port

set -e

PORT="${PORT:-29101}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Step 1: Starting emulators ==="
# Reuse existing emulator setup script if available
if [ -f /app/setup_emulators.sh ]; then
    bash /app/setup_emulators.sh
elif [ -f "$SCRIPT_DIR/../../../../setup_emulators.sh" ]; then
    bash "$SCRIPT_DIR/../../../../setup_emulators.sh"
else
    echo "WARNING: setup_emulators.sh not found. Assuming emulators are already running."
fi

echo ""
echo "=== Step 2: Launching FastAPI server on port $PORT ==="
cd "$SCRIPT_DIR"
uvicorn android_grpo_server:app --host 0.0.0.0 --port "$PORT" --log-level info
