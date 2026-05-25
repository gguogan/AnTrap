#!/bin/bash
# Start 8 Android emulators and launch the GRPO training server.
#
# Usage:
#   bash start_server.sh                  # default port 29101
#   PORT=9001 bash start_server.sh        # custom port

set -e

PORT="${PORT:-29101}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Step 1: Starting 8 emulators ==="
# Reuse existing emulator startup script if available
if [ -f /app/start_8_emulators.sh ]; then
    bash /app/start_8_emulators.sh
elif [ -f "$SCRIPT_DIR/../../../../androidworld_test/start_8_emulators.sh" ]; then
    bash "$SCRIPT_DIR/../../../../androidworld_test/start_8_emulators.sh"
else
    echo "WARNING: start_8_emulators.sh not found. Assuming emulators are already running."
fi

echo ""
echo "=== Step 2: Launching FastAPI server on port $PORT ==="
cd "$SCRIPT_DIR"
uvicorn android_grpo_server:app --host 0.0.0.0 --port "$PORT" --log-level info
