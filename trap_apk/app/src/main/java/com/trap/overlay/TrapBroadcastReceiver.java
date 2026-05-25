package com.trap.overlay;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.util.Log;

/**
 * Receives ADB broadcast commands to show/dismiss trap popups.
 *
 * Usage:
 *   adb shell am broadcast -a com.trap.SHOW_POPUP \
 *     --es type "permission" \
 *     --es title "Camera Permission" \
 *     --es message "Allow this app to access your camera?" \
 *     --es button1 "Allow" \
 *     --es button2 "Deny"
 *
 *   adb shell am broadcast -a com.trap.SHOW_POPUP \
 *     --es type "fullscreen_ad" \
 *     --es image_path "/sdcard/Download/ad.png"
 *
 *   adb shell am broadcast -a com.trap.SHOW_POPUP \
 *     --es type "top_banner" \
 *     --es title "New message" \
 *     --es message "You have a new notification"
 *
 *   adb shell am broadcast -a com.trap.SHOW_POPUP \
 *     --es type "center_dialog" \
 *     --es title "Update Available" \
 *     --es message "A new version is available. Update now?"
 *
 *   adb shell am broadcast -a com.trap.DISMISS_POPUP
 */
public class TrapBroadcastReceiver extends BroadcastReceiver {
    private static final String TAG = "TrapOverlay";

    @Override
    public void onReceive(Context context, Intent intent) {
        String action = intent.getAction();
        Log.d(TAG, "Received broadcast: " + action);

        if ("com.trap.SHOW_POPUP".equals(action)) {
            String type = intent.getStringExtra("type");
            String title = intent.getStringExtra("title");
            String message = intent.getStringExtra("message");
            String button1 = intent.getStringExtra("button1");
            String button2 = intent.getStringExtra("button2");
            String imagePath = intent.getStringExtra("image_path");

            if (type == null) type = "center_dialog";
            if (title == null) title = "";
            if (message == null) message = "";
            if (button1 == null) button1 = "OK";
            if (button2 == null) button2 = "Cancel";

            Log.d(TAG, "Show popup: type=" + type + " title=" + title);

            Intent serviceIntent = new Intent(context, TrapOverlayService.class);
            serviceIntent.setAction("SHOW");
            serviceIntent.putExtra("type", type);
            serviceIntent.putExtra("title", title);
            serviceIntent.putExtra("message", message);
            serviceIntent.putExtra("button1", button1);
            serviceIntent.putExtra("button2", button2);
            serviceIntent.putExtra("image_path", imagePath);
            context.startForegroundService(serviceIntent);

        } else if ("com.trap.DISMISS_POPUP".equals(action)) {
            Intent serviceIntent = new Intent(context, TrapOverlayService.class);
            serviceIntent.setAction("DISMISS");
            context.startService(serviceIntent);
        }
    }
}
