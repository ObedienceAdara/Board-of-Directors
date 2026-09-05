"""HTTP API for the board pipeline."""

from __future__ import annotations

import os
import time
from collections import defaultdict
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from langchain_core.runnables import RunnableLambda
from langserve import add_routes

from .pipeline import run_board_meeting

API_SECRET_KEY = os.getenv("API_SECRET_KEY", "")
RATE_LIMIT = max(1, int(os.getenv("RATE_LIMIT_PER_MINUTE", "10")))
EXEMPT_PATHS = {"/", "/docs", "/openapi.json", "/redoc"}
_request_log: dict[str, list[float]] = defaultdict(list)

app = FastAPI(
    title="Plex Hedge — Board of Directors AI",
    description="Formal multi-agent business analysis with deterministic validation, global contradiction adjudication and dynamic scheduling",
    version="3.0.0",
)


@app.middleware("http")
async def security_middleware(request: Request, call_next):
    if request.url.path in EXEMPT_PATHS:
        return await call_next(request)
    if API_SECRET_KEY and request.headers.get("X-API-Key", "") != API_SECRET_KEY:
        return JSONResponse(status_code=401, content={"detail": "Invalid or missing API key."})
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    cutoff = now - 60
    _request_log[client_ip] = [stamp for stamp in _request_log[client_ip] if stamp > cutoff]
    if len(_request_log[client_ip]) >= RATE_LIMIT:
        return JSONResponse(status_code=429, content={"detail": "Rate limit exceeded."})
    _request_log[client_ip].append(now)
    return await call_next(request)


def _invoke_board(inputs: dict[str, Any]) -> dict[str, Any]:
    return run_board_meeting(inputs["brief"])


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
    }
