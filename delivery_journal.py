"""Durable, conservative Telegram delivery state in the existing Supabase table.

Namespaced URNs cannot collide with grant URLs. Journal rows are never `posted`
and never enter reminders or grant deduplication. See docs/delivery-journal.md.
"""

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone

import database
from resilience import execute as execute_query

PREFIX = "urn:novagrants:delivery:"
TZ = timezone(timedelta(hours=5))


class UncertainDelivery(RuntimeError):
    """An earlier send may have arrived; an operator must reconcile it."""


def _scope(target):
    return hashlib.sha256(str(target).strip().lower().encode()).hexdigest()[:20]


def _key(target, kind):
    day = datetime.now(TZ).date().isoformat()
    return f"{PREFIX}{_scope(target)}:{kind}:{day}"


def _client():
    if database.supabase is None:
        raise database.DatabaseWriteError("Yuborish jurnali uchun baza sozlanmagan")
    return database.supabase.table(database.TABLE)


def _get(key):
    result = execute_query(_client().select("*").eq("url_key", key).limit(1))
    return result.data[0] if result.data else None


def _payload(row):
    payload = json.loads(row["source_url"])
    if payload.get("version") != 1 or not isinstance(payload.get("saves"), list):
        raise RuntimeError("Yuborish jurnali formati yaroqsiz")
    return payload


def _transition(row, before, after, extra=None):
    token = uuid.uuid4().hex if before == "delivery_prepared" else row.get("fingerprint")
    changes = {"status": after}
    changes.update(extra or {})
    if token:
        changes["fingerprint"] = token
    query = _client().update(changes).eq("url_key", row["url_key"]).eq("status", before)
    if before != "delivery_prepared" and token:
        query = query.eq("fingerprint", token)
    error = None
    try:
        result = execute_query(query)
        if len(result.data or []) == 1:
            row.update(changes)
            return
    except Exception as exc:
        error = exc
    # Confirm a lost acknowledgment using this process's claim token only.
    current = _get(row["url_key"])
    if current and current["status"] == after and current.get("fingerprint") == token:
        row.update(changes)
        return
    if error:
        raise error
    raise database.DatabaseWriteError("Jurnal holati tasdiqlanmadi; yuborish to'xtatildi")


def _finish(row):
    payload = _payload(row)
    # Both operations are idempotent. A crash here only repeats DB writes.
    database.save_grants_batch(payload["saves"])
    for url in payload.get("reminder_urls", []):
        database.mark_reminder_sent(url)
    _transition(row, "delivery_sent", "delivery_done")


def recover(target):
    """Repair acknowledged sends, then stop on any unresolved send for this chat."""
    rows = (execute_query(_client().select("*")
            .in_("status", ["delivery_sent", "delivery_sending"]))).data or []
    scoped = [r for r in rows if r.get("url_key", "").startswith(f"{PREFIX}{_scope(target)}:")]
    for row in scoped:
        if row["status"] == "delivery_sent":
            _finish(row)
    if any(r["status"] == "delivery_sending" for r in scoped):
        raise UncertainDelivery(
            "Oldingi Telegram yuborilishi noma'lum. Kanal va delivery_sending jurnalini "
            "solishtiring; avtomatik qayta yuborish bloklandi.")


def _send(row, sender):
    if row["status"] == "delivery_done":
        return 0
    if row["status"] != "delivery_prepared":
        raise UncertainDelivery("Yuborish jurnali tekshirilishi kerak; qayta yuborilmadi")
    payload = _payload(row)
    # Compare-and-set grants exactly one process permission to send.
    _transition(row, "delivery_prepared", "delivery_sending")
    # Exceptions deliberately leave `sending`: the server may have accepted it.
    delivery = sender(payload["blocks"], payload["html"])
    if not delivery:
        # Only an explicit rejection with ZERO delivered parts can return False.
        _transition(row, "delivery_sending", "delivery_prepared")
        raise RuntimeError("Telegram xabarni rad etdi; keyingi yurishda qayta uriniladi")
    extra = None
    if isinstance(delivery, dict):
        if delivery.get("delivered") is not True:
            raise UncertainDelivery("Publisher natijasi tasdiqlanmadi; qayta yuborilmadi")
        payload["messages"] = delivery.get("messages", [])
        extra = {"source_url": json.dumps(payload, ensure_ascii=False)}
    _transition(row, "delivery_sending", "delivery_sent", extra)
    _finish(row)
    return payload["count"]


