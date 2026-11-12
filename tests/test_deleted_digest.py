import json

import pytest

import database
import delivery_journal as journal
from test_reliability import grant, use_database


def saved_digest(monkeypatch):
    db = use_database(monkeypatch)
    g = grant()
    journal.deliver("@Nova_Grants", "digest", [], "Test", [{"grant": g, "status": "posted"}],
        lambda *args: {"delivered": True, "messages": [{"message_id": 587, "chat_id": -100}]}, 1)
    return db, g


def test_confirmed_deleted_post_is_archived_and_only_its_grants_requeued(monkeypatch):
    db, g = saved_digest(monkeypatch)
    other = grant(2)
    database.save_grant(other)
    archive = journal.release_confirmed_deleted_digest("@Nova_Grants", 587)
    assert journal._get(journal._key("@Nova_Grants", "digest")) is None
    archived = journal._get(archive)
    assert archived["status"] == "delivery_deleted"
    assert json.loads(archived["source_url"])["deletion"]["message_id"] == 587
    assert next(r for r in db.rows if r["url"] == g["url"])["status"] == "removed"
    assert next(r for r in db.rows if r["url"] == other["url"])["status"] == "posted"
    assert database.get_seen_source_keys([g["source_key"]]) == set()
    assert journal.deliver("@Nova_Grants", "digest", [], "New", [{"grant": g}], lambda *args: True, 1) == 1


def test_wrong_message_identifier_cannot_reopen_a_completed_day(monkeypatch):
    db, _ = saved_digest(monkeypatch)
    before = json.dumps(db.rows, sort_keys=True)
    with pytest.raises(ValueError, match="identifikatori"):
        journal.release_confirmed_deleted_digest("@Nova_Grants", 999)
    assert json.dumps(db.rows, sort_keys=True) == before


def test_unresolved_send_cannot_be_released_as_deleted(monkeypatch):
    db, _ = saved_digest(monkeypatch)
    db.rows[0]["status"] = "delivery_sending"
    with pytest.raises(journal.UncertainDelivery):
        journal.release_confirmed_deleted_digest("@Nova_Grants", 587)
    assert db.rows[1]["status"] == "posted"
