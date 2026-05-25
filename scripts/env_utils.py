"""Auto-load API keys from a `.env` file at repo root.

Looks for (in order of priority):
  <repo>/.env.local   — personal overrides, gitignored
  <repo>/.env         — shared defaults, gitignored

Already-set env vars are NEVER overwritten (so CLI `FOO=bar ./run.sh` still
wins). No-op if python-dotenv is not installed or no file is found.

Usage:
  from scripts.env_utils import load_env
  load_env()  # call once at import time in runner scripts
"""

from __future__ import annotations

import os
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parent.parent


def load_env(verbose: bool = True) -> dict[str, str]:
    """Load .env files into os.environ without overriding existing values."""
    loaded: dict[str, str] = {}
    try:
        from dotenv import dotenv_values  # type: ignore
    except ImportError:
        if verbose:
            print('[env] python-dotenv not installed; skipping .env load')
        return loaded

    for name in ('.env.local', '.env'):
        path = _REPO_ROOT / name
        if not path.is_file():
            continue
        for k, v in dotenv_values(str(path)).items():
            if v is None or k in os.environ:
                continue
            os.environ[k] = v
            loaded[k] = v
        if verbose:
            print(f'[env] Loaded {len(loaded)} keys from {path}')
    return loaded
