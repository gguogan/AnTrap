"""Tier F -- additional Markor text-manipulation variants."""

from android_world.env import device_constants
from android_world.task_evals.single.markor import Markor, generate_random_sentence
from android_world.task_evals.single.markor_extras import _random_note_name
from android_world.utils import file_utils


class MarkorWrapInParens(Markor):
  """Wrap note content in parentheses."""

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
      ' parentheses so it reads `(`original content`(`. Save the note.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'], device_constants.MARKOR_DATA,
        env.controller, content=self.params['original_content'],
    )

  def is_successful(self, env):
    super().is_successful(env)
    expected = '(' + self.params['original_content'].strip() + ')'
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    return {
        'file_name': _random_note_name(),
        'original_content': generate_random_sentence(),
    }


class MarkorWrapInAngles(Markor):
  """Wrap note content in angle brackets."""

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
      ' angle brackets so it reads `<`original content`<`. Save the note.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'], device_constants.MARKOR_DATA,
        env.controller, content=self.params['original_content'],
    )

  def is_successful(self, env):
    super().is_successful(env)
    expected = '<' + self.params['original_content'].strip() + '>'
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    return {
        'file_name': _random_note_name(),
        'original_content': generate_random_sentence(),
    }


class MarkorWrapInDoubleQ(Markor):
  """Wrap note content in double quotes."""

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
      ' double quotes so it reads `"`original content`"`. Save the note.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'], device_constants.MARKOR_DATA,
        env.controller, content=self.params['original_content'],
    )

  def is_successful(self, env):
    super().is_successful(env)
    expected = '"' + self.params['original_content'].strip() + '"'
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    return {
        'file_name': _random_note_name(),
        'original_content': generate_random_sentence(),
    }


class MarkorWrapInBackticks(Markor):
  """Wrap note content in backticks."""

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
      ' backticks so it reads ```original content```. Save the note.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'], device_constants.MARKOR_DATA,
        env.controller, content=self.params['original_content'],
    )

  def is_successful(self, env):
    super().is_successful(env)
    expected = '`' + self.params['original_content'].strip() + '`'
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    return {
        'file_name': _random_note_name(),
        'original_content': generate_random_sentence(),
    }


class MarkorWrapInStars(Markor):
  """Wrap note content in single asterisks."""

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
      ' single asterisks so it reads `*`original content`*`. Save the note.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'], device_constants.MARKOR_DATA,
        env.controller, content=self.params['original_content'],
    )

  def is_successful(self, env):
    super().is_successful(env)
    expected = '*' + self.params['original_content'].strip() + '*'
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    return {
        'file_name': _random_note_name(),
        'original_content': generate_random_sentence(),
    }


class MarkorWrapInDoubleStars(Markor):
  """Wrap note content in double asterisks."""

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
      ' double asterisks so it reads `**`original content`**`. Save the note.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'], device_constants.MARKOR_DATA,
        env.controller, content=self.params['original_content'],
    )

  def is_successful(self, env):
    super().is_successful(env)
    expected = '**' + self.params['original_content'].strip() + '**'
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    return {
        'file_name': _random_note_name(),
        'original_content': generate_random_sentence(),
    }


class MarkorWrapInUnderscores(Markor):
  """Wrap note content in underscores."""

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
      ' underscores so it reads `_`original content`_`. Save the note.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'], device_constants.MARKOR_DATA,
        env.controller, content=self.params['original_content'],
    )

  def is_successful(self, env):
    super().is_successful(env)
    expected = '_' + self.params['original_content'].strip() + '_'
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    return {
        'file_name': _random_note_name(),
        'original_content': generate_random_sentence(),
    }


class MarkorWrapInHash(Markor):
  """Wrap note content in hash characters."""

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
      ' hash characters so it reads `#`original content`#`. Save the note.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'], device_constants.MARKOR_DATA,
        env.controller, content=self.params['original_content'],
    )

  def is_successful(self, env):
    super().is_successful(env)
    expected = '#' + self.params['original_content'].strip() + '#'
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    return {
        'file_name': _random_note_name(),
        'original_content': generate_random_sentence(),
    }


