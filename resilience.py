"""Bounded retries for idempotent database requests, never Telegram sends."""

import time

import httpx
import requests

ATTEMPTS = 3
DELAYS = (1, 3)


def transient_error(exc):
    """Schema, authorization and uniqueness failures must not be retried."""
    seen = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        code = str(getattr(exc, "code", ""))
        status = getattr(exc, "status_code", None)
        response = getattr(exc, "response", None)
        status = status or getattr(response, "status_code", None)
        if code in {"23505", "42501", "42P01", "42703"} or status in {400, 401, 403, 404}:
            return False
        if isinstance(exc, (httpx.TransportError, requests.Timeout, requests.ConnectionError)):
            return True
        if status in {408, 429, 500, 502, 503, 504} or code in {"408", "429", "500", "502", "503", "504", "PGRST000", "PGRST001", "PGRST002"}:
            return True
        exc = exc.__cause__
    return False


def execute(query):
    """Identical DB writes are reconciled by their keys/CAS at the caller."""
    for attempt in range(ATTEMPTS):
        try:
            return query.execute()
        except Exception as exc:
            if not transient_error(exc) or attempt + 1 == ATTEMPTS:
                raise
            delay = DELAYS[attempt]
            print(f"  Baza vaqtincha javob bermadi ({type(exc).__name__}); {delay}s dan keyin qayta urinish.")
            time.sleep(delay)
