# Copyright 2025 The android_world Authors.

"""Tier F -- additional system-settings toggle pairs.

Adaptive brightness, mobile data, NFC, and screen timeout. Each pair
follows the same precondition-setup pattern as the existing AndroidWorld
SystemWifi* family.
"""

import random

from android_world.env import adb_utils
from android_world.env import interface
from android_world.task_evals import task_eval


def _settings_put(controller, namespace, key, value):
  adb_utils.issue_generic_request(
      ['shell', 'settings', 'put', namespace, key, value], controller,
  )


def _settings_get(controller, namespace, key):
  res = adb_utils.issue_generic_request(
      ['shell', 'settings', 'get', namespace, key], controller,
  )
  return res.generic.output.decode().strip()


# =============================================================================
# Adaptive brightness -- settings system screen_brightness_mode (0/1)
# =============================================================================
class _AdaptiveBrightnessToggle(task_eval.TaskEval):
  app_names = ('settings',)
  complexity = 1
  schema = {
      'type': 'object',
      'properties': {'on_or_off': {'type': 'string', 'enum': ['on', 'off']}},
      'required': ['on_or_off'],
  }
  template = 'Turn adaptive brightness {on_or_off}.'

  def is_successful(self, env: interface.AsyncEnv) -> float:
    super().is_successful(env)
    val = _settings_get(env.controller, 'system', 'screen_brightness_mode')
    if self.params['on_or_off'] == 'on':
      return 1.0 if val == '1' else 0.0
    return 1.0 if val == '0' else 0.0

  @classmethod
  def generate_random_params(cls):
    return {'on_or_off': 'on' if random.choice([True, False]) else 'off'}


class SystemAdaptiveBrightnessTurnOn(_AdaptiveBrightnessToggle):
  def initialize_task(self, env):
    super().initialize_task(env)
    _settings_put(env.controller, 'system', 'screen_brightness_mode', '0')

  @classmethod
  def generate_random_params(cls):
    return {'on_or_off': 'on'}


class SystemAdaptiveBrightnessTurnOff(_AdaptiveBrightnessToggle):
  def initialize_task(self, env):
    super().initialize_task(env)
    _settings_put(env.controller, 'system', 'screen_brightness_mode', '1')

  @classmethod
  def generate_random_params(cls):
    return {'on_or_off': 'off'}


# =============================================================================
# Mobile data -- svc data enable/disable (via cmd phone)
# =============================================================================
def _set_mobile_data(controller, on: bool):
  arg = 'enable' if on else 'disable'
  adb_utils.issue_generic_request(['shell', 'svc', 'data', arg], controller)


class _MobileDataToggle(task_eval.TaskEval):
  app_names = ('settings',)
  complexity = 1
  schema = {
      'type': 'object',
      'properties': {'on_or_off': {'type': 'string', 'enum': ['on', 'off']}},
      'required': ['on_or_off'],
  }
  template = 'Turn mobile data {on_or_off}.'

  def is_successful(self, env: interface.AsyncEnv) -> float:
    super().is_successful(env)
    val = _settings_get(env.controller, 'global', 'mobile_data')
    if self.params['on_or_off'] == 'on':
      return 1.0 if val == '1' else 0.0
    return 1.0 if val == '0' else 0.0

  @classmethod
  def generate_random_params(cls):
    return {'on_or_off': 'on' if random.choice([True, False]) else 'off'}


class SystemMobileDataTurnOn(_MobileDataToggle):
  def initialize_task(self, env):
    super().initialize_task(env)
    _set_mobile_data(env.controller, on=False)

  @classmethod
  def generate_random_params(cls):
    return {'on_or_off': 'on'}


class SystemMobileDataTurnOff(_MobileDataToggle):
  def initialize_task(self, env):
    super().initialize_task(env)
    _set_mobile_data(env.controller, on=True)

  @classmethod
  def generate_random_params(cls):
    return {'on_or_off': 'off'}


