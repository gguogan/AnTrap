#!/usr/bin/env python3
"""Generate a markdown summary table from log files.

Scans log/origin/{MODEL}/ and log/trap/{MODEL}/ directories,
parses the final success rate and per-task results from each log,
and produces a markdown table.

Rows = models, Columns = origin + trap categories.

Usage:
    python scripts/summarize_results.py
    python scripts/summarize_results.py --log_root log --output results.md
    python scripts/summarize_results.py --detail   # include per-task breakdown
"""

import argparse
import math
import os
import re
from collections import defaultdict


def parse_log_file(log_path):
    """Parse a log file and extract results.

    Returns:
        dict with keys:
        - 'mean_success_rate': float (overall)
        - 'num_tasks': int
        - 'num_completed': int
        - 'tasks': dict of {task_name: success_rate}
        - 'trap_config': str (e.g., 'a_layer/grounding_error')
        - 'trap_events': int (total trap events)
    """
    result = {
        'mean_success_rate': None,
        'num_tasks': 0,
        'num_completed': 0,
        'tasks': {},
        'trap_config': 'origin',
        'trap_events': 0,
        'total_attempts': 0,
        'task_attempts': {},  # per-task attempts
    }

    # Extract trap config from filename
    basename = os.path.basename(log_path)
    # Patterns: log_{MODEL}_none_none_{ts}.log or log_{MODEL}_{cat}_{type}_{ts}.log
    # or log_{MODEL}_parallel_{ts}.log (origin)
    trap_match = re.search(r'log_[^_]+_([a-z]+_[a-z]+)_(\w+)_\d{4}', basename)
    if trap_match:
        cat_type = trap_match.group(1) + '/' + trap_match.group(2)
        if 'none_none' in cat_type or 'none/none' in cat_type:
            result['trap_config'] = 'origin'
        else:
            result['trap_config'] = cat_type
    elif 'parallel' in basename and 'trap' not in basename:
        result['trap_config'] = 'origin'

    # Parse file content
    last_average_line = None
    task_lines = []
    in_table = False
    header_seen = False
    trap_event_count = 0
    total_attempts = 0

    with open(log_path, 'r', errors='replace') as f:
        for line in f:
            # Count trap events (look for '[TRAP] step=' marker)
            if '[TRAP] step=' in line:
                trap_event_count += 1

            # Parse attempts from task summary line
            # Format: [1/116] CameraTakePhoto_0: OK  (4 steps, 37.1s, 1 attempts)
            attempts_match = re.search(r'\[(\d+)/\d+\]\s+(\S+):\s+\S+\s+\(\d+\s+steps,[^)]+,\s*(\d+)\s+attempts\)', line)
            if attempts_match:
                task_name = attempts_match.group(2)
                attempts = int(attempts_match.group(3))
                result['task_attempts'][task_name] = attempts
                total_attempts += attempts

            # Detect Trap config from log content
            trap_log_match = re.search(r'Trap: (\S+)/(\S+)', line)
            if trap_log_match:
                cat = trap_log_match.group(1)
                typ = trap_log_match.group(2)
                if cat != 'none':
                    result['trap_config'] = f'{cat}/{typ}'

            # Track table header
            if 'task_num' in line and 'num_complete_trials' in line:
                header_seen = True
                in_table = True
                task_lines = []
                continue

            # Parse table rows
            if in_table and header_seen:
                stripped = line.strip()
                if not stripped:
                    in_table = False
                    continue
                if '========= Average =========' in stripped:
                    last_average_line = stripped
                    in_table = False
                    continue
                # Parse task row
                # Format: TaskName  <spaces>  num  num  float  float  float  num
                parts = stripped.rsplit(None, 6)
                if len(parts) >= 4:
                    task_name = parts[0]
                    try:
                        success_rate = float(parts[3])
                        # NaN (from skipped/errored tasks) → treat as failure (0)
                        if math.isnan(success_rate):
                            success_rate = 0.0
                        task_lines.append((task_name, success_rate))
                    except (ValueError, IndexError):
                        pass

    # Parse the last Average line (only for num_completed; mean_success_rate
    # from this line is rounded to 2 decimals, so we recompute it below)
    if last_average_line:
        parts = last_average_line.split()
        nums = []
        for p in parts:
            try:
                nums.append(float(p))
            except ValueError:
                continue
        if len(nums) >= 2:
            result['num_completed'] = int(nums[1])  # num_complete_trials

    # Store per-task results and recompute mean_success_rate at full precision
    # (per-task values are binary 0.00/1.00 so no precision is lost)
    for task_name, sr in task_lines:
        result['tasks'][task_name] = sr
    result['num_tasks'] = len(task_lines)
    if task_lines:
        result['mean_success_rate'] = sum(sr for _, sr in task_lines) / len(task_lines)
    result['trap_events'] = trap_event_count
    result['total_attempts'] = total_attempts

    return result


