"""Durable, conservative Telegram delivery state in the existing Supabase table.

Namespaced URNs cannot collide with grant URLs. Journal rows are never `posted`
and never enter reminders or grant deduplication. See docs/delivery-journal.md.
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone

import database

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
    result = _client().select("*").eq("url_key", key).limit(1).execute()
    return result.data[0] if result.data else None


def _payload(row):
    payload = json.loads(row["source_url"])
    if payload.get("version") != 1 or not isinstance(payload.get("saves"), list):
        raise RuntimeError("Yuborish jurnali formati yaroqsiz")
    return payload


def _transition(row, before, after):
    result = (_client().update({"status": after}).eq("url_key", row["url_key"])
              .eq("status", before).execute())
    if len(result.data or []) != 1:
        raise database.DatabaseWriteError("Jurnal holati tasdiqlanmadi; yuborish to'xtatildi")
    row["status"] = after


def _finish(row):
    payload = _payload(row)
    # Both operations are idempotent. A crash here only repeats DB writes.
    database.save_grants_batch(payload["saves"])
    for url in payload.get("reminder_urls", []):
        database.mark_reminder_sent(url)
    _transition(row, "delivery_sent", "delivery_done")


def recover(target):
    """Repair acknowledged sends, then stop on any unresolved send for this chat."""
    rows = (_client().select("*")
            .in_("status", ["delivery_sent", "delivery_sending"]).execute()).data or []
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
    if not sender(payload["blocks"], payload["html"]):
        # Only an explicit rejection with ZERO delivered parts can return False.
        _transition(row, "delivery_sending", "delivery_prepared")
        raise RuntimeError("Telegram xabarni rad etdi; keyingi yurishda qayta uriniladi")
    _transition(row, "delivery_sending", "delivery_sent")
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
            result = _client().insert(row).execute()
            if len(result.data or []) != 1:
                raise database.DatabaseWriteError("Jurnal yozuvi tasdiqlanmadi")
        except Exception:
            # Unique-key race OR a committed insert whose response was lost.
            row = _get(key)
            if not row:
                raise
    return _send(row, sender)
