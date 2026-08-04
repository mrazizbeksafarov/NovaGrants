"""Nova Grants — asosiy quvur.

Bosqichlar:
  1. YIG'ISH     — barcha manbalardan xom yozuvlar (scraper.py)
  2. SARALASH    — yangilik/reklama/qo'llanmalarni tashlash (filters.py)
  3. ESKIRIB     — allaqachon ko'rilgan maqolalarni tashlash (source_key bo'yicha)
  4. QAZISH      — aggregator maqolasidan ASL havolani topish (link_resolver.py)
  5. TAKROR      — asl havola va sarlavha izi bo'yicha takrorlarni tashlash
  6. POST        — AI matn yozadi, kanalga chiqadi (ai_agent.py, telegram_bot.py)
  7. ESLATMA     — muddati yaqinlashganlar haqida (yagona ruxsat etilgan takror)

Asosiy kafolat: kanalga FAQAT asl havola tushadi. Asl havola topilmagan yozuv
post qilinmaydi — bazaga "skipped" deb yoziladi va qayta urinilmaydi.
"""

import os
import sys
import time
import concurrent.futures
from datetime import datetime, timezone

from scraper import fetch_all
from filters import (
    looks_like_opportunity, extract_deadline, deadline_passed, validate_deadline_iso,
)
from link_resolver import resolve_grant, is_aggregator
from database import (
    init_db, get_seen_source_keys, get_seen_url_keys, get_seen_fingerprints,
    save_grant as _save_grant, get_grants_nearing_deadline,
    mark_reminder_sent as _mark_reminder_sent, stats,
)
from ai_agent import generate_post_content, BATCH_SIZE
from post_builder import build_post
from telegram_bot import (
    send_telegram_message as _send_telegram_message,
    publish as _publish,
    validate_rich_blocks,
)

MAX_RESOLVE_PER_RUN = 70     # bir yurishda nechta maqolani ochamiz (tarmoq nazorati)
MAX_POST_PER_RUN = 32        # bir kunda kanalga nechta yangi imkoniyat (4 ta post)
RESOLVE_WORKERS = 5          # parallel oqim (saytlarni bezovta qilmaslik uchun kam)

# Quruq sinov: hech narsa yuborilmaydi va bazaga yozilmaydi.
#   python main.py --dry-run     yoki     DRY_RUN=1
DRY_RUN = os.getenv("DRY_RUN") == "1" or "--dry-run" in sys.argv


def log(msg=""):
    print(msg, flush=True)


# Baza sxemasi tayyormi (quruq sinovda tayyor bo'lmasligi mumkin)
DB_READY = False


def save_grant(grant, deadline_iso=None, status="posted"):
    if DRY_RUN or not DB_READY:
        return
    _save_grant(grant, deadline_iso=deadline_iso, status=status)


def seen_source_keys(keys):
    return get_seen_source_keys(keys) if DB_READY else set()


def seen_url_keys(keys):
    return get_seen_url_keys(keys) if DB_READY else set()


def seen_fingerprints(keys):
    return get_seen_fingerprints(keys) if DB_READY else set()


def mark_reminder_sent(url):
    if DRY_RUN:
        return
    _mark_reminder_sent(url)


def send_telegram_message(text):
    if DRY_RUN:
        log("\n┌─ QURUQ SINOV — kanalga yuborilmadi, post shunday ko'rinardi:")
        for line in text.split("\n"):
            log(f"│ {line}")
        log("└─\n")
        return True
    return _send_telegram_message(text)


def publish_post(blocks, html):
    if DRY_RUN:
        from telegram_bot import html_to_plain
        ok, detail = validate_rich_blocks(blocks, html_to_plain(html))
        mark = "✅ tuzilma yaroqli" if ok else f"❌ XATO: {detail[:70]}"
        log(f"\n┌─ QURUQ SINOV — {len(blocks)} ta rich blok, tuzilma tekshiruvi: {mark}")
        log("│  HTML ko'rinishi (zaxira):")
        for line in html.split("\n"):
            log(f"│ {line}")
        log("└─\n")
        return True
    return _publish(blocks, html)


# ──────────────────────────────────────────────────────────────────
# 7-bosqich: eslatmalar (takrorga yagona ruxsat)
# ──────────────────────────────────────────────────────────────────
def send_reminders():
    log("── Muddati yaqinlashgan grantlar tekshirilmoqda...")
    grants = get_grants_nearing_deadline(days=5)

    if not grants:
        log("   Bugun eslatma yo'q.")
        return

    from post_builder import _deadline_label, _esc, CHANNEL_TAG

    valid = [g for g in grants if g.get("url") and g.get("title")]
    if not valid:
        log("   Eslatma uchun yaroqli yozuv yo'q.")
        return

    # Rich ko'rinish: sarlavha + har bir imkoniyat uchun havolali qator
    blocks = [
        {"type": "heading", "size": 2, "text": "Oxirgi muddat yaqinlashmoqda"},
        {"type": "paragraph",
         "text": "Quyidagi imkoniyatlar uchun hujjat topshirish muddati tugayapti."},
        {"type": "divider"},
        # Har bir element InputRichBlockListItem: ichida `blocks` bo'ladi
        {"type": "list", "items": [
            {"blocks": [{"type": "paragraph", "text": [
                {"type": "url", "url": g["url"], "text": str(g["title"])[:120]},
                f" — {_deadline_label(g.get('deadline'))}",
            ]}]} for g in valid
        ]},
        {"type": "paragraph", "text": "Kechikkan ariza qabul qilinmaydi."},
        {"type": "footer", "text": CHANNEL_TAG},
    ]

    # HTML zaxira — xuddi shu ma'lumotdan
    html = ["<b>Oxirgi muddat yaqinlashmoqda</b>", "",
            "Quyidagi imkoniyatlar uchun hujjat topshirish muddati tugayapti:", ""]
    for i, g in enumerate(valid, 1):
        html.append(f'{i}. <a href="{g["url"]}">{_esc(str(g["title"])[:120])}</a>')
        html.append(f"   <i>Muddat: {_deadline_label(g.get('deadline'))}</i>")
        html.append("")
    html.append("Kechikkan ariza qabul qilinmaydi.")
    html.append("")
    html.append(CHANNEL_TAG)

    if publish_post(blocks, "\n".join(html)):
        for g in valid:
            mark_reminder_sent(g.get("url", ""))
        log(f"   {len(valid)} ta eslatma yuborildi.")
    else:
        log("   Eslatma yuborilmadi — keyingi safar qayta urinamiz.")


# ──────────────────────────────────────────────────────────────────
# 1-6 bosqichlar
# ──────────────────────────────────────────────────────────────────
def collect_candidates():
    """Yig'ish → saralash → eskilarini tashlash."""
    raw = fetch_all()
    if not raw:
        log("Hech qanday ma'lumot yig'ilmadi.")
        return []

    # 2-bosqich: mavzu bo'yicha saralash
    relevant = []
    for item in raw:
        text = f"{item.get('title', '')}\n{item.get('summary', '')}"
        if deadline_passed(text):
            continue
        if not looks_like_opportunity(item.get("title", ""), item.get("summary", ""), item.get("topic", "")):
            continue
        relevant.append(item)

    log(f"── Saralash: {len(raw)} → {len(relevant)} ta imkoniyatga o'xshash yozuv")

    # 3-bosqich: allaqachon ko'rilgan maqolalar
    seen_sources = seen_source_keys([i["source_key"] for i in relevant])
    fresh = [i for i in relevant if i["source_key"] not in seen_sources]
    log(f"── Yangi: {len(fresh)} ta ({len(relevant) - len(fresh)} tasi avval ko'rilgan)")

    return fresh


def resolve_links(items):
    """4-bosqich: asl havolalarni qazib olish."""
    batch = items[:MAX_RESOLVE_PER_RUN]
    if len(items) > MAX_RESOLVE_PER_RUN:
        log(f"── Diqqat: {len(items)} tadan faqat {MAX_RESOLVE_PER_RUN} tasi qayta ishlanadi, "
            f"qolgan {len(items) - MAX_RESOLVE_PER_RUN} tasi keyingi yurishga qoladi.")

    log(f"── {len(batch)} ta yozuvda asl havola qidirilmoqda...")
    started = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=RESOLVE_WORKERS) as ex:
        resolved = list(ex.map(resolve_grant, batch))

    ok = [g for g in resolved if g.get("url")]
    failed = [g for g in resolved if not g.get("url")]

    log(f"── Asl havola topildi: {len(ok)}/{len(resolved)} ta ({time.time() - started:.0f}s)")

    # Topilmaganlarni belgilab qo'yamiz — ertaga qayta urinmaslik uchun
    for g in failed:
        save_grant(g, status="skipped")

    return ok


def deduplicate(items):
    """5-bosqich: asl havola va sarlavha izi bo'yicha takrorlarni tashlash."""
    seen_urls = seen_url_keys([g["url_key"] for g in items])
    seen_fps = seen_fingerprints([g["fingerprint"] for g in items if g.get("fingerprint")])

    unique, batch_urls, batch_fps = [], set(), set()
    dropped_db, dropped_batch = 0, 0

    for g in items:
        uk, fp = g.get("url_key", ""), g.get("fingerprint", "")

        if uk in seen_urls or (fp and fp in seen_fps):
            dropped_db += 1
            save_grant(g, status="skipped")       # qayta qazimaslik uchun
            continue

        if uk in batch_urls or (fp and fp in batch_fps):
            dropped_batch += 1
            continue

        batch_urls.add(uk)
        if fp:
            batch_fps.add(fp)
        unique.append(g)

    log(f"── Takrorlar tashlandi: bazada bor {dropped_db} ta, shu yurishda takror {dropped_batch} ta")
    log(f"── Post uchun qoldi: {len(unique)} ta")
    return unique


def enrich_deadlines(items):
    """Har bir grant uchun muddatni matndan chiqaramiz (AI dan oldin)."""
    for g in items:
        dt = extract_deadline(f"{g.get('title', '')}\n{g.get('summary', '')}")
        g["deadline_iso"] = dt.isoformat().replace("+00:00", "Z") if dt else None
    return items


def publish(items):
    """6-bosqich: AI matn yozadi va kanalga chiqaramiz."""
    if not items:
        log("── Post qilinadigan yangi imkoniyat yo'q.")
        return 0

    if len(items) > MAX_POST_PER_RUN:
        # Bular yo'qolmaydi: bazaga yozilmagani uchun keyingi yurishda yana keladi.
        log(f"── {len(items)} tadan {MAX_POST_PER_RUN} tasi post qilinadi, "
            f"qolgan {len(items) - MAX_POST_PER_RUN} tasi keyingi yurishga qoladi.")
        items = items[:MAX_POST_PER_RUN]

    posted = 0
    tokens = 0

    for start in range(0, len(items), BATCH_SIZE):
        batch = items[start:start + BATCH_SIZE]
        log(f"── {start // BATCH_SIZE + 1}-to'plam: {len(batch)} ta imkoniyat AI ga yuborilmoqda...")

        content = generate_post_content(batch)

        if not content or not content.get("cards"):
            log("   AI bu to'plamdan mos imkoniyat topmadi.")
            for g in batch:
                save_grant(g, deadline_iso=g.get("deadline_iso"), status="skipped")
            continue

        usage = content.get("usage") or {}
        if usage:
            tokens += usage.get("total", 0)
            log(f"   {usage.get('model')} | {usage.get('total')} token")

        cards = content["cards"]
        blocks, html = build_post(content.get("headline", ""), cards)

        if not publish_post(blocks, html):
            log("   Xabar yuborilmadi — bu to'plam keyingi safar qayta urinib ko'riladi.")
            continue

        # AI tanlagan imkoniyatlar — "posted", tanlanmaganlari — "skipped".
        # Ikkalasi ham bazaga tushadi, shunda ertaga qayta ishlanmaydi.
        chosen = {c["_source"]["url"]: c for c in cards if c.get("_source")}

        for g in batch:
            card = chosen.get(g["url"])
            if card:
                # AI bergan sanani tekshiramiz — o'tib ketgan bo'lsa o'zimiznikiga qaytamiz
                deadline = (validate_deadline_iso(card.get("deadline_iso"))
                            or g.get("deadline_iso"))
                save_grant(g, deadline_iso=deadline, status="posted")
                posted += 1
            else:
                save_grant(g, deadline_iso=g.get("deadline_iso"), status="skipped")

        log(f"   ✅ {len(chosen)} ta post qilindi, {len(batch) - len(chosen)} tasi rad etildi.")

    if tokens:
        log(f"── Jami sarflangan token: {tokens}")
    return posted


def run():
    started = datetime.now(timezone.utc)
    log("=" * 66)
    log(f"Nova Grants — {started.strftime('%Y-%m-%d %H:%M')} UTC"
        + ("   [QURUQ SINOV]" if DRY_RUN else ""))
    log("=" * 66)

    global DB_READY
    DB_READY = init_db(strict=not DRY_RUN)
    if DB_READY:
        log(f"Baza holati: {stats()}")
    elif DRY_RUN:
        log("Baza tayyor emas — quruq sinovda takror tekshiruvisiz davom etamiz.")
    log()

    # Avval eslatmalar (bu yagona ruxsat etilgan takror)
    send_reminders()
    log()

    candidates = collect_candidates()
    if not candidates:
        log("\nYangi imkoniyat yo'q. Vazifa yakunlandi.")
        return

    resolved = resolve_links(candidates)

    # Xavfsizlik to'ri: aggregator havolasi hech qanday holatda o'tmasin
    leaked = [g for g in resolved if is_aggregator(g["url"])]
    if leaked:
        log(f"── DIQQAT: {len(leaked)} ta aggregator havolasi filtrdan o'tib ketdi — tashlandi.")
        resolved = [g for g in resolved if not is_aggregator(g["url"])]

    unique = deduplicate(resolved)
    unique = enrich_deadlines(unique)

    posted = publish(unique)

    log()
    log("=" * 66)
    log(f"Yakunlandi: {posted} ta yangi imkoniyat kanalga chiqdi "
        f"({(datetime.now(timezone.utc) - started).seconds}s)")
    log("=" * 66)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    run()
