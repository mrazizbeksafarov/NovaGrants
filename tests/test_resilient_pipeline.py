"""Fault injection for service outages, lost acknowledgments and source drift."""

from types import SimpleNamespace

import httpx
import pytest
import requests

import ai_agent
import database
import delivery_journal as journal
import main
import official_evidence
import resilience
import scraper
import telegram_bot
from opportunity_content import opportunity_summary
from test_delivery_journal import deliver
from test_reliability import Query, grant, use_database
from tools import workflow_alert


@pytest.fixture(autouse=True)
def no_delays(monkeypatch):
    monkeypatch.setattr(resilience.time, "sleep", lambda seconds: None)


@pytest.mark.parametrize("stage", ["delivery_sending", "delivery_sent", "delivery_done", "insert"])
def test_committed_journal_write_with_lost_acknowledgment_never_duplicates(monkeypatch, stage):
    db = use_database(monkeypatch)
    execute = Query.execute
    lost, sends = [], []
    def inject(query):
        result = execute(query)
        target = query.action == "insert" if stage == "insert" else (
            query.action == "update" and query.payload.get("status") == stage)
        if target and not lost:
            lost.append(True)
            raise httpx.ReadTimeout("committed but acknowledgment lost")
        return result
    monkeypatch.setattr(Query, "execute", inject)
    assert deliver(lambda *args: sends.append(True) or True) == 1
    assert journal.resume("@Nova_Grants", "digest", lambda *args: sends.append(True) or True) == 0
    assert len(sends) == 1 and lost
    assert sum(r["status"] == "posted" for r in db.rows) == 1


def test_transient_database_read_recovers_before_sending(monkeypatch):
    use_database(monkeypatch)
    execute = Query.execute
    calls = []
    def flaky(query):
        if query.action == "read" and not calls:
            calls.append(True)
            raise httpx.ConnectError("temporary outage")
        return execute(query)
    monkeypatch.setattr(Query, "execute", flaky)
    sends = []
    assert deliver(lambda *args: sends.append(True) or True) == 1
    assert len(sends) == 1


def test_persistent_database_outage_has_bounded_attempts_and_zero_sends(monkeypatch):
    use_database(monkeypatch)
    reads, sends = [], []
    def outage(query):
        reads.append(True)
        raise httpx.ReadTimeout("database unavailable")
    monkeypatch.setattr(Query, "execute", outage)
    with pytest.raises(httpx.ReadTimeout):
        deliver(lambda *args: sends.append(True) or True)
    assert len(reads) == resilience.ATTEMPTS and sends == []


def test_different_process_claim_is_never_mistaken_for_own_lost_ack(monkeypatch):
    db = use_database(monkeypatch)
    with pytest.raises(RuntimeError, match="Telegram"):
        deliver(lambda *args: False)
    row = dict(db.rows[0])
    db.rows[0].update(status="delivery_sending", fingerprint="another-process")
    sends = []
    with pytest.raises(database.DatabaseWriteError):
        journal._send(row, lambda *args: sends.append(True) or True)
    assert sends == []


@pytest.mark.parametrize("code", ["23505", "42501", "42703", "42P01"])
def test_permanent_database_errors_do_not_use_transient_retries(code):
    calls = []
    class Failure(RuntimeError):
        pass
    error = Failure("permanent")
    error.code = code
    def execute():
        calls.append(True)
        raise error
    with pytest.raises(Failure):
        resilience.execute(SimpleNamespace(execute=execute))
    assert len(calls) == 1


def test_supervisor_recovers_known_database_error(monkeypatch):
    calls = []
    def run():
        calls.append(True)
        if len(calls) == 1:
            try:
                raise httpx.ConnectError("offline")
            except httpx.ConnectError as exc:
                raise database.DatabaseWriteError("retryable") from exc
        return "recovered"
    monkeypatch.setattr(main, "run", run)
    assert main.run_with_recovery() == "recovered" and len(calls) == 2


