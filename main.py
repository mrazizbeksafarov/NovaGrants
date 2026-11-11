"""Nova Grants — asosiy quvur.

Bosqichlar:
  1. YIG'ISH     — barcha manbalardan xom yozuvlar (scraper.py)
  2. SARALASH    — yangilik/reklama/qo'llanmalarni tashlash (filters.py)
  3. ESKIRIB     — allaqachon ko'rilgan maqolalarni tashlash (source_key bo'yicha)
  4. QAZISH      — aggregator maqolasidan ASL havolani topish (link_resolver.py)
  5. TAKROR      — asl havola va sarlavha izi bo'yicha takrorlarni tashlash
  6. POST        — AI matn yozadi, kanalga chiqadi (ai_agent.py, telegram_bot.py)
  7. ESLATMA     — muddati yaqinlashganlar haqida (yagona ruxsat etilgan takror)

Asosiy kafolat: kanalga FAQAT asl havola tushadi. Vaqtinchalik xatolar
doimiy rad etish bilan aralashtirilmaydi — yozuv keyingi yurishda qayta ko'riladi.
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
from link_resolver import resolve_grant, is_aggregator, is_blocked
from database import (
    init_db, get_seen_source_keys, get_seen_url_keys, get_seen_fingerprints,
    get_seen_fingerprint_scopes,
    save_grant as _save_grant, save_grants_batch as _save_grants_batch,
    get_grants_nearing_deadline, mark_reminder_sent as _mark_reminder_sent, stats,
)
from ai_agent import generate_post_content, BATCH_SIZE
from post_builder import build_post, usable_cards
from telegram_bot import (
    send_telegram_message as _send_telegram_message,
    publish as _publish,
    notify_admin,
)

MAX_RESOLVE_PER_RUN = 80     # bir yurishda nechta maqolani ochamiz (tarmoq nazorati)
MAX_POST_PER_RUN = 32        # bir kunda kanalga nechta yangi imkoniyat (4 ta post)
RESOLVE_WORKERS = 14         # superkompyuter parallel oqimlari (har bir domen alohida throttle nazoratida)

# Quruq sinov: hech narsa yuborilmaydi va bazaga yozilmaydi.
#   python main.py --dry-run     yoki     DRY_RUN=1
DRY_RUN = os.getenv("DRY_RUN") == "1" or "--dry-run" in sys.argv


def log(msg=""):
    print(msg, flush=True)


def candidate_quality(grant):
    """Prefer the most informative account when sources describe one programme."""
    import re
    summary = str(grant.get("summary") or "")
    eligibility = bool(re.search(r"uzbek|o.zbekiston|all nationalities|all countries|worldwide", summary, re.I))
    return (eligibility, bool(grant.get("deadline_iso")),
            grant.get("kind") == "official", min(len(summary), 1800))


# Baza sxemasi tayyormi (quruq sinovda tayyor bo'lmasligi mumkin)
DB_READY = False


def save_grant(grant, deadline_iso=None, status="posted", key=None):
    if DRY_RUN or not DB_READY:
        return
    _save_grant(grant, deadline_iso=deadline_iso, status=status, key=key)


def save_grants_batch(items_with_meta):
    if DRY_RUN or not DB_READY:
        return
    _save_grants_batch(items_with_meta)


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
        log(f"\n┌─ QURUQ SINOV — {len(blocks)} ta rich blok (Telegram so'rovisiz)")
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

    from post_builder import _deadline_label, _esc, _esc_attr, CHANNEL_TAG

    # Bazada 2800+ eski yozuv bor va ularning URL'i aggregator maqolasiniki.
    # Asosiy oqimda aggregator filtri bor, eslatmada yo'q edi — natijada
    # "faqat asl havola" kafolati aynan shu yerdan buzilardi.
    valid = []
    leaked = 0
    for g in grants:
        url = str(g.get("url") or "")
        if not url or not g.get("title"):
            continue
        if is_aggregator(url) or is_blocked(url):
            leaked += 1
            mark_reminder_sent(url)               # qayta ko'tarilmasin
            continue
        if not validate_deadline_iso(str(g.get("deadline") or "")):
            continue                              # muddat o'tib ketgan yoki ishonchsiz
        valid.append(g)

    if leaked:
        log(f"   {leaked} ta eski aggregator havolasi eslatmadan chiqarildi.")

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
        html.append(f'{i}. <a href="{_esc_attr(g["url"])}">{_esc(str(g["title"])[:120])}</a>')
        html.append(f"   <i>Muddat: {_deadline_label(g.get('deadline'))}</i>")
        html.append("")
    html.append("Kechikkan ariza qabul qilinmaydi.")
    html.append("")
    html.append(CHANNEL_TAG)

    if publish_post(blocks, "\n".join(html)):
        for g in valid:
            mark_reminder_sent(g.get("url", ""))
        log(f"   {len(valid)} ta eslatma " + ("tayyorlandi (quruq sinov)." if DRY_RUN else "yuborildi."))
    else:
        log("   Eslatma yuborilmadi — keyingi safar qayta urinamiz.")


# ──────────────────────────────────────────────────────────────────
# 1-6 bosqichlar
# ──────────────────────────────────────────────────────────────────
def collect_candidates():
    """Yig'ish → saralash → eskilarini tashlash."""
    raw = fetch_all()
    if not raw:
        raise RuntimeError("Hech bir manbadan ma'lumot yig'ilmadi — manbalarni tekshiring")

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
    # Round-robin across sources so one failing feed cannot fill the entire budget.
    from collections import defaultdict, deque
    queues = defaultdict(deque)
    for item in items:
        queues[item.get("source_id", "unknown")].append(item)
    batch = []
    while queues and len(batch) < MAX_RESOLVE_PER_RUN:
        for source in list(queues):
            batch.append(queues[source].popleft())
            if not queues[source]:
                del queues[source]
            if len(batch) == MAX_RESOLVE_PER_RUN:
                break
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

    # Failure may be a timeout/429. Do not permanently hide these source keys.
    if failed:
        log(f"── Havolasi topilmagan {len(failed)} ta yozuv qayta urinish uchun qoldi.")

    return ok


