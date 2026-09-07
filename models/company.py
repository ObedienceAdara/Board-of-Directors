"""Canonical persistent company world model.

This module is the source-of-truth boundary for organizational reality. Board
execution artifacts may reference or propose changes to this model, but they do
not become canonical merely because an LLM emitted them.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .decisions import DecisionState
from .entities import Competitor, Customer, Employee, Metric, Money, Project, Risk, StateChange
from .events import EventState
from .objectives import ObjectivesState

SCHEMA_VERSION = "1.0"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CompanyIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    industry: str = ""
    target_market: str = ""
    currency: str = "USD"
    founded_at: datetime | None = None


class StrategyState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thesis: str = ""
    priorities: list[str] = Field(default_factory=list)
    competitive_position: str = ""
    strategic_assumptions: list[str] = Field(default_factory=list)


class FinanceState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cash_balance: Money | None = None
    monthly_revenue: Money | None = None
    monthly_operating_costs: Money | None = None
    monthly_net_burn: Money | None = None
    gross_margin: float | None = Field(default=None, ge=-1, le=1)
    contribution_margin: Money | None = None
    runway_months: float | None = Field(default=None, ge=0)
    break_even_month: int | None = Field(default=None, ge=1, le=12)
    twelve_month_revenue: Money | None = None
    twelve_month_operating_profit: Money | None = None
    last_forecast: dict[str, Any] = Field(default_factory=dict)


class SalesState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    monthly_traffic: float | None = Field(default=None, ge=0)
    qualification_rate: float | None = Field(default=None, ge=0, le=1)
    opportunity_rate: float | None = Field(default=None, ge=0, le=1)
    close_rate: float | None = Field(default=None, ge=0, le=1)
    funnel_yield: float | None = Field(default=None, ge=0, le=1)
    annual_revenue_target: Money | None = None
    target_gap: Money | None = None
    pipeline_summary: dict[str, Any] = Field(default_factory=dict)


class MarketingState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    monthly_budget: Money | None = None
    channels: dict[str, float] = Field(default_factory=dict)
    strategy: str = ""


class ProductState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    roadmap_summary: str = ""
    priority_features: list[str] = Field(default_factory=list)
    ranked_features: list[dict[str, Any]] = Field(default_factory=list)


class EngineeringState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    delivery_duration_weeks: float | None = Field(default=None, ge=0)
    active_phases: list[dict[str, Any]] = Field(default_factory=list)
    team_capacity: float | None = Field(default=None, ge=0)
    infrastructure_summary: str = ""


class OperationsState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capacity_customers: float | None = Field(default=None, ge=0)
    capacity_gap_months: list[int] = Field(default_factory=list)
    monthly_payroll: Money | None = None
    twelve_month_payroll: Money | None = None
    operating_summary: str = ""


class WorkforceState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    employees: list[Employee] = Field(default_factory=list)
    headcount: float = Field(default=0, ge=0)
    annual_payroll_run_rate: Money | None = None


class CustomerState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    customers: list[Customer] = Field(default_factory=list)
    active_count: float = Field(default=0, ge=0)
    acquired_this_period: float = Field(default=0, ge=0)
    churned_this_period: float = Field(default=0, ge=0)


class ProjectState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projects: list[Project] = Field(default_factory=list)


class CompetitorState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    competitors: list[Competitor] = Field(default_factory=list)


class RiskState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risks: list[Risk] = Field(default_factory=list)


class PolicyState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    autonomy_level: str = "recommend_only"
    approval_required_for_external_actions: bool = True
    financial_execution_enabled: bool = False
    production_change_enabled: bool = False
    allowed_domains: list[str] = Field(default_factory=list)


class MemoryState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    facts: dict[str, Any] = Field(default_factory=dict)
    recent_state_changes: list[StateChange] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CompanyState(BaseModel):
    """Single canonical representation of the company's current world state."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = SCHEMA_VERSION
    state_id: str = Field(default_factory=lambda: str(uuid4()))
    revision: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    identity: CompanyIdentity = Field(default_factory=CompanyIdentity)
    objectives: ObjectivesState = Field(default_factory=ObjectivesState)
    strategy: StrategyState = Field(default_factory=StrategyState)
    finance: FinanceState = Field(default_factory=FinanceState)
    sales: SalesState = Field(default_factory=SalesState)
    marketing: MarketingState = Field(default_factory=MarketingState)
    product: ProductState = Field(default_factory=ProductState)
    engineering: EngineeringState = Field(default_factory=EngineeringState)
    operations: OperationsState = Field(default_factory=OperationsState)
    workforce: WorkforceState = Field(default_factory=WorkforceState)
    customers: CustomerState = Field(default_factory=CustomerState)
    projects: ProjectState = Field(default_factory=ProjectState)
    competitors: CompetitorState = Field(default_factory=CompetitorState)
    risks: RiskState = Field(default_factory=RiskState)
    decisions: DecisionState = Field(default_factory=DecisionState)
    events: EventState = Field(default_factory=EventState)
    policies: PolicyState = Field(default_factory=PolicyState)
    memory: MemoryState = Field(default_factory=MemoryState)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")

    def record_change(
        self,
        section: str,
        field: str,
        value: Any,
        *,
        source: str,
        method: str,
        provenance_ref: str | None = None,
    ) -> StateChange:
        if source not in {"brief", "deterministic", "agent", "external", "system"}:
            raise ValueError(f"Unsupported state-change source: {source}")
        self.revision += 1
        self.updated_at = utc_now()
        change = StateChange(
            revision=self.revision,
            section=section,
            field=field,
            value=value,
            source=source,
            method=method,
            provenance_ref=provenance_ref,
        )
        self.memory.recent_state_changes.append(change)
        self.memory.recent_state_changes = self.memory.recent_state_changes[-100:]
        return change


