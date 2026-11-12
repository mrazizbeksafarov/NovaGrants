"""Optional Groq editorial fallback; Gemini remains the primary provider."""

import copy
import json
import os
import time

import requests


RETRIES = 1
RETRY_STATUSES = {400, 408, 429, 500, 502, 503, 504}
RETRY_WAIT_SECONDS = 5
# The free tier limits tokens per minute; one digest batch is ~6.5k tokens, so a
# 429 usually clears within a minute. Honour Retry-After up to this cap.
MAX_RATE_LIMIT_WAIT_SECONDS = 65
# Two editorial batches inside one minute exceed that budget, so space them out.
MIN_EDITORIAL_INTERVAL_SECONDS = 60
_last_editorial_call = None


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
    body = {"model": model, "messages": [{"role": "system", "content": system},
                                         {"role": "user", "content": prompt}],
            "response_format": {"type": "json_schema", "json_schema": {
                "name": "nova_grants", "strict": True, "schema": strict_schema(schema)}},
            "reasoning_effort": "medium", "max_completion_tokens": 6000}
    # A strict-schema generation that drifts is rejected with HTTP 400
    # (json_validate_failed); like 429/5xx it is transient, so retry once.
    global _last_editorial_call
    for attempt in range(RETRIES + 1):
        if _last_editorial_call is not None:
            pause = MIN_EDITORIAL_INTERVAL_SECONDS - (time.monotonic() - _last_editorial_call)
            if pause > 0:
                print(f"  Groq minutlik limiti uchun {int(pause)} s kutamiz...")
                time.sleep(pause)
        _last_editorial_call = time.monotonic()
        try:
            response = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": "Bearer " + os.environ["GROQ_API_KEY"].strip()},
                json=body,
                timeout=(15, min(int(os.getenv("AI_TIMEOUT_SECONDS", "240")), 120)),
            )
            if response.status_code != 200:
                print(f"  Groq zaxirasi HTTP {response.status_code} ({_error_code(response)}).")
                if response.status_code in RETRY_STATUSES and attempt < RETRIES:
                    time.sleep(_retry_wait(response))
                    continue
                print("  Groq zaxirasidan mazmun olinmadi; post qilinmaydi.")
                return None
            data = response.json()
            raw = data["choices"][0]["message"]["content"]
            usage = data.get("usage") or {}
            return {"data": json.loads(raw), "usage": {"provider": "groq", "model": model,
                    "prompt": usage.get("prompt_tokens", 0), "output": usage.get("completion_tokens", 0),
                    "total": usage.get("total_tokens", 0)}}
        except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
            print(f"  Groq zaxira xatosi: {type(exc).__name__}")
            if attempt < RETRIES:
                time.sleep(RETRY_WAIT_SECONDS)
                continue
            return None
    return None


def request_text(prompt, max_tokens=400):
    """Short plain-text answer (official-link choice). None on any failure; no retry."""
    if not configured():
        return None
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": "Bearer " + os.environ["GROQ_API_KEY"].strip()},
            json={"model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip(),
                  "messages": [{"role": "user", "content": prompt}],
                  "reasoning_effort": "low", "max_completion_tokens": max_tokens},
            timeout=(15, 60),
        )
        if response.status_code != 200:
            print(f"  Havola AI (Groq) HTTP {response.status_code} ({_error_code(response)}).")
            return None
        return (response.json()["choices"][0]["message"]["content"] or "").strip()
    except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
        print(f"  Havola AI (Groq) xatosi: {type(exc).__name__}")
        return None


def _retry_wait(response):
    if response.status_code != 429:
        return RETRY_WAIT_SECONDS
    headers = getattr(response, "headers", None) or {}
    try:
        wait = float(headers.get("retry-after") or headers.get("Retry-After") or 30)
    except (TypeError, ValueError):
        wait = 30
    return max(RETRY_WAIT_SECONDS, min(wait, MAX_RATE_LIMIT_WAIT_SECONDS))


def _error_code(response):
    """Only the machine-readable code is logged, never the generated text."""
    try:
        error = response.json().get("error") or {}
        return str(error.get("code") or error.get("type") or "unknown")
    except (ValueError, AttributeError):
        return "unknown"
