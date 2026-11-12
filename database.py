"""Supabase bazasi — takror postni to'xtatish va deadline eslatmalari.

TAKRORGA QARSHI UCH QATLAM:
  1. source_key  — aggregator maqolasining kaliti. Bir marta ko'rilgan maqola
                   qayta OCHILMAYDI ham (tarmoq so'rovi tejaladi).
  2. url_key     — grantning ASL havolasi kaliti. 8 ta aggregator bitta rasmiy
                   saytga olib borsa, faqat bittasi o'tadi.
  3. fingerprint — sarlavha barmoq izi. Rasmiy havolalar biroz farq qilsa ham
                   ("/apply" va "/apply/en") takrorni ushlaydi.

Yozuv holati (status):
  "posted"    — kanalga chiqdi
  "skipped"   — AI muvaffaqiyatli tekshirgan, ammo mos emas deb topgan maqola.
                Havola/AI vaqtinchalik xatosi bu holatda saqlanmaydi.
  "duplicate" — boshqa aggregatorda chiqqan, bazada allaqachon bor grant.
                Bu yozuv MANBA MAQOLASI kaliti bilan saqlanadi, grantning o'zi emas.

MUHIM QOIDA — "posted" YOZUV HECH QACHON PASAYTIRILMAYDI.
Ilgari `deduplicate()` takror topilgan grantni `status="skipped"` bilan qayta
yozardi va upsert mavjud qatorni ustidan bosardi. Natijada:
  • post qilingan grant `skipped` ga tushardi,
  • `deadline` NULL ga aylanardi,
  • `reminder_sent` False ga qaytardi,
  • `source_key` boshqa aggregatorniki bilan almashardi.
Ya'ni 2+ manbada chiqqan har qanday grant eslatma ololmay qolardi. Endi
`save_grant()` avval qatorni o'qiydi va posted qatorni o'zgartirmaydi.

Yangi ustunlar kerak — migration.sql ni Supabase SQL Editor da bir marta ishlating.
"""

import os
import sys
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
from supabase import create_client, Client
from resilience import execute as execute_query, transient_error

load_dotenv()

TABLE = "posted_grants"
CHUNK = 100                  # bitta so'rovda nechta kalit tekshiriladi
HAS_SEMANTIC_SLUG = False

_url = str(os.getenv("SUPABASE_URL", "")).strip()
_key = str(os.getenv("SUPABASE_KEY", "")).strip()

supabase: Client = None
if _url and _key and "your_supabase" not in _url:
    try:
        supabase = create_client(_url, _key)
    except Exception as e:
        print(f"Supabase ulanishida xatolik: {e}")
else:
    print("DIQQAT: SUPABASE_URL yoki SUPABASE_KEY topilmadi!")


def init_db(strict: bool = True) -> bool:
    """Ulanishni va kerakli ustunlar borligini tekshiradi.

    strict=True  — kamchilik bo'lsa dastur to'xtaydi (haqiqiy yurish uchun;
                   baza ishlamasa kanalga takror post yog'ilishi mumkin).
    strict=False — ogohlantiradi va False qaytaradi (quruq sinov uchun).
    """
    global HAS_SEMANTIC_SLUG
    if not supabase:
        print("Baza sozlanmagan.")
        if strict:
            raise RuntimeError("Baza sozlanmagan")
        return False

    try:
        execute_query(supabase.table(TABLE).select("id").limit(1))
    except Exception as e:
        print(f"Bazaga ulanib bo'lmadi: {e}")
        if strict:
            raise RuntimeError("Bazaga ulanib bo'lmadi") from e
        return False

    required = ("url", "source_url", "url_key", "source_key", "fingerprint", "status", "deadline", "reminder_sent")
    missing = False
    try:
        execute_query(supabase.table(TABLE).select(",".join(required)).limit(1))
    except Exception as exc:
        if transient_error(exc):
            raise RuntimeError("Baza sxemasini vaqtincha tekshirib bo'lmadi") from exc
        missing = True

    if missing:
        print("=" * 66)
        print(f"BAZA SXEMASI YOKI O'QISH HUQUQI TEKSHIRILMADI: {', '.join(required)}")
        print("migration.sql faylini Supabase SQL Editor da ishga tushiring.")
        print("=" * 66)
        if strict:
            raise RuntimeError("Baza sxemasi tayyor emas")
        return False

    try:
        execute_query(supabase.table(TABLE).select("semantic_slug").limit(1))
        HAS_SEMANTIC_SLUG = True
    except Exception as exc:
        if transient_error(exc):
            raise RuntimeError("Baza ustunini vaqtincha tekshirib bo'lmadi") from exc
        HAS_SEMANTIC_SLUG = False
        print("Eslatma: 'semantic_slug' ustuni bazada mavjud emas (migration.sql orqali qo'shish tavsiya etiladi).")

    print("Baza tayyor.")
    return True


