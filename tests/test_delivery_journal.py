"""Crash windows, daily limits and fallback behavior without real API writes."""

import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

import ai_agent
import database
import delivery_journal as journal
import main
import telegram_bot
from post_builder import build_post
from test_reliability import grant, use_database


def deliver(sender, target="@Nova_Grants"):
    g = grant()
    return journal.deliver(target, "digest", [{"type": "paragraph", "text": "Test"}],
                           "Test", [{"grant": g, "status": "posted"}], sender, 1)


def test_database_failure_after_telegram_is_repaired_without_resending(monkeypatch):
    db = use_database(monkeypatch)
    real_save = database.save_grants_batch
    sends = []
    monkeypatch.setattr(database, "save_grants_batch", lambda rows: (_ for _ in ()).throw(RuntimeError("DB down")))
    with pytest.raises(RuntimeError, match="DB down"):
        deliver(lambda *args: sends.append(args) or True)
    assert db.rows[0]["status"] == "delivery_sent"
    monkeypatch.setattr(database, "save_grants_batch", real_save)
    assert journal.resume("@Nova_Grants", "digest", lambda *args: sends.append(args) or True) == 0
    assert len(sends) == 1
    assert [r["status"] for r in db.rows] == ["delivery_done", "posted"]


@pytest.mark.parametrize("old_status", ["duplicate", "skipped", "posted"])
def test_legacy_official_url_under_source_key_does_not_break_delivery(monkeypatch, old_status):
    g = grant()
    original = {"url": g["url"], "url_key": g["source_key"], "status": old_status,
                "deadline": "2030-01-01", "reminder_sent": True}
    db = use_database(monkeypatch, [original])
    sends = []
    assert deliver(lambda *args: sends.append(args) or True) == 1
    assert journal.resume("@Nova_Grants", "digest", lambda *args: sends.append(args) or True) == 0
    assert len(sends) == 1
    url_owner = next(r for r in db.rows if r["url"] == g["url"])
    assert url_owner["status"] == "posted"
    if old_status == "posted":
        assert url_owner == original


def test_two_legacy_rows_owning_url_and_key_preserve_both_without_conflict(monkeypatch):
    g = grant()
    db = use_database(monkeypatch, [
        {"url": g["url"], "url_key": "legacy-source-key", "status": "duplicate"},
        {"url": g["source_url"], "url_key": g["url_key"], "status": "skipped"}])
    database.save_grant(g)
    assert len(db.rows) == 2
    assert db.rows[0]["status"] == "posted" and db.rows[0]["url_key"] == "legacy-source-key"
    assert db.rows[1]["status"] == "skipped"


def test_insert_race_on_url_with_a_different_key_is_reconciled(monkeypatch):
    g = grant()
    db = use_database(monkeypatch)
    db.race_row = {"url": g["url"], "url_key": "legacy-source-key", "status": "duplicate"}
    database.save_grant(g)
    assert len(db.rows) == 1 and db.rows[0]["status"] == "posted"


def test_legacy_posted_url_is_deduplicated_even_when_every_derived_key_changed(monkeypatch):
    g = grant()
    use_database(monkeypatch, [{"url": g["url"], "url_key": "legacy-key", "status": "posted"}])
    monkeypatch.setattr(main, "DB_READY", True)
    monkeypatch.setattr(main, "save_grants_batch", lambda rows: None)
    assert main.deduplicate([g]) == []


def test_key_claimed_during_legacy_url_promotion_is_reconciled(monkeypatch):
    g = grant()
    db = use_database(monkeypatch, [{"url": g["url"], "url_key": "legacy-key", "status": "duplicate"}])
    db.race_row = {"url": g["source_url"], "url_key": g["url_key"], "status": "skipped"}
    database.save_grant(g)
    assert len(db.rows) == 2 and db.rows[0]["status"] == "posted"
    assert db.rows[0]["url_key"] == "legacy-key"


def test_timeout_blocks_another_send_even_on_the_next_day(monkeypatch):
    db = use_database(monkeypatch)
    def timeout(*args):
        raise telegram_bot.DeliveryUncertain("timeout")
    with pytest.raises(telegram_bot.DeliveryUncertain):
        deliver(timeout)
    old_key = db.rows[0]["url_key"]
    db.rows[0]["url_key"] = old_key[:-10] + "2020-01-01"
    sends = []
    with pytest.raises(journal.UncertainDelivery):
        deliver(lambda *args: sends.append(args) or True)
    assert sends == []


