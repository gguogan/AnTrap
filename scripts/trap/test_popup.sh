#!/bin/bash
# ============================================================================
# Test TrapOverlay popup on a single emulator
# Usage: bash scripts/trap/test_popup.sh [emulator-port]
# Example: bash scripts/trap/test_popup.sh 5572
# ============================================================================

PORT="${1:-5572}"
EMU="emulator-${PORT}"
APK="trap_apk/app/build/outputs/apk/debug/app-debug.apk"
SCREENSHOT_DIR="scripts/trap/test_screenshots"
mkdir -p "$SCREENSHOT_DIR"

echo "=== Testing TrapOverlay on ${EMU} ==="

# Step 0: Check if APK is installed
echo "[1/7] Checking APK installation..."
INSTALLED=$(adb -s $EMU shell pm list packages 2>&1 | grep com.trap.overlay)
if [ -z "$INSTALLED" ]; then
    echo "  APK NOT installed. Installing..."
    if [ -f "$APK" ]; then
        adb -s $EMU install "$APK"
    else
        echo "  ERROR: APK file not found at $APK"
        echo "  Build it first: cd trap_apk && ./gradlew assembleDebug"
        exit 1
    fi
else
    echo "  APK installed: $INSTALLED"
fi

# Step 1: Grant overlay permission
echo "[2/7] Granting SYSTEM_ALERT_WINDOW permission..."
adb -s $EMU shell appops set com.trap.overlay SYSTEM_ALERT_WINDOW allow
echo "  Permission status:"
adb -s $EMU shell appops get com.trap.overlay SYSTEM_ALERT_WINDOW

# Step 2: Take a "before" screenshot
echo "[3/7] Taking BEFORE screenshot..."
adb -s $EMU shell screencap -p /sdcard/before_popup.png
adb -s $EMU pull /sdcard/before_popup.png "${SCREENSHOT_DIR}/before_popup_${PORT}.png" 2>&1
echo "  Saved to ${SCREENSHOT_DIR}/before_popup_${PORT}.png"

# Step 3: Start overlay app (register dynamic receiver)
echo "[4/7] Starting TrapOverlay app..."
adb -s $EMU shell am start -n com.trap.overlay/.MainActivity
sleep 1

# Step 4: Go back to previous screen
echo "[5/7] Going back..."
adb -s $EMU shell input keyevent KEYCODE_BACK
sleep 0.5

# Step 5: Send broadcast to show popup
echo "[6/7] Sending SHOW_POPUP broadcast..."
adb -s $EMU shell am broadcast \
    -n com.trap.overlay/.TrapBroadcastReceiver \
    -a com.trap.SHOW_POPUP \
    --es type "permission" \
    --es title "\"Camera Permission\"" \
    --es message "\"Allow this app to access your camera to take photos and scan QR codes?\"" \
    --es button1 "\"Allow\"" \
    --es button2 "\"Deny\""
sleep 1.5

# Step 6: Take an "after" screenshot
echo "[7/7] Taking AFTER screenshot..."
adb -s $EMU shell screencap -p /sdcard/after_popup.png
adb -s $EMU pull /sdcard/after_popup.png "${SCREENSHOT_DIR}/after_popup_${PORT}.png" 2>&1
echo "  Saved to ${SCREENSHOT_DIR}/after_popup_${PORT}.png"

# Check logcat for errors
echo ""
echo "=== TrapOverlay logcat (last 20 lines) ==="
adb -s $EMU shell logcat -d -s TrapOverlay | tail -20

echo ""
echo "=== Done ==="
echo "Compare screenshots:"
echo "  BEFORE: ${SCREENSHOT_DIR}/before_popup_${PORT}.png"
echo "  AFTER:  ${SCREENSHOT_DIR}/after_popup_${PORT}.png"
echo ""
echo "If AFTER has no popup, check:"
echo "  1. SYSTEM_ALERT_WINDOW permission (shown above)"
echo "  2. Logcat errors (shown above)"
echo ""

# Dismiss popup
echo "Dismissing popup..."
adb -s $EMU shell am broadcast \
    -n com.trap.overlay/.TrapBroadcastReceiver \
    -a com.trap.DISMISS_POPUP
