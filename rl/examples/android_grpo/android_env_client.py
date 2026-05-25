"""HTTP client for communicating with the remote Android emulator server.

Replaces all direct uiautomator2/adb calls with HTTP requests to the
android_grpo_server.py running on the emulator machine.
"""

import base64
import io
import logging
import time
from typing import Any, Optional

import numpy as np
import requests
from PIL import Image

logger = logging.getLogger(__name__)


class AndroidEnvClient:
    """HTTP client for a single remote Android emulator."""

    def __init__(self, base_url: str, emu_id: int, timeout: int = 120, max_retries: int = 3):
        self.base_url = f"{base_url.rstrip('/')}/emu/{emu_id}"
        self.emu_id = emu_id
        self.timeout = timeout
        self.max_retries = max_retries
        self._session = requests.Session()

    def _request(self, method: str, path: str, **kwargs) -> dict:
        """Make an HTTP request with retry logic."""
        url = f"{self.base_url}{path}"
        kwargs.setdefault("timeout", self.timeout)

        for attempt in range(1, self.max_retries + 1):
            try:
                resp = self._session.request(method, url, **kwargs)
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.ConnectionError as e:
                if attempt < self.max_retries:
                    wait = 5 * attempt
                    logger.warning(f"Emu {self.emu_id}: connection error (attempt {attempt}), retrying in {wait}s: {e}")
                    time.sleep(wait)
                else:
                    raise
            except requests.exceptions.HTTPError as e:
                logger.error(f"Emu {self.emu_id}: HTTP error on {path}: {e}")
                raise
            except requests.exceptions.Timeout as e:
                if attempt < self.max_retries:
                    logger.warning(f"Emu {self.emu_id}: timeout (attempt {attempt}), retrying: {e}")
                else:
                    raise

    @staticmethod
    def _decode_screenshot(b64_str: str) -> Image.Image:
        """Decode base64 JPEG string to PIL Image."""
        raw = base64.b64decode(b64_str)
        return Image.open(io.BytesIO(raw)).convert("RGB")

    # ------------------------------------------------------------------
    # Core environment methods
    # ------------------------------------------------------------------

    def reset(self, go_home: bool = True) -> dict:
        return self._request("POST", "/reset", params={"go_home": go_home})

    def screenshot(self, wait_to_stabilize: bool = True) -> Image.Image:
        resp = self._request("GET", "/screenshot", params={"wait_to_stabilize": wait_to_stabilize})
        return self._decode_screenshot(resp["screenshot"])

    def execute_action(self, action_dict: dict[str, Any]) -> dict:
        return self._request("POST", "/execute_action", json={"action_dict": action_dict})

    def initialize_task(self, task_type: str, task_idx: int) -> dict:
        return self._request("POST", "/task/initialize", json={"task_type": task_type, "task_idx": task_idx})

    def score_task(self) -> bool:
        resp = self._request("GET", "/task/score")
        return resp["is_successful"]

    def get_goal(self) -> str:
        resp = self._request("GET", "/task/goal")
        return resp["goal"]

    def tear_down_task(self) -> dict:
        return self._request("POST", "/task/tear_down")

    def health(self) -> bool:
        try:
            resp = self._request("GET", "/health")
            return resp.get("status") == "ok"
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Trap methods
    # ------------------------------------------------------------------

    def configure_trap(
        self,
        category: str = "none",
        trap_type: str = "none",
        trigger_probability: float = 0.3,
        seed: int = 42,
        max_traps: int = 0,
        params: Optional[dict] = None,
    ) -> dict:
        return self._request("POST", "/trap/configure", json={
            "category": category,
            "trap_type": trap_type,
            "trigger_probability": trigger_probability,
            "seed": seed,
            "max_traps": max_traps,
            "params": params or {},
        })

    def trap_reset(self) -> dict:
        return self._request("POST", "/trap/reset")

    def trap_screenshot(self, step_idx: int) -> tuple[Image.Image, Image.Image]:
        """Get trap-modified screenshot. Returns (model_input, history)."""
        resp = self._request("POST", "/trap/on_screenshot", json={
            "step_idx": step_idx,
        })
        model_img = self._decode_screenshot(resp["screenshot"])
        history_img = self._decode_screenshot(resp["history_screenshot"])
        return model_img, history_img

    def trap_on_action(self, action: dict, dummy_action: dict, step_idx: int) -> tuple[dict, dict]:
        resp = self._request("POST", "/trap/on_action", json={
            "action": action,
            "dummy_action": dummy_action,
            "step_idx": step_idx,
        })
        return resp["action"], resp["dummy_action"]

    def trap_should_block(self, step_idx: int) -> bool:
        resp = self._request("GET", "/trap/should_block", params={"step_idx": step_idx})
        return resp["should_block"]

    def trap_pre_step(self, step_idx: int) -> dict:
        return self._request("POST", "/trap/pre_step", params={"step_idx": step_idx})

    def trap_log(self) -> list[dict]:
        resp = self._request("GET", "/trap/log")
        return resp["log"]


class AndroidEnvClientPool:
    """Manages clients for all emulators."""

    def __init__(self, base_url: str, num_emulators: int = 8, **kwargs):
        self.clients = {
            i: AndroidEnvClient(base_url, i, **kwargs)
            for i in range(num_emulators)
        }

    def __getitem__(self, emu_id: int) -> AndroidEnvClient:
        return self.clients[emu_id]

    def __len__(self) -> int:
        return len(self.clients)

    def health_check(self) -> dict[int, bool]:
        return {emu_id: client.health() for emu_id, client in self.clients.items()}