def _collect(column: str, values: list, posted_only: bool = False) -> set:
    """Berilgan ustun bo'yicha bazada allaqachon bor qiymatlarni qaytaradi."""
    global HAS_SEMANTIC_SLUG
    found = set()
    values = [v for v in values if v]
    if not supabase or not values:
        return found
    if column == "semantic_slug" and not HAS_SEMANTIC_SLUG:
        return found

    uniq = list(dict.fromkeys(values))
    for i in range(0, len(uniq), CHUNK):
        batch = uniq[i:i + CHUNK]
        try:
            query = supabase.table(TABLE).select(column).in_(column, batch)
            if posted_only:
                query = query.eq("status", "posted")
            resp = execute_query(query)
            for row in resp.data or []:
                if row.get(column):
                    found.add(row[column])
        except Exception as e:
            err_msg = str(e).lower()
            if column == "semantic_slug" and ("does not exist" in err_msg or "42703" in err_msg):
                HAS_SEMANTIC_SLUG = False
                return found
            # Bazani o'qib bo'lmasa — to'xtaymiz. Aks holda hamma narsa
            # "yangi" ko'rinib, kanalga takror post yog'iladi.
            print(f"Bazani o'qishda xatolik ({column}): {e}")
            raise RuntimeError(f"Dedup bazasi o'qilmadi: {column}") from e
    return found


def get_seen_source_keys(source_keys: list) -> set:
    """Allaqachon ko'rib chiqilgan aggregator maqolalari."""
    return _collect("source_key", source_keys)


def get_seen_url_keys(url_keys: list) -> set:
    """Allaqachon post qilingan asl havolalar."""
    return _collect("url_key", url_keys, posted_only=True)


def get_seen_urls(urls: list) -> set:
    """Exact official URLs also identify legacy rows with source-based keys."""
    return _collect("url", urls, posted_only=True)


def get_seen_fingerprints(fingerprints: list) -> set:
    """Allaqachon post qilingan sarlavha barmoq izlari."""
    return _collect("fingerprint", fingerprints, posted_only=True)


def get_seen_fingerprint_scopes(fingerprints: list) -> set:
    """A generic title at two unrelated institutions is not one opportunity."""
    from link_resolver import root_domain, host_of
    values = list(dict.fromkeys(v for v in fingerprints if v))
    if not supabase or not values:
        return set()
    found = set()
    try:
        for start in range(0, len(values), CHUNK):
            response = (execute_query(supabase.table(TABLE).select("fingerprint,url")
                        .in_("fingerprint", values[start:start + CHUNK]).eq("status", "posted")))
            found.update((r["fingerprint"], root_domain(host_of(r.get("url", ""))))
                         for r in response.data or [] if r.get("fingerprint"))
    except Exception as exc:
        raise RuntimeError("Sarlavha va tashkilot bo'yicha dedup o'qilmadi") from exc
    return found


