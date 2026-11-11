"""Regressions found in the November 2026 code and production-log audit."""

import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import ai_agent
import database
import main
import telegram_bot
import http_client
from filters import deadline_passed, extract_deadline, validate_deadline_iso
from link_resolver import link_matches_title, STRONG_ANCHOR_SCORE


def grant(n=1):
    return {
        "title": f"Research Fellowship {n}", "summary": "International students may apply.",
        "url": f"https://university.example/apply/{n}",
        "url_key": f"university.example/apply/{n}",
        "source_url": f"https://news.example/grant/{n}",
        "source_key": f"news.example/grant/{n}", "fingerprint": f"research-{n}",
    }


@pytest.mark.parametrize("url", [
    "https://awfchuckwallprogram.submit.com/show/18",
    "https://thebarackobamafoundation.submittable.com/submit",
    "https://example.org/whole-youth-fellowship",
])
def test_application_platform_is_not_mit_or_who(url):
    assert link_matches_title("Global Youth Fellowship", url, STRONG_ANCHOR_SCORE)[0]


def test_real_university_mismatch_is_still_rejected():
    assert not link_matches_title(
        "Oxford Research Fellowship", "https://mit.edu/apply", STRONG_ANCHOR_SCORE)[0]


def configure_ai(monkeypatch, replies):
    replies = iter(replies)
    def generate(**kwargs):
        result = next(replies)
        if isinstance(result, Exception):
            raise result
        return SimpleNamespace(text=result, usage_metadata=None)
    cli = SimpleNamespace(models=SimpleNamespace(generate_content=generate))
    monkeypatch.setattr(ai_agent, "API_KEYS", ["test-key"])
    monkeypatch.setattr(ai_agent, "get_client", lambda *args: cli)
    monkeypatch.setattr(ai_agent, "MAX_ATTEMPTS", 2)
    monkeypatch.setattr(ai_agent.time, "sleep", lambda *args: None)


def test_ai_failure_does_not_publish_unreviewed_source_text(monkeypatch):
    configure_ai(monkeypatch, [RuntimeError("503"), RuntimeError("503")])
    assert ai_agent.generate_post_content([grant()]) is None


def test_missing_ai_key_is_not_a_successful_post(monkeypatch):
    monkeypatch.setattr(ai_agent, "API_KEYS", [])
    assert ai_agent.generate_post_content([grant()]) is None


def test_intentional_ai_rejection_is_distinct_from_failure(monkeypatch):
    configure_ai(monkeypatch, [json.dumps({"headline": "No matches", "cards": []})])
    content = ai_agent.generate_post_content([grant()])
    assert content is not None and content["cards"] == []


def test_malformed_ai_json_shape_is_retried(monkeypatch):
    configure_ai(monkeypatch, ['[]', '{"headline":"New","cards":[]}'])
    assert ai_agent.generate_post_content([grant()])["cards"] == []


def test_missing_cards_is_not_an_intentional_rejection(monkeypatch):
    configure_ai(monkeypatch, ['{"headline":"Incomplete"}'] * 2)
    assert ai_agent.generate_post_content([grant()]) is None


def test_invalid_index_does_not_silently_skip_a_source(monkeypatch):
    payload = {"headline": "New", "cards": [{"index": 99, "name": "Fellowship", "summary": "Details"}]}
    configure_ai(monkeypatch, [json.dumps(payload)] * 2)
    assert ai_agent.generate_post_content([grant()]) is None


def test_ai_cannot_invent_official_link(monkeypatch):
    configure_ai(monkeypatch, ["https://invented.example/apply"] * 2)
    assert ai_agent.resolve_official_url_with_ai("Research Fellowship", "", [grant()["url"]]) is None


def test_ai_can_select_a_supplied_link(monkeypatch):
    configure_ai(monkeypatch, [grant()["url"]])
    assert ai_agent.resolve_official_url_with_ai("Research Fellowship", "", [grant()["url"]]) == grant()["url"]


def test_ai_duplicate_indexes_keep_only_one_card():
    cards = [{"index": 1, "name": "Fellowship", "summary": "Details"}] * 2
    content = ai_agent._attach_urls({"cards": cards}, [grant()])
    assert len(content["cards"]) == 1


def test_many_ai_keys_cannot_create_unbounded_retries(monkeypatch):
    calls = []
    def fail(**kwargs):
        calls.append(kwargs["model"])
        raise RuntimeError("503")
    cli = SimpleNamespace(models=SimpleNamespace(generate_content=fail))
    monkeypatch.setattr(ai_agent, "API_KEYS", [f"test-{i}" for i in range(9)])
    monkeypatch.setattr(ai_agent, "get_client", lambda *args: cli)
    monkeypatch.setattr(ai_agent.time, "sleep", lambda *args: None)
    assert ai_agent.generate_post_content([grant()]) is None
    assert len(calls) == 4
    assert calls[:2] == [ai_agent.MODEL_CHAIN[0]] * 2
    assert set(calls) == set(ai_agent.MODEL_CHAIN)


