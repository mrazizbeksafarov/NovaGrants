"""Nova Grants — manbalar katalogi.

Bu ro'yxatdagi HAR BIR manba jonli tekshirilgan (tools/check_sources.py).
Ishlamaydigan, yangilik lentasi bo'lgan yoki mavzuga aloqasi yo'q manbalar
DISABLED ro'yxatiga tushirilgan — sababi bilan birga.

Maydonlar:
  id      — qisqa nom, loglarda ko'rinadi
  type    — "rss" | "telegram" | "grantsgov"
  kind    — "official"   : havolasi allaqachon rasmiy, qazish shart emas
            "aggregator" : maqola ichidan ASL havola qazib olinadi
  region  — geografiya
  topic   — scholarship | fellowship | research | grant | ngo | arts | startup

MUHIM: "aggregator" manbaning o'z havolasi HECH QACHON kanalga tushmaydi.
link_resolver.py maqolani ochib, grantning rasmiy saytini topib beradi.
"""

SOURCES = [
    # ══════════════════════════════════════════════════════════════════════
    # INSTITUTSIONAL FONDLAR — sukut bo'yicha O'CHIQ
    #
    # Bular haqiqiy va rasmiy manbalar, lekin grantni JISMONIY SHAXS emas,
    # UNIVERSITET yoki TASHKILOT so'raydi ("principal investigator", "host
    # institution", "UK-based organisations"). O'zbekistonlik talaba yoki yosh
    # mutaxassis ularga to'g'ridan-to'g'ri ariza topshira olmaydi.
    #
    # Sinovda aynan shular kanalni to'ldirib yubordi (NSF PESOSE, UKRI doctoral
    # focal award va h.k.), shuning uchun o'chirildi. Agar kanal ilmiy
    # tashkilotlarga ham qaratilsa — enabled ni True qiling.
    # ══════════════════════════════════════════════════════════════════════
    {"id": "ukri", "type": "rss", "kind": "official", "region": "UK", "topic": "research",
     "url": "https://www.ukri.org/opportunity/feed/", "enabled": False},

    {"id": "nsf", "type": "rss", "kind": "official", "region": "US", "topic": "research",
     "url": "https://new.nsf.gov/rss/rss_www_funding_upcoming.xml", "enabled": False},

    {"id": "erc-europa", "type": "rss", "kind": "official", "region": "EU", "topic": "research",
     "url": "https://erc.europa.eu/rss.xml", "enabled": False},

    {"id": "nea-arts", "type": "rss", "kind": "official", "region": "US", "topic": "arts",
     "url": "https://www.arts.gov/rss.xml", "enabled": False},

    # grants.gov rasmiy API (1200+ ochiq imkoniyat) — xuddi shu sabab bilan o'chiq.
    {"id": "grants.gov", "type": "grantsgov", "kind": "official", "region": "US", "topic": "grant",
     "url": "https://api.grants.gov/v1/api/search2", "enabled": False},

    # ══════════════════════════════════════════════════════════════════════
    # AGGREGATORLAR — ichidan ASL havola qazib olinadi
    # ══════════════════════════════════════════════════════════════════════
    {"id": "opportunitydesk", "type": "rss", "kind": "aggregator", "region": "Global", "topic": "scholarship",
     "url": "https://opportunitydesk.org/feed/"},

    {"id": "opps4youth", "type": "rss", "kind": "aggregator", "region": "Global", "topic": "fellowship",
     "url": "https://opportunitiesforyouth.org/feed/"},

    {"id": "oyaop", "type": "rss", "kind": "aggregator", "region": "Global", "topic": "scholarship",
     "url": "https://oyaop.com/feed/"},

    {"id": "oppscircle", "type": "rss", "kind": "aggregator", "region": "Global", "topic": "scholarship",
     "url": "https://opportunitiescircle.com/feed/"},

    {"id": "scholarshiproar", "type": "rss", "kind": "aggregator", "region": "Global", "topic": "scholarship",
     "url": "https://scholarshiproar.com/feed/"},

    {"id": "scholarshipregion", "type": "rss", "kind": "aggregator", "region": "Global", "topic": "scholarship",
     "url": "https://scholarshipregion.com/feed/"},

    {"id": "fellowshipbard", "type": "rss", "kind": "aggregator", "region": "Global", "topic": "fellowship",
     "url": "https://fellowshipbard.com/feed/"},

    {"id": "profellow", "type": "rss", "kind": "aggregator", "region": "Global", "topic": "fellowship",
     "url": "https://www.profellow.com/feed/"},

    {"id": "oppscorners", "type": "rss", "kind": "aggregator", "region": "Global", "topic": "scholarship",
     "url": "https://opportunitiescorners.com/feed/"},

    {"id": "mladiinfo", "type": "rss", "kind": "aggregator", "region": "EU", "topic": "fellowship",
     "url": "https://www.mladiinfo.eu/feed/"},

    {"id": "opps4africans", "type": "rss", "kind": "aggregator", "region": "Africa", "topic": "scholarship",
     "url": "https://www.opportunitiesforafricans.com/feed/"},

    {"id": "terravivagrants", "type": "rss", "kind": "aggregator", "region": "Global", "topic": "ngo",
     "url": "https://terravivagrants.org/feed/"},

    {"id": "fundsforngos", "type": "rss", "kind": "aggregator", "region": "Global", "topic": "ngo",
     "url": "https://www.fundsforngos.org/feed/"},

    {"id": "grantlar.uz", "type": "rss", "kind": "aggregator", "region": "UZ", "topic": "scholarship",
     "url": "https://grantlar.uz/feed/"},

    # ══════════════════════════════════════════════════════════════════════
    # TELEGRAM — O'zbekiston
    # ══════════════════════════════════════════════════════════════════════
    {"id": "tg:edugrandsuz", "type": "telegram", "kind": "aggregator", "region": "UZ", "topic": "scholarship",
     "channel": "edugrandsuz"},

    {"id": "tg:grantlar", "type": "telegram", "kind": "aggregator", "region": "UZ", "topic": "scholarship",
     "channel": "grantlar"},

    {"id": "tg:erasmus_uz", "type": "telegram", "kind": "aggregator", "region": "UZ", "topic": "scholarship",
     "channel": "erasmus_uz"},

    {"id": "tg:grantsuzb", "type": "telegram", "kind": "aggregator", "region": "UZ", "topic": "scholarship",
     "channel": "grantsuzb"},

    {"id": "tg:yoshlar", "type": "telegram", "kind": "aggregator", "region": "UZ", "topic": "grant",
     "channel": "yoshlaragentligi"},

    {"id": "tg:itpark", "type": "telegram", "kind": "aggregator", "region": "UZ", "topic": "startup",
     "channel": "itpark_uz"},

    {"id": "tg:startupbaseuz", "type": "telegram", "kind": "aggregator", "region": "UZ", "topic": "startup",
     "channel": "startupbaseuz"},

    # ══════════════════════════════════════════════════════════════════════
    # TELEGRAM — Global
    # ══════════════════════════════════════════════════════════════════════
    {"id": "tg:globalscholar", "type": "telegram", "kind": "aggregator", "region": "Global", "topic": "scholarship",
     "channel": "theglobalscholarship"},

    {"id": "tg:intlopps", "type": "telegram", "kind": "aggregator", "region": "Global", "topic": "scholarship",
     "channel": "internationalopportunities"},

    {"id": "tg:scholarshipregion", "type": "telegram", "kind": "aggregator", "region": "Global", "topic": "scholarship",
     "channel": "scholarshipregion"},

    {"id": "tg:globalopps", "type": "telegram", "kind": "aggregator", "region": "Global", "topic": "scholarship",
     "channel": "globalopportunities"},

    {"id": "tg:ru_grants", "type": "telegram", "kind": "aggregator", "region": "CIS", "topic": "scholarship",
     "channel": "grantsandscholarships"},
]


