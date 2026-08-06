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
  pages   — WordPress feed uchun nechta sahifa o'qiladi (ixtiyoriy, sukut 1)

MUHIM: "aggregator" manbaning o'z havolasi HECH QACHON kanalga tushmaydi.
link_resolver.py maqolani ochib, grantning rasmiy saytini topib beradi.

── SAHIFALASH (2026-08-06 da o'lchandi) ──────────────────────────────────
WordPress feed'lari bir sahifada atigi 10 ta yozuv beradi, lekin `?paged=2`
va `?paged=3` yana 10 tadan NOYOB yozuv qaytaradi. Ya'ni bitta ishonchli
manbadan 10 emas, 30 ta yozuv olish mumkin. Bu — yangi manba qidirishdan
ko'ra arzon va aniqroq yo'l, chunki manbalar allaqachon tekshirilgan.

── NEGA RASMIY MANBALAR KAM ──────────────────────────────────────────────
40+ rasmiy sayt tekshirildi (chevening.org, daad.de, britishcouncil.org,
turkiyeburslari.gov.tr, stipendiumhungaricum.hu, euraxess, salto-youth,
unjobs, jobs.ac.uk, mastersportal va h.k.) — 2026-yilda ularning deyarli
hech birida ishlaydigan RSS yo'q (404, JS bilan yuklanadigan sahifa yoki
bot himoyasi). Ishlayotgan kam sonlisi DISABLED da sababi bilan yozilgan.
Shu sabab qamrov aggregatorlar + sahifalash orqali kengaytirildi.
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
    # `pages: 3` — jonli o'lchangan: har sahifa 10 tadan NOYOB yozuv beradi.
    {"id": "opportunitydesk", "type": "rss", "kind": "aggregator", "region": "Global", "topic": "scholarship",
     "url": "https://opportunitydesk.org/feed/", "pages": 3},

    {"id": "oyaop", "type": "rss", "kind": "aggregator", "region": "Global", "topic": "scholarship",
     "url": "https://oyaop.com/feed/", "pages": 3},

    {"id": "oppscircle", "type": "rss", "kind": "aggregator", "region": "Global", "topic": "scholarship",
     "url": "https://opportunitiescircle.com/feed/", "pages": 3},

    {"id": "scholarshiproar", "type": "rss", "kind": "aggregator", "region": "Global", "topic": "scholarship",
     "url": "https://scholarshiproar.com/feed/", "pages": 3},

    {"id": "profellow", "type": "rss", "kind": "aggregator", "region": "Global", "topic": "fellowship",
     "url": "https://www.profellow.com/feed/", "pages": 2},

    {"id": "oppscorners", "type": "rss", "kind": "aggregator", "region": "Global", "topic": "scholarship",
     "url": "https://opportunitiescorners.com/feed/", "pages": 2},

    {"id": "mladiinfo", "type": "rss", "kind": "aggregator", "region": "EU", "topic": "fellowship",
     "url": "https://www.mladiinfo.eu/feed/", "pages": 2},

    {"id": "opps4africans", "type": "rss", "kind": "aggregator", "region": "Africa", "topic": "scholarship",
     "url": "https://www.opportunitiesforafricans.com/feed/", "pages": 2},

    {"id": "grantlar.uz", "type": "rss", "kind": "aggregator", "region": "UZ", "topic": "scholarship",
     "url": "https://grantlar.uz/feed/", "pages": 2},

    # 2026-08-06 da topilgan va tekshirilgan: 10 ta yozuv, o'sha kungi.
    {"id": "scholarshipunion", "type": "rss", "kind": "aggregator", "region": "Global", "topic": "scholarship",
     "url": "https://scholarshipunion.com/feed/", "pages": 2},

    # Oddiy `requests` ga HTTP 429 berardi. http_client.py (Chrome TLS izi)
    # bilan 200 va 254 KB feed qaytardi — shu sabab qaytarildi.
    # DIQQAT: bu sayt tez-tez cheklaydi. 2026-08-06 da ko'p sinovdan keyin
    # 429 dan 403 ga o'tdi. Kuniga bir marta murojaatda tiklanishi kutiladi;
    # bir necha kun 403 tursa — DISABLED ga ko'chiring. Bitta sahifa yetarli.
    {"id": "opps4youth", "type": "rss", "kind": "aggregator", "region": "Global", "topic": "fellowship",
     "url": "https://opportunitiesforyouth.org/feed/"},

    # ── RASMIY (qazish shart emas) ──────────────────────────────────────
    # O'zbekiston uchun Fulbright, UGRAD, professional almashuv dasturlari.
    # 2026-08-06: 10 ta yozuv, 1 kunlik. Eng aniq manbalardan biri.
    {"id": "usembassy-uz", "type": "rss", "kind": "official", "region": "UZ", "topic": "scholarship",
     "url": "https://uz.usembassy.gov/feed/"},

    # Yevropa Ittifoqining yoshlar portali — almashuv, korpus, tanlovlar.
    {"id": "youth-europa", "type": "rss", "kind": "official", "region": "EU", "topic": "grant",
     "url": "https://youth.europa.eu/rss.xml"},

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

    # 2026-08-06 da qo'shildi. Har uchalasi o'sha kuni faol edi.
    {"id": "tg:grantgo", "type": "telegram", "kind": "aggregator", "region": "UZ", "topic": "scholarship",
     "channel": "grantgouz"},          # 20/20 postda tashqi havola

    {"id": "tg:oliygoh", "type": "telegram", "kind": "aggregator", "region": "UZ", "topic": "scholarship",
     "channel": "oliygoh_grantlar"},   # 19/20 postda tashqi havola

    {"id": "tg:joinyouth", "type": "telegram", "kind": "aggregator", "region": "UZ", "topic": "grant",
     "channel": "joinyouthuz"},        # 17/20 postda tashqi havola

    # ══════════════════════════════════════════════════════════════════════
    # TELEGRAM — Global
    # ══════════════════════════════════════════════════════════════════════
    {"id": "tg:globalscholar", "type": "telegram", "kind": "aggregator", "region": "Global", "topic": "scholarship",
     "channel": "theglobalscholarship"},

    {"id": "tg:scholarshipregion", "type": "telegram", "kind": "aggregator", "region": "Global", "topic": "scholarship",
     "channel": "scholarshipregion"},

    {"id": "tg:scholarshipscorner", "type": "telegram", "kind": "aggregator", "region": "Global", "topic": "scholarship",
     "channel": "scholarshipscorner"},  # 20/20 postda tashqi havola
]


