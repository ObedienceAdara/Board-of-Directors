"""Public interface for deterministic cross-domain consistency checks."""

from consistency_engine import consistency_bundle, detect_cross_domain_contradictions

__all__ = ["consistency_bundle", "detect_cross_domain_contradictions"]