def find_latest_log(directory):
    """Find the most recent log file in a directory."""
    if not os.path.isdir(directory):
        return None
    logs = [f for f in os.listdir(directory) if f.endswith('.log')]
    if not logs:
        return None
    # Sort by modification time, newest first
    logs.sort(key=lambda f: os.path.getmtime(os.path.join(directory, f)), reverse=True)
    return os.path.join(directory, logs[0])


def scan_logs(log_root):
    """Scan log directory and collect results.

    Supports new directory structure:
    - origin: log/origin/{MODEL}/*.log
    - trap: log/trap/{MODEL}/{TRAP_CATEGORY}/*.log

    Trap config format: {category}/{trap_type} (e.g., 's_layer/external_interruption')

    Returns:
        dict of {model: {trap_config: result_dict}}
    """
    results = defaultdict(dict)

    for group in ('origin', 'trap'):
        group_dir = os.path.join(log_root, group)
        if not os.path.isdir(group_dir):
            continue
        for model in sorted(os.listdir(group_dir)):
            model_dir = os.path.join(group_dir, model)
            if not os.path.isdir(model_dir):
                continue

            # Check if model_dir has subdirectories (new structure) or log files (old structure)
            has_subdirs = any(os.path.isdir(os.path.join(model_dir, d))
                             for d in os.listdir(model_dir) if not d.startswith('.'))

            if group == 'trap' and has_subdirs:
                # New structure: log/trap/{MODEL}/{TRAP_CATEGORY}/*.log
                for category in sorted(os.listdir(model_dir)):
                    cat_dir = os.path.join(model_dir, category)
                    if not os.path.isdir(cat_dir):
                        continue
                    for log_file in sorted(os.listdir(cat_dir)):
                        if not log_file.endswith('.log'):
                            continue
                        log_path = os.path.join(cat_dir, log_file)
                        result = parse_log_file(log_path)

                        # Extract trap_type from filename
                        # Format: log_{MODEL}_{category}_{trap_type}_{timestamp}.log
                        basename = os.path.basename(log_file)
                        trap_type = None

                        # Try to extract trap_type from filename
                        # Pattern: log_MODEL_category_trap_type_timestamp.log
                        parts = basename.replace('.log', '').split('_')
                        # Find category index
                        try:
                            cat_idx = parts.index(category.replace('_', '')) if category.replace('_', '') in parts else -1
                            if cat_idx >= 0 and cat_idx + 1 < len(parts) - 2:  # -2 for timestamp
                                trap_type = '_'.join(parts[cat_idx + 1:-2])
                        except (ValueError, IndexError):
                            pass

                        # Fallback: use result's trap_type if parsed from file content
                        if not trap_type or trap_type == 'none':
                            # Extract from parse_log_file result
                            cfg = result.get('trap_config', '')
                            if '/' in cfg:
                                trap_type = cfg.split('/')[1]
                            else:
                                trap_type = 'unknown'

                        # Set trap_config as category/trap_type
                        if category == 'trap_none' or trap_type == 'none':
                            result['trap_config'] = 'origin'
                        else:
                            result['trap_config'] = f'{category}/{trap_type}'

                        if result['mean_success_rate'] is not None:
                            trap_cfg = result['trap_config']
                            # Extract timestamp from filename for comparison
                            # Format: log_MODEL_category_type_YYYY-MM-DD_HH-MM-SS.log
                            timestamp = ''
                            ts_match = re.search(r'(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})', log_file)
                            if ts_match:
                                timestamp = ts_match.group(1)

                            result['_timestamp'] = timestamp

                            if trap_cfg not in results[model]:
                                results[model][trap_cfg] = result
                            else:
                                # Keep the one with newer timestamp
                                old_ts = results[model][trap_cfg].get('_timestamp', '')
                                if timestamp > old_ts:
                                    results[model][trap_cfg] = result
            else:
                # Old structure: log/{group}/{MODEL}/*.log
                for log_file in sorted(os.listdir(model_dir)):
                    if not log_file.endswith('.log'):
                        continue
                    log_path = os.path.join(model_dir, log_file)
                    result = parse_log_file(log_path)
                    if result['mean_success_rate'] is not None:
                        trap_cfg = result['trap_config']
                        # Extract timestamp for comparison
                        timestamp = ''
                        ts_match = re.search(r'(\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2})', log_file)
                        if ts_match:
                            timestamp = ts_match.group(1)
                        result['_timestamp'] = timestamp

                        if trap_cfg not in results[model]:
                            results[model][trap_cfg] = result
                        else:
                            old_ts = results[model][trap_cfg].get('_timestamp', '')
                            if timestamp > old_ts:
                                results[model][trap_cfg] = result

    return dict(results)