# =============================================================================
# NFC -- svc nfc enable/disable
# =============================================================================
def _set_nfc(controller, on: bool):
  arg = 'enable' if on else 'disable'
  adb_utils.issue_generic_request(['shell', 'svc', 'nfc', arg], controller)


class _NfcToggle(task_eval.TaskEval):
  app_names = ('settings',)
  complexity = 1
  schema = {
      'type': 'object',
      'properties': {'on_or_off': {'type': 'string', 'enum': ['on', 'off']}},
      'required': ['on_or_off'],
  }
  template = 'Turn NFC {on_or_off}.'

  def is_successful(self, env: interface.AsyncEnv) -> float:
    super().is_successful(env)
    # NFC state is typically exposed via settings.global.nfc_on or similar;
    # fall back to dumpsys nfc.
    val = _settings_get(env.controller, 'global', 'nfc_on')
    if val not in ('0', '1'):
      # Fallback to dumpsys
      res = adb_utils.issue_generic_request(
          ['shell', 'dumpsys', 'nfc'], env.controller,
      )
      out = res.generic.output.decode().lower()
      is_on = 'state=on' in out or 'mstate=on' in out
      val = '1' if is_on else '0'
    if self.params['on_or_off'] == 'on':
      return 1.0 if val == '1' else 0.0
    return 1.0 if val == '0' else 0.0

  @classmethod
  def generate_random_params(cls):
    return {'on_or_off': 'on' if random.choice([True, False]) else 'off'}


class SystemNfcTurnOn(_NfcToggle):
  def initialize_task(self, env):
    super().initialize_task(env)
    _set_nfc(env.controller, on=False)

  @classmethod
  def generate_random_params(cls):
    return {'on_or_off': 'on'}


class SystemNfcTurnOff(_NfcToggle):
  def initialize_task(self, env):
    super().initialize_task(env)
    _set_nfc(env.controller, on=True)

  @classmethod
  def generate_random_params(cls):
    return {'on_or_off': 'off'}


# =============================================================================
# Screen timeout -- settings system screen_off_timeout (ms). Targets: short=15s
# vs long=30 minutes.
# =============================================================================
class _ScreenTimeoutToggle(task_eval.TaskEval):
  app_names = ('settings',)
  complexity = 1
  schema = {
      'type': 'object',
      'properties': {'mode': {'type': 'string', 'enum': ['short', 'long']}},
      'required': ['mode'],
  }
  template = 'Set screen timeout to {mode}.'

  _SHORT_MS = 15000      # 15 seconds
  _LONG_MS = 1800000     # 30 minutes
  _TOL = 5000

  def is_successful(self, env: interface.AsyncEnv) -> float:
    super().is_successful(env)
    val = _settings_get(env.controller, 'system', 'screen_off_timeout')
    try:
      ms = int(val)
    except ValueError:
      return 0.0
    target = self._SHORT_MS if self.params['mode'] == 'short' else self._LONG_MS
    return 1.0 if abs(ms - target) <= self._TOL else 0.0

  @classmethod
  def generate_random_params(cls):
    return {'mode': random.choice(['short', 'long'])}


class SystemScreenTimeoutShort(_ScreenTimeoutToggle):
  template = 'Set screen timeout to a short value of about 15 seconds.'

  def initialize_task(self, env):
    super().initialize_task(env)
    _settings_put(env.controller, 'system', 'screen_off_timeout', '600000')

  @classmethod
  def generate_random_params(cls):
    return {'mode': 'short'}


class SystemScreenTimeoutLong(_ScreenTimeoutToggle):
  template = 'Set screen timeout to a long value of about 30 minutes.'

  def initialize_task(self, env):
    super().initialize_task(env)
    _settings_put(env.controller, 'system', 'screen_off_timeout', '30000')

  @classmethod
  def generate_random_params(cls):
    return {'mode': 'long'}
