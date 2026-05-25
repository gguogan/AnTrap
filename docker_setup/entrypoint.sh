#!/bin/bash

set -e  # Exit on first error

# Start Emulator
#============================================
echo "Starting Android emulator..."
./docker_setup/start_emu_headless.sh

# Ensure adb connection is ready
#============================================
echo "Verifying adb connection..."
adb root

# Wait for adb to fully stabilize
sleep 2

# Verify emulator is still responsive
if ! adb shell getprop sys.boot_completed | grep -q "1"; then
  echo "ERROR: Emulator failed to fully boot"
  exit 1
fi

echo "Android emulator is ready. Starting FastAPI server..."

# Start the FastAPI server
#============================================
python3 -m server.android_server
