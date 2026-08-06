"""Manbalardan xom ma'lumot yig'ish.

Bu modul FAQAT ma'lumot yig'adi va dastlabki tozalashni bajaradi.
Asl havolani topish — link_resolver.py, saralash — filters.py ishi.

Har bir yozuv quyidagi ko'rinishda qaytadi:
    {
      "source_id": "opportunitydesk",
      "kind":      "aggregator",   # yoki "official"
      "title":     "...",
      "url":       "https://opportunitydesk.org/2026/...",   # manba havolasi
      "direct_url": "https://official-site.org/apply",       # Telegram postidagi tashqi havola (ixtiyoriy)
      "summary":   "...",
    }
"""

import re
import time
import concurrent.futures
from datetime import datetime, timezone, timedelta

import feedparser
from bs4 import BeautifulSoup

import http_client
from sources import enabled_sources
from link_resolver import clean_url, url_key, is_blocked, is_aggregator, host_of

TIMEOUT = 25
MAX_PER_SOURCE = 60          # bitta manbadan ko'pi bilan shuncha yangi yozuv
SUMMARY_LIMIT = 1500
MAX_RETRY = 2                # 429 / vaqtinchalik xatolarda qayta urinish

# ── YANGILIK CHEGARASI ────────────────────────────────────────────────────
# Ilgari na RSS, na Telegram uchun sana tekshirilmasdi. Natijada 2021-yilda
# to'xtab qolgan kanallar 5 yillik postlarini "yangi imkoniyat" sifatida
# quvurga tiqib turardi (jonli auditda tasdiqlandi). Sanasi noma'lum yozuv
# o'tkaziladi — ko'p feed'da sana bo'lmaydi va uni tashlash zarar keltiradi.
MAX_AGE_DAYS = 60

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/html;q=0.9, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Brauzer TLS izi bilan ishlaydigan mijoz. Bir qancha sayt oddiy `requests`
# ga umuman javob bermaydi (chevening.org, britishcouncil.org,
# opportunitiesforyouth.org) — sabab cookie emas, TLS barmoq izi.
# Batafsil: http_client.py boshidagi izoh.
_session = http_client.Client(HEADERS)


def _clean_html(raw: str) -> str:
    """HTML teglarni olib tashlab, toza matn qaytaradi."""
    if not raw:
        return ""
    try:
        text = BeautifulSoup(raw, "html.parser").get_text(separator="\n")
    except Exception:
        text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


# ──────────────────────────────────────────────────────────────────────
# RSS
# ──────────────────────────────────────────────────────────────────────
def _entry_age_days(entry):
    """Yozuv necha kunlik. Sana yo'q bo'lsa None."""
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            try:
                dt = datetime(*t[:6], tzinfo=timezone.utc)
                return (datetime.now(timezone.utc) - dt).days
            except Exception:
                continue
    return None


def _fetch_feed(url, source_id):
    """Feed'ni oladi. 429 va vaqtinchalik xatolarda qayta uriniladi."""
    for attempt in range(MAX_RETRY + 1):
        resp = _session.get(url, timeout=TIMEOUT)

        if resp is None:                          # ulanib bo'lmadi
            if attempt < MAX_RETRY:
                time.sleep(3 * (attempt + 1))
                continue
            print(f"  [{source_id}] ulanib bo'lmadi")
            return None

        if resp.status_code == 200:
            return feedparser.parse(resp.content)

        # 429/503 — sayt bizni sekinlashtirmoqchi, biroz kutamiz
        if resp.status_code in (429, 503) and attempt < MAX_RETRY:
            retry_after = resp.headers.get("Retry-After", "")
            delay = float(retry_after) if retry_after.isdigit() else 5.0 * (attempt + 1)
            time.sleep(min(delay, 20))
            continue

        print(f"  [{source_id}] HTTP {resp.status_code}")
        return None
    return None


