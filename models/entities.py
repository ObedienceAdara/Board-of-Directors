"""Canonical business entities used by the company world model."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EntityRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: str
    entity_id: str


class Money(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: float = Field(ge=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)


class Metric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: float
    unit: str = ""
    as_of: datetime = Field(default_factory=utc_now)
    source: Literal["brief", "deterministic", "agent", "external", "system"] = "system"
    confidence: float = Field(default=1.0, ge=0, le=1)
    provenance_ref: str | None = None


class Customer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customer_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    status: Literal["prospect", "active", "churned", "inactive"] = "prospect"
    segment: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Employee(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employee_id: str = Field(default_factory=lambda: str(uuid4()))
    role: str
    department: str
    status: Literal["planned", "active", "inactive"] = "planned"
    start_month: int | None = Field(default=None, ge=1, le=12)
    annual_salary: Money | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    status: Literal["planned", "active", "blocked", "completed", "cancelled"] = "planned"
    owner: str | None = None
    priority: float = Field(default=0.0, ge=0)
    deadline: datetime | None = None
    dependencies: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Competitor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    competitor_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    status: Literal["active", "watch", "inactive"] = "active"
    threat_level: float = Field(default=0.0, ge=0, le=1)
    notes: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class Risk(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    category: str
    probability: float = Field(default=0.0, ge=0, le=1)
    impact: float = Field(default=0.0, ge=0, le=1)
    status: Literal["open", "mitigating", "accepted", "closed"] = "open"
    owner: str | None = None
    mitigations: list[str] = Field(default_factory=list)


class StateChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    revision: int = Field(ge=1)
    changed_at: datetime = Field(default_factory=utc_now)
    section: str
    field: str
    value: Any
    source: Literal["brief", "deterministic", "agent", "external", "system"]
    method: str
    provenance_ref: str | None = None
