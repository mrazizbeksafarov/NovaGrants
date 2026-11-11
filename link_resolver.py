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

from bs4 import BeautifulSoup

import http_client
from opportunity_content import opportunity_summary

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
    "edugrants.uz", "grantss.uz", "stipendiya.uz", "grantlar.info", "oliygoh.uz",
    "grantgo.uz", "joinyouth.uz", "startupbase.uz", "theglobalscholarship.org",
    "globalscholarship.com", "scholarshipscorner.com",
    "opportunitiespedia.com", "fullyscholarships.com", "youthbreaktheboundaries.com",
    "greatyop.com",
}

# Nufuzli rasmiy grant va dasturlar domenlari (darhol ishoniladi)
KNOWN_OFFICIAL_DOMAINS = {
    "chevening.org", "daad.de", "daad-uzbekistan.org", "turkiyeburslari.gov.tr",
    "stipendiumhungaricum.hu", "fulbrightonline.org", "usembassy.gov",
    "eyuf.uz", "el-yurt.uz", "yoshlar.gov.uz", "it-park.uz", "mininnovation.uz", "innovation.gov.uz",
    "edu.uz", "studyinkorea.go.kr", "campuschina.org", "erasmus-plus.ec.europa.eu",
    "youth.europa.eu", "mfa.gov.hu", "mext.go.jp", "visegradfund.org",
    "si.se", "sbfi.admin.ch", "britishcouncil.org", "cambridge.org", "ox.ac.uk", "harvard.edu"
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

# Brauzer TLS izi bilan — aggregator maqolalarining ko'pi Cloudflare orqasida.
# Oddiy `requests` ularga umuman kira olmasdi (http_client.py izohiga qarang).
_session = http_client.Client(HEADERS)

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


def _get(url: str, allow_redirects=True):
    """Xushmuomala GET: domen bo'yicha tanaffus, 429 da qayta urinish va sovutish."""
    host = host_of(url)

    with _guard:
        until = _host_blocked_until.get(host, 0.0)
    if time.monotonic() < until:
        return None                              # bu domen hozircha bizni qabul qilmayapti

    for attempt in range(MAX_RETRY_429 + 1):
        _throttle(host)
        with _guard:
            if time.monotonic() < _host_blocked_until.get(host, 0.0):
                return None
        r = _session.get(url, timeout=TIMEOUT, allow_redirects=allow_redirects)
        if r is None:
            return None

        if r.status_code == 429:
            if attempt < MAX_RETRY_429:
                retry_after = r.headers.get("Retry-After", "")
                delay = float(retry_after) if retry_after.isdigit() else 5.0 * (attempt + 1)
                if delay > 20:
                    with _guard:
                        _host_blocked_until[host] = time.monotonic() + delay
                    return r
                time.sleep(delay)
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


KNOWN_ACRONYMS = [
    "mewc", "kgfp", "ams", "daad", "mext", "gks", "csc", "eyuf", "chevening",
    "fulbright", "erasmus", "schwarzman", "knight-hennessy", "rhodes", "gates",
    "cern", "desy", "oist", "mitacs", "amgen", "ritsumeikan", "epfl", "eth",
    "inasp", "ugrad", "susie", "techwomen", "flex", "harriman", "vlir", "nuffic",
    "yiss", "epp", "epos", "helmut-schmidt", "stipendium-hungaricum", "turkiye-burslari",
    "turkiyeburslari", "clarendon", "boustany", "weidenfeld-hoffmann", "skoll", "yali",
    "mandela", "humphrey", "hubert-humphrey", "atlas-corps", "vub", "kaist", "gist"
]

ENTITY_DOMAINS = {
    "kaust.edu.sa": "kaust",
    "ox.ac.uk": "oxford",
    "oxford.ac.uk": "oxford",
    "cambridge.org": "cambridge",
    "cam.ac.uk": "cambridge",
    "harvard.edu": "harvard",
    "stanford.edu": "stanford",
    "mit.edu": "mit",
    "imperial.ac.uk": "imperial",
    "daad.de": "daad",
    "mext.go.jp": "mext",
    "chevening.org": "chevening",
    "fulbrightonline.org": "fulbright",
    "usembassy.gov": "usembassy",
    "eyuf.uz": "eyuf",
    "yoshlar.gov.uz": "yoshlar",
    "it-park.uz": "itpark",
    "turkiyeburslari.gov.tr": "turkiyeburslari",
    "stipendiumhungaricum.hu": "stipendiumhungaricum",
    "erasmus-plus.ec.europa.eu": "erasmus",
    "europa.eu": "europa",
    "cern.ch": "cern",
    "desy.de": "desy",
    "oist.jp": "oist",
    "epfl.ch": "epfl",
    "ethz.ch": "eth",
    "kaist.ac.kr": "kaist",
    "gist.ac.kr": "gist",
}

SINGLE_PROGRAM_ORGS = {
    "turkiyeburslari", "chevening", "fulbright", "mext", "eyuf",
    "stipendiumhungaricum", "schwarzman", "rhodes", "gatescambridge"
}


def root_domain(host: str) -> str:
    """Subdomenlarni olib tashlab, tashkilotning asosiy domenni qaytaradi (masalan, cemse.kaust.edu.sa -> kaust.edu.sa)."""
    if not host:
        return ""
    host = host.lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    two_level_tlds = {
        "edu.sa", "ac.uk", "gov.uz", "co.uk", "go.kr", "ac.jp", "edu.au",
        "gov.uk", "gov.tr", "gov.kz", "gov.ru", "or.kr", "ne.jp", "com.uz",
        "org.uk", "ac.nz", "edu.sg", "europa.eu", "usembassy.gov", "ec.europa.eu",
        "ac.kr", "edu.cn", "gov.cn", "org.za", "edu.tr", "gov.in"
    }
    if len(parts) >= 3 and ".".join(parts[-2:]) in two_level_tlds:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def program_fingerprint(title: str, url: str = "") -> str:
    """Ko'p tilli va turli agregatorlar sarlavhalarini yagona dastur kodiga birlashtiradi.
    
    Masalan:
      'KAUST Microelectronics Winter Camp (MEWC) 2027'
      'Saudiya Arabistonida MEWC qishki amaliyot dasturi'
    ikkalasi ham -> 'kaust:mewc' ga tushadi.
    """
    t_str = str(title or "")
    u_str = str(url or "")
    combined = f"{t_str} {u_str}".lower()
    host = host_of(url) if url else ""
    r_dom = root_domain(host) if host else ""
    org = ENTITY_DOMAINS.get(r_dom, "")
    if not org:
        for brand in ("kaust", "cambridge", "oxford", "harvard", "stanford", "mit",
                      "imperial", "daad", "mext", "chevening", "fulbright", "erasmus",
                      "turkiyeburslari", "stipendiumhungaricum", "eyuf", "itpark", "unicef",
                      "cern", "desy", "oist", "mitacs", "amgen", "kaist", "gist"):
            if _mentions_brand(brand, combined):
                org = brand
                break
    acronym = ""
    for ac in KNOWN_ACRONYMS:
        if re.search(r"(?<![a-z])" + re.escape(ac) + r"(?![a-z])", combined):
            acronym = ac.replace("-", "")
            break
    if org and acronym:
        return org if org == acronym else f"{org}:{acronym}"
    if acronym:
        return acronym
    if org in SINGLE_PROGRAM_ORGS:
        return org
    if org:
        words = [w for w in re.findall(r"[a-z0-9]{4,}", t_str.lower())
                 if w not in _STOPWORDS and w != org]
        if words:
            return f"{org}:{'-'.join(sorted(words)[:3])}"
        return org
    return ""


def canonical_url_key(url: str, title: str = "") -> str:
    """Asosiy tashkilot va dastur yo'lini birlashtiruvchi kanonik kalit."""
    if not url:
        return ""
    try:
        p = urlparse(clean_url(url) or url)
        r_domain = root_domain(host_of(url))
        path = (p.path or "/").strip("/").lower()
        prog_code = program_fingerprint(title, url)
        if prog_code:
            return f"{r_domain}:{prog_code}"
        slugs = [s for s in path.split("/") if s and len(s) > 3 and s not in (
            "apply", "register", "registration", "how-to-apply", "admissions",
            "admission", "portal", "en", "uz", "ru", "tr", "fees-funding", "scholarships",
            "internship-opportunities", "opportunities", "index", "default"
        )]
        if slugs:
            clean_slug = re.sub(r"[^a-z0-9]+", "-", slugs[-1]).strip("-")
            if clean_slug:
                return f"{r_domain}:{clean_slug}"
        return f"{r_domain}:{path}" if path else r_domain
    except Exception:
        return url_key(url)


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
    """Sarlavhadan barmoq izi — 3-qatlam takror tekshiruvi.

    Yil, tinish belgilari va umumiy so'zlar ("scholarship", "fully funded",
    "apply now") olib tashlanadi; qolgan so'zlar to'plamidan hash olinadi.
    Shu sabab "Erasmus Mundus Joint Master Degree 2027" va "Joint Master
    Degree Erasmus Mundus (Fully Funded)" bir xil izga tushadi.

    ATAYIN CHEKLANGAN — 2 tadan kam mazmunli so'z qolsa BO'SH qaytaradi.
    Masalan "Chevening Scholarship 2026 (Fully Funded)" da faqat "chevening"
    qoladi va iz berilmaydi. Sabab: bitta so'zli iz "Oxford Scholarship" bilan
    "Oxford Fellowship" ni bitta grant deb hisoblab, haqiqiy imkoniyatni
    jimgina yo'q qilardi. Noto'g'ri takror — o'tkazib yuborilgan takrordan
    xavfliroq, chunki uni hech kim sezmaydi. Bunday sarlavhalar uchun
    `url_key` qatlami ishlaydi.
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
    return hashlib.sha1(" ".join(sorted(tokens)[:12]).encode("utf-8"), usedforsecurity=False).hexdigest()[:20]


def follow_redirects(url: str) -> str:
    """Qisqartirilgan/o'tkazuvchi havolani oxirgi haqiqiy manzilgacha ochadi."""
    r = _get(url, allow_redirects=True)
    if r is None:
        return url
    return getattr(r, "url", "") or url


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


def _article_roots(soup: BeautifulSoup) -> list:
    """Maqola tanasi uchun nomzodlar — birinchisidan boshlab sinab ko'riladi.

    NEGA RO'YXAT, BITTA EMAS: opportunitiescircle.com Elementor'da qurilgan va
    `div.elementor-widget-theme-post-content` ichida faqat ichki havolalar
    bo'ladi — "Apply" tugmasi alohida vidjetda, konteynerdan TASHQARIDA.
    Eski kod birinchi mos konteynerni tanlab, boshqa joyga qaramas edi va
    natijada bu manbadan 8 tadan 8 tasi "havola topilmadi" bo'lardi (jonli
    o'lchandi). Endi tor doiradan boshlab, natija bo'lmasa kengaytiramiz.
    """
    roots, seen = [], set()

    def add(node):
        # BeautifulSoup teglarini `==` bilan solishtirish MAZMUN bo'yicha
        # ishlaydi va sekin — shuning uchun aynanlik (id) bo'yicha tekshiramiz.
        if node is None or id(node) in seen:
            return
        seen.add(id(node))
        roots.append(node)

    for sel in ("article", "div.entry-content", "div.post-content", "div.td-post-content",
                "div.single-content", "div.content-area", "div.elementor-widget-theme-post-content",
                "main"):
        node = soup.select_one(sel)
        if node and len(node.get_text(strip=True)) > 200:
            add(node)

    add(soup.body or soup)                       # oxirgi chora: butun sahifa
    return roots


def _collect_candidates(root, article_url: str, source_host: str) -> tuple:
    """Berilgan konteynerdagi havolalarni baholab, ikki ro'yxatga ajratadi:
    (tashqi_havolalar, ichki_o'tish_havolalari) — ikkalasi ham (baho, url)."""
    anchors = root.find_all("a", href=True)
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

    return external, internal_redirects


def find_original_link(article_url: str, title: str = "") -> tuple:
    """Aggregator maqolasidan grantning rasmiy havolasini topadi.

    Qaytaradi: (havola, anchor_bahosi). Topilmasa ("", 0).
    Baho keyinchalik link_matches_title() da ishlatiladi — kuchli anchor
    ("Apply now", "Rasmiy veb-sayt") so'z mosligi talabini bekor qiladi.
    """
    resp = _get(article_url)
    if resp is None or resp.status_code != 200:
        code = resp.status_code if resp is not None else "ulanmadi"
        print(f"    ! {host_of(article_url)} javob bermadi ({code})")
        return "", 0

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
    except Exception:
        return "", 0

    source_host = host_of(article_url)

    # Tor konteynerdan boshlaymiz (sidebar reklamalari tushmasin), tashqi
    # havola topilmasa kengroq doiraga o'tamiz.
    external, internal_redirects = [], []
    for root in _article_roots(soup):
        external, internal_redirects = _collect_candidates(root, article_url, source_host)
        if external:
            break

    if not external and not internal_redirects:
        return "", 0

    for pool in (external, internal_redirects):
        if not pool:
            continue
        pool.sort(key=lambda x: x[0], reverse=True)

        # Agar maqolada umuman bitta tashqi havola bo'lsa — bu deyarli aniq o'sha grant.
        # Bunday holatda past bahoga ham ishonamiz.
        threshold = 4 if len(pool) == 1 else 10

        for score, href in pool[:5]:
            if score < threshold:                # ishonch past — reklama bo'lishi mumkin
                break
            final = follow_redirects(href)
            if is_blocked(final):
                continue
            if host_of(final) == source_host:
                continue
            if title and not is_aggregator(final) and not link_matches_title(title, final, score)[0]:
                continue
            return clean_url(final), score

    return "", 0


# Sarlavha bilan havola mosligini tekshirishda e'tiborga olinmaydigan so'zlar
_TITLE_NOISE = {
    "the", "and", "for", "with", "from", "fully", "funded", "full", "free",
    "scholarship", "scholarships", "program", "programme", "programs", "positions",
    "position", "university", "college", "international", "students", "student",
    "opportunity", "opportunities", "apply", "application", "applications", "open",
    "now", "call", "grant", "grants", "award", "awards", "study", "abroad",
    "uchun", "yangi", "dastur", "talabalar", "imkoniyat", "boshlandi", "qabul",
}

# Sarlavha va URL yo'lida uchrashi mumkin bo'lgan mavzu so'zlari (qisqa bo'lsa ham)
_TOPIC_WORDS = ("phd", "postdoc", "intern", "internship", "fellow", "fellowship",
                "scholarship", "grant", "master", "bachelor", "summer", "exchange",
                "residency", "award", "contest", "competition", "accelerator",
                "incubator", "vacanc", "career", "job", "admission", "apply")


STRONG_ANCHOR_SCORE = 30    # "Apply now", "Official website", "Rasmiy veb-sayt" darajasi

ENTITY_BRANDS = [
    "cambridge", "oxford", "harvard", "stanford", "mit", "imperial", "kaust",
    "columbia", "yale", "princeton", "berkeley", "cornell", "caltech", "chicago",
    "edinburgh", "kcl", "ucl", "manchester", "toronto", "mcgill", "unicef",
    "unesco", "undp", "who", "worldbank", "rotary", "fulbright", "chevening",
    "daad", "mext", "erasmus", "turkiyeburslari", "stipendium", "gatescambridge",
    "rhodes", "schwarzman", "knight-hennessy", "ellison"
]


def _mentions_brand(brand: str, text: str) -> bool:
    # MIT must not match subMIT.com; WHO must not match "whole".
    if len(brand) <= 3:
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(brand)}(?![a-z0-9])", text))
    return brand in text