@pytest.mark.parametrize("error", [
    telegram_bot.DeliveryUncertain("unknown Telegram delivery"),
    journal.UncertainDelivery("old send unresolved"),
    ValueError("programming error"),
])
def test_supervisor_does_not_replay_unknown_sends_or_programming_errors(monkeypatch, error):
    calls = []
    error.__cause__ = httpx.ReadTimeout("transport") if not isinstance(error, ValueError) else None
    def run():
        calls.append(True)
        raise error
    monkeypatch.setattr(main, "run", run)
    with pytest.raises(type(error)):
        main.run_with_recovery()
    assert len(calls) == 1


def test_supervisor_cannot_retry_forever(monkeypatch):
    calls = []
    def run():
        calls.append(True)
        raise httpx.ConnectError("offline")
    monkeypatch.setattr(main, "run", run)
    with pytest.raises(httpx.ConnectError):
        main.run_with_recovery()
    assert len(calls) == 3


@pytest.mark.parametrize("body", [{"ok": True}, {"ok": True, "result": None}, {}, {"ok": "true"}])
def test_ambiguous_telegram_success_is_not_accepted_or_replayed(monkeypatch, body):
    monkeypatch.setattr(telegram_bot, "BOT_TOKEN", "test")
    monkeypatch.setattr(telegram_bot.requests, "post", lambda *args, **kwargs: SimpleNamespace(
        status_code=200, json=lambda: body))
    with pytest.raises(telegram_bot.DeliveryUncertain):
        telegram_bot._post({"chat_id": "test", "text": "Test"})


def test_broken_telegram_response_stream_does_not_trigger_a_duplicate(monkeypatch):
    monkeypatch.setattr(telegram_bot, "BOT_TOKEN", "test")
    def truncated(*args, **kwargs):
        raise requests.exceptions.ChunkedEncodingError("response was truncated")
    monkeypatch.setattr(telegram_bot.requests, "post", truncated)
    with pytest.raises(telegram_bot.DeliveryUncertain):
        telegram_bot._post({"chat_id": "test", "text": "Test"})


def test_one_resolver_exception_does_not_discard_healthy_candidates(monkeypatch):
    def resolve(g):
        if g["title"].endswith("1"):
            raise ValueError("bad article")
        return g
    monkeypatch.setattr(main, "resolve_grant", resolve)
    rows = main.resolve_links([grant(1), grant(2)])
    assert [g["title"] for g in rows] == [grant(2)["title"]]
    assert main.RESOLVE_ISSUES == ["ValueError"]


def test_broken_adapter_and_malformed_rows_do_not_kill_healthy_source(monkeypatch):
    sources = [{"id": "bad", "type": "broken"}, {"id": "good", "type": "good"}]
    def broken(src):
        raise ValueError("invalid format")
    monkeypatch.setattr(scraper, "enabled_sources", lambda: sources)
    monkeypatch.setattr(scraper, "_ADAPTERS", {"broken": broken, "good": lambda src: [None, {}, grant()]})
    rows = scraper.fetch_all()
    assert len(rows) == 1 and rows[0]["url"] == grant()["url"]
    assert scraper.SOURCE_ISSUES == ["bad"]


def test_bad_field_types_and_non_web_source_urls_do_not_reach_the_editor(monkeypatch):
    source = {"id": "feed", "type": "rss"}
    monkeypatch.setattr(scraper, "enabled_sources", lambda: [source])
    rows = [{**grant(), "summary": {"bad": "type"}},
            {**grant(2), "url": "file:///etc/passwd"}, {**grant(3), "title": ["bad"]}]
    monkeypatch.setattr(scraper, "_ADAPTERS", {"rss": lambda src: rows})
    result = scraper.fetch_all()
    assert len(result) == 1 and result[0]["summary"] == ""


