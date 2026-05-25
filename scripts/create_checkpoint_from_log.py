#!/usr/bin/env python3
"""Create checkpoint files from a log file to enable resume.

Usage:
    python scripts/create_checkpoint_from_log.py <log_file> <checkpoint_dir> [--num_tasks N]

Example:
    python scripts/create_checkpoint_from_log.py \
        log/trap/gemini-3-pro-preview/overall/log_xxx.log \
        /root/android_world/runs/run_xxx \
        --num_tasks 42
"""

import argparse
import gzip
import io
import os
import pickle
import re
from typing import Any


def _gzip_pickle(data: Any) -> bytes:
    """Pickle and gzip compress an object."""
    pickled_data = io.BytesIO()
    pickle.dump(data, pickled_data)
    pickled_data.seek(0)
    compressed_data = io.BytesIO()
    with gzip.GzipFile(fileobj=compressed_data, mode='wb', compresslevel=5) as f_out:
        f_out.write(pickled_data.getvalue())
    return compressed_data.getvalue()


def parse_completed_tasks(log_path: str, max_tasks: int = None):
    """Parse completed task names from log file.

    Format: [x/116] TaskName: OK/FAIL  (...)
    """
    tasks = []
    # Allow optional leading whitespace (log lines have 2-space indent)
    pattern = re.compile(r'\s*\[(\d+)/\d+\]\s+(\S+):')

    with open(log_path, 'r', errors='replace') as f:
        for line in f:
            match = pattern.match(line)
            if match:
                task_num = int(match.group(1))
                task_name = match.group(2)
                tasks.append((task_num, task_name))

    # Sort by task number
    tasks.sort(key=lambda x: x[0])

    if max_tasks:
        tasks = tasks[:max_tasks]

    return tasks


def create_checkpoint(checkpoint_dir: str, task_names: list[str]):
    """Create checkpoint files for given task names.

    Task name format: {task_template}_{instance_id} (e.g., AudioRecorderRecordAudio_0)
    Episode format must include: task_template, instance_id, is_successful
    """
    os.makedirs(checkpoint_dir, exist_ok=True)

    for task_name in task_names:
        # Split task_name into task_template and instance_id
        # Format: {task_template}_{instance_id}, e.g., AudioRecorderRecordAudio_0
        # Find last underscore followed by a number
        parts = task_name.rsplit('_', 1)
        if len(parts) == 2 and parts[1].isdigit():
            task_template = parts[0]
            instance_id = int(parts[1])
        else:
            # Fallback: treat whole name as template, instance_id=0
            task_template = task_name
            instance_id = 0

        # Create episode with required fields for _get_task_info
        episode = {
            'task_template': task_template,
            'instance_id': instance_id,
            'is_successful': 1.0,  # Mark as success
            'goal': '',  # Empty goal
            'episode_length': 0,
            'run_time': 0.0,
            'exception_info': None,  # No exception = completed (not failed)
            'aux_data': {},
        }

        filename = os.path.join(checkpoint_dir, f'{task_name}.pkl.gz')
        with open(filename, 'wb') as f:
            f.write(_gzip_pickle([episode]))

        print(f'Created: {filename} (template={task_template}, instance_id={instance_id})')

    print(f'\nTotal: {len(task_names)} checkpoint files created in {checkpoint_dir}')


def main():
    parser = argparse.ArgumentParser(description='Create checkpoint from log')
    parser.add_argument('log_file', help='Log file to parse')
    parser.add_argument('checkpoint_dir', help='Checkpoint directory to create')
    parser.add_argument('--num_tasks', type=int, help='Number of tasks to include (default: all)')
    args = parser.parse_args()

    tasks = parse_completed_tasks(args.log_file, args.num_tasks)
    task_names = [name for _, name in tasks]

    print(f'Found {len(tasks)} tasks in log:')
    for num, name in tasks[:10]:
        print(f'  {num}: {name}')
    if len(tasks) > 10:
        print(f'  ... and {len(tasks) - 10} more')

    create_checkpoint(args.checkpoint_dir, task_names)


if __name__ == '__main__':
    main()