def link_matches_title(title: str, url: str, anchor_score: int = 0) -> tuple:
    """Havola sarlavhaga mos keladimi? Qaytaradi: (mos_keladi, sabab).

    Ikkita aniq nosozlikni ushlaydi (ikkalasi ham jonli kanalda sodir bo'lgan):
      • bosh sahifaga havola — "Ariza topshirish" bosh sahifaga olib borsa foydasiz
        ("Amaliyot Ofisi" -> yoshlar.gov.uz/)
      • butunlay boshqa saytga havola — maqoladagi begona havola tanlangan bo'lsa
        ("CoCreate Pitch" -> accio.com/work/installGuide)
      • brend/universitet nomuvofiqligi — aggregatordagi qo'shimcha reklama/vidjet
        ("Imperial College London" -> gatescambridge.org)

    MUHIM: sarlavha o'zbekcha yoki ruscha bo'lsa, inglizcha URL bilan so'z mosligi
    bo'lmaydi (masalan "Incubation Program" -> awards.gov.uz/en/pta). Shuning uchun
    havola KUCHLI anchor matnidan olingan bo'lsa ("Ariza topshirish", "Apply now"),
    so'z mosligi talab qilinmaydi — anchor matnining o'zi yetarli dalil.
    """
    if not url:
        return False, "havola yo'q"

    path = (urlparse(url).path or "").strip("/")
    host = host_of(url)
    blob = f"{host}/{path}".lower()
    low_title = (title or "").lower()

    tokens = {t for t in re.findall(r"[a-z0-9]{4,}", low_title)
              if t not in _TITLE_NOISE}

    # Brend/tashkilot nomuvofiqligi tekshiruvi (begona universitet havolasini rad etadi)
    for b in ENTITY_BRANDS:
        if _mentions_brand(b, blob) and not _mentions_brand(b, low_title):
            other_brands = [ob for ob in ENTITY_BRANDS if _mentions_brand(ob, low_title)]
            if other_brands or (len(tokens) >= 2 and anchor_score < STRONG_ANCHOR_SCORE):
                return False, f"brend nomuvofiqligi: URL da '{b}', lekin sarlavhada yo'q"

    token_hit = any(t in blob for t in tokens)
    strong = anchor_score >= STRONG_ANCHOR_SCORE

    if not path:
        # Bosh sahifa. Faqat domen nomining o'zi sarlavhaga mos kelsa qabul qilamiz
        # (masalan "Green Talents Award" -> greentalents.de).
        if token_hit:
            return True, ""
        return False, "bosh sahifa (aniq ariza sahifasi emas)"

    if not tokens or token_hit or strong:
        return True, ""

    low_title = (title or "").lower()
    if any(w in low_title and w in blob for w in _TOPIC_WORDS):
        return True, ""

    return False, "sarlavha bilan bog'liq emas"


