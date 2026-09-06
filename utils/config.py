"""Application configuration bootstrap helpers."""

from __future__ import annotations

from pathlib import Path
from threading import Lock

from dotenv import load_dotenv

_LOADED = False
_LOCK = Lock()


def load_environment() -> None:
    """Load the repository's .env file once without overriding real env vars.

    Resolving the path from this module makes startup independent of the current
    working directory and keeps configuration loading before modules that read
    environment variables at import time.
    """
    global _LOADED
    if _LOADED:
        return
    with _LOCK:
        if _LOADED:
            return
        env_path = Path(__file__).resolve().parents[1] / ".env"
        load_dotenv(dotenv_path=env_path, override=False)
        _LOADED = True
