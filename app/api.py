"""HTTP API for the board pipeline."""

from __future__ import annotations

import os
import time
from collections import defaultdict
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from langchain_core.runnables import RunnableLambda
from langserve import add_routes
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.pipeline import run_board_meeting
from utils.config import load_environment

load_environment()

API_SECRET_KEY = os.getenv("API_SECRET_KEY", "").strip()
APP_ENV = os.getenv("APP_ENV", "production").strip().lower()
RATE_LIMIT = max(1, int(os.getenv("RATE_LIMIT_PER_MINUTE", "10")))
MAX_REQUEST_BYTES = max(1024, int(os.getenv("MAX_REQUEST_BYTES", "65536")))
AUTH_REQUIRED = APP_ENV not in {"development", "test"}
EXEMPT_PATHS = {"/", "/docs", "/openapi.json", "/redoc"}
_request_log: dict[str, list[float]] = defaultdict(list)


class BoardMeetingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    brief: dict[str, Any] = Field(min_length=1)

    @field_validator("brief")
    @classmethod
    def validate_brief(cls, value: dict[str, Any]) -> dict[str, Any]:
        allowed = {"idea", "target_market", "budget", "founder_background", "timeline", "constraints"}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError(f"Unknown brief fields: {sorted(unknown)}")
        lengths = {"idea": 500, "target_market": 300, "budget": 100, "founder_background": 300, "timeline": 100, "constraints": 300}
        idea = str(value.get("idea", "")).strip()
        if not idea:
            raise ValueError("brief.idea is required")
        for key, limit in lengths.items():
            if len(str(value.get(key, ""))) > limit:
                raise ValueError(f"brief.{key} cannot exceed {limit} characters")
        return value


app = FastAPI(
    title="Plex Hedge — Board of Directors AI",
    description="Formal multi-agent business analysis with deterministic validation, global contradiction adjudication and dynamic scheduling",
    version="3.0.0",
)


@app.middleware("http")
async def security_middleware(request: Request, call_next: Callable[[Request], Awaitable[Any]]) -> Any:
    if request.url.path in EXEMPT_PATHS:
        return await call_next(request)

    if request.method == "POST":
        try:
            content_length = int(request.headers.get("content-length", "0"))
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header."})
        if content_length > MAX_REQUEST_BYTES:
            return JSONResponse(status_code=413, content={"detail": "Request body too large."})
        body = await request.body()
        if len(body) > MAX_REQUEST_BYTES:
            return JSONResponse(status_code=413, content={"detail": "Request body too large."})
        async def receive() -> dict[str, Any]:
            return {"type": "http.request", "body": body, "more_body": False}
        request = Request(request.scope, receive)

    if not API_SECRET_KEY:
        if AUTH_REQUIRED:
            return JSONResponse(status_code=503, content={"detail": "API_SECRET_KEY is not configured for this environment."})
    elif request.headers.get("X-API-Key", "") != API_SECRET_KEY:
        return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key."})

    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    cutoff = now - 60
    history = [stamp for stamp in _request_log[client_ip] if stamp > cutoff]
    if len(history) >= RATE_LIMIT:
        _request_log[client_ip] = history
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded."})
    history.append(now)
    _request_log[client_ip] = history
    return await call_next(request)


def _invoke_board(inputs: dict[str, Any]) -> dict[str, Any]:
    request = BoardMeetingRequest.model_validate(inputs)
    return run_board_meeting(request.brief)


board_runnable: RunnableLambda = RunnableLambda(_invoke_board)
add_routes(app, board_runnable, path="/board-meeting")


@app.get("/")
async def root() -> dict[str, Any]:
    return {
        "status": "running",
        "version": "3.0.0",
        "architecture": "dynamic-readiness + formal-validation + deterministic-contradiction-detection + LLM-adjudication",
        "agents": ["CEO", "Researcher", "CFO", "CTO", "CMO", "Head of Sales", "COO", "PM"],
        "docs": "/docs",
        "playground": "/board-meeting/playground",
        "authentication_required": AUTH_REQUIRED,
    }
