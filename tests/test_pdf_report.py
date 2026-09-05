from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader

from reports import build_executive_report
from tools.pdf import generate_pdf


def sample_state():
    return {
        "brief": {"idea": "Compact board report test", "founder_background": "Technical founder"},
        "research_report": "Market evidence indicates a focused opportunity.\n- Strong demand signal\n- Competitive gap\n- Main uncertainty is customer willingness to pay",
        "financial_plan": "Economics are viable only with disciplined acquisition and operating costs.\n- Startup cost $10,000\n- Break-even depends on conversion",
        "tech_plan": "MVP can be delivered with a narrow scope.\n- API backend\n- Web dashboard\n- 12-week delivery risk",
        "marketing_plan": "Start with targeted founder-led acquisition.\n- WhatsApp distribution\n- Partnerships\n- Content",
        "sales_strategy": "Use a controlled funnel and validate conversion before scaling.",
        "operations_plan": "Keep the initial team lean and outsource non-core work.",
        "product_roadmap": "MVP prioritizes the core customer workflow and measurable outcomes.",
        "final_board_report": "GO with disciplined validation. The board recommends a narrow MVP followed by measured customer validation.",
        "consistency_status": "CONSISTENT",
        "scheduler_status": {agent: "passed" for agent in ("researcher", "cfo", "cto", "cmo", "coo", "head_of_sales", "pm")},
        "researcher_validation": {"claims": [{"id": "market.sam", "value": 1000000, "unit": "USD"}]},
        "cfo_validation": {"claims": [
            {"id": "finance.startup_cost", "value": 10000, "unit": "USD"},
            {"id": "finance.break_even_month", "value": 8, "unit": "months"},
            {"id": "unit_economics.ltv_cac_ratio", "value": 3.2, "unit": "x"},
        ]},
        "cto_validation": {"claims": [{"id": "technical.mvp_weeks", "value": 12, "unit": "weeks"}]},
        "marketing_validation": {"claims": [{"id": "marketing.budget", "value": 1500, "unit": "USD"}]},
        "coo_validation": {"claims": [{"id": "operations.annual_payroll", "value": 24000, "unit": "USD"}]},
        "head_of_sales_validation": {"claims": [{"id": "sales.annual_revenue_target", "value": 120000, "unit": "USD"}, {"id": "sales.required_annual_customers", "value": 120, "unit": "customers"}]},
        "pm_validation": {"claims": []},
        "deterministic_contradictions": [],
        "contradiction_adjudication": {"issues": []},
    }


def test_executive_report_has_eleven_strategic_pages():
    report = build_executive_report(sample_state())
    assert len(report["pages"]) == 11
    assert report["pages"][0]["title"] == "Executive Decision Brief"
    assert report["pages"][-1]["title"] == "Final Board Recommendation"


def test_pdf_is_twelve_pages_including_cover(tmp_path: Path):
    output = tmp_path / "board.pdf"
    generate_pdf(build_executive_report(sample_state()), str(output))
    reader = PdfReader(str(output))
    assert len(reader.pages) == 12
