"""Application configuration bootstrap helpers."""

from __future__ import annotations

import os
from pathlib import Path
from threading import Lock

from dotenv import load_dotenv

_LOADED = False
_LOCK = Lock()
DEPRECATED_GROQ_MODELS = {"llama-3.3-70b-versatile": "openai/gpt-oss-120b"}
DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"


def load_environment() -> None:
    """Load repository configuration exactly once before consumers read it."""
    global _LOADED
    if _LOADED:
        return
    with _LOCK:
        if _LOADED:
            return
        env_path = Path(__file__).resolve().parents[1] / ".env"
        load_dotenv(dotenv_path=env_path, override=False)
        tracing = str(os.getenv("LANGSMITH_TRACING", "false")).strip().lower() in {"1", "true", "yes", "on"}
        os.environ["LANGSMITH_TRACING"] = "true" if tracing else "false"
        os.environ["LANGCHAIN_TRACING_V2"] = "true" if tracing else "false"
        if tracing:
            if not os.getenv("LANGSMITH_PROJECT") and os.getenv("LANGCHAIN_PROJECT"):
                os.environ["LANGSMITH_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "")
            if not os.getenv("LANGSMITH_API_KEY") and os.getenv("LANGCHAIN_API_KEY"):
                os.environ["LANGSMITH_API_KEY"] = os.getenv("LANGCHAIN_API_KEY", "")
        _LOADED = True


def resolve_groq_model(value: str | None = None) -> str:
    """Return the configured Groq model, transparently replacing retired IDs."""
    load_environment()
    candidate = (value or os.getenv("GROQ_MODEL") or DEFAULT_GROQ_MODEL).strip()
    return DEPRECATED_GROQ_MODELS.get(candidate, candidate) or DEFAULT_GROQ_MODEL
