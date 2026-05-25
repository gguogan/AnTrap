#!/usr/bin/env python3
"""Generate an interactive HTML trajectory viewer for trap experiments.

Usage:
  python scripts/view_trajectories.py

Features:
  - Select trajectory from web interface
  - Display screenshots with coordinate markers
  - Show thinking/action/conclusion from log
  - Note functionality for marking examples
"""
import http.server
import json
import os
import re
import sys
from http.server import HTTPStatus
from urllib.parse import unquote

# Screen dimensions for coordinate conversion
DEFAULT_SCREEN_WIDTH = 1080
DEFAULT_SCREEN_HEIGHT = 2400

# Models that use normalized 0-1000 coordinates (need conversion)
NORMALIZED_COORD_MODELS = ['GUI-Owl-1.5', 'Qwen3-VL', 'MAI-UI']

# Models that use absolute pixel coordinates (no conversion needed)
PIXEL_COORD_MODELS = ['GUI-Owl-7B']

# Known trap category subdirectories (used by scan_trajectory_dirs)
KNOWN_CATEGORY_DIRS = {'s_layer', 't_layer', 'a_layer', 'overall'}


def rescale_coord(coord: int, dimension: int, divisor: int = 999) -> int:
    """Rescale a coordinate from normalized range to pixel dimension.

    Args:
        coord: Coordinate in normalized range (0-999 for qwen-vl, 0-1000 for others)
        dimension: Target dimension in pixels (width or height)
        divisor: The divisor based on model format (999 for qwen-vl, 1000 for others)
    """
    return round(coord / divisor * dimension)


def convert_coordinates(tool_call: dict, width: int = DEFAULT_SCREEN_WIDTH,
                        height: int = DEFAULT_SCREEN_HEIGHT) -> dict:
    """Convert normalized coordinates (0-999 qwen-vl format) to absolute pixel coordinates."""
    if not tool_call or not isinstance(tool_call, dict):
        return tool_call

    result = dict(tool_call)
    if "arguments" not in result:
        return result

    args = dict(result["arguments"])

    # Convert 'coordinate' - qwen-vl uses 0-999 range
    if "coordinate" in args and isinstance(args["coordinate"], list):
        coord = args["coordinate"]
        if len(coord) >= 2:
            args["coordinate"] = [
                rescale_coord(coord[0], width, divisor=999),
                rescale_coord(coord[1], height, divisor=999)
            ]

    # Convert 'coordinate2'
    if "coordinate2" in args and isinstance(args["coordinate2"], list):
        coord2 = args["coordinate2"]
        if len(coord2) >= 2:
            args["coordinate2"] = [
                rescale_coord(coord2[0], width, divisor=999),
                rescale_coord(coord2[1], height, divisor=999)
            ]

    result["arguments"] = args
    return result


def parse_ui_tars_action(action_str: str) -> dict:
    """Parse UI-TARS action format like: click(start_box='(259,453)')"""
    # Match action type
    action_match = re.match(r'(\w+)\(', action_str)
    if not action_match:
        return None

    action_type = action_match.group(1)
    args = {}

    # Parse arguments - support multiple formats:
    # - start_box='(x,y)'  - UI-TARS format with parens
    # - start_box='[x,y]'  - bracket format
    # - start_box='[x1,y1,x2,y2]'  - bounding box format
    if action_type == 'click':
        # Match start_box with various formats
        box_match = re.search(r"start_box='?\(?([\d,\s]+)\)?'?", action_str)
        if box_match:
            coords = [int(x.strip()) for x in box_match.group(1).split(',')]
            if len(coords) >= 2:
                # Take center if it's a bounding box
                if len(coords) >= 4:
                    x = (coords[0] + coords[2]) // 2
                    y = (coords[1] + coords[3]) // 2
                else:
                    x, y = coords[0], coords[1]
                args = {"action": "click", "coordinate": [x, y]}

    elif action_type == 'long_press':
        box_match = re.search(r"start_box='?\(?([\d,\s]+)\)?'?", action_str)
        if box_match:
            coords = [int(x.strip()) for x in box_match.group(1).split(',')]
            if len(coords) >= 2:
                if len(coords) >= 4:
                    x = (coords[0] + coords[2]) // 2
                    y = (coords[1] + coords[3]) // 2
                else:
                    x, y = coords[0], coords[1]
                args = {"action": "long_press", "coordinate": [x, y]}

    elif action_type == 'scroll':
        # scroll(start_box='(x1,y1)', end_box='(x2,y2)')
        start_match = re.search(r"start_box='?\(?([\d,\s]+)\)?'?", action_str)
        end_match = re.search(r"end_box='?\(?([\d,\s]+)\)?'?", action_str)
        if start_match and end_match:
            start_coords = [int(x.strip()) for x in start_match.group(1).split(',')]
            end_coords = [int(x.strip()) for x in end_match.group(1).split(',')]
            if len(start_coords) >= 2 and len(end_coords) >= 2:
                args = {"action": "swipe", "coordinate": [start_coords[0], start_coords[1]],
                        "coordinate2": [end_coords[0], end_coords[1]]}

    elif action_type == 'type':
        # type(content='xxx')
        content_match = re.search(r"content='([^']*)'", action_str)
        if content_match:
            args = {"action": "type", "text": content_match.group(1)}

    elif action_type == 'open_app':
        # open_app(app_name='xxx')
        app_match = re.search(r"app_name='([^']*)'", action_str)
        if app_match:
            args = {"action": "open_app", "app_name": app_match.group(1)}

    elif action_type == 'press_home':
        args = {"action": "home"}

    elif action_type == 'press_back':
        args = {"action": "back"}

    elif action_type == 'finished':
        args = {"action": "terminate"}

    if args:
        return {"name": "mobile_use", "arguments": args}
    return None


