import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

"""Parallel eval suite runner for Gemini 3 Pro Preview (M3A action space)."""

# Auto-load API keys from <repo>/.env before anything else reads os.environ.
from scripts.env_utils import load_env
load_env()

from collections.abc import Sequence
import io
import queue
import threading
import time
import traceback

from absl import app
from absl import flags
from absl import logging as absl_logging
from android_world import checkpointer as checkpointer_lib
from android_world import constants
from android_world import episode_runner
from android_world import registry
from android_world import suite_utils
from android_world.agents import gemini3
from android_world.agents import infer_gemini3
from android_world.env import env_launcher
from scripts.emulator_failover import SpareEmulatorPool, check_emulator_alive

absl_logging.set_verbosity(absl_logging.WARNING)

os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GRPC_TRACE'] = 'none'


# ---------------------------------------------------------------------------
class _CapturingStream:
    def __init__(self, real_stream):
        self._real = real_stream
        self._buffers = {}
        self._lock = threading.Lock()

    def start_capture(self):
        with self._lock:
            self._buffers[threading.get_ident()] = io.StringIO()

    def stop_capture(self):
        with self._lock:
            buf = self._buffers.pop(threading.get_ident(), None)
            return buf.getvalue() if buf else ''

    def write(self, text):
        tid = threading.get_ident()
        with self._lock:
            if tid in self._buffers:
                self._buffers[tid].write(text)
            else:
                self._real.write(text)

    def flush(self):
        self._real.flush()

    @property
    def encoding(self):
        return getattr(self._real, 'encoding', 'utf-8')

    def fileno(self):
        return self._real.fileno()

    def isatty(self):
        return self._real.isatty()

    def __getattr__(self, name):
        return getattr(self._real, name)


_real_stdout = sys.stdout
_real_stderr = sys.stderr
_cap_stdout = _CapturingStream(_real_stdout)
_cap_stderr = _CapturingStream(_real_stderr)
sys.stdout = _cap_stdout
sys.stderr = _cap_stderr


def _patch_logging_handlers():
    import logging as _logging
    for logger in [_logging.root] + list(_logging.Logger.manager.loggerDict.values()):
        if not isinstance(logger, _logging.Logger):
            continue
        for handler in logger.handlers:
            if hasattr(handler, 'stream'):
                if handler.stream is _real_stderr:
                    handler.stream = _cap_stderr
                elif handler.stream is _real_stdout:
                    handler.stream = _cap_stdout


# ---------------------------------------------------------------------------
def _find_adb_directory() -> str:
    potential_paths = [
        os.path.expanduser('~/Library/Android/sdk/platform-tools/adb'),
        os.path.expanduser('~/Android/Sdk/platform-tools/adb'),
        '/root/android/android_sdk/platform-tools/adb',
        '/app/.android/platform-tools/adb',
    ]
    for path in potential_paths:
        if os.path.isfile(path):
            return path
    raise EnvironmentError('adb not found in the common Android SDK paths.')


