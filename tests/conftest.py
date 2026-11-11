"""Offline tests must never load production credentials or open sockets."""

import os
import socket
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["PYTHON_DOTENV_DISABLED"] = "1"
for name in list(os.environ):
    if name.startswith(("SUPABASE_", "TELEGRAM_", "GEMINI_API_KEY", "GROQ_")) or name == "ADMIN_ID":
        os.environ.pop(name)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    attempts = []
    def blocked(*args, **kwargs):
        attempts.append(True)
        raise AssertionError("Offline test attempted a network connection")
    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    # curl_cffi uses native sockets, so Python socket patches alone are not enough.
    import requests
    import httpx
    import http_client
    monkeypatch.setattr(requests.Session, "request", blocked)
    monkeypatch.setattr(httpx.Client, "request", blocked)
    if http_client.HAS_CURL:
        monkeypatch.setattr(http_client._curl.Session, "request", blocked)
    yield
    assert not attempts, "Offline test tried a network call that application error handling swallowed"


@pytest.fixture(autouse=True)
def no_groq_pacing(monkeypatch):
    import groq_fallback
    monkeypatch.setattr(groq_fallback, "MIN_EDITORIAL_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(groq_fallback, "_last_editorial_call", None)