def resolve_grant(grant: dict) -> dict:
    """Bitta yozuv uchun asl havolani aniqlaydi.

    Qo'shadi: `url` (asl havola), `source_url`, `url_key`, `fingerprint`, `canonical_url_key`, `program_fingerprint`.
    Asl havola topilmasa `url` bo'sh qoladi — chaqiruvchi uni tashlab yuborishi kerak.
    """
    source_url = clean_url(grant.get("url", ""))
    grant["source_url"] = source_url
    title = grant.get("title", "")
    grant["fingerprint"] = title_fingerprint(title)
    grant["url"] = ""
    grant["url_key"] = ""
    grant["canonical_url_key"] = ""
    grant["program_fingerprint"] = ""

    def accept(final_url, anchor_score=0):
        """Havolani qabul qilishdan oldin sarlavhaga mosligini va agregator emasligini tekshiradi."""
        if not final_url or is_aggregator(final_url) or is_blocked(final_url):
            return False
        ok, reason = link_matches_title(title, final_url, anchor_score)
        if not ok:
            print(f"    ! havola rad etildi ({reason}): {final_url[:70]}")
            return False
        clean = clean_url(final_url) or final_url
        if is_aggregator(clean) or is_blocked(clean):
            return False
        grant["url"] = clean
        grant["url_key"] = url_key(clean)
        grant["canonical_url_key"] = canonical_url_key(clean, title)
        grant["program_fingerprint"] = program_fingerprint(title, clean)
        return True

    if not source_url:
        return grant

    # Full RSS entries already contain the article's application links. Reuse
    # the same scoring, redirect and title checks without fetching the article.
    if grant.get("feed_html"):
        soup = BeautifulSoup(grant["feed_html"], "html.parser")
        candidates, _ = _collect_candidates(soup, source_url, host_of(source_url))
        for score, href in sorted(candidates, reverse=True)[:5]:
            related_path = GOOD_PATH.search(urlparse(href).path or "") and link_matches_title(title, href, 0)[0]
            if (score >= STRONG_ANCHOR_SCORE or (score >= 8 and related_path)) and not is_aggregator(href):
                if accept(follow_redirects(href), anchor_score=score):
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
        if is_aggregator(final):
            start = final                         # yo'naltirish agregatorga olib bordi — ichini qazamiz
        else:
            accept(clean_url(final) or start,
                   anchor_score=STRONG_ANCHOR_SCORE if from_telegram else 0)
            if grant.get("url"):
                if grant.get("fetch_details"):
                    response = _get(grant["url"])
                    if response is None or response.status_code != 200:
                        grant["url"] = ""  # unavailable details are retryable
                        return grant
                    if not accept(getattr(response, "url", "") or grant["url"]):
                        grant["url"] = ""
                        return grant
                    page = BeautifulSoup(response.text, "html.parser")
                    root = page.select_one(grant.get("detail_selector", "main, article"))
                    if root is None:
                        grant["url"] = ""
                        return grant
                    grant["summary"] = opportunity_summary(str(root))
                return grant

    # Aggregator — ichidan qazib olamiz (kerak bo'lsa bir necha bosqichda)
    current = start
    for _ in range(MAX_HOPS):
        found, score = find_original_link(current, title=title)
        if not found:
            break
        if not is_aggregator(found):
            if accept(found, anchor_score=score):
                return grant
        current = found                           # yana aggregator — chuqurroq qazamiz

    # Agar hali ham asl havola topilmagan bo'lsa — Gemini AI flagman modeli orqali sinaymiz
    if not grant.get("url"):
        try:
            from ai_agent import resolve_official_url_with_ai
            resp = _get(start)
            if resp and resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                candidates = []
                for a in soup.find_all("a", href=True):
                    h = a["href"].strip()
                    if h.startswith(("http://", "https://")) and not is_blocked(h) and not is_aggregator(h):
                        if h not in candidates:
                            candidates.append(h)
                if candidates:
                    ai_url = resolve_official_url_with_ai(title, grant.get("summary", ""), candidates)
                    if ai_url and ai_url in candidates:
                        # An allowed candidate may redirect to an aggregator or unrelated site.
                        accept(clean_url(follow_redirects(ai_url)), anchor_score=STRONG_ANCHOR_SCORE)
        except Exception as exc:
            print(f"    ! zaxira havola qidirish xatosi: {type(exc).__name__}")

    return grant


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    for t in sys.argv[1:]:
        found, score = find_original_link(t)
        print(f"\n{t}")
        print(f"  kalit : {url_key(t)}")
        print(f"  asl   : {found or '(topilmadi)'}  (anchor bahosi: {score})")