_ADB_PATH = flags.DEFINE_string('adb_path', _find_adb_directory(), 'Path to adb.')
_EMULATOR_SETUP = flags.DEFINE_boolean('perform_emulator_setup', False, 'Whether to perform emulator setup.')
_MODEL = flags.DEFINE_string('model', 'gemini-3-pro-preview', 'Gemini model id.')
_ENDPOINT = flags.DEFINE_string(
    'endpoint', '',
    'API host. If empty, falls back to GEMINI_ENDPOINT env var, then '
    'https://api.example.com.',
)
_API_KEY = flags.DEFINE_string(
    'api_key', '',
    'API key. If empty, falls back to GEMINI_API_KEY env var.',
)
_SUITE_FAMILY = flags.DEFINE_enum(
    'suite_family', registry.TaskRegistry.ANDROID_WORLD_FAMILY,
    [registry.TaskRegistry.ANDROID_WORLD_FAMILY, registry.TaskRegistry.MINIWOB_FAMILY_SUBSET,
     registry.TaskRegistry.MINIWOB_FAMILY, registry.TaskRegistry.ANDROID_FAMILY,
     registry.TaskRegistry.INFORMATION_RETRIEVAL_FAMILY],
    'Suite family to run.',
)
_TASK_RANDOM_SEED = flags.DEFINE_integer('task_random_seed', 30, 'Random seed.')
_TASKS = flags.DEFINE_list('tasks', None, 'Specific tasks to run.')
_N_TASK_COMBINATIONS = flags.DEFINE_integer('n_task_combinations', 1, 'Task instances per template.')
_CHECKPOINT_DIR = flags.DEFINE_string('checkpoint_dir', '', 'Checkpoint directory.')
_OUTPUT_PATH = flags.DEFINE_string('output_path', os.path.expanduser('~/android_world/runs'), 'Results path.')
_TRAJ_OUTPUT_PATH = flags.DEFINE_string('traj_output_path', '', 'Trajectory path.')
_FIXED_TASK_SEED = flags.DEFINE_boolean('fixed_task_seed', False, 'Same seed for all combinations.')
# Gemini 3 sampling / agent knobs
_TEMPERATURE = flags.DEFINE_float('temperature', 1.0, 'Sampling temperature (Gemini 3: keep 1.0).')
_THINKING_LEVEL = flags.DEFINE_string('thinking_level', 'high', 'Thinking level: low|medium|high.')
_MEDIA_RESOLUTION = flags.DEFINE_string(
    'media_resolution', 'media_resolution_high',
    'Media resolution: media_resolution_low|_medium|_high.',
)
_MAX_OUTPUT_TOKENS = flags.DEFINE_integer('max_output_tokens', 4096, 'Max output tokens.')
_MAX_HISTORY_IMAGES = flags.DEFINE_integer(
    'max_history_images', 3,
    'Max past screenshots kept in the model prompt (sliding window).',
)
_MAX_RETRY = flags.DEFINE_integer('max_retry', 15, 'Max retries for generic transient errors.')
_CAPACITY_RETRY_DELAY = flags.DEFINE_float(
    'capacity_retry_delay', 30.0,
    'Seconds to sleep between retries on 429/503 capacity errors.',
)
_CAPACITY_MAX_RETRY = flags.DEFINE_integer(
    'capacity_max_retry', 30,
    'Separate retry budget for 429/503 capacity errors.',
)
_NUM_WORKERS = flags.DEFINE_integer('num_workers', 4, 'Number of parallel workers.')
_CONSOLE_PORTS = flags.DEFINE_string('console_ports', '5554,5556,5558,5560', 'Console ports.')
_GRPC_PORTS = flags.DEFINE_string('grpc_ports', '8554,8556,8558,8560', 'gRPC ports.')
_RESUME_LOG = flags.DEFINE_string('resume_log', '', 'Previous log file to resume from.')
_SPARE_CONSOLE_PORTS = flags.DEFINE_string(
    'spare_console_ports', '5570,5572',
    'Comma-separated console ports for spare emulators (failover).',
)
_SPARE_GRPC_PORTS = flags.DEFINE_string(
    'spare_grpc_ports', '8570,8572',
    'Comma-separated gRPC ports for spare emulators (failover).',
)

_METADATA_FIELDS = [
    constants.EpisodeConstants.GOAL, constants.EpisodeConstants.TASK_TEMPLATE,
    constants.EpisodeConstants.INSTANCE_ID, constants.EpisodeConstants.IS_SUCCESSFUL,
    constants.EpisodeConstants.EPISODE_LENGTH, constants.EpisodeConstants.RUN_TIME,
    constants.EpisodeConstants.EXCEPTION_INFO, constants.EpisodeConstants.AUX_DATA,
]


def _parse_resume_log(log_path):
    checkpoint_dir = traj_output_path = None
    with open(log_path) as f:
        for line in f:
            if 'Checkpoint dir:' in line:
                checkpoint_dir = line.split('Checkpoint dir:')[1].strip()
            if 'Trajectory dir:' in line:
                traj_output_path = line.split('Trajectory dir:')[1].strip()
    if not checkpoint_dir:
        raise ValueError(f'Could not find "Checkpoint dir:" in {log_path}')
    if not traj_output_path:
        log_basename = os.path.basename(log_path)
        traj_name = log_basename.replace('log_', 'traj_', 1).rsplit('.log', 1)[0]
        traj_output_path = os.path.join(os.path.dirname(os.path.dirname(log_path)), 'trajectory', traj_name)
    return checkpoint_dir, traj_output_path


def build_task_queue(suite, checkpointer):
    completed_tasks, failed_tasks = suite_utils._get_task_info(
        checkpointer.load(fields=_METADATA_FIELDS)
    )
    task_queue = queue.Queue()
    preloaded_episodes = []
    for name, instances in suite.items():
        for i, instance in enumerate(instances):
            instance_name = instance.name + checkpointer_lib.INSTANCE_SEPARATOR + str(i)
            if instance_name in completed_tasks:
                preloaded_episodes.extend(completed_tasks[instance_name])
            if instance_name in failed_tasks:
                preloaded_episodes.extend(failed_tasks[instance_name])
            if instance_name in completed_tasks and instance_name not in failed_tasks:
                continue
            task_queue.put((instance_name, i, instance))
    return task_queue, preloaded_episodes