def parse_action_blocks(block: str, model_name: str = '') -> list:
    """Parse action response blocks from log content.

    Supports multiple model formats based on actual log samples:
    - GUI-Owl-7B: tuple format with <thinking>/<conclusion> tags
    - GUI-Owl-1.5-Instruct: plain text Action: + JSON (no tuple)
    - GUI-Owl-1.5-Think: tuple format with thinking as first element
    - Qwen3-VL-4B (action_response): tuple with <thinking>/<conclusion> tags
    - Qwen3-VL (qwen3vl): tuple format, first element is thinking
    - UI-TARS: plain text Thought: ... Action: ...
    """
    import ast
    steps = []

    # Determine if coordinates need conversion (0-1000 -> pixels)
    needs_conversion = any(m in model_name for m in NORMALIZED_COORD_MODELS)

    # Split by response markers
    markers = [
        r'==========\s*action_response\s*==========',
        r'==========\s*gui_owl_1_5\s+response\s*==========',
        r'==========\s*qwen3vl\s+response\s*==========',
        r'==========\s*mai_ui\s+response\s*==========',
    ]

    # Find all response blocks
    parts = [block]
    for marker in markers:
        new_parts = []
        for p in parts:
            new_parts.extend(re.split(marker, p))
        parts = new_parts

    for part in parts[1:]:  # Skip first empty part
        if not part.strip():
            continue

        step_data = {
            'thinking': '',
            'action': None,
            'conclusion': '',
        }

        # Check for UI-TARS format: Thought: ... Action: click(...)
        if re.search(r'Thought:.*Action:', part, re.DOTALL):
            tars_thought = re.search(r'Thought:\s*(.*?)(?=Action:|$)', part, re.DOTALL)
            tars_action = re.search(r'Action:\s*(\w+\([^)]*\))', part)

            if tars_thought:
                step_data['thinking'] = tars_thought.group(1).strip()

            if tars_action:
                action_str = tars_action.group(1)
                tool_call = parse_ui_tars_action(action_str)
                if tool_call:
                    # UI-TARS uses absolute pixel coordinates, no conversion
                    step_data['action'] = tool_call

            if re.search(r'Completed step\s+\d+', part):
                steps.append(step_data)
            continue

        # Check for tuple format (starts with '(' on a line)
        lines = part.split('\n')
        tuple_start = -1
        tuple_end = -1

        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith('('):
                tuple_start = i
            if stripped.endswith(')') and tuple_start >= 0:
                tuple_end = i
                break

        if tuple_start >= 0 and tuple_end >= 0:
            # GUI-Owl-1.5-Think format:
            # ('etheus...thinking...}<|end|>\n'
            #  'Action: action summary\n'
            #  'gc_team|{"name": ...}\n'  or just '{"name": ...}'
            #  'gc_team_end')

            tuple_content = '\n'.join(lines[tuple_start:tuple_end+1])

            # First, find JSON directly in the whole content using brace counting
            json_start = tuple_content.find('{"name":')
            if json_start >= 0:
                # Count braces to find the end of JSON
                depth = 0
                for i in range(json_start, len(tuple_content)):
                    if tuple_content[i] == '{':
                        depth += 1
                    elif tuple_content[i] == '}':
                        depth -= 1
                        if depth == 0:
                            json_str = tuple_content[json_start:i+1]
                            # Clean JSON: remove '\n ' patterns from multi-line strings
                            json_str = re.sub(r"'\s*\n\s*'", '', json_str)
                            try:
                                tool_call = json.loads(json_str)
                                if needs_conversion:
                                    tool_call = convert_coordinates(tool_call)
                                step_data['action'] = tool_call
                            except json.JSONDecodeError:
                                pass
                            break

            # Extract all string literals from the tuple (both single and double quotes)
            string_matches = re.findall(r"""'([^']*)'|\"([^\"]*)\"""", tuple_content)
            # Flatten matches (each match is a tuple of two groups)
            all_strings = [m[0] if m[0] else m[1] for m in string_matches]

            if all_strings:
                thinking_parts = []
                action_summary = ''

                for s in all_strings:
                    s_clean = s.strip()
                    if s_clean.startswith('Action:'):
                        action_summary = s_clean[7:].strip()
                    elif s_clean.startswith('consult_team|') or s_clean.startswith('gc_team|'):
                        pass  # JSON already extracted above
                    elif s_clean == 'consult_team_end' or s_clean == 'gc_team_end':
                        pass  # Skip end marker
                    elif s_clean.startswith('{"name":'):
                        pass  # JSON already extracted above
                    elif not action_summary:  # Before Action:, it's thinking
                        thinking_parts.append(s)

                # Combine thinking parts
                if thinking_parts:
                    full_thinking = ' '.join(thinking_parts)
                    # Clean special tokens at start
                    full_thinking = re.sub(r"^'?\w*etheus\s*", '', full_thinking)
                    # Clean }<|end|> marker
                    full_thinking = re.sub(r"\}\s*<\|end\|>.*", '', full_thinking)
                    step_data['thinking'] = full_thinking.strip()
                    if action_summary:
                        step_data['thinking'] += '\n\nAction: ' + action_summary

            # Also check for <thinking> tag content (Qwen3-VL-4B format)
            think_match = re.search(r'<thinking>(.*?)</thinking>', tuple_content, re.DOTALL)
            if think_match:
                step_data['thinking'] = think_match.group(1).strip()

            # Extract <conclusion> tag content
            concl_match = re.search(r'<conclusion>(.*?)</conclusion>', tuple_content, re.DOTALL)
            if concl_match:
                step_data['conclusion'] = concl_match.group(1).strip()

        else:
            # Plain text format (GUI-Owl-1.5-Instruct style)
            # Format: Action: ... \n\n {"name": ...} or Action: ... \n<|start|>\n{"name":...}

            # Clean special tokens from the part first
            # These tokens may appear as decoded special markers from the model
            cleaned_part = part
            # Remove <|start|> / <|box_start|> style markers (decoded as various strings)
            cleaned_part = re.sub(r'\n?\s*<\|?\w*_?start\|?>\s*\n?', '\n', cleaned_part)
            cleaned_part = re.sub(r'\n?\s*<\|?\w*_?end\|?>\s*\n?', '\n', cleaned_part)
            # Also handle decoded markers like 'start' / 'endent' without brackets
            cleaned_part = re.sub(r'\n\s*start\s*\n', '\n', cleaned_part)
            cleaned_part = re.sub(r'\n\s*endent\s*\n', '\n', cleaned_part)

            # Extract Action text - stop before JSON or special markers
            action_match = re.search(r'Action:\s*(.*?)(?=\n\n|\n\s*\{"name"|{"name"|Parsed action)', cleaned_part, re.DOTALL)
            if action_match:
                thinking_text = action_match.group(1).strip()
                # Remove any remaining special token fragments
                thinking_text = re.sub(r'<\|?\w*\|?>', '', thinking_text)
                thinking_text = re.sub(r'\s*endent\s*', '', thinking_text)
                step_data['thinking'] = thinking_text.strip()

            # Extract JSON tool call
            json_match = re.search(r'\{"name":\s*"[^"]+",\s*"arguments":\s*\{.*?\}\s*\}', cleaned_part, re.DOTALL)
            if json_match:
                try:
                    tool_call = json.loads(json_match.group(0))
                    if needs_conversion:
                        tool_call = convert_coordinates(tool_call)
                    step_data['action'] = tool_call
                except json.JSONDecodeError:
                    pass

        # Check Completed step marker
        if re.search(r'Completed step\s+\d+', part):
            steps.append(step_data)

    return steps


