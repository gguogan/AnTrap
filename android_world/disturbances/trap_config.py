"""Trap configuration dataclass."""

import dataclasses
from typing import Optional


VALID_CATEGORIES = ('s_layer', 't_layer', 'a_layer', 'overall', 'none')

VALID_TRAP_TYPES = {
    's_layer': ('visual_obscuration', 'external_interruption'),
    't_layer': ('temporal_conflict', 'visual_hallucination'),
    'a_layer': ('grounding_error', 'type_mismatch', 'intent_deviation'),
    'overall': ('state_deadlock', 'context_disruption', 'loop'),
    'none': ('none',),
}


@dataclasses.dataclass
class TrapConfig:
    """Configuration for a single trap experiment run.

    Each run activates ONE category. trap_type can be:
    - A specific sub-type (e.g., 'grounding_error')
    - 'random': randomly pick from available sub-types each trigger
    """

    category: str = 'none'        # 's_layer' | 't_layer' | 'a_layer' | 'overall' | 'none'
    trap_type: str = 'none'       # Sub-type within category, or 'random'
    trigger_probability: float = 0.3  # Per-step trigger probability
    seed: int = 42                # RNG seed for reproducibility
    max_traps: int = 0            # Max trap events per episode (0 = unlimited)

    # --- S-Layer params ---
    blur_radius: int = 15                # Visual Obscuration: Gaussian blur kernel size
    blur_target: str = 'random_element'  # 'random_element' | 'key_element' | 'random_region'
    patch_color: Optional[tuple] = None  # If set, use solid color patch instead of blur
    popup_apk_package: str = ''          # External Interruption: APK package name

    # --- T-Layer params ---
    temporal_source: str = 'same_episode'  # 'same_episode' | 'preloaded'
    temporal_offset: int = -3              # Steps back for same_episode
    preloaded_screenshot_dir: str = ''     # Path to pre-collected screenshots
    semantic_target: str = 'random_text'   # Which text element to modify
    semantic_replacement: str = ''         # Pre-defined replacement; if empty, use LLM

    # --- A-Layer params ---
    offset_range: tuple = (20, 50)   # Grounding Error: pixel offset range (min, max)
    action_remap: Optional[dict] = None  # Type Mismatch: e.g. {'click': 'long_press'}
    intent_max_distance_frac: float = 0.35  # Intent Deviation: max retarget distance / min(W,H)

    # --- Overall params ---
    deadlock_duration: int = 3       # State Deadlock: consecutive steps to block
    disruption_type: str = 'home'    # Context Disruption: 'home' | 'app_switch'
    loop_interval: int = 2           # Loop: inject BACK every N steps

    # --- Logging ---
    save_tampered_screenshots: bool = True  # Save modified screenshots for debugging

    def __post_init__(self):
        if self.category not in VALID_CATEGORIES:
            raise ValueError(
                f"Invalid category '{self.category}'. Must be one of {VALID_CATEGORIES}"
            )
        valid_types = VALID_TRAP_TYPES.get(self.category, ())
        if self.trap_type != 'random' and self.trap_type not in valid_types:
            raise ValueError(
                f"Invalid trap_type '{self.trap_type}' for category '{self.category}'. "
                f"Must be one of {valid_types} or 'random'"
            )
        if self.action_remap is None:
            self.action_remap = {}
