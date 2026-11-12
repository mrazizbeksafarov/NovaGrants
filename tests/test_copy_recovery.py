import pytest
from copy import deepcopy

import ai_agent
import main
from test_sources_and_rich import item, card


def test_official_screening_batches_use_one_page_with_all_evidence():
    rows = [item(n, official_evidence_url=f"https://official.example/{n}") for n in range(15)]
    batches = list(main.editorial_batches(rows))
    assert max(map(len, batches)) == 1 and sum(map(len, batches)) == 15


def test_every_official_candidate_in_daily_input_budget_gets_a_decision(monkeypatch):
    rows = [item(n, url=f"https://official.example/{n}", official_evidence_url=f"https://official.example/{n}") for n in range(16)]
    calls = []
    monkeypatch.setattr(main, "DB_READY", False)
    monkeypatch.setattr(main, "DRY_RUN", True)
    def decide(batch):
        calls.extend(batch)
        return {"cards": [], "rejected_urls": [g["url"] for g in batch]}
    monkeypatch.setattr(main, "generate_post_content", decide)
    assert main.publish(rows) == 0
    assert {g["url"] for g in calls} == {g["url"] for g in rows}


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


def test_official_batches_follow_provider_availability(monkeypatch):
    rows = [item(n, url=f"https://official.example/{n}", official_evidence_url=f"https://official.example/{n}",
                 summary="x" * 3000) for n in range(9)]
    monkeypatch.setattr(main.ai_agent, "gemini_available", lambda: True)
    assert [len(b) for b in main.editorial_batches(rows)] == [4, 4, 1]
    monkeypatch.setattr(main.ai_agent, "gemini_available", lambda: False)
    assert [len(b) for b in main.editorial_batches(rows)] == [1] * 9


def test_editorial_phase_stops_at_time_budget_and_leaves_rest_retryable(monkeypatch):
    rows = [item(n, url=f"https://official.example/{n}", official_evidence_url=f"https://official.example/{n}") for n in range(6)]
    monkeypatch.setattr(main, "DB_READY", False)
    monkeypatch.setattr(main, "DRY_RUN", True)
    monkeypatch.setattr(main.ai_agent, "gemini_available", lambda: False)
    clock = [0.0]
    monkeypatch.setattr(main.time, "monotonic", lambda: clock[0])
    seen, saved = [], []
    def decide(batch):
        seen.extend(batch)
        clock[0] += main.EDITORIAL_TIME_BUDGET_SECONDS / 2 + 1
        return {"cards": [], "rejected_urls": [g["url"] for g in batch]}
    monkeypatch.setattr(main, "generate_post_content", decide)
    monkeypatch.setattr(main, "save_grants_batch", saved.extend)
    assert main.publish(rows) == 0
    assert len(seen) == 2
    assert {row["grant"]["url"] for row in saved} == {g["url"] for g in seen}


def test_screening_stops_when_every_provider_is_out_of_quota(monkeypatch):
    rows = [item(n, url=f"https://official.example/{n}", official_evidence_url=f"https://official.example/{n}") for n in range(5)]
    monkeypatch.setattr(main, "DB_READY", False)
    monkeypatch.setattr(main, "DRY_RUN", True)
    monkeypatch.setattr(main.ai_agent, "gemini_available", lambda: False)
    state = {"left": True}
    monkeypatch.setattr(main.ai_agent, "any_provider_available", lambda: state["left"])
    seen, saved = [], []
    def decide(batch):
        seen.extend(batch)
        state["left"] = False
        return None
    monkeypatch.setattr(main, "generate_post_content", decide)
    monkeypatch.setattr(main, "save_grants_batch", saved.extend)
    with pytest.raises(RuntimeError, match="AI"):
        main.publish(rows)
    assert len(seen) == 1 and saved == []
