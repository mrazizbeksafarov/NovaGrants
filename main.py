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
import delivery_journal
from datetime import datetime, timezone, timedelta

from scraper import fetch_all
from filters import (
    extract_deadline, validate_deadline_iso,
    discovery_decision,
)
from link_resolver import resolve_grant, is_aggregator, is_blocked
from database import (
    init_db, get_seen_source_keys, get_seen_url_keys, get_seen_urls, get_seen_fingerprints,
    get_seen_fingerprint_scopes,
    save_grant as _save_grant, save_grants_batch as _save_grants_batch,
    save_review as _save_review, posted_identity_rows,
    get_grants_nearing_deadline, mark_reminder_sent as _mark_reminder_sent, stats,
)
from ai_agent import generate_post_content, BATCH_SIZE
from official_evidence import verify_all as verify_official_pages
from scraper import SOURCE_ISSUES
from resilience import transient_error
import selection_audit
from selection_policy import priority as selection_priority, discovery_priority, cycle_hint
from post_builder import build_post, usable_cards
from telegram_bot import (
    send_telegram_message as _send_telegram_message,
    publish_single as _publish, fits_single_message, CHANNEL_ID,
    notify_admin,
    DeliveryUncertain,
    delivery_receipts,
)

MAX_RESOLVE_PER_RUN = 80     # bir yurishda nechta maqolani ochamiz (tarmoq nazorati)
MAX_POST_PER_RUN = 32        # AI tekshiradigan nomzodlar; nashr — kuniga bitta digest
MAX_DIGEST_CARDS = 8
MAX_EDITORIAL_BATCHES = 8
RESOLVE_ISSUES = []
PUBLISH_ISSUES = []
REMINDER_ISSUES = []
REVIEW_ISSUES = []
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


def seen_source_keys(keys, incoming_titles=None):
    return get_seen_source_keys(keys, incoming_titles) if DB_READY else set()


def hold_for_review(grant, reason):
    selection_audit.record("policy", grant, "review", reason)
    REVIEW_ISSUES.append((grant.get("source_key") or grant.get("url"), reason))
    if not DRY_RUN and DB_READY:
        _save_review(grant, reason)


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
    if not _publish(blocks, html):
        return False
    return {"delivered": True, "messages": delivery_receipts()}


# ──────────────────────────────────────────────────────────────────
# 7-bosqich: eslatmalar (takrorga yagona ruxsat)
# ──────────────────────────────────────────────────────────────────
def send_reminders():
    log("── Muddati yaqinlashgan grantlar tekshirilmoqda...")
    REMINDER_ISSUES.clear()
    if DB_READY and not DRY_RUN:
        resumed = delivery_journal.resume(CHANNEL_ID, "reminder", publish_post)
        if resumed is not None:
            log("   Bugungi eslatma jurnali tiklandi yoki allaqachon yuborilgan.")
            return
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

    # Keep the complete reminder, including its HTML fallback, in one message.
    # Unselected rows remain reminder_sent=False for another day.

    if leaked:
        log(f"   {leaked} ta eski aggregator havolasi eslatmadan chiqarildi.")

    if not valid:
        log("   Eslatma uchun yaroqli yozuv yo'q.")
        return

    valid = revalidate_reminders(valid)
    if not valid:
        log("   Hozirgi saralash bo'yicha tasdiqlangan eslatma yo'q; tekshirilmaganlar yuborilmadi.")
        return
    valid = sorted(valid, key=lambda g: g["deadline"])[:8]

    def render_reminder(valid):
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

        html = "\n".join(html)
        return blocks, html

    while valid:
        blocks, html = render_reminder(valid)
        if fits_single_message(blocks, html):
            break
        valid = valid[:-1]
    if not valid:
        raise RuntimeError("Eslatma bitta xabarga sig'madi; yuborish boshlanmadi")
    if DB_READY and not DRY_RUN:
        delivered = delivery_journal.deliver(
            CHANNEL_ID, "reminder", blocks, html, [], publish_post, len(valid),
            reminder_urls=[g["url"] for g in valid])
    else:
        delivered = publish_post(blocks, html)
    if delivered:
        if DRY_RUN or not DB_READY:
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
        state, reason = discovery_decision(item.get("title", ""), item.get("summary", ""), item.get("topic", ""),
            refresh_details=item.get("kind") == "official" and item.get("fetch_details"))
        selection_audit.record("discovery", item, state, reason)
        if state == "reject":
            continue
        relevant.append(item)

    log(f"── Saralash: {len(raw)} → {len(relevant)} ta imkoniyatga o'xshash yozuv")

    # 3-bosqich: allaqachon ko'rilgan maqolalar
    seen_sources = seen_source_keys([i["source_key"] for i in relevant],
                                   {i["source_key"]: i.get("title", "") for i in relevant})
    fresh = [i for i in relevant if i["source_key"] not in seen_sources
             or (i.get("kind") == "official" and i.get("fetch_details"))]
    log(f"── Yangi: {len(fresh)} ta ({len(relevant) - len(fresh)} tasi avval ko'rilgan)")

    return fresh