def scrape_rss(src):
    out = []
    seen_links = set()
    stale = 0

    # WordPress feed'lari sahifada 10 ta beradi; ?paged=N yana 10 tadan
    # NOYOB yozuv qaytaradi (jonli o'lchandi). Shu bilan ishonchli manbadan
    # yangi manba qidirmasdan 3 barobar ko'proq qamrov olamiz.
    pages = max(1, int(src.get("pages", 1)))

    for page in range(1, pages + 1):
        if page == 1:
            url = src["url"]
        else:
            sep = "&" if "?" in src["url"] else "?"
            url = f"{src['url']}{sep}paged={page}"
        feed = _fetch_feed(url, src["id"])
        if feed is None:
            break
        if not feed.entries:
            if page == 1:
                print(f"  [{src['id']}] feed bo'sh")
            break

        for entry in feed.entries:
            if len(out) >= MAX_PER_SOURCE:
                break
            link = clean_url(entry.get("link", ""))
            if not link or link in seen_links:
                continue

            age = _entry_age_days(entry)
            if age is not None and age > MAX_AGE_DAYS:
                stale += 1
                continue

            seen_links.add(link)
            summary = entry.get("summary") or entry.get("description") or ""
            # to'liq matn bo'lsa (content:encoded) — undan foydalanamiz, deadline shu yerda bo'ladi
            if entry.get("content"):
                try:
                    summary = entry["content"][0].get("value", summary)
                except Exception:
                    pass
            out.append({
                "source_id": src["id"],
                "kind": src["kind"],
                "topic": src.get("topic", ""),
                "title": _clean_html(entry.get("title", "")).strip(),
                "url": link,
                "summary": _clean_html(summary)[:SUMMARY_LIMIT],
            })

        if len(out) >= MAX_PER_SOURCE:
            break

    note = f" ({stale} tasi eskirgan)" if stale else ""
    if out or stale:
        print(f"  [{src['id']}] {len(out)} ta yozuv{note}")
    return out


# ──────────────────────────────────────────────────────────────────────
# Telegram (ochiq web preview: t.me/s/<kanal>)
# ──────────────────────────────────────────────────────────────────────
# Emoji, ko'rinmas belgilar va bezak chiziqlari — sarlavha boshidan tozalanadi
_DECOR = re.compile(
    r"^[\s​-‏⁠﻿ "
    r"\U0001F000-\U0001FAFF←-⯿☀-➿️⃣•▪▫◾◽●○*_\-—–=~#>»›|]+"
)


def _telegram_title(text: str) -> str:
    """Post matnidan mazmunli sarlavha ajratadi.

    Telegram postlari ko'pincha emoji bilan boshlanadi ("💡", "🎓 ---") — oddiy
    "birinchi qator" qoidasi bunday hollarda BO'SH sarlavha beradi va yozuv
    keyinchalik filtrda tushib qoladi. Shuning uchun mazmunli birinchi qatorni
    qidiramiz.
    """
    for raw in text.split("\n"):
        line = _DECOR.sub("", raw).strip()
        line = re.sub(r"\s+", " ", line)
        if len(re.findall(r"\w", line)) >= 12:        # mazmunli qator
            if len(line) > 110:
                line = line[:107].rsplit(" ", 1)[0] + "..."
            return line

    # Mazmunli qator topilmadi — butun matndan boshini olamiz
    flat = re.sub(r"\s+", " ", _DECOR.sub("", text)).strip()
    return (flat[:107].rsplit(" ", 1)[0] + "...") if len(flat) > 110 else (flat or "Imkoniyat")


def _post_age_days(wrap):
    """Telegram postining yoshi (kunlarda). Sana topilmasa None."""
    tag = wrap.find("time", attrs={"datetime": True})
    if not tag:
        return None
    try:
        dt = datetime.fromisoformat(tag["datetime"].replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).days
    except Exception:
        return None


