"""Formal analysis, consistency, provenance, and domain-calculation interfaces."""

from .calculations import (
    calculate_delivery_model,
    calculate_financial_model,
    calculate_financial_scenarios,
    calculate_product_priorities,
    calculate_sales_funnel,
    calculate_workforce_capacity,
)
from .consistency import consistency_bundle, detect_cross_domain_contradictions
from .formal import compact_json, formalize_agent_output, parse_formal_output
from .phase2 import run_phase2_calculations
from .provenance import build_provenance_ledger, validate_provenance_ledger

__all__ = [
    "compact_json", "formalize_agent_output", "parse_formal_output",
    "consistency_bundle", "detect_cross_domain_contradictions",
    "build_provenance_ledger", "validate_provenance_ledger",
    "calculate_financial_model", "calculate_financial_scenarios", "calculate_sales_funnel",
    "calculate_workforce_capacity", "calculate_delivery_model", "calculate_product_priorities",
    "run_phase2_calculations",
]
