"""GPT-5 agent for AndroidWorld using Set-of-Marks (M3A-style).

Motivation: the computer-use / pixel-grounding approaches (mobile_use,
OpenAI computer_use_preview, xy-based chat.completions) all fail on
gpt-5.4-mini because the model does not reliably localize in pixel
space. M3A solves this by rendering numbered bounding boxes over a11y
elements (Set-of-Marks) and letting the model pick an index.  This
module reuses AndroidWorld's official M3A prompt and SoM rendering,
swapping the LLM backend to our OpenAI-compat chat.completions wrapper.

Additions on top of M3A:
- Trajectory persistence (output_path, task_name).
- Initial home + swipe-up in reset() for a consistent start state.
- Trap hooks (on_screenshot, on_action, should_block_execution).

The agent expects ``llm.predict_mm(prompt, images)`` to exist on the LLM
wrapper (it does on ``Gpt5Wrapper``).  Images are numpy arrays; M3A
always sends [raw_screenshot, som_screenshot] during action selection
and [before_som, after_som] during summarisation.
"""

import json
import logging
import os
import time
from typing import Any

import numpy as np
from android_world.agents import agent_utils
from android_world.agents import base_agent
from android_world.agents import infer_gpt5
from android_world.agents import m3a
from android_world.agents import m3a_utils
from android_world.env import adb_utils
from android_world.env import interface
from android_world.env import json_action
from PIL import Image


