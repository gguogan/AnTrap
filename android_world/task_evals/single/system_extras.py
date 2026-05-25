# Copyright 2025 The android_world Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tier D system-settings toggle tasks.

Four pairs of toggle tasks (TurnOn / TurnOff) for additional Settings panes:

  airplane mode, dark (night) mode, auto-rotate, location services.

Each pair follows the same recipe used by the existing AndroidWorld
`SystemWifiTurnOn` / `SystemWifiTurnOff`: a private `_Xxx` base class
implements `is_successful()` by reading the underlying Android settings
key, and the two concrete subclasses set the precondition state in
`initialize_task()` before the agent runs.
"""

import random

from android_world.env import adb_utils
from android_world.env import interface
from android_world.task_evals import task_eval


# =============================================================================
# Airplane mode -- settings global airplane_mode_on
# =============================================================================
def _set_airplane(controller, on: bool) -> None:
  value = '1' if on else '0'
  adb_utils.issue_generic_request(
      ['shell', 'settings', 'put', 'global', 'airplane_mode_on', value],
      controller,
  )
  adb_utils.issue_generic_request(
      [
          'shell', 'am', 'broadcast', '-a',
          'android.intent.action.AIRPLANE_MODE', '--ez', 'state',
          'true' if on else 'false',
      ],
      controller,
  )


class _SystemAirplaneToggle(task_eval.TaskEval):
  """Common machinery for airplane-mode toggle tasks."""

  app_names = ('settings',)
  complexity = 1
  schema = {
      'type': 'object',
      'properties': {'on_or_off': {'type': 'string', 'enum': ['on', 'off']}},
      'required': ['on_or_off'],
  }
  template = 'Turn airplane mode {on_or_off}.'

  def is_successful(self, env: interface.AsyncEnv) -> float:
    super().is_successful(env)
    res = adb_utils.issue_generic_request(
        ['shell', 'settings', 'get', 'global', 'airplane_mode_on'],
        env.controller,
    )
    val = res.generic.output.decode().strip()
    if self.params['on_or_off'] == 'on':
      return 1.0 if val == '1' else 0.0
    return 1.0 if val == '0' else 0.0

  @classmethod
  def generate_random_params(cls):
    return {'on_or_off': 'on' if random.choice([True, False]) else 'off'}


class SystemAirplaneTurnOn(_SystemAirplaneToggle):
  """Turn airplane mode on. Precondition: it is off."""

  def initialize_task(self, env: interface.AsyncEnv) -> None:
    super().initialize_task(env)
    _set_airplane(env.controller, on=False)

  @classmethod
  def generate_random_params(cls):
    return {'on_or_off': 'on'}


class SystemAirplaneTurnOff(_SystemAirplaneToggle):
  """Turn airplane mode off. Precondition: it is on."""

  def initialize_task(self, env: interface.AsyncEnv) -> None:
    super().initialize_task(env)
    _set_airplane(env.controller, on=True)

  @classmethod
  def generate_random_params(cls):
    return {'on_or_off': 'off'}


# =============================================================================
# Dark / night mode -- uimode night
# =============================================================================
def _set_dark_mode(controller, on: bool) -> None:
  arg = 'yes' if on else 'no'
  adb_utils.issue_generic_request(
      ['shell', 'cmd', 'uimode', 'night', arg], controller,
  )


class _SystemDarkModeToggle(task_eval.TaskEval):
  """Common machinery for dark-mode toggle tasks."""

  app_names = ('settings',)
  complexity = 1
  schema = {
      'type': 'object',
      'properties': {'on_or_off': {'type': 'string', 'enum': ['on', 'off']}},
      'required': ['on_or_off'],
  }
  template = 'Turn dark mode {on_or_off}.'

  def is_successful(self, env: interface.AsyncEnv) -> float:
    super().is_successful(env)
    res = adb_utils.issue_generic_request(
        ['shell', 'cmd', 'uimode', 'night'], env.controller,
    )
    out = res.generic.output.decode().strip().lower()
    is_on = 'yes' in out or 'on' in out
    if self.params['on_or_off'] == 'on':
      return 1.0 if is_on else 0.0
    return 1.0 if not is_on else 0.0

  @classmethod
  def generate_random_params(cls):
    return {'on_or_off': 'on' if random.choice([True, False]) else 'off'}


class SystemDarkModeTurnOn(_SystemDarkModeToggle):
  """Turn dark mode on. Precondition: dark mode is off."""

  def initialize_task(self, env: interface.AsyncEnv) -> None:
    super().initialize_task(env)
    _set_dark_mode(env.controller, on=False)

  @classmethod
  def generate_random_params(cls):
    return {'on_or_off': 'on'}


class SystemDarkModeTurnOff(_SystemDarkModeToggle):
  """Turn dark mode off. Precondition: dark mode is on."""

  def initialize_task(self, env: interface.AsyncEnv) -> None:
    super().initialize_task(env)
    _set_dark_mode(env.controller, on=True)

  @classmethod
  def generate_random_params(cls):
    return {'on_or_off': 'off'}


# =============================================================================
# Auto-rotate -- settings system accelerometer_rotation
# =============================================================================
def _set_auto_rotate(controller, on: bool) -> None:
  value = '1' if on else '0'
  adb_utils.issue_generic_request(
      ['shell', 'settings', 'put', 'system', 'accelerometer_rotation', value],
      controller,
  )


class _SystemAutoRotateToggle(task_eval.TaskEval):
  """Common machinery for auto-rotate toggle tasks."""

  app_names = ('settings',)
  complexity = 1
  schema = {
      'type': 'object',
      'properties': {'on_or_off': {'type': 'string', 'enum': ['on', 'off']}},
      'required': ['on_or_off'],
  }
  template = 'Turn auto-rotate {on_or_off}.'

  def is_successful(self, env: interface.AsyncEnv) -> float:
    super().is_successful(env)
    res = adb_utils.issue_generic_request(
        [
            'shell', 'settings', 'get', 'system',
            'accelerometer_rotation',
        ],
        env.controller,
    )
    val = res.generic.output.decode().strip()
    if self.params['on_or_off'] == 'on':
      return 1.0 if val == '1' else 0.0
    return 1.0 if val == '0' else 0.0

  @classmethod
  def generate_random_params(cls):
    return {'on_or_off': 'on' if random.choice([True, False]) else 'off'}


class SystemAutoRotateTurnOn(_SystemAutoRotateToggle):
  """Turn auto-rotate on. Precondition: auto-rotate is off."""

  def initialize_task(self, env: interface.AsyncEnv) -> None:
    super().initialize_task(env)
    _set_auto_rotate(env.controller, on=False)

  @classmethod
  def generate_random_params(cls):
    return {'on_or_off': 'on'}


class SystemAutoRotateTurnOff(_SystemAutoRotateToggle):
  """Turn auto-rotate off. Precondition: auto-rotate is on."""

  def initialize_task(self, env: interface.AsyncEnv) -> None:
    super().initialize_task(env)
    _set_auto_rotate(env.controller, on=True)

  @classmethod
  def generate_random_params(cls):
    return {'on_or_off': 'off'}


# =============================================================================
# Location services -- settings secure location_mode
# =============================================================================
# location_mode: 0 = off, 3 = high-accuracy (or any non-zero = on).
def _set_location(controller, on: bool) -> None:
  value = '3' if on else '0'
  adb_utils.issue_generic_request(
      ['shell', 'settings', 'put', 'secure', 'location_mode', value],
      controller,
  )


class _SystemLocationToggle(task_eval.TaskEval):
  """Common machinery for location-services toggle tasks."""

  app_names = ('settings',)
  complexity = 1
  schema = {
      'type': 'object',
      'properties': {'on_or_off': {'type': 'string', 'enum': ['on', 'off']}},
      'required': ['on_or_off'],
  }
  template = 'Turn location services {on_or_off}.'

  def is_successful(self, env: interface.AsyncEnv) -> float:
    super().is_successful(env)
    res = adb_utils.issue_generic_request(
        ['shell', 'settings', 'get', 'secure', 'location_mode'],
        env.controller,
    )
    val = res.generic.output.decode().strip()
    if self.params['on_or_off'] == 'on':
      # Any non-zero value counts as on.
      return 1.0 if val not in ('0', 'null', '') else 0.0
    return 1.0 if val == '0' else 0.0

  @classmethod
  def generate_random_params(cls):
    return {'on_or_off': 'on' if random.choice([True, False]) else 'off'}


class SystemLocationTurnOn(_SystemLocationToggle):
  """Turn location services on. Precondition: location is off."""

  def initialize_task(self, env: interface.AsyncEnv) -> None:
    super().initialize_task(env)
    _set_location(env.controller, on=False)

  @classmethod
  def generate_random_params(cls):
    return {'on_or_off': 'on'}


class SystemLocationTurnOff(_SystemLocationToggle):
  """Turn location services off. Precondition: location is on."""

  def initialize_task(self, env: interface.AsyncEnv) -> None:
    super().initialize_task(env)
    _set_location(env.controller, on=True)

  @classmethod
  def generate_random_params(cls):
    return {'on_or_off': 'off'}