def test_link_selection_has_a_small_attempt_budget(monkeypatch):
    calls = []
    def fail(**kwargs):
        calls.append(kwargs["model"])
        raise RuntimeError("503")
    cli = SimpleNamespace(models=SimpleNamespace(generate_content=fail))
    monkeypatch.setattr(ai_agent, "API_KEYS", [f"test-{i}" for i in range(9)])
    monkeypatch.setattr(ai_agent, "get_client", lambda *args: cli)
    assert ai_agent.resolve_official_url_with_ai("Fellowship", "", [grant()["url"]]) is None
    assert len(calls) == 2


def test_network_timeout_does_not_retry_all_browser_profiles(monkeypatch):
    calls = []
    def fail(*args, **kwargs):
        calls.append(kwargs["impersonate"])
        raise TimeoutError()
    client = http_client.Client()
    client._curl_session = SimpleNamespace(get=fail)
    assert client._curl_get("https://example.org") is None
    assert len(calls) == 1


def test_publish_failure_leaves_sources_retryable(monkeypatch):
    saved = []
    monkeypatch.setattr(main, "generate_post_content", lambda batch: None)
    monkeypatch.setattr(main, "save_grants_batch", saved.extend)
    with pytest.raises(RuntimeError, match="AI"):
        main.publish([grant()])
    assert saved == []


def test_telegram_failure_is_not_a_successful_run(monkeypatch):
    saved = []
    g = grant()
    content = {"headline": "New", "cards": [{"name": g["title"], "url": g["url"], "_source": g}]}
    monkeypatch.setattr(main, "generate_post_content", lambda batch: content)
    monkeypatch.setattr(main, "publish_post", lambda *args: False)
    monkeypatch.setattr(main, "save_grants_batch", saved.extend)
    with pytest.raises(RuntimeError, match="Telegram"):
        main.publish([g])
    assert saved == []


def test_all_sources_down_is_not_reported_as_no_new_grants(monkeypatch):
    monkeypatch.setattr(main, "fetch_all", lambda: [])
    with pytest.raises(RuntimeError, match="manba"):
        main.collect_candidates()


def test_resolver_failure_does_not_permanently_skip_source(monkeypatch):
    saved = []
    monkeypatch.setattr(main, "resolve_grant", lambda g: {**g, "url": ""})
    monkeypatch.setattr(main, "save_grants_batch", saved.extend)
    assert main.resolve_links([grant()]) == []
    assert saved == []


def test_resolve_budget_is_shared_across_sources(monkeypatch):
    visited = []
    def resolve(g):
        visited.append(g["source_id"])
        return g
    monkeypatch.setattr(main, "MAX_RESOLVE_PER_RUN", 3)
    monkeypatch.setattr(main, "RESOLVE_WORKERS", 1)
    monkeypatch.setattr(main, "resolve_grant", resolve)
    items = [{**grant(i), "source_id": "first"} for i in range(10)]
    items += [{**grant(99), "source_id": "second"}]
    main.resolve_links(items)
    assert visited == ["first", "second", "first"]


def test_dry_run_preview_never_calls_telegram(monkeypatch):
    monkeypatch.setattr(main, "DRY_RUN", True)
    assert main.publish_post([{"type": "paragraph", "text": "Preview"}], "Preview")


def test_missing_telegram_credentials_returns_failure(monkeypatch):
    monkeypatch.setattr(telegram_bot, "BOT_TOKEN", None)
    assert telegram_bot.send_telegram_message("hello") is False


def test_admin_target_does_not_require_channel_setting(monkeypatch):
    monkeypatch.setattr(telegram_bot, "BOT_TOKEN", "test")
    monkeypatch.setattr(telegram_bot, "CHANNEL_ID", None)
    sent = []
    monkeypatch.setattr(telegram_bot, "_post", lambda payload: (sent.append(payload) or True, ""))
    assert telegram_bot.send_telegram_message("hello", target_chat_id="admin")
    assert sent[0]["chat_id"] == "admin"


def test_expired_numeric_deadline_is_filtered():
    past = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%d.%m.%Y")
    assert deadline_passed(f"Fully funded fellowship. Deadline: {past}.")


def test_event_start_is_not_used_as_application_deadline():
    year = datetime.now(timezone.utc).year + 1
    assert extract_deadline(f"The summer school starts 15 March {year}.") is None


def test_multiple_rounds_keep_the_open_deadline():
    past = (datetime.now(timezone.utc) - timedelta(days=10)).strftime("%Y-%m-%d")
    future = (datetime.now(timezone.utc) + timedelta(days=10)).strftime("%Y-%m-%d")
    assert not deadline_passed(f"Early deadline: {past}\nFinal deadline: {future}")


@pytest.mark.parametrize("date", ["15 dekabr", "15-dekabr"])
def test_uzbek_deadline_month(date):
    year = datetime.now(timezone.utc).year + 1
    assert extract_deadline(f"Oxirgi muddat: {date} {year}").month == 12