# ══════════════════════════════════════════════════════════════════════════
# O'CHIRILGAN MANBALAR — nima uchun olib tashlanganini eslab qolish uchun
# ══════════════════════════════════════════════════════════════════════════
DISABLED = {
    # Feed o'lgan / bot himoyasi (2026-08-04 holatiga)
    "scholars4dev.com/feed":        "RSS bo'sh qaytadi (0 ta yozuv)",
    "youthop.com/feed":             "HTTP 404 — feed olib tashlangan",
    "scholarship-positions.com":    "Cloudflare himoyasi, HTML stub qaytaradi",
    "armacad.info/rss":             "HTTP 404",
    "afterschoolafrica.com/feed":   "RSS o'chirilgan, HTML JS bilan yuklanadi",
    "philanthropynewsdigest.org":   "RSS o'chirilgan (Next.js sahifa)",
    "grantstation.com/rss.xml":     "RSS bo'sh",
    "scholarshipdb.net":            "HTTP 403",
    "wemakescholars.com":           "HTTP 404",
    "daad.de / eurodesk / salto":   "HTTP 403/404 — bot himoyasi",
    "nih.gov":                      "HTTP 403",
    "globalgiving / opensociety":   "HTTP 403 / ulanish uzildi",
    "youth-time.eu":                "SSL sertifikat xatosi",

    # Ishlaydi, lekin GRANT MANBASI EMAS — kanalga reklama/yangilik olib keladi
    "techcrunch.com":               "Yangilik lentasi — 'startup $5M jaldi' tipidagi postlar",
    "news.ycombinator.com":         "Forum lentasi, grant yo'q",
    "news.crunchbase.com":          "Investitsiya yangiliklari",
    "sifted.eu / e27.co":           "Biznes yangiliklari",
    "techinasia / dealstreetasia":  "Biznes yangiliklari",
    "firstround.com / vccafe.com":  "Blog",
    "eu-startups.com":              "Investitsiya yangiliklari",
    "insidehighered.com":           "Ta'lim yangiliklari, imkoniyat emas",
    "researchprofessionalnews":     "Yangilik lentasi",
    "kun.uz":                       "Umumiy yangiliklar",
    "opportunitydesk.info":         "Nomi o'xshash, lekin oshxona blogi (!)",
    "youthvillage.co.za":           "Ko'ngilochar sayt",
    "msu.ac.zw":                    "Bitta universitet yangiliklari",
    "scholarshipowl.com/blog":      "Marketing blogi",
    "reliefweb.int":                "Gumanitar hisobotlar, grant emas",
    "devex.com":                    "To'lovli, HTTP 403",
    "tg:udevs_news, tg:udevs_jobs": "Kompaniya yangiliklari / ish o'rinlari",
    "tg:startupmix, tg:startups":   "Reklama va yangilik",
    "tg:uzvc_uz, tg:aloqaventures": "VC yangiliklari, ochiq chaqiruv emas",
    "tg:opportunitydesk":           "Ochiq preview yo'q (t.me/s ishlamaydi)",
    "tg:scholarshipsads":           "Ochiq preview yo'q",
    "tg:opportunitiescorners":      "Deyarli faol emas (2 ta post)",
}


def enabled_sources():
    """Faol manbalar ro'yxati."""
    return [s for s in SOURCES if s.get("enabled", True)]


def stats():
    from collections import Counter
    act = enabled_sources()
    return {
        "faol": len(act),
        "o_chirilgan": len(SOURCES) - len(act),
        "type": dict(Counter(s["type"] for s in act)),
        "kind": dict(Counter(s["kind"] for s in act)),
        "region": dict(Counter(s["region"] for s in act)),
    }


if __name__ == "__main__":
    import json, sys
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(stats(), indent=2, ensure_ascii=False))
