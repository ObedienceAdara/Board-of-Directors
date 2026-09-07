from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from models.company import CompanyState, company_state_from_brief, synchronize_deterministic_results
from models.entities import Customer, Employee, Money


def test_company_state_has_single_canonical_domain_surface() -> None:
    state = CompanyState()

    assert state.schema_version == "1.0"
    assert state.revision == 0
    assert state.identity.currency == "USD"
    assert state.finance.monthly_revenue is None
    assert state.sales.pipeline_summary == {}
    assert state.customers.active_count == 0
    assert state.workforce.headcount == 0
    assert state.decisions.records == []
    assert state.events.total_events == 0
    assert state.policies.autonomy_level == "recommend_only"


def test_company_state_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        CompanyState(unknown_field="must-not-be-accepted")


def test_company_state_from_brief_does_not_invent_numeric_truth() -> None:
    state = company_state_from_brief(
        {
            "idea": "AI sales assistant",
            "target_market": "Nigerian SMEs",
            "constraints": "Preserve 12 months runway",
        }
    )

    assert state.identity.name == "AI sales assistant"
    assert state.identity.target_market == "Nigerian SMEs"
    assert state.strategy.thesis == "AI sales assistant"
    assert state.finance.cash_balance is None
    assert state.customers.active_count == 0
    assert state.workforce.headcount == 0


def test_record_change_is_revisioned_and_bounded() -> None:
    state = CompanyState()

    change = state.record_change(
        "finance",
        "monthly_revenue",
        1000.0,
        source="deterministic",
        method="phase2_financial_model",
        provenance_ref="CLAIM-0001",
    )

    assert state.revision == 1
    assert change.revision == 1
    assert change.section == "finance"
    assert change.source == "deterministic"
    assert state.memory.recent_state_changes[-1].provenance_ref == "CLAIM-0001"

    with pytest.raises(ValueError):
        state.record_change("finance", "cash_balance", 1, source="invented", method="bad")


def test_deterministic_results_update_canonical_state() -> None:
    state = CompanyState(identity={"currency": "USD"})

    synchronize_deterministic_results(
        state,
        {
            "finance": {
                "model": "deterministic_financial_v2",
                "ending_cash": 42000,
                "monthly_revenue": 8500,
                "monthly_costs": 9100,
                "net_burn": 600,
                "gross_margin": 0.72,
                "contribution_margin": -100,
                "runway_months": 10.5,
                "break_even_month": 7,
                "12_month_revenue": 110000,
                "12_month_operating_profit": -12000,
            },
            "sales": {
                "funnel_yield": 0.08,
                "annual_revenue_target": 120000,
                "target_gap": 10000,
                "ending_customers": 145,
                "months": [{"traffic": 1000}],
            },
            "operations": {
                "peak_capacity_customers": 160,
                "capacity_gap_months": [1, 2],
                "monthly_payroll": 12000,
                "12_month_payroll": 144000,
                "peak_headcount": 4,
                "annual_payroll_run_rate": 168000,
            },
            "technical": {
                "delivery_duration_weeks": 11,
                "phases": [{"name": "MVP", "weeks": 6}],
                "team_capacity": 320,
            },
            "product": {
                "features": [
                    {"name": "Billing", "priority_score": 9.0, "in_scope": True},
                    {"name": "Themes", "priority_score": 2.0, "in_scope": False},
                ]
            },
        },
    )

    assert state.finance.monthly_revenue == Money(amount=8500, currency="USD")
    assert state.finance.contribution_margin == Money(amount=-100, currency="USD")
    assert state.sales.pipeline_summary["ending_customers"] == 145
    assert state.operations.capacity_gap_months == [1, 2]
    assert state.workforce.headcount == 4
    assert state.engineering.delivery_duration_weeks == 11
    assert state.product.priority_features == ["Billing"]
    assert state.revision >= 5


def test_entity_models_are_typed_and_serializable() -> None:
    customer = Customer(name="Acme", status="active")
    employee = Employee(role="Engineer", department="engineering", annual_salary={"amount": 48000, "currency": "USD"})

    payload = {
        "customer": customer.model_dump(mode="json"),
        "employee": employee.model_dump(mode="json"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    assert payload["customer"]["status"] == "active"
    assert payload["employee"]["annual_salary"]["amount"] == 48000