def test_deadline_uses_actual_time_and_rejects_garbage():
    expired = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    assert validate_deadline_iso(expired) is None
    assert validate_deadline_iso("2090-12-15garbage") is None
    future = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d")
    assert validate_deadline_iso(future).endswith("T23:59:59Z")


class FakeDatabase:
    """Enforce both UNIQUE(url) and UNIQUE(url_key), as the live schema does."""
    def __init__(self, rows=()):
        self.rows = deepcopy(list(rows))
        self.fail_reads = False
        self.fail_writes = False
        self.race_row = None
        self.empty_writes = False

    def table(self, name):
        return Query(self)


class Query:
    def __init__(self, db):
        self.db, self.filters, self.action, self.payload = db, [], "read", None

    def select(self, *args, **kwargs):
        return self

    def limit(self, *args):
        return self

    def eq(self, key, value):
        self.filters.append(lambda r: r.get(key) == value)
        return self

    def is_(self, key, value):
        return self.eq(key, None if value == "null" else value)

    def in_(self, key, values):
        self.filters.append(lambda r: r.get(key) in values)
        return self

    def update(self, row):
        self.action, self.payload = "update", row
        return self

    def insert(self, rows):
        self.action, self.payload = "insert", rows if isinstance(rows, list) else [rows]
        return self

    def execute(self):
        db = self.db
        matches = [r for r in db.rows if all(f(r) for f in self.filters)]
        if self.action == "read":
            if db.fail_reads:
                raise RuntimeError("read failed")
            return SimpleNamespace(data=deepcopy(matches))
        if db.fail_writes:
            raise RuntimeError("write failed")
        if db.empty_writes:
            return SimpleNamespace(data=[])
        if self.action == "update":
            for row in matches:
                row.update(self.payload)
            return SimpleNamespace(data=deepcopy(matches))
        if db.race_row is not None:
            db.rows.append(db.race_row)
            db.race_row = None
        seen = deepcopy(db.rows)
        for row in self.payload:
            if any(r["url_key"] == row["url_key"] or r["url"] == row["url"] for r in seen):
                raise RuntimeError("23505 duplicate key")
            seen.append(deepcopy(row))
        db.rows = seen
        return SimpleNamespace(data=deepcopy(self.payload))


def use_database(monkeypatch, rows=()):
    db = FakeDatabase(rows)
    monkeypatch.setattr(database, "supabase", db)
    monkeypatch.setattr(database, "HAS_SEMANTIC_SLUG", True)
    return db


def test_duplicate_source_can_be_saved_with_live_unique_url_constraint(monkeypatch):
    g = grant()
    db = use_database(monkeypatch, [{"url": g["url"], "url_key": g["url_key"], "status": "posted"}])
    database.save_grant(g, status="duplicate", key=g["source_key"])
    assert len(db.rows) == 2
    assert db.rows[1]["url"] == g["source_url"]
    assert db.rows[0]["status"] == "posted"


@pytest.mark.parametrize("status", ["skipped", "duplicate", "posted"])
def test_posted_row_deadline_and_reminder_are_preserved(monkeypatch, status):
    g = grant()
    original = {"url": g["url"], "url_key": g["url_key"], "status": "posted",
                "deadline": "2030-01-01", "reminder_sent": True}
    db = use_database(monkeypatch, [original])
    database.save_grant(g, status=status, key=g["url_key"])
    assert db.rows == [original]


def test_skipped_fingerprint_does_not_hide_grant_from_another_source(monkeypatch):
    g = grant()
    use_database(monkeypatch, [{"url": g["source_url"], "url_key": g["source_key"],
                               "source_key": g["source_key"],
                               "fingerprint": g["fingerprint"], "status": "skipped"}])
    assert database.get_seen_source_keys([g["source_key"]]) == {g["source_key"]}
    assert database.get_seen_fingerprints([g["fingerprint"]]) == set()


@pytest.mark.parametrize("failure", ["fail_reads", "fail_writes", "empty_writes"])
def test_persistence_errors_are_not_hidden(monkeypatch, failure):
    db = use_database(monkeypatch)
    setattr(db, failure, True)
    with pytest.raises(database.DatabaseWriteError):
        database.save_grant(grant())


def test_insert_race_never_downgrades_a_posted_record(monkeypatch):
    g = grant()
    db = use_database(monkeypatch)
    posted = {"url": g["url"], "url_key": g["url_key"], "status": "posted", "reminder_sent": True}
    db.race_row = deepcopy(posted)
    database.save_grant(g, status="skipped", key=g["url_key"])
    assert db.rows == [posted]


def test_duplicate_batch_keys_do_not_break_insertion(monkeypatch):
    db = use_database(monkeypatch)
    database.save_grants_batch([{"grant": grant()}, {"grant": grant()}])
    assert len(db.rows) == 1
