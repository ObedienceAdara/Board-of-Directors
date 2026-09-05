"""Typed models and shared state for Board of Directors."""

from .provenance import build_provenance_ledger, validate_provenance_ledger
from .state import BoardState, BusinessBrief, EVALUATED_AGENTS

__all__ = [
    "BoardState", "BusinessBrief", "EVALUATED_AGENTS",
    "build_provenance_ledger", "validate_provenance_ledger",
]
