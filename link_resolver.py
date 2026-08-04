"""Grantning ASL (original) havolasini topish va URL larni bir xil ko'rinishga keltirish.

Muammo: RSS feed'dagi `entry.link` — bu aggregator saytining reklamaga to'la maqolasi
(masalan opportunitydesk.org/2026/...), grantning rasmiy sahifasi emas. Bir grant 8 ta
aggregatorda chiqsa, 8 xil URL paydo bo'ladi va kanalga 8 marta tushadi.

Bu modul aggregator maqolasini ochib, ichidan rasmiy "Apply / Official website"
havolasini topadi. Shu tufayli:
  1. Kanalga faqat grantning o'z sayti tushadi (reklama emas).
  2. 8 ta aggregator ham bitta rasmiy URL ga tushadi — takror post o'z-o'zidan yo'qoladi.

Aggregator boshqa aggregatorga ulasa (masalan edugrants.uz -> universitet sayti),
MAX_HOPS gacha qazishda davom etadi.
"""

import re
import time
import hashlib
import threading
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode, urljoin

import requests
from bs4 import BeautifulSoup

TIMEOUT = 15
MAX_HOPS = 2                 # aggregator -> aggregator -> rasmiy sayt
MIN_HOST_INTERVAL = 3.0      # bitta domenga so'rovlar orasidagi minimal tanaffus (sekund)
MAX_RETRY_429 = 2
COOLDOWN_429 = 120           # 429 bergan domen shuncha soniya butunlay chetlab o'tiladi

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# Aggregator saytlar: bularning maqolasi grantning o'zi emas, "qayta hikoya".
# Bularning havolasi POSTGA TUSHMASLIGI kerak — ichidan rasmiy link qidiriladi.
AGGREGATORS = {
    "scholars4dev.com", "opportunitydesk.org", "youthop.com", "opportunitiescorners.com",
    "scholarshiproar.com", "wemakescholars.com", "scholarshipdb.net", "scholarship-positions.com",
    "advance-africa.com", "oyaop.com", "opportunitiesforyouth.org", "opportunitiesforafricans.com",
    "afterschoolafrica.com", "opportunitiescircle.com", "heysuccess.com", "profellow.com",
    "armacad.info", "mladiinfo.eu", "philanthropywomen.org", "terravivagrants.org",
    "fundsforngos.org", "grantlar.uz", "scholarshipscorner.website", "opportunitiesforafrica.org",
    "youthopportunitieshub.com", "scholarshipair.com", "opportunitiesbank.org",
    "scholarshipregion.com", "fellowshipbard.com", "scholarshipunion.com", "freeeducator.com",
    "scholarshipfellow.com", "opportunitydesk.info", "youthopportunities.info",
    # O'zbek aggregatorlari — bular ham "qayta hikoya" qiladi
    "edugrants.uz", "grantss.uz", "stipendiya.uz", "grantlar.info",
}

# Hech qachon "asl havola" bo'la olmaydi: ijtimoiy tarmoq, reklama, share tugmalari.
BLOCKED_HOSTS = {
    "facebook.com", "fb.com", "twitter.com", "x.com", "linkedin.com", "instagram.com",
    "pinterest.com", "whatsapp.com", "wa.me", "t.me", "telegram.me", "telegram.org",
    "reddit.com", "tumblr.com", "vk.com", "threads.net", "youtube.com", "youtu.be",
    "addtoany.com", "sharethis.com", "addthis.com", "doubleclick.net", "googleadservices.com",
    "googlesyndication.com", "google-analytics.com", "amazon.com", "amzn.to", "aliexpress.com",
    "gravatar.com", "wordpress.com", "wp.com", "jetpack.com", "feedburner.com", "paypal.com",
    "patreon.com", "buymeacoffee.com", "play.google.com", "apps.apple.com", "mailchimp.com",
    "sendinblue.com", "disqus.com", "gstatic.com", "googletagmanager.com", "bit.ly",
    "tinyurl.com", "linktr.ee", "docs.google.com", "forms.gle",
}

# Aggregatorning ichki "o'tish" havolalari (/go/123) — ochib, oxirgi manzilni olamiz.
REDIRECT_PATH = re.compile(r"/(go|out|goto|link|links|redirect|visit|away|click|track)(/|\?|$)", re.I)

