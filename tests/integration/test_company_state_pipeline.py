from __future__ import annotations

from app.pipeline import initialize_state
from models.company import CompanyState


def test_initialize_state_attaches_canonical_company_state() -> None:
    brief = {
        "idea": "Autonomous inventory platform",
        "target_market": "SMEs",
        "budget": "$100k",
        "constraints": "No external execution",
    }

    state = initialize_state(brief)
    company = state["company_state"]

    assert isinstance(company, CompanyState)
    assert company.identity.name == "Autonomous inventory platform"
    assert company.identity.target_market == "SMEs"
    assert state["brief"] == brief
    assert company.revision == 0


def test_canonical_state_is_serializable_without_replacing_legacy_board_state() -> None:
    state = initialize_state({"idea": "Test company"})
    payload = state["company_state"].to_dict()

    assert payload["schema_version"] == "1.0"
    assert set(
        (
            "identity",
            "objectives",
            "strategy",
            "finance",
            "sales",
            "marketing",
            "product",
            "engineering",
            "operations",
            "workforce",
            "customers",
            "projects",
            "competitors",
            "risks",
            "decisions",
            "events",
            "policies",
            "memory",
        )
    ).issubset(payload)