def _count_tasks_in_traj(traj_path: str) -> int:
    """Count task directories inside a trajectory path (handles worker_X subdirs)."""
    task_count = 0
    for item in os.listdir(traj_path):
        item_path = os.path.join(traj_path, item)
        if item.startswith('worker_') and os.path.isdir(item_path):
            task_count += len([d for d in os.listdir(item_path)
                              if os.path.isdir(os.path.join(item_path, d))])
        elif os.path.isdir(item_path):
            task_count += 1
    return task_count


def _parse_trap_config(traj_name: str) -> str:
    """Parse trap config string from trajectory directory name."""
    trap_match = re.search(r'_(\w+)_(\w+)_(\d{4}-\d{2}-\d{2})', traj_name)
    if trap_match:
        cat = trap_match.group(1)
        typ = trap_match.group(2)
        if cat != 'none':
            return f'{cat}/{typ}'
    return 'origin'


def scan_trajectory_dirs() -> dict:
    """Scan trajectory directories and return structured data.

    Supports both flat and category-subdirectory layouts:
      trajectory/{group}/{model}/traj_xxx/...           (flat / origin)
      trajectory/{group}/{model}/{category}/traj_xxx/... (trap with TRAP_SUBDIR)
    """
    result = {'origin': {}, 'trap': {}}

    for group in ('origin', 'trap'):
        group_dir = os.path.join('trajectory', group)
        if not os.path.isdir(group_dir):
            continue

        for model in sorted(os.listdir(group_dir)):
            model_dir = os.path.join(group_dir, model)
            if not os.path.isdir(model_dir):
                continue

            for entry in sorted(os.listdir(model_dir)):
                entry_path = os.path.join(model_dir, entry)
                if not os.path.isdir(entry_path):
                    continue

                if entry in KNOWN_CATEGORY_DIRS:
                    # Category subdirectory — iterate traj dirs inside
                    for traj_name in sorted(os.listdir(entry_path)):
                        traj_path = os.path.join(entry_path, traj_name)
                        if not os.path.isdir(traj_path):
                            continue
                        rel_path = os.path.join('trajectory', group, model, entry, traj_name)
                        result[group].setdefault(model, []).append({
                            'name': traj_name,
                            'path': rel_path,
                            'task_count': _count_tasks_in_traj(traj_path),
                            'trap_config': _parse_trap_config(traj_name),
                        })
                else:
                    # Direct traj directory (backward-compatible)
                    rel_path = os.path.join('trajectory', group, model, entry)
                    result[group].setdefault(model, []).append({
                        'name': entry,
                        'path': rel_path,
                        'task_count': _count_tasks_in_traj(entry_path),
                        'trap_config': _parse_trap_config(entry),
                    })

    return result


def find_log_for_trajectory(traj_path: str) -> str:
    """Find the corresponding log file for a trajectory directory.

    Supports both flat and category-subdirectory layouts:
      log/{group}/{model}/log_xxx.log                   (flat)
      log/{group}/{model}/{category}/log_xxx.log         (with TRAP_SUBDIR)
    """
    basename = os.path.basename(traj_path)
    if basename.startswith('traj_'):
        log_name = 'log_' + basename[5:] + '.log'
    else:
        log_name = basename + '.log'

    parts = traj_path.split(os.sep)
    group = parts[1] if len(parts) > 1 else 'trap'
    model = parts[2] if len(parts) > 2 else ''

    # Collect any subdirs between model and the traj dir (e.g., 'a_layer')
    subdirs = parts[3:-1] if len(parts) > 4 else []

    log_path = os.path.join('log', group, model, *subdirs, log_name)
    if os.path.isfile(log_path):
        return log_path

    # Fallback: try without subdirs (backward compatibility)
    if subdirs:
        log_path_flat = os.path.join('log', group, model, log_name)
        if os.path.isfile(log_path_flat):
            return log_path_flat

    return None


