package com.trap.overlay;

import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.widget.TextView;
import android.widget.Toast;

/**
 * Simple activity for manually granting overlay permission.
 * In practice, permission is granted via:
 *   adb shell appops set com.trap.overlay SYSTEM_ALERT_WINDOW allow
 */
public class MainActivity extends Activity {

    private BroadcastReceiver trapReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            String action = intent.getAction();
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
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Register receiver dynamically
        IntentFilter filter = new IntentFilter();
        filter.addAction("com.trap.SHOW_POPUP");
        filter.addAction("com.trap.DISMISS_POPUP");
        registerReceiver(trapReceiver, filter, Context.RECEIVER_EXPORTED);

        TextView tv = new TextView(this);
        tv.setPadding(48, 100, 48, 48);
        tv.setTextSize(16);

        if (Settings.canDrawOverlays(this)) {
            tv.setText("TrapOverlay: Overlay permission GRANTED.\n\n"
                    + "The app is ready. Popups can be triggered via:\n\n"
                    + "adb shell am broadcast -a com.trap.SHOW_POPUP "
                    + "--es type \"permission\" "
                    + "--es title \"Test\" "
                    + "--es message \"Test message\"");
        } else {
            tv.setText("TrapOverlay: Overlay permission NOT granted.\n\n"
                    + "Grant via ADB:\n"
                    + "  adb shell appops set com.trap.overlay SYSTEM_ALERT_WINDOW allow\n\n"
                    + "Or tap below to open settings.");

            tv.setOnClickListener(v -> {
                Intent intent = new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                        Uri.parse("package:" + getPackageName()));
                startActivityForResult(intent, 100);
            });
        }

        setContentView(tv);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == 100) {
            if (Settings.canDrawOverlays(this)) {
                Toast.makeText(this, "Overlay permission granted!", Toast.LENGTH_SHORT).show();
            }
            recreate();
        }
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        unregisterReceiver(trapReceiver);
    }
}
