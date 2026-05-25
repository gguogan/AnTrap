"""Ray remote worker for a single Android emulator in GRPO training.

Adapted from androidcoach/verl/trainer/ppo/android.py.
Key difference: uses HTTP client (AndroidEnvClient) instead of uiautomator2.
Does NOT manage emulator lifecycle — the remote server handles that.
"""

import logging
import time
import traceback
from typing import Any, Optional

import ray
from PIL import Image

from android_env_client import AndroidEnvClient
from ui_tars_parser import parse_action_to_structure_output

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# UI-TARS system prompt -- verbatim from AndroidCoach/data/prompt/uitars_system_prompt.py
# ---------------------------------------------------------------------------
SYSTEM_PROMPT_FORMAT = """
You are a GUI agent. You are given a task and your action history, with screenshots. You need to perform the next action to complete the task.

## Output Format

Thought: ...
Action: ...


## Action Space

click(start_box='<|box_start|>(x1,y1)<|box_end|>')
long_press(start_box='<|box_start|>(x1,y1)<|box_end|>')
type(content='xxx')
scroll(start_box='<|box_start|>(x1,y1)<|box_end|>', end_box='<|box_start|>(x2,y2)<|box_end|>')
open_app(app_name='')
drag(start_box='<|box_start|>(x1,y1)<|box_end|>', end_box='<|box_start|>(x2,y2)<|box_end|>')
press_home()
press_back()
finished(content='') # Submit the task regardless of whether it succeeds or fails.

## Note
- Use English in Thought part.
- First summarize your previous actions, then write a small plan and finally summarize your next action (with its save target element) in one sentence in Thought part.

## User Instruction
{instruction}
"""


def prepare_system_prompt(instruction: str) -> str:
    return SYSTEM_PROMPT_FORMAT.format(instruction=instruction)


# ---------------------------------------------------------------------------
# Ray Worker
# ---------------------------------------------------------------------------