def test_invalid_resolver_return_value_is_isolated(monkeypatch):
    monkeypatch.setattr(main, "resolve_grant", lambda g: None if g["title"].endswith("1") else g)
    assert len(main.resolve_links([grant(1), grant(2)])) == 1


def page(text, url=None):
    html = "<main>" + text + "</main>"
    return SimpleNamespace(status_code=200, text=html, content=html.encode(), url=url)


def test_official_requirements_override_aggregator_worldwide_claim(monkeypatch):
    g = grant()
    g["summary"] = "Applicants of all nationalities worldwide may apply."
    text = "<h1>Eligibility</h1><p>Applicants must be enrolled in a university located in the United States.</p>" + "<p>Research details.</p>" * 12
    monkeypatch.setattr(official_evidence, "_get", lambda url: page(text, url))
    result = official_evidence.verify_one(g)
    assert result.status == "ineligible" and result.grant is g


@pytest.mark.parametrize("response", [None, SimpleNamespace(status_code=403), page("Enable JavaScript and cookies"), page("<p>Nothing here.</p>")])
def test_unreadable_official_evidence_is_retryable_not_skipped(monkeypatch, response):
    monkeypatch.setattr(official_evidence, "_get", lambda url: response)
    assert official_evidence.verify_one(grant()).status == "retry"


def test_healthy_official_evidence_replaces_aggregator_copy(monkeypatch):
    text = "<h1>Eligibility</h1><p>Applicants of all nationalities may apply.</p><p>" + "Official research programme details. " * 8 + "</p>"
    g = grant()
    g["summary"] = "Aggregator promises everything is free."
    monkeypatch.setattr(official_evidence, "_get", lambda url: page(text, url))
    result = official_evidence.verify_one(g)
    assert result.status == "ready"
    assert "Aggregator promises" not in result.grant["summary"]
    assert "all nationalities" in ai_agent._build_prompt([result.grant])
    assert result.grant["official_evidence_url"] == g["url"]


def test_one_broken_official_page_does_not_lose_healthy_evidence(monkeypatch):
    def get(url):
        if url.endswith("/1"):
            raise ValueError("malformed page")
        return page("<h1>Eligibility</h1>" + "Applicants of all nationalities may apply. " * 8, url)
    monkeypatch.setattr(official_evidence, "_get", get)
    results = official_evidence.verify_all([grant(1), grant(2)])
    assert [r.status for r in results] == ["retry", "ready"]


def test_generic_official_homepage_follows_only_same_organisation_programme_link(monkeypatch):
    g = {**grant(), "url": "https://university.example/", "title": "Global Young Leaders Fellowship 2027"}
    calls = []
    def get(url):
        calls.append(url)
        if len(calls) == 1:
            return page('<a href="/call-2027">Global Young Leaders Fellowship 2027</a>' + "<p>Home page information.</p>" * 8, url)
        return page("<h1>Eligibility</h1>" + "Applicants of all nationalities may apply. " * 8, url)
    monkeypatch.setattr(official_evidence, "_get", get)
    result = official_evidence.verify_one(g)
    assert result.status == "ready"
    assert calls == [g["url"], "https://university.example/call-2027"]
    assert result.grant["url"] == g["url"]


def test_late_restrictions_and_deposit_survive_official_summary_budget():
    raw = "<h1>Program</h1>" + "<p>Promotional introduction.</p>" * 100
    raw += "<h2>Eligibility</h2><p>All nationalities may apply.</p>" + "<p>More programme information.</p>" * 100
    raw += "<p>Students outside the United States are not eligible.</p><p>Application fee $29 is non-refundable.</p><p>Accepted applicants pay a $100 deposit.</p>"
    summary = opportunity_summary(raw, 6000)
    assert "outside the United States are not eligible" in summary
    assert "fee $29 is non-refundable" in summary
    assert "$100 deposit" in summary


