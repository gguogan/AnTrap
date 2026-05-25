#!/bin/bash
# setup_emulators.sh — duplicate the base AVD and launch N parallel emulators,
# then wait for boot, install trap.apk, and verify network reachability.
#
# Run inside the docker container after the image is built.
#
# Usage:
#   bash setup_emulators.sh                # default: full pipeline, N=10
#   N=8 bash setup_emulators.sh            # custom emulator count
#   bash setup_emulators.sh copy           # only duplicate AVDs
#   bash setup_emulators.sh launch         # only launch + post-boot config
#                                          # (assumes AVDs already copied)
#
# Default count is 10 (8 primary workers + 2 spares for failover).
# Each emulator i listens on console port 5554+2i and grpc port 8554+2i.

set -e

BASE_AVD="${BASE_AVD:-Pixel_6_API_33}"
N="${N:-10}"
AVD_DIR="${AVD_DIR:-$HOME/.android/avd}"
EMULATOR_DIR="${EMULATOR_DIR:-/app/.android/emulator}"
ADB="${ADB:-/app/.android/platform-tools/adb}"
TRAP_APK="${TRAP_APK:-/app/workspace/trap.apk}"

PHASE="${1:-all}"   # all | copy | launch

# ============================================================================
# Phase 1: duplicate the base AVD into N independent copies.
# ============================================================================
copy_avds() {
    echo "Creating $N AVD copies from $BASE_AVD in $AVD_DIR..."
    if [ ! -d "$AVD_DIR/${BASE_AVD}.avd" ]; then
        echo "Error: base AVD $BASE_AVD not found in $AVD_DIR" >&2
        exit 1
    fi

    for i in $(seq 0 $((N-1))); do
        local AVD_NAME="${BASE_AVD}_${i}"
        local AVD_PATH="${AVD_DIR}/${AVD_NAME}.avd"
        local INI_PATH="${AVD_DIR}/${AVD_NAME}.ini"

        if [ -d "$AVD_PATH" ]; then
            echo "  $AVD_NAME already exists, skipping"
            continue
        fi

        cp -r "$AVD_DIR/${BASE_AVD}.avd" "$AVD_PATH"
        # Drop qcow2 deltas and the multi-instance lock so each copy is fresh
        rm -f "$AVD_PATH"/*.qcow2 "$AVD_PATH/multiinstance.lock"
        cat > "$INI_PATH" <<EOF
avd.ini.encoding=UTF-8
path=$AVD_PATH
target=android-33
EOF
        echo "  Created $AVD_NAME"
    done

    echo
    echo "Available AVDs:"
    ls -d "$AVD_DIR"/${BASE_AVD}_*.avd 2>/dev/null | xargs -n1 basename
}

# ============================================================================
# Phase 2: launch the emulators, install trap.apk, verify network.
# ============================================================================
avd_for_port() { echo "${BASE_AVD}_$(( ($1 - 5554) / 2 ))"; }

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
    if [ -f "$TRAP_APK" ]; then
        $ADB -s emulator-${p} install -r -g "$TRAP_APK" >/dev/null
    fi
}

restart_with_wipe() {
    local p=$1 grpc=$(( $1 + 3000 )) avd
    avd=$(avd_for_port $p)
    local pid
    pid=$(ps -eo pid,cmd | grep -E "qemu-system.*-port ${p}\b" | grep -v grep | awk '{print $1}')
    [[ -n "$pid" ]] && kill -9 $pid
    sleep 3
    $EMULATOR_DIR/emulator -avd $avd -no-window -no-audio -no-snapshot -wipe-data \
        -grpc $grpc -port $p -feature -MultiDisplay >/tmp/emu_${p}.log 2>&1 &
    sleep 60
    wait_boot $p
    post_boot_setup $p
}

launch_emulators() {
    echo "Starting $N emulators..."
    local ports=()
    for i in $(seq 0 $((N-1))); do
        local port=$((5554 + 2*i))
        local grpc=$((8554 + 2*i))
        local avd="${BASE_AVD}_${i}"
        $EMULATOR_DIR/emulator -avd $avd -no-window -no-audio -no-snapshot \
            -grpc $grpc -port $port -feature -MultiDisplay &
        echo "  emulator-${port} (grpc $grpc, AVD $avd)"
        ports+=($port)
    done

    echo
    echo "Waiting 60s for emulators to boot..."
    sleep 60

    local failed=()
    for port in "${ports[@]}"; do
        echo "Configuring emulator-${port}..."
        wait_boot $port
        post_boot_setup $port

        # Pass 1: airplane-mode toggle if the host gateway is unreachable
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

        # Pass 2: wipe-data restart (up to 2 attempts)
        if [[ "$(ping_ok $port)" != "OK" ]]; then
            for wipe in 1 2; do
                echo "  emulator-${port}: still unreachable, wipe-data restart (${wipe}/2)..."
                restart_with_wipe $port
                [[ "$(ping_ok $port)" == "OK" ]] && break
            done
        fi

        if [[ "$(ping_ok $port)" == "OK" ]]; then
            echo "  emulator-${port}: network OK"
        else
            echo "  emulator-${port}: FAILED to recover"
            failed+=($port)
        fi
    done

    echo
    if [[ ${#failed[@]} -eq 0 ]]; then
        echo "All $N emulators ready (trap.apk installed, network verified)."
        return 0
    else
        echo "WARNING: ${#failed[@]} emulator(s) could not be rescued: ${failed[*]}"
        echo "Runners may still proceed using spare slots for failover."
        return 1
    fi
}

case "$PHASE" in
    copy)   copy_avds ;;
    launch) launch_emulators ;;
    all)    copy_avds; launch_emulators ;;
    *)      echo "Usage: $0 [copy|launch|all]" >&2; exit 1 ;;
esac
