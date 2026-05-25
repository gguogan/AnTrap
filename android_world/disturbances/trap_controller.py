"""TrapController — central coordinator for trap injection.

Provides hooks at 4 interception points:
1. on_screenshot()  — after screenshot capture, before model input (S/T-Layer)
2. on_action()      — after action parsing, before execution (A-Layer)
3. should_block_execution() — state deadlock check (Overall)
4. pre_step()       — before agent.step(), trajectory-level injection (Overall)
"""

from __future__ import annotations

import json
import random
import time
from typing import Optional

import numpy as np

from android_world.disturbances.trap_config import TrapConfig, VALID_TRAP_TYPES


class TrapController:

    def __init__(self, config: TrapConfig, env=None,
                 vllm_wrapper=None):
        self.config = config
        self.env = env
        self.max_steps: int = 30  # Updated by episode_runner before each episode
        self.screenshot_history: list[np.ndarray] = []
        self.trap_log: list[dict] = []
        self._deadlock_remaining: int = 0
        self._traps_fired: int = 0  # Counter for min/max enforcement
        self._rng = random.Random(config.seed)
        self._step_resolved_type: dict[int, str] = {}  # Cache resolved type per step
        self._vllm_wrapper = vllm_wrapper  # For LLM-generated popup content
        self._current_app: str = ''  # Current foreground app (set by agent)
        self._current_task_name: str = ''  # Task class name, for screenshot pool
        self._last_ui_elements = None  # Cached so on_action() can see them
        self._last_screen_size = (1080, 2400)  # Updated in on_screenshot
        # Lazy-loaded layer implementations
        self._s_layer = None
        self._t_layer = None
        self._a_layer = None
        self._overall = None

    # ------------------------------------------------------------------
    # Lazy imports for layer implementations
    # ------------------------------------------------------------------
    def _get_s_layer(self):
        if self._s_layer is None:
            from android_world.disturbances import s_layer
            self._s_layer = s_layer
        return self._s_layer

    def _get_t_layer(self):
        if self._t_layer is None:
            from android_world.disturbances import t_layer
            self._t_layer = t_layer
        return self._t_layer

    def _get_a_layer(self):
        if self._a_layer is None:
            from android_world.disturbances import a_layer
            self._a_layer = a_layer
        return self._a_layer

    def _get_overall(self):
        if self._overall is None:
            from android_world.disturbances import overall
            self._overall = overall
        return self._overall

    def _get_current_app(self):
        """Get current foreground app package name via ADB."""
        if self.env is None:
            return ''
        from android_world.env import adb_utils
        import re
        try:
            # Get foreground activity via dumpsys
            result = adb_utils.issue_generic_request(
                ['shell', 'dumpsys', 'activity', 'activities'],
                self.env.controller,
            )
            # Parse mResumedActivity from output
            # Example: mResumedActivity: ActivityRecord{... com.example.app/.MainActivity}
            match = re.search(r'mResumedActivity:.*\s([\w.]+)/', str(result))
            if match:
                return match.group(1)
        except Exception:
            pass
        return ''

    # ------------------------------------------------------------------
    # Core decision
    # ------------------------------------------------------------------
    def _resolve_trap_type(self, step_idx: int = -1) -> str:
        """Resolve 'random' to a concrete trap_type.

        When step_idx >= 0, caches the result so multiple hooks in the
        same step see the same resolved type.
        """
        if self.config.trap_type != 'random':
            return self.config.trap_type
        if step_idx >= 0 and step_idx in self._step_resolved_type:
            return self._step_resolved_type[step_idx]
        types = VALID_TRAP_TYPES.get(self.config.category, ())
        chosen = self._rng.choice(types)
        if step_idx >= 0:
            self._step_resolved_type[step_idx] = chosen
        return chosen

    def _in_trap_window(self, step_idx: int) -> bool:
        """Check if current step is within the trap injection window (first 80% of original max_steps)."""
        trap_cutoff = int(self.max_steps * 0.8)
        return step_idx < trap_cutoff

    def should_trigger(self, step_idx: int) -> bool:
        """Roll dice to decide if trap fires this step.

        Enforces:
        - At most max_traps per episode (0 = unlimited)
        - Only within trap window (first 80% of original max_steps)
        - If no trap triggers, episode will be re-run by the runner
        """
        if not self._in_trap_window(step_idx):
            return False

        # Max cap: stop if already hit limit
        max_traps = self.config.max_traps
        if max_traps > 0 and self._traps_fired >= max_traps:
            return False

        return self._rng.random() < self.config.trigger_probability

    # ------------------------------------------------------------------
    # Hook 1: Screenshot interception
    # ------------------------------------------------------------------
    def set_current_task_name(self, name: str) -> None:
        """Episode runner should call this once per episode so traps that
        depend on the task identity (e.g. preloaded screenshot pool) can look
        up the right resources."""
        self._current_task_name = name or ''

    def on_screenshot(
        self,
        pixels: np.ndarray,
        step_idx: int,
        ui_elements=None,
    ) -> tuple[np.ndarray, np.ndarray]:
        """Called after screenshot capture.

        Returns:
            (model_input_pixels, history_pixels)
            - Mode A: both modified (S-Layer)
            - Mode B: only model_input modified, history keeps original (T-Layer)
        """
        self.screenshot_history.append(pixels.copy())
        # Cache for on_action — Intent Deviation needs ui_elements & screen size.
        self._last_ui_elements = ui_elements
        if pixels is not None and hasattr(pixels, 'shape') and len(pixels.shape) >= 2:
            self._last_screen_size = (pixels.shape[1], pixels.shape[0])

        if self.config.category == 's_layer' and self.should_trigger(step_idx):
            trap_type = self._resolve_trap_type(step_idx)
            mod = self._get_s_layer()
            if trap_type == 'visual_obscuration':
                modified = mod.apply_visual_obscuration(
                    pixels, ui_elements, self.config, self._rng
                )
            elif trap_type == 'external_interruption':
                # Get current foreground app for contextual LLM generation
                self._current_app = self._get_current_app()
                # Trigger popup overlay via APK. The popup appears on the
                # real device BEFORE the agent's next screenshot capture.
                # We trigger it here (during screenshot hook) so the agent
                # sees it in the current step's screenshot.
                details = mod.apply_external_interruption(
                    self.env, self.config, self._rng,
                    vllm_wrapper=self._vllm_wrapper,
                    current_app=self._current_app,
                )
                self._log(step_idx, 'external_interruption', details)
                # Re-capture screenshot with popup visible
                if self.env is not None:
                    import time
                    time.sleep(0.5)
                    try:
                        state = self.env.get_state(wait_to_stabilize=False)
                        return state.pixels, state.pixels  # Mode A
                    except Exception:
                        pass
                return pixels, pixels
            else:
                return pixels, pixels
            self._log(step_idx, 'screenshot_modified', {
                'trap_type': trap_type,
            })
            return modified, modified  # Mode A

        if self.config.category == 't_layer' and self.should_trigger(step_idx):
            trap_type = self._resolve_trap_type(step_idx)
            mod = self._get_t_layer()
            if trap_type == 'temporal_conflict':
                modified = mod.apply_temporal_conflict(
                    pixels, step_idx, self.screenshot_history, self.config,
                    task_name=self._current_task_name,
                )
            elif trap_type == 'visual_hallucination':
                modified = mod.apply_visual_hallucination(
                    pixels, ui_elements, self.config, self._rng
                )
            else:
                return pixels, pixels
            if modified is None:
                # Trap skipped (e.g., not enough history)
                return pixels, pixels
            self._log(step_idx, 'screenshot_tampered', {
                'trap_type': trap_type,
            })
            return modified, pixels  # Mode B: history keeps original

        return pixels, pixels

    # ------------------------------------------------------------------
    # Hook 2: Action interception
    # ------------------------------------------------------------------
    def on_action(self, action, dummy_action, step_idx: int):
        """Called after action parsing, before execution.

        Returns:
            (modified_action, modified_dummy_action)
        """
        if self.config.category == 'a_layer' and self.should_trigger(step_idx):
            trap_type = self._resolve_trap_type(step_idx)
            mod = self._get_a_layer()
            if trap_type == 'grounding_error':
                action, dummy_action = mod.apply_grounding_error(
                    action, dummy_action, self.config, self._rng
                )
                trap_info = getattr(action, '_trap_info', {})
                self._log(step_idx, 'coordinate_offset', {
                    'trap_type': trap_type,
                    'original': trap_info.get('original'),
                    'offset': trap_info.get('offset'),
                })
            elif trap_type == 'type_mismatch':
                orig_type = action.action_type
                action, dummy_action = mod.apply_type_mismatch(
                    action, dummy_action, self.config, self._rng
                )
                self._log(step_idx, 'action_remapped', {
                    'trap_type': trap_type,
                    'original': orig_type,
                    'new_type': action.action_type,
                })
            elif trap_type == 'intent_deviation':
                action, dummy_action = mod.apply_intent_deviation(
                    action, dummy_action,
                    self._last_ui_elements, self._last_screen_size,
                    self.config, self._rng,
                )
                info = getattr(action, '_trap_info', {})
                self._log(step_idx, 'intent_deviated', {
                    'trap_type': trap_type,
                    'original_type': info.get('original_type'),
                    'original_xy': info.get('original_xy'),
                    'retargeted_xy': info.get('retargeted_xy'),
                    'retargeted_text': info.get('retargeted_text'),
                    'retarget_label': info.get('retarget_label'),
                })
        return action, dummy_action

    # ------------------------------------------------------------------
    # Hook 3: Execution blocking (State Deadlock)
    # ------------------------------------------------------------------
    def should_block_execution(self, step_idx: int) -> bool:
        """State Deadlock: return True to skip ADB execution this step."""
        if self.config.category != 'overall':
            return False

        # If in an active deadlock sequence, continue blocking
        if self._deadlock_remaining > 0:
            self._deadlock_remaining -= 1
            self._log(step_idx, 'execution_blocked', {
                'remaining': self._deadlock_remaining,
            }, is_continuation=True)
            return True

        # Only start new deadlock when resolved type is state_deadlock
        trap_type = self._resolve_trap_type(step_idx)
        if trap_type == 'state_deadlock' and self.should_trigger(step_idx):
            # Random duration: 1 to max_steps//4
            max_dur = max(1, self.max_steps // 4)
            duration = self._rng.randint(1, max_dur)
            self._deadlock_remaining = duration - 1
            self._log(step_idx, 'deadlock_started', {
                'trap_type': trap_type, 'duration': duration,
            })
            return True

        return False

    # ------------------------------------------------------------------
    # Hook 4: Pre-step trajectory injection
    # ------------------------------------------------------------------
    def pre_step(self, env, step_idx: int):
        """Called BEFORE agent.step(). For trajectory-level traps."""
        if self.config.category != 'overall':
            return

        trap_type = self._resolve_trap_type()
        mod = self._get_overall()

        if trap_type == 'context_disruption':
            if self.should_trigger(step_idx):
                mod.inject_context_disruption(env, self.config)
                self._log(step_idx, 'context_disruption', {
                    'trap_type': trap_type, 'type': self.config.disruption_type,
                })

        elif trap_type == 'loop':
            if step_idx > 0 and step_idx % self.config.loop_interval == 0:
                max_traps = self.config.max_traps
                if max_traps > 0 and self._traps_fired >= max_traps:
                    pass  # Already hit max_traps limit
                else:
                    mod.inject_back(env)
                    self._log(step_idx, 'loop_back_injected', {'trap_type': trap_type})

        elif trap_type == 'state_deadlock':
            pass  # Handled in should_block_execution()

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def _log(self, step_idx: int, event: str, details: dict,
             is_continuation: bool = False):
        if not is_continuation:
            self._traps_fired += 1
        entry = {
            'step': step_idx,
            'category': self.config.category,
            'trap_type': self.config.trap_type,
            'event': event,
            'details': details,
            'traps_fired': self._traps_fired,
            'timestamp': time.time(),
        }
        self.trap_log.append(entry)
        print(f'[TRAP] step={step_idx} event={event} details={details}')

    def get_trap_log(self) -> list[dict]:
        return self.trap_log

    def save_trap_log(self, path: str):
        with open(path, 'w') as f:
            for entry in self.trap_log:
                f.write(json.dumps(entry) + '\n')

    def reset(self):
        """Reset state for a new episode."""
        self.screenshot_history.clear()
        self.trap_log.clear()
        self._deadlock_remaining = 0
        self._traps_fired = 0
        self._step_resolved_type.clear()
        # RNG state carries over (not reset) so each episode gets a fresh random sequence.
        # Clean up any leftover trap overlay popups.
        self._dismiss_trap_overlay()

    def _dismiss_trap_overlay(self):
        """Grant overlay permission and dismiss any lingering trap popup."""
        if self.env is None:
            return
        from android_world.env import adb_utils
        try:
            # Grant SYSTEM_ALERT_WINDOW permission (required for popup overlay)
            adb_utils.issue_generic_request(
                ['shell', 'appops', 'set', 'com.trap.overlay', 'SYSTEM_ALERT_WINDOW', 'allow'],
                self.env.controller,
            )
            # Launch the TrapOverlay app first so it can receive the broadcast
            adb_utils.issue_generic_request(
                ['shell', 'am', 'start', '-n', 'com.trap.overlay/.MainActivity'],
                self.env.controller,
            )
            time.sleep(0.2)
            # Send the dismiss broadcast
            adb_utils.issue_generic_request(
                ['shell', 'am', 'broadcast',
                 '-n', 'com.trap.overlay/.TrapBroadcastReceiver',
                 '-a', 'com.trap.DISMISS_POPUP'],
                self.env.controller,
            )
            print('[TRAP] Dismissed overlay popup')
        except Exception as e:
            print(f'[TRAP] Failed to dismiss overlay: {e}')