def _dismiss_trap_overlay(env):
    from android_world.env import adb_utils
    try:
        adb_utils.issue_generic_request(
            ['shell', 'appops', 'set', 'com.trap.overlay',
             'SYSTEM_ALERT_WINDOW', 'allow'],
            env.controller,
        )
        adb_utils.issue_generic_request(
            ['shell', 'am', 'start', '-n', 'com.trap.overlay/.MainActivity'],
            env.controller,
        )
        time.sleep(0.2)
        adb_utils.issue_generic_request(
            ['shell', 'am', 'broadcast',
             '-n', 'com.trap.overlay/.TrapBroadcastReceiver',
             '-a', 'com.trap.DISMISS_POPUP'],
            env.controller,
        )
        print('[CLEANUP] Dismissed overlay popup')
    except Exception as e:
        print(f'[CLEANUP] Failed to dismiss overlay: {e}')


def worker(
    worker_id, console_port, grpc_port,
    task_queue, result_queue, suite,
    output_lock, model, api_key, endpoint,
    adb_path, emulator_setup, traj_output_path,
    temperature, thinking_level, media_resolution,
    max_output_tokens, max_retry,
    capacity_retry_delay, capacity_max_retry,
    max_history_images,
    spare_pool=None,
):
    tag = f'[W{worker_id}]'
    env = None

    def _print_direct(msg):
        with output_lock:
            _real_stdout.write(msg + '\n')
            _real_stdout.flush()

    try:
        _print_direct(f'{tag} Connecting to emulator (console={console_port}, grpc={grpc_port})...')
        for attempt in range(1, 4):
            try:
                env = env_launcher.load_and_setup_env(
                    console_port=console_port, emulator_setup=emulator_setup,
                    adb_path=adb_path, grpc_port=grpc_port,
                )
                break
            except Exception as e:
                if attempt < 3:
                    _print_direct(f'{tag} Env connect failed (attempt {attempt}/3): {e}. Retrying in 10s...')
                    time.sleep(10)
                else:
                    spare = spare_pool.get() if spare_pool else None
                    if spare:
                        console_port, grpc_port = spare
                        _print_direct(f'{tag} Primary emulator failed. Switching to spare (console={console_port}, grpc={grpc_port})...')
                        env = env_launcher.load_and_setup_env(
                            console_port=console_port, emulator_setup=emulator_setup,
                            adb_path=adb_path, grpc_port=grpc_port,
                        )
                    else:
                        raise

        _dismiss_trap_overlay(env)

        worker_traj = ''
        if traj_output_path:
            worker_traj = os.path.join(traj_output_path, f'worker_{worker_id}')
            os.makedirs(worker_traj, exist_ok=True)

        llm = infer_gemini3.Gemini3RestWrapper(
            api_key=api_key or None,
            model_name=model,
            endpoint=endpoint,
            temperature=temperature,
            thinking_level=thinking_level,
            media_resolution=media_resolution,
            max_output_tokens=max_output_tokens,
            max_retry=max_retry,
            capacity_retry_delay=capacity_retry_delay,
            capacity_max_retry=capacity_max_retry,
        )
        agent = gemini3.Gemini3Agent(
            env=env,
            llm=llm,
            name=f'Gemini3_w{worker_id}',
            max_history_images=max_history_images,
            output_path=worker_traj,
        )
        agent.tmp_prefix = f'w{worker_id}_'
        agent.get_task_name(suite)
        agent.transition_pause = None

        _print_direct(f'{tag} Ready.')

        def run_episode(task):
            return episode_runner.run_episode(
                goal=task.goal, agent=agent,
                max_n_steps=suite_utils._allocate_step_budget(task.complexity),
                start_on_home_screen=task.start_on_home_screen,
            )

        _patch_logging_handlers()

        while True:
            try:
                instance_name, instance_idx, task_instance = task_queue.get_nowait()
            except queue.Empty:
                break

            _cap_stdout.start_capture()
            _cap_stderr.start_capture()
            try:
                episode = suite_utils._run_task(task_instance, run_episode, env, demo_mode=False)
                episode[constants.EpisodeConstants.AGENT_NAME] = agent.name
                episode[constants.EpisodeConstants.INSTANCE_ID] = instance_idx
            except Exception:
                exc_info = traceback.format_exc()
                if not check_emulator_alive(adb_path, console_port):
                    _print_direct(f'{tag} Emulator on port {console_port} disconnected!')
                    spare = spare_pool.get() if spare_pool else None
                    if spare:
                        new_cp, new_gp = spare
                        _print_direct(f'{tag} Switching to spare emulator (console={new_cp}, grpc={new_gp})...')
                        try:
                            if env is not None:
                                try: env.close()
                                except Exception: pass
                            env = env_launcher.load_and_setup_env(
                                console_port=new_cp, emulator_setup=emulator_setup,
                                adb_path=adb_path, grpc_port=new_gp,
                            )
                            console_port = new_cp
                            grpc_port = new_gp
                            agent.env = env
                            _dismiss_trap_overlay(env)
                            _print_direct(f'{tag} Failover successful! Re-queuing task {instance_name}')
                            _ = _cap_stdout.stop_capture()
                            _ = _cap_stderr.stop_capture()
                            task_queue.put((instance_name, instance_idx, task_instance))
                            continue
                        except Exception:
                            _print_direct(f'{tag} Failover FAILED: {traceback.format_exc()}')
                    else:
                        _print_direct(f'{tag} No spare emulators available!')
                episode = {
                    constants.EpisodeConstants.GOAL: getattr(task_instance, 'goal', ''),
                    constants.EpisodeConstants.TASK_TEMPLATE: getattr(task_instance, 'name', instance_name),
                    constants.EpisodeConstants.INSTANCE_ID: instance_idx,
                    constants.EpisodeConstants.IS_SUCCESSFUL: 0.0,
                    constants.EpisodeConstants.EPISODE_LENGTH: 0,
                    constants.EpisodeConstants.RUN_TIME: 0.0,
                    constants.EpisodeConstants.EXCEPTION_INFO: exc_info,
                    constants.EpisodeConstants.AUX_DATA: None,
                    constants.EpisodeConstants.AGENT_NAME: f'Gemini3_w{worker_id}',
                }
            finally:
                captured_out = _cap_stdout.stop_capture()
                captured_err = _cap_stderr.stop_capture()

            task_log = ''
            if captured_out.strip():
                task_log += captured_out
            if captured_err.strip():
                task_log += captured_err
            result_queue.put((instance_name, episode, task_log))

        _print_direct(f'{tag} No more tasks.')
    except Exception:
        _cap_stdout.stop_capture()
        _cap_stderr.stop_capture()
        _print_direct(f'{tag} FATAL ERROR: {traceback.format_exc()}')
    finally:
        if env is not None:
            try:
                env.close()
            except Exception:
                pass


