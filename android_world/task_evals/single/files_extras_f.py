"""Tier F -- additional independent Files-app variants."""

import os
import random
from android_world.env import device_constants
from android_world.task_evals import task_eval
from android_world.task_evals.utils import user_data_generation
from android_world.utils import file_utils


class FilesCopyDocToDownload(task_eval.TaskEval):
  """Copy a file from Documents to Download; both locations must end up with it."""

  app_names = ('files',)
  complexity = 2.2
  schema = {
      'type': 'object',
      'properties': {
          'file_name': {'type': 'string'},
      },
      'required': ['file_name'],
  }
  template = (
      'Using the Files app, copy {file_name} from Documents to Download.'
      ' Keep the original in Documents and also place the file in Download.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    user_data_generation.clear_device_storage(env)
    src = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Documents')
    dst = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Download')
    file_utils.mkdir(src, env.controller)
    file_utils.mkdir(dst, env.controller)
    file_utils.create_file(
        self.params['file_name'], src, env.controller,
        content='seed content',
    )

  def tear_down(self, env):
    super().tear_down(env)
    user_data_generation.clear_device_storage(env)

  def is_successful(self, env):
    super().is_successful(env)
    src = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Documents')
    dst = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Download')
    if not file_utils.check_file_or_folder_exists(self.params['file_name'], src, env.controller):
      return 0.0
    if not file_utils.check_file_or_folder_exists(self.params['file_name'], dst, env.controller):
      return 0.0
    return 1.0

  @classmethod
  def generate_random_params(cls):
    candidate = random.choice(user_data_generation.EMULATOR_DIRECTORIES['Documents'])
    return {'file_name': candidate}


class FilesCopyPicToDcim(task_eval.TaskEval):
  """Copy a file from Pictures to DCIM; both locations must end up with it."""

  app_names = ('files',)
  complexity = 2.2
  schema = {
      'type': 'object',
      'properties': {
          'file_name': {'type': 'string'},
      },
      'required': ['file_name'],
  }
  template = (
      'Using the Files app, copy {file_name} from Pictures to DCIM.'
      ' Keep the original in Pictures and also place the file in DCIM.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    user_data_generation.clear_device_storage(env)
    src = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Pictures')
    dst = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'DCIM')
    file_utils.mkdir(src, env.controller)
    file_utils.mkdir(dst, env.controller)
    file_utils.create_file(
        self.params['file_name'], src, env.controller,
        content='seed content',
    )

  def tear_down(self, env):
    super().tear_down(env)
    user_data_generation.clear_device_storage(env)

  def is_successful(self, env):
    super().is_successful(env)
    src = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Pictures')
    dst = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'DCIM')
    if not file_utils.check_file_or_folder_exists(self.params['file_name'], src, env.controller):
      return 0.0
    if not file_utils.check_file_or_folder_exists(self.params['file_name'], dst, env.controller):
      return 0.0
    return 1.0

  @classmethod
  def generate_random_params(cls):
    candidate = random.choice(user_data_generation.EMULATOR_DIRECTORIES['Pictures'])
    return {'file_name': candidate}