def parse_log_file(log_path: str, model_name: str = '') -> dict:
    """Parse log file to extract tasks with steps, goals, actions, and trap events.

    Supports multiple log formats:
    - Format 1: [1/116] TaskName_0: OK  (5 steps, 41.6s) - standard AndroidWorld format
    - Format 2: GUI-Owl-1.5 style - summary table at end
    - Format 3: GUI-Owl-7B style - "Running task TaskName" + "Task Successful/Failed"
    """
    tasks = {}

    with open(log_path, 'r', errors='replace') as f:
        content = f.read()

    # Format 1: Standard with [1/116] markers
    task_pattern = r'\[(\d+)/\d+\]\s+(\S+):\s+(\S+)\s+\((\d+)\s+steps'
    for match in re.finditer(task_pattern, content):
        task_name = match.group(2)
        status = match.group(3)
        steps = int(match.group(4))
        tasks[task_name] = {
            'status': status,
            'steps': steps,
            'goal': '',
            'trap_events': [],
            'steps_data': [],
        }

    # Format 2: GUI-Owl-1.5 style - parse from summary table at end
    # Table format: TaskName   0   1.0   1.0   8.0   72.7   0.0
    if not tasks:
        # Find the summary table
        table_pattern = r'^(\w+)\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)'
        for match in re.finditer(table_pattern, content, re.MULTILINE):
            task_name = match.group(1)
            success_rate = float(match.group(4))
            steps = int(float(match.group(5)))
            tasks[task_name + '_0'] = {
                'status': 'OK' if success_rate > 0.5 else 'FAIL',
                'steps': steps,
                'goal': '',
                'trap_events': [],
                'steps_data': [],
            }

    # Format 3: GUI-Owl-7B style - Running task + Task Successful/Failed markers
    if not tasks:
        # Find all "Running task TaskName with goal" blocks
        running_pattern = r'Running task\s+(\w+)\s+with goal\s+"([^"]+)"'
        # Find task boundaries: each "Running task" starts a new task section
        task_sections = []
        for match in re.finditer(running_pattern, content):
            task_sections.append({
                'name': match.group(1),
                'goal': match.group(2),
                'start': match.start(),
            })

        # For each task section, find its end (next task or end of file)
        for i, section in enumerate(task_sections):
            # Find end of this task section
            if i + 1 < len(task_sections):
                end = task_sections[i + 1]['start']
            else:
                # Look for summary table or end of file
                avg_match = re.search(r'========= Average', content[section['start']:])
                if avg_match:
                    end = section['start'] + avg_match.start()
                else:
                    end = len(content)

            # Extract this task's content
            task_block = content[section['start']:end]

            # Determine status
            status = 'unknown'
            if re.search(r'Task Successful', task_block):
                status = 'OK'
            elif re.search(r'Task Failed', task_block):
                status = 'FAIL'

            # Count steps (Completed step markers)
            step_matches = re.findall(r'Completed step\s+\d+', task_block)
            steps = len(step_matches)

            tasks[section['name']] = {
                'status': status,
                'steps': steps,
                'goal': section['goal'],
                'trap_events': [],
                'steps_data': [],
                'block': task_block,  # Store block for later parsing
            }

    # Find goals for existing tasks (Format 1 & 2)
    goal_pattern = r'Running task:?\s+(\w+)\s+with goal\s+"([^"]+)"'
    for match in re.finditer(goal_pattern, content):
        task_base = match.group(1)
        goal = match.group(2)
        for name in tasks:
            if name == task_base or name.startswith(task_base + '_'):
                tasks[name]['goal'] = goal
                break

    # Parse per-step content for each task
    for task_name in tasks:
        task_block = tasks[task_name].get('block', '')

        if task_block:
            # Already have the block from Format 3
            tasks[task_name]['steps_data'] = parse_action_blocks(task_block, model_name)
            continue

        # Try multiple patterns to find task block

        # Pattern 1: [1/116] task_name: ...
        task_pattern_block = rf'\[\d+/\d+\]\s+{re.escape(task_name)}:\s+\S+\s*\([^)]+\)'
        match = re.search(task_pattern_block, content)

        if match:
            start = match.start()
            next_match = re.search(r'\[\d+/\d+\]\s+\S+:\s+\S+\s*\([^)]+\)', content[start + 1:])
            if next_match:
                end = start + 1 + next_match.start()
            else:
                end = len(content)
            block = content[start:end]
            tasks[task_name]['steps_data'] = parse_action_blocks(block, model_name)
            continue

        # Pattern 2: Running task: TaskName (GUI-Owl-1.5 style)
        task_base = task_name.rstrip('_0123456789')
        # Match "Running task TaskName with goal" (the actual task start)
        task_header = rf'Running task\s+{re.escape(task_base)}\s+with goal'
        match = re.search(task_header, content)

        if match:
            # Find the start of the section
            section_start = match.start()

            # Find next task or end
            next_match = re.search(r'(========= Average|Running task:?\s+\w+\s*$)', content[section_start + 50:])
            if next_match:
                end = section_start + 50 + next_match.start()
            else:
                end = len(content)

            block = content[section_start:end]
            tasks[task_name]['steps_data'] = parse_action_blocks(block, model_name)

    # Find trap events: [TRAP] step=2 event=loop_back_injected
    trap_pattern = r'\[TRAP\]\s+step=(\d+)\s+event=(\S+)'
    current_task = None
    for line in content.split('\n'):
        task_marker = re.search(r'\[\d+/\d+\]\s+(\S+):', line)
        if task_marker:
            current_task = task_marker.group(1)
        # Also check for GUI-Owl-1.5 style
        running_match = re.search(r'Running task:?\s+(\w+)', line)
        if running_match:
            task_base = running_match.group(1)
            for name in tasks:
                if name == task_base or name.startswith(task_base + '_'):
                    current_task = name
                    break

        trap_match = re.search(trap_pattern, line)
        if trap_match and current_task and current_task in tasks:
            step = int(trap_match.group(1))
            event = trap_match.group(2)
            tasks[current_task]['trap_events'].append({
                'step': step,
                'event': event
            })

    return tasks


def parse_action_jsonl(jsonl_path: str) -> list:
    """Parse action.jsonl file to extract step data."""
    steps = []
    if not os.path.isfile(jsonl_path):
        return steps

    with open(jsonl_path, 'r') as f:
        for line in f:
            if line.strip():
                try:
                    data = json.loads(line)
                    # GUI-Owl-7B uses absolute pixel coordinates, no conversion needed
                    steps.append({'action': data, 'thinking': '', 'conclusion': ''})
                except json.JSONDecodeError:
                    pass
    return steps


def get_trajectory_data(traj_path: str) -> dict:
    """Get full trajectory data for a specific path."""
    if not os.path.isdir(traj_path):
        return {'error': 'Trajectory directory not found'}

    # Extract model name from path: trajectory/{group}/{MODEL}/traj_xxx/...
    path_parts = traj_path.split(os.sep)
    model_name = ''
    try:
        # Find 'trajectory' in path and get the model name after group
        if 'trajectory' in path_parts:
            traj_idx = path_parts.index('trajectory')
            if len(path_parts) > traj_idx + 2:
                model_name = path_parts[traj_idx + 2]
    except (ValueError, IndexError):
        pass

    log_path = find_log_for_trajectory(traj_path)
    log_tasks = {}
    if log_path:
        log_tasks = parse_log_file(log_path, model_name)

    trajectories = []

    # Collect all task directories - handle both worker_X subdirs and direct task dirs
    task_dirs = []  # List of (task_name, task_path, worker_name or None)

    for item in sorted(os.listdir(traj_path)):
        item_path = os.path.join(traj_path, item)
        if not os.path.isdir(item_path):
            continue

        if item.startswith('worker_'):
            # Worker subdirectory structure - collect tasks inside
            for task_name in sorted(os.listdir(item_path)):
                task_path = os.path.join(item_path, task_name)
                if os.path.isdir(task_path):
                    task_dirs.append((task_name, task_path, item))  # item is worker_X
        else:
            # Direct task directory (no worker subdirs)
            # Check if it contains screenshots (indicates it's a task dir)
            screenshots = [f for f in os.listdir(item_path)
                          if f.startswith('screenshot_') and f.endswith('.png')]
            if screenshots:
                task_dirs.append((item, item_path, None))  # No worker subdir

    for task_name, task_path, worker_name in task_dirs:

            screenshots = sorted([f for f in os.listdir(task_path)
                                  if f.startswith('screenshot_') and f.endswith('.png')])

            # Get task info from log
            # Log has names like "TaskName_0", trajectory dir has "TaskName"
            task_info = None
            # Try exact match first
            if task_name in log_tasks:
                task_info = log_tasks[task_name]
            else:
                # Try matching with _0, _1, _2 suffixes
                for suffix in ['_0', '_1', '_2', '_3', '_4']:
                    if task_name + suffix in log_tasks:
                        task_info = log_tasks[task_name + suffix]
                        break

            if not task_info:
                task_info = {'status': 'unknown', 'steps': len(screenshots), 'goal': '',
                            'trap_events': [], 'steps_data': []}

            # Use steps_data from log if available, else from action.jsonl
            steps_data = task_info.get('steps_data', [])
            if not steps_data:
                jsonl_path = os.path.join(task_path, 'action.jsonl')
                steps_data = parse_action_jsonl(jsonl_path)

            # Ensure steps count matches
            steps = task_info.get('steps', len(screenshots))

            trajectories.append({
                'name': task_name,
                'status': task_info.get('status', 'unknown'),
                'steps': steps,
                'goal': task_info.get('goal', ''),
                'trap_events': task_info.get('trap_events', []),
                'screenshots': screenshots,
                'steps_data': steps_data,
                'worker': worker_name,  # worker_X or None
            })

    return {
        'path': traj_path,
        'log_file': os.path.basename(log_path) if log_path else None,
        'trajectories': trajectories
    }


