"""Supabase bazasi — takror postni to'xtatish va deadline eslatmalari.

TAKRORGA QARSHI UCH QATLAM:
  1. source_key  — aggregator maqolasining kaliti. Bir marta ko'rilgan maqola
                   qayta OCHILMAYDI ham (tarmoq so'rovi tejaladi).
  2. url_key     — grantning ASL havolasi kaliti. 8 ta aggregator bitta rasmiy
                   saytga olib borsa, faqat bittasi o'tadi.
  3. fingerprint — sarlavha barmoq izi. Rasmiy havolalar biroz farq qilsa ham
                   ("/apply" va "/apply/en") takrorni ushlaydi.

Yozuv holati (status):
  "posted"  — kanalga chiqdi
  "skipped" — chiqmadi (asl havola topilmadi, AI rad etdi va h.k.).
              Baribir yozib qo'yamiz — ertaga qayta urinib vaqt sarflamaslik uchun.

Yangi ustunlar kerak — migration.sql ni Supabase SQL Editor da bir marta ishlating.
"""

import os
import sys
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

TABLE = "posted_grants"
CHUNK = 100                  # bitta so'rovda nechta kalit tekshiriladi

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
    if not supabase:
        print("Baza sozlanmagan.")
        if strict:
            sys.exit(1)
        return False

    try:
        supabase.table(TABLE).select("id").limit(1).execute()
    except Exception as e:
        print(f"Bazaga ulanib bo'lmadi: {e}")
        if strict:
            sys.exit(1)
        return False

    missing = []
    for col in ("url_key", "source_key", "fingerprint", "status"):
        try:
            supabase.table(TABLE).select(col).limit(1).execute()
        except Exception:
            missing.append(col)

    if missing:
        print("=" * 66)
        print(f"BAZADA USTUNLAR YETISHMAYAPTI: {', '.join(missing)}")
        print("migration.sql faylini Supabase SQL Editor da ishga tushiring.")
        print("=" * 66)
        if strict:
            sys.exit(1)
        return False

    print("Baza tayyor.")
    return True


def _collect(column: str, values: list) -> set:
    """Berilgan ustun bo'yicha bazada allaqachon bor qiymatlarni qaytaradi."""
    found = set()
    values = [v for v in values if v]
    if not supabase or not values:
        return found

    uniq = list(dict.fromkeys(values))
    for i in range(0, len(uniq), CHUNK):
        batch = uniq[i:i + CHUNK]
        try:
            resp = supabase.table(TABLE).select(column).in_(column, batch).execute()
            for row in resp.data or []:
                if row.get(column):
                    found.add(row[column])
        except Exception as e:
            # Bazani o'qib bo'lmasa — to'xtaymiz. Aks holda hamma narsa
            # "yangi" ko'rinib, kanalga takror post yog'iladi.
            print(f"Bazani o'qishda xatolik ({column}): {e}")
            sys.exit(1)
    return found


def get_seen_source_keys(source_keys: list) -> set:
    """Allaqachon ko'rib chiqilgan aggregator maqolalari."""
    return _collect("source_key", source_keys)


def get_seen_url_keys(url_keys: list) -> set:
    """Allaqachon post qilingan asl havolalar."""
    return _collect("url_key", url_keys)


def get_seen_fingerprints(fingerprints: list) -> set:
    """Allaqachon post qilingan sarlavha barmoq izlari."""
    return _collect("fingerprint", fingerprints)


def save_grant(grant: dict, deadline_iso: str = None, status: str = "posted"):
    """Yozuvni bazaga qo'shadi (mavjud bo'lsa yangilaydi)."""
    if not supabase:
        return

    if deadline_iso and (deadline_iso == "null" or len(str(deadline_iso)) < 10):
        deadline_iso = None

    # Asl havola topilmagan yozuvlarda url_key bo'sh bo'ladi. Bunday holatda
    # manba maqolasining kalitini ishlatamiz — shunda yozuv baribir yagona
    # bo'ladi va ertaga o'sha maqola qayta ochilmaydi.
    url_key = grant.get("url_key") or grant.get("source_key") or ""

    row = {
        "title": (grant.get("title") or "")[:255],
        "url": grant.get("url") or grant.get("source_url", ""),
        "url_key": url_key,
        "source_url": grant.get("source_url", ""),
        "source_key": grant.get("source_key", ""),
        "fingerprint": grant.get("fingerprint", ""),
        "deadline": deadline_iso,
        "reminder_sent": False,
        "status": status,
    }

    # 1-usul: upsert. Bu `url_key` bo'yicha YAGONA INDEKS mavjud bo'lgandagina
    # ishlaydi (migration.sql dagi idx_pg_url_key_uniq).
    try:
        supabase.table(TABLE).upsert(row, on_conflict="url_key").execute()
        return
    except Exception as e:
        msg = str(e)
        # 42P10 = "no unique or exclusion constraint matching the ON CONFLICT
        # specification", ya'ni indeks yaratilmagan.
        if "42P10" not in msg and "ON CONFLICT" not in msg:
            print(f"  Bazaga yozib bo'lmadi: {msg[:120]}")
            return

    # 2-usul (zaxira): indeks yo'q. Qo'lda tekshirib, yangilaymiz yoki qo'shamiz.
    # Bu MUHIM — aks holda hech nima yozilmaydi va bot bir xil grantlarni
    # har kuni qayta post qiladi.
    try:
        existing = (supabase.table(TABLE).select("id")
                    .eq("url_key", url_key).limit(1).execute())
        if existing.data:
            supabase.table(TABLE).update(row).eq("url_key", url_key).execute()
        else:
            supabase.table(TABLE).insert(row).execute()
    except Exception as e:
        print(f"  Bazaga yozib bo'lmadi (zaxira usul ham): {str(e)[:120]}")


def get_grants_nearing_deadline(days: int = 5) -> list:
    """Muddati yaqinlashgan va eslatma yuborilmagan grantlar."""
    if not supabase:
        return []
    try:
        now = datetime.now(timezone.utc)
        resp = (supabase.table(TABLE)
                .select("*")
                .eq("status", "posted")
                .eq("reminder_sent", False)
                .not_.is_("deadline", "null")
                .gt("deadline", now.isoformat())
                .lte("deadline", (now + timedelta(days=days)).isoformat())
                .order("deadline")
                .limit(15)
                .execute())
        return resp.data or []
    except Exception as e:
        print(f"Muddati yaqin grantlarni olishda xatolik: {e}")
        return []


def mark_reminder_sent(grant_url: str):
    if not supabase:
        return
    try:
        supabase.table(TABLE).update({"reminder_sent": True}).eq("url", grant_url).execute()
    except Exception as e:
        print(f"Eslatma belgisini saqlashda xatolik: {e}")


def stats() -> dict:
    """Baza holati — loglar uchun."""
    if not supabase:
        return {}
    out = {}
    try:
        for st in ("posted", "skipped"):
            r = supabase.table(TABLE).select("id", count="exact").eq("status", st).limit(1).execute()
            out[st] = r.count
    except Exception:
        pass
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    init_db()
    print("Holat:", stats())