TRACKING_EXACT = {
    "fbclid", "gclid", "gbraid", "wbraid", "igshid", "mibextid", "yclid", "msclkid", "twclid",
    "ref", "ref_src", "referrer", "source", "src", "campaign", "campaign_id", "cmpid",
    "amp", "feature", "spm", "_ga", "_gl", "mc_cid", "mc_eid", "vero_id", "trk",
    "sfmc_id", "rss", "utm", "guccounter", "share", "fromrss", "s", "fbrefresh",
}
TRACKING_PREFIX = ("utm_", "pk_", "mtm_", "piwik_", "hsa_", "at_", "ic_", "oly_")

APPLY_STRONG = re.compile(
    # inglizcha
    r"(official\s+(web\s*)?(site|website|link|page|announcement|call)"
    r"|apply\s*(now|here|online|via|through)?|application\s+(link|portal|form|page|website)"
    r"|submit\s+(your\s+)?(application|entry)|start\s+your\s+application|scholarship\s+link"
    r"|registration\s+(link|form|page)|register\s+(now|here)"
    # o'zbekcha — "Rasmiy veb-sayt", "rasmiy sahifa", "saytga o'tish"
    r"|rasmiy[\s\-]*(veb[\s\-]*)?(sayt|manba|sahifa|havola)"
    r"|ariza\s+topshir|hujjat\s+topshir|saytga\s+o'tish|ro'yxatdan\s+o'tish"
    # ruscha
    r"|официальн\w*\s+(сайт|страниц|ссылк)|подать\s+заявк|перейти\s+на\s+сайт"
    r")",
    re.I,
)
APPLY_WEAK = re.compile(
    r"(more\s+(information|details|info)|further\s+(information|details)|for\s+(more\s+)?details"
    r"|visit\s+the|see\s+(here|the)|read\s+more|check\s+here|learn\s+more|find\s+out\s+more"
    r"|batafsil|to'liq\s+ma|havola|manba|подробнее|источник)",
    re.I,
)
GOOD_PATH = re.compile(
    r"(scholarship|grant|fellowship|apply|application|admission|call|funding|bursary"
    r"|award|competition|programme|program|opportunit|vacanc|intake|admissions"
    r"|submit|register|registration|portal|form|contest|challenge|fund)",
    re.I,
)
GOOD_TLD = (".edu", ".ac.uk", ".gov", ".edu.au", ".ac.jp", ".int", ".eu", ".org", ".uz")

_session = requests.Session()
_session.headers.update(HEADERS)

# ── Domen bo'yicha tezlikni cheklash (429 "Too Many Requests" oldini oladi) ──
_host_locks = {}
_host_last = {}
_host_blocked_until = {}     # 429 bergan domenlar shu vaqtgacha chetlab o'tiladi
_guard = threading.Lock()


def _throttle(host: str):
    """Bitta domenga so'rovlar orasida majburiy tanaffus."""
    with _guard:
        lock = _host_locks.setdefault(host, threading.Lock())
    with lock:
        wait = MIN_HOST_INTERVAL - (time.monotonic() - _host_last.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        _host_last[host] = time.monotonic()


def _get(url: str, allow_redirects=True, stream=False):
    """Xushmuomala GET: domen bo'yicha tanaffus, 429 da qayta urinish va sovutish."""
    host = host_of(url)

    with _guard:
        until = _host_blocked_until.get(host, 0.0)
    if time.monotonic() < until:
        return None                              # bu domen hozircha bizni qabul qilmayapti

    for attempt in range(MAX_RETRY_429 + 1):
        _throttle(host)
        try:
            r = _session.get(url, timeout=TIMEOUT, allow_redirects=allow_redirects, stream=stream)
        except Exception:
            return None

        if r.status_code == 429:
            if attempt < MAX_RETRY_429:
                retry_after = r.headers.get("Retry-After", "")
                delay = float(retry_after) if retry_after.isdigit() else 5.0 * (attempt + 1)
                time.sleep(min(delay, 20))
                continue
            # Uch marta 429 — bu domenni bir muddat tinch qo'yamiz
            with _guard:
                _host_blocked_until[host] = time.monotonic() + COOLDOWN_429
            print(f"    ! {host} so'rovlarni cheklayapti (429) — {COOLDOWN_429}s chetlab o'tiladi")
        return r
    return None


def host_of(url: str) -> str:
    """URL dan domenni oladi (www. siz, kichik harflarda)."""
    try:
        h = (urlparse(url).hostname or "").lower()
        return h[4:] if h.startswith("www.") else h
    except Exception:
        return ""


def _host_in(host: str, group: set) -> bool:
    """Domen yoki uning subdomeni ro'yxatda bormi (mail.google.com -> google.com)."""
    if not host:
        return False
    parts = host.split(".")
    for i in range(len(parts) - 1):
        if ".".join(parts[i:]) in group:
            return True
    return False


def is_aggregator(url: str) -> bool:
    return _host_in(host_of(url), AGGREGATORS)


def is_blocked(url: str) -> bool:
    return _host_in(host_of(url), BLOCKED_HOSTS)


def clean_url(url: str) -> str:
    """Ko'rsatish uchun toza URL: tracking parametrlari va #fragment olib tashlanadi."""
    if not url:
        return ""
    try:
        p = urlparse(url.strip())
        if p.scheme not in ("http", "https"):
            return ""
        keep = [
            (k, v) for k, v in parse_qsl(p.query, keep_blank_values=False)
            if k.lower() not in TRACKING_EXACT and not k.lower().startswith(TRACKING_PREFIX)
        ]
        return urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode(keep), ""))
    except Exception:
        return ""


