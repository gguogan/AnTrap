"""FastAPI server for managing 8 parallel Android emulators for GRPO training.

Extends the single-emulator pattern from androidworld_test/server/android_server.py
to support 8 parallel emulators with trap injection.

Endpoints are prefixed by emulator index: /emu/{emu_id}/...

Usage:
    # Start 8 emulators first, then:
    uvicorn android_grpo_server:app --host 0.0.0.0 --port 29101

    # Or with auto-reload during development:
    uvicorn android_grpo_server:app --host 0.0.0.0 --port 29101 --reload
"""

import base64
import io
import json
import logging
import traceback
from typing import Any, Optional

import fastapi
import numpy as np
import pydantic
import uvicorn
from PIL import Image

from android_world import registry as aw_registry_module
from android_world import suite_utils
from android_world.disturbances import TrapConfig, TrapController
from android_world.env import env_launcher

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
NUM_EMULATORS = 8
CONSOLE_PORTS = [5554 + 2 * i for i in range(NUM_EMULATORS)]
GRPC_PORTS = [8554 + 2 * i for i in range(NUM_EMULATORS)]
ADB_PATH = "/app/.android/platform-tools/adb"

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class ActionRequest(pydantic.BaseModel):
    action_dict: dict[str, Any]


class TaskRequest(pydantic.BaseModel):
    task_type: str
    task_idx: int


class TrapConfigRequest(pydantic.BaseModel):
    category: str = "none"
    trap_type: str = "none"
    trigger_probability: float = 0.3
    seed: int = 42
    max_traps: int = 0
    params: dict[str, Any] = {}


class TrapScreenshotRequest(pydantic.BaseModel):
    step_idx: int
    ui_elements: Optional[list[Any]] = None


class TrapActionRequest(pydantic.BaseModel):
    action: dict[str, Any]
    dummy_action: dict[str, Any]
    step_idx: int


class SuiteReinitRequest(pydantic.BaseModel):
    n_task_combinations: int = 2
    seed: int = 42
    task_family: str = "android_world"


# ---------------------------------------------------------------------------
# Emulator state
# ---------------------------------------------------------------------------

class EmulatorState:
    """Holds the environment, suite, and trap controller for one emulator."""

    def __init__(self, emu_id: int, env, suite, task_registry):
        self.emu_id = emu_id
        self.env = env
        self.suite = suite
        self.task_registry = task_registry
        self.trap_controller: Optional[TrapController] = None
        self.current_task_type: Optional[str] = None
        self.current_task_idx: Optional[int] = None


# Global state
emulators: dict[int, EmulatorState] = {}
global_task_registry = None


def _screenshot_to_base64(pixels: np.ndarray) -> str:
    """Convert numpy pixel array to base64-encoded JPEG string."""
    img = Image.fromarray(pixels)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _get_emu(emu_id: int) -> EmulatorState:
    if emu_id not in emulators:
        raise fastapi.HTTPException(
            status_code=404, detail=f"Emulator {emu_id} not found"
        )
    return emulators[emu_id]


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------
import contextlib


@contextlib.asynccontextmanager
async def lifespan(fast_api_app: fastapi.FastAPI):
    global global_task_registry

    # Initialize task registry (shared across all emulators)
    global_task_registry = aw_registry_module.TaskRegistry()

    # Initialize each emulator
    for i in range(NUM_EMULATORS):
        logger.info(f"Initializing emulator {i} (console={CONSOLE_PORTS[i]}, grpc={GRPC_PORTS[i]})...")
        try:
            env = env_launcher.load_and_setup_env(
                console_port=CONSOLE_PORTS[i],
                emulator_setup=False,
                freeze_datetime=True,
                adb_path=ADB_PATH,
                grpc_port=GRPC_PORTS[i],
            )
            aw_registry = global_task_registry.get_registry(
                global_task_registry.ANDROID_WORLD_FAMILY
            )
            suite = suite_utils.create_suite(
                task_registry=aw_registry,
                n_task_combinations=2,
                seed=42,
            )
            emulators[i] = EmulatorState(i, env, suite, global_task_registry)
            logger.info(f"Emulator {i} initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize emulator {i}: {e}")
            logger.error(traceback.format_exc())

    logger.info(f"Server ready with {len(emulators)}/{NUM_EMULATORS} emulators.")
    yield

    # Shutdown
    for emu_id, state in emulators.items():
        try:
            state.env.close()
        except Exception:
            pass


app = fastapi.FastAPI(lifespan=lifespan)


# ---------------------------------------------------------------------------
# Global endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    active = [eid for eid in emulators]
    return {"status": "ok", "active_emulators": active, "total": len(emulators)}


