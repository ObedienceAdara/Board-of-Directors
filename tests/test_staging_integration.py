from __future__ import annotations

import os
from pathlib import Path

import pytest

import main


pytestmark = pytest.mark.staging


STAGING_BRIEF = {
    "idea": "AI sales assistant for Nigerian SMEs",
    "target_market": "Nigerian small and medium businesses using WhatsApp for sales",
    "budget": "$10000",
    "founder_background": "Technical founder",
    "timeline": "MVP in 12 weeks",
    "constraints": "Bootstrapped; first revenue within 6 months",
}


def test_real_staging_board_run(tmp_path, monkeypatch):
    required = ("GROQ_API_KEY", "TAVILY_API_KEY", "NOTION_API_KEY", "NOTION_DATABASE_ID")
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        pytest.fail("Credentialed staging run is not configured; missing: " + ", ".join(missing))

    monkeypatch.chdir(tmp_path)
    result = main.run_board_meeting(STAGING_BRIEF)

    assert result["status"] == "success", result
    assert result["success"] is True, result
    assert result["final_report"].strip(), result
    assert result["consistency_status"] in {"CONSISTENT", "INCONSISTENT", "INSUFFICIENT_EVIDENCE"}, result
    assert all(status == "passed" for status in result["scheduler_status"].values()), result

    pdf_path = Path(result["pdf_path"])
    assert pdf_path.exists(), result
    assert pdf_path.stat().st_size > 0
    assert result["notion_board_url"].startswith("https://notion.so/"), result