class MarkorWrapInTildes(Markor):
  """Wrap note content in tildes."""

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
      ' tildes so it reads `~`original content`~`. Save the note.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'], device_constants.MARKOR_DATA,
        env.controller, content=self.params['original_content'],
    )

  def is_successful(self, env):
    super().is_successful(env)
    expected = '~' + self.params['original_content'].strip() + '~'
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    return {
        'file_name': _random_note_name(),
        'original_content': generate_random_sentence(),
    }


class MarkorWrapInPipes(Markor):
  """Wrap note content in pipes."""

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
      ' pipes so it reads `|`original content`|`. Save the note.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'], device_constants.MARKOR_DATA,
        env.controller, content=self.params['original_content'],
    )

  def is_successful(self, env):
    super().is_successful(env)
    expected = '|' + self.params['original_content'].strip() + '|'
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    return {
        'file_name': _random_note_name(),
        'original_content': generate_random_sentence(),
    }


class MarkorReplaceHotCold(Markor):
  """Replace every "hot" with "cold" in the note."""

  complexity = 1.3
  schema = {
      'type': 'object',
      'properties': {
          'file_name': {'type': 'string'},
          'original_content': {'type': 'string'},
      },
      'required': ['file_name', 'original_content'],
  }
  template = (
      'Open the Markor note {file_name}. Replace every occurrence of the'
      ' word "hot" with "cold" and save the note.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'], device_constants.MARKOR_DATA,
        env.controller, content=self.params['original_content'],
    )

  def is_successful(self, env):
    super().is_successful(env)
    expected = self.params['original_content'].replace('hot', 'cold')
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    base = generate_random_sentence()
    if 'hot' not in base.lower():
      base = 'The hot thing is here. ' + base
    return {
        'file_name': _random_note_name(),
        'original_content': base,
    }


class MarkorReplaceLightDark(Markor):
  """Replace every "light" with "dark" in the note."""

  complexity = 1.3
  schema = {
      'type': 'object',
      'properties': {
          'file_name': {'type': 'string'},
          'original_content': {'type': 'string'},
      },
      'required': ['file_name', 'original_content'],
  }
  template = (
      'Open the Markor note {file_name}. Replace every occurrence of the'
      ' word "light" with "dark" and save the note.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'], device_constants.MARKOR_DATA,
        env.controller, content=self.params['original_content'],
    )

  def is_successful(self, env):
    super().is_successful(env)
    expected = self.params['original_content'].replace('light', 'dark')
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    base = generate_random_sentence()
    if 'light' not in base.lower():
      base = 'The light thing is here. ' + base
    return {
        'file_name': _random_note_name(),
        'original_content': base,
    }


class MarkorReplaceNorthSouth(Markor):
  """Replace every "north" with "south" in the note."""

  complexity = 1.3
  schema = {
      'type': 'object',
      'properties': {
          'file_name': {'type': 'string'},
          'original_content': {'type': 'string'},
      },
      'required': ['file_name', 'original_content'],
  }
  template = (
      'Open the Markor note {file_name}. Replace every occurrence of the'
      ' word "north" with "south" and save the note.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'], device_constants.MARKOR_DATA,
        env.controller, content=self.params['original_content'],
    )

  def is_successful(self, env):
    super().is_successful(env)
    expected = self.params['original_content'].replace('north', 'south')
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    base = generate_random_sentence()
    if 'north' not in base.lower():
      base = 'The north thing is here. ' + base
    return {
        'file_name': _random_note_name(),
        'original_content': base,
    }


class MarkorReplaceWinSummer(Markor):
  """Replace every "winter" with "summer" in the note."""

  complexity = 1.3
  schema = {
      'type': 'object',
      'properties': {
          'file_name': {'type': 'string'},
          'original_content': {'type': 'string'},
      },
      'required': ['file_name', 'original_content'],
  }
  template = (
      'Open the Markor note {file_name}. Replace every occurrence of the'
      ' word "winter" with "summer" and save the note.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'], device_constants.MARKOR_DATA,
        env.controller, content=self.params['original_content'],
    )

  def is_successful(self, env):
    super().is_successful(env)
    expected = self.params['original_content'].replace('winter', 'summer')
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    base = generate_random_sentence()
    if 'winter' not in base.lower():
      base = 'The winter thing is here. ' + base
    return {
        'file_name': _random_note_name(),
        'original_content': base,
    }