@app.get("/suite/task_list")
async def suite_task_list(max_index: int = -1):
    """Return available task types from the first emulator's suite."""
    if not emulators:
        raise fastapi.HTTPException(status_code=503, detail="No emulators available")
    emu = next(iter(emulators.values()))
    keys = list(emu.suite.keys())
    if max_index > 0:
        keys = keys[:max_index]
    return {"task_list": keys, "total": len(emu.suite)}


@app.post("/suite/reinitialize")
async def suite_reinitialize(req: SuiteReinitRequest):
    """Re-initialize task suite for all emulators."""
    try:
        aw_registry = global_task_registry.get_registry(req.task_family)
    except ValueError as exc:
        raise fastapi.HTTPException(
            status_code=400, detail=f"Invalid task family: {req.task_family}"
        ) from exc

    for emu_id, state in emulators.items():
        new_suite = suite_utils.create_suite(
            task_registry=aw_registry,
            n_task_combinations=req.n_task_combinations,
            seed=req.seed,
        )
        state.suite = new_suite

    return {"status": "ok", "message": f"Suite reinitialized for {len(emulators)} emulators"}


# ---------------------------------------------------------------------------
# Per-emulator endpoints
# ---------------------------------------------------------------------------

@app.post("/emu/{emu_id}/reset")
async def emu_reset(emu_id: int, go_home: bool = True):
    """Reset emulator, optionally go home."""
    emu = _get_emu(emu_id)
    try:
        emu.env.reset(go_home=go_home)
        emu.current_task_type = None
        emu.current_task_idx = None
        return {"status": "ok"}
    except Exception as e:
        raise fastapi.HTTPException(status_code=503, detail=str(e))


@app.post("/emu/{emu_id}/task/initialize")
async def emu_task_initialize(emu_id: int, req: TaskRequest):
    """Initialize a specific task on an emulator."""
    emu = _get_emu(emu_id)
    try:
        emu.suite[req.task_type][req.task_idx].initialize_task(emu.env)
        emu.current_task_type = req.task_type
        emu.current_task_idx = req.task_idx
        return {"status": "ok", "task_type": req.task_type, "task_idx": req.task_idx}
    except KeyError:
        raise fastapi.HTTPException(
            status_code=404,
            detail=f"Task {req.task_type}[{req.task_idx}] not found in suite",
        )
    except Exception as e:
        raise fastapi.HTTPException(status_code=503, detail=str(e))


@app.get("/emu/{emu_id}/screenshot")
async def emu_screenshot(emu_id: int, wait_to_stabilize: bool = True):
    """Capture screenshot, return as base64-encoded JPEG."""
    emu = _get_emu(emu_id)
    try:
        state = emu.env.get_state(wait_to_stabilize=wait_to_stabilize)
        b64 = _screenshot_to_base64(state.pixels)
        return {"screenshot": b64, "width": state.pixels.shape[1], "height": state.pixels.shape[0]}
    except Exception as e:
        raise fastapi.HTTPException(status_code=503, detail=str(e))


@app.post("/emu/{emu_id}/execute_action")
async def emu_execute_action(emu_id: int, req: ActionRequest):
    """Execute a JSON action on the emulator."""
    emu = _get_emu(emu_id)
    try:
        from android_world.env import json_action
        action = json_action.JSONAction(**req.action_dict)
        emu.env.execute_action(action)
        return {"status": "ok"}
    except Exception as e:
        raise fastapi.HTTPException(status_code=503, detail=str(e))


@app.get("/emu/{emu_id}/task/score")
async def emu_task_score(emu_id: int):
    """Get task success status."""
    emu = _get_emu(emu_id)
    if emu.current_task_type is None:
        raise fastapi.HTTPException(status_code=400, detail="No task initialized")
    try:
        task = emu.suite[emu.current_task_type][emu.current_task_idx]
        is_successful = task.is_successful(emu.env)
        return {"score": float(is_successful), "is_successful": bool(is_successful)}
    except Exception as e:
        raise fastapi.HTTPException(status_code=503, detail=str(e))


@app.get("/emu/{emu_id}/task/goal")
async def emu_task_goal(emu_id: int):
    """Get task goal description."""
    emu = _get_emu(emu_id)
    if emu.current_task_type is None:
        raise fastapi.HTTPException(status_code=400, detail="No task initialized")
    task = emu.suite[emu.current_task_type][emu.current_task_idx]
    return {"goal": task.goal}


@app.post("/emu/{emu_id}/task/tear_down")
async def emu_task_tear_down(emu_id: int):
    """Tear down current task."""
    emu = _get_emu(emu_id)
    if emu.current_task_type is None:
        return {"status": "ok", "message": "No task to tear down"}
    try:
        task = emu.suite[emu.current_task_type][emu.current_task_idx]
        task.tear_down(emu.env)
        emu.current_task_type = None
        emu.current_task_idx = None
        return {"status": "ok"}
    except Exception as e:
        raise fastapi.HTTPException(status_code=503, detail=str(e))


