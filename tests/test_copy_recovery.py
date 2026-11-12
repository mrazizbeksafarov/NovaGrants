from copy import deepcopy

import ai_agent
import main
from test_sources_and_rich import item, card


def test_official_screening_batches_use_one_page_with_all_evidence():
    rows = [item(n, official_evidence_url=f"https://official.example/{n}") for n in range(15)]
    batches = list(main.editorial_batches(rows))
    assert max(map(len, batches)) == 1 and sum(map(len, batches)) == 15


def test_copy_repair_uses_a_smaller_schema_and_keeps_screening_evidence(monkeypatch):
    source = item()
    bad = card(eligibility="O'zbekiston fuqarolari, bakalavr talabalari")
    evidence = deepcopy(bad["screening"])
    data = {"cards": [bad]}
    monkeypatch.setattr(ai_agent, "_copy_repairs", 0)
    monkeypatch.setattr(ai_agent.groq_fallback, "configured", lambda: True)
    captured = []
    def repair(system, prompt, schema):
        captured.append(schema)
        return {"data": {"edits": [{"index": 1, "summary": bad["summary"], "benefits": [],
                 "eligibility": "Bakalavr bosqichida o'qiyotgan nomzodlar", "mandatory_costs": []}]}, "usage": {"total": 12}}
    monkeypatch.setattr(ai_agent.groq_fallback, "request_content", repair)
    result, tokens = ai_agent._repair_public_copy(data, [source])
    assert result["cards"][0]["eligibility"] == "Bakalavr bosqichida o'qiyotgan nomzodlar"
    assert result["cards"][0]["screening"] == evidence
    assert tokens == 12 and "screening" not in str(captured)


def test_copy_editor_cannot_invent_age_or_stipend(monkeypatch):
    source = item()
    bad = card(eligibility="O'zbekiston fuqarolari, bakalavr talabalari")
    original = deepcopy(bad)
    monkeypatch.setattr(ai_agent, "_copy_repairs", 0)
    monkeypatch.setattr(ai_agent.groq_fallback, "configured", lambda: True)
    monkeypatch.setattr(ai_agent.groq_fallback, "request_content", lambda *args: {
        "data": {"edits": [{"index": 1, "summary": bad["summary"], "benefits": ["$9,000 stipendiya"],
                   "eligibility": "18-25 yoshdagi nomzodlar", "mandatory_costs": []}]}, "usage": {}})
    data, _ = ai_agent._repair_public_copy({"cards": [bad]}, [source])
    assert data["cards"][0] == original


def test_copy_repair_has_a_run_wide_limit(monkeypatch):
    monkeypatch.setattr(ai_agent, "_copy_repairs", ai_agent.MAX_COPY_REPAIRS)
    monkeypatch.setattr(ai_agent.groq_fallback, "configured", lambda: True)
    calls = []
    monkeypatch.setattr(ai_agent.groq_fallback, "request_content", lambda *args: calls.append(args))
    data = {"cards": [card(eligibility="O'zbekiston fuqarolari, bakalavr talabalari")]}
    assert ai_agent._repair_public_copy(data, [item()]) == (data, 0)
    assert calls == []


def test_failed_copy_repair_leaves_the_card_unverified(monkeypatch):
    monkeypatch.setattr(ai_agent, "_copy_repairs", 0)
    monkeypatch.setattr(ai_agent.groq_fallback, "configured", lambda: True)
    monkeypatch.setattr(ai_agent.groq_fallback, "request_content", lambda *args: None)
    data = {"cards": [card(eligibility="O'zbekiston fuqarolari, bakalavr talabalari")]}
    result, _ = ai_agent._repair_public_copy(data, [item()])
    reviewed = ai_agent._review_content({"headline": "Test", **result}, [item()], {})
    assert reviewed["cards"] == [] and reviewed["unverified_urls"] == [item()["url"]]
