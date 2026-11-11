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
    assert ai_agent._groq_content([item()]) is None


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
    monkeypatch.setattr(groq_fallback.requests, "post", lambda *args, **kwargs: SimpleNamespace(status_code=429))
    assert groq_fallback.request_content("Editor", "Prompt", {}) is None