def generate_markdown(results, detail=False):
    """Generate markdown summary from results.

    Args:
        results: dict of {model: {trap_config: result_dict}}
        detail: if True, include per-task breakdown

    Returns:
        markdown string
    """
    if not results:
        return "No results found.\n"

    # Collect all trap configs across all models
    all_configs = set()
    for model_results in results.values():
        all_configs.update(model_results.keys())

    # Sort configs: origin first, then by category
    def config_sort_key(c):
        if c == 'origin':
            return (0, '')
        return (1, c)

    configs = sorted(all_configs, key=config_sort_key)

    lines = []
    lines.append("# Experiment Results Summary\n")
    lines.append(f"Models: {len(results)} | Configurations: {len(configs)}\n")

    # --- Overall success rate table ---
    lines.append("## Overall Success Rate\n")

    # Header
    header = "| Model |"
    separator = "| :--- |"
    for cfg in configs:
        display = cfg if cfg != 'origin' else 'Baseline'
        header += f" {display} |"
        separator += " :---: |"
    lines.append(header)
    lines.append(separator)

    # Rows
    for model in sorted(results.keys()):
        row = f"| {model} |"
        for cfg in configs:
            if cfg in results[model]:
                r = results[model][cfg]
                sr = r['mean_success_rate']
                n = r['num_tasks']
                traps = r['trap_events']
                attempts = r.get('total_attempts', n)  # default to n if not tracked
                avg_attempts = attempts / n if n > 0 else 1
                cell = f"{sr:.3f} ({n}t"
                if traps > 0:
                    cell += f", {traps}traps"
                if avg_attempts > 1:
                    cell += f", {avg_attempts:.1f}att"
                cell += ")"
                row += f" {cell} |"
            else:
                row += " - |"
        lines.append(row)

    lines.append("")

    # --- Delta table (drop from baseline) ---
    lines.append("## Performance Drop from Baseline\n")
    header = "| Model |"
    separator = "| :--- |"
    for cfg in configs:
        if cfg == 'origin':
            continue
        display = cfg
        header += f" {display} |"
        separator += " :---: |"
    lines.append(header)
    lines.append(separator)

    for model in sorted(results.keys()):
        row = f"| {model} |"
        baseline_sr = None
        if 'origin' in results[model]:
            baseline_sr = results[model]['origin']['mean_success_rate']
        for cfg in configs:
            if cfg == 'origin':
                continue
            if cfg in results[model] and baseline_sr is not None:
                sr = results[model][cfg]['mean_success_rate']
                delta = sr - baseline_sr
                sign = "+" if delta >= 0 else ""
                row += f" {sign}{delta:.3f} |"
            else:
                row += " - |"
        lines.append(row)

    lines.append("")

    # --- Per-task detail ---
    if detail:
        lines.append("## Per-Task Breakdown\n")
        for model in sorted(results.keys()):
            lines.append(f"### {model}\n")

            # Collect all task names
            all_tasks = set()
            for cfg_results in results[model].values():
                all_tasks.update(cfg_results['tasks'].keys())

            if not all_tasks:
                lines.append("No per-task data available.\n")
                continue

            # Header
            header = "| Task |"
            separator = "| :--- |"
            for cfg in configs:
                if cfg in results[model]:
                    display = cfg if cfg != 'origin' else 'Baseline'
                    header += f" {display} |"
                    separator += " :---: |"
            lines.append(header)
            lines.append(separator)

            # Rows
            for task in sorted(all_tasks):
                row = f"| {task} |"
                for cfg in configs:
                    if cfg not in results[model]:
                        continue
                    tasks = results[model][cfg]['tasks']
                    if task in tasks:
                        sr = tasks[task]
                        row += f" {sr:.1f} |"
                    else:
                        row += " - |"
                lines.append(row)

            lines.append("")

    # --- Metadata ---
    lines.append("## Run Details\n")
    header = "| Model | Config | Tasks | Completed | Trap Events | Log File |"
    separator = "| :--- | :--- | :---: | :---: | :---: | :--- |"
    lines.append(header)
    lines.append(separator)

    for model in sorted(results.keys()):
        for cfg in configs:
            if cfg not in results[model]:
                continue
            r = results[model][cfg]
            display = cfg if cfg != 'origin' else 'Baseline'
            lines.append(
                f"| {model} | {display} | {r['num_tasks']} | "
                f"{r['num_completed']} | {r['trap_events']} | - |"
            )

    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='Summarize experiment results from logs')
    parser.add_argument('--log_root', default='log', help='Root log directory (default: log)')
    parser.add_argument('--output', default='results.md', help='Output markdown file (default: results.md)')
    parser.add_argument('--detail', action='store_true', help='Include per-task breakdown')
    parser.add_argument('--print', action='store_true', dest='print_output', help='Print to stdout')
    args = parser.parse_args()

    results = scan_logs(args.log_root)

    if not results:
        print(f"No log files found in {args.log_root}/{{origin,trap}}/*/")
        print("Expected structure:")
        print("  log/origin/{MODEL}/log_*.log")
        print("  log/trap/{MODEL}/log_*.log")
        return

    md = generate_markdown(results, detail=args.detail)

    with open(args.output, 'w') as f:
        f.write(md)
    print(f"Results written to {args.output}")

    if args.print_output:
        print("\n" + md)
    else:
        # Always print the overview table
        for line in md.split('\n'):
            if line.startswith('#') or line.startswith('|') or line.startswith('Models:'):
                if 'Per-Task' in line:
                    break
                print(line)


if __name__ == '__main__':
    main()
