#!/bin/bash

# Launch 10 Android emulators in parallel
# Each emulator uses its own independent AVD copy
# Emulators 0-7 are primary workers; 8-9 are spares for failover

EMULATOR_DIR="/app/.android/emulator"
BASE_AVD="Pixel_6_API_33"

echo "Starting 10 emulators (8 primary + 2 spare)..."

# Emulator 0: console_port=5554, grpc_port=8554
AVD="${BASE_AVD}_0"
$EMULATOR_DIR/emulator -avd $AVD -no-window -no-audio -no-snapshot -grpc 8554 -port 5554 -feature -MultiDisplay &
echo "Started emulator 0 on console 5554, grpc 8554 (AVD: $AVD)"

# Emulator 1: console_port=5556, grpc_port=8556
AVD="${BASE_AVD}_1"
$EMULATOR_DIR/emulator -avd $AVD -no-window -no-audio -no-snapshot -grpc 8556 -port 5556 -feature -MultiDisplay &
echo "Started emulator 1 on console 5556, grpc 8556 (AVD: $AVD)"

# Emulator 2: console_port=5558, grpc_port=8558
AVD="${BASE_AVD}_2"
$EMULATOR_DIR/emulator -avd $AVD -no-window -no-audio -no-snapshot -grpc 8558 -port 5558 -feature -MultiDisplay &
echo "Started emulator 2 on console 5558, grpc 8558 (AVD: $AVD)"

# Emulator 3: console_port=5560, grpc_port=8560
AVD="${BASE_AVD}_3"
$EMULATOR_DIR/emulator -avd $AVD -no-window -no-audio -no-snapshot -grpc 8560 -port 5560 -feature -MultiDisplay &
echo "Started emulator 3 on console 5560, grpc 8560 (AVD: $AVD)"

# Emulator 4: console_port=5562, grpc_port=8562
AVD="${BASE_AVD}_4"
$EMULATOR_DIR/emulator -avd $AVD -no-window -no-audio -no-snapshot -grpc 8562 -port 5562 -feature -MultiDisplay &
echo "Started emulator 4 on console 5562, grpc 8562 (AVD: $AVD)"

# Emulator 5: console_port=5564, grpc_port=8564
AVD="${BASE_AVD}_5"
$EMULATOR_DIR/emulator -avd $AVD -no-window -no-audio -no-snapshot -grpc 8564 -port 5564 -feature -MultiDisplay &
echo "Started emulator 5 on console 5564, grpc 8564 (AVD: $AVD)"

# Emulator 6: console_port=5566, grpc_port=8566
AVD="${BASE_AVD}_6"
$EMULATOR_DIR/emulator -avd $AVD -no-window -no-audio -no-snapshot -grpc 8566 -port 5566 -feature -MultiDisplay &
echo "Started emulator 6 on console 5566, grpc 8566 (AVD: $AVD)"

# Emulator 7: console_port=5568, grpc_port=8568
AVD="${BASE_AVD}_7"
$EMULATOR_DIR/emulator -avd $AVD -no-window -no-audio -no-snapshot -grpc 8568 -port 5568 -feature -MultiDisplay &
echo "Started emulator 7 on console 5568, grpc 8568 (AVD: $AVD)"

# Emulator 8 (spare): console_port=5570, grpc_port=8570
AVD="${BASE_AVD}_8"
$EMULATOR_DIR/emulator -avd $AVD -no-window -no-audio -no-snapshot -grpc 8570 -port 5570 -feature -MultiDisplay &
echo "Started emulator 8 (spare) on console 5570, grpc 8570 (AVD: $AVD)"

# Emulator 9 (spare): console_port=5572, grpc_port=8572
AVD="${BASE_AVD}_9"
$EMULATOR_DIR/emulator -avd $AVD -no-window -no-audio -no-snapshot -grpc 8572 -port 5572 -feature -MultiDisplay &
echo "Started emulator 9 (spare) on console 5572, grpc 8572 (AVD: $AVD)"

echo ""
echo "All 10 emulators started!"
echo "Waiting 60 seconds for emulators to boot..."
sleep 60

# Manually apply settings that the emulator failed to set via adb -e
ADB="/app/.android/platform-tools/adb"
TRAP_APK="/app/workspace/trap.apk"
PORTS="5554 5556 5558 5560 5562 5564 5566 5568 5570 5572"

# port -> AVD index (5554+2*i)
avd_for_port() {
    local p=$1
    echo "${BASE_AVD}_$(( (p - 5554) / 2 ))"
}

wait_boot() {
    local p=$1
    $ADB -s emulator-${p} wait-for-device
    until [[ "$($ADB -s emulator-${p} shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" == "1" ]]; do
        sleep 2
    done
}

ping_ok() {
    local p=$1
    $ADB -s emulator-${p} shell 'ping -c1 -W2 10.0.2.2 >/dev/null 2>&1 && echo OK' 2>/dev/null | tr -d '\r'
}

post_boot_setup() {
    local p=$1
    $ADB -s emulator-${p} shell settings put system screen_off_timeout 2147483647 2>/dev/null
    $ADB -s emulator-${p} install -r -g "$TRAP_APK" >/dev/null
}

restart_with_wipe() {
    local p=$1 grpc=$(( p + 3000 )) avd=$(avd_for_port $p)
    local pid
    pid=$(ps -eo pid,cmd | grep -E "qemu-system.*-port ${p}\b" | grep -v grep | awk '{print $1}')
    if [[ -n "$pid" ]]; then kill -9 $pid; fi
    sleep 3
    $EMULATOR_DIR/emulator -avd $avd -no-window -no-audio -no-snapshot -wipe-data \
        -grpc $grpc -port $p -feature -MultiDisplay >/tmp/emu_${p}.log 2>&1 &
    sleep 60
    wait_boot $p
    post_boot_setup $p
}

declare -a FINAL_FAIL=()

for port in $PORTS; do
    echo "Waiting for emulator-${port} to fully boot..."
    wait_boot $port
    echo "Configuring + installing trap.apk on emulator-${port}..."
    post_boot_setup $port

    # Pass 1: airplane-mode toggle if ping fails
    if [[ "$(ping_ok $port)" != "OK" ]]; then
        echo "  emulator-${port}: 10.0.2.2 unreachable, airplane-mode toggle..."
        for try in 1 2; do
            $ADB -s emulator-${port} shell 'cmd connectivity airplane-mode enable' >/dev/null 2>&1
            sleep 3
            $ADB -s emulator-${port} shell 'cmd connectivity airplane-mode disable' >/dev/null 2>&1
            sleep 5
            $ADB -s emulator-${port} shell 'svc wifi enable' >/dev/null 2>&1
            sleep 3
            [[ "$(ping_ok $port)" == "OK" ]] && break
        done
    fi

    # Pass 2: -wipe-data restart if still broken (up to 2 attempts)
    if [[ "$(ping_ok $port)" != "OK" ]]; then
        for wipe in 1 2; do
            echo "  emulator-${port}: still unreachable, wipe-data restart (attempt ${wipe}/2)..."
            restart_with_wipe $port
            [[ "$(ping_ok $port)" == "OK" ]] && break
        done
    fi

    if [[ "$(ping_ok $port)" == "OK" ]]; then
        echo "  emulator-${port}: network OK"
    else
        echo "  emulator-${port}: FAILED to recover"
        FINAL_FAIL+=($port)
    fi
done

echo
if [[ ${#FINAL_FAIL[@]} -eq 0 ]]; then
    echo "All 10 emulators ready (trap.apk installed, network verified)."
    exit 0
else
    echo "WARNING: ${#FINAL_FAIL[@]} emulator(s) could not be rescued: ${FINAL_FAIL[*]}"
    echo "Runner may still proceed using spare pool (5570/5572) for failover."
    exit 1
fi