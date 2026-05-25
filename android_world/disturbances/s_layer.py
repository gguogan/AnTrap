"""S-Layer (Observation Perturbation) traps.

- Visual Obscuration: blur or patch over UI elements in screenshot
- External Interruption: trigger popup overlay via TrapOverlay APK
"""

from __future__ import annotations

import os
import random
import time

import numpy as np
from PIL import Image, ImageFilter

from android_world.disturbances.trap_config import TrapConfig


# Device-side directory where the fullscreen-ad image pool lives. Populated
# by _ensure_ad_pool_on_device() on the first external_interruption trigger
# per env, then referenced via image_path in the broadcast extras.
_AD_POOL_DEVICE_DIR = '/sdcard/trap_ad_pool'

# Track which env instances we have already pushed the pool to, so subsequent
# triggers in the same worker don't re-push 2 MB per episode.
_ad_pool_pushed: set[int] = set()


def _host_ad_pool_dir() -> str:
    """Absolute host path of `<repo_root>/screenshot_photo/_ad_pool/`."""
    here = os.path.dirname(os.path.abspath(__file__))
    # disturbances/ -> android_world/ -> repo root
    return os.path.abspath(os.path.join(here, '..', '..', 'screenshot_photo', '_ad_pool'))


def _host_ad_files() -> list[str]:
    """List of fullscreen_ad_*.{jpg,jpeg,png} basenames sorted lexicographically."""
    host = _host_ad_pool_dir()
    if not os.path.isdir(host):
        return []
    return sorted(
        f for f in os.listdir(host)
        if f.startswith('fullscreen_ad_')
        and f.lower().endswith(('.jpg', '.jpeg', '.png'))
    )


def _device_ad_paths() -> list[str]:
    """Device-side paths matching the host pool."""
    return [f'{_AD_POOL_DEVICE_DIR}/{f}' for f in _host_ad_files()]


def _ensure_ad_pool_on_device(env) -> None:
    """Mirror the host fullscreen-ad pool onto /sdcard/trap_ad_pool/.

    No-op on subsequent calls within the same env. Safe to call when the host
    pool is empty (APK will then fall back to its text placeholder)."""
    if env is None or id(env) in _ad_pool_pushed:
        return
    files = _host_ad_files()
    if not files:
        _ad_pool_pushed.add(id(env))
        return
    try:
        from android_world.env import adb_utils
        adb_utils.issue_generic_request(
            ['shell', 'mkdir', '-p', _AD_POOL_DEVICE_DIR], env.controller,
        )
        host = _host_ad_pool_dir()
        for f in files:
            adb_utils.issue_generic_request(
                ['push', os.path.join(host, f), f'{_AD_POOL_DEVICE_DIR}/{f}'],
                env.controller,
            )
    except Exception as e:
        print(f'[TRAP] _ensure_ad_pool_on_device failed: {e}')
    _ad_pool_pushed.add(id(env))


# =========================================================================
# Popup content templates (used when vLLM is not available)
# =========================================================================
_POPUP_TEMPLATES = {
    'permission': [
        # Location permission
        {'title': 'Location Access', 'message': 'This app wants to access your device location to provide location-based services and recommendations.', 'button1': 'Allow', 'button2': "Don't allow"},
        {'title': 'Location Permission', 'message': 'This app needs your location to show nearby places, get directions, and provide local weather updates.', 'button1': 'Allow while using app', 'button2': 'Deny'},
        {'title': 'Background Location', 'message': 'This app wants to access your location even when you are not using it for better tracking and notifications.', 'button1': 'Allow all the time', 'button2': 'Deny'},
        # Camera permission
        {'title': 'Camera Permission', 'message': 'This app needs access to your camera to take photos, record videos, and scan documents or QR codes.', 'button1': 'Allow', 'button2': "Don't allow"},
        {'title': 'Camera Access', 'message': 'Allow this app to use your camera? This is needed for taking photos and video calls with your contacts.', 'button1': 'Allow', 'button2': 'Deny'},
        # Microphone permission
        {'title': 'Microphone Access', 'message': 'This app needs access to your microphone for voice recording, voice messages, and audio calls.', 'button1': 'Allow', 'button2': "Don't allow"},
        {'title': 'Voice Recording', 'message': 'To record voice notes and make voice calls, this app needs permission to use your microphone.', 'button1': 'Allow', 'button2': 'Deny'},
        # Storage permission
        {'title': 'Storage Permission', 'message': 'This app needs access to your photos, media, and files to save downloads and attach files to messages.', 'button1': 'Allow', 'button2': 'Deny'},
        {'title': 'Media Access', 'message': 'Allow access to photos and videos? This lets you add attachments and save content to your device.', 'button1': 'Allow', 'button2': "Don't allow"},
        {'title': 'File Access', 'message': 'This app wants to read and write to your device storage to manage documents and downloaded files.', 'button1': 'Allow', 'button2': 'Deny'},
        # Contacts permission
        {'title': 'Contacts Access', 'message': 'This app wants to access your contacts to help you find friends and share content with people you know.', 'button1': 'Allow', 'button2': "Don't allow"},
        {'title': 'Contact Permission', 'message': 'Allow access to your contacts? This helps you connect with friends and send invitations easily.', 'button1': 'Allow', 'button2': 'Deny'},
        # Notification permission
        {'title': 'Notification Permission', 'message': 'This app would like to send you notifications about messages, updates, and important alerts.', 'button1': 'Allow', 'button2': "Don't allow"},
        {'title': 'Push Notifications', 'message': 'Enable notifications to stay updated with new messages, friend requests, and app updates?', 'button1': 'Enable', 'button2': 'Not now'},
        # Phone/SMS permission
        {'title': 'Phone Permission', 'message': 'This app needs to make and manage phone calls for verification and calling features.', 'button1': 'Allow', 'button2': 'Deny'},
        {'title': 'SMS Permission', 'message': 'Allow this app to send and receive SMS messages for verification codes and notifications?', 'button1': 'Allow', 'button2': "Don't allow"},
        # Calendar permission
        {'title': 'Calendar Access', 'message': 'This app wants to access your calendar to add events and reminders for your scheduled activities.', 'button1': 'Allow', 'button2': 'Deny'},
        # Bluetooth permission
        {'title': 'Bluetooth Permission', 'message': 'This app needs Bluetooth access to find and connect to nearby devices like headphones and speakers.', 'button1': 'Allow', 'button2': "Don't allow"},
        # Nearby devices
        {'title': 'Nearby Devices', 'message': 'Allow this app to scan for and connect to nearby devices? This is needed for sharing and streaming.', 'button1': 'Allow', 'button2': 'Deny'},
        # Other
        {'title': 'Background Data', 'message': 'This app wants to use mobile data in the background to sync content and send notifications.', 'button1': 'Allow', 'button2': 'Deny'},
        {'title': 'Display Over Apps', 'message': 'Allow this app to draw over other apps? This is needed for floating widgets and overlay features.', 'button1': 'Allow', 'button2': "Don't allow"},
    ],
    'center_dialog': [
        # Updates
        {'title': 'Update Available', 'message': 'A new version (v2.3.1) is now available. Update now to get the latest features and bug fixes for a better experience.'},
        {'title': 'App Update', 'message': 'Version 3.0 has been released! This update includes new features, improved performance, and important security patches.'},
        {'title': 'Security Update', 'message': 'A critical security update is available. We strongly recommend updating now to protect your data and privacy.'},
        # Rating / feedback
        {'title': 'Rate This App', 'message': 'Are you enjoying this app? Your feedback helps us improve. Please take a moment to rate us on the Play Store.'},
        {'title': 'Feedback Request', 'message': 'We value your opinion! How has your experience been? Help us make this app better by sharing your feedback.'},
        {'title': 'Love the App?', 'message': 'Great to hear you are enjoying it! Would you mind rating us 5 stars? It only takes a few seconds.'},
        # Sign-in / account
        {'title': 'Sign In Required', 'message': 'You need to sign in to access this feature. Please log in with your account to continue.'},
        {'title': 'Session Expired', 'message': 'Your session has expired for security reasons. Please log in again to continue using the app.'},
        {'title': 'Account Verification', 'message': 'Please verify your email address to secure your account and unlock all features of the application.'},
        {'title': 'Password Changed', 'message': 'Your password was changed 2 hours ago from a Windows device. Was this you? If not, secure your account now.'},
        # Storage / disk space
        {'title': 'Storage Almost Full', 'message': 'Your device is running low on storage space. Delete some files or apps to continue using this feature.'},
        {'title': 'Low Disk Space', 'message': 'Only 500MB of storage remaining. Your device may slow down. Consider clearing cache or deleting unused files.'},
        # Network / connection
        {'title': 'Network Error', 'message': 'Unable to connect to the server. Please check your internet connection and try again in a moment.'},
        {'title': 'Connection Lost', 'message': 'You appear to be offline. Some features may not be available. Check your WiFi or mobile data connection.'},
        {'title': 'Server Unavailable', 'message': 'Our servers are temporarily down for maintenance. We apologize for the inconvenience. Please try again later.'},
        # Sync / backup
        {'title': 'Sync Required', 'message': 'Your data needs to be synced with the cloud. This will only take a few seconds and will backup your progress.'},
        {'title': 'Backup Available', 'message': 'A backup from March 28 at 3:45 PM is available. Would you like to restore your data from this backup?'},
        # Privacy / terms
        {'title': 'Privacy Policy Update', 'message': 'We have updated our Privacy Policy with new data handling practices. Please review and accept to continue.'},
        {'title': 'Terms of Service', 'message': 'By continuing to use this app, you agree to our updated Terms of Service and Privacy Policy. Read more details.'},
        # Payment / subscription
        {'title': 'Subscription Renewal', 'message': 'Your premium subscription will renew tomorrow at $9.99/month. Manage your subscription in Settings.'},
        {'title': 'Payment Required', 'message': 'Your payment method has expired. Please update your payment information to continue enjoying premium features.'},
        {'title': 'Free Trial Ending', 'message': 'Your 7-day free trial ends in 2 days. Upgrade to Premium now to keep all features and avoid interruptions.'},
        # Confirmation / warning
        {'title': 'Unsaved Changes', 'message': 'You have unsaved changes that will be lost if you leave. Are you sure you want to discard them?'},
        {'title': 'Delete Confirmation', 'message': 'Are you sure you want to delete this item? This action cannot be undone and all data will be permanently removed.'},
        {'title': 'Log Out', 'message': 'Are you sure you want to log out? You will need to enter your credentials again to access your account.'},
        # Permissions / settings
        {'title': 'Enable Location', 'message': 'Location services are currently disabled. Enable them in Settings to get personalized recommendations near you.'},
        {'title': 'Enable Notifications', 'message': 'Notifications are disabled. Enable them in Settings to receive important updates and never miss a message.'},
        {'title': 'Battery Saver Mode', 'message': 'Battery Saver is currently enabled. Some features may be limited or unavailable until you charge your device.'},
        {'title': 'Low Battery', 'message': 'Your battery is below 15%. Consider connecting to a charger soon to avoid losing your current progress.'},
        # Social / share
        {'title': 'Share with Friends', 'message': 'Love this app? Share it with your friends and you will both get 1 month of Premium for free!'},
        {'title': 'Invite Friends', 'message': 'Invite 3 friends to join and unlock exclusive features! They will also receive a special welcome bonus.'},
        # Errors / issues
        {'title': 'Something Went Wrong', 'message': 'An unexpected error occurred while processing your request. Please try again or contact support if the problem persists.'},
        {'title': 'Feature Unavailable', 'message': 'This feature is not yet available in your region. We are working hard to bring it to you soon.'},
    ],
    'top_banner': [
        # Messages / communication
        {'title': 'New Message', 'message': 'You have 3 new messages waiting for you. Tap to view your conversation with Alex and others.'},
        {'title': 'Missed Call', 'message': 'You missed a video call from Mom 5 minutes ago. Tap to call back or send a message.'},
        {'title': 'New Email', 'message': '2 new emails received. Important: Your order has been shipped and will arrive tomorrow.'},
        {'title': 'Voice Message', 'message': 'New voice message from Alex (0:42). Tap to listen now or save for later.'},
        # Calendar / reminders
        {'title': 'Reminder', 'message': 'Team meeting starts in 15 minutes. Meeting room: Conference A. Agenda attached.'},
        {'title': 'Calendar Event', 'message': 'Doctor appointment scheduled for tomorrow at 10:00 AM at City Medical Center.'},
        {'title': 'Task Due', 'message': 'Your project report is due today at 5:00 PM. 3 tasks remaining to complete.'},
        {'title': 'Birthday Reminder', 'message': "It's Sarah's birthday today! Send her a message to wish her a great day."},
        # Downloads / updates
        {'title': 'Download Complete', 'message': 'Your file "Q2_Report.pdf" (2.4MB) has been downloaded successfully. Tap to open.'},
        {'title': 'App Updated', 'message': 'This app has been updated to version 3.2.1. Enjoy new features and improved performance!'},
        {'title': 'Download Started', 'message': 'Downloading update (45% complete). Estimated time remaining: 2 minutes.'},
        # System status
        {'title': 'System Update', 'message': 'Android 14 security patch (March 2026) is ready to install. Restart your device to complete.'},
        {'title': 'Device Restart', 'message': 'Your device will restart tonight at 3:00 AM to install important system updates.'},
        {'title': 'Storage Warning', 'message': 'Storage is almost full. Only 200MB remaining. Delete unused apps to free up space.'},
        {'title': 'Battery Low', 'message': 'Battery at 10%. Connect charger soon to avoid losing your current work.'},
        # Weather / travel
        {'title': 'Weather Alert', 'message': 'Heavy rain expected in your area this afternoon. Bring an umbrella if going out.'},
        {'title': 'Traffic Update', 'message': 'Heavy traffic detected on your usual route. Consider taking an alternate route to save 15 minutes.'},
        {'title': 'Flight Status', 'message': 'Your flight AA123 to New York is delayed by 45 minutes. New departure time: 3:45 PM.'},
        # Promotions / offers
        {'title': 'Limited Offer', 'message': 'Flash sale! 50% off Premium subscription ends in 2 hours. Upgrade now and save!'},
        {'title': 'Reward Ready', 'message': 'You earned 150 points this week! Redeem them for exclusive rewards in the Rewards Store.'},
        {'title': 'New Feature', 'message': 'Dark Mode is now available! Enable it in Settings to reduce eye strain and save battery.'},
        # Social / activity
        {'title': 'New Follower', 'message': 'John Doe started following you. You now have 1,234 followers on your profile.'},
        {'title': 'Post Liked', 'message': 'Your photo received 25 likes in the last hour. Tap to see all the reactions.'},
        {'title': 'Friend Request', 'message': 'You have 2 new friend requests from Emma and Michael. Tap to view and respond.'},
        # Health / fitness
        {'title': 'Step Goal', 'message': 'Great job! You reached 80% of your daily step goal. Only 2,000 steps left to complete.'},
        {'title': 'Workout Reminder', 'message': 'Time for your scheduled 30-minute workout session. Stay consistent and reach your fitness goals!'},
        {'title': 'Hydration Reminder', 'message': "It's been 2 hours since your last glass of water. Stay hydrated for better focus and energy."},
        # Finance / payments
        {'title': 'Payment Received', 'message': 'You received $25.00 from Mike via QuickPay. Your balance is now $156.50.'},
        {'title': 'Bill Reminder', 'message': 'Your electricity bill of $85.00 is due in 3 days. Set up auto-pay to never miss a payment.'},
        {'title': 'Transaction Alert', 'message': 'A transaction of $49.99 was made at Amazon. Was this you? If not, report immediately.'},
        # Security / verification
        {'title': 'Security Alert', 'message': 'New login detected from a Windows device in New York at 2:30 PM. Was this you?'},
        {'title': 'Verification Code', 'message': 'Your verification code is 847291. Valid for 5 minutes. Do not share this code with anyone.'},
        {'title': 'Password Changed', 'message': 'Your password was changed successfully. If this was not you, reset your password immediately.'},
    ],
    'fullscreen_ad': [
        {'title': 'LIMITED TIME OFFER - 50% OFF PREMIUM TODAY ONLY!'},
        {'title': 'FREE 7-DAY TRIAL - Experience Premium Features Now!'},
        {'title': 'DOWNLOAD NOW - Join 10 Million Happy Users!'},
        {'title': 'EXCLUSIVE DEAL - Get 3 Months Free with Annual Plan!'},
        {'title': 'SAVE $50 - Upgrade to Premium Before This Deal Ends!'},
        {'title': 'NEW ARRIVAL - Discover Our Latest Collection Today!'},
        {'title': 'MEMBERS ONLY - Unlock Early Access to New Features!'},
        {'title': 'HOLIDAY SALE - Up to 70% Off Everything This Weekend!'},
    ],
}

# Popup types supported by the APK
POPUP_TYPES = ('permission', 'center_dialog', 'top_banner', 'fullscreen_ad')


def apply_external_interruption(env, config: TrapConfig, rng: random.Random,
                                 vllm_wrapper=None, current_app: str = ''):
    """Trigger a popup overlay via the TrapOverlay APK.

    Args:
        env: AsyncAndroidEnv with .controller attribute.
        config: TrapConfig.
        rng: Random instance.
        vllm_wrapper: Optional GUIOwlWrapper for LLM-generated content.
        current_app: Current foreground app name (for contextual content).

    Returns:
        dict with popup details for logging.
    """
    from android_world.env import adb_utils

    # Pick random popup type
    popup_type = rng.choice(POPUP_TYPES)

    # Check if current_app is a valid target (not launcher/system UI)
    # Launcher apps have generic context, LLM generates poor content for them
    _LAUNCHER_PACKAGES = (
        'launcher', 'launcher3', 'nexuslauncher', 'pixel_launcher',
        'trebuchet', 'quickstep', 'touchwizhome', 'oneui_home',
    )
    is_launcher = current_app and any(l in current_app.lower() for l in _LAUNCHER_PACKAGES)

    # Generate content: use LLM only for valid app context
    if vllm_wrapper and current_app and not is_launcher:
        content = _generate_content_with_llm(vllm_wrapper, popup_type, current_app)
        # Fallback to template if LLM fails or returns invalid content
        if content is None:
            content = _get_template_content(popup_type, rng)
    else:
        content = _get_template_content(popup_type, rng)

    # For fullscreen_ad, attach a random image from the device-side pool so the
    # APK renders a real bitmap instead of the "ADVERTISEMENT" text fallback.
    # The pool is mirrored once per env from <repo>/screenshot_photo/_ad_pool/.
    if popup_type == 'fullscreen_ad':
        _ensure_ad_pool_on_device(env)
        pool = _device_ad_paths()
        if pool:
            content['image_path'] = rng.choice(pool)

    # Step 1: Ensure TrapOverlay app is running (dynamic receiver needs it)
    adb_utils.issue_generic_request(
        ['shell', 'am', 'start', '-n', 'com.trap.overlay/.MainActivity'],
        env.controller,
    )
    time.sleep(0.3)

    # Step 2: Go back to the task app
    adb_utils.issue_generic_request(
        ['shell', 'input', 'keyevent', 'KEYCODE_BACK'],
        env.controller,
    )
    time.sleep(0.5)

    # Step 3: Send broadcast to show popup overlay (must specify component)
    # Note: String values must be quoted to preserve spaces in shell command
    cmd = ['shell', 'am', 'broadcast',
           '-n', 'com.trap.overlay/.TrapBroadcastReceiver',
           '-a', 'com.trap.SHOW_POPUP',
           '--es', 'type', popup_type,
           '--es', 'title', '"{}"'.format(content.get('title', '')),
           '--es', 'message', '"{}"'.format(content.get('message', '')),
           '--es', 'button1', '"{}"'.format(content.get('button1', 'OK')),
           '--es', 'button2', '"{}"'.format(content.get('button2', 'Cancel'))]

    if 'image_path' in content:
        cmd.extend(['--es', 'image_path', '"{}"'.format(content['image_path'])])

    adb_utils.issue_generic_request(cmd, env.controller)

    # Wait for popup to render
    time.sleep(1.0)

    return {
        'popup_type': popup_type,
        'title': content.get('title', ''),
        'message': content.get('message', ''),
        'image_path': content.get('image_path', ''),
    }


