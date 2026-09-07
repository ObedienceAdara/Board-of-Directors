"""Decision records for persistent organizational memory."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DecisionOption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    description: str = ""
    score: float | None = None
    expected_outcomes: dict[str, Any] = Field(default_factory=dict)


class DecisionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_id: str = Field(default_factory=lambda: str(uuid4()))
    decision_type: str
    problem: str
    status: Literal["proposed", "approved", "rejected", "executed", "observed", "superseded"] = "proposed"
    created_at: datetime = Field(default_factory=utc_now)
    decided_at: datetime | None = None
    owner: str | None = None
    options: list[DecisionOption] = Field(default_factory=list)
    selected_option_id: str | None = None
    rationale: str = ""
    evidence_refs: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    expected_outcomes: dict[str, Any] = Field(default_factory=dict)
    actual_outcomes: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[DecisionRecord] = Field(default_factory=list)
    active_decision_id: str | None = None
