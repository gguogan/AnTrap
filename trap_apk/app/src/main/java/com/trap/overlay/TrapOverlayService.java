package com.trap.overlay;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.graphics.Typeface;
import android.os.IBinder;
import android.util.Log;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.MotionEvent;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.ImageButton;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;

import java.io.File;

/**
 * Overlay service that displays trap popups on top of all apps.
 *
 * Supports 4 popup types:
 * - fullscreen_ad:  Full-screen image with X close button in top-right
 * - top_banner:     Top notification banner, dismiss by swiping up
 * - center_dialog:  Center dialog with title, message, close button
 * - permission:     Permission request dialog with Allow/Deny buttons
 */
public class TrapOverlayService extends Service {
    private static final String TAG = "TrapOverlay";
    private static final String CHANNEL_ID = "trap_overlay_channel";

    private WindowManager windowManager;
    private View overlayView;

    @Override
    public void onCreate() {
        super.onCreate();
        windowManager = (WindowManager) getSystemService(WINDOW_SERVICE);
        createNotificationChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent == null) return START_NOT_STICKY;

        String action = intent.getAction();
        if ("SHOW".equals(action)) {
            // Start as foreground service (required for Android 13)
            Notification notification = new Notification.Builder(this, CHANNEL_ID)
                    .setContentTitle("Trap Overlay Active")
                    .setSmallIcon(android.R.drawable.ic_dialog_alert)
                    .build();
            startForeground(1, notification);

            // Remove existing overlay if any
            removeOverlay();

            String type = intent.getStringExtra("type");
            String title = intent.getStringExtra("title");
            String message = intent.getStringExtra("message");
            String button1 = intent.getStringExtra("button1");
            String button2 = intent.getStringExtra("button2");
            String imagePath = intent.getStringExtra("image_path");

            switch (type) {
                case "fullscreen_ad":
                    showFullscreenAd(imagePath, title);
                    break;
                case "top_banner":
                    showTopBanner(title, message);
                    break;
                case "center_dialog":
                    showCenterDialog(title, message);
                    break;
                case "permission":
                    showPermissionDialog(title, message, button1, button2);
                    break;
                default:
                    Log.w(TAG, "Unknown popup type: " + type);
                    showCenterDialog(title, message);
                    break;
            }
        } else if ("DISMISS".equals(action)) {
            removeOverlay();
            stopForeground(true);
            stopSelf();
        }