def url_key(url: str) -> str:
    """Dedup uchun qat'iy kalit: sxema, www, oxirgi '/' va tracking hisobga olinmaydi.

    http://www.Example.com/Grant/?utm_source=rss  ->  example.com/grant
    """
    if not url:
        return ""
    try:
        p = urlparse(clean_url(url) or url)
        host = host_of(url)
        path = (p.path or "/").rstrip("/").lower() or "/"
        path = re.sub(r"/(index|default)\.(html?|php|aspx?)$", "", path)
        query = urlencode(sorted(parse_qsl(p.query, keep_blank_values=False)))
        return f"{host}{path}" + (f"?{query}" if query else "")
    except Exception:
        return url.lower()


_STOPWORDS = {
    "the", "a", "an", "of", "for", "in", "at", "on", "to", "and", "or", "with", "by", "from",
    "is", "are", "be", "your", "you", "all", "new", "apply", "applications", "application",
    "open", "now", "call", "scholarship", "scholarships", "grant", "grants", "fellowship",
    "fellowships", "program", "programme", "programs", "fully", "funded", "full", "free",
    "international", "students", "student", "study", "abroad", "opportunity", "opportunities",
    "deadline", "award", "awards", "uchun", "grantlar", "dastur", "talabalar", "stipendiya",
}
_YEAR = re.compile(r"\b(19|20)\d{2}(/(19|20)?\d{2})?\b")


def title_fingerprint(title: str) -> str:
    """Sarlavhadan barmoq izi — turli aggregator turlicha yozsa ham bir xil chiqadi.

    "Chevening Scholarship 2026 (Fully Funded)" va "Fully Funded Chevening Scholarships UK"
    ikkalasi ham bir xil izga tushadi.
    """
    if not title:
        return ""
    t = title.lower()
    t = re.sub(r"^\[[^\]]{1,40}\]\s*", "", t)
    t = _YEAR.sub(" ", t)
    t = re.sub(r"[^a-z0-9\s']", " ", t)
    tokens = {w for w in t.split() if len(w) > 2 and w not in _STOPWORDS}
    if len(tokens) < 2:
        return ""                                # juda umumiy sarlavha — izga ishonmaymiz
    return hashlib.sha1(" ".join(sorted(tokens)[:12]).encode("utf-8")).hexdigest()[:20]


def follow_redirects(url: str) -> str:
    """Qisqartirilgan/o'tkazuvchi havolani oxirgi haqiqiy manzilgacha ochadi."""
    r = _get(url, allow_redirects=True, stream=True)
    if r is None:
        return url
    final = r.url
    try:
        r.close()
    except Exception:
        pass
    return final or url


def _score_candidate(anchor_text: str, href: str, position: float) -> int:
    """Havola qanchalik "rasmiy ariza sahifasi" ekanini baholaydi."""
    score = 0
    text = (anchor_text or "").strip()
    path = urlparse(href).path or ""

    if APPLY_STRONG.search(text):
        score += 30
    elif APPLY_WEAK.search(text):
        score += 10

    if GOOD_PATH.search(path):
        score += 8

    host = host_of(href)
    if host.endswith(GOOD_TLD):
        score += 6
    if host.count(".") <= 1:
        score += 2

    score += int(position * 8)                   # rasmiy havola odatda oxirroqda

    if path.lower().endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx")):
        score -= 12                              # hujjat — ariza sahifasi emas
    if len(text) > 120:
        score -= 5
    if not text:
        score -= 8
    return score


