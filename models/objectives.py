"""Objectives, KPIs, and constraints for the company world model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class KPI(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kpi_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    target: float
    unit: str = ""
    current: float | None = None
    direction: Literal["maximize", "minimize", "maintain"] = "maximize"


class Constraint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    constraint_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    operator: Literal["<=", ">=", "==", "<", ">"]
    value: float | str
    unit: str = ""
    hard: bool = True


class Objective(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""
    status: Literal["draft", "active", "paused", "completed", "cancelled"] = "active"
    priority: float = Field(default=1.0, ge=0)
    deadline: datetime | None = None
    kpis: list[KPI] = Field(default_factory=list)
    constraints: list[Constraint] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class ObjectivesState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objectives: list[Objective] = Field(default_factory=list)
    active_objective_id: str | None = None