        return START_NOT_STICKY;
    }

    // =========================================================================
    // Full-screen Ad: covers entire screen with image + X close button
    // =========================================================================
    private void showFullscreenAd(String imagePath, String fallbackText) {
        FrameLayout container = new FrameLayout(this);
        container.setBackgroundColor(Color.BLACK);

        // Ad image or colored placeholder
        if (imagePath != null && new File(imagePath).exists()) {
            ImageView imageView = new ImageView(this);
            Bitmap bitmap = BitmapFactory.decodeFile(imagePath);
            if (bitmap != null) {
                imageView.setImageBitmap(bitmap);
                imageView.setScaleType(ImageView.ScaleType.FIT_CENTER);
            }
            container.addView(imageView, new FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.MATCH_PARENT));
        } else {
            // Placeholder: colored background with "AD" text
            TextView adText = new TextView(this);
            adText.setText(fallbackText != null && !fallbackText.isEmpty()
                    ? fallbackText : "ADVERTISEMENT");
            adText.setTextColor(Color.WHITE);
            adText.setTextSize(TypedValue.COMPLEX_UNIT_SP, 28);
            adText.setGravity(Gravity.CENTER);
            adText.setBackgroundColor(Color.argb(200, 30, 30, 30));
            container.addView(adText, new FrameLayout.LayoutParams(
                    ViewGroup.LayoutParams.MATCH_PARENT,
                    ViewGroup.LayoutParams.MATCH_PARENT));
        }

        // X close button in top-right
        TextView closeBtn = new TextView(this);
        closeBtn.setText("✕");
        closeBtn.setTextColor(Color.WHITE);
        closeBtn.setTextSize(TypedValue.COMPLEX_UNIT_SP, 24);
        closeBtn.setBackgroundColor(Color.argb(150, 0, 0, 0));
        closeBtn.setPadding(dp(16), dp(8), dp(16), dp(8));
        closeBtn.setGravity(Gravity.CENTER);
        closeBtn.setOnClickListener(v -> dismiss());

        FrameLayout.LayoutParams closeLp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
        closeLp.gravity = Gravity.TOP | Gravity.END;
        closeLp.topMargin = dp(40);
        closeLp.rightMargin = dp(16);
        container.addView(closeBtn, closeLp);

        showOverlay(container, makeModalFullscreenParams());
    }

    // =========================================================================
    // Top Banner: notification-style bar at top, swipe up to dismiss
    // =========================================================================
    private void showTopBanner(String title, String message) {
        // Get screen height and set banner to 1/5 of screen
        android.util.DisplayMetrics metrics = new android.util.DisplayMetrics();
        windowManager.getDefaultDisplay().getMetrics(metrics);
        int bannerHeight = metrics.heightPixels / 6;

        LinearLayout banner = new LinearLayout(this);
        banner.setOrientation(LinearLayout.VERTICAL);
        banner.setBackgroundColor(Color.argb(240, 50, 50, 50));
        banner.setPadding(dp(20), dp(16), dp(20), dp(16));
        banner.setGravity(Gravity.CENTER_VERTICAL);

        // Title
        if (title != null && !title.isEmpty()) {
            TextView titleView = new TextView(this);
            titleView.setText(title);
            titleView.setTextColor(Color.WHITE);
            titleView.setTextSize(TypedValue.COMPLEX_UNIT_SP, 20);
            titleView.setTypeface(null, Typeface.BOLD);
            banner.addView(titleView);
        }

        // Message
        if (message != null && !message.isEmpty()) {
            TextView msgView = new TextView(this);
            msgView.setText(message);
            msgView.setTextColor(Color.argb(200, 255, 255, 255));
            msgView.setTextSize(TypedValue.COMPLEX_UNIT_SP, 16);
            msgView.setPadding(0, dp(8), 0, 0);
            banner.addView(msgView);
        }

        // Swipe up to dismiss
        banner.setOnTouchListener(new SwipeUpDismissListener());

        WindowManager.LayoutParams params = new WindowManager.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                bannerHeight,
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                        | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
                PixelFormat.TRANSLUCENT);
        params.gravity = Gravity.TOP;

        showOverlay(banner, params);
    }

    // =========================================================================
    // Center Dialog: modal dialog in center with close button
    // =========================================================================
    private void showCenterDialog(String title, String message) {
        LinearLayout dialog = new LinearLayout(this);
        dialog.setOrientation(LinearLayout.VERTICAL);
        dialog.setBackgroundColor(Color.WHITE);
        dialog.setPadding(dp(24), dp(20), dp(24), dp(16));
        dialog.setMinimumWidth(dp(300));

        // Title
        if (title != null && !title.isEmpty()) {
            TextView titleView = new TextView(this);
            titleView.setText(title);
            titleView.setTextColor(Color.BLACK);
            titleView.setTextSize(TypedValue.COMPLEX_UNIT_SP, 18);
            titleView.setTypeface(null, Typeface.BOLD);
            titleView.setPadding(0, 0, 0, dp(12));
            dialog.addView(titleView);
        }

        // Message
        if (message != null && !message.isEmpty()) {
            TextView msgView = new TextView(this);
            msgView.setText(message);
            msgView.setTextColor(Color.DKGRAY);
            msgView.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
            msgView.setPadding(0, 0, 0, dp(20));
            dialog.addView(msgView);
        }

        // Close button
        Button closeBtn = new Button(this);
        closeBtn.setText("Close");
        closeBtn.setOnClickListener(v -> dismiss());
        dialog.addView(closeBtn);

        // Dim background
        FrameLayout wrapper = createDimWrapper(dialog);
        showOverlay(wrapper, makeModalFullscreenParams());
    }

    // =========================================================================
    // Permission Dialog: system-style permission request with Allow/Deny
    // =========================================================================
    private void showPermissionDialog(String title, String message,
                                       String button1, String button2) {
        LinearLayout dialog = new LinearLayout(this);
        dialog.setOrientation(LinearLayout.VERTICAL);
        dialog.setBackgroundColor(Color.WHITE);
        dialog.setPadding(dp(24), dp(24), dp(24), dp(16));
        dialog.setMinimumWidth(dp(300));

        // Title
        if (title != null && !title.isEmpty()) {
            TextView titleView = new TextView(this);
            titleView.setText(title);
            titleView.setTextColor(Color.BLACK);
            titleView.setTextSize(TypedValue.COMPLEX_UNIT_SP, 18);
            titleView.setTypeface(null, Typeface.BOLD);
            titleView.setPadding(0, 0, 0, dp(12));
            dialog.addView(titleView);
        }

        // Message
        if (message != null && !message.isEmpty()) {
            TextView msgView = new TextView(this);
            msgView.setText(message);
            msgView.setTextColor(Color.DKGRAY);
            msgView.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
            msgView.setPadding(0, 0, 0, dp(24));
            dialog.addView(msgView);
        }

        // Buttons row
        LinearLayout btnRow = new LinearLayout(this);
        btnRow.setOrientation(LinearLayout.HORIZONTAL);
        btnRow.setGravity(Gravity.END);

        // Deny / button2
        Button denyBtn = new Button(this);
        denyBtn.setText(button2);
        denyBtn.setTextColor(Color.parseColor("#666666"));
        denyBtn.setBackgroundColor(Color.TRANSPARENT);
        denyBtn.setOnClickListener(v -> dismiss());

        // Allow / button1
        Button allowBtn = new Button(this);
        allowBtn.setText(button1);
        allowBtn.setTextColor(Color.parseColor("#1A73E8"));
        allowBtn.setBackgroundColor(Color.TRANSPARENT);
        allowBtn.setOnClickListener(v -> dismiss());

        btnRow.addView(denyBtn);
        btnRow.addView(allowBtn);
        dialog.addView(btnRow);

        // Dim background
        FrameLayout wrapper = createDimWrapper(dialog);
        showOverlay(wrapper, makeModalFullscreenParams());
    }

    // =========================================================================
    // Helper methods
    // =========================================================================
    private FrameLayout createDimWrapper(View content) {
        FrameLayout wrapper = new FrameLayout(this);
        wrapper.setBackgroundColor(Color.argb(120, 0, 0, 0));
        wrapper.setOnClickListener(v -> {
            // Click outside does NOT dismiss (agent must find the button)
        });

        FrameLayout.LayoutParams lp = new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.WRAP_CONTENT,
                ViewGroup.LayoutParams.WRAP_CONTENT);
        lp.gravity = Gravity.CENTER;
        wrapper.addView(content, lp);
        return wrapper;
    }

    private WindowManager.LayoutParams makeFullscreenParams() {
        WindowManager.LayoutParams params = new WindowManager.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT,
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                        | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
                PixelFormat.TRANSLUCENT);
        params.gravity = Gravity.CENTER;
        return params;
    }

    // Modal fullscreen params - captures touch events, blocks background
    private WindowManager.LayoutParams makeModalFullscreenParams() {
        WindowManager.LayoutParams params = new WindowManager.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT,
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
                PixelFormat.TRANSLUCENT);
        params.gravity = Gravity.CENTER;
        return params;
    }

    private void showOverlay(View view, WindowManager.LayoutParams params) {
        overlayView = view;
        try {
            windowManager.addView(overlayView, params);
            Log.d(TAG, "Overlay shown");
        } catch (Exception e) {
            Log.e(TAG, "Failed to show overlay: " + e.getMessage());
        }
    }

    private void removeOverlay() {
        if (overlayView != null) {
            try {
                windowManager.removeView(overlayView);
                Log.d(TAG, "Overlay removed");
            } catch (Exception e) {
                Log.w(TAG, "Failed to remove overlay: " + e.getMessage());
            }
            overlayView = null;
        }
    }

    private void dismiss() {
        removeOverlay();
        stopForeground(true);
        stopSelf();
    }

    private int dp(int value) {
        return (int) TypedValue.applyDimension(
                TypedValue.COMPLEX_UNIT_DIP, value,
                getResources().getDisplayMetrics());
    }

    private void createNotificationChannel() {
        NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID, "Trap Overlay",
                NotificationManager.IMPORTANCE_LOW);
        channel.setDescription("Foreground service for trap overlay");
        NotificationManager nm = getSystemService(NotificationManager.class);
        if (nm != null) nm.createNotificationChannel(channel);
    }

    // Swipe-up gesture listener for top banner
    private class SwipeUpDismissListener implements View.OnTouchListener {
        private float startY;
        private static final float SWIPE_THRESHOLD = 100;

        @Override
        public boolean onTouch(View v, MotionEvent event) {
            switch (event.getAction()) {
                case MotionEvent.ACTION_DOWN:
                    startY = event.getRawY();
                    return true;
                case MotionEvent.ACTION_UP:
                    float deltaY = event.getRawY() - startY;
                    if (deltaY < -SWIPE_THRESHOLD) {
                        // Swiped up
                        dismiss();
                    }
                    return true;
            }
            return false;
        }
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    @Override
    public void onDestroy() {
        removeOverlay();
        super.onDestroy();
    }
}
