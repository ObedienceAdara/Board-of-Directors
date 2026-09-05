"""Formal analysis and consistency interfaces."""

from .consistency import consistency_bundle, detect_cross_domain_contradictions
from .formal import compact_json, formalize_agent_output, parse_formal_output

__all__ = [
    "compact_json", "formalize_agent_output", "parse_formal_output",
    "consistency_bundle", "detect_cross_domain_contradictions",
]