def _get_template_content(popup_type: str, rng: random.Random) -> dict:
    """Pick a random template for the popup type."""
    templates = _POPUP_TEMPLATES.get(popup_type, _POPUP_TEMPLATES['center_dialog'])
    return dict(rng.choice(templates))


def _generate_content_with_llm(vllm_wrapper, popup_type: str, current_app: str) -> dict:
    """Use vLLM to generate contextual popup content."""
    # Build detailed prompt for realistic popup generation
    if popup_type == 'permission':
        prompt = f"""Generate a realistic Android permission request dialog for the app '{current_app}'.

Requirements:
- title: 3-6 words, specific to the app (e.g., "Camera Access Required")
- message: 10-20 words, explain why the permission is needed
- button1: positive action (e.g., "Allow", "Enable")
- button2: negative action (e.g., "Deny", "Don't Allow")

Output JSON only:
{{"title": "...", "message": "...", "button1": "...", "button2": "..."}}"""
    elif popup_type == 'fullscreen_ad':
        prompt = f"""Generate a realistic full-screen advertisement text for an app that might appear while using '{current_app}'.

Requirements:
- title: 5-10 words, catchy promotional text (e.g., "LIMITED TIME OFFER - 50% OFF TODAY ONLY!")

Output JSON only:
{{"title": "..."}}"""
    elif popup_type == 'top_banner':
        prompt = f"""Generate a realistic Android notification banner that might appear while using '{current_app}'.

Requirements:
- title: 2-4 words, notification type (e.g., "New Message", "Update Available")
- message: 8-15 words, specific notification content

Output JSON only:
{{"title": "...", "message": "..."}}"""
    else:  # center_dialog
        prompt = f"""Generate a realistic Android dialog popup that might appear while using '{current_app}'.

Requirements:
- title: 3-5 words, dialog purpose (e.g., "Update Available", "Sign In Required")
- message: 15-25 words, detailed information about the dialog

Output JSON only:
{{"title": "...", "message": "..."}}"""

    try:
        response, _, _ = vllm_wrapper.predict_mm(prompt, [])
        import json
        # Try to parse JSON from response
        response = response.strip()
        print(f'[TRAP LLM] Raw response: {response[:200]}...' if len(response) > 200 else f'[TRAP LLM] Raw response: {response}')
        if '{' in response:
            json_str = response[response.index('{'):response.rindex('}') + 1]
            content = json.loads(json_str)
            # Validate: title must be meaningful (at least 3 chars)
            if not content.get('title') or len(content.get('title', '')) < 3:
                print(f'[TRAP LLM] Invalid title: {content.get("title")}')
                return None
            print(f'[TRAP LLM] Generated: {content}')
            return content
    except Exception as e:
        print(f'[TRAP LLM] Error: {e}')

    # Fallback to template if LLM fails or returns invalid content
    return None


