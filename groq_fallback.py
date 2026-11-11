"""Optional Groq editorial fallback; Gemini remains the primary provider."""

import copy
import json
import os

import requests


def configured():
    key = os.getenv("GROQ_API_KEY", "").strip()
    return bool(key and not key.startswith("your_"))


def strict_schema(schema):
    """Groq strict output requires every property and forbids extra keys."""
    schema = copy.deepcopy(schema)
    def walk(value):
        if isinstance(value, dict):
            value.pop("default", None)
            if value.get("type") == "object":
                value["additionalProperties"] = False
                value["required"] = list(value.get("properties", {}))
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(schema)
    return schema


def request_content(system, prompt, schema):
    """One bounded call. Returned content still needs shared semantic validation."""
    if not configured():
        return None
    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": "Bearer " + os.environ["GROQ_API_KEY"].strip()},
            json={"model": model, "messages": [{"role": "system", "content": system},
                                               {"role": "user", "content": prompt}],
                  "response_format": {"type": "json_schema", "json_schema": {
                      "name": "nova_grants", "strict": True, "schema": strict_schema(schema)}},
                  "reasoning_effort": "medium", "max_completion_tokens": 6000},
            timeout=(15, min(int(os.getenv("AI_TIMEOUT_SECONDS", "240")), 120)),
        )
        if response.status_code != 200:
            print(f"  Groq zaxirasi HTTP {response.status_code}; mazmun post qilinmaydi.")
            return None
        data = response.json()
        raw = data["choices"][0]["message"]["content"]
        usage = data.get("usage") or {}
        return {"data": json.loads(raw), "usage": {"provider": "groq", "model": model,
                "prompt": usage.get("prompt_tokens", 0), "output": usage.get("completion_tokens", 0),
                "total": usage.get("total_tokens", 0)}}
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
        print(f"  Groq zaxira xatosi: {type(exc).__name__}")
        return None