def company_state_from_brief(brief: dict[str, Any]) -> CompanyState:
    """Create a conservative world state from a user business brief.

    Free-form values are preserved as context. No financial or operating fact is
    inferred from prose at this boundary; deterministic engines must establish
    authoritative quantitative state later.
    """
    identity = CompanyIdentity(
        name=str(brief.get("company_name") or brief.get("idea") or ""),
        description=str(brief.get("idea") or ""),
        target_market=str(brief.get("target_market") or ""),
        currency=str(brief.get("currency") or "USD")[:3].upper(),
    )
    strategy = StrategyState(
        thesis=str(brief.get("idea") or ""),
        strategic_assumptions=[str(brief.get("constraints"))] if str(brief.get("constraints") or "").strip() else [],
    )
    return CompanyState(identity=identity, strategy=strategy)


def synchronize_deterministic_results(company: CompanyState, calculations: dict[str, Any]) -> CompanyState:
    """Apply validated deterministic calculator outputs to canonical state.

    Only deterministic outputs are promoted to authoritative quantitative state.
    LLM narratives remain transient board artifacts until independently validated.
    """
    currency = company.identity.currency or "USD"
    finance = calculations.get("finance", {})
    if isinstance(finance, dict) and finance:
        company.finance.cash_balance = Money(amount=max(float(finance.get("ending_cash", 0.0)), 0.0), currency=currency)
        company.finance.monthly_revenue = Money(amount=float(finance.get("monthly_revenue", 0.0)), currency=currency)
        company.finance.monthly_operating_costs = Money(amount=float(finance.get("monthly_costs", 0.0)), currency=currency)
        company.finance.monthly_net_burn = Money(amount=max(float(finance.get("net_burn", 0.0)), 0.0), currency=currency)
        company.finance.gross_margin = float(finance.get("gross_margin", 0.0))
        company.finance.contribution_margin = Money(amount=float(finance.get("contribution_margin", 0.0)), currency=currency)
        company.finance.runway_months = finance.get("runway_months")
        company.finance.break_even_month = finance.get("break_even_month")
        company.finance.twelve_month_revenue = Money(amount=float(finance.get("12_month_revenue", 0.0)), currency=currency)
        company.finance.twelve_month_operating_profit = Money(amount=float(finance.get("12_month_operating_profit", 0.0)), currency=currency)
        company.finance.last_forecast = finance
        company.record_change("finance", "last_forecast", {"model": finance.get("model")}, source="deterministic", method="phase2_financial_model")

    sales = calculations.get("sales", {})
    if isinstance(sales, dict) and sales:
        company.sales.funnel_yield = sales.get("funnel_yield")
        target = sales.get("annual_revenue_target")
        gap = sales.get("target_gap")
        if target is not None:
            company.sales.annual_revenue_target = Money(amount=max(float(target), 0.0), currency=currency)
        if gap is not None:
            company.sales.target_gap = Money(amount=float(gap), currency=currency)
        company.sales.pipeline_summary = {
            "ending_customers": sales.get("ending_customers"),
            "required_annual_sales": sales.get("required_annual_sales"),
            "implied_monthly_traffic_for_target": sales.get("implied_monthly_traffic_for_target"),
        }
        if isinstance(sales.get("months"), list) and sales["months"]:
            first = sales["months"][0]
            company.sales.monthly_traffic = first.get("traffic")
        company.record_change("sales", "pipeline_summary", company.sales.pipeline_summary, source="deterministic", method="phase2_sales_funnel")

    operations = calculations.get("operations", {})
    if isinstance(operations, dict) and operations:
        company.operations.capacity_customers = operations.get("peak_capacity_customers")
        company.operations.capacity_gap_months = [int(x) for x in operations.get("capacity_gap_months", [])]
        company.operations.monthly_payroll = Money(amount=float(operations.get("monthly_payroll", 0.0)), currency=currency)
        company.operations.twelve_month_payroll = Money(amount=float(operations.get("12_month_payroll", 0.0)), currency=currency)
        company.workforce.headcount = float(operations.get("peak_headcount", 0.0))
        company.workforce.annual_payroll_run_rate = Money(amount=float(operations.get("annual_payroll_run_rate", 0.0)), currency=currency)
        company.record_change("workforce", "headcount", company.workforce.headcount, source="deterministic", method="phase2_workforce_capacity")

    technical = calculations.get("technical", {})
    if isinstance(technical, dict) and technical:
        company.engineering.delivery_duration_weeks = technical.get("delivery_duration_weeks")
        company.engineering.active_phases = list(technical.get("phases", []))
        company.engineering.team_capacity = technical.get("team_capacity")
        company.record_change("engineering", "delivery_duration_weeks", company.engineering.delivery_duration_weeks, source="deterministic", method="phase2_delivery_model")

    product = calculations.get("product", {})
    if isinstance(product, dict) and product:
        ranked = product.get("features", [])
        company.product.ranked_features = list(ranked) if isinstance(ranked, list) else []
        company.product.priority_features = [str(item.get("name")) for item in company.product.ranked_features if isinstance(item, dict) and item.get("in_scope")][:20]
        company.record_change("product", "ranked_features", len(company.product.ranked_features), source="deterministic", method="phase2_product_priorities")

    company.updated_at = utc_now()
    return company
