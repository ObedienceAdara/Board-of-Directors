from __future__ import annotations

from analysis_engine import validate_cfo, validate_cmo, validate_coo, validate_cto, validate_research, validate_sales
from consistency_engine import consistency_bundle, detect_cross_domain_contradictions


def test_cfo_rejects_negative_or_missing_core_inputs() -> None:
    missing = validate_cfo({"currency": "USD", "startup_costs": [], "cogs_per_customer": 0, "cogs_percent_revenue": 0})
    assert not missing["valid"]
    assert any("starting_cash" in error for error in missing["errors"])
    negative = validate_cfo({"currency": "USD", "starting_cash": -1, "startup_costs": [], "cogs_per_customer": 0, "cogs_percent_revenue": 0, "monthly_budget_by_category": {}})
    assert not negative["valid"]


def test_cmo_requires_budget_to_equal_channel_allocations_and_period() -> None:
    result = validate_cmo({"currency": "USD", "marketing_budget": 1000, "budget_period": "month", "channel_allocations": [{"channel": "Search", "amount": 600}, {"channel": "Content", "amount": 200}]})
    assert not result["valid"]
    assert any("allocations sum" in error for error in result["errors"])


def test_coo_derives_payroll_from_headcount_plan() -> None:
    result = validate_coo({"currency": "USD", "headcount_plan": [{"role": "Engineer", "count": 2, "annual_salary": 60000, "start_month": 1}, {"role": "Operator", "count": 1, "annual_salary": 40000, "start_month": 1}], "annual_payroll": 160000, "workload_hours_per_customer": 1})
    assert result["valid"]
    assert result["derived"]["annual_payroll"] == 160000


def test_researcher_rejects_invalid_market_hierarchy() -> None:
    result = validate_research({"market": {"currency": "USD", "tam": 100, "sam": 120, "som": 90}, "evidence": []})
    assert not result["valid"]
    assert "SAM cannot exceed TAM" in result["errors"]


def test_sales_requires_explicit_price_period_and_adjacent_funnel_rates() -> None:
    result = validate_sales({"currency": "USD", "primary_price": 100, "starting_customers": 0, "annual_revenue_target": 12000, "monthly_traffic": [100], "qualification_rate": 0.5, "opportunity_rate": 0.5, "close_rate": 0.2, "monthly_churn_rate": 0})
    assert not result["valid"]
    assert any("price_period" in error for error in result["errors"])


def test_cto_rejects_cycles_and_zero_capacity() -> None:
    result = validate_cto({"currency": "USD", "development_phases": [{"name": "A", "weeks": 1, "dependencies": ["B"]}, {"name": "B", "weeks": 1, "dependencies": ["A"]}], "engineering_team": [{"count": 0, "weekly_capacity_weeks": 1}]})
    assert not result["valid"]
    assert any("cycle" in error for error in result["errors"])
    assert any("capacity" in error for error in result["errors"])


def test_cross_domain_detector_uses_current_phase2_schema() -> None:
    formal = {
        "cfo": {"currency": "USD", "starting_cash": 1000, "startup_costs": [], "cogs_per_customer": 0, "cogs_percent_revenue": 0, "monthly_budget_by_category": {"infrastructure": 100}},
        "cto": {"currency": "USD", "monthly_infrastructure_cost": 800, "development_phases": [{"name": "Build", "weeks": 1, "dependencies": []}], "engineering_team": [{"count": 1, "weekly_capacity_weeks": 1}]},
        "coo": {"currency": "USD", "headcount_plan": [{"role": "Ops", "count": 1, "annual_salary": 24000, "start_month": 1}], "workload_hours_per_customer": 1},
        "head_of_sales": {"currency": "USD", "annual_revenue_target": 120000, "primary_price": 100, "price_period": "month"},
        "researcher": {"market": {"currency": "USD", "som": 50000}, "evidence": []},
        "cmo": {"currency": "USD", "marketing_budget": 1200, "budget_period": "year", "channel_allocations": [{"channel": "Organic", "amount": 1200}]},
    }
    contradictions = detect_cross_domain_contradictions(formal, {})
    assert any(item["id"] == "CD-001" for item in contradictions)
    assert any(item["id"] == "CD-005" for item in contradictions)


def test_consistency_bundle_reports_failure_when_conflicts_exist() -> None:
    formal = {"cfo": {"currency": "USD", "starting_cash": 1000, "startup_costs": [], "cogs_per_customer": 0, "cogs_percent_revenue": 0, "monthly_budget_by_category": {"infrastructure": 100}}, "cto": {"currency": "USD", "monthly_infrastructure_cost": 900, "development_phases": [{"name": "Build", "weeks": 1, "dependencies": []}], "engineering_team": [{"count": 1, "weekly_capacity_weeks": 1}]}}
    validations = {agent: {"valid": True, "errors": [], "claims": []} for agent in formal}
    bundle = consistency_bundle({}, formal, validations)
    assert bundle["integrity_status"] == "FAIL"
    assert bundle["contradiction_count"] >= 1
