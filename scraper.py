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
import concurrent.futures

import feedparser
import requests
from bs4 import BeautifulSoup

from sources import enabled_sources
from link_resolver import clean_url, url_key, is_blocked, is_aggregator, host_of

TIMEOUT = 25
MAX_PER_SOURCE = 20          # bitta manbadan ko'pi bilan shuncha yangi yozuv
SUMMARY_LIMIT = 1500

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/html;q=0.9, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_session = requests.Session()
_session.headers.update(HEADERS)


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
def scrape_rss(src):
    out = []
    try:
        resp = _session.get(src["url"], timeout=TIMEOUT)
        if resp.status_code != 200:
            print(f"  [{src['id']}] HTTP {resp.status_code}")
            return out
        feed = feedparser.parse(resp.content)
    except Exception as e:
        print(f"  [{src['id']}] xatolik: {type(e).__name__}")
        return out

    if not feed.entries:
        print(f"  [{src['id']}] feed bo'sh")
        return out

    for entry in feed.entries[:MAX_PER_SOURCE]:
        link = clean_url(entry.get("link", ""))
        if not link:
            continue
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

    print(f"  [{src['id']}] {len(out)} ta yozuv")
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
def scrape_telegram(src):
    ch = src["channel"]
    out = []
    try:
        resp = _session.get(f"https://t.me/s/{ch}", timeout=TIMEOUT)
        if resp.status_code != 200:
            print(f"  [{src['id']}] HTTP {resp.status_code}")
            return out
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        print(f"  [{src['id']}] xatolik: {type(e).__name__}")
        return out

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

    print(f"  [{src['id']}] {len(out)} ta post")
    return out


# ──────────────────────────────────────────────────────────────────────
# grants.gov rasmiy API
# ──────────────────────────────────────────────────────────────────────
def scrape_grantsgov(src):
    out = []
    try:
        resp = _session.post(
            src["url"],
            json={"rows": 50, "keyword": "", "oppStatuses": "posted"},
            headers={"Content-Type": "application/json"},
            timeout=TIMEOUT,
        )
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