class MarkorReplaceUpDown(Markor):
  """Replace every "up" with "down" in the note."""

  complexity = 1.3
  schema = {
      'type': 'object',
      'properties': {
          'file_name': {'type': 'string'},
          'original_content': {'type': 'string'},
      },
      'required': ['file_name', 'original_content'],
  }
  template = (
      'Open the Markor note {file_name}. Replace every occurrence of the'
      ' word "up" with "down" and save the note.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'], device_constants.MARKOR_DATA,
        env.controller, content=self.params['original_content'],
    )

  def is_successful(self, env):
    super().is_successful(env)
    expected = self.params['original_content'].replace('up', 'down')
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    base = generate_random_sentence()
    if 'up' not in base.lower():
      base = 'The up thing is here. ' + base
    return {
        'file_name': _random_note_name(),
        'original_content': base,
    }


class MarkorReplaceLeftRight(Markor):
  """Replace every "left" with "right" in the note."""

  complexity = 1.3
  schema = {
      'type': 'object',
      'properties': {
          'file_name': {'type': 'string'},
          'original_content': {'type': 'string'},
      },
      'required': ['file_name', 'original_content'],
  }
  template = (
      'Open the Markor note {file_name}. Replace every occurrence of the'
      ' word "left" with "right" and save the note.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'], device_constants.MARKOR_DATA,
        env.controller, content=self.params['original_content'],
    )

  def is_successful(self, env):
    super().is_successful(env)
    expected = self.params['original_content'].replace('left', 'right')
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    base = generate_random_sentence()
    if 'left' not in base.lower():
      base = 'The left thing is here. ' + base
    return {
        'file_name': _random_note_name(),
        'original_content': base,
    }


class MarkorReplaceCatDog(Markor):
  """Replace every "cat" with "dog" in the note."""

  complexity = 1.3
  schema = {
      'type': 'object',
      'properties': {
          'file_name': {'type': 'string'},
          'original_content': {'type': 'string'},
      },
      'required': ['file_name', 'original_content'],
  }
  template = (
      'Open the Markor note {file_name}. Replace every occurrence of the'
      ' word "cat" with "dog" and save the note.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'], device_constants.MARKOR_DATA,
        env.controller, content=self.params['original_content'],
    )

  def is_successful(self, env):
    super().is_successful(env)
    expected = self.params['original_content'].replace('cat', 'dog')
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    base = generate_random_sentence()
    if 'cat' not in base.lower():
      base = 'The cat thing is here. ' + base
    return {
        'file_name': _random_note_name(),
        'original_content': base,
    }


class MarkorReplaceBlackWhite(Markor):
  """Replace every "black" with "white" in the note."""

  complexity = 1.3
  schema = {
      'type': 'object',
      'properties': {
          'file_name': {'type': 'string'},
          'original_content': {'type': 'string'},
      },
      'required': ['file_name', 'original_content'],
  }
  template = (
      'Open the Markor note {file_name}. Replace every occurrence of the'
      ' word "black" with "white" and save the note.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'], device_constants.MARKOR_DATA,
        env.controller, content=self.params['original_content'],
    )

  def is_successful(self, env):
    super().is_successful(env)
    expected = self.params['original_content'].replace('black', 'white')
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    base = generate_random_sentence()
    if 'black' not in base.lower():
      base = 'The black thing is here. ' + base
    return {
        'file_name': _random_note_name(),
        'original_content': base,
    }


class MarkorReplaceMonTue(Markor):
  """Replace every "monday" with "tuesday" in the note."""

  complexity = 1.3
  schema = {
      'type': 'object',
      'properties': {
          'file_name': {'type': 'string'},
          'original_content': {'type': 'string'},
      },
      'required': ['file_name', 'original_content'],
  }
  template = (
      'Open the Markor note {file_name}. Replace every occurrence of the'
      ' word "monday" with "tuesday" and save the note.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'], device_constants.MARKOR_DATA,
        env.controller, content=self.params['original_content'],
    )

  def is_successful(self, env):
    super().is_successful(env)
    expected = self.params['original_content'].replace('monday', 'tuesday')
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    base = generate_random_sentence()
    if 'monday' not in base.lower():
      base = 'The monday thing is here. ' + base
    return {
        'file_name': _random_note_name(),
        'original_content': base,
    }


