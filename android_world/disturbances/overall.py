"""Overall (Trajectory & Temporal) traps.

- State Deadlock: handled in TrapController.should_block_execution()
- Context Disruption: inject HOME/APP_SWITCH keyevent before agent step
- Loop: inject BACK keyevent periodically
"""

import time

from android_world.env import adb_utils
from android_world.disturbances.trap_config import TrapConfig


def inject_context_disruption(env, config: TrapConfig):
    """Send a disruptive keyevent to break the agent's context.

    Args:
        env: AsyncAndroidEnv (has .controller attribute).
        config: TrapConfig with disruption_type.
    """
    if config.disruption_type == 'home':
        adb_utils.press_home_button(env.controller)
    elif config.disruption_type == 'app_switch':
        adb_utils.issue_generic_request(
            ['shell', 'input', 'keyevent', 'KEYCODE_APP_SWITCH'],
            env.controller,
        )
    else:
        adb_utils.press_home_button(env.controller)
    # Brief pause to let the screen update
    time.sleep(1.0)


def inject_back(env):
    """Send BACK keyevent to force navigation regression."""
    adb_utils.press_back_button(env.controller)
    time.sleep(0.5)