def apply_visual_obscuration(
    pixels: np.ndarray,
    ui_elements,
    config: TrapConfig,
    rng: random.Random,
) -> np.ndarray:
    """Apply blur or color patch to a region of the screenshot.

    Args:
        pixels: Screenshot as numpy array (H, W, 3).
        ui_elements: List of UIElement objects with bbox_pixels.
        config: TrapConfig with blur params.
        rng: Random instance for reproducibility.

    Returns:
        Modified pixels array.
    """
    h, w = pixels.shape[:2]
    img = Image.fromarray(pixels)

    # Determine target region
    bbox = _select_target_bbox(ui_elements, config, rng, w, h)
    if bbox is None:
        return pixels  # No valid target, skip

    x_min, y_min, x_max, y_max = bbox

    # Apply blur or solid patch
    if config.patch_color is not None:
        # Solid color patch
        region = Image.new('RGB', (x_max - x_min, y_max - y_min), config.patch_color)
    else:
        # Gaussian blur
        region = img.crop((x_min, y_min, x_max, y_max))
        region = region.filter(ImageFilter.GaussianBlur(radius=config.blur_radius))

    img.paste(region, (x_min, y_min))
    return np.array(img)


def _select_target_bbox(ui_elements, config: TrapConfig, rng: random.Random, w, h):
    """Select a bounding box region to obscure.

    Returns:
        (x_min, y_min, x_max, y_max) in pixel coordinates, or None.
    """
    if config.blur_target == 'random_region':
        # Random rectangular region (10-30% of screen)
        region_w = rng.randint(int(w * 0.1), int(w * 0.3))
        region_h = rng.randint(int(h * 0.1), int(h * 0.3))
        x_min = rng.randint(0, max(0, w - region_w))
        y_min = rng.randint(0, max(0, h - region_h))
        return (x_min, y_min, x_min + region_w, y_min + region_h)

    if ui_elements is None or len(ui_elements) == 0:
        return None

    # Filter elements with valid bounding boxes
    valid_elements = []
    for elem in ui_elements:
        if elem.bbox_pixels is not None:
            bb = elem.bbox_pixels
            if bb.x_max > bb.x_min and bb.y_max > bb.y_min:
                valid_elements.append(elem)

    if not valid_elements:
        return None

    if config.blur_target == 'key_element':
        # Prefer clickable/editable elements
        key_elements = [
            e for e in valid_elements
            if e.is_clickable or e.is_editable
        ]
        if key_elements:
            valid_elements = key_elements

    # Pick random element
    elem = rng.choice(valid_elements)
    bb = elem.bbox_pixels
    return (
        int(bb.x_min), int(bb.y_min),
        int(bb.x_max), int(bb.y_max),
    )