def deduplicate(items):
    """5-bosqich: asl havola, kanonik kalit, semantik slug va barmoq izi bo'yicha takrorlarni tashlash."""
    from database import make_semantic_slug, get_seen_semantic_slugs
    from link_resolver import host_of, root_domain, is_aggregator, is_blocked, canonical_url_key, program_fingerprint

    # Har bir grant uchun semantik slug va kanonik kalit tayyorlaymiz, agregatorlarni suzamiz
    clean_items = []
    for g in sorted(items, key=candidate_quality, reverse=True):
        u = g.get("url", "")
        if not u or is_aggregator(u) or is_blocked(u):
            continue
        title = g.get("title", "")
        if not g.get("canonical_url_key"):
            g["canonical_url_key"] = canonical_url_key(u, title)
        if not g.get("program_fingerprint"):
            g["program_fingerprint"] = program_fingerprint(title, u)
        if not g.get("semantic_slug"):
            g["semantic_slug"] = make_semantic_slug(title, host_of(u), g.get("deadline_iso"), u)
        clean_items.append(g)

    items = clean_items
    url_queries = [g["url_key"] for g in items if g.get("url_key")] + [g["canonical_url_key"] for g in items if g.get("canonical_url_key")]
    seen_urls = seen_url_keys(url_queries)
    seen_fps = get_seen_fingerprint_scopes([g["fingerprint"] for g in items if g.get("fingerprint")]) if DB_READY else set()
    seen_slugs = get_seen_semantic_slugs([g["semantic_slug"] for g in items if g.get("semantic_slug")]) if DB_READY else set()

    # Group connected identities before choosing representatives. A later
    # bridging article can connect two earlier records; a greedy set misses it.
    parents = list(range(len(items)))
    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i
    owners = {}
    for i, g in enumerate(items):
        domain = root_domain(host_of(g["url"]))
        identities = [
            ("url", g.get("url_key")), ("url", g.get("canonical_url_key")),
            ("title", (g.get("fingerprint"), domain) if g.get("fingerprint") else None),
            ("program", g.get("program_fingerprint")), ("slug", g.get("semantic_slug")),
        ]
        for kind, identity in identities:
            if not identity:
                continue
            key = (kind, identity)
            if key in owners:
                parents[root(i)] = root(owners[key])
            else:
                owners[key] = i
    groups = {}
    for i, g in enumerate(items):
        groups.setdefault(root(i), []).append(g)

    unique, duplicates_to_save = [], []
    dropped_db = dropped_batch = 0
    for group in groups.values():
        in_database = any(
            g.get("url_key") in seen_urls or g.get("canonical_url_key") in seen_urls
            or (g.get("fingerprint"), root_domain(host_of(g["url"]))) in seen_fps
            or g.get("semantic_slug") in seen_slugs
            for g in group)
        if in_database:
            dropped_db += len(group)
            duplicates_to_save.extend({"grant": g, "status": "duplicate", "key": g.get("source_key")} for g in group)
            continue
        winner = group[0]  # already ordered by evidence quality
        winner["_aliases"] = group[1:]
        unique.append(winner)
        dropped_batch += len(group) - 1

    if duplicates_to_save:
        save_grants_batch(duplicates_to_save)

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

        if content is None:
            raise RuntimeError("AI javobi olinmadi — grantlar keyingi yurishga qoldirildi")

        if not content.get("cards"):
            log("   AI bu to'plamdan mos imkoniyat topmadi.")
            save_grants_batch([{"grant": g, "deadline_iso": g.get("deadline_iso"), "status": "skipped"} for g in batch])
            continue

        usage = content.get("usage") or {}
        if usage:
            tokens += usage.get("total", 0)
            log(f"   {usage.get('model')} | {usage.get('total')} token")

        cards = usable_cards(content["cards"])
        if not cards:
            raise RuntimeError("AI kartochkalari yaroqsiz — grantlar saqlanmagan holda qoldirildi")
        # A mixed digest can contain partial awards. Do not let an AI headline
        # claim that every opportunity is fully funded or has one eligibility.
        blocks, html = build_post(f"{len(cards)} ta yangi xalqaro imkoniyat", cards)

        if not publish_post(blocks, html):
            raise RuntimeError("Telegram xabari to'liq yuborilmadi — Actions logini tekshiring")

        # AI tanlagan imkoniyatlar — "posted", tanlanmaganlari — "skipped".
        # Ikkalasi ham bazaga tushadi, shunda ertaga qayta ishlanmaydi.
        chosen = {c["_source"]["url"]: c for c in cards if c.get("_source")}
        batch_saves = []

        for g in batch:
            card = chosen.get(g["url"])
            if card:
                # AI bergan sanani tekshiramiz — o'tib ketgan bo'lsa o'zimiznikiga qaytamiz
                deadline = (validate_deadline_iso(card.get("deadline_iso"))
                            or g.get("deadline_iso"))
                batch_saves.append({"grant": g, "deadline_iso": deadline, "status": "posted"})
                for alias in g.get("_aliases", []):
                    batch_saves.append({"grant": alias, "status": "duplicate", "key": alias.get("source_key")})
                posted += 1
            else:
                batch_saves.append({"grant": g, "deadline_iso": g.get("deadline_iso"), "status": "skipped"})

        save_grants_batch(batch_saves)
        action = "tayyorlandi (yuborilmadi)" if DRY_RUN else "post qilindi"
        log(f"   ✅ {len(chosen)} ta {action}, {len(batch) - len(chosen)} tasi rad etildi.")

    if tokens:
        log(f"── Jami sarflangan token: {tokens}")
    return posted