@app.get("/emu/{emu_id}/health")
async def emu_health(emu_id: int):
    emu = _get_emu(emu_id)
    try:
        # Quick check: try to get state
        emu.env.get_state(wait_to_stabilize=False)
        return {"status": "ok", "emu_id": emu_id}
    except Exception as e:
        return {"status": "error", "emu_id": emu_id, "detail": str(e)}


# ---------------------------------------------------------------------------
# Trap endpoints
# ---------------------------------------------------------------------------

@app.post("/emu/{emu_id}/trap/configure")
async def emu_trap_configure(emu_id: int, req: TrapConfigRequest):
    """Configure TrapController for this emulator."""
    emu = _get_emu(emu_id)
    try:
        config_kwargs = {
            "category": req.category,
            "trap_type": req.trap_type,
            "trigger_probability": req.trigger_probability,
            "seed": req.seed,
            "max_traps": req.max_traps,
        }
        config_kwargs.update(req.params)
        trap_config = TrapConfig(**config_kwargs)
        emu.trap_controller = TrapController(config=trap_config, env=emu.env)
        return {"status": "ok", "category": req.category, "trap_type": req.trap_type}
    except Exception as e:
        raise fastapi.HTTPException(status_code=400, detail=str(e))


@app.post("/emu/{emu_id}/trap/reset")
async def emu_trap_reset(emu_id: int):
    """Reset TrapController state for new episode."""
    emu = _get_emu(emu_id)
    if emu.trap_controller is None:
        return {"status": "ok", "message": "No trap controller configured"}
    emu.trap_controller.reset()
    return {"status": "ok"}


@app.post("/emu/{emu_id}/trap/on_screenshot")
async def emu_trap_on_screenshot(emu_id: int, req: TrapScreenshotRequest):
    """Apply trap to screenshot. Returns modified screenshot as base64 JPEG."""
    emu = _get_emu(emu_id)
    if emu.trap_controller is None:
        raise fastapi.HTTPException(status_code=400, detail="No trap controller configured")
    try:
        # Capture raw screenshot
        state = emu.env.get_state(wait_to_stabilize=True)
        raw_pixels = state.pixels

        # Apply trap
        model_pixels, history_pixels = emu.trap_controller.on_screenshot(
            raw_pixels, req.step_idx, ui_elements=req.ui_elements
        )

        return {
            "screenshot": _screenshot_to_base64(model_pixels),
            "history_screenshot": _screenshot_to_base64(history_pixels),
            "width": model_pixels.shape[1],
            "height": model_pixels.shape[0],
        }
    except Exception as e:
        raise fastapi.HTTPException(status_code=503, detail=str(e))


@app.post("/emu/{emu_id}/trap/on_action")
async def emu_trap_on_action(emu_id: int, req: TrapActionRequest):
    """Apply trap to action before execution. Returns modified action dicts."""
    emu = _get_emu(emu_id)
    if emu.trap_controller is None:
        return {"action": req.action, "dummy_action": req.dummy_action, "modified": False}

    from android_world.env import json_action

    try:
        action_obj = json_action.JSONAction(**req.action)
        dummy_obj = json_action.JSONAction(**req.dummy_action)

        modified_action, modified_dummy = emu.trap_controller.on_action(
            action_obj, dummy_obj, req.step_idx
        )

        return {
            "action": modified_action.__dict__,
            "dummy_action": modified_dummy.__dict__,
            "modified": True,
        }
    except Exception as e:
        logger.warning(f"Trap on_action failed: {e}")
        return {"action": req.action, "dummy_action": req.dummy_action, "modified": False}


@app.get("/emu/{emu_id}/trap/should_block")
async def emu_trap_should_block(emu_id: int, step_idx: int):
    """Check if action execution should be blocked (state deadlock)."""
    emu = _get_emu(emu_id)
    if emu.trap_controller is None:
        return {"should_block": False}
    return {"should_block": emu.trap_controller.should_block_execution(step_idx)}


@app.post("/emu/{emu_id}/trap/pre_step")
async def emu_trap_pre_step(emu_id: int, step_idx: int):
    """Execute pre-step trap injection (context disruption, loop)."""
    emu = _get_emu(emu_id)
    if emu.trap_controller is None:
        return {"status": "ok", "message": "No trap controller"}
    try:
        emu.trap_controller.pre_step(emu.env, step_idx)
        return {"status": "ok"}
    except Exception as e:
        logger.warning(f"Trap pre_step failed: {e}")
        return {"status": "error", "detail": str(e)}


@app.get("/emu/{emu_id}/trap/log")
async def emu_trap_log(emu_id: int):
    """Get trap event log for this emulator."""
    emu = _get_emu(emu_id)
    if emu.trap_controller is None:
        return {"log": []}
    return {"log": emu.trap_controller.get_trap_log()}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="0.0.0.0", port=29101)
