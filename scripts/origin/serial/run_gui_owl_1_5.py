import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# Copyright 2025 The android_world Authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Run eval suite for GUI-Owl-1.5-8B-Instruct agent."""

from collections.abc import Sequence
import os

from absl import app
from absl import flags
from absl import logging
from android_world import checkpointer as checkpointer_lib
from android_world import registry
from android_world import suite_utils
from android_world.agents import infer_ma3
from android_world.agents import gui_owl_1_5
from android_world.env import env_launcher

logging.set_verbosity(logging.WARNING)

os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GRPC_TRACE'] = 'none'


def _find_adb_directory() -> str:
    """Returns the directory where adb is located."""
    potential_paths = [
        os.path.expanduser('~/Library/Android/sdk/platform-tools/adb'),
        os.path.expanduser('~/Android/Sdk/platform-tools/adb'),
        '/root/android/android_sdk/platform-tools/adb',
        '/app/.android/platform-tools/adb',
    ]
    for path in potential_paths:
        if os.path.isfile(path):
            return path
    raise EnvironmentError(
        'adb not found in the common Android SDK paths. Please install Android'
        " SDK and ensure adb is in one of the expected directories. If it's"
        ' already installed, point to the installed location.'
    )


_ADB_PATH = flags.DEFINE_string(
    'adb_path',
    _find_adb_directory(),
    'Path to adb. Set if not installed through SDK.',
)
_EMULATOR_SETUP = flags.DEFINE_boolean(
    'perform_emulator_setup',
    False,
    'Whether to perform emulator setup. This must be done once and only once'
    ' before running Android World.',
)
_DEVICE_CONSOLE_PORT = flags.DEFINE_integer(
    'console_port',
    5554,
    'The console port of the running Android device.',
)
_GRPC_PORT = flags.DEFINE_integer(
    'grpc_port',
    8554,
    'grpc_port',
)
_MODEL = flags.DEFINE_string(
    'model',
    'GUI-Owl-1.5-8B-Instruct',
    'Model name served by vllm.',
)
_SUITE_FAMILY = flags.DEFINE_enum(
    'suite_family',
    registry.TaskRegistry.ANDROID_WORLD_FAMILY,
    [
        registry.TaskRegistry.ANDROID_WORLD_FAMILY,
        registry.TaskRegistry.MINIWOB_FAMILY_SUBSET,
        registry.TaskRegistry.MINIWOB_FAMILY,
        registry.TaskRegistry.ANDROID_FAMILY,
        registry.TaskRegistry.INFORMATION_RETRIEVAL_FAMILY,
    ],
    'Suite family to run.',
)
_TASK_RANDOM_SEED = flags.DEFINE_integer(
    'task_random_seed', 30, 'Random seed for task randomness.'
)
_TASKS = flags.DEFINE_list(
    'tasks',
    None,
    'List of specific tasks to run. If None, run all tasks in the suite family.',
)
_N_TASK_COMBINATIONS = flags.DEFINE_integer(
    'n_task_combinations',
    1,
    'Number of task instances to run for each task template.',
)
_CHECKPOINT_DIR = flags.DEFINE_string(
    'checkpoint_dir',
    '',
    'Directory to save/resume checkpoints.',
)
_OUTPUT_PATH = flags.DEFINE_string(
    'output_path',
    os.path.expanduser('~/android_world/runs'),
    'Path to save results.',
)
_TRAJ_OUTPUT_PATH = flags.DEFINE_string(
    'traj_output_path',
    '',
    'Path to save trajectory screenshots and action logs.',
)
_API_KEY = flags.DEFINE_string(
    'api_key',
    'EMPTY',
    'API key for the vllm server (use EMPTY for local servers).',
)
_BASE_URL = flags.DEFINE_string(
    'base_url',
    'http://localhost:8000/v1',
    'Base URL of the vllm OpenAI-compatible server.',
)
_FIXED_TASK_SEED = flags.DEFINE_boolean(
    'fixed_task_seed',
    False,
    'Whether to use the same task seed for multiple combinations.',
)
_MAX_HISTORY_IMAGES = flags.DEFINE_integer(
    'max_history_images',
    5,
    'Maximum number of past screenshots to include in the prompt.',
)

_MINIWOB_TRANSITION_PAUSE = 0.2
_MINIWOB_ADDITIONAL_GUIDELINES = [
    (
        'This task is running in a mock app, you must stay in this app and'
        ' DO NOT use the `navigate_home` action.'
    ),
]


def _main() -> None:
    """Runs eval suite and gets rewards back."""
    env = env_launcher.load_and_setup_env(
        console_port=_DEVICE_CONSOLE_PORT.value,
        emulator_setup=_EMULATOR_SETUP.value,
        adb_path=_ADB_PATH.value,
        grpc_port=_GRPC_PORT.value,
    )

    n_task_combinations = _N_TASK_COMBINATIONS.value
    print("n_task_combinations:", n_task_combinations)

    task_registry = registry.TaskRegistry()
    suite = suite_utils.create_suite(
        task_registry.get_registry(family=_SUITE_FAMILY.value),
        n_task_combinations=n_task_combinations,
        seed=_TASK_RANDOM_SEED.value,
        tasks=_TASKS.value,
        use_identical_params=_FIXED_TASK_SEED.value,
    )
    suite.suite_family = _SUITE_FAMILY.value

    print('Initializing GUI-Owl-1.5 agent...')
    vllm_wrapper = infer_ma3.GUIOwlWrapper(
        _API_KEY.value,
        _BASE_URL.value,
        _MODEL.value,
    )
    agent = gui_owl_1_5.GUIOwl15Agent(
        env=env,
        vllm=vllm_wrapper,
        name='GUIOwl15',
        max_history_images=_MAX_HISTORY_IMAGES.value,
        output_path=_TRAJ_OUTPUT_PATH.value,
        api_key=_API_KEY.value,
        url=_BASE_URL.value,
    )
    agent.get_task_name(suite)
    print("Agent:", agent)

    if _SUITE_FAMILY.value.startswith('miniwob'):
        agent.transition_pause = _MINIWOB_TRANSITION_PAUSE
    else:
        agent.transition_pause = None

    if _CHECKPOINT_DIR.value:
        checkpoint_dir = _CHECKPOINT_DIR.value
    else:
        checkpoint_dir = checkpointer_lib.create_run_directory(_OUTPUT_PATH.value)

    print(f'Starting eval with GUI-Owl-1.5 agent, writing to {checkpoint_dir}')
    suite_utils.run(
        suite,
        agent,
        checkpointer=checkpointer_lib.IncrementalCheckpointer(checkpoint_dir),
        demo_mode=False,
    )
    print(f'Finished. Results written to {checkpoint_dir}.')
    env.close()


def main(argv: Sequence[str]) -> None:
    del argv
    _main()


if __name__ == '__main__':
    app.run(main)