class FilesCopyMusicToAlarms(task_eval.TaskEval):
  """Copy a file from Music to Alarms; both locations must end up with it."""

  app_names = ('files',)
  complexity = 2.2
  schema = {
      'type': 'object',
      'properties': {
          'file_name': {'type': 'string'},
      },
      'required': ['file_name'],
  }
  template = (
      'Using the Files app, copy {file_name} from Music to Alarms.'
      ' Keep the original in Music and also place the file in Alarms.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    user_data_generation.clear_device_storage(env)
    src = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Music')
    dst = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Alarms')
    file_utils.mkdir(src, env.controller)
    file_utils.mkdir(dst, env.controller)
    file_utils.create_file(
        self.params['file_name'], src, env.controller,
        content='seed content',
    )

  def tear_down(self, env):
    super().tear_down(env)
    user_data_generation.clear_device_storage(env)

  def is_successful(self, env):
    super().is_successful(env)
    src = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Music')
    dst = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Alarms')
    if not file_utils.check_file_or_folder_exists(self.params['file_name'], src, env.controller):
      return 0.0
    if not file_utils.check_file_or_folder_exists(self.params['file_name'], dst, env.controller):
      return 0.0
    return 1.0

  @classmethod
  def generate_random_params(cls):
    candidate = random.choice(user_data_generation.EMULATOR_DIRECTORIES['Music'])
    return {'file_name': candidate}


class FilesCopyAudioToMusic(task_eval.TaskEval):
  """Copy a file from Audiobooks to Music; both locations must end up with it."""

  app_names = ('files',)
  complexity = 2.2
  schema = {
      'type': 'object',
      'properties': {
          'file_name': {'type': 'string'},
      },
      'required': ['file_name'],
  }
  template = (
      'Using the Files app, copy {file_name} from Audiobooks to Music.'
      ' Keep the original in Audiobooks and also place the file in Music.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    user_data_generation.clear_device_storage(env)
    src = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Audiobooks')
    dst = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Music')
    file_utils.mkdir(src, env.controller)
    file_utils.mkdir(dst, env.controller)
    file_utils.create_file(
        self.params['file_name'], src, env.controller,
        content='seed content',
    )

  def tear_down(self, env):
    super().tear_down(env)
    user_data_generation.clear_device_storage(env)

  def is_successful(self, env):
    super().is_successful(env)
    src = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Audiobooks')
    dst = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Music')
    if not file_utils.check_file_or_folder_exists(self.params['file_name'], src, env.controller):
      return 0.0
    if not file_utils.check_file_or_folder_exists(self.params['file_name'], dst, env.controller):
      return 0.0
    return 1.0

  @classmethod
  def generate_random_params(cls):
    candidate = random.choice(user_data_generation.EMULATOR_DIRECTORIES['Audiobooks'])
    return {'file_name': candidate}


class FilesCopyMovieToDcim(task_eval.TaskEval):
  """Copy a file from Movies to DCIM; both locations must end up with it."""

  app_names = ('files',)
  complexity = 2.2
  schema = {
      'type': 'object',
      'properties': {
          'file_name': {'type': 'string'},
      },
      'required': ['file_name'],
  }
  template = (
      'Using the Files app, copy {file_name} from Movies to DCIM.'
      ' Keep the original in Movies and also place the file in DCIM.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    user_data_generation.clear_device_storage(env)
    src = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Movies')
    dst = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'DCIM')
    file_utils.mkdir(src, env.controller)
    file_utils.mkdir(dst, env.controller)
    file_utils.create_file(
        self.params['file_name'], src, env.controller,
        content='seed content',
    )

  def tear_down(self, env):
    super().tear_down(env)
    user_data_generation.clear_device_storage(env)

  def is_successful(self, env):
    super().is_successful(env)
    src = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Movies')
    dst = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'DCIM')
    if not file_utils.check_file_or_folder_exists(self.params['file_name'], src, env.controller):
      return 0.0
    if not file_utils.check_file_or_folder_exists(self.params['file_name'], dst, env.controller):
      return 0.0
    return 1.0

  @classmethod
  def generate_random_params(cls):
    candidate = random.choice(user_data_generation.EMULATOR_DIRECTORIES['Movies'])
    return {'file_name': candidate}


class FilesRenameInDocuments(task_eval.TaskEval):
  """Rename a file inside the Documents folder."""

  app_names = ('files',)
  complexity = 1.8
  schema = {
      'type': 'object',
      'properties': {
          'original_name': {'type': 'string'},
          'new_name': {'type': 'string'},
      },
      'required': ['original_name', 'new_name'],
  }
  template = (
      'Using the Files app, open the Documents folder and rename'
      ' {original_name} to {new_name}.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    user_data_generation.clear_device_storage(env)
    folder = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Documents')
    file_utils.mkdir(folder, env.controller)
    file_utils.create_file(
        self.params['original_name'], folder, env.controller,
        content='seed content',
    )

  def tear_down(self, env):
    super().tear_down(env)
    user_data_generation.clear_device_storage(env)

  def is_successful(self, env):
    super().is_successful(env)
    folder = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Documents')
    if file_utils.check_file_or_folder_exists(self.params['original_name'], folder, env.controller):
      return 0.0
    if not file_utils.check_file_or_folder_exists(self.params['new_name'], folder, env.controller):
      return 0.0
    return 1.0

  @classmethod
  def generate_random_params(cls):
    candidate = random.choice(user_data_generation.EMULATOR_DIRECTORIES['Documents'])
    base, ext = os.path.splitext(candidate)
    new = user_data_generation.generate_random_file_name() + ext
    return {'original_name': candidate, 'new_name': new}


class FilesRenameInDownload(task_eval.TaskEval):
  """Rename a file inside the Download folder."""

  app_names = ('files',)
  complexity = 1.8
  schema = {
      'type': 'object',
      'properties': {
          'original_name': {'type': 'string'},
          'new_name': {'type': 'string'},
      },
      'required': ['original_name', 'new_name'],
  }
  template = (
      'Using the Files app, open the Download folder and rename'
      ' {original_name} to {new_name}.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    user_data_generation.clear_device_storage(env)
    folder = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Download')
    file_utils.mkdir(folder, env.controller)
    file_utils.create_file(
        self.params['original_name'], folder, env.controller,
        content='seed content',
    )

  def tear_down(self, env):
    super().tear_down(env)
    user_data_generation.clear_device_storage(env)

  def is_successful(self, env):
    super().is_successful(env)
    folder = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Download')
    if file_utils.check_file_or_folder_exists(self.params['original_name'], folder, env.controller):
      return 0.0
    if not file_utils.check_file_or_folder_exists(self.params['new_name'], folder, env.controller):
      return 0.0
    return 1.0

  @classmethod
  def generate_random_params(cls):
    candidate = random.choice(user_data_generation.EMULATOR_DIRECTORIES['Download'])
    base, ext = os.path.splitext(candidate)
    new = user_data_generation.generate_random_file_name() + ext
    return {'original_name': candidate, 'new_name': new}


class FilesRenameInDcim(task_eval.TaskEval):
  """Rename a file inside the DCIM folder."""

  app_names = ('files',)
  complexity = 1.8
  schema = {
      'type': 'object',
      'properties': {
          'original_name': {'type': 'string'},
          'new_name': {'type': 'string'},
      },
      'required': ['original_name', 'new_name'],
  }
  template = (
      'Using the Files app, open the DCIM folder and rename'
      ' {original_name} to {new_name}.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    user_data_generation.clear_device_storage(env)
    folder = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'DCIM')
    file_utils.mkdir(folder, env.controller)
    file_utils.create_file(
        self.params['original_name'], folder, env.controller,
        content='seed content',
    )

  def tear_down(self, env):
    super().tear_down(env)
    user_data_generation.clear_device_storage(env)

  def is_successful(self, env):
    super().is_successful(env)
    folder = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'DCIM')
    if file_utils.check_file_or_folder_exists(self.params['original_name'], folder, env.controller):
      return 0.0
    if not file_utils.check_file_or_folder_exists(self.params['new_name'], folder, env.controller):
      return 0.0
    return 1.0

  @classmethod
  def generate_random_params(cls):
    candidate = random.choice(user_data_generation.EMULATOR_DIRECTORIES['DCIM'])
    base, ext = os.path.splitext(candidate)
    new = user_data_generation.generate_random_file_name() + ext
    return {'original_name': candidate, 'new_name': new}


class FilesRenameInMusic(task_eval.TaskEval):
  """Rename a file inside the Music folder."""

  app_names = ('files',)
  complexity = 1.8
  schema = {
      'type': 'object',
      'properties': {
          'original_name': {'type': 'string'},
          'new_name': {'type': 'string'},
      },
      'required': ['original_name', 'new_name'],
  }
  template = (
      'Using the Files app, open the Music folder and rename'
      ' {original_name} to {new_name}.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    user_data_generation.clear_device_storage(env)
    folder = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Music')
    file_utils.mkdir(folder, env.controller)
    file_utils.create_file(
        self.params['original_name'], folder, env.controller,
        content='seed content',
    )

  def tear_down(self, env):
    super().tear_down(env)
    user_data_generation.clear_device_storage(env)

  def is_successful(self, env):
    super().is_successful(env)
    folder = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Music')
    if file_utils.check_file_or_folder_exists(self.params['original_name'], folder, env.controller):
      return 0.0
    if not file_utils.check_file_or_folder_exists(self.params['new_name'], folder, env.controller):
      return 0.0
    return 1.0

  @classmethod
  def generate_random_params(cls):
    candidate = random.choice(user_data_generation.EMULATOR_DIRECTORIES['Music'])
    base, ext = os.path.splitext(candidate)
    new = user_data_generation.generate_random_file_name() + ext
    return {'original_name': candidate, 'new_name': new}


class FilesCreateProjectsFolder(task_eval.TaskEval):
  """Create a folder named Projects at the top of internal storage."""

  app_names = ('files',)
  complexity = 1.4
  schema = {'type': 'object', 'properties': {}, 'required': []}
  template = (
      'Using the Files app, create a new folder named Projects at the'
      ' top level of internal storage (sdk_gphone_x86_64).'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    user_data_generation.clear_device_storage(env)

  def tear_down(self, env):
    super().tear_down(env)
    user_data_generation.clear_device_storage(env)

  def is_successful(self, env):
    super().is_successful(env)
    ok = file_utils.check_file_or_folder_exists(
        'Projects', device_constants.EMULATOR_DATA, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    return {}


class FilesCreateArchiveFolder(task_eval.TaskEval):
  """Create a folder named Archive at the top of internal storage."""

  app_names = ('files',)
  complexity = 1.4
  schema = {'type': 'object', 'properties': {}, 'required': []}
  template = (
      'Using the Files app, create a new folder named Archive at the'
      ' top level of internal storage (sdk_gphone_x86_64).'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    user_data_generation.clear_device_storage(env)

  def tear_down(self, env):
    super().tear_down(env)
    user_data_generation.clear_device_storage(env)

  def is_successful(self, env):
    super().is_successful(env)
    ok = file_utils.check_file_or_folder_exists(
        'Archive', device_constants.EMULATOR_DATA, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    return {}


class FilesCreate2024Folder(task_eval.TaskEval):
  """Create a folder named 2024_backup at the top of internal storage."""

  app_names = ('files',)
  complexity = 1.4
  schema = {'type': 'object', 'properties': {}, 'required': []}
  template = (
      'Using the Files app, create a new folder named 2024_backup at the'
      ' top level of internal storage (sdk_gphone_x86_64).'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    user_data_generation.clear_device_storage(env)

  def tear_down(self, env):
    super().tear_down(env)
    user_data_generation.clear_device_storage(env)

  def is_successful(self, env):
    super().is_successful(env)
    ok = file_utils.check_file_or_folder_exists(
        '2024_backup', device_constants.EMULATOR_DATA, env.controller,
    )
    return 1.0 if ok else 0.0

  @classmethod
  def generate_random_params(cls):
    return {}


class FilesMoveToNewInMusic(task_eval.TaskEval):
  """Create a sub-folder under Music then move a file from Music into it."""

  app_names = ('files',)
  complexity = 2.4
  schema = {
      'type': 'object',
      'properties': {
          'file_name': {'type': 'string'},
          'new_folder_name': {'type': 'string'},
      },
      'required': ['file_name', 'new_folder_name'],
  }
  template = (
      'Using the Files app, open Music, create a new sub-folder there named'
      ' {new_folder_name}, and move {file_name} from Music into it.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    user_data_generation.clear_device_storage(env)
    src = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Music')
    file_utils.mkdir(src, env.controller)
    file_utils.create_file(
        self.params['file_name'], src, env.controller, content='seed content',
    )

  def tear_down(self, env):
    super().tear_down(env)
    user_data_generation.clear_device_storage(env)

  def is_successful(self, env):
    super().is_successful(env)
    src = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Music')
    new_dir = file_utils.convert_to_posix_path(src, self.params['new_folder_name'])
    if not file_utils.check_file_or_folder_exists(
        self.params['new_folder_name'], src, env.controller,
    ):
      return 0.0
    if file_utils.check_file_or_folder_exists(self.params['file_name'], src, env.controller):
      return 0.0
    if not file_utils.check_file_or_folder_exists(self.params['file_name'], new_dir, env.controller):
      return 0.0
    return 1.0

  @classmethod
  def generate_random_params(cls):
    candidate = random.choice(user_data_generation.EMULATOR_DIRECTORIES['Music'])
    new_folder = user_data_generation.generate_random_file_name()
    return {'file_name': candidate, 'new_folder_name': new_folder}


class FilesMoveToNewInPictures(task_eval.TaskEval):
  """Create a sub-folder under Pictures then move a file from Pictures into it."""

  app_names = ('files',)
  complexity = 2.4
  schema = {
      'type': 'object',
      'properties': {
          'file_name': {'type': 'string'},
          'new_folder_name': {'type': 'string'},
      },
      'required': ['file_name', 'new_folder_name'],
  }
  template = (
      'Using the Files app, open Pictures, create a new sub-folder there named'
      ' {new_folder_name}, and move {file_name} from Pictures into it.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    user_data_generation.clear_device_storage(env)
    src = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Pictures')
    file_utils.mkdir(src, env.controller)
    file_utils.create_file(
        self.params['file_name'], src, env.controller, content='seed content',
    )

  def tear_down(self, env):
    super().tear_down(env)
    user_data_generation.clear_device_storage(env)

  def is_successful(self, env):
    super().is_successful(env)
    src = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Pictures')
    new_dir = file_utils.convert_to_posix_path(src, self.params['new_folder_name'])
    if not file_utils.check_file_or_folder_exists(
        self.params['new_folder_name'], src, env.controller,
    ):
      return 0.0
    if file_utils.check_file_or_folder_exists(self.params['file_name'], src, env.controller):
      return 0.0
    if not file_utils.check_file_or_folder_exists(self.params['file_name'], new_dir, env.controller):
      return 0.0
    return 1.0

  @classmethod
  def generate_random_params(cls):
    candidate = random.choice(user_data_generation.EMULATOR_DIRECTORIES['Pictures'])
    new_folder = user_data_generation.generate_random_file_name()
    return {'file_name': candidate, 'new_folder_name': new_folder}


class FilesMoveToNewInDocuments(task_eval.TaskEval):
  """Create a sub-folder under Documents then move a file from Documents into it."""

  app_names = ('files',)
  complexity = 2.4
  schema = {
      'type': 'object',
      'properties': {
          'file_name': {'type': 'string'},
          'new_folder_name': {'type': 'string'},
      },
      'required': ['file_name', 'new_folder_name'],
  }
  template = (
      'Using the Files app, open Documents, create a new sub-folder there named'
      ' {new_folder_name}, and move {file_name} from Documents into it.'
  )

  def initialize_task(self, env):
    super().initialize_task(env)
    user_data_generation.clear_device_storage(env)
    src = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Documents')
    file_utils.mkdir(src, env.controller)
    file_utils.create_file(
        self.params['file_name'], src, env.controller, content='seed content',
    )

  def tear_down(self, env):
    super().tear_down(env)
    user_data_generation.clear_device_storage(env)

  def is_successful(self, env):
    super().is_successful(env)
    src = file_utils.convert_to_posix_path(device_constants.EMULATOR_DATA, 'Documents')
    new_dir = file_utils.convert_to_posix_path(src, self.params['new_folder_name'])
    if not file_utils.check_file_or_folder_exists(
        self.params['new_folder_name'], src, env.controller,
    ):
      return 0.0
    if file_utils.check_file_or_folder_exists(self.params['file_name'], src, env.controller):
      return 0.0
    if not file_utils.check_file_or_folder_exists(self.params['file_name'], new_dir, env.controller):
      return 0.0
    return 1.0

  @classmethod
  def generate_random_params(cls):
    candidate = random.choice(user_data_generation.EMULATOR_DIRECTORIES['Documents'])
    new_folder = user_data_generation.generate_random_file_name()
    return {'file_name': candidate, 'new_folder_name': new_folder}