def resolve_links(items):
    """4-bosqich: asl havolalarni qazib olish."""
    # Round-robin across sources so one failing feed cannot fill the entire budget.
    from collections import defaultdict, deque
    queues = defaultdict(deque)
    for item in sorted(items, key=lambda g: (*discovery_priority(g), *candidate_quality(g)), reverse=True):
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

    RESOLVE_ISSUES.clear()
    def resolve_safely(grant):
        try:
            result = resolve_grant(dict(grant))
            if not isinstance(result, dict) or not isinstance(result.get("url", ""), str):
                raise TypeError("Havola natijasi yaroqsiz")
            return result
        except Exception as exc:
            RESOLVE_ISSUES.append(type(exc).__name__)
            log(f"   Bitta havola qayta tekshirishga qoldi: {type(exc).__name__}")
            return {**grant, "url": ""}
    with concurrent.futures.ThreadPoolExecutor(max_workers=RESOLVE_WORKERS) as ex:
        resolved = list(ex.map(resolve_safely, batch))

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
    seen_exact_urls = get_seen_urls([g["url"] for g in items]) if DB_READY else set()
    seen_fps = get_seen_fingerprint_scopes([g["fingerprint"] for g in items if g.get("fingerprint")]) if DB_READY else set()
    seen_slugs = get_seen_semantic_slugs([g["semantic_slug"] for g in items if g.get("semantic_slug")]) if DB_READY else set()
    prior_rows = posted_identity_rows(items) if DB_READY else []

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
            g.get("url") in seen_exact_urls or g.get("url_key") in seen_urls or g.get("canonical_url_key") in seen_urls
            or (g.get("fingerprint"), root_domain(host_of(g["url"]))) in seen_fps
            or g.get("semantic_slug") in seen_slugs
            for g in group)
        if in_database:
            for grant in group:
                incoming_year = cycle_hint(grant.get("title"))
                matches = [row for row in prior_rows if (
                    row.get("url") == grant["url"] or row.get("url_key") in {grant.get("url_key"), grant.get("canonical_url_key")}
                    or (row.get("semantic_slug") and row.get("semantic_slug") == grant.get("semantic_slug"))
                    or (row.get("fingerprint") and row.get("fingerprint") == grant.get("fingerprint")
                        and root_domain(host_of(row.get("url", ""))) == root_domain(host_of(grant["url"]))))]
                known_years = [cycle_hint(row.get("title")) for row in matches]
                known_years = [year for year in known_years if year]
                if incoming_year and matches and (not known_years or incoming_year > max(known_years)):
                    hold_for_review(grant, "new_intake_same_programme_needs_confirmation")
                    log(f"   Yangi qabul davri tekshiruvga qoldi: {grant.get('title', '')[:70]}")
                    grant["_cycle_review"] = True
            dropped_db += len(group)
            duplicates_to_save.extend({"grant": g, "status": "duplicate", "key": g.get("source_key")} for g in group if not g.get("_cycle_review"))
            continue
        winner = group[0]  # already ordered by evidence quality
        winner["_aliases"] = group[1:]
        unique.append(winner)
        dropped_batch += len(group) - 1

    if duplicates_to_save:
        save_grants_batch(duplicates_to_save)

    log(f"── Takrorlar tashlandi: bazada bor {dropped_db} ta, shu yurishda takror {dropped_batch} ta")
    log(f"── Post uchun qoldi: {len(unique)} ta")
    return sorted(unique, key=lambda g: (*discovery_priority(g), *candidate_quality(g)), reverse=True)


def enrich_deadlines(items):
    """Har bir grant uchun muddatni matndan chiqaramiz (AI dan oldin)."""
    for g in items:
        dt = extract_deadline(f"{g.get('title', '')}\n{g.get('summary', '')}")
        g["deadline_iso"] = dt.isoformat().replace("+00:00", "Z") if dt else None
    return items


