import formal_agents


def test_ceo_contradiction_prompt_formats_without_template_errors(monkeypatch):
    monkeypatch.setattr(
        formal_agents,
        "safe_invoke",
        lambda *args, **kwargs: '{"overall_status":"CONSISTENT","issues":[],"unresolved_questions":[]}',
    )
    state = {
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

    result = formal_agents.ceo_adjudicate_contradictions(state)

    assert result["consistency_status"] == "CONSISTENT"
    assert result["contradiction_adjudication"]["issues"] == []