@ray.remote(num_cpus=1)
class AndroidGRPOWorker:
    """Manages a single remote Android emulator for GRPO training."""

    def __init__(
        self,
        worker_idx: int,
        server_url: str,
        emu_id: int,
        max_steps: int = 16,
        max_pixels: int = 1270180,
        min_pixels: int = 256,
        trap_mode: bool = False,
        trap_config: Optional[dict] = None,
    ):
        self.worker_idx = worker_idx
        self.emu_id = emu_id
        self.max_steps = max_steps
        self.max_pixels = max_pixels
        self.min_pixels = min_pixels
        self.trap_mode = trap_mode
        self.trap_config = trap_config or {}

        # HTTP client to remote emulator
        self.client = AndroidEnvClient(server_url, emu_id)

        # Episode state
        self.task_type: Optional[str] = None
        self.task_idx: Optional[int] = None
        self.task_goal: str = ""
        self.history_messages: list[dict] = []
        self.history_images: list[Image.Image] = []
        self.step_counter: int = 0
        self.is_done: bool = False
        self.outcome_reward: float = 0.0

    def get_worker_idx(self) -> int:
        return self.worker_idx

    def get_is_done(self) -> bool:
        return self.is_done

    def get_history_messages(self) -> list[dict]:
        return self.history_messages

    def health(self) -> bool:
        return self.client.health()

    def reset(self, task_type: str, task_idx: int) -> dict:
        """Reset environment and initialize a task. Returns initial observation dict."""
        # Reset emulator
        self.client.reset(go_home=True)

        # Configure trap if in trap mode
        if self.trap_mode and self.trap_config:
            self.client.configure_trap(**self.trap_config)
            self.client.trap_reset()

        # Initialize task
        self.client.initialize_task(task_type, task_idx)
        self.task_type = task_type
        self.task_idx = task_idx
        self.task_goal = self.client.get_goal()

        # Get initial screenshot
        if self.trap_mode:
            initial_screenshot, _ = self.client.trap_screenshot(step_idx=0)
        else:
            initial_screenshot = self.client.screenshot()

        # Build initial messages
        user_prompt = prepare_system_prompt(self.task_goal)

        self.history_messages = [
            {
                "role": "system",
                "content": [{"type": "text", "text": "You are a helpful assistant."}],
            },
            {
                "role": "user",
                "content": [{"type": "text", "text": user_prompt}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "image": initial_screenshot,
                        "min_pixels": self.min_pixels,
                        "max_pixels": self.max_pixels,
                    }
                ],
            },
        ]
        self.history_images = [initial_screenshot]
        self.step_counter = 0
        self.is_done = False
        self.outcome_reward = 0.0

        return {
            "env_idx": self.worker_idx,
            "obs_messages": self.history_messages,
            "is_done": False,
        }

    def step(self, model_response: str) -> dict:
        """Execute one step: parse action, execute remotely, get new screenshot."""
        # Parse action from model output. UI-TARS emits coords in [0, 1000); the
        # parser rescales to pixel space using the device viewport.
        try:
            parsed = parse_action_to_structure_output(
                model_response,
                factor=1000,
                origin_resized_height=2400,
                origin_resized_width=1080,
                model_type="qwen25vl",
                max_pixels=self.max_pixels,
                min_pixels=self.min_pixels,
            )
            action = parsed[0] if parsed else {"action_type": "wait", "action_inputs": {}}
        except Exception as e:
            logger.warning(f"Worker {self.worker_idx}: parse_action failed: {e}")
            action = {"action_type": "wait", "action_inputs": {}}
        action_type = action.get("action_type", "wait")

        # Append assistant response to history
        self.history_messages.append({
            "role": "assistant",
            "content": [{"type": "text", "text": model_response}],
        })

        # Check if task is finished
        if action_type == "finished":
            self.is_done = True
            self.step_counter += 1
            return {
                "env_idx": self.worker_idx,
                "obs_messages": self.history_messages,
                "is_done": True,
            }

        # Trap: pre-step injection
        if self.trap_mode:
            self.client.trap_pre_step(self.step_counter)

            # Check for execution blocking (state deadlock)
            if self.client.trap_should_block(self.step_counter):
                # Action blocked — get screenshot without executing
                new_screenshot, _ = self.client.trap_screenshot(self.step_counter)
                self.history_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "image": new_screenshot,
                            "min_pixels": self.min_pixels,
                            "max_pixels": self.max_pixels,
                        }
                    ],
                })
                self.history_images.append(new_screenshot)
                self.step_counter += 1
                if self.step_counter >= self.max_steps:
                    self.is_done = True
                return {
                    "env_idx": self.worker_idx,
                    "obs_messages": self.history_messages,
                    "is_done": self.is_done,
                }

        # Execute action on remote emulator
        try:
            # Convert action to the format expected by the server
            action_dict = self._action_to_server_format(action)
            self.client.execute_action(action_dict)
        except Exception as e:
            logger.warning(f"Worker {self.worker_idx}: action execution failed: {e}")
            self.is_done = True
            return {
                "env_idx": self.worker_idx,
                "obs_messages": self.history_messages,
                "is_done": True,
            }

        # Wait for UI to settle
        time.sleep(2)

        # Get new screenshot
        try:
            if self.trap_mode:
                new_screenshot, _ = self.client.trap_screenshot(self.step_counter)
            else:
                new_screenshot = self.client.screenshot()
        except Exception as e:
            logger.warning(f"Worker {self.worker_idx}: screenshot failed: {e}")
            self.is_done = True
            return {
                "env_idx": self.worker_idx,
                "obs_messages": self.history_messages,
                "is_done": True,
            }

        # Append new observation
        self.history_messages.append({
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "image": new_screenshot,
                    "min_pixels": self.min_pixels,
                    "max_pixels": self.max_pixels,
                }
            ],
        })
        self.history_images.append(new_screenshot)

        self.step_counter += 1
        if self.step_counter >= self.max_steps:
            self.is_done = True

        return {
            "env_idx": self.worker_idx,
            "obs_messages": self.history_messages,
            "is_done": self.is_done,
        }

    def evaluate(self) -> float:
        """Evaluate task success via remote server. Returns 0.0 or 1.0."""
        try:
            is_successful = self.client.score_task()
            self.outcome_reward = 1.0 if is_successful else 0.0
        except Exception as e:
            logger.warning(f"Worker {self.worker_idx}: evaluation failed: {e}")
            self.outcome_reward = 0.0
        return self.outcome_reward

    def get_outcome_reward(self) -> float:
        return self.outcome_reward

    def get_step_count(self) -> int:
        return self.step_counter

    def get_policy_train_dict(self) -> list[dict]:
        """Extract step-level (prompt, response) pairs for GRPO training.

        Returns list of dicts, each with:
            - prompt_messages: conversation up to that step's screenshot
            - response_text: the model's response at that step
            - step_idx: step index in the trajectory
        """
        train_pairs = []
        # History format: [system, user_prompt, user_screenshot, assistant, user_screenshot, assistant, ...]
        #                   0       1            2                3          4                5
        # Step k prompt = messages[0 : 2 + 2*k + 1] (up to and including screenshot at step k)
        # Step k response = messages[2 + 2*k + 1] (the assistant message)

        step_idx = 0
        i = 2  # Start after system + user_prompt
        while i < len(self.history_messages):
            msg = self.history_messages[i]
            if msg["role"] == "user" and i + 1 < len(self.history_messages):
                next_msg = self.history_messages[i + 1]
                if next_msg["role"] == "assistant":
                    train_pairs.append({
                        "prompt_messages": self.history_messages[: i + 1],
                        "response_text": next_msg["content"][0]["text"],
                        "step_idx": step_idx,
                    })
                    step_idx += 1
                    i += 2  # Skip past assistant message
                    continue
            i += 1

        return train_pairs

    def _action_to_server_format(self, action: dict) -> dict:
        """Convert parsed UI-TARS action into the JSON action format expected
        by the AndroidWorld server. Coordinates have already been rescaled to
        pixel space by ``parse_action_to_structure_output``."""
        action_type = action["action_type"]
        inputs = action.get("action_inputs", {})

        if action_type in ("click", "long_press", "double_tap"):
            x, y = self._coords_from_box(inputs.get("start_box"))
            return {"action_type": action_type, "x": x, "y": y}
        if action_type == "type":
            return {"action_type": "input_text", "text": inputs.get("content", "")}
        if action_type in ("scroll", "drag"):
            sx, sy = self._coords_from_box(inputs.get("start_box"))
            ex, ey = self._coords_from_box(inputs.get("end_box"))
            return {
                "action_type": "swipe",
                "x": sx, "y": sy,
                "direction": self._direction(sx, sy, ex, ey),
            }
        if action_type == "open_app":
            return {"action_type": "open_app", "app_name": inputs.get("app_name", "")}
        if action_type == "press_home":
            return {"action_type": "navigate_home"}
        if action_type == "press_back":
            return {"action_type": "navigate_back"}
        if action_type == "finished":
            return {"action_type": "status", "goal_status": "complete"}
        if action_type == "answer":
            return {"action_type": "answer", "text": inputs.get("content", "")}
        return {"action_type": "wait"}

    @staticmethod
    def _coords_from_box(box: Any) -> tuple[int, int]:
        """Pull (x, y) out of a parsed start_box / end_box value.

        ``parse_action_to_structure_output`` produces ``[x, y]`` or
        ``[x1, y1, x2, y2]`` already in pixel space; we just unpack."""
        if isinstance(box, (list, tuple)) and len(box) >= 2:
            if len(box) >= 4:
                return int((box[0] + box[2]) / 2), int((box[1] + box[3]) / 2)
            return int(box[0]), int(box[1])
        # Defensive default -- centre of a 1080x2400 viewport.
        return 540, 1200

    @staticmethod
    def _direction(sx: int, sy: int, ex: int, ey: int) -> str:
        dx, dy = ex - sx, ey - sy
        if abs(dx) > abs(dy):
            return "right" if dx > 0 else "left"
        return "down" if dy > 0 else "up"