def publish(items):
    """6-bosqich: AI matn yozadi va kanalga chiqaramiz."""
    PUBLISH_ISSUES.clear()
    if DB_READY and not DRY_RUN:
        resumed = delivery_journal.resume(CHANNEL_ID, "digest", publish_post)
        if resumed is not None:
            log("── Bugungi digest jurnali tiklandi yoki allaqachon yuborilgan.")
            return resumed
    if not items:
        log("── Post qilinadigan yangi imkoniyat yo'q.")
        return 0

    if len(items) > MAX_POST_PER_RUN:
        # Bular yo'qolmaydi: bazaga yozilmagani uchun keyingi yurishda yana keladi.
        log(f"── {len(items)} tadan {MAX_POST_PER_RUN} tasi tekshiriladi, "
            f"qolgan {len(items) - MAX_POST_PER_RUN} tasi keyingi yurishga qoladi.")
        items = items[:MAX_POST_PER_RUN]

    tokens = 0
    selected = []   # (card, grant): AI tanlagan, hali post qilinmagan
    rejected = []   # AI rad etgan — "skipped", ertaga qayta ishlanmaydi
    review_records = []
    failure = None

    # 1) AI barcha to'plamlarni ko'rib chiqadi. Post hali yuborilmaydi: aks holda
    # har to'plam (8 ta) o'z muqovasi bilan alohida, ko'pincha 1 grantli post bo'lardi.
    for number, batch in enumerate(editorial_batches(items), 1):
        if number > MAX_EDITORIAL_BATCHES:
            log("── Tahrir uchun so'rov chegarasi tugadi; qolgan nomzodlar keyingi yurishga qoldi.")
            break
        log(f"── {number}-to'plam: {len(batch)} ta imkoniyat AI ga yuborilmoqda...")

        content = generate_post_content(batch)

        # Bitta to'plamdagi nosozlik qolganlarini to'xtatmaydi: bu to'plam bazaga
        # yozilmay keyingi yurishga qoladi, xato esa oxirida adminga bildiriladi.
        if content is None:
            log("   AI javobi olinmadi — bu to'plam keyingi yurishga qoldi.")
            failure = RuntimeError("AI javobi olinmadi — grantlar keyingi yurishga qoldirildi")
            continue

        retry_later = set(content.get("unverified_urls") or ())
        rejected_urls = set(content.get("rejected_urls") or ())
        reviews = {r["grant"]["url"]: r for r in content.get("review", [])}
        review_records.extend(reviews.values())
        declared = {c.get("_source", {}).get("url") for c in content.get("cards", [])}
        retry_later.update(g["url"] for g in batch
                           if g["url"] not in declared | rejected_urls | set(reviews))
        for decision in content.get("decisions", []):
            source = next((g for g in batch if g["url"] == decision["url"]), {})
            selection_audit.record("editorial", source, decision["state"], decision["reason"])
        if not content.get("cards"):
            if retry_later:
                failure = RuntimeError("AI dalillari tasdiqlanmadi — grantlar qayta tekshirishga qoldi")
            log("   AI bu to'plamdan tasdiqlangan mos imkoniyat topmadi"
                + (f" ({len(retry_later)} tasi keyingi yurishda qayta ko'riladi)." if retry_later else "."))
            rejected += [{"grant": g, "deadline_iso": g.get("deadline_iso"), "status": "skipped"}
                         for g in batch if g["url"] in rejected_urls]
            continue

        usage = content.get("usage") or {}
        if usage:
            tokens += usage.get("total", 0)
            log(f"   {usage.get('model')} | {usage.get('total')} token")

        cards = usable_cards(content["cards"])
        if not cards:
            log("   AI kartochkalari yaroqsiz — bu to'plam keyingi yurishga qoldi.")
            failure = RuntimeError("AI kartochkalari yaroqsiz — grantlar saqlanmagan holda qoldirildi")
            continue

        chosen = {c["_source"]["url"]: c for c in cards if c.get("_source")}
        for g in batch:
            if g["url"] in chosen:
                selected.append((chosen[g["url"]], g))
            elif g["url"] in rejected_urls:
                rejected.append({"grant": g, "deadline_iso": g.get("deadline_iso"), "status": "skipped"})
        later = sum(g["url"] in retry_later for g in batch)
        log(f"   {len(chosen)} ta tanlandi, {len(rejected_urls)} tasi asosli rad etildi, {len(reviews)} tasi tahrir tekshiruviga qoldi"
            + (f", {later} tasi keyingi yurishda qayta ko'riladi." if later else "."))

    if rejected:
        save_grants_batch(rejected)
    if review_records:
        for record in review_records:
            hold_for_review(record["grant"], record["reason"])

    # 2) Exactly ONE message. Overflow stays retryable, never `skipped`.
    posted = 0
    if selected:
        selected.sort(key=lambda item: selection_priority(item[0]), reverse=True)
        chunk = selected[:MAX_DIGEST_CARDS]
        while chunk:
            cards = [card for card, _ in chunk]
            blocks, html = build_post(f"{len(cards)} ta yangi xalqaro imkoniyat", cards)
            if fits_single_message(blocks, html):
                break
            chunk = chunk[:-1]
        if not chunk:
            raise RuntimeError("Bitta kartochka ham xabar limitiga sig'madi; talablar kesilmadi")
        cards = [card for card, _ in chunk]
        # A mixed digest can contain partial awards. Do not let an AI headline
        # claim that every opportunity is fully funded or has one eligibility.
        blocks, html = build_post(f"{len(cards)} ta yangi xalqaro imkoniyat", cards)

        saves = []
        for card, g in chunk:
            # AI bergan sanani tekshiramiz — o'tib ketgan bo'lsa o'zimiznikiga qaytamiz
            deadline = validate_deadline_iso(card.get("deadline_iso")) or g.get("deadline_iso")
            saves.append({"grant": g, "deadline_iso": deadline, "status": "posted"})
            for alias in g.get("_aliases", []):
                saves.append({"grant": alias, "status": "duplicate", "key": alias.get("source_key")})
        if DB_READY and not DRY_RUN:
            posted = delivery_journal.deliver(
                CHANNEL_ID, "digest", blocks, html, saves, publish_post, len(chunk))
        else:
            if not publish_post(blocks, html):
                raise RuntimeError("Telegram xabari to'liq yuborilmadi — Actions logini tekshiring")
            save_grants_batch(saves)
            posted = len(chunk)
        if len(selected) > len(chunk):
            log(f"   {len(selected) - len(chunk)} ta tanlangan imkoniyat keyingi yurishga qoldi (bazaga rad etilmadi).")
        for _, grant in selected[len(chunk):]:
            selection_audit.record("publication", grant, "defer", "digest_limit")
        for _, grant in chunk:
            selection_audit.record("publication", grant, "prepared" if DRY_RUN else "posted", "ranked_verified_opportunity")
        action = "tayyorlandi (yuborilmadi)" if DRY_RUN else "post qilindi"
        log(f"   ✅ {len(chunk)} ta imkoniyat bitta postda {action}.")

    if tokens:
        log(f"── Jami sarflangan token: {tokens}")
    if failure:
        if not posted:
            raise failure
        PUBLISH_ISSUES.append(str(failure))
        log(f"── Qisman yakunlandi: {failure}. Tasdiqlangan digest tayyor, qolganlari qayta tekshiriladi.")
    return posted


