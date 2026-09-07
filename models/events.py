"""Canonical events representing observations and state changes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CompanyEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str
    occurred_at: datetime = Field(default_factory=utc_now)
    source: str = "system"
    severity: Literal["info", "low", "medium", "high", "critical"] = "info"
    entity_type: str | None = None
    entity_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    state_revision: int | None = Field(default=None, ge=0)


class EventState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recent: list[CompanyEvent] = Field(default_factory=list)
    total_events: int = Field(default=0, ge=0)
    last_event_at: datetime | None = None
