import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

"""Parallel eval suite runner for GUI-Owl-1.5 with trap injection."""

from collections.abc import Sequence
import datetime
import io
import json
import os
import queue
import shutil
import sys
import tempfile
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
from android_world.agents import gui_owl_1_5
from android_world.agents import infer_ma3
from android_world.disturbances import TrapConfig, TrapController
from android_world.env import env_launcher
from scripts.emulator_failover import SpareEmulatorPool, check_emulator_alive, try_recover_network

absl_logging.set_verbosity(absl_logging.WARNING)
os.environ['GRPC_VERBOSITY'] = 'ERROR'
os.environ['GRPC_TRACE'] = 'none'


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
    raise EnvironmentError('adb not found.')


_ADB_PATH = flags.DEFINE_string('adb_path', _find_adb_directory(), 'Path to adb.')
_EMULATOR_SETUP = flags.DEFINE_boolean('perform_emulator_setup', False, 'Emulator setup.')
_MODEL = flags.DEFINE_string('model', 'GUI-Owl-1.5-8B-Think', 'Model name.')
_SUITE_FAMILY = flags.DEFINE_enum(
    'suite_family', registry.TaskRegistry.ANDROID_WORLD_FAMILY,
    [registry.TaskRegistry.ANDROID_WORLD_FAMILY, registry.TaskRegistry.MINIWOB_FAMILY_SUBSET,
     registry.TaskRegistry.MINIWOB_FAMILY, registry.TaskRegistry.ANDROID_FAMILY,
     registry.TaskRegistry.INFORMATION_RETRIEVAL_FAMILY], 'Suite family.',
)
_TASK_RANDOM_SEED = flags.DEFINE_integer('task_random_seed', 30, 'Random seed.')
_TASKS = flags.DEFINE_list('tasks', None, 'Specific tasks.')
_N_TASK_COMBINATIONS = flags.DEFINE_integer('n_task_combinations', 1, 'Instances per template.')
_CHECKPOINT_DIR = flags.DEFINE_string('checkpoint_dir', '', 'Checkpoint directory.')
_OUTPUT_PATH = flags.DEFINE_string('output_path', os.path.expanduser('~/android_world/runs'), 'Results path.')
_TRAJ_OUTPUT_PATH = flags.DEFINE_string('traj_output_path', '', 'Trajectory path.')
_API_KEY = flags.DEFINE_string('api_key', 'EMPTY', 'API key.')
_BASE_URL = flags.DEFINE_string('base_url', 'http://localhost:9001/v1', 'vLLM base URL.')
_FIXED_TASK_SEED = flags.DEFINE_boolean('fixed_task_seed', False, 'Same seed for all.')
_MAX_HISTORY_IMAGES = flags.DEFINE_integer('max_history_images', 5, 'Max past screenshots.')
_NUM_WORKERS = flags.DEFINE_integer('num_workers', 4, 'Parallel workers.')
_CONSOLE_PORTS = flags.DEFINE_string('console_ports', '5554,5556,5558,5560', 'Console ports.')
_GRPC_PORTS = flags.DEFINE_string('grpc_ports', '8554,8556,8558,8560', 'gRPC ports.')
_RESUME_LOG = flags.DEFINE_string('resume_log', '', 'Previous log to resume from.')

# Trap flags
_TRAP_CATEGORY = flags.DEFINE_string('trap_category', 'none', 'Trap category.')
_TRAP_TYPE = flags.DEFINE_string('trap_type', 'none', 'Trap sub-type.')
_TRAP_PROBABILITY = flags.DEFINE_float('trap_probability', 0.3, 'Per-step trigger probability.')
_TRAP_SEED = flags.DEFINE_integer('trap_seed', 42, 'RNG seed for traps.')
_MAX_TRAPS = flags.DEFINE_integer('max_traps', 0, 'Max traps per episode (0=unlimited).')
_TRAP_PARAMS = flags.DEFINE_string('trap_params', '{}', 'JSON extra trap params.')
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


def _build_trap_config():
    extra = json.loads(_TRAP_PARAMS.value) if _TRAP_PARAMS.value else {}
    return TrapConfig(
        category=_TRAP_CATEGORY.value, trap_type=_TRAP_TYPE.value,
        trigger_probability=_TRAP_PROBABILITY.value, seed=_TRAP_SEED.value,
        max_traps=_MAX_TRAPS.value, **extra,
    )