def test_ack_write_failure_keeps_unknown_state_and_never_resends(monkeypatch):
    db = use_database(monkeypatch)
    sends = []
    def sent(*args):
        sends.append(args)
        db.fail_writes = True
        return True
    with pytest.raises(RuntimeError, match="write failed"):
        deliver(sent)
    db.fail_writes = False
    assert db.rows[0]["status"] == "delivery_sending"
    with pytest.raises(journal.UncertainDelivery):
        deliver(lambda *args: sends.append(args) or True)
    assert len(sends) == 1


def test_explicit_rejection_retries_the_original_saved_payload(monkeypatch):
    db = use_database(monkeypatch)
    with pytest.raises(RuntimeError, match="Telegram"):
        deliver(lambda *args: False)
    assert db.rows[0]["status"] == "delivery_prepared"
    original = json.loads(db.rows[0]["source_url"])
    sends = []
    assert journal.resume("@Nova_Grants", "digest", lambda *args: sends.append(args) or True) == 1
    assert sends == [(original["blocks"], original["html"])]


def test_done_daily_digest_blocks_different_content_and_case_of_handle(monkeypatch):
    use_database(monkeypatch)
    sends = []
    assert deliver(lambda *args: sends.append(args) or True) == 1
    assert deliver(lambda *args: sends.append(args) or True, "@nova_grants") == 0
    assert len(sends) == 1


def test_journal_failure_prevents_every_telegram_write(monkeypatch):
    db = use_database(monkeypatch)
    db.fail_writes = True
    sends = []
    with pytest.raises(RuntimeError):
        deliver(lambda *args: sends.append(args) or True)
    assert sends == []


def test_unreadable_journal_prevents_every_telegram_write(monkeypatch):
    db = use_database(monkeypatch)
    db.fail_reads = True
    sends = []
    with pytest.raises(RuntimeError, match="read failed"):
        deliver(lambda *args: sends.append(args) or True)
    assert sends == []


def test_lost_claim_race_never_sends(monkeypatch):
    db = use_database(monkeypatch)
    with pytest.raises(RuntimeError, match="Telegram"):
        deliver(lambda *args: False)
    row = deepcopy(db.rows[0])
    db.rows[0]["status"] = "delivery_sending"
    sends = []
    with pytest.raises(database.DatabaseWriteError):
        journal._send(row, lambda *args: sends.append(args) or True)
    assert sends == []


def test_reminder_flags_are_recovered_without_another_message(monkeypatch):
    g = grant()
    db = use_database(monkeypatch, [{"url": g["url"], "url_key": g["url_key"],
                                    "status": "posted", "reminder_sent": False}])
    real_mark = database.mark_reminder_sent
    monkeypatch.setattr(database, "mark_reminder_sent", lambda url: (_ for _ in ()).throw(RuntimeError("DB down")))
    sends = []
    with pytest.raises(RuntimeError):
        journal.deliver("@Nova_Grants", "reminder", [], "Test", [],
                        lambda *args: sends.append(args) or True, 1, [g["url"]])
    monkeypatch.setattr(database, "mark_reminder_sent", real_mark)
    journal.recover("@Nova_Grants")
    assert len(sends) == 1 and db.rows[0]["reminder_sent"] is True


def test_day_boundary_is_tashkent_midnight(monkeypatch):
    class Clock:
        @staticmethod
        def now(tz):
            return datetime(2026, 11, 12, 19, 1, tzinfo=timezone.utc).astimezone(tz)
    monkeypatch.setattr(journal, "datetime", Clock)
    assert journal._key("@Nova_Grants", "digest").endswith(":2026-11-13")


def test_groq_only_official_link_selection(monkeypatch):
    url = grant()["url"]
    monkeypatch.setattr(ai_agent, "API_KEYS", [])
    monkeypatch.setattr(ai_agent.groq_fallback, "configured", lambda: True)
    calls = []
    monkeypatch.setattr(ai_agent.groq_fallback, "request_text", lambda prompt: calls.append(prompt) or url)
    assert ai_agent.resolve_official_url_with_ai("Research", "", [url]) == url
    assert len(calls) == 1
    assert ai_agent.resolve_official_url_with_ai("Research", "", []) is None
    assert len(calls) == 1


def test_nine_selected_grants_make_one_message_and_overflow_is_retryable(monkeypatch):
    grants = [grant(i) for i in range(9)]
    monkeypatch.setattr(main, "DB_READY", False)
    monkeypatch.setattr(main, "generate_post_content", lambda batch: {"cards": [
        {"name": g["title"], "url": g["url"], "_source": g} for g in batch]})
    posts, saves = [], []
    monkeypatch.setattr(main, "publish_post", lambda blocks, html: posts.append((blocks, html)) or True)
    monkeypatch.setattr(main, "save_grants_batch", saves.extend)
    count = main.publish(grants)
    assert len(posts) == 1 and 0 < count <= 8
    assert telegram_bot.fits_single_message(*posts[0])
    assert len(saves) == count and all(e["status"] == "posted" for e in saves)
    assert len({e["grant"]["url"] for e in saves}) < len(grants)


