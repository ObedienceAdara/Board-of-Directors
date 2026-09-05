"""Unit tests for the Phase 1 evidence/provenance ledger."""

from __future__ import annotations

import json

from models.provenance import build_provenance_ledger, validate_provenance_ledger


def _state() -> dict:
    return {
        "brief": {"idea": "Evidence-first analytics platform"},
        "researcher_formal": {
            "confidence": 0.81,
            "market": {"currency": "USD", "sam": 420000000},
            "evidence": [
                {
                    "claim_id": "market.sam",
                    "claim": "serviceable available market is $420M",
                    "value": 420000000,
                    "unit": "USD",
                    "source_name": "Market Research Publisher",
                    "source_title": "Market outlook 2026",
                    "source_url": "https://example.com/market-2026",
                    "publisher": "Market Research Publisher",
                    "evidence_excerpt": "The serviceable available market is estimated at $420M.",
                    "retrieved_at": "2026-09-05T10:00:00Z",
                    "provider": "tavily",
                    "query": "serviceable available market 2026",
                    "rank": 1,
                }
            ],
        },
        "researcher_validation": {
            "claims": [
                {"id": "market.sam", "value": 420000000, "unit": "USD", "confidence": 0.81}
            ],
            "errors": [],
        },
        "cfo_formal": {
            "currency": "USD",
            "confidence": 0.74,
            "startup_costs": [{"name": "Engineering", "amount": 10000}, {"name": "Legal", "amount": 2000}],
            "unit_economics": {"cac": 50, "ltv": 300, "ltv_cac_ratio": 6},
        },
        "cfo_validation": {
            "claims": [
                {"id": "finance.startup_cost", "value": 12000, "unit": "USD"},
                {"id": "unit_economics.cac", "value": 50, "unit": "USD"},
                {"id": "unit_economics.ltv", "value": 300, "unit": "USD"},
                {"id": "unit_economics.ltv_cac_ratio", "value": 6, "unit": "x"},
            ],
            "errors": [],
        },
        "head_of_sales_formal": {"currency": "USD", "confidence": 0.72, "primary_price": 100, "annual_revenue_target": 420000},
        "head_of_sales_validation": {
            "claims": [
                {"id": "pricing.primary_price", "value": 100, "unit": "USD"},
                {"id": "sales.annual_revenue_target", "value": 420000, "unit": "USD"},
                {"id": "sales.required_annual_customers", "value": 4200, "unit": "customers"},
            ],
            "errors": [],
        },
        "deterministic_contradictions": [],
        "contradiction_adjudication": {"issues": []},
        "consistency_status": "CONSISTENT",
        "final_board_report": "Board recommendation: GO, subject to validating demand and unit economics.",
    }


def test_sourced_claim_has_source_and_retrieval_metadata() -> None:
    ledger = build_provenance_ledger(_state())
    claim = next(item for item in ledger["claims"] if item["claim_id"] == "market.sam")
    assert claim["method"] == "reported"
    assert claim["evidence_refs"]
    assert claim["source_refs"]
    source = next(item for item in ledger["sources"] if item["source_id"] == claim["source_refs"][0])
    assert source["url"] == "https://example.com/market-2026"
    assert source["retrieved_at"] == "2026-09-05T10:00:00Z"
    assert source["retrieval_metadata"]["provider"] == "tavily"
    assert source["retrieval_metadata"]["retrieval_timestamp_recorded"] is True
    evidence = next(item for item in ledger["evidence"] if item["evidence_id"] == claim["evidence_refs"][0])
    assert "420M" in evidence["excerpt"]


def test_missing_retrieval_timestamp_is_not_fabricated() -> None:
    state = _state()
    state["researcher_formal"]["evidence"][0].pop("retrieved_at")
    ledger = build_provenance_ledger(state, generated_at="2026-09-05T11:00:00Z")
    source = ledger["sources"][0]
    assert source["retrieved_at"] is None
    assert source["retrieval_metadata"]["retrieval_timestamp_recorded"] is False
    assert source["retrieval_metadata"]["captured_at"] == "2026-09-05T11:00:00Z"


def test_derived_sales_claim_has_formula_dependencies_and_transformation() -> None:
    ledger = build_provenance_ledger(_state())
    claim = next(item for item in ledger["claims"] if item["claim_id"] == "sales.required_annual_customers")
    assert claim["method"] == "derived"
    assert claim["formula"] == "sales.annual_revenue_target / pricing.primary_price"
    assert claim["dependencies"] == ["sales.annual_revenue_target", "pricing.primary_price"]
    transformation = next(item for item in ledger["transformations"] if item["output_claim_id"] == claim["claim_id"])
    assert transformation["deterministic"] is True
    assert transformation["dependency_claims"] == claim["dependencies"]


def test_derived_finance_claim_has_component_lineage() -> None:
    ledger = build_provenance_ledger(_state())
    claim = next(item for item in ledger["claims"] if item["claim_id"] == "finance.startup_cost")
    assert claim["method"] == "derived"
    assert claim["dependencies"] == ["finance.startup_cost.item.1", "finance.startup_cost.item.2"]
    component_values = {item["claim_id"]: item["value"] for item in ledger["claims"] if item["claim_id"].startswith("finance.startup_cost.item.")}
    assert component_values == {"finance.startup_cost.item.1": 10000.0, "finance.startup_cost.item.2": 2000.0}


def test_agent_assertion_without_source_is_explicitly_unsourced() -> None:
    ledger = build_provenance_ledger(_state())
    claim = next(item for item in ledger["claims"] if item["claim_id"] == "pricing.primary_price")
    assert claim["method"] == "agent_assertion"
    assert claim["source_refs"] == []
    assert claim["evidence_refs"] == []


def test_ledger_is_json_serializable_and_internal_references_validate() -> None:
    ledger = build_provenance_ledger(_state())
    result = validate_provenance_ledger(ledger)
    assert result["valid"] is True, result
    json.dumps(ledger)
    decision = next(item for item in ledger["decisions"] if item["decision_id"] == "board.recommendation")
    assert "market.sam" in decision["claim_refs"]
    assert "sales.required_annual_customers" in decision["claim_refs"]
