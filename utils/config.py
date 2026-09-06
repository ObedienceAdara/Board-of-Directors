"""Application configuration bootstrap helpers."""

from __future__ import annotations

import os
from pathlib import Path
from threading import Lock

from dotenv import load_dotenv

_LOADED = False
_LOCK = Lock()


def load_environment() -> None:
    """Load local configuration before modules read environment variables.

    The repository `.env` is loaded independently of the process working
    directory. LangSmith tracing is opt-in through the modern `LANGSMITH_*`
    variables; the legacy `LANGCHAIN_TRACING_V2=true` setting is deliberately
    disabled unless the modern opt-in is present, preventing an invalid legacy
    credential from breaking local runs.
    """
    global _LOADED
    if _LOADED:
        return
    with _LOCK:
        if _LOADED:
            return
        env_path = Path(__file__).resolve().parents[1] / ".env"
        load_dotenv(dotenv_path=env_path, override=False)

        tracing = os.getenv("LANGSMITH_TRACING")
        if tracing is None:
            tracing = "false"
        normalized_tracing = tracing.strip().lower() in {"1", "true", "yes", "on"}
        os.environ["LANGSMITH_TRACING"] = "true" if normalized_tracing else "false"
        os.environ["LANGCHAIN_TRACING_V2"] = "true" if normalized_tracing else "false"

        if normalized_tracing and not os.getenv("LANGSMITH_PROJECT"):
            legacy_project = os.getenv("LANGCHAIN_PROJECT", "")
            if legacy_project:
                os.environ["LANGSMITH_PROJECT"] = legacy_project
        if normalized_tracing and not os.getenv("LANGSMITH_API_KEY"):
            legacy_key = os.getenv("LANGCHAIN_API_KEY", "")
            if legacy_key:
                os.environ["LANGSMITH_API_KEY"] = legacy_key

        _LOADED = True
