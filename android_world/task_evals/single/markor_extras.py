# Copyright 2025 The android_world Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tier B Markor tasks: text-manipulation tasks on a single seed note.

Each task seeds MARKOR_DATA with one .md file of known content, asks the
agent to perform a small text edit through Markor's UI, then verifies the
resulting file content with `file_utils.check_file_content`. The data
directory is cleared by the parent `Markor.initialize_task` so noise from
prior tasks does not interfere.
"""

import random
from typing import Any

from android_world.env import device_constants
from android_world.env import interface
from android_world.task_evals.single.markor import (
    Markor,
    _generate_random_note,
    generate_random_sentence,
)
from android_world.task_evals.utils import user_data_generation
from android_world.utils import file_utils


_NOTE_EXTENSIONS = ('.md', '.txt')


def _random_note_name() -> str:
  return (
      user_data_generation.generate_random_file_name()
      + random.choice(_NOTE_EXTENSIONS)
  )


# =============================================================================
# 1. MarkorRenameNote
# =============================================================================
class MarkorRenameNote(Markor):
  """Rename an existing note. Content must stay identical."""

  complexity = 1.2
  schema = {
      'type': 'object',
      'properties': {
          'original_name': {'type': 'string'},
          'new_name': {'type': 'string'},
          'content': {'type': 'string'},
      },
      'required': ['original_name', 'new_name', 'content'],
  }
  template = (
      'Open Markor, rename the note {original_name} to {new_name}.'
      ' Do not change its text content.'
  )

  def initialize_task(self, env: interface.AsyncEnv) -> None:
    super().initialize_task(env)
    file_utils.create_file(
        self.params['original_name'],
        device_constants.MARKOR_DATA,
        env.controller,
        content=self.params['content'],
    )

  def is_successful(self, env: interface.AsyncEnv) -> float:
    super().is_successful(env)
    if file_utils.check_file_or_folder_exists(
        self.params['original_name'], device_constants.MARKOR_DATA,
        env.controller,
    ):
      return 0.0
    if not file_utils.check_file_or_folder_exists(
        self.params['new_name'], device_constants.MARKOR_DATA,
        env.controller,
    ):
      return 0.0
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['new_name']
        ),
        self.params['content'],
        env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls) -> dict[str, Any]:
    return {
        'original_name': _random_note_name(),
        'new_name': _random_note_name(),
        'content': generate_random_sentence(),
    }


# =============================================================================
# 2. MarkorAppendLine
# =============================================================================
class MarkorAppendLine(Markor):
  """Append a specific line to the end of an existing note."""

  complexity = 1.1
  schema = {
      'type': 'object',
      'properties': {
          'file_name': {'type': 'string'},
          'original_content': {'type': 'string'},
          'line_to_append': {'type': 'string'},
      },
      'required': ['file_name', 'original_content', 'line_to_append'],
  }
  template = (
      'Open the Markor note {file_name} and append the line'
      ' "{line_to_append}" to the end of the file. Save the note.'
  )

  def initialize_task(self, env: interface.AsyncEnv) -> None:
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'],
        device_constants.MARKOR_DATA,
        env.controller,
        content=self.params['original_content'],
    )

  def is_successful(self, env: interface.AsyncEnv) -> float:
    super().is_successful(env)
    expected = (
        self.params['original_content'].rstrip('\n')
        + '\n'
        + self.params['line_to_append']
    )
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected,
        env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls) -> dict[str, Any]:
    return {
        'file_name': _random_note_name(),
        'original_content': generate_random_sentence(),
        'line_to_append': generate_random_sentence(),
    }


# =============================================================================
# 3. MarkorPrependLine
# =============================================================================
class MarkorPrependLine(Markor):
  """Prepend a specific line to the top of an existing note."""

  complexity = 1.1
  schema = {
      'type': 'object',
      'properties': {
          'file_name': {'type': 'string'},
          'original_content': {'type': 'string'},
          'line_to_prepend': {'type': 'string'},
      },
      'required': ['file_name', 'original_content', 'line_to_prepend'],
  }
  template = (
      'Open the Markor note {file_name} and add the line'
      ' "{line_to_prepend}" as a new first line at the top.'
      ' Save the note.'
  )

  def initialize_task(self, env: interface.AsyncEnv) -> None:
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'],
        device_constants.MARKOR_DATA,
        env.controller,
        content=self.params['original_content'],
    )

  def is_successful(self, env: interface.AsyncEnv) -> float:
    super().is_successful(env)
    expected = (
        self.params['line_to_prepend']
        + '\n'
        + self.params['original_content']
    )
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected,
        env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls) -> dict[str, Any]:
    return {
        'file_name': _random_note_name(),
        'original_content': generate_random_sentence(),
        'line_to_prepend': generate_random_sentence(),
    }


# =============================================================================
# 4. MarkorReplaceWord
# =============================================================================
class MarkorReplaceWord(Markor):
  """Replace one specific word with another in an existing note."""

  _WORD_PAIRS = (
      ('quick', 'slow'),
      ('happy', 'glad'),
      ('big', 'large'),
      ('small', 'tiny'),
      ('start', 'begin'),
      ('end', 'finish'),
      ('open', 'launch'),
      ('close', 'shut'),
  )

  complexity = 1.3
  schema = {
      'type': 'object',
      'properties': {
          'file_name': {'type': 'string'},
          'old_word': {'type': 'string'},
          'new_word': {'type': 'string'},
          'original_content': {'type': 'string'},
      },
      'required': ['file_name', 'old_word', 'new_word', 'original_content'],
  }
  template = (
      'Open the Markor note {file_name}. Replace every occurrence of the'
      ' word "{old_word}" with "{new_word}" and save the note.'
  )

  def initialize_task(self, env: interface.AsyncEnv) -> None:
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'],
        device_constants.MARKOR_DATA,
        env.controller,
        content=self.params['original_content'],
    )

  def is_successful(self, env: interface.AsyncEnv) -> float:
    super().is_successful(env)
    expected = self.params['original_content'].replace(
        self.params['old_word'], self.params['new_word']
    )
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected,
        env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls) -> dict[str, Any]:
    old_word, new_word = random.choice(cls._WORD_PAIRS)
    # Make sure the seed note actually contains old_word so the replacement
    # is observable; if generate_random_sentence misses it we wrap a sample.
    base = generate_random_sentence()
    if old_word not in base.lower():
      base = f'The {old_word} fox is here. {base}'
    return {
        'file_name': _random_note_name(),
        'old_word': old_word,
        'new_word': new_word,
        'original_content': base,
    }


# =============================================================================
# 5. MarkorWrapInBrackets
# =============================================================================
class MarkorWrapInBrackets(Markor):
  """Wrap an existing note's body in square brackets."""

  complexity = 1.1
  schema = {
      'type': 'object',
      'properties': {
          'file_name': {'type': 'string'},
          'original_content': {'type': 'string'},
      },
      'required': ['file_name', 'original_content'],
  }
  template = (
      'Open the Markor note {file_name}. Wrap the entire note content in'
      ' square brackets so it reads [original content]. Save the note.'
  )

  def initialize_task(self, env: interface.AsyncEnv) -> None:
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'],
        device_constants.MARKOR_DATA,
        env.controller,
        content=self.params['original_content'],
    )

  def is_successful(self, env: interface.AsyncEnv) -> float:
    super().is_successful(env)
    expected = '[' + self.params['original_content'].strip() + ']'
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected,
        env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls) -> dict[str, Any]:
    return {
        'file_name': _random_note_name(),
        'original_content': generate_random_sentence(),
    }


