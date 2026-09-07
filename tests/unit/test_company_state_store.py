from __future__ import annotations

import pytest

from models.company import CompanyState
from models.store import JsonCompanyStateStore


def test_json_store_round_trips_company_state(tmp_path) -> None:
    store = JsonCompanyStateStore(tmp_path)
    state = CompanyState(identity={"company_id": "acme", "name": "Acme"})
    state.record_change("strategy", "thesis", "Build trust", source="brief", method="user_input")

    store.save(state)
    loaded = store.load("acme")

    assert loaded is not None
    assert loaded.identity.company_id == "acme"
    assert loaded.identity.name == "Acme"
    assert loaded.revision == 1
    assert loaded.memory.recent_state_changes[-1].field == "thesis"


def test_json_store_detects_optimistic_revision_conflict(tmp_path) -> None:
    store = JsonCompanyStateStore(tmp_path)
    state = CompanyState(identity={"company_id": "acme", "name": "Acme"})
    store.save(state)

    state.record_change("strategy", "thesis", "new", source="brief", method="user_input")
    store.save(state, expected_revision=0)

    stale = CompanyState(identity={"company_id": "acme", "name": "Acme"})
    with pytest.raises(ValueError, match="revision conflict"):
        store.save(stale, expected_revision=0)
