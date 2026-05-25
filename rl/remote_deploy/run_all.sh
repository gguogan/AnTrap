#!/bin/bash
# One-click: copy AVDs → start 8 emulators → launch FastAPI server.
# This is the main entrypoint inside the Docker container.

set -e

echo "========================================="
echo "  GRPO Emulator Server - Starting Up"
echo "========================================="

# Step 1: Copy AVDs (skip if already done)
echo ""
echo "[1/3] Preparing AVDs..."
bash copy_emulators.sh

# Step 2: Start emulators
echo ""
echo "[2/3] Starting 8 emulators..."
bash start_emulators.sh

# Step 3: Start FastAPI server
echo ""
echo "[3/3] Launching FastAPI server on port 29101..."
echo "  Test: curl http://localhost:29101/health"
echo ""
python android_grpo_server.py