def editorial_batches(items):
    """Keep larger official evidence inside a bounded per-request token budget."""
    batch, size = [], 0
    for grant in items:
        cost = len(str(grant.get("summary") or "")) + len(str(grant.get("title") or ""))
        # Full screening plus quotes exceeds the free-tier output budget for
        # several cards. One official programme per call was verified live.
        limit = 1 if grant.get("official_evidence_url") or any(g.get("official_evidence_url") for g in batch) else BATCH_SIZE
        if batch and (len(batch) >= limit or size + cost > 12000):
            yield batch
            batch, size = [], 0
        batch.append(grant)
        size += cost
    if batch:
        yield batch


def revalidate_reminders(grants):
    """Legacy posted rows must satisfy the same current policy as new posts."""
    evidence = verify_official_pages(grants)
    ready = []
    for item in evidence:
        selection_audit.record("reminder_evidence", item.grant, item.status, item.reason)
        if item.status == "ready":
            ready.append(item.grant)
        elif item.status in {"ineligible", "review"}:
            if item.status == "review":
                hold_for_review(item.grant, item.reason)
            mark_reminder_sent(item.grant["url"])
        else:
            REMINDER_ISSUES.append("Bitta eslatmaning rasmiy sahifasi vaqtincha o'qilmadi")
    selected = []
    for batch in editorial_batches(enrich_deadlines(ready)):
        content = generate_post_content(batch)
        if content is None:
            REMINDER_ISSUES.append("Eslatma saralashi uchun AI javobi olinmadi")
            continue
        for item in content.get("review", []):
            hold_for_review(item["grant"], item["reason"])
        for card in usable_cards(content.get("cards")):
            date = validate_deadline_iso(card.get("deadline_iso"))
            if not date:
                REMINDER_ISSUES.append("Eslatmaning yangi muddati tasdiqlanmadi")
                continue
            remaining = datetime.fromisoformat(date.replace("Z", "+00:00")) - datetime.now(timezone.utc)
            if not timedelta(0) < remaining <= timedelta(days=5):
                continue
            selected.append({**card["_source"], "title": card["name"], "deadline": date})
        for url in content.get("rejected_urls", []):
            mark_reminder_sent(url)
        if content.get("unverified_urls"):
            REMINDER_ISSUES.append("Tasdiqlanmagan eslatmalar keyingi tekshiruvga qoldi")
    return selected


