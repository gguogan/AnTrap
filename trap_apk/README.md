# TrapOverlay APK

Android overlay app for External Interruption trap. Shows popups on top of all apps.

## Build

1. Open `trap_apk/` folder in Android Studio
2. Build > Build Bundle(s) / APK(s) > Build APK(s)
3. APK output: `app/build/outputs/apk/debug/app-debug.apk`

## Install & Setup (per emulator)

```bash
# Install APK
adb -s emulator-5554 install app/build/outputs/apk/debug/app-debug.apk

# Grant overlay permission (required!)
adb -s emulator-5554 shell appops set com.trap.overlay SYSTEM_ALERT_WINDOW allow
```

For all 8 emulators:
```bash
for port in 5554 5556 5558 5560 5562 5564 5566 5568; do
    adb -s emulator-$port install app-debug.apk
    adb -s emulator-$port shell appops set com.trap.overlay SYSTEM_ALERT_WINDOW allow
done
```

## Test

```bash
# Permission dialog
adb shell am broadcast -a com.trap.SHOW_POPUP \
    --es type "permission" \
    --es title "Camera Permission" \
    --es message "Allow this app to access your camera?" \
    --es button1 "Allow" --es button2 "Deny"

# Center dialog
adb shell am broadcast -a com.trap.SHOW_POPUP \
    --es type "center_dialog" \
    --es title "Update Available" \
    --es message "A new version is ready. Update now?"

# Top banner (swipe up to dismiss)
adb shell am broadcast -a com.trap.SHOW_POPUP \
    --es type "top_banner" \
    --es title "New Message" \
    --es message "You have 3 unread messages"

# Fullscreen ad (click X to close)
adb shell am broadcast -a com.trap.SHOW_POPUP \
    --es type "fullscreen_ad" \
    --es title "SPECIAL OFFER"

# Dismiss programmatically
adb shell am broadcast -a com.trap.DISMISS_POPUP
```

## Popup Types

| Type | Style | Dismiss |
|------|-------|---------|
| `permission` | System permission dialog | Allow/Deny buttons |
| `center_dialog` | Modal dialog in center | Close button |
| `top_banner` | Notification bar at top | Swipe up |
| `fullscreen_ad` | Full-screen overlay | X button (top-right) |