def make_semantic_slug(title: str, host: str, deadline: str = None, url: str = "") -> str:
    """Yagona semantik slug/kalit yaratadi.

    Tashkilot va dastur kodi mavjud bo'lsa (masalan kaust:mewc, daad:epos, turkiyeburslari)
    -> 'kaust.edu.sa:kaust:mewc' kabi invariant kalit qaytaradi.
    Aks holda sarlavha va domen asosida slug yaratadi.
    """
    import re
    from link_resolver import program_fingerprint, root_domain
    prog = program_fingerprint(title, url or host)
    r_dom = root_domain(host) or host
    if prog:
        return f"{r_dom}:{prog}".lower()

    clean_t = re.sub(r"[^a-z0-9]+", "-", (title or "").lower()).strip("-")
    clean_h = re.sub(r"[^a-z0-9]+", "-", (r_dom or host or "").lower()).strip("-")
    year = ""
    if deadline:
        m = re.search(r"202[5-9]", str(deadline))
        if m:
            year = m.group(0)
    else:
        m = re.search(r"202[5-9]", clean_t)
        if m:
            year = m.group(0)
    parts = [clean_t[:45], year, clean_h]
    return "-".join(p for p in parts if p).strip("-")


def get_seen_semantic_slugs(slugs: list) -> set:
    """Allaqachon post qilingan semantik sluglar."""
    return _collect("semantic_slug", slugs, posted_only=True)


class DatabaseWriteError(RuntimeError):
    """Persistence failed: stop publishing instead of silently forgetting posts."""


def _grant_row(entry: dict) -> dict:
    from link_resolver import is_aggregator, host_of

    g = entry.get("grant", {})
    status = entry.get("status", "posted")
    posted = status == "posted"
    target_url = g.get("url") or g.get("source_url", "")
    if posted and is_aggregator(target_url):
        raise DatabaseWriteError("Aggregator havolasi posted sifatida saqlanmaydi")

    # The live schema has UNIQUE(url) as well as UNIQUE(url_key).
    # Rejected/duplicate articles own their SOURCE identity, never the posted URL.
    if not posted:
        target_url = g.get("source_url") or target_url
    key = entry.get("key") or (g.get("url_key") if posted else g.get("source_key"))
    key = key or g.get("source_key") or g.get("url_key")
    if not key or not target_url:
        raise DatabaseWriteError("Grant uchun URL yoki dedup kaliti yo'q")

    row = {
        "title": (g.get("title") or "")[:255], "url": target_url,
        "url_key": key, "source_url": g.get("source_url", ""),
        "source_key": g.get("source_key", ""),
        "fingerprint": g.get("fingerprint", ""), "status": status,
    }
    deadline = entry.get("deadline_iso") or g.get("deadline_iso")
    if deadline and deadline != "null" and len(str(deadline)) >= 10:
        row["deadline"] = deadline
    slug = g.get("semantic_slug") or make_semantic_slug(
        g.get("title", ""), host_of(g.get("url") or target_url), deadline, g.get("url") or target_url)
    if HAS_SEMANTIC_SLUG and slug:
        row["semantic_slug"] = slug
    return row


def _save_row(row: dict, existing: dict = None, attempt: int = 0):
    """Persist one row, protecting posted records even after an insert race."""
    if existing is None:
        response = (execute_query(supabase.table(TABLE).select("url_key,status")
                    .eq("url_key", row["url_key"]).limit(1)))
        existing = response.data[0] if response.data else {}
    # Older releases stored an official URL under an aggregator/source key.
    # UNIQUE(url) and UNIQUE(url_key) are independent identities; inspect both.
    url_response = (execute_query(supabase.table(TABLE).select("url_key,status")
                    .eq("url", row["url"]).limit(1)))
    url_owner = url_response.data[0] if url_response.data else {}
    if existing.get("status") == "posted" or url_owner.get("status") == "posted":
        return
    desired = row
    if url_owner:
        # If two legacy rows own the two identities, keep both rows and keys.
        # Promote the URL owner; never delete source history or steal its key.
        if existing and url_owner["url_key"] != row["url_key"]:
            desired = {**row, "url_key": url_owner["url_key"]}
        existing = url_owner
    if existing:
        # A successful post is immutable here (including deadline/reminder_sent).
        if existing.get("status") == "posted":
            return
        query = supabase.table(TABLE).update(desired).eq("url_key", existing["url_key"])
        # Compare-and-set: a concurrent promotion to posted must never be overwritten.
        if existing.get("status") is None:
            query = query.is_("status", "null")
        else:
            query = query.eq("status", existing["status"])
        try:
            result = execute_query(query)
        except Exception as exc:
            if attempt < 2 and (str(getattr(exc, "code", "")) == "23505"
                                or "23505" in str(exc) or "duplicate key" in str(exc).lower()):
                return _save_row(row, attempt=attempt + 1)
            raise
    else:
        try:
            result = execute_query(supabase.table(TABLE).insert({**row, "reminder_sent": False}))
        except Exception as exc:
            code = str(getattr(exc, "code", ""))
            if code == "23505" or "23505" in str(exc) or "duplicate key" in str(exc).lower():
                if attempt < 2:
                    return _save_row(row, attempt=attempt + 1)
            raise
    if not result.data:
        if attempt < 2:
            return _save_row(row, attempt=attempt + 1)
        raise DatabaseWriteError("Baza yozishni tasdiqlamadi (RLS yoki parallel o'zgarish)")


def save_grant(grant: dict, deadline_iso: str = None, status: str = "posted", key: str = None):
    save_grants_batch([{"grant": grant, "deadline_iso": deadline_iso, "status": status, "key": key}])


def save_grants_batch(items_with_meta: list):
    """Batch inserts with explicit failure and immutable posted records."""
    if not items_with_meta:
        return
    if not supabase:
        raise DatabaseWriteError("Baza sozlanmagan — yozuvlar saqlanmadi")

    # Collapse repeated keys before insertion; posted takes precedence.
    rows = {}
    for entry in items_with_meta:
        row = _grant_row(entry)
        previous = rows.get(row["url_key"])
        if previous is None or previous["status"] != "posted":
            rows[row["url_key"]] = row

    try:
        keys = list(rows)
        for start in range(0, len(keys), CHUNK):
            part = keys[start:start + CHUNK]
            result = execute_query(supabase.table(TABLE).select("url_key,status").in_("url_key", part))
            existing = {r["url_key"]: r for r in result.data or []}
            inserts = []
            for key in part:
                if key in existing:
                    _save_row(rows[key], existing[key])
                else:
                    inserts.append({**rows[key], "reminder_sent": False})
            if not inserts:
                continue
            try:
                result = execute_query(supabase.table(TABLE).insert(inserts))
                if len(result.data or []) != len(inserts):
                    raise DatabaseWriteError("Baza barcha yozuvlarni tasdiqlamadi")
            except Exception:
                # The request may have committed before a timeout, or one row
                # raced. Re-read each key; never blindly overwrite posted data.
                for row in inserts:
                    _save_row(row)
    except DatabaseWriteError:
        raise
    except Exception as exc:
        raise DatabaseWriteError("Bazaga yozib bo'lmadi — yurish to'xtatildi") from exc


def get_grants_nearing_deadline(days: int = 5) -> list:
    """Muddati yaqinlashgan va eslatma yuborilmagan grantlar."""
    if not supabase:
        return []
    try:
        now = datetime.now(timezone.utc)
        resp = (execute_query(supabase.table(TABLE)
                .select("*")
                .eq("status", "posted")
                .eq("reminder_sent", False)
                .not_.is_("deadline", "null")
                .gt("deadline", now.isoformat())
                .lte("deadline", (now + timedelta(days=days)).isoformat())
                .order("deadline")
                .limit(15)))
        return resp.data or []
    except Exception as e:
        raise RuntimeError("Muddati yaqin grantlar o'qilmadi") from e


def mark_reminder_sent(grant_url: str):
    if not supabase:
        raise DatabaseWriteError("Eslatma belgisi uchun baza sozlanmagan")
    try:
        response = execute_query(supabase.table(TABLE).update({"reminder_sent": True}).eq("url", grant_url))
        if not response.data:
            raise DatabaseWriteError("Eslatma belgisi saqlangani tasdiqlanmadi")
    except Exception as e:
        raise DatabaseWriteError("Eslatma belgisi saqlanmadi") from e


def stats() -> dict:
    """Baza holati — loglar uchun."""
    if not supabase:
        return {}
    out = {}
    try:
        for st in ("posted", "skipped", "duplicate"):
            r = execute_query(supabase.table(TABLE).select("id", count="exact").eq("status", st).limit(1))
            out[st] = r.count
    except Exception:
        pass
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    init_db()
    print("Holat:", stats())
