"""Persistence boundary for the canonical CompanyState.

Phase 1 deliberately keeps persistence backend-agnostic. JSON storage provides a
small local/reference implementation while a future database adapter can satisfy
the same contract without changing the world-model schema.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Protocol

from .company import CompanyState


class CompanyStateStore(Protocol):
    def load(self, company_id: str) -> CompanyState | None: ...

    def save(self, state: CompanyState, *, expected_revision: int | None = None) -> CompanyState: ...


class JsonCompanyStateStore:
    """Atomic file-backed CompanyState store for local development and tests."""

    def __init__(self, root: str | os.PathLike[str] = ".bod_state") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, company_id: str) -> Path:
        safe_id = "".join(char for char in company_id if char.isalnum() or char in {"-", "_"})
        if not safe_id:
            raise ValueError("company_id must contain at least one safe filename character")
        return self.root / f"{safe_id}.json"

    def load(self, company_id: str) -> CompanyState | None:
        path = self._path(company_id)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return CompanyState.model_validate(payload)

    def save(self, state: CompanyState, *, expected_revision: int | None = None) -> CompanyState:
        if expected_revision is not None:
            current = self.load(state.identity.company_id)
            current_revision = current.revision if current is not None else 0
            if current_revision != expected_revision:
                raise ValueError(
                    f"CompanyState revision conflict: expected {expected_revision}, current {current_revision}"
                )

        path = self._path(state.identity.company_id)
        payload = json.dumps(state.to_dict(), ensure_ascii=False, indent=2, sort_keys=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{state.identity.company_id}.", suffix=".tmp", dir=self.root)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        except Exception:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise
        return state