def test_oversized_fallback_is_rejected_before_network(monkeypatch):
    calls = []
    monkeypatch.setattr(telegram_bot, "_post", lambda *args, **kwargs: calls.append(args) or (True, ""))
    blocks, _ = build_post("Test", [{"name": "Test", "url": grant()["url"]}])
    with pytest.raises(ValueError, match="bitta"):
        telegram_bot.publish_single(blocks, "x" * 10000)
    assert calls == []


def test_all_unverified_cards_fail_without_recording_rejection(monkeypatch):
    g = grant()
    monkeypatch.setattr(main, "DB_READY", False)
    monkeypatch.setattr(main, "generate_post_content", lambda batch: {"cards": [], "unverified_urls": [g["url"]]})
    saves = []
    monkeypatch.setattr(main, "save_grants_batch", saves.extend)
    with pytest.raises(RuntimeError, match="dalillari"):
        main.publish([g])
    assert saves == []


def test_partial_rich_delivery_is_uncertain_without_html_fallback(monkeypatch):
    monkeypatch.setattr(telegram_bot, "send_rich_message", lambda *args: (False, 1))
    sends = []
    monkeypatch.setattr(telegram_bot, "send_telegram_message", lambda *args: sends.append(args))
    with pytest.raises(telegram_bot.DeliveryUncertain):
        telegram_bot.publish([{"type": "paragraph", "text": "Test"}], "Test")
    assert sends == []


def test_partial_html_delivery_never_releases_the_claim(monkeypatch):
    monkeypatch.setattr(telegram_bot, "BOT_TOKEN", "test")
    monkeypatch.setattr(telegram_bot, "CHANNEL_ID", "test")
    monkeypatch.setattr(telegram_bot.time, "sleep", lambda *args: None)
    replies = iter([(True, ""), *[(False, "Bad Request")] * telegram_bot.MAX_SEND_RETRY])
    monkeypatch.setattr(telegram_bot, "_post", lambda *args, **kwargs: next(replies))
    with pytest.raises(telegram_bot.DeliveryUncertain):
        telegram_bot.send_telegram_message("x" * 6000)


def test_pipeline_second_daily_run_does_not_call_ai_or_telegram(monkeypatch):
    db = use_database(monkeypatch)
    monkeypatch.setattr(main, "DB_READY", True)
    monkeypatch.setattr(main, "DRY_RUN", False)
    monkeypatch.setattr(main, "CHANNEL_ID", "@Nova_Grants")
    g = grant()
    ai_calls, posts = [], []
    def content(batch):
        ai_calls.append(batch)
        return {"cards": [{"name": g["title"], "url": g["url"], "_source": g}]}
    monkeypatch.setattr(main, "generate_post_content", content)
    monkeypatch.setattr(main, "publish_post", lambda *args: posts.append(args) or True)
    assert main.publish([g]) == 1
    assert main.publish([grant(2)]) == 0
    assert len(ai_calls) == len(posts) == 1
    assert [r["status"] for r in db.rows] == ["delivery_done", "posted"]


def test_completed_day_exits_before_source_fetch_and_link_resolution(monkeypatch):
    use_database(monkeypatch)
    deliver(lambda *args: True)
    monkeypatch.setattr(main, "DB_READY", True)
    monkeypatch.setattr(main, "DRY_RUN", False)
    monkeypatch.setattr(main, "CHANNEL_ID", "@Nova_Grants")
    monkeypatch.setattr(main, "init_db", lambda **kwargs: True)
    monkeypatch.setattr(main, "send_reminders", lambda: None)
    calls = []
    monkeypatch.setattr(main, "collect_candidates", lambda: calls.append("fetch") or [])
    monkeypatch.setattr(main, "resolve_links", lambda items: calls.append("resolve") or [])
    main.run()
    assert calls == []


def test_new_day_allows_a_new_digest(monkeypatch):
    use_database(monkeypatch)
    sends = []
    assert deliver(lambda *args: sends.append(args) or True) == 1
    class Tomorrow:
        @staticmethod
        def now(tz):
            return datetime.now(tz) + timedelta(days=1)
    monkeypatch.setattr(journal, "datetime", Tomorrow)
    assert deliver(lambda *args: sends.append(args) or True) == 1
    assert len(sends) == 2