def build_html(traj_dirs: dict) -> str:
    """Generate the main HTML viewer."""

    traj_dirs_json = json.dumps(traj_dirs, ensure_ascii=False)

    html = '''<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Trajectory Viewer</title>
  <style>
    :root {
      --primary: #2563eb;
      --success: #16a34a;
      --danger: #dc2626;
      --warning: #f59e0b;
      --bg: #f8fafc;
      --card-bg: #ffffff;
      --text-main: #0f172a;
      --text-muted: #64748b;
      --border: #e2e8f0;
    }

    * { box-sizing: border-box; }

    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: var(--bg);
      color: var(--text-main);
      margin: 0;
      display: flex;
      height: 100vh;
      overflow: hidden;
    }

    #sidebar {
      width: 300px;
      background: var(--card-bg);
      border-right: 1px solid var(--border);
      display: flex;
      flex-direction: column;
      flex-shrink: 0;
    }

    .sidebar-header {
      padding: 16px;
      border-bottom: 1px solid var(--border);
      font-weight: 600;
      background: #f1f5f9;
    }

    .selector-area {
      padding: 12px 16px;
      border-bottom: 1px solid var(--border);
    }

    .selector-area label {
      display: block;
      font-size: 0.8rem;
      color: var(--text-muted);
      margin-bottom: 4px;
    }

    .selector-area select {
      width: 100%;
      padding: 8px;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      font-size: 0.9rem;
    }

    .sidebar-stats {
      padding: 12px 16px;
      font-size: 0.85rem;
      color: var(--text-muted);
      border-bottom: 1px solid var(--border);
      background: #fafafa;
    }

    .task-list {
      flex: 1;
      overflow-y: auto;
    }

    .task-item {
      padding: 10px 16px;
      cursor: pointer;
      border-left: 3px solid transparent;
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 0.85rem;
      border-bottom: 1px solid #f1f5f9;
    }

    .task-item:hover { background: #f8fafc; }
    .task-item.active {
      background: #eff6ff;
      border-left-color: var(--primary);
      font-weight: 600;
    }

    .status-dot {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      flex-shrink: 0;
    }

    .status-ok { background: var(--success); }
    .status-fail { background: var(--danger); }

    .trap-badge {
      background: var(--warning);
      color: white;
      font-size: 0.7rem;
      padding: 2px 6px;
      border-radius: 999px;
      font-weight: 600;
    }

    .main-content {
      flex: 1;
      overflow-y: auto;
      padding: 24px;
    }

    .header {
      margin-bottom: 24px;
    }

    .header h1 {
      font-size: 1.25rem;
      margin: 0 0 8px 0;
    }

    .goal-box {
      background: #e0f2fe;
      padding: 12px 16px;
      border-radius: 8px;
      border-left: 4px solid #0ea5e9;
      margin-bottom: 12px;
    }

    .status-badge {
      display: inline-block;
      padding: 4px 12px;
      border-radius: 999px;
      font-size: 0.8rem;
      font-weight: 600;
      text-transform: uppercase;
    }

    .status-badge.ok { background: #dcfce7; color: #166534; }
    .status-badge.fail { background: #fee2e2; color: #991b1b; }

    .nav-buttons {
      margin-top: 16px;
      display: flex;
      gap: 12px;
    }

    .nav-btn {
      padding: 8px 16px;
      background: #f8fafc;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 500;
    }

    .nav-btn:hover { background: #f1f5f9; border-color: var(--primary); }

    .step-nav {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 24px;
      padding: 12px;
      background: white;
      border-radius: 8px;
      border: 1px solid var(--border);
    }

    .step-nav-btn {
      padding: 6px 12px;
      background: #f8fafc;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      cursor: pointer;
      font-weight: 500;
      font-size: 0.9rem;
    }

    .step-nav-btn:hover { border-color: var(--primary); color: var(--primary); }
    .step-nav-btn.has-trap {
      border-color: var(--warning);
      background: #fffbeb;
      color: #d97706;
    }

    .step {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      margin-bottom: 24px;
      display: flex;
      overflow: hidden;
    }

    .step-img {
      padding: 16px;
      background: #f8fafc;
      border-right: 1px solid var(--border);
      min-width: 320px;
      display: flex;
      align-items: flex-start;
      justify-content: center;
    }

    .img-container {
      position: relative;
      display: inline-block;
    }

    .img-container img {
      max-width: 280px;
      border-radius: 8px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }

    .overlay {
      position: absolute;
      left: 0;
      top: 0;
      pointer-events: none;
      width: 100%;
      height: 100%;
    }

    .step-content {
      flex: 1;
      padding: 16px;
    }

    .step-title {
      font-size: 1.1rem;
      font-weight: 600;
      color: var(--primary);
      margin-bottom: 12px;
      padding-bottom: 8px;
      border-bottom: 2px solid var(--border);
    }

    .info-block {
      background: #f1f5f9;
      padding: 12px 16px;
      border-radius: 8px;
      margin-bottom: 12px;
      border-left: 4px solid var(--text-muted);
    }

    .info-block strong {
      display: block;
      font-size: 0.8rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 4px;
    }

    .info-block.action { border-left-color: var(--warning); }
    .info-block.action strong { color: #d97706; }

    .info-block.thinking { border-left-color: #6366f1; }
    .info-block.thinking strong { color: #6366f1; }

    .info-block.conclusion { border-left-color: var(--success); }
    .info-block.conclusion strong { color: var(--success); }

    .info-block.trap {
      border-left-color: var(--danger);
      background: #fef2f2;
    }
    .info-block.trap strong { color: var(--danger); }

    .note-area {
      margin-top: 24px;
      padding: 16px;
      background: #fffbeb;
      border-radius: 8px;
      border: 1px solid #fcd34d;
    }

    .note-area textarea {
      width: 100%;
      min-height: 80px;
      padding: 8px;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      font-family: inherit;
      resize: vertical;
    }

    .note-area button {
      margin-top: 8px;
      padding: 6px 16px;
      background: var(--primary);
      color: white;
      border: none;
      border-radius: 6px;
      cursor: pointer;
    }

    .placeholder {
      text-align: center;
      padding: 60px 20px;
      color: var(--text-muted);
    }
  </style>
</head>
<body>
  <div id="sidebar">
    <div class="sidebar-header">Trajectory Viewer</div>

    <div class="selector-area">
      <label>Group</label>
      <select id="groupSelect" onchange="onGroupChange()">
        <option value="trap">Trap</option>
        <option value="origin">Origin</option>
      </select>
    </div>

    <div class="selector-area">
      <label>Model</label>
      <select id="modelSelect" onchange="onModelChange()"></select>
    </div>

    <div class="selector-area">
      <label>Trajectory</label>
      <select id="trajSelect" onchange="onTrajChange()"></select>
    </div>

    <div class="sidebar-stats" id="statsInfo">Select a trajectory</div>

    <div class="task-list" id="taskList"></div>
  </div>

  <div class="main-content" id="mainContent">
    <div class="placeholder">
      <h2>Trajectory Viewer</h2>
      <p>Select a trajectory to view</p>
    </div>
  </div>

  <script>
    const trajDirs = __TRAJ_DIRS__;
    let currentTraj = null;
    let currentTrajData = null;
    let currentTaskIdx = 0;
    let notes = {};

    function init() {
      // Restore from URL hash if available
      restoreFromUrl();
      if (!document.getElementById('trajSelect').value) {
        onGroupChange();
      }
    }

    function updateUrlState() {
      const group = document.getElementById('groupSelect').value;
      const model = document.getElementById('modelSelect').value;
      const traj = document.getElementById('trajSelect').value;
      const task = currentTaskIdx;

      const params = new URLSearchParams();
      if (group) params.set('group', group);
      if (model) params.set('model', model);
      if (traj) params.set('traj', traj);
      if (task) params.set('task', task);

      window.history.replaceState(null, '', '#' + params.toString());
    }

    async function restoreFromUrl() {
      const hash = window.location.hash.slice(1);
      if (!hash) return;

      const params = new URLSearchParams(hash);
      const group = params.get('group');
      const model = params.get('model');
      const traj = params.get('traj');
      const task = parseInt(params.get('task') || '0');

      if (group) {
        document.getElementById('groupSelect').value = group;
        onGroupChange();
      }

      if (model) {
        // Wait for model select to be populated
        setTimeout(() => {
          document.getElementById('modelSelect').value = model;
          onModelChange();
        }, 50);
      }

      if (traj) {
        // Wait for traj select to be populated
        setTimeout(async () => {
          document.getElementById('trajSelect').value = traj;
          await onTrajChange();
          if (task > 0 && currentTrajData) {
            setTimeout(() => selectTask(task), 100);
          }
        }, 150);
      }
    }

    function onGroupChange() {
      const group = document.getElementById('groupSelect').value;
      const models = Object.keys(trajDirs[group] || {});

      const modelSelect = document.getElementById('modelSelect');
      modelSelect.innerHTML = '';
      models.forEach(m => {
        const opt = document.createElement('option');
        opt.value = m;
        opt.textContent = m;
        modelSelect.appendChild(opt);
      });

      updateUrlState();
      if (models.length > 0) onModelChange();
    }

    function onModelChange() {
      const group = document.getElementById('groupSelect').value;
      const model = document.getElementById('modelSelect').value;
      const trajs = trajDirs[group]?.[model] || [];

      const trajSelect = document.getElementById('trajSelect');
      trajSelect.innerHTML = '';
      trajs.forEach(t => {
        const opt = document.createElement('option');
        opt.value = t.path;
        opt.textContent = t.name + ' (' + t.task_count + ' tasks, ' + t.trap_config + ')';
        trajSelect.appendChild(opt);
      });

      updateUrlState();
      if (trajs.length > 0) onTrajChange();
    }

    async function onTrajChange() {
      const trajPath = document.getElementById('trajSelect').value;
      if (!trajPath) return;

      updateUrlState();
      try {
        const resp = await fetch('/api/traj?path=' + encodeURIComponent(trajPath));
        if (resp.ok) {
          currentTrajData = await resp.json();
          if (currentTrajData.error) {
            document.getElementById('mainContent').innerHTML = '<div class="placeholder"><h2>Error</h2><p>' + currentTrajData.error + '</p></div>';
            return;
          }
          currentTraj = trajPath;
          currentTaskIdx = 0;
          notes = JSON.parse(localStorage.getItem('notes_' + trajPath) || '{}');
          renderTrajectory();
        }
      } catch (e) {
        console.error(e);
      }
    }

    function renderTrajectory() {
      if (!currentTrajData) return;

      const trajPath = currentTrajData.path;
      const logFile = currentTrajData.log_file;
      const trajectories = currentTrajData.trajectories || [];

      const ok = trajectories.filter(t => t.status === 'OK').length;
      const total = trajectories.length;
      const avgSteps = trajectories.reduce((s, t) => s + (t.steps || 0), 0) / (total || 1);
      const traps = trajectories.reduce((s, t) => s + ((t.trap_events || []).length), 0);

      document.getElementById('statsInfo').innerHTML = `
        <div><strong>Log:</strong> ${logFile || 'N/A'}</div>
        <div><strong>Tasks:</strong> ${ok}/${total} OK</div>
        <div><strong>Avg Steps:</strong> ${avgSteps.toFixed(1)}</div>
        <div><strong>Traps:</strong> ${traps} events</div>
      `;

      const taskList = document.getElementById('taskList');
      taskList.innerHTML = '';

      trajectories.forEach((traj, idx) => {
        const item = document.createElement('div');
        item.className = 'task-item' + (idx === currentTaskIdx ? ' active' : '');
        item.onclick = () => selectTask(idx);

        const dot = document.createElement('span');
        dot.className = 'status-dot ' + (traj.status === 'OK' ? 'status-ok' : 'status-fail');

        const name = document.createElement('span');
        name.textContent = traj.name;
        name.style.flex = '1';
        name.style.overflow = 'hidden';
        name.style.textOverflow = 'ellipsis';
        name.style.whiteSpace = 'nowrap';

        item.appendChild(dot);
        item.appendChild(name);

        if ((traj.trap_events || []).length > 0) {
          const badge = document.createElement('span');
          badge.className = 'trap-badge';
          badge.textContent = (traj.trap_events || []).length;
          item.appendChild(badge);
        }

        taskList.appendChild(item);
      });

      selectTask(currentTaskIdx);
    }

    function selectTask(idx) {
      if (!currentTrajData) return;
      currentTaskIdx = idx;
      updateUrlState();
      const traj = currentTrajData.trajectories[idx];

      // Update sidebar active state
      document.querySelectorAll('.task-item').forEach((item, i) => {
        item.classList.toggle('active', i === idx);
      });

      // Render header
      let html = `
        <div class="header">
          <h1>${traj.name}</h1>
          <div class="goal-box"><strong>Goal:</strong> ${traj.goal || 'N/A'}</div>
          <span class="status-badge ${traj.status === 'OK' ? 'ok' : 'fail'}">${traj.status}</span>
          <span style="margin-left: 16px; color: var(--text-muted);">${traj.steps || 0} steps</span>
          ${(traj.trap_events || []).length > 0 ? '<span class="trap-badge" style="margin-left: 16px;">' + traj.trap_events.length + ' traps</span>' : ''}

          <div class="nav-buttons">
            <button class="nav-btn" onclick="prevTask()">← Previous</button>
            <button class="nav-btn" onclick="nextTask()">Next →</button>
          </div>
        </div>
        <div id="stepsContainer"></div>
      `;

      document.getElementById('mainContent').innerHTML = html;

      renderSteps(traj);
    }

    function prevTask() {
      if (!currentTrajData || currentTaskIdx <= 0) return;
      selectTask(currentTaskIdx - 1);
    }

    function nextTask() {
      if (!currentTrajData || currentTaskIdx >= currentTrajData.trajectories.length - 1) return;
      selectTask(currentTaskIdx + 1);
    }

    function renderSteps(traj) {
      const container = document.getElementById('stepsContainer');
      const trajPath = currentTraj;
      const workerPath = traj.worker ? trajPath + '/' + traj.worker : trajPath;

      // Step navigation
      let navHtml = '<div class="step-nav">';
      for (let i = 0; i < traj.steps; i++) {
        const hasTrap = (traj.trap_events || []).some(e => e.step === i);
        navHtml += `<button class="step-nav-btn ${hasTrap ? 'has-trap' : ''}" onclick="scrollToStep(${i})">Step ${i}</button>`;
      }
      navHtml += '</div>';
      container.innerHTML = navHtml;

      // Render each step using DOM (like error_analysis_html_CH.py)
      for (let i = 0; i < traj.steps; i++) {
        const stepData = traj.steps_data[i] || {};
        const trapEvents = (traj.trap_events || []).filter(e => e.step === i);
        const screenshot = traj.screenshots[i] || '';

        // Step container
        const stepDiv = document.createElement('div');
        stepDiv.className = 'step';
        stepDiv.id = 'step-' + i;

        // Image column
        const imgCol = document.createElement('div');
        imgCol.className = 'step-img';

        const imgWrap = document.createElement('div');
        imgWrap.className = 'img-container';

        if (screenshot) {
          const img = document.createElement('img');
          img.src = '/screenshot?path=' + encodeURIComponent(workerPath + '/' + traj.name + '/' + screenshot);
          img.alt = 'Step ' + i;
          imgWrap.appendChild(img);

          // SVG overlay
          const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
          svg.setAttribute('class', 'overlay');
          svg.style.width = '100%';
          svg.style.height = '100%';
          svg.style.position = 'absolute';
          svg.style.left = '0';
          svg.style.top = '0';
          imgWrap.appendChild(svg);

          // Draw marker when image loads
          img.onload = function() {
            svg.setAttribute('width', img.width);
            svg.setAttribute('height', img.height);
            svg.setAttribute('viewBox', '0 0 ' + img.naturalWidth + ' ' + img.naturalHeight);
            drawMarker(svg, stepData.action);
          };
        }
        imgCol.appendChild(imgWrap);
        stepDiv.appendChild(imgCol);

        // Content column
        const contentCol = document.createElement('div');
        contentCol.className = 'step-content';

        const stepTitle = document.createElement('div');
        stepTitle.className = 'step-title';
        stepTitle.textContent = 'Step ' + i;
        contentCol.appendChild(stepTitle);

        // Trap events
        trapEvents.forEach(te => {
          const trapDiv = document.createElement('div');
          trapDiv.className = 'info-block trap';
          trapDiv.innerHTML = '<strong>TRAP</strong>' + escapeHtml(te.event);
          contentCol.appendChild(trapDiv);
        });

        // Thinking
        if (stepData.thinking) {
          const thinkDiv = document.createElement('div');
          thinkDiv.className = 'info-block thinking';
          thinkDiv.innerHTML = '<strong>Thinking</strong>' + escapeHtml(stepData.thinking);
          contentCol.appendChild(thinkDiv);
        }

        // Action
        if (stepData.action) {
          const args = stepData.action.arguments || {};
          const actionStr = JSON.stringify(args, null, 2);
          const actionDiv = document.createElement('div');
          actionDiv.className = 'info-block action';
          actionDiv.innerHTML = '<strong>Action</strong>' + (stepData.action.name || 'mobile_use') + '<br><code>' + escapeHtml(actionStr) + '</code>';
          contentCol.appendChild(actionDiv);
        }

        // Conclusion
        if (stepData.conclusion) {
          const conclDiv = document.createElement('div');
          conclDiv.className = 'info-block conclusion';
          conclDiv.innerHTML = '<strong>Conclusion</strong>' + escapeHtml(stepData.conclusion);
          contentCol.appendChild(conclDiv);
        }

        stepDiv.appendChild(contentCol);
        container.appendChild(stepDiv);
      }

      // Note area
      const note = notes[traj.name] || '';
      const noteArea = document.createElement('div');
      noteArea.className = 'note-area';
      noteArea.innerHTML = '<strong>Note:</strong><textarea id="noteInput">' + note + '</textarea><button onclick="saveNote()">Save Note</button>';
      container.appendChild(noteArea);
    }

    function drawMarker(svg, tool_call) {
      if (!svg || !tool_call) return;

      const args = tool_call.arguments || {};
      const act = args.action;
      const coord = args.coordinate;
      const coord2 = args.coordinate2;

      if (act === 'click' && coord && coord.length >= 2) {
        const [x, y] = coord;

        // Outer ring with animation
        const ring = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        ring.setAttribute('cx', x);
        ring.setAttribute('cy', y);
        ring.setAttribute('fill', 'rgba(255, 0, 0, 0.2)');
        ring.setAttribute('stroke', 'red');
        ring.setAttribute('stroke-width', '3');

        const animR = document.createElementNS('http://www.w3.org/2000/svg', 'animate');
        animR.setAttribute('attributeName', 'r');
        animR.setAttribute('values', '25; 65; 25');
        animR.setAttribute('dur', '1.5s');
        animR.setAttribute('repeatCount', 'indefinite');
        ring.appendChild(animR);

        const animOp = document.createElementNS('http://www.w3.org/2000/svg', 'animate');
        animOp.setAttribute('attributeName', 'opacity');
        animOp.setAttribute('values', '1; 0; 1');
        animOp.setAttribute('dur', '1.5s');
        animOp.setAttribute('repeatCount', 'indefinite');
        ring.appendChild(animOp);

        svg.appendChild(ring);

        // Shadow
        const shadow = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        shadow.setAttribute('cx', x);
        shadow.setAttribute('cy', y);
        shadow.setAttribute('r', 26);
        shadow.setAttribute('fill', 'rgba(0,0,0,0.4)');
        svg.appendChild(shadow);

        // Inner dot
        const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        dot.setAttribute('cx', x);
        dot.setAttribute('cy', y);
        dot.setAttribute('r', 20);
        dot.setAttribute('fill', 'red');
        dot.setAttribute('stroke', 'white');
        dot.setAttribute('stroke-width', '6');
        svg.appendChild(dot);

      } else if (act === 'swipe' && coord && coord2) {
        const [x1, y1] = coord;
        const [x2, y2] = coord2;

        // Shadow line
        const shadowLine = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        shadowLine.setAttribute('x1', x1);
        shadowLine.setAttribute('y1', y1);
        shadowLine.setAttribute('x2', x2);
        shadowLine.setAttribute('y2', y2);
        shadowLine.setAttribute('stroke', 'rgba(0,0,0,0.5)');
        shadowLine.setAttribute('stroke-width', 16);
        svg.appendChild(shadowLine);

        // Main line
        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('x1', x1);
        line.setAttribute('y1', y1);
        line.setAttribute('x2', x2);
        line.setAttribute('y2', y2);
        line.setAttribute('stroke', 'red');
        line.setAttribute('stroke-width', 8);
        svg.appendChild(line);

        // Start dot
        const startDot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        startDot.setAttribute('cx', x1);
        startDot.setAttribute('cy', y1);
        startDot.setAttribute('r', 18);
        startDot.setAttribute('fill', 'transparent');
        startDot.setAttribute('stroke', 'red');
        startDot.setAttribute('stroke-width', 6);
        svg.appendChild(startDot);

        // End dot
        const endDot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        endDot.setAttribute('cx', x2);
        endDot.setAttribute('cy', y2);
        endDot.setAttribute('r', 8);
        endDot.setAttribute('fill', 'black');
        endDot.setAttribute('stroke', 'white');
        endDot.setAttribute('stroke-width', 3);
        svg.appendChild(endDot);

      } else if (act === 'long_press' && coord) {
        const [x, y] = coord;

        const ring = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        ring.setAttribute('cx', x);
        ring.setAttribute('cy', y);
        ring.setAttribute('r', 25);
        ring.setAttribute('fill', 'rgba(255, 0, 0, 0.3)');
        ring.setAttribute('stroke', 'red');
        ring.setAttribute('stroke-width', 4);
        svg.appendChild(ring);

        const dot = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        dot.setAttribute('cx', x);
        dot.setAttribute('cy', y);
        dot.setAttribute('r', 10);
        dot.setAttribute('fill', 'darkred');
        svg.appendChild(dot);
      }
    }

    function escapeHtml(str) {
      return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function scrollToStep(idx) {
      document.getElementById('step-' + idx).scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    function saveNote() {
      if (!currentTrajData) return;
      const traj = currentTrajData.trajectories[currentTaskIdx];
      notes[traj.name] = document.getElementById('noteInput').value;
      localStorage.setItem('notes_' + currentTraj, JSON.stringify(notes));
      alert('Note saved!');
    }

    init();
  </script>
</body>
</html>'''

    return html.replace('__TRAJ_DIRS__', traj_dirs_json)


