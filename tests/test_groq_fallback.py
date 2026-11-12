import json
from types import SimpleNamespace

import ai_agent
import groq_fallback
from test_sources_and_rich import card, item


def test_strict_schema_requires_every_property_and_forbids_extras():
    schema = groq_fallback.strict_schema(ai_agent.PostContent.model_json_schema())
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    grant = schema["$defs"]["GrantCard"]
    assert grant["additionalProperties"] is False
    assert set(grant["required"]) == set(grant["properties"])


def test_groq_request_uses_fixed_endpoint_and_structured_output(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-secret")
    calls = []
    data = {"choices": [{"message": {"content": json.dumps({"headline": "New", "cards": []})}}],
            "usage": {"total_tokens": 10}}
    def post(url, **kwargs):
        calls.append((url, kwargs))
        return SimpleNamespace(status_code=200, json=lambda: data)
    monkeypatch.setattr(groq_fallback.requests, "post", post)
    result = groq_fallback.request_content("Editor", "Grants", ai_agent.PostContent.model_json_schema())
    assert result["usage"]["provider"] == "groq"
    assert calls[0][0] == "https://api.groq.com/openai/v1/chat/completions"
    assert calls[0][1]["json"]["response_format"]["json_schema"]["strict"] is True


def test_groq_never_publishes_unsupported_eligibility_quote(monkeypatch):
    result = {"data": {"headline": "New", "cards": [card(eligibility_evidence="Invented Uzbekistan guarantee")]},
              "usage": {"total": 100}}
    monkeypatch.setattr(groq_fallback, "request_content", lambda *args: result)
    content = ai_agent._groq_content([item()])
    assert content["cards"] == []
    assert content["unverified_urls"] == [item()["url"]]


def test_groq_keeps_verified_cards_when_another_quote_is_invented(monkeypatch):
    first, second = item(1), item(2, url="https://other.example/award", url_key="other.example/award")
    good = card(index=1, eligibility_evidence=first["summary"])
    bad = card(index=1, eligibility_evidence="Invented Uzbekistan guarantee")
    replies = [{"data": {"headline": "New", "cards": [good]}, "usage": {}},
               {"data": {"headline": "New", "cards": [bad]}, "usage": {}}]
    prompts = []
    def one_by_one(system, prompt, schema):
        prompts.append(prompt)
        return replies.pop(0)
    monkeypatch.setattr(groq_fallback, "request_content", one_by_one)
    content = ai_agent._groq_content([first, second])
    assert len(prompts) == 2 and all("Imkoniyat 2" not in p for p in prompts)
    assert [c["url"] for c in content["cards"]] == [first["url"]]
    assert content["unverified_urls"] == [second["url"]]


def test_groq_uses_original_url_not_model_supplied_link(monkeypatch):
    result = {"data": {"headline": "New", "cards": [card(url="https://invented.example")]}, "usage": {"total": 100}}
    monkeypatch.setattr(groq_fallback, "request_content", lambda *args: result)
    assert ai_agent._groq_content([item()])["cards"][0]["url"] == item()["url"]


def test_groq_is_used_after_gemini_exhaustion(monkeypatch):
    monkeypatch.setattr(ai_agent, "API_KEYS", ["test"])
    monkeypatch.setattr(ai_agent, "MAX_ATTEMPTS", 1)
    def fail(**kwargs):
        raise RuntimeError("503")
    monkeypatch.setattr(ai_agent, "get_client", lambda *args: SimpleNamespace(models=SimpleNamespace(generate_content=fail)))
    expected = {"cards": []}
    monkeypatch.setattr(ai_agent, "_groq_content", lambda grants: expected)
    assert ai_agent.generate_post_content([item()]) is expected


def test_groq_http_failure_does_not_produce_raw_fallback(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setattr(groq_fallback, "RETRY_WAIT_SECONDS", 0)
    monkeypatch.setattr(groq_fallback, "MAX_RATE_LIMIT_WAIT_SECONDS", 0)
    monkeypatch.setattr(groq_fallback.requests, "post", lambda *args, **kwargs: SimpleNamespace(
        status_code=429, json=lambda: {"error": {"code": "rate_limit_exceeded"}}))
    assert groq_fallback.request_content("Editor", "Prompt", {}) is None


def test_groq_retries_once_after_schema_validation_failure(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setattr(groq_fallback, "RETRY_WAIT_SECONDS", 0)
    good = {"choices": [{"message": {"content": json.dumps({"headline": "New", "cards": []})}}], "usage": {}}
    replies = [SimpleNamespace(status_code=400, json=lambda: {"error": {"code": "json_validate_failed"}}),
               SimpleNamespace(status_code=200, json=lambda: good)]
    monkeypatch.setattr(groq_fallback.requests, "post", lambda *args, **kwargs: replies.pop(0))
    assert groq_fallback.request_content("Editor", "Prompt", {})["data"]["headline"] == "New"
    assert replies == []


def test_groq_does_not_retry_authentication_failure(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test")
    calls = []
    def post(*args, **kwargs):
        calls.append(1)
        return SimpleNamespace(status_code=401, json=lambda: {"error": {"code": "invalid_api_key"}})
    monkeypatch.setattr(groq_fallback.requests, "post", post)
    assert groq_fallback.request_content("Editor", "Prompt", {}) is None
    assert len(calls) == 1


def test_primary_gemini_model_is_the_one_that_answers_in_time():
    assert ai_agent.MODEL_CHAIN[0] == "gemini-3.6-flash"


def test_link_choice_uses_groq_and_spares_gemini_quota(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setattr(ai_agent, "API_KEYS", ["test"])
    monkeypatch.setattr(ai_agent, "get_client", lambda *a: (_ for _ in ()).throw(AssertionError("Gemini used")))
    monkeypatch.setattr(groq_fallback, "request_text", lambda prompt: "https://uni.example/apply")
    url = ai_agent.resolve_official_url_with_ai("Award", "text", ["https://agg.example/x", "https://uni.example/apply"])
    assert url == "https://uni.example/apply"


def test_link_choice_rejects_url_outside_candidates(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setattr(ai_agent, "API_KEYS", ["test"])
    monkeypatch.setattr(groq_fallback, "request_text", lambda prompt: "https://invented.example/")
    assert ai_agent.resolve_official_url_with_ai("Award", "text", ["https://uni.example/apply"]) is None


class QuotaError(Exception):
    code = 429


def test_daily_quota_model_is_not_retried_in_later_batches(monkeypatch):
    monkeypatch.setattr(ai_agent, "API_KEYS", ["test"])
    monkeypatch.setattr(ai_agent, "MODEL_CHAIN", ["model-a"])
    monkeypatch.setattr(ai_agent, "_UNAVAILABLE_MODELS", set())
    monkeypatch.setattr(ai_agent.time, "sleep", lambda s: None)
    calls = []
    def quota(**kwargs):
        calls.append(kwargs["model"])
        raise QuotaError("429 RESOURCE_EXHAUSTED. Generate content requests per day limit exceeded on Free Tier.")
    monkeypatch.setattr(ai_agent, "get_client", lambda *a: SimpleNamespace(models=SimpleNamespace(generate_content=quota)))
    monkeypatch.setattr(ai_agent, "_groq_content", lambda grants: None)
    assert ai_agent.generate_post_content([item()]) is None
    assert ai_agent.generate_post_content([item()]) is None
    assert calls == ["model-a"]


def test_rate_limit_retry_honours_retry_after_with_a_cap():
    ok = SimpleNamespace(status_code=429, headers={"retry-after": "41"})
    long = SimpleNamespace(status_code=429, headers={"retry-after": "900"})
    bad = SimpleNamespace(status_code=400, headers={})
    assert groq_fallback._retry_wait(ok) == 41
    assert groq_fallback._retry_wait(long) == groq_fallback.MAX_RATE_LIMIT_WAIT_SECONDS
    assert groq_fallback._retry_wait(bad) == groq_fallback.RETRY_WAIT_SECONDS


def test_editorial_calls_are_spaced_for_the_per_minute_token_limit(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setattr(groq_fallback, "MIN_EDITORIAL_INTERVAL_SECONDS", 60)
    clock = [1000.0]
    pauses = []
    monkeypatch.setattr(groq_fallback.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(groq_fallback.time, "sleep", lambda s: pauses.append(s) or clock.__setitem__(0, clock[0] + s))
    good = {"choices": [{"message": {"content": json.dumps({"headline": "New", "cards": []})}}], "usage": {}}
    monkeypatch.setattr(groq_fallback.requests, "post", lambda *a, **k: SimpleNamespace(status_code=200, json=lambda: good))
    groq_fallback.request_content("Editor", "Prompt", {})
    clock[0] += 15
    groq_fallback.request_content("Editor", "Prompt", {})
    assert pauses == [45]


def test_schema_error_retry_is_paced_before_the_next_generation(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test")
    monkeypatch.setattr(groq_fallback, "MIN_EDITORIAL_INTERVAL_SECONDS", 60)
    clock, times = [1000.0], []
    monkeypatch.setattr(groq_fallback.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(groq_fallback.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0]+seconds))
    def post(*args, **kwargs):
        times.append(clock[0])
        if len(times) == 1:
            return SimpleNamespace(status_code=400, json=lambda: {"error": {"code": "json_validate_failed"}})
        return SimpleNamespace(status_code=200, json=lambda: {"choices": [{"message": {"content": '{"cards":[]}'}}], "usage": {}})
    monkeypatch.setattr(groq_fallback.requests, "post", post)
    assert groq_fallback.request_content("Editor", "Prompt", {}) is not None
    assert times[1]-times[0] >= 60


def test_groq_failure_for_one_candidate_keeps_it_retryable(monkeypatch):
    first, second = item(1), item(2, url="https://other.example/award", url_key="other.example/award")
    replies = [None, {"data": {"headline": "New", "cards": [card(index=1, eligibility_evidence=second["summary"])]}, "usage": {"total": 5}}]
    monkeypatch.setattr(groq_fallback, "request_content", lambda *args: replies.pop(0))
    content = ai_agent._groq_content([first, second])
    assert [c["url"] for c in content["cards"]] == [second["url"]]
    assert first["url"] in content["unverified_urls"]


def test_quota_on_one_key_does_not_disable_the_other_key(monkeypatch):
    monkeypatch.setattr(ai_agent, "API_KEYS", ["key-a", "key-b"])
    monkeypatch.setattr(ai_agent, "MODEL_CHAIN", ["model-a"])
    monkeypatch.setattr(ai_agent, "_UNAVAILABLE_MODELS", set())
    assert ai_agent._mark_unavailable("model-a", QuotaError("429 per day limit exceeded"), 0)
    assert ai_agent.gemini_available()
    assert ai_agent._usable_key("model-a") == 1
    ai_agent._mark_unavailable("model-a", QuotaError("429 per day limit exceeded"), 1)
    assert not ai_agent.gemini_available()