def test_cost_heading_keeps_the_following_bullet_values():
    raw = "<p>General information.</p>" * 350
    raw += "<h2>Costs Not Covered</h2><ul><li>Passport Fees</li><li>Visa Fees</li></ul>"
    summary = opportunity_summary(raw, 6000)
    assert "Passport Fees" in summary and "Visa Fees" in summary


def test_large_official_evidence_is_batched_without_truncating_constraints():
    rows = [{**grant(n), "summary": "x" * 5900 + " critical final restriction"} for n in range(8)]
    batches = list(main.editorial_batches(rows))
    assert sum(map(len, batches)) == 8
    assert max(len(b) for b in batches) <= 2
    assert all("critical final restriction" in ai_agent._build_prompt(b) for b in batches)


@pytest.mark.parametrize("error", [httpx.ReadTimeout("deadline"), TimeoutError("deadline")])
def test_model_transport_timeout_opens_circuit_for_the_rest_of_the_run(monkeypatch, error):
    monkeypatch.setattr(ai_agent, "_UNAVAILABLE_MODELS", set())
    assert ai_agent._mark_unavailable("test-model", error)
    assert "test-model" in ai_agent._UNAVAILABLE_MODELS


def test_editorial_request_limit_leaves_unprocessed_grants_retryable(monkeypatch):
    monkeypatch.setattr(main, "DB_READY", False)
    calls, saves, sends = [], [], []
    def select(batch):
        calls.append(batch)
        g = batch[0]
        return {"cards": [{"name": g["title"], "url": g["url"], "_source": g}]}
    monkeypatch.setattr(main, "generate_post_content", select)
    monkeypatch.setattr(main, "save_grants_batch", saves.extend)
    monkeypatch.setattr(main, "publish_post", lambda *args: sends.append(True) or True)
    rows = [{**grant(n), "summary": "x" * 6000} for n in range(32)]
    assert main.publish(rows) == 8
    assert len(calls) == 8 and len(sends) == 1
    assert len(saves) == 8 and all(row["status"] == "posted" for row in saves)


def test_verified_digest_is_not_failed_by_another_unverified_batch(monkeypatch):
    monkeypatch.setattr(main, "DB_READY", False)
    rows = [{**grant(n), "summary": "x" * 6000} for n in range(2)]
    replies = [{"cards": [{"name": rows[0]["title"], "url": rows[0]["url"], "_source": rows[0]}]},
               {"cards": [], "unverified_urls": [rows[1]["url"]]}]
    monkeypatch.setattr(main, "generate_post_content", lambda batch: replies.pop(0))
    sends, saves = [], []
    monkeypatch.setattr(main, "publish_post", lambda *args: sends.append(True) or True)
    monkeypatch.setattr(main, "save_grants_batch", saves.extend)
    assert main.publish(rows) == 1
    assert len(sends) == 1 and len(saves) == 1
    assert saves[0]["grant"]["url"] == rows[0]["url"]
    assert main.PUBLISH_ISSUES


def test_pipeline_keeps_healthy_programme_when_another_official_page_is_down(monkeypatch):
    db = use_database(monkeypatch)
    rows = [grant(1), grant(2)]
    monkeypatch.setattr(main, "DRY_RUN", False)
    monkeypatch.setattr(main, "DB_READY", True)
    monkeypatch.setattr(main, "CHANNEL_ID", "@Nova_Grants")
    monkeypatch.setattr(main, "init_db", lambda **kwargs: True)
    monkeypatch.setattr(main, "send_reminders", lambda: None)
    monkeypatch.setattr(main, "collect_candidates", lambda: rows)
    monkeypatch.setattr(main, "resolve_links", lambda candidates: candidates)
    monkeypatch.setattr(main, "deduplicate", lambda candidates: candidates)
    monkeypatch.setattr(main, "notify_admin", lambda *args: True)
    def get(url):
        if url.endswith("/1"):
            return None
        return page("<h1>Eligibility</h1>" + "Applicants of all nationalities may apply. " * 8, url)
    monkeypatch.setattr(official_evidence, "_get", get)
    def select(batch):
        assert len(batch) == 1 and batch[0]["url"] == rows[1]["url"]
        return {"cards": [{"name": batch[0]["title"], "url": batch[0]["url"], "_source": batch[0]}]}
    monkeypatch.setattr(main, "generate_post_content", select)
    sends = []
    monkeypatch.setattr(main, "publish_post", lambda *args: sends.append(True) or True)
    main.run()
    assert len(sends) == 1
    assert any(r["status"] == "posted" and r["url"] == rows[1]["url"] for r in db.rows)
    assert not any(r["url"] in {rows[0]["url"], rows[0]["source_url"]} for r in db.rows)