class TrajectoryHandler(http.server.BaseHTTPRequestHandler):
    """Custom handler for trajectory viewer API and static files."""

    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = self.path.split('?')[0]
        query = self.path.split('?')[1] if '?' in self.path else ''

        params = {}
        if query:
            for pair in query.split('&'):
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    params[k] = unquote(v)

        if parsed == '/':
            self.send_html(build_html(scan_trajectory_dirs()))
            return

        if parsed == '/api/traj':
            traj_path = params.get('path', '')
            if not traj_path:
                self.send_error(400, 'Missing path')
                return
            data = get_trajectory_data(traj_path)
            self.send_json(data)
            return

        if parsed == '/screenshot':
            img_path = params.get('path', '')
            if not img_path or not os.path.isfile(img_path):
                self.send_error(404, 'Image not found')
                return
            self.send_file(img_path, 'image/png')
            return

        self.send_error(404, 'Not found')

    def send_html(self, content):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))

    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def send_file(self, path, content_type):
        with open(path, 'rb') as f:
            content = f.read()
        self.send_response(200)
        self.send_header('Content-type', content_type)
        self.send_header('Content-length', len(content))
        self.end_headers()
        self.wfile.write(content)


def run_server(port: int = 8000):
    server = http.server.HTTPServer(('0.0.0.0', port), TrajectoryHandler)
    print(f"Server running at http://localhost:{port}")
    print("Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped")


def main():
    if not os.path.isdir('trajectory'):
        print("Error: trajectory/ directory not found")
        sys.exit(1)
    run_server()


if __name__ == '__main__':
    main()