def run():
    problems = []                # yurish oxirida adminga yuboriladi
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
    if DB_READY:
        send_reminders()
    log()

    candidates = collect_candidates()
    if not candidates:
        log("\nYangi imkoniyat yo'q.")

    resolved = resolve_links(candidates)
    if candidates and len(resolved) < len(candidates[:MAX_RESOLVE_PER_RUN]) * 0.35:
        problems.append(f"Asl havola topish darajasi past: "
                        f"{len(resolved)}/{len(candidates[:MAX_RESOLVE_PER_RUN])}")

    # Xavfsizlik to'ri: aggregator havolasi hech qanday holatda o'tmasin
    leaked = [g for g in resolved if is_aggregator(g["url"])]
    if leaked:
        log(f"── DIQQAT: {len(leaked)} ta aggregator havolasi filtrdan o'tib ketdi — tashlandi.")
        problems.append(f"{len(leaked)} ta aggregator havolasi filtrdan o'tib ketdi")
        resolved = [g for g in resolved if not is_aggregator(g["url"])]

    unique = deduplicate(enrich_deadlines(resolved))

    posted = publish(unique)
    if unique and not posted:
        problems.append(f"{len(unique)} ta nomzod bor edi, lekin hech biri post qilinmadi")

    elapsed = int((datetime.now(timezone.utc) - started).total_seconds())
    log()
    log("=" * 66)
    if DRY_RUN:
        log(f"Quruq sinov yakunlandi: {posted} ta kartochka tayyorlandi, yuborilmadi ({elapsed}s)")
    else:
        log(f"Yakunlandi: {posted} ta yangi imkoniyat kanalga chiqdi ({elapsed}s)")
    log("=" * 66)

    if not DRY_RUN:
        title = "⚠️ <b>Nova Grants — diqqat talab qiladi</b>" if problems else "✅ <b>Nova Grants — Kunlik hisobot</b>"
        lines = [title, ""]
        if problems:
            lines.append("<b>Aniqlangan muammolar:</b>")
            lines.extend(f"• {p}" for p in problems)
            lines.append("")
        lines.append(f"📊 <b>Kanalga chiqdi:</b> {posted} ta yangi grant")
        lines.append(f"⏱ <b>Vaqt:</b> {elapsed} soniya")
        db_stat = stats()
        if db_stat:
            lines.append(f"🗄 <b>Bazada saqlangan:</b> {db_stat.get('posted', 0)} ta grant")
        lines.append(f"📅 <b>Yurish vaqti:</b> {started.strftime('%Y-%m-%d %H:%M')} UTC")
        notify_admin("\n".join(lines))



if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        run()
    except Exception as exc:
        if not DRY_RUN:
            notify_admin(f"⚠️ <b>Nova Grants to'xtadi</b>\nXato turi: {type(exc).__name__}. "
                         "GitHub Actions logini tekshiring; saqlanmagan to'plam qayta ko'riladi.")
        raise
