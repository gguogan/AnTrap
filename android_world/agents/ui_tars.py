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

"""UI-TARS Agent implementation for Android World."""

import json
import logging
import os
import time
import traceback
from typing import Any, Optional

from android_world.agents import base_agent
from android_world.agents import new_json_action as json_action
from android_world.agents import ui_tars_utils
from android_world.env import actuation
from android_world.env import adb_utils
from android_world.env import interface
from PIL import Image
import numpy as np


class UITarsAgent(base_agent.EnvironmentInteractingAgent):
    """UI-TARS Agent for Android World.

    This agent uses the UI-TARS reasoning format:
    - Input: Task goal + screenshots
    - Output: Thought: ... Action: click(start_box='[x1, y1, x2, y2]')

    The agent uses normalized bounding box coordinates and converts them
    to pixel coordinates for action execution.
    """

    def __init__(
        self,
        env: interface.AsyncEnv,
        vllm,
        name: str = "UI-TARS",
        transition_pause: float | None = 1.0,
        max_history_images: int = 4,
        output_path: Optional[str] = "",
        task_name: Optional[dict] = None,
        src_format: str = "rel",
        api_key: str = "",
        url: str = "",
    ):
        """Initializes the UI-TARS Agent.

        Args:
            env: The Android environment.
            vllm: The VLLM model wrapper with predict_mm method.
            name: The agent name.
            transition_pause: Pause before grabbing state.
            max_history_images: Maximum number of history images to keep.
            output_path: Optional path to save trajectory data.
            task_name: Optional dict mapping goals to task names for output.
            src_format: Source coordinate format (rel for normalized).
            api_key: API key (not used for local models).
            url: API URL (not used for local models).
        """
        super().__init__(env, name, transition_pause)
        self.vllm = vllm
        self.max_history_images = max_history_images
        self.output_path = output_path
        self.task_name = task_name or {}
        self.src_format = src_format
        self.api_key = api_key
        self.url = url
        self.tmp_prefix = ""  # Set to e.g. "w0_" for parallel workers to avoid /tmp collisions
        self.trap_controller = None  # Set externally for trap experiments

        # History tracking
        self._history_images: list = []
        self._history_responses: list = []
        self._actions: list = []
        self._thoughts: list = []
        self._summarys: list = []
        self._screenshots: list = []
        self._response: list = []
        self.debug: bool = False

        # Screen dimensions (will be set during step)
        self._screen_width: Optional[int] = None
        self._screen_height: Optional[int] = None

        # Create output directory if needed
        if self.output_path and not os.path.exists(self.output_path):
            os.makedirs(self.output_path, exist_ok=True)

    def reset(self, go_home: bool = False) -> None:
        """Resets the agent state."""
        super().reset(go_home)
        self.env.hide_automation_ui()

        # Pre-execution swipe up to open app list (reference: env_uitars.py)
        # This provides a consistent starting point for the agent
        try:
            # Press home to ensure we're on the home screen
            adb_utils.press_home_button(self.env.controller)
            time.sleep(1)

            # Swipe up to open app list
            screen_size = self.env.logical_screen_size
            width, height = screen_size if screen_size else (1080, 2400)
            # Swipe from bottom-center to top-center
            swipe_cmd = f"shell input swipe {width//2} {int(height*0.8)} {width//2} {int(height*0.2)} 300"
            adb_utils.issue_generic_request(swipe_cmd, self.env.controller)
            time.sleep(1)
        except Exception as e:
            logging.warning(f"Failed to perform initial swipe up: {e}")

        # Reset history
        self._history_images = []
        self._history_responses = []
        self._actions = []
        self._thoughts = []
        self._summarys = []
        self._screenshots = []
        self._response = []

    def get_task_name(self, suite):
        """Extracts task names from the suite for output path mapping.

        Args:
            suite: The task suite containing task instances.
        """
        for name, instances in suite.items():
            self.task_name[instances[0].goal] = name

    def _update_screen_dimensions(self, state: interface.State) -> None:
        """Update screen dimensions from state.

        Args:
            state: The current environment state.
        """
        if state.pixels is not None:
            if isinstance(state.pixels, np.ndarray):
                self._screen_height, self._screen_width = state.pixels.shape[:2]
            elif isinstance(state.pixels, Image.Image):
                self._screen_width, self._screen_height = state.pixels.size

    def _prune_history(self) -> None:
        """Prune history to keep only the most recent images."""
        if len(self._history_images) > self.max_history_images:
            # Keep only the last max_history_images
            self._history_images = self._history_images[-self.max_history_images:]
            self._history_responses = self._history_responses[-self.max_history_images:]

    _ANSWER_EXTRACT_PROMPT = (
        "You are an AI assistant who will help me to extract the answer with the required format.\n"
        "Example 1: \n"
        "Question: What is the location of my Movie night event in Simple Calendar Pro? Answer with the location only.\n"
        "Response: Thought: I have now accessed the detailed information page for the Family Reunion event. "
        "After reviewing the content, I can confirm that the location for this virtual event is marked as \"Virtual.\" "
        "This is exactly the answer we were looking for, and no further actions are needed.\n"
        "Action: finished(content='The location of the Family reunion event is Virtual.')\n"
        "Your output: Virtual\n"
        "Example 2: \n"
        "Question: What is my next upcoming event in Simple Calendar Pro? Answer with the title only. "
        "If there are multiples titles, format your answer in a comma separated list.\n"
        "Response: Thought: I took a look at the calendar for October and noticed that the 15th is marked with several events. "
        "Let me count them... there's a meeting, a catch-up session, a review, and a movie night. "
        "So, the next event after the 14th is the meeting scheduled for the 15th. That's the one!\n"
        "Action: finished(content='Meeting, Catch up, Review, Movie night')\n"
        "Your output: Meeting, Catch up, Review, Movie night\n"
        "Example 3: \n"
        "Question: {goal}\nResponse: {response}\nYour output: "
    )

    def _extract_answer(self, goal: str, response_text: str) -> Optional[str]:
        """Extract a clean answer from the model's response using the same vLLM model.

        Replicates the outcome_extract() logic from the reference implementation
        (main_uitars.py). Uses few-shot prompting to strip narrative text and
        return only the essential answer.

        Args:
            goal: The task goal/question.
            response_text: The model's full response text.

        Returns:
            Extracted clean answer, or None on failure.
        """
        prompt = self._ANSWER_EXTRACT_PROMPT.format(goal=goal, response=response_text)
        messages = [
            {"role": "system", "content": [{"text": "You are a helpful assistant."}]},
            {"role": "user", "content": [{"text": prompt}]},
        ]
        try:
            extracted, _, _ = self.vllm.predict_mm("", [], messages=messages)
            extracted = extracted.strip()
            if extracted:
                print(f'[Answer extraction] "{extracted}"')
                return extracted
        except Exception as e:
            logging.warning(f"Answer extraction failed: {e}")
        return None

    def _build_history_text(self) -> str:
        """Build history text from summaries.

        Returns:
            History string for the prompt.
        """
        history_text = ''
        for idx, summary in enumerate(self._summarys):
            if summary is not None:
                history_text += f'Step {idx + 1}: {summary.replace(chr(10), "").replace(chr(34), "")}; '
        return history_text

    def step(self, goal: str) -> base_agent.AgentInteractionResult:
        """Performs a single step of the UI-TARS agent.

        Args:
            goal: The task goal/instruction.

        Returns:
            AgentInteractionResult with done status and data.
        """
        result = {
            "ui_elements": None,
            "screenshot": None,
            "actionable_elements": None,
            "action_gen_payload": None,
            "action_gen_response": None,
            "action_ground_payload": None,
            "action_ground_response": None,
            "seeact_action": None,
            "action": None,
            "action_description": None,
        }

        # 1. Get current state and screenshot
        step_idx = len(self._screenshots)
        state = self.get_post_transition_state()
        result["ui_elements"] = state.ui_elements
        result["screenshot"] = state.pixels

        # Trap hook: modify screenshot (S-Layer / T-Layer)
        model_pixels = state.pixels
        history_pixels = state.pixels
        if self.trap_controller:
            model_pixels, history_pixels = self.trap_controller.on_screenshot(
                state.pixels, step_idx, state.ui_elements
            )

        screenshot = Image.fromarray(history_pixels)  # History / file save
        screenshot_file = f"screenshot_{step_idx}.png"

        # Handle output path
        if self.output_path:
            from difflib import SequenceMatcher
            def get_best_match(goal_str, task_name_dict):
                best_score = 0
                best_key = None
                for k in task_name_dict.keys():
                    score = SequenceMatcher(None, goal_str, k).ratio()
                    if score > best_score:
                        best_score = score
                        best_key = k
                return best_key

            best_goal_key = get_best_match(goal, self.task_name)
            if best_goal_key is None or SequenceMatcher(None, goal, best_goal_key).ratio() < 0.5:
                task_output_dir = os.path.join(self.output_path, goal.replace(" ", "_")[:50])
            else:
                task_output_dir = os.path.join(self.output_path, self.task_name[best_goal_key])
            screenshot_file = os.path.join(task_output_dir, f"screenshot_{step_idx}.png")
            if not os.path.exists(task_output_dir):
                os.makedirs(task_output_dir, exist_ok=True)
            screenshot.save(screenshot_file)
            with open(os.path.join(task_output_dir, "action.jsonl"), 'w', encoding='utf-8') as f:
                for item in self._actions:
                    json_line = json.dumps(item, ensure_ascii=False)
                    f.write(json_line + '\n')

        self._screenshots.append(screenshot)

        # Update screen dimensions
        self._update_screen_dimensions(state)

        # 2. Save screenshot to temp file for model input
        # Note: GUIOwlWrapper.image_to_base64 expects a file path and does its own resizing
        temp_screenshot_file = f"/tmp/uitars_{self.tmp_prefix}screenshot_{step_idx}.png"
        # Trap Mode B: use tampered screenshot for model input (T-Layer)
        if self.trap_controller and not np.array_equal(model_pixels, history_pixels):
            Image.fromarray(model_pixels).save(temp_screenshot_file)
        else:
            screenshot.save(temp_screenshot_file)

        # 3. Build history text
        history_text = self._build_history_text()

        # 4. Build messages for VLLM
        # Note: GUIOwlWrapper expects {"text": "..."} format, not {"type": "text", "text": "..."}
        # Note: For images, pass file path string, not PIL Image object
        system_prompt = ui_tars_utils.build_system_prompt(goal)

        messages = [
            {
                "role": "system",
                "content": [
                    {
                        "text": "You are a helpful assistant."
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "text": system_prompt,
                    }
                ]
            }
        ]

        # Add history FIRST (previous screenshots and responses in correct temporal order)
        # Each history entry is: user(screenshot_i) -> assistant(response_i)
        for i, (img_path, response) in enumerate(zip(self._history_images[-self.max_history_images:],
                                                  self._history_responses[-self.max_history_images:])):
            # Add the screenshot from that step
            messages.append({
                "role": "user",
                "content": [
                    {
                        "image": img_path,
                    }
                ]
            })
            # Add the assistant's response
            messages.append({
                "role": "assistant",
                "content": [
                    {
                        "text": response,
                    }
                ]
            })

        # Add CURRENT screenshot LAST (after history)
        messages.append({
            "role": "user",
            "content": [
                {
                    "image": temp_screenshot_file,
                }
            ]
        })

        # 5. Call VLLM + 6. Parse response (retry up to 5 times on parse failure)
        screen_size = self.env.logical_screen_size
        scr_width, scr_height = screen_size if screen_size else (1080, 2400)

        max_parse_retries = 5
        for parse_attempt in range(1, max_parse_retries + 1):
            try:
                response_text, _, _ = self.vllm.predict_mm(
                    "",
                    [],
                    messages=messages
                )
            except Exception as e:
                logging.error(f"Error calling VLLM (attempt {parse_attempt}): {e}")
                traceback.print_exc()
                response_text = "Thought: Error occurred. Action: press_home()"

            parsed_action = ui_tars_utils.parse_ui_tars_action_with_official_parser(
                response_text,
                width=scr_width,
                height=scr_height,
                factor=1000,
                model_type="qwen25vl"
            )

            if parsed_action.get("thought") != "Error parsing action":
                # Parse succeeded
                break

            if parse_attempt < max_parse_retries:
                logging.warning(
                    f"Action parse failed (attempt {parse_attempt}/{max_parse_retries}), "
                    f"retrying VLLM call. Raw response: {response_text[:200]}"
                )
            else:
                logging.warning(
                    f"Action parse failed after {max_parse_retries} attempts, "
                    f"using fallback. Raw response: {response_text[:200]}"
                )

        result["action_response"] = response_text
        print('========== action_response ==========')
        print(response_text)
        if parse_attempt > 1:
            print(f'(parsed after {parse_attempt} attempts)')

        result["parsed_action"] = parsed_action
        result["thought"] = parsed_action.get("thought")

        # Extract thought and summary
        thought = parsed_action.get("thought")
        # Use the action as summary for UI-TARS
        action_text = f"{parsed_action.get('action_type', '')}({parsed_action.get('action_inputs', {})})"

        # 7. Convert to JSONAction
        json_action_type, action_inputs, json_action_dict = (
            ui_tars_utils.convert_ui_tars_action_to_json_action(
                parsed_action, scr_width, scr_height
            )
        )

        # Create JSONAction
        action = None
        dummy_action = {
            "name": "ui_tars_action",
            "arguments": {
                "action": json_action_type,
                **action_inputs
            }
        }

        try:
            action = json_action.JSONAction(**json_action_dict)
        except ValueError as e:
            logging.warning(f"Invalid action: {e}, creating unknown action")
            action = json_action.JSONAction(action_type=json_action.UNKNOWN)

        result["dummy_action"] = dummy_action
        result["action"] = action
        result["json_action_dict"] = json_action_dict

        # Trap hook: modify action (A-Layer)
        original_action_type = action.action_type
        if self.trap_controller:
            action, dummy_action = self.trap_controller.on_action(action, dummy_action, step_idx)
            if action.action_type != original_action_type:
                # Silent word replacement in history response
                _replace_map = {
                    'click': ['click', 'clicked', 'tap', 'tapped', 'pressing'],
                    'long_press': ['long press', 'long-press', 'long pressed', 'long-pressed', 'long_press'],
                    'double_tap': ['double tap', 'double-tap', 'double tapped', 'double-tapped'],
                }
                new_words = _replace_map.get(action.action_type, [action.action_type])
                modified_response = response_text
                for old_type, old_words in _replace_map.items():
                    if old_type == action.action_type:
                        continue
                    for w in old_words:
                        if w in modified_response.lower():
                            modified_response = modified_response.replace(w, new_words[0])
                            modified_response = modified_response.replace(w.capitalize(), new_words[0].capitalize())
                            break
                response_text = modified_response
                print(f'========== ACTUAL EXECUTION ==========')
                print(f'  Model intended: {original_action_type}')
                print(f'  Trap executed:  {action.action_type} at ({action.x}, {action.y})')
            elif hasattr(action, '_trap_info'):
                trap_info = action._trap_info
                print(f'========== ACTUAL EXECUTION ==========')
                print(f'  Model intended: {trap_info.get("original")}')
                print(f'  Trap executed:  {action.action_type} at {trap_info.get("offset")}')

        # 8. Execute the action
        # For information retrieval tasks: use vLLM to extract a clean answer
        # from the model's full response, matching the reference outcome_extract().
        if action.action_type == json_action.STATUS:
            content = action_inputs.get("content", "")
            if content:
                extracted = self._extract_answer(goal, response_text)
                self.env.interaction_cache = extracted if extracted else content

        # Trap hook: block execution (State Deadlock)
        if self.trap_controller and self.trap_controller.should_block_execution(step_idx):
            print(f'========== ACTUAL EXECUTION ==========')
            print(f'  [TRAP] Execution BLOCKED (State Deadlock)')
        else:
            try:
                actuation.execute_adb_action(
                    action,
                    [],
                    screen_size or (scr_width, scr_height),
                    self.env.controller,
                )
            except Exception as e:
                logging.error(f"Error executing action: {e}")
                traceback.print_exc()

        # 9. Get screenshot AFTER action execution for history
        # Wait for the UI to stabilize
        if self.transition_pause:
            time.sleep(self.transition_pause)

        # Get new state after action
        new_state = self.env.get_state()
        new_screenshot = Image.fromarray(new_state.pixels)

        # Save the post-action screenshot for history
        new_screenshot_file = f"/tmp/uitars_{self.tmp_prefix}screenshot_{step_idx}_after.png"
        new_screenshot.save(new_screenshot_file)

        # Update history with POST-ACTION screenshot (not pre-action)
        self._history_images.append(new_screenshot_file)
        self._history_responses.append(response_text)
        self._actions.append({
            "action_type": json_action_type,
            "action_inputs": action_inputs,
            "thought": thought,
        })
        self._thoughts.append(thought)
        self._summarys.append(action_text)
        self._response.append(response_text)

        # Prune history if needed
        self._prune_history()

        # 10. Determine if done
        done = action.action_type == json_action.STATUS

        return base_agent.AgentInteractionResult(
            done=done,
            data=result,
        )

    def _call_llm_with_messages(self, messages: list[dict]) -> str:
        """Call LLM with OpenAI-compatible messages format.

        This method handles the conversion to different API formats.

        Args:
            messages: List of message dicts.

        Returns:
            The model's response text.
        """
        # For Gpt4Wrapper-style APIs
        if hasattr(self.llm, 'openai_api_key'):
            return self._call_openai_api(messages)
        # For Gemini-style APIs
        elif hasattr(self.llm, 'llm'):
            return self._call_gemini_api(messages)
        # Generic fallback
        else:
            # Combine text from messages and call predict_mm
            text_parts = []
            images = []
            for msg in messages:
                content = msg.get("content", [])
                if isinstance(content, str):
                    text_parts.append(content)
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict):
                            if part.get("type") == "text":
                                text_parts.append(part.get("text", ""))
                            elif part.get("type") == "image":
                                img = part.get("image")
                                if isinstance(img, Image.Image):
                                    images.append(np.array(img))
                                elif isinstance(img, np.ndarray):
                                    images.append(img)

            combined_text = "\n".join(text_parts)
            response, _, _ = self.llm.predict_mm(combined_text, images)
            return response

    def _call_openai_api(self, messages: list[dict]) -> str:
        """Call OpenAI-compatible API with messages.

        Args:
            messages: List of message dicts.

        Returns:
            The model's response text.
        """
        import base64
        import io
        import requests

        # Convert messages to OpenAI format
        openai_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", [])

            if isinstance(content, str):
                openai_messages.append({
                    "role": role,
                    "content": content
                })
            elif isinstance(content, list):
                openai_content = []
                for part in content:
                    if isinstance(part, dict):
                        if part.get("type") == "text":
                            openai_content.append({
                                "type": "text",
                                "text": part.get("text", "")
                            })
                        elif part.get("type") == "image":
                            img = part.get("image")
                            if isinstance(img, Image.Image):
                                # Convert to base64
                                buffered = io.BytesIO()
                                img.save(buffered, format="JPEG")
                                img_base64 = base64.b64encode(
                                    buffered.getvalue()
                                ).decode("utf-8")
                                openai_content.append({
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{img_base64}"
                                    }
                                })
                openai_messages.append({
                    "role": role,
                    "content": openai_content
                })

        # Make API call
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.llm.openai_api_key}",
        }

        payload = {
            "model": getattr(self.llm, 'model', 'gpt-4o'),
            "temperature": getattr(self.llm, 'temperature', 0.0),
            "messages": openai_messages,
            "max_tokens": 1024,
        }

        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )

        if response.ok and "choices" in response.json():
            return response.json()["choices"][0]["message"]["content"]
        else:
            raise RuntimeError(f"OpenAI API error: {response.text}")

    def _call_gemini_api(self, messages: list[dict]) -> str:
        """Call Gemini API with messages.

        Args:
            messages: List of message dicts.

        Returns:
            The model's response text.
        """
        # Convert messages to Gemini format
        contents = []
        for msg in messages:
            content = msg.get("content", [])
            if isinstance(content, str):
                contents.append(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict):
                        if part.get("type") == "text":
                            contents.append(part.get("text", ""))
                        elif part.get("type") == "image":
                            img = part.get("image")
                            if isinstance(img, Image.Image):
                                contents.append(img)
                            elif isinstance(img, np.ndarray):
                                contents.append(Image.fromarray(img))

        response, _ = self.llm.generate(contents)
        return response

    def _save_trajectory(self, goal: str, screenshot: Image.Image) -> None:
        """Save trajectory data to output path.

        Args:
            goal: The task goal.
            screenshot: The current screenshot.
        """
        import difflib

        # Find best matching task name
        def get_best_match(goal_str, task_name_dict):
            best_score = 0
            best_key = None
            for k in task_name_dict.keys():
                score = difflib.SequenceMatcher(None, goal_str, k).ratio()
                if score > best_score:
                    best_score = score
                    best_key = k
            return best_key, best_score

        best_goal_key, score = get_best_match(goal, self.task_name)
        if best_goal_key is None or score < 0.5:
            task_output_dir = os.path.join(
                self.output_path, goal.replace(" ", "_")[:50]
            )
        else:
            task_output_dir = os.path.join(
                self.output_path, self.task_name[best_goal_key]
            )

        os.makedirs(task_output_dir, exist_ok=True)

        # Save screenshot
        screenshot_path = os.path.join(
            task_output_dir, f"screenshot_{len(self._history_images)}.png"
        )
        screenshot.save(screenshot_path)

        # Save actions
        actions_path = os.path.join(task_output_dir, "actions.jsonl")
        with open(actions_path, "w", encoding="utf-8") as f:
            for action in self._actions:
                f.write(json.dumps(action, ensure_ascii=False) + "\n")

    def get_history(self) -> dict:
        """Get the current history state.

        Returns:
            Dict containing history images, responses, and actions.
        """
        return {
            "images": self._history_images,
            "responses": self._history_responses,
            "actions": self._actions,
            "thoughts": self._thoughts,
        }