# =============================================================================
# 6. MarkorAddTimestamp
# =============================================================================
class MarkorAddTimestamp(Markor):
  """Append a specific timestamp line to the end of an existing note."""

  _DATES = (
      '2025-05-13', '2025-06-20', '2025-07-04', '2025-08-15',
      '2025-09-30', '2025-10-31', '2025-11-22', '2025-12-25',
  )

  complexity = 1.1
  schema = {
      'type': 'object',
      'properties': {
          'file_name': {'type': 'string'},
          'original_content': {'type': 'string'},
          'timestamp': {'type': 'string'},
      },
      'required': ['file_name', 'original_content', 'timestamp'],
  }
  template = (
      'Open the Markor note {file_name} and append the timestamp'
      ' "Date: {timestamp}" as a new last line. Save the note.'
  )

  def initialize_task(self, env: interface.AsyncEnv) -> None:
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'],
        device_constants.MARKOR_DATA,
        env.controller,
        content=self.params['original_content'],
    )

  def is_successful(self, env: interface.AsyncEnv) -> float:
    super().is_successful(env)
    expected = (
        self.params['original_content'].rstrip('\n')
        + '\nDate: '
        + self.params['timestamp']
    )
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected,
        env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls) -> dict[str, Any]:
    return {
        'file_name': _random_note_name(),
        'original_content': generate_random_sentence(),
        'timestamp': random.choice(cls._DATES),
    }