def scrape_telegram(src):
    ch = src["channel"]
    out = []
    resp = _session.get(f"https://t.me/s/{ch}", timeout=TIMEOUT)
    if resp is None:
        print(f"  [{src['id']}] ulanib bo'lmadi")
        return out
    if resp.status_code != 200:
        print(f"  [{src['id']}] HTTP {resp.status_code}")
        return out
    try:
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"  [{src['id']}] xatolik: {type(e).__name__}")
        return out

    stale = 0
    wrappers = soup.find_all("div", class_="tgme_widget_message")
    for wrap in wrappers[-MAX_PER_SOURCE:]:
        body = wrap.find("div", class_="tgme_widget_message_text")
        if not body:
            continue
        text = body.get_text(separator="\n", strip=True)
        if len(text) < 60:                       # juda qisqa post — foydasiz
            continue

        date_tag = wrap.find("a", class_="tgme_widget_message_date")
        post_link = date_tag.get("href") if date_tag else f"https://t.me/{ch}"

        # Post sanasi. Kanal to'xtab qolgan bo'lsa (masalan 2021-yilda),
        # eski postlar "yangi imkoniyat" bo'lib o'tib ketmasligi kerak.
        age = _post_age_days(wrap)
        if age is not None and age > MAX_AGE_DAYS:
            stale += 1
            continue

        # Post ichidagi TASHQI havola — aynan shu grantning asl manzili bo'lishi mumkin
        direct = ""
        for a in body.find_all("a", href=True):
            href = a["href"].strip()
            if not href.lower().startswith("http"):
                continue
            if is_blocked(href) or is_aggregator(href):
                continue
            if host_of(href) in ("t.me", "telegram.me"):
                continue
            direct = clean_url(href)
            if direct:
                break

        title = _telegram_title(text)

        out.append({
            "source_id": src["id"],
            "kind": src["kind"],
            "topic": src.get("topic", ""),
            "title": title,
            "url": post_link,
            "direct_url": direct,
            "summary": text[:SUMMARY_LIMIT],
        })

    note = f" ({stale} tasi eskirgan)" if stale else ""
    print(f"  [{src['id']}] {len(out)} ta post{note}")
    return out


# ──────────────────────────────────────────────────────────────────────
# grants.gov rasmiy API
# ──────────────────────────────────────────────────────────────────────
def scrape_grantsgov(src):
    out = []
    resp = _session.post(
        src["url"],
        json={"rows": 50, "keyword": "", "oppStatuses": "posted"},
        headers={"Content-Type": "application/json"},
        timeout=TIMEOUT,
    )
    if resp is None:
        print(f"  [{src['id']}] ulanib bo'lmadi")
        return out
    try:
        hits = resp.json().get("data", {}).get("oppHits", [])
    except Exception as e:
        print(f"  [{src['id']}] xatolik: {type(e).__name__}")
        return out

    for h in hits:
        opp_id = h.get("id")
        if not opp_id:
            continue
        close = h.get("closeDate", "")
        out.append({
            "source_id": src["id"],
            "kind": src["kind"],
            "topic": src.get("topic", ""),
            "title": h.get("title", "").strip(),
            "url": f"https://grants.gov/search-results-detail/{opp_id}",
            "summary": f"{h.get('agencyName', '')}. Opportunity number: {h.get('number', '')}. "
                       f"Deadline: {close}." if close else h.get("agencyName", ""),
        })

    print(f"  [{src['id']}] {len(out)} ta imkoniyat")
    return out


_ADAPTERS = {
    "rss": scrape_rss,
    "telegram": scrape_telegram,
    "grantsgov": scrape_grantsgov,
}


def _fetch_one(src):
    fn = _ADAPTERS.get(src["type"])
    if not fn:
        return []
    try:
        return fn(src)
    except Exception as e:
        print(f"  [{src['id']}] kutilmagan xatolik: {type(e).__name__}: {e}")
        return []


def fetch_all():
    """Barcha faol manbalardan yig'ib, manba havolasi bo'yicha takrorlarni tashlaydi."""
    srcs = enabled_sources()
    print(f"Ma'lumot yig'ilmoqda — {len(srcs)} ta manba...")

    collected = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        for batch in ex.map(_fetch_one, srcs):
            collected.extend(batch)

    # Bir yurish ichidagi takrorlar (bir maqola ikki feed'da chiqishi mumkin)
    seen = set()
    unique = []
    for item in collected:
        key = url_key(item["url"])
        if not key or key in seen:
            continue
        seen.add(key)
        item["source_key"] = key
        unique.append(item)

    print(f"Jami: {len(collected)} ta yozuv, takrorlar tozalangach: {len(unique)} ta")
    return unique


if __name__ == "__main__":
    import sys
    from collections import Counter
    sys.stdout.reconfigure(encoding="utf-8")

    items = fetch_all()
    print("\nManbalar bo'yicha:")
    for sid, n in Counter(i["source_id"] for i in items).most_common():
        print(f"  {sid:<24} {n}")
    if items:
        print("\nNamuna:")
        for it in items[:3]:
            print(f"  [{it['source_id']}] {it['title'][:70]}")
            print(f"     {it['url']}")