def _dismiss_trap_overlay(env):
    from android_world.env import adb_utils
    try:
        adb_utils.issue_generic_request(
            ['shell', 'appops', 'set', 'com.trap.overlay', 'SYSTEM_ALERT_WINDOW', 'allow'],
            env.controller)
        adb_utils.issue_generic_request(
            ['shell', 'am', 'start', '-n', 'com.trap.overlay/.MainActivity'], env.controller)
        time.sleep(0.2)
        adb_utils.issue_generic_request(
            ['shell', 'am', 'broadcast', '-n', 'com.trap.overlay/.TrapBroadcastReceiver',
             '-a', 'com.trap.DISMISS_POPUP'], env.controller)
        print('[CLEANUP] Overlay permission granted & popup dismissed')
    except Exception as e:
        print(f'[CLEANUP] Failed to setup overlay: {e}')


def worker(
    worker_id, console_port, grpc_port,
    task_queue, result_queue, suite,
    output_lock, model, api_key, base_url,
    adb_path, emulator_setup, traj_output_path, max_history_images,
    trap_config,
    spare_pool=None,
):
    tag = f'[W{worker_id}]'
    env = None

    def _print_direct(msg):
        with output_lock:
            _real_stdout.write(msg + '\n')
            _real_stdout.flush()

    def _swap_to_spare(cur_env, cur_cp, cur_gp, agent_obj=None, trap_obj=None):
        """Close current env, pull a spare from the pool, load a new env on it.

        Returns (env, console_port, grpc_port, ok). When called before the
        agent/trap_controller exist, pass None for those args.
        """
        spare = spare_pool.get() if spare_pool else None
        if not spare:
            _print_direct(f'{tag} No spare emulators available!')
            return cur_env, cur_cp, cur_gp, False
        new_cp, new_gp = spare
        _print_direct(f'{tag} Switching to spare emulator (console={new_cp}, grpc={new_gp})...')
        try:
            if cur_env is not None:
                try: cur_env.close()
                except Exception: pass
            new_env = env_launcher.load_and_setup_env(
                console_port=new_cp, emulator_setup=emulator_setup,
                adb_path=adb_path, grpc_port=new_gp,
            )
            if agent_obj is not None:
                agent_obj.env = new_env
            if trap_obj is not None:
                trap_obj.env = new_env
            _dismiss_trap_overlay(new_env)
            _print_direct(f'{tag} Failover successful!')
            return new_env, new_cp, new_gp, True
        except Exception:
            _print_direct(f'{tag} Failover FAILED: {traceback.format_exc()}')
            return cur_env, cur_cp, cur_gp, False

    try:
        _print_direct(f'{tag} Connecting to emulator (console={console_port}, grpc={grpc_port})...')
        for attempt in range(1, 4):
            try:
                env = env_launcher.load_and_setup_env(
                    console_port=console_port, emulator_setup=emulator_setup,
                    adb_path=adb_path, grpc_port=grpc_port)
                break
            except Exception as e:
                if attempt < 3:
                    _print_direct(f'{tag} Env connect failed (attempt {attempt}/3): {e}. Retrying in 10s...')
                    time.sleep(10)
                else:
                    env, console_port, grpc_port, ok = _swap_to_spare(env, console_port, grpc_port)
                    if not ok:
                        raise

        # Pre-flight: even if env_launcher succeeded, the emulator may have
        # broken host-network state (eth0 down / ConnectivityService not
        # registered). The wrapper will then never receive a11y events and
        # we'd burn 10x reset retries before noticing. Detect upfront and
        # fail over now if possible.
        if not check_emulator_alive(adb_path, console_port):
            _print_direct(f'{tag} Emulator on port {console_port} failed pre-flight; attempting in-place recovery...')
            if try_recover_network(adb_path, console_port):
                _print_direct(f'{tag} In-place recovery succeeded.')
            else:
                env, console_port, grpc_port, ok = _swap_to_spare(env, console_port, grpc_port)
                if not ok:
                    _print_direct(f'{tag} No usable emulator; worker exiting.')
                    return

        _dismiss_trap_overlay(env)

        worker_traj = ''
        if traj_output_path:
            worker_traj = os.path.join(traj_output_path, f'worker_{worker_id}')
            os.makedirs(worker_traj, exist_ok=True)

        vllm_wrapper = infer_ma3.GUIOwlWrapper(api_key, base_url, model)

        trap_controller = None
        if trap_config.category != 'none':
            trap_controller = TrapController(trap_config, env=env, vllm_wrapper=vllm_wrapper)
            trap_controller._dismiss_trap_overlay()

        agent = gui_owl_1_5.GUIOwl15Agent(
            env=env, vllm=vllm_wrapper,
            name=f'GUIOwl15_w{worker_id}',
            max_history_images=max_history_images,
            output_path=worker_traj,
            api_key=api_key, url=base_url,
        )
        agent.get_task_name(suite)
        agent.transition_pause = None
        agent.trap_controller = trap_controller

        _print_direct(f'{tag} Ready. Trap: {trap_config.category}/{trap_config.trap_type} (p={trap_config.trigger_probability})')

        def run_episode_fn(task):
            if trap_controller:
                trap_controller.reset()
                trap_controller.set_current_task_name(task.__class__.__name__)
            return episode_runner.run_episode(
                goal=task.goal, agent=agent,
                max_n_steps=suite_utils._allocate_step_budget(task.complexity),
                start_on_home_screen=task.start_on_home_screen,
                trap_controller=trap_controller,
            )

        _patch_logging_handlers()

        while True:
            try:
                instance_name, instance_idx, task_instance = task_queue.get_nowait()
            except queue.Empty:
                break

            max_retries = 10
            episode = None
            task_trap_log = []
            attempts = 1
            captured_out = ''
            captured_err = ''

            for attempt in range(max_retries):
                temp_traj = tempfile.mkdtemp(prefix=f'trap_retry_{attempt}_')
                original_output_path = agent.output_path
                agent.output_path = temp_traj

                _cap_stdout.start_capture()
                _cap_stderr.start_capture()
                try:
                    agent.reset(go_home=False)
                    task_instance.initialized = False  # Allow re-initialization on retry
                    if trap_controller:
                        trap_controller.reset()
                    env.reset(go_home=True)

                    episode = suite_utils._run_task(
                        task_instance, run_episode_fn, env, demo_mode=False)
                    episode[constants.EpisodeConstants.AGENT_NAME] = agent.name
                    episode[constants.EpisodeConstants.INSTANCE_ID] = instance_idx

                    captured_out = _cap_stdout.stop_capture()
                    captured_err = _cap_stderr.stop_capture()

                    if trap_controller is None or trap_controller._traps_fired > 0:
                        if worker_traj:
                            for item in os.listdir(temp_traj):
                                src = os.path.join(temp_traj, item)
                                dst = os.path.join(worker_traj, item)
                                if os.path.exists(dst):
                                    shutil.rmtree(dst)
                                shutil.move(src, dst)
                            shutil.rmtree(temp_traj)
                        else:
                            shutil.rmtree(temp_traj)
                        attempts = attempt + 1
                        break

                    shutil.rmtree(temp_traj)
                    _print_direct(f'{tag} No trap triggered (attempt {attempt+1}/{max_retries}), retrying {instance_name}...')

                except Exception:
                    captured_out = _cap_stdout.stop_capture()
                    captured_err = _cap_stderr.stop_capture()
                    if os.path.exists(temp_traj):
                        shutil.rmtree(temp_traj)
                    _print_direct(f'{tag} Error on attempt {attempt+1}: {traceback.format_exc()}')
                    # Check if emulator disconnected or has broken host network;
                    # attempt failover to a spare. check_emulator_alive now
                    # additionally pings 10.0.2.2 to catch the silent-network case.
                    if not check_emulator_alive(adb_path, console_port):
                        _print_direct(f'{tag} Emulator on port {console_port} unhealthy; attempting in-place recovery...')
                        if try_recover_network(adb_path, console_port):
                            _print_direct(f'{tag} In-place recovery succeeded.')
                        else:
                            env, console_port, grpc_port, swap_ok = _swap_to_spare(
                                env, console_port, grpc_port,
                                agent_obj=agent, trap_obj=trap_controller,
                            )
                            if not swap_ok:
                                _print_direct(f'{tag} Spare pool exhausted; skipping {instance_name}.')
                                break
                finally:
                    agent.output_path = original_output_path

            if trap_controller:
                task_trap_log = list(trap_controller.get_trap_log())
                if trap_controller._traps_fired == 0:
                    _print_direct(f'{tag} WARNING: No trap triggered after {max_retries} retries for {instance_name}')
                if worker_traj:
                    trap_log_path = os.path.join(worker_traj, f'trap_log_{instance_name.replace("/", "_")}.jsonl')
                    trap_controller.save_trap_log(trap_log_path)

            task_log = ''
            if captured_out.strip():
                task_log += captured_out
            if captured_err.strip():
                task_log += captured_err

            if episode:
                episode['attempts'] = attempts

            result_queue.put((instance_name, episode, task_log, task_trap_log, attempts))

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

    trap_config = _build_trap_config()

    spare_console = [int(p) for p in _SPARE_CONSOLE_PORTS.value.split(',') if p.strip()] if _SPARE_CONSOLE_PORTS.value else []
    spare_grpc = [int(p) for p in _SPARE_GRPC_PORTS.value.split(',') if p.strip()] if _SPARE_GRPC_PORTS.value else []
    spare_pool = SpareEmulatorPool(spare_console, spare_grpc) if spare_console else None

    print(f'Parallel runner (GUI-Owl-1.5 + Trap): {num_workers} workers')
    print(f'Console ports: {console_ports[:num_workers]}')
    print(f'gRPC ports:    {grpc_ports[:num_workers]}')
    print(f'Trap: {trap_config.category}/{trap_config.trap_type} (p={trap_config.trigger_probability}, seed={trap_config.seed})')
    print(f'Spare emulators: {list(zip(spare_console, spare_grpc)) if spare_pool else "none"}')

    task_registry = registry.TaskRegistry()
    suite = suite_utils.create_suite(
        task_registry.get_registry(family=_SUITE_FAMILY.value),
        n_task_combinations=_N_TASK_COMBINATIONS.value, seed=_TASK_RANDOM_SEED.value,
        tasks=_TASKS.value, use_identical_params=_FIXED_TASK_SEED.value,
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
                  _MODEL.value, _API_KEY.value, _BASE_URL.value, _ADB_PATH.value, _EMULATOR_SETUP.value,
                  traj_output_path, _MAX_HISTORY_IMAGES.value, trap_config, spare_pool),
            name=f'worker-{i}', daemon=True)
        threads.append(t)
        t.start()

    episodes_metadata = list(preloaded_episodes)
    completed = 0

    while completed < num_remaining:
        try:
            instance_name, episode, task_log, task_trap_log, attempts = result_queue.get(timeout=5)
        except queue.Empty:
            if not any(t.is_alive() for t in threads):
                print(f'\nAll workers exited. {completed}/{num_remaining} tasks completed.')
                break
            continue

        if episode is None:
            # All retries failed (e.g. emulator a11y tree errors). Record a stub
            # so the run can continue with the next task instead of crashing.
            completed += 1
            with output_lock:
                _real_stdout.write(
                    f'\n[SKIP] {instance_name}: all {attempts} attempts failed,'
                    ' episode is None (see worker log above)\n'
                )
                _real_stdout.flush()
            continue

        with checkpoint_lock:
            checkpointer.save_episodes([episode], instance_name)

        episode_meta = {k: episode.get(k) for k in _METADATA_FIELDS}
        episode_meta['attempts'] = attempts
        episodes_metadata.append(episode_meta)
        completed += 1

        sr = episode.get(constants.EpisodeConstants.IS_SUCCESSFUL)
        err = episode.get(constants.EpisodeConstants.EXCEPTION_INFO)
        steps = episode.get(constants.EpisodeConstants.EPISODE_LENGTH, 0)
        secs = episode.get(constants.EpisodeConstants.RUN_TIME, 0)
        status = 'ERROR' if err is not None else ('OK' if sr is not None and sr > 0.5 else 'FAIL')

        trap_summary = ''
        if task_trap_log:
            triggered_steps = [e['step'] for e in task_trap_log]
            events = [e['event'] for e in task_trap_log]
            trap_summary = (
                f'  TRAP: {len(task_trap_log)} events at steps {triggered_steps}\n'
                f'        events: {events}\n')

        with output_lock:
            header = (
                f'\n{"="*80}\n'
                f'  [{completed}/{num_remaining}] {instance_name}: {status}'
                f'  ({steps} steps, {secs:.1f}s, {attempts} attempts)\n')
            if trap_summary:
                header += trap_summary
            header += '=' * 80
            _real_stdout.write(header + '\n')
            if task_log.strip():
                _real_stdout.write(task_log.rstrip() + '\n')
                _real_stdout.write('-' * 80 + '\n')
            _real_stdout.flush()
            suite_utils.process_episodes(episodes_metadata, print_summary=True)

    for t in threads:
        t.join(timeout=30)

    print('\n' + '=' * 80)
    print('ALL TASKS COMPLETE')
    print(f'Trap: {trap_config.category}/{trap_config.trap_type}')
    print('=' * 80)

    if episodes_metadata:
        retry_counts = {}
        for ep in episodes_metadata:
            a = ep.get('attempts', 1)
            retry_counts[a] = retry_counts.get(a, 0) + 1
        print('\nRetry Statistics:')
        for a, count in sorted(retry_counts.items()):
            print(f'  {a} attempt(s): {count} tasks')
        total_a = sum(k * v for k, v in retry_counts.items())
        total_t = sum(retry_counts.values())
        if total_t > 0:
            print(f'  Average attempts: {total_a / total_t:.2f}')
        print()
        suite_utils.process_episodes(episodes_metadata, print_summary=True)
    else:
        print('No episodes completed.')
    print(f'\nFinished. Results written to {checkpoint_dir}.')


def main(argv: Sequence[str]) -> None:
    del argv
    _main()


if __name__ == '__main__':
    app.run(main)
