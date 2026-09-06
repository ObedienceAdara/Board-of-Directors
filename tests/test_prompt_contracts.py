import formal_agents


def _sample_state() -> dict[str, object]:
    return {
        "brief": {
            "idea": "Test idea",
            "target_market": "Test market",
            "budget": "$1000",
            "founder_background": "Founder",
            "timeline": "12 weeks",
            "constraints": "Bootstrapped",
        },
        "formal_snapshot": {},
    }


def test_all_department_prompts_format_without_template_errors():
    values = {
        "brief": "Test business",
        "task": "Test task",
        "feedback": "No feedback",
        "search_results": "No search results",
        "research_report": "Research",
        "financial_plan": "Finance",
        "tech_plan": "Technology",
        "marketing_plan": "Marketing",
    }

    for prompt in formal_agents.PROMPTS.values():
        formal_agents.template_from_prompt(prompt).format_messages(**values)


def test_ceo_task_assignment_prompt_formats_without_template_errors(monkeypatch):
    monkeypatch.setattr(
        formal_agents,
        "safe_invoke",
        lambda *args, **kwargs: '{"opportunity_summary":"ok","tasks":{}}',
    )

    result = formal_agents.ceo_assign_tasks(_sample_state())

    assert result["ceo_task_assignments"].startswith("{")


def test_ceo_contradiction_prompt_formats_without_template_errors(monkeypatch):
    monkeypatch.setattr(
        formal_agents,
        "safe_invoke",
        lambda *args, **kwargs: '{"overall_status":"CONSISTENT","issues":[],"unresolved_questions":[]}',
    )

    result = formal_agents.ceo_adjudicate_contradictions(_sample_state())

    assert result["consistency_status"] == "CONSISTENT"
    assert result["contradiction_adjudication"]["issues"] == []