def _article_root(soup: BeautifulSoup):
    """Maqola tanasini topadi — sidebar'dagi reklamalarni chetlab o'tish uchun."""
    for sel in ("article", "div.entry-content", "div.post-content", "div.td-post-content",
                "div.single-content", "div.content-area", "div.elementor-widget-theme-post-content",
                "main"):
        node = soup.select_one(sel)
        if node and len(node.get_text(strip=True)) > 200:
            return node
    return soup.body or soup


def find_original_link(article_url: str) -> str:
    """Aggregator maqolasidan grantning rasmiy havolasini topadi. Topilmasa ""."""
    resp = _get(article_url)
    if resp is None or resp.status_code != 200:
        code = resp.status_code if resp is not None else "ulanmadi"
        print(f"    ! {host_of(article_url)} javob bermadi ({code})")
        return ""

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception:
        return ""

    root = _article_root(soup)
    anchors = root.find_all("a", href=True)
    if not anchors:
        return ""

    source_host = host_of(article_url)
    external, internal_redirects = [], []

    for i, a in enumerate(anchors):
        try:
            href = urljoin(article_url, a["href"].strip())
        except Exception:
            continue
        if not href.lower().startswith(("http://", "https://")):
            continue
        if is_blocked(href):
            continue

        host = host_of(href)
        position = i / max(len(anchors) - 1, 1)
        text = a.get_text(" ", strip=True)
        score = _score_candidate(text, href, position)

        if host == source_host:
            if REDIRECT_PATH.search(urlparse(href).path or ""):
                internal_redirects.append((score, href))
            continue

        external.append((score, href))

    for pool in (external, internal_redirects):
        if not pool:
            continue
        pool.sort(key=lambda x: x[0], reverse=True)

        # Agar maqolada umuman bitta tashqi havola bo'lsa — bu deyarli aniq o'sha grant.
        # Bunday holatda past bahoga ham ishonamiz.
        threshold = 4 if len(pool) == 1 else 10

        for score, href in pool[:3]:
            if score < threshold:                # ishonch past — reklama bo'lishi mumkin
                break
            final = follow_redirects(href)
            if is_blocked(final):
                continue
            if host_of(final) == source_host:
                continue
            return clean_url(final)

    return ""


def resolve_grant(grant: dict) -> dict:
    """Bitta yozuv uchun asl havolani aniqlaydi.

    Qo'shadi: `url` (asl havola), `source_url`, `url_key`, `fingerprint`.
    Asl havola topilmasa `url` bo'sh qoladi — chaqiruvchi uni tashlab yuborishi kerak.
    """
    source_url = clean_url(grant.get("url", ""))
    grant["source_url"] = source_url
    grant["fingerprint"] = title_fingerprint(grant.get("title", ""))
    grant["url"] = ""
    grant["url_key"] = ""

    if not source_url:
        return grant

    from_telegram = str(grant.get("source_id", "")).startswith("tg:") or \
        host_of(source_url) in ("t.me", "telegram.me")

    # Boshlang'ich nuqta: Telegram bo'lsa — post ichidagi tashqi havola,
    # aks holda manbaning o'z havolasi.
    if from_telegram:
        start = grant.get("direct_url") or ""
        if not start:
            return grant                          # postda tashqi havola yo'q — foydasiz
        start = follow_redirects(start)
    else:
        start = source_url

    if is_blocked(start):
        return grant

    # Manba aggregator emas (ukri.org, nsf.gov, erc.europa.eu...) — havolasi allaqachon rasmiy
    if not is_aggregator(start):
        final = follow_redirects(start) if from_telegram else start
        if is_blocked(final) or host_of(final) in ("t.me", "telegram.me"):
            return grant
        grant["url"] = clean_url(final) or start
        grant["url_key"] = url_key(grant["url"])
        return grant

    # Aggregator — ichidan qazib olamiz (kerak bo'lsa bir necha bosqichda)
    current = start
    for _ in range(MAX_HOPS):
        found = find_original_link(current)
        if not found:
            return grant
        if not is_aggregator(found):
            grant["url"] = found
            grant["url_key"] = url_key(found)
            return grant
        current = found                           # yana aggregator — chuqurroq qazamiz

    return grant


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    for t in sys.argv[1:]:
        print(f"\n{t}")
        print(f"  kalit : {url_key(t)}")
        print(f"  asl   : {find_original_link(t) or '(topilmadi)'}")