class Gpt5Agent(base_agent.EnvironmentInteractingAgent):
    """M3A-style SoM agent backed by Gpt5Wrapper (chat.completions)."""

    def __init__(
        self,
        env: interface.AsyncEnv,
        llm: 'infer_gpt5.Gpt5Wrapper',
        name: str = 'Gpt5',
        max_history_images: int = 3,  # kept for CLI compat; unused here
        output_path: str = '',
        task_name: dict | None = None,
        wait_after_action_seconds: float = 2.0,
    ):
        super().__init__(env, name)
        del max_history_images  # M3A uses a text summary history instead.
        self.llm = llm
        self.history: list[dict] = []
        self.additional_guidelines: list[str] | None = None
        self.wait_after_action_seconds = wait_after_action_seconds

        self.output_path = output_path
        if self.output_path and not os.path.exists(self.output_path):
            os.makedirs(self.output_path, exist_ok=True)
        self.task_name = task_name or {}
        self.tmp_prefix = ''
        self.trap_controller = None

    # ---------------------------------------------------- M3A extensions
    def set_task_guidelines(self, task_guidelines: list[str]) -> None:
        self.additional_guidelines = task_guidelines

    def get_task_name(self, suite) -> None:
        for _, instances in suite.items():
            self.task_name[instances[0].goal] = instances[0].name

    # ------------------------------------------------------------ reset
    def reset(self, go_home: bool = False) -> None:
        super().reset(go_home)
        self.env.hide_automation_ui()
        self.history = []

        try:
            adb_utils.press_home_button(self.env.controller)
            time.sleep(1)
            screen_size = self.env.logical_screen_size
            width, height = screen_size if screen_size else (1080, 2400)
            swipe_cmd = (
                f'shell input swipe {width // 2} {int(height * 0.8)} '
                f'{width // 2} {int(height * 0.2)} 300'
            )
            adb_utils.issue_generic_request(swipe_cmd, self.env.controller)
            time.sleep(1)
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging.warning('Gpt5 initial swipe-up failed: %s', e)

    # --------------------------------------------------- trajectory save
    def _task_output_dir(self, goal: str) -> str:
        if not self.output_path:
            return ''
        if goal in self.task_name:
            sub = self.task_name[goal]
        else:
            sub = goal.replace(' ', '_')[:50]
        path = os.path.join(self.output_path, sub)
        os.makedirs(path, exist_ok=True)
        return path

    def _save_step_artifacts(
        self,
        task_dir: str,
        step_idx: int,
        raw_pixels: np.ndarray,
        som_pixels: np.ndarray,
        action_dict: dict | None,
    ) -> None:
        if not task_dir:
            return
        try:
            Image.fromarray(raw_pixels).save(
                os.path.join(task_dir, f'screenshot_{step_idx}.png')
            )
            Image.fromarray(som_pixels).save(
                os.path.join(task_dir, f'screenshot_{step_idx}_som.png')
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging.warning('Gpt5 screenshot save failed: %s', e)
        if action_dict is not None:
            try:
                with open(
                    os.path.join(task_dir, 'action.jsonl'),
                    'a', encoding='utf-8',
                ) as f:
                    f.write(json.dumps(action_dict, ensure_ascii=False) + '\n')
            except Exception as e:  # pylint: disable=broad-exception-caught
                logging.warning('Gpt5 action log write failed: %s', e)

    # ------------------------------------------------------------- step
    def step(self, goal: str) -> base_agent.AgentInteractionResult:
        step_data: dict[str, Any] = {
            'raw_screenshot': None,
            'before_screenshot_with_som': None,
            'before_ui_elements': [],
            'after_screenshot_with_som': None,
            'action_prompt': None,
            'action_output': None,
            'action_output_json': None,
            'action_reason': None,
            'action_raw_response': None,
            'summary_prompt': None,
            'summary': None,
            'summary_raw_response': None,
        }
        step_idx = len(self.history)
        logging.info('----------step %s----------', str(step_idx + 1))

        state = self.get_post_transition_state()
        logical_screen_size = self.env.logical_screen_size
        orientation = self.env.orientation
        physical_frame_boundary = self.env.physical_frame_boundary

        before_ui_elements = state.ui_elements
        step_data['before_ui_elements'] = before_ui_elements
        before_ui_elements_list = m3a._generate_ui_elements_description_list(
            before_ui_elements, logical_screen_size
        )
        step_data['raw_screenshot'] = state.pixels.copy()

        # Trap S-layer hook: model may see a tampered screenshot.
        raw_model_pixels = state.pixels
        raw_history_pixels = state.pixels
        if self.trap_controller:
            raw_model_pixels, raw_history_pixels = \
                self.trap_controller.on_screenshot(
                    state.pixels, step_idx, before_ui_elements,
                )

        # Build SoM overlay on the (model-facing) pixels.
        before_screenshot = raw_model_pixels.copy()
        for index, ui_element in enumerate(before_ui_elements):
            if m3a_utils.validate_ui_element(ui_element, logical_screen_size):
                m3a_utils.add_ui_element_mark(
                    before_screenshot,
                    ui_element,
                    index,
                    logical_screen_size,
                    physical_frame_boundary,
                    orientation,
                )
        step_data['before_screenshot_with_som'] = before_screenshot.copy()

        action_prompt = m3a._action_selection_prompt(
            goal,
            ['Step ' + str(i + 1) + '- ' + si['summary']
             for i, si in enumerate(self.history)],
            before_ui_elements_list,
            self.additional_guidelines,
        )
        step_data['action_prompt'] = action_prompt

        action_output, is_safe, raw_response = self.llm.predict_mm(
            action_prompt,
            [raw_model_pixels, before_screenshot],
        )

        if is_safe is False:
            action_output = (
                f'Reason: {m3a_utils.TRIGGER_SAFETY_CLASSIFIER}\n'
                'Action: {"action_type": "status", "goal_status": "infeasible"}'
            )
        if not raw_response:
            print('[WARN] Gpt5 action-selection returned no response; '
                  'treating as UNKNOWN.')
            action_output = (
                'Reason: LLM call failed.\n'
                'Action: {"action_type": "status", "goal_status": "infeasible"}'
            )

        step_data['action_output'] = action_output
        step_data['action_raw_response'] = raw_response

        print('========== gpt5 response ==========')
        print(action_output[:2000] if isinstance(action_output, str) else action_output)

        reason, action_str = m3a_utils.parse_reason_action_output(action_output)

        task_dir = self._task_output_dir(goal)

        if (not reason) or (not action_str):
            logging.info('Action prompt output is not in the correct format.')
            step_data['summary'] = (
                'Output for action selection is not in the correct format, '
                'so no action is performed.'
            )
            self.history.append(step_data)
            self._save_step_artifacts(
                task_dir, step_idx,
                state.pixels, before_screenshot, None,
            )
            return base_agent.AgentInteractionResult(False, step_data)

        step_data['action_reason'] = reason

        try:
            converted_action = json_action.JSONAction(
                **agent_utils.extract_json(action_str),
            )
            step_data['action_output_json'] = converted_action
        except Exception as e:  # pylint: disable=broad-exception-caught
            logging.info('Failed to convert the output to a valid action: %s', e)
            step_data['summary'] = (
                'Can not parse the output to a valid action. Please pick an '
                'action from the list with required parameters (if any) in '
                'the correct JSON format!'
            )
            self.history.append(step_data)
            self._save_step_artifacts(
                task_dir, step_idx,
                state.pixels, before_screenshot,
                {'raw_action_str': action_str, 'parse_error': str(e)},
            )
            return base_agent.AgentInteractionResult(False, step_data)

        # Bounds check on SoM index (copied from M3A).
        action_index = converted_action.index
        num_ui_elements = len(before_ui_elements)
        if (converted_action.action_type in
                ['click', 'long_press', 'input_text', 'scroll']
                and action_index is not None):
            if action_index >= num_ui_elements:
                logging.info(
                    'Index out of range: %s (only %d elements).',
                    action_index, num_ui_elements,
                )
                step_data['summary'] = (
                    'The parameter index is out of range. Remember the '
                    'index must be in the UI element list!'
                )
                self.history.append(step_data)
                return base_agent.AgentInteractionResult(False, step_data)
            m3a_utils.add_ui_element_mark(
                step_data['raw_screenshot'],
                before_ui_elements[action_index],
                action_index,
                logical_screen_size,
                physical_frame_boundary,
                orientation,
            )

        # Trap A-layer hook.
        original_action_type = converted_action.action_type
        action_dict_for_trap = {
            'action_type': converted_action.action_type,
            'index': converted_action.index,
            'text': converted_action.text,
            'direction': converted_action.direction,
            'goal_status': converted_action.goal_status,
            'app_name': converted_action.app_name,
        }
        if self.trap_controller:
            converted_action, _ = self.trap_controller.on_action(
                converted_action, action_dict_for_trap, step_idx,
            )
            if converted_action.action_type != original_action_type:
                print('========== ACTUAL EXECUTION ==========')
                print(f'  Model intended: {original_action_type}')
                print(f'  Trap executed:  {converted_action.action_type}')

        if converted_action.action_type == 'status':
            if converted_action.goal_status == 'infeasible':
                logging.info('Agent stopped: infeasible.')
            step_data['summary'] = 'Agent thinks the request has been completed.'
            self.history.append(step_data)
            self._save_step_artifacts(
                task_dir, step_idx,
                state.pixels, before_screenshot,
                {'action': action_str, 'reason': reason},
            )
            return base_agent.AgentInteractionResult(True, step_data)

        if converted_action.action_type == 'answer':
            logging.info('Agent answered with: %s', converted_action.text)

        # Trap execution-blocking hook.
        if (self.trap_controller
                and self.trap_controller.should_block_execution(step_idx)):
            print('========== ACTUAL EXECUTION ==========')
            print('  [TRAP] Execution BLOCKED (State Deadlock)')
        else:
            try:
                self.env.execute_action(converted_action)
            except Exception as e:  # pylint: disable=broad-exception-caught
                logging.info('Failed to execute action: %s', e)
                step_data['summary'] = (
                    'Can not execute the action, make sure to select the '
                    'action with required parameters (if any) in the '
                    'correct JSON format!'
                )
                self.history.append(step_data)
                return base_agent.AgentInteractionResult(False, step_data)

        time.sleep(self.wait_after_action_seconds)

        # ---------- summarisation phase ----------
        state = self.env.get_state(wait_to_stabilize=False)
        logical_screen_size = self.env.logical_screen_size
        orientation = self.env.orientation
        physical_frame_boundary = self.env.physical_frame_boundary
        after_ui_elements = state.ui_elements
        after_ui_elements_list = m3a._generate_ui_elements_description_list(
            after_ui_elements, logical_screen_size
        )
        after_screenshot = state.pixels.copy()
        for index, ui_element in enumerate(after_ui_elements):
            if m3a_utils.validate_ui_element(ui_element, logical_screen_size):
                m3a_utils.add_ui_element_mark(
                    after_screenshot,
                    ui_element,
                    index,
                    logical_screen_size,
                    physical_frame_boundary,
                    orientation,
                )

        m3a_utils.add_screenshot_label(
            step_data['before_screenshot_with_som'], 'before'
        )
        m3a_utils.add_screenshot_label(after_screenshot, 'after')
        step_data['after_screenshot_with_som'] = after_screenshot.copy()

        summary_prompt = m3a._summarize_prompt(
            action_str, reason, goal,
            before_ui_elements_list, after_ui_elements_list,
        )
        summary, is_safe, raw_response = self.llm.predict_mm(
            summary_prompt,
            [step_data['before_screenshot_with_som'], after_screenshot],
        )
        if is_safe is False:
            summary = 'Summary triggered LLM safety classifier.'
        if not raw_response:
            step_data['summary'] = (
                f'Some error occurred calling LLM during summarization '
                f'phase: {summary}'
            )
            self.history.append(step_data)
            self._save_step_artifacts(
                task_dir, step_idx,
                step_data['raw_screenshot'], before_screenshot,
                {'action': action_str, 'reason': reason},
            )
            return base_agent.AgentInteractionResult(False, step_data)

        step_data['summary_prompt'] = summary_prompt
        step_data['summary'] = f'Action selected: {action_str}. {summary}'
        step_data['summary_raw_response'] = raw_response
        logging.info('Summary: %s', summary)

        self.history.append(step_data)
        self._save_step_artifacts(
            task_dir, step_idx,
            step_data['raw_screenshot'], before_screenshot,
            {'action': action_str, 'reason': reason, 'summary': summary},
        )
        return base_agent.AgentInteractionResult(False, step_data)
