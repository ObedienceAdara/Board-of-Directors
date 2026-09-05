"""Backward-compatible runtime imports.

Canonical runtime status assessment now lives in utils.runtime.
"""

from utils.runtime import AGENTS, FALLBACK_MARKERS, assess_run

__all__ = ["AGENTS", "FALLBACK_MARKERS", "assess_run"]
