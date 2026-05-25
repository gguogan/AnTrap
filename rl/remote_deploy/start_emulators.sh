#!/bin/bash
# Start 8 Android emulators in parallel.
# Each emulator uses its own independent AVD copy.
# Run copy_emulators.sh first if you haven't already.

EMULATOR_CMD="${ANDROID_HOME:-/app/.android}/emulator/emulator"
ADB_CMD="${ANDROID_HOME:-/app/.android}/platform-tools/adb"
BASE_AVD="Pixel_6_API_33"

echo "Starting 8 emulators..."

for i in $(seq 0 7); do
    AVD="${BASE_AVD}_${i}"
    PORT=$((5554 + i * 2))
    GRPC=$((8554 + i * 2))

    echo "  Emu $i: AVD=$AVD, console=$PORT, grpc=$GRPC"
    $EMULATOR_CMD -avd "$AVD" \
        -no-window -no-audio -no-snapshot \
        -grpc "$GRPC" -port "$PORT" \
        -feature -MultiDisplay &
done

echo ""
echo "Waiting 90s for emulators to boot..."
sleep 90

# Configure emulators
for i in $(seq 0 7); do
    PORT=$((5554 + i * 2))
    echo "Configuring emulator-${PORT}..."
    $ADB_CMD -s "emulator-${PORT}" shell settings put system screen_off_timeout 2147483647 2>/dev/null
    $ADB_CMD -s "emulator-${PORT}" shell settings put global window_animation_scale 0.0 2>/dev/null
    $ADB_CMD -s "emulator-${PORT}" shell settings put global transition_animation_scale 0.0 2>/dev/null
    $ADB_CMD -s "emulator-${PORT}" shell settings put global animator_duration_scale 0.0 2>/dev/null
done

echo ""
echo "Verifying..."
$ADB_CMD devices
echo ""
echo "All 8 emulators should be listed above."