def test_full_official_outage_leaves_all_sources_retryable_without_publication(monkeypatch):
    db = use_database(monkeypatch)
    monkeypatch.setattr(main, "DRY_RUN", False)
    monkeypatch.setattr(main, "DB_READY", True)
    monkeypatch.setattr(main, "CHANNEL_ID", "@Nova_Grants")
    monkeypatch.setattr(main, "init_db", lambda **kwargs: True)
    monkeypatch.setattr(main, "send_reminders", lambda: None)
    monkeypatch.setattr(main, "collect_candidates", lambda: [grant()])
    monkeypatch.setattr(main, "resolve_links", lambda candidates: candidates)
    monkeypatch.setattr(main, "deduplicate", lambda candidates: candidates)
    monkeypatch.setattr(official_evidence, "_get", lambda url: None)
    sends = []
    monkeypatch.setattr(main, "publish_post", lambda *args: sends.append(True) or True)
    with pytest.raises(RuntimeError, match="Rasmiy sahifalardan"):
        main.run()
    assert sends == [] and db.rows == []


def test_transient_optional_schema_read_does_not_silently_disable_deduplication(monkeypatch):
    use_database(monkeypatch)
    select, execute = Query.select, Query.execute
    def column(query, field, *args, **kwargs):
        query.column = field
        return select(query, field, *args, **kwargs)
    def outage(query):
        if getattr(query, "column", "") == "semantic_slug":
            raise httpx.ReadTimeout("temporary schema lookup failure")
        return execute(query)
    monkeypatch.setattr(Query, "select", column)
    monkeypatch.setattr(Query, "execute", outage)
    with pytest.raises(RuntimeError, match="vaqtincha"):
        database.init_db()
    assert database.HAS_SEMANTIC_SLUG is True


def test_startup_alert_requires_no_third_party_dependencies_and_hides_token(monkeypatch, capsys):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-test-token")
    monkeypatch.setenv("ADMIN_ID", "123")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_RUN_ID", "456")
    calls = []
    def send(method, path, **kwargs):
        calls.append(kwargs["body"])
    connection = SimpleNamespace(request=send, close=lambda: None,
        getresponse=lambda: SimpleNamespace(status=200, read=lambda: b'{"ok":true}'))
    monkeypatch.setattr(workflow_alert.http.client, "HTTPSConnection", lambda *args, **kwargs: connection)
    assert workflow_alert.send_startup_alert()
    assert b"actions/runs/456" in calls[0]
    assert "secret-test-token" not in capsys.readouterr().out


def test_startup_alert_failure_does_not_expose_secret_in_exception(monkeypatch, capsys):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-test-token")
    monkeypatch.setenv("ADMIN_ID", "123")
    def fail(*args, **kwargs):
        raise ValueError("https://api.telegram.org/botsecret-test-token/sendMessage")
    connection = SimpleNamespace(request=fail, close=lambda: None)
    monkeypatch.setattr(workflow_alert.http.client, "HTTPSConnection", lambda *args, **kwargs: connection)
    assert not workflow_alert.send_startup_alert()
    assert "secret-test-token" not in capsys.readouterr().out