def resume(target, kind, sender):
    """None = no daily reservation; 0 = already sent; positive = resumed send."""
    recover(target)
    row = _get(_key(target, kind))
    return _send(row, sender) if row else None


def deliver(target, kind, blocks, html, saves, sender, count, reminder_urls=()):
    """Persist the complete intent BEFORE making any Telegram write."""
    recover(target)
    key = _key(target, kind)
    row = _get(key)
    if not row:
        fields = ("title", "url", "url_key", "source_url", "source_key", "fingerprint",
                  "semantic_slug", "deadline_iso")
        compact = [{**{k: v for k, v in entry.items() if k != "grant"},
                    "grant": {k: entry["grant"][k] for k in fields if k in entry["grant"]}}
                   for entry in saves]
        payload = {"version": 1, "blocks": blocks, "html": html, "saves": compact,
                   "count": count, "reminder_urls": list(reminder_urls)}
        row = {"url": key, "url_key": key, "source_key": key,
               "title": f"Nova Grants {kind} delivery", "status": "delivery_prepared",
               "source_url": json.dumps(payload, ensure_ascii=False), "reminder_sent": True}
        try:
            result = execute_query(_client().insert(row))
            if len(result.data or []) != 1:
                raise database.DatabaseWriteError("Jurnal yozuvi tasdiqlanmadi")
        except Exception:
            # Unique-key race OR a committed insert whose response was lost.
            row = _get(key)
            if not row:
                raise
    return _send(row, sender)


def release_confirmed_deleted_digest(target, message_id):
    """Operator-only: release a completed day after the user confirms deletion.

    Never called by retries. The complete old intent is archived, not erased.
    The daily reservation remains closed until every affected row is reconciled.
    """
    key = _key(target, "digest")
    row = _get(key)
    if not row or row["status"] != "delivery_done":
        raise UncertainDelivery("Faqat to'liq yakunlangan digestning tasdiqlangan o'chirilishini tiklash mumkin")
    payload = _payload(row)
    known_ids = {r.get("message_id") for r in payload.get("messages", [])}
    known_ids.update(r.get("message_id") for r in payload.get("corrections", []))
    known_ids.discard(None)
    if known_ids != {message_id}:
        raise ValueError("O'chirilgan xabar identifikatori jurnalga aynan mos emas")
    owners = {}
    for entry in payload["saves"]:
        expected = database._grant_row(entry)
        response = execute_query(_client().select("*").eq("url", expected["url"]).limit(1))
        owner = response.data[0] if response.data else None
        if not owner or owner.get("status") == "removed":
            continue
        if entry.get("status", "posted") == "duplicate" and owner.get("status") == "posted":
            continue  # an alias must not demote a different existing public post
        if owner.get("status") != entry.get("status", "posted"):
            raise database.DatabaseWriteError("Grant holati jurnalga mos emas; kunlik cheklov ochilmadi")
        if (owner.get("fingerprint") and expected.get("fingerprint")
                and owner["fingerprint"] != expected["fingerprint"]):
            raise database.DatabaseWriteError("Grant boshqa versiyaga o'zgargan; kunlik cheklov ochilmadi")
        owners[owner["url_key"]] = owner
    for owner in owners.values():
        result = execute_query(_client().update({"status": "removed"})
            .eq("url_key", owner["url_key"]).eq("status", owner["status"]))
        if not result.data:
            latest = execute_query(_client().select("status").eq("url_key", owner["url_key"]))
            if not latest.data or latest.data[0]["status"] != "removed":
                raise database.DatabaseWriteError("O'chirilgan post yozuvlari tasdiqlanmadi")
    archive_key = key + ":deleted:" + uuid.uuid4().hex
    payload["deletion"] = {"message_id": message_id, "confirmed_by": "explicit_user_instruction",
                           "at": datetime.now(timezone.utc).isoformat(), "previous_rows": list(owners.values())}
    result = execute_query(_client().update({"url": archive_key, "url_key": archive_key,
        "source_key": archive_key, "status": "delivery_deleted",
        "source_url": json.dumps(payload, ensure_ascii=False)}).eq("url_key", key).eq("status", "delivery_done"))
    if not result.data and (_get(key) or not _get(archive_key)):
        raise database.DatabaseWriteError("Eski yuborish jurnali arxivlangani tasdiqlanmadi")
    return archive_key
