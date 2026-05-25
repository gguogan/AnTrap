# Copyright 2025 The android_world Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tier C Files-app tasks.

Five standalone TaskEval classes that exercise the on-device file manager
("files" app) via copy / rename / mkdir / move-into-new-folder / delete-empty
operations. None of them inherit from another single-task class; each carries
its own initialize_task and is_successful and clears device storage at the
beginning and end of the episode.
"""

import os
import random
from typing import Any

from android_world.env import device_constants
from android_world.env import interface
from android_world.task_evals import task_eval
from android_world.task_evals.utils import user_data_generation
from android_world.utils import file_utils


_DIRS = list(user_data_generation.EMULATOR_DIRECTORIES.keys())


# =============================================================================
# 1. FilesCopyFile
# =============================================================================
class FilesCopyFile(task_eval.TaskEval):
  """Copy a file from one folder to another; both locations must exist."""

  app_names = ('files',)
  complexity = 2.2
  schema = {
      'type': 'object',
      'properties': {
          'file_name': {'type': 'string'},
          'source_folder': {'type': 'string'},
          'destination_folder': {'type': 'string'},
      },
      'required': ['file_name', 'source_folder', 'destination_folder'],
  }
  template = (
      'Using the Files app, copy {file_name} from {source_folder} to'
      ' {destination_folder}. The file should remain in {source_folder}'
      ' AND also appear in {destination_folder}.'
  )

  def initialize_task(self, env: interface.AsyncEnv) -> None:
    super().initialize_task(env)
    user_data_generation.clear_device_storage(env)
    src_dir = file_utils.convert_to_posix_path(
        device_constants.EMULATOR_DATA, self.params['source_folder']
    )
    file_utils.mkdir(src_dir, env.controller)
    dst_dir = file_utils.convert_to_posix_path(
        device_constants.EMULATOR_DATA, self.params['destination_folder']
    )
    file_utils.mkdir(dst_dir, env.controller)
    file_utils.create_file(
        self.params['file_name'], src_dir, env.controller,
        content='seed content',
    )

  def tear_down(self, env: interface.AsyncEnv) -> None:
    super().tear_down(env)
    user_data_generation.clear_device_storage(env)

  def is_successful(self, env: interface.AsyncEnv) -> float:
    super().is_successful(env)
    name = self.params['file_name']
    src_dir = file_utils.convert_to_posix_path(
        device_constants.EMULATOR_DATA, self.params['source_folder']
    )
    dst_dir = file_utils.convert_to_posix_path(
        device_constants.EMULATOR_DATA, self.params['destination_folder']
    )
    if not file_utils.check_file_or_folder_exists(name, src_dir, env.controller):
      return 0.0
    if not file_utils.check_file_or_folder_exists(name, dst_dir, env.controller):
      return 0.0
    return 1.0

  @classmethod
  def generate_random_params(cls) -> dict[str, Any]:
    source_folder = random.choice(_DIRS)
    destination_folder = random.choice([d for d in _DIRS if d != source_folder])
    file_name = random.choice(
        user_data_generation.EMULATOR_DIRECTORIES[source_folder]
    )
    return {
        'file_name': file_name,
        'source_folder': source_folder,
        'destination_folder': destination_folder,
    }


# =============================================================================
# 2. FilesRenameFile
# =============================================================================
class FilesRenameFile(task_eval.TaskEval):
  """Rename a file in the same folder."""

  app_names = ('files',)
  complexity = 1.8
  schema = {
      'type': 'object',
      'properties': {
          'folder': {'type': 'string'},
          'original_name': {'type': 'string'},
          'new_name': {'type': 'string'},
      },
      'required': ['folder', 'original_name', 'new_name'],
  }
  template = (
      'Using the Files app, navigate to {folder} and rename the file'
      ' {original_name} to {new_name}. Keep it in the same folder.'
  )

  def initialize_task(self, env: interface.AsyncEnv) -> None:
    super().initialize_task(env)
    user_data_generation.clear_device_storage(env)
    folder = file_utils.convert_to_posix_path(
        device_constants.EMULATOR_DATA, self.params['folder']
    )
    file_utils.mkdir(folder, env.controller)
    file_utils.create_file(
        self.params['original_name'], folder, env.controller,
        content='seed content',
    )

  def tear_down(self, env: interface.AsyncEnv) -> None:
    super().tear_down(env)
    user_data_generation.clear_device_storage(env)

  def is_successful(self, env: interface.AsyncEnv) -> float:
    super().is_successful(env)
    folder = file_utils.convert_to_posix_path(
        device_constants.EMULATOR_DATA, self.params['folder']
    )
    if file_utils.check_file_or_folder_exists(
        self.params['original_name'], folder, env.controller,
    ):
      return 0.0
    if not file_utils.check_file_or_folder_exists(
        self.params['new_name'], folder, env.controller,
    ):
      return 0.0
    return 1.0

  @classmethod
  def generate_random_params(cls) -> dict[str, Any]:
    folder = random.choice(_DIRS)
    candidate = random.choice(
        user_data_generation.EMULATOR_DIRECTORIES[folder]
    )
    base, ext = os.path.splitext(candidate)
    new_name = (
        user_data_generation.generate_random_file_name() + ext
    )
    return {
        'folder': folder,
        'original_name': candidate,
        'new_name': new_name,
    }


# =============================================================================
# 3. FilesCreateFolder
# =============================================================================
class FilesCreateFolder(task_eval.TaskEval):
  """Create a new folder at the top level of internal storage."""

  app_names = ('files',)
  complexity = 1.4
  schema = {
      'type': 'object',
      'properties': {
          'folder_name': {'type': 'string'},
      },
      'required': ['folder_name'],
  }
  template = (
      'Using the Files app, create a new folder named {folder_name} at the'
      ' top level of internal storage (sdk_gphone_x86_64).'
  )

  def initialize_task(self, env: interface.AsyncEnv) -> None:
    super().initialize_task(env)
    user_data_generation.clear_device_storage(env)

  def tear_down(self, env: interface.AsyncEnv) -> None:
    super().tear_down(env)
    user_data_generation.clear_device_storage(env)

  def is_successful(self, env: interface.AsyncEnv) -> float:
    super().is_successful(env)
    ok = file_utils.check_file_or_folder_exists(
        self.params['folder_name'],
        device_constants.EMULATOR_DATA,
        env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls) -> dict[str, Any]:
    return {
        'folder_name': user_data_generation.generate_random_file_name(),
    }


# =============================================================================
# 4. FilesDeleteEmptyFolder
# =============================================================================
class FilesDeleteEmptyFolder(task_eval.TaskEval):
  """Delete an existing empty folder."""

  app_names = ('files',)
  complexity = 1.6
  schema = {
      'type': 'object',
      'properties': {
          'folder_name': {'type': 'string'},
      },
      'required': ['folder_name'],
  }
  template = (
      'Using the Files app, delete the empty folder named {folder_name} from'
      ' the top level of internal storage (sdk_gphone_x86_64).'
  )

  def initialize_task(self, env: interface.AsyncEnv) -> None:
    super().initialize_task(env)
    user_data_generation.clear_device_storage(env)
    folder = file_utils.convert_to_posix_path(
        device_constants.EMULATOR_DATA, self.params['folder_name']
    )
    file_utils.mkdir(folder, env.controller)

  def tear_down(self, env: interface.AsyncEnv) -> None:
    super().tear_down(env)
    user_data_generation.clear_device_storage(env)

  def is_successful(self, env: interface.AsyncEnv) -> float:
    super().is_successful(env)
    exists = file_utils.check_file_or_folder_exists(
        self.params['folder_name'],
        device_constants.EMULATOR_DATA,
        env.controller,
    )
    return 0.0 if exists else 1.0

  @classmethod
  def generate_random_params(cls) -> dict[str, Any]:
    return {
        'folder_name': user_data_generation.generate_random_file_name(),
    }


# =============================================================================
# 5. FilesMoveFileToNewFolder
# =============================================================================
class FilesMoveFileToNewFolder(task_eval.TaskEval):
  """Create a new folder under a source folder, then move a file into it."""

  app_names = ('files',)
  complexity = 2.4
  schema = {
      'type': 'object',
      'properties': {
          'file_name': {'type': 'string'},
          'source_folder': {'type': 'string'},
          'new_folder_name': {'type': 'string'},
      },
      'required': ['file_name', 'source_folder', 'new_folder_name'],
  }
  template = (
      'Using the Files app, go into {source_folder}, create a new folder'
      ' there named {new_folder_name}, and move the file {file_name} from'
      ' {source_folder} into that new folder.'
  )

  def initialize_task(self, env: interface.AsyncEnv) -> None:
    super().initialize_task(env)
    user_data_generation.clear_device_storage(env)
    src_dir = file_utils.convert_to_posix_path(
        device_constants.EMULATOR_DATA, self.params['source_folder']
    )
    file_utils.mkdir(src_dir, env.controller)
    file_utils.create_file(
        self.params['file_name'], src_dir, env.controller,
        content='seed content',
    )

  def tear_down(self, env: interface.AsyncEnv) -> None:
    super().tear_down(env)
    user_data_generation.clear_device_storage(env)

  def is_successful(self, env: interface.AsyncEnv) -> float:
    super().is_successful(env)
    src_dir = file_utils.convert_to_posix_path(
        device_constants.EMULATOR_DATA, self.params['source_folder']
    )
    new_dir = file_utils.convert_to_posix_path(
        src_dir, self.params['new_folder_name']
    )
    if not file_utils.check_file_or_folder_exists(
        self.params['new_folder_name'], src_dir, env.controller,
    ):
      return 0.0
    # File should no longer sit directly under the source folder.
    if file_utils.check_file_or_folder_exists(
        self.params['file_name'], src_dir, env.controller,
    ):
      return 0.0
    if not file_utils.check_file_or_folder_exists(
        self.params['file_name'], new_dir, env.controller,
    ):
      return 0.0
    return 1.0

  @classmethod
  def generate_random_params(cls) -> dict[str, Any]:
    folder = random.choice(_DIRS)
    candidate = random.choice(
        user_data_generation.EMULATOR_DIRECTORIES[folder]
    )
    new_folder = user_data_generation.generate_random_file_name()
    return {
        'file_name': candidate,
        'source_folder': folder,
        'new_folder_name': new_folder,
    }