# =============================================================================
# 7. MarkorRemoveLastLine
# =============================================================================
class MarkorRemoveLastLine(Markor):
  """Delete the final line of a multi-line note. Keep the rest."""

  complexity = 1.2
  schema = {
      'type': 'object',
      'properties': {
          'file_name': {'type': 'string'},
          'line1': {'type': 'string'},
          'line2': {'type': 'string'},
          'line3': {'type': 'string'},
      },
      'required': ['file_name', 'line1', 'line2', 'line3'],
  }
  template = (
      'Open the Markor note {file_name}, which contains three lines.'
      ' Delete the last line so only the first two lines remain.'
      ' Save the note.'
  )

  def initialize_task(self, env: interface.AsyncEnv) -> None:
    super().initialize_task(env)
    body = '\n'.join([
        self.params['line1'], self.params['line2'], self.params['line3'],
    ])
    file_utils.create_file(
        self.params['file_name'],
        device_constants.MARKOR_DATA,
        env.controller,
        content=body,
    )

  def is_successful(self, env: interface.AsyncEnv) -> float:
    super().is_successful(env)
    expected = self.params['line1'] + '\n' + self.params['line2']
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected,
        env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls) -> dict[str, Any]:
    return {
        'file_name': _random_note_name(),
        'line1': generate_random_sentence(),
        'line2': generate_random_sentence(),
        'line3': generate_random_sentence(),
    }


# =============================================================================
# 8. MarkorInsertMiddleLine
# =============================================================================
class MarkorInsertMiddleLine(Markor):
  """Insert a new line between two existing lines of a two-line note."""

  complexity = 1.3
  schema = {
      'type': 'object',
      'properties': {
          'file_name': {'type': 'string'},
          'line1': {'type': 'string'},
          'line2': {'type': 'string'},
          'middle_line': {'type': 'string'},
      },
      'required': ['file_name', 'line1', 'line2', 'middle_line'],
  }
  template = (
      'Open the Markor note {file_name}, which contains two lines.'
      ' Insert the line "{middle_line}" between them so the file ends up'
      ' with three lines in order. Save the note.'
  )

  def initialize_task(self, env: interface.AsyncEnv) -> None:
    super().initialize_task(env)
    body = self.params['line1'] + '\n' + self.params['line2']
    file_utils.create_file(
        self.params['file_name'],
        device_constants.MARKOR_DATA,
        env.controller,
        content=body,
    )

  def is_successful(self, env: interface.AsyncEnv) -> float:
    super().is_successful(env)
    expected = '\n'.join([
        self.params['line1'],
        self.params['middle_line'],
        self.params['line2'],
    ])
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected,
        env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls) -> dict[str, Any]:
    return {
        'file_name': _random_note_name(),
        'line1': generate_random_sentence(),
        'line2': generate_random_sentence(),
        'middle_line': generate_random_sentence(),
    }