class MarkorReplaceYesNo(Markor):
  """Replace every "yes" with "no" in the note."""

  complexity = 1.3
  schema = {
      'type': 'object',
      'properties': {
          'file_name': {'type': 'string'},
          'original_content': {'type': 'string'},
      },
      'required': ['file_name', 'original_content'],
  }
  template = (
      'Open the Markor note {file_name}. Replace every occurrence of the'
      ' word "yes" with "no" and save the note.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'], device_constants.MARKOR_DATA,
        env.controller, content=self.params['original_content'],
    )

  def is_successful(self, env):
    super().is_successful(env)
    expected = self.params['original_content'].replace('yes', 'no')
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    base = generate_random_sentence()
    if 'yes' not in base.lower():
      base = 'The yes thing is here. ' + base
    return {
        'file_name': _random_note_name(),
        'original_content': base,
    }


class MarkorPrependTodoHeader(Markor):
  """Prepend "# TODO" as a new first line."""

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
      'Open the Markor note {file_name}. Add the line "# TODO" as a new first'
      ' line at the top of the note. Save the note.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'], device_constants.MARKOR_DATA,
        env.controller, content=self.params['original_content'],
    )

  def is_successful(self, env):
    super().is_successful(env)
    expected = '# TODO' + "\n" + self.params['original_content']
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    return {
        'file_name': _random_note_name(),
        'original_content': generate_random_sentence(),
    }


class MarkorPrependDoneHeader(Markor):
  """Prepend "# DONE" as a new first line."""

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
      'Open the Markor note {file_name}. Add the line "# DONE" as a new first'
      ' line at the top of the note. Save the note.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'], device_constants.MARKOR_DATA,
        env.controller, content=self.params['original_content'],
    )

  def is_successful(self, env):
    super().is_successful(env)
    expected = '# DONE' + "\n" + self.params['original_content']
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    return {
        'file_name': _random_note_name(),
        'original_content': generate_random_sentence(),
    }


class MarkorPrependDraftTag(Markor):
  """Prepend "DRAFT" as a new first line."""

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
      'Open the Markor note {file_name}. Add the line "DRAFT" as a new first'
      ' line at the top of the note. Save the note.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'], device_constants.MARKOR_DATA,
        env.controller, content=self.params['original_content'],
    )

  def is_successful(self, env):
    super().is_successful(env)
    expected = 'DRAFT' + "\n" + self.params['original_content']
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    return {
        'file_name': _random_note_name(),
        'original_content': generate_random_sentence(),
    }


class MarkorPrependAuthorLine(Markor):
  """Prepend "Author: anonymous" as a new first line."""

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
      'Open the Markor note {file_name}. Add the line "Author: anonymous" as a new first'
      ' line at the top of the note. Save the note.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'], device_constants.MARKOR_DATA,
        env.controller, content=self.params['original_content'],
    )

  def is_successful(self, env):
    super().is_successful(env)
    expected = 'Author: anonymous' + "\n" + self.params['original_content']
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    return {
        'file_name': _random_note_name(),
        'original_content': generate_random_sentence(),
    }


class MarkorPrependDivider(Markor):
  """Prepend "---" (a Markdown horizontal rule) as a new first line."""

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
      'Open the Markor note {file_name}. Add the line "---" (a Markdown horizontal rule) as a new first'
      ' line at the top of the note. Save the note.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    file_utils.create_file(
        self.params['file_name'], device_constants.MARKOR_DATA,
        env.controller, content=self.params['original_content'],
    )

  def is_successful(self, env):
    super().is_successful(env)
    expected = '---' + "\n" + self.params['original_content']
    ok = file_utils.check_file_content(
        file_utils.convert_to_posix_path(
            device_constants.MARKOR_DATA, self.params['file_name']
        ),
        expected, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    return {
        'file_name': _random_note_name(),
        'original_content': generate_random_sentence(),
    }