# ══════════════════════════════════════════════════════════════════════════
# O'CHIRILGAN MANBALAR — nima uchun olib tashlanganini eslab qolish uchun
# ══════════════════════════════════════════════════════════════════════════
DISABLED = {
    # ── 2026-08-06 auditida olib tashlanganlar ────────────────────────────
    # O'LIK TELEGRAM KANALLARI. Scraper sanaga qaramagani uchun bular 5 yillik
    # e'lonlarni "yangi imkoniyat" sifatida quvurga tiqib turgan edi.
    "tg:globalopportunities":       "O'lik — oxirgi post 2021-01-04 (5.6 yil)",
    "tg:grantsandscholarships":     "O'lik — oxirgi post 2021-05-13 (5.2 yil)",
    "tg:internationalopportunities": "So'nayotgan — oxirgi post 2026-04-16",

    # TEXNIK
    "fellowshipbard.com/feed":      "ConnectTimeout — sayt javob bermaydi",
    "opportunitiesforyouth.org":    "HTTP 429 — feed ham, maqolalari ham. "
                                    "Qazish bosqichida har safar bloklanadi",
    "scholarshipscorner.website":   "Ulanmaydi — tg:scholarshipscorner o'z saytiga havola qiladi",
    "scholarshipregion.com/feed":   "HTTP 202 (Cloudflare) — Telegram varianti ishlatiladi",

    # MAVZU: NGO/tashkilot grantlari. AI ga "institutsional grantlarni tashla"
    # deb aytilgan, ya'ni bu ikkisi deyarli faqat tarmoq va token isrofi edi
    # (bir yurishda 29 ta yozuv berib, deyarli hammasi rad etilardi).
    "terravivagrants.org":          "NGO/tashkilot grantlari — jismoniy shaxs uchun emas",
    "fundsforngos.org":             "NGO/tashkilot grantlari + 'Sample Proposal' maqolalari",

    # 2026-08-06 da tekshirilgan, RSS'i yo'q rasmiy saytlar (JS yoki 404):
    "chevening.org / daad.de":      "RSS yo'q — sahifa JS bilan yuklanadi",
    "britishcouncil.org":           "ReadTimeout, RSS topilmadi",
    "turkiyeburslari / stipendiumhungaricum": "RSS yo'q yoki bo'sh WordPress",
    "euraxess / salto-youth / eurodesk": "HTTP 403/404 — feed olib tashlangan",
    "unjobs / jobs.ac.uk / mastersportal": "RSS yo'q",
    "api.reliefweb.int":            "v1 o'chirilgan (410), v2 ro'yxatdan o'tish talab qiladi",
    "ec.europa.eu funding-tenders": "API kalit talab qiladi (403/500)",

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