def _main() -> None:
    console_ports = [int(p) for p in _CONSOLE_PORTS.value.split(',')]
    grpc_ports = [int(p) for p in _GRPC_PORTS.value.split(',')]
    num_workers = min(_NUM_WORKERS.value, len(console_ports), len(grpc_ports))

    spare_console = [int(p) for p in _SPARE_CONSOLE_PORTS.value.split(',') if p.strip()] if _SPARE_CONSOLE_PORTS.value else []
    spare_grpc = [int(p) for p in _SPARE_GRPC_PORTS.value.split(',') if p.strip()] if _SPARE_GRPC_PORTS.value else []
    spare_pool = SpareEmulatorPool(spare_console, spare_grpc) if spare_console else None

    api_key = _API_KEY.value or os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        raise RuntimeError(
            'No API key. Pass --api_key=<KEY>, set GEMINI_API_KEY, or write '
            'it into <repo>/.env.'
        )
    endpoint = (
        _ENDPOINT.value
        or os.environ.get('GEMINI_ENDPOINT')
        or 'https://api.example.com'
    )

    print(f'Parallel runner (Gemini 3): {num_workers} workers')
    print(f'Model: {_MODEL.value}  Endpoint: {endpoint}')
    print(f'Console ports: {console_ports[:num_workers]}')
    print(f'gRPC ports:    {grpc_ports[:num_workers]}')
    print(f'Spare emulators: {list(zip(spare_console, spare_grpc))}')

    task_registry = registry.TaskRegistry()
    suite = suite_utils.create_suite(
        task_registry.get_registry(family=_SUITE_FAMILY.value),
        n_task_combinations=_N_TASK_COMBINATIONS.value,
        seed=_TASK_RANDOM_SEED.value,
        tasks=_TASKS.value,
        use_identical_params=_FIXED_TASK_SEED.value,
    )
    suite.suite_family = _SUITE_FAMILY.value

    if _RESUME_LOG.value:
        resume_ckpt, resume_traj = _parse_resume_log(_RESUME_LOG.value)
        checkpoint_dir = resume_ckpt
        traj_output_path = resume_traj
        print(f'RESUME MODE from: {_RESUME_LOG.value}')
        print(f'  Checkpoint dir: {checkpoint_dir}')
        print(f'  Trajectory dir: {traj_output_path}')
    else:
        checkpoint_dir = _CHECKPOINT_DIR.value or checkpointer_lib.create_run_directory(_OUTPUT_PATH.value)
        traj_output_path = _TRAJ_OUTPUT_PATH.value

    checkpointer = checkpointer_lib.IncrementalCheckpointer(checkpoint_dir)
    task_queue, preloaded_episodes = build_task_queue(suite, checkpointer)
    num_remaining = task_queue.qsize()

    if num_remaining == 0:
        print('All tasks already completed.')
        suite_utils.process_episodes(preloaded_episodes, print_summary=True)
        return

    print(f'Tasks remaining: {num_remaining}, already done: {len(preloaded_episodes)}')
    print(f'Checkpoint dir: {checkpoint_dir}')
    print(f'Trajectory dir: {traj_output_path}')

    result_queue = queue.Queue()
    output_lock = threading.Lock()
    checkpoint_lock = threading.Lock()
    if traj_output_path:
        os.makedirs(traj_output_path, exist_ok=True)

    threads = []
    for i in range(num_workers):
        t = threading.Thread(
            target=worker,
            args=(i, console_ports[i], grpc_ports[i], task_queue, result_queue, suite, output_lock,
                  _MODEL.value, api_key, endpoint, _ADB_PATH.value, _EMULATOR_SETUP.value,
                  traj_output_path,
                  _TEMPERATURE.value, _THINKING_LEVEL.value, _MEDIA_RESOLUTION.value,
                  _MAX_OUTPUT_TOKENS.value, _MAX_RETRY.value,
                  _CAPACITY_RETRY_DELAY.value, _CAPACITY_MAX_RETRY.value,
                  _MAX_HISTORY_IMAGES.value,
                  spare_pool),
            name=f'worker-{i}', daemon=True,
        )
        threads.append(t)
        t.start()

    episodes_metadata = list(preloaded_episodes)
    completed = 0
    while completed < num_remaining:
        try:
            instance_name, episode, task_log = result_queue.get(timeout=5)
        except queue.Empty:
            if not any(t.is_alive() for t in threads):
                print(f'\nAll workers exited. {completed}/{num_remaining} tasks completed.')
                break
            continue

        with checkpoint_lock:
            checkpointer.save_episodes([episode], instance_name)
        episode_meta = {k: episode[k] for k in _METADATA_FIELDS}
        episodes_metadata.append(episode_meta)
        completed += 1

        sr = episode.get(constants.EpisodeConstants.IS_SUCCESSFUL)
        err = episode.get(constants.EpisodeConstants.EXCEPTION_INFO)
        steps = episode.get(constants.EpisodeConstants.EPISODE_LENGTH, 0)
        secs = episode.get(constants.EpisodeConstants.RUN_TIME, 0)
        status = 'ERROR' if err else ('OK' if sr and sr > 0.5 else 'FAIL')

        with output_lock:
            _real_stdout.write(
                f'\n{"="*80}\n  [{completed}/{num_remaining}] {instance_name}: {status}'
                f'  ({steps} steps, {secs:.1f}s)\n{"="*80}\n'
            )
            if task_log.strip():
                _real_stdout.write(task_log.rstrip() + '\n' + '-' * 80 + '\n')
            _real_stdout.flush()
            suite_utils.process_episodes(episodes_metadata, print_summary=True)

    for t in threads:
        t.join(timeout=30)
    print('\n' + '=' * 80 + '\nALL TASKS COMPLETE\n' + '=' * 80)
    if episodes_metadata:
        suite_utils.process_episodes(episodes_metadata, print_summary=True)
    else:
        print('No episodes completed — check the worker errors above (likely '
              'emulator or network setup).')
    print(f'\nFinished. Results written to {checkpoint_dir}.')


def main(argv: Sequence[str]) -> None:
    del argv
    _main()


if __name__ == '__main__':
    app.run(main)