def run():
    problems = []                # yurish oxirida adminga yuboriladi
    REVIEW_ISSUES.clear()
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
        problems.extend(REMINDER_ISSUES)
    log()

    if DB_READY and not DRY_RUN:
        resumed = delivery_journal.resume(CHANNEL_ID, "digest", publish_post)
        if resumed is not None:
            log(f"Yakunlandi: {resumed} ta imkoniyat. Bugungi digest jurnali yopilgan.")
            return

    candidates = collect_candidates()
    if SOURCE_ISSUES:
        problems.append(f"{len(SOURCE_ISSUES)} ta manba vaqtincha o'qilmadi; qolganlari ishlatildi")
    if not candidates:
        log("\nYangi imkoniyat yo'q.")

    resolved = resolve_links(candidates)
    if RESOLVE_ISSUES:
        problems.append(f"{len(RESOLVE_ISSUES)} ta havola xatosi ajratildi va keyingi yurishga qoldi")
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
    evidence = verify_official_pages(unique[:MAX_POST_PER_RUN])
    for item in evidence:
        selection_audit.record("official", item.grant, item.status, item.reason or "official_evidence_read")
    ready = [item.grant for item in evidence if item.status == "ready"]
    rejected = [item.grant for item in evidence if item.status == "ineligible"]
    policy_reviews = [item for item in evidence if item.status == "review"]
    deferred = [item for item in evidence if item.status == "retry"]
    if rejected:
        save_grants_batch([{"grant": g, "status": "skipped"} for g in rejected])
    if policy_reviews:
        for item in policy_reviews:
            hold_for_review(item.grant, item.reason)
        problems.append(f"{len(policy_reviews)} ta pullik xususiy forum avtomatik nashrdan olib qolindi")
    if deferred:
        problems.append(f"{len(deferred)} ta dastur uchun rasmiy dalil olinmadi; qayta tekshirishga qoldi")
        for item in deferred:
            log(f"   Rasmiy tekshiruv: {item.reason} — {item.grant.get('title', '')[:65]}")
    log(f"── Rasmiy tekshiruv: {len(ready)} tayyor, {len(rejected)} mos emas, {len(deferred)} qayta uriniladi")
    if deferred and not ready and not (rejected or policy_reviews):
        raise RuntimeError("Rasmiy sahifalardan yetarli dalil olinmadi; tasdiqlanmagan grant chiqarilmadi")
    posted = publish(enrich_deadlines(ready))
    problems.extend(PUBLISH_ISSUES)
    if REVIEW_ISSUES:
        problems.append(f"{len(set(REVIEW_ISSUES))} ta saralash qarori tekshiruv navbatida; sabablar saralash hisobotida saqlandi")
    if ready and not posted:
        problems.append(f"{len(ready)} ta nomzod bor edi, lekin hech biri post qilinmadi")

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
            if db_stat.get("review"):
                lines.append(f"Tekshiruv navbatida: {db_stat['review']} ta")
        lines.append(f"📅 <b>Yurish vaqti:</b> {started.strftime('%Y-%m-%d %H:%M')} UTC")
        notify_admin("\n".join(lines))



def run_with_recovery():
    """Restart only a known transient DB failure; Telegram uncertainty is final."""
    selection_audit.reset()
    for attempt in range(3):
        try:
            return run()
        except (DeliveryUncertain, delivery_journal.UncertainDelivery):
            raise
        except Exception as exc:
            if attempt == 2 or not transient_error(exc):
                raise
            delay = (5, 15)[attempt]
            log(f"Baza vaqtincha uzildi; jurnal orqali {delay}s dan keyin xavfsiz tiklash.")
            time.sleep(delay)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        run_with_recovery()
    except Exception as exc:
        if not DRY_RUN and os.getenv("NOVA_WORKFLOW_ALERT") != "1":
            notify_admin(f"⚠️ <b>Nova Grants: yurish yakunlanmadi</b>\nXato turi: {type(exc).__name__}. "
                         "GitHub Actions logini va yuborish jurnalini tekshiring; "
                         "yetkazilgani tasdiqlangan post qayta yuborilmaydi.")
        raise
    finally:
        selection_audit.write_report()
