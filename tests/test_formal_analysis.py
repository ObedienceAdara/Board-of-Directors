"""Deterministic tests for the v3 business-analysis engine."""

from analysis_engine import validate_cfo, validate_cmo, validate_coo, validate_research
from consistency_engine import consistency_bundle, detect_cross_domain_contradictions


def test_cfo_rejects_incorrect_ltv_cac_ratio():
    result = validate_cfo({
        "currency": "USD",
        "startup_costs": [{"name": "Build", "amount": 1000}],
        "monthly_operating_cost": 500,
        "unit_economics": {"cac": 100, "ltv": 500, "ltv_cac_ratio": 3},
        "revenue_scenarios": {"base": {"annual_revenue": 10000}},
        "break_even_month": 12,
    })
    assert not result["valid"]
    assert any("LTV:CAC ratio" in error for error in result["errors"])


def test_cmo_requires_budget_to_equal_channel_allocations():
    result = validate_cmo({
        "currency": "USD",
        "marketing_budget": 1000,
        "channel_allocations": [
            {"channel": "Search", "amount": 600},
            {"channel": "Content", "amount": 200},
        ],
    })
    assert not result["valid"]
    assert "marketing allocations sum" in result["errors"][0]


def test_coo_derives_payroll_from_headcount_plan():
    result = validate_coo({
        "currency": "USD",
        "headcount_plan": [
            {"role": "Engineer", "count": 2, "annual_salary": 60000},
            {"role": "Operator", "count": 1, "annual_salary": 40000},
        ],
        "annual_payroll": 160000,
    })
    assert result["valid"]
    assert result["derived"]["annual_payroll"] == 160000


def test_researcher_rejects_invalid_market_hierarchy():
    result = validate_research({
        "market": {"currency": "USD", "tam": 100, "sam": 120, "som": 90},
        "evidence": [],
    })
    assert not result["valid"]
    assert "SAM cannot exceed TAM" in result["errors"]


def test_cross_domain_detector_finds_budget_capacity_conflict():
    formal = {
        "cfo": {
            "currency": "USD",
            "monthly_operating_cost": 1000,
            "revenue_scenarios": {},
            "startup_costs": [],
        },
        "cto": {"currency": "USD", "monthly_infrastructure_cost": 800},
        "coo": {
            "currency": "USD",
            "headcount_plan": [{"role": "Ops", "count": 1, "annual_salary": 6000}],
            "monthly_operating_payroll": 500,
        },
    }
    contradictions = detect_cross_domain_contradictions(formal, {})
    assert any(item["id"] == "CD-001" for item in contradictions)


def test_cross_domain_detector_finds_revenue_and_timeline_conflicts():
    formal = {
        "cfo": {"currency": "USD", "monthly_operating_cost": 1000, "revenue_scenarios": {"base": {"annual_revenue": 100000}}, "startup_costs": []},
        "sales": {"currency": "USD", "annual_revenue_target": 180000},
        "head_of_sales": {"currency": "USD", "annual_revenue_target": 180000},
        "cto": {"currency": "USD", "mvp_weeks": 20},
        "cmo": {"currency": "USD", "launch_weeks": 12},
    }
    # Canonical key expected by the production detector is head_of_sales.
    contradictions = detect_cross_domain_contradictions(formal, {})
    assert any(item["id"] == "CD-002" for item in contradictions)
    assert any(item["id"] == "CD-005" for item in contradictions)


def test_consistency_bundle_reports_failure_when_conflicts_exist():
    formal = {
        "cfo": {"currency": "USD", "monthly_operating_cost": 1000, "revenue_scenarios": {}, "startup_costs": []},
        "cto": {"currency": "USD", "monthly_infrastructure_cost": 900},
        "coo": {"currency": "USD", "headcount_plan": [{"role": "Ops", "count": 1, "annual_salary": 6000}], "monthly_operating_payroll": 500},
    }
    validations = {agent: {"valid": True, "errors": [], "claims": []} for agent in formal}
    bundle = consistency_bundle({}, formal, validations)
    assert bundle["integrity_status"] == "FAIL"
    assert bundle["contradiction_count"] >= 1
