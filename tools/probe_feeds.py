"""Ishlamagan manbalar uchun muqobil feed manzillarini sinab ko'rish."""

import sys
import os
import concurrent.futures

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import feedparser
import requests

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
    "Accept": "application/rss+xml, application/xml, text/xml, application/atom+xml, */*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

CANDIDATES = [
    # grants.gov
    "https://grants.gov/rss/GG_NewOppByCategory.xml",
    "https://www.grants.gov/rss/GG_NewOppByCategory.xml",
    "https://apply07.grants.gov/rss/GG_NewOppByCategory.xml",
    "https://grants.gov/api/common/rss/newoppbycategory",
    # NIH
    "https://grants.nih.gov/grants/guide/newsfeed/fundingopps.xml",
    "https://grants.nih.gov/funding/searchguide/rss/weekly.xml",
    # SALTO
    "https://www.salto-youth.net/rss/trainings/",
    "https://www.salto-youth.net/tools/european-training-calendar/rss.xml",
    "https://www.salto-youth.net/rss/etcalendar/",
    # Eurodesk
    "https://programmes.eurodesk.eu/rss",
    "https://national.eurodesk.eu/rss.xml",
    # DAAD
    "https://www.daad.de/rss/en/",
    "https://www2.daad.de/rss/en/",
    # Humboldt / Wellcome
    "https://www.humboldt-foundation.de/en/rss.xml",
    "https://wellcome.org/news/rss.xml",
    "https://wellcome.org/feed",
    # Open Society / GlobalGiving
    "https://www.opensocietyfoundations.org/rss",
    "https://www.globalgiving.org/rss/projects.xml",
    # scholars4dev
    "https://www.scholars4dev.com/feed/",
    "https://www.scholars4dev.com/feed/rss/",
    "https://www.scholars4dev.com/category/scholarships/feed/",
    # youthop
    "https://www.youthop.com/feed/",
    "https://www.youthop.com/rss",
    "https://www.youthop.com/feed.xml",
    # scholarship-positions
    "https://scholarship-positions.com/feed/",
    "https://www.scholarship-positions.com/feed/",
    "https://scholarship-positions.com/rss",
    # armacad
    "https://armacad.info/feed",
    "https://armacad.info/rss.xml",
    "https://armacad.info/feed/rss",
    # afterschoolafrica
    "https://www.afterschoolafrica.com/feed/",
    "https://afterschoolafrica.com/feed/",
    # wemakescholars
    "https://www.wemakescholars.com/feed",
    "https://www.wemakescholars.com/blog/rss",
    # philanthropy news digest
    "https://philanthropynewsdigest.org/rfps/rss",
    "https://philanthropynewsdigest.org/feeds/rfp.rss",
    "https://philanthropynewsdigest.org/feed/rfp",
    # scholarshipdb
    "https://scholarshipdb.net/rss",
    "https://scholarshipdb.net/scholarships/rss",
    # grantstation
    "https://grantstation.com/rss.xml",
    # youth-time
    "http://youth-time.eu/feed/",
    # qo'shimcha nomzodlar (yangi manbalar)
    "https://www.scholarshipsads.com/feed/",
    "https://scholarshipunion.com/feed/",
    "https://www.opportunitiesforafrica.org/feed/",
    "https://scholarshiptab.com/rss",
    "https://www.studyabroadaide.com/feed/",
    "https://www.thescholarshipportal.com/feed",
    "https://www.grantwatch.com/rss/rss-grants.xml",
    "https://ec.europa.eu/info/funding-tenders/opportunities/rss",
    "https://euraxess.ec.europa.eu/jobs/rss",
    "https://www.findaphd.com/rss/phd-projects.aspx",
    "https://academicpositions.com/rss",
    "https://www.jobs.ac.uk/rss/",
    "https://opportunitiesforyouths.com/feed/",
    "https://www.youthopportunities.info/feed/",
    "https://kachwanya.com/feed/",
    "https://www.msmestartupfund.com/feed/",
    "https://devex.com/news/rss",
    "https://reliefweb.int/updates/rss.xml?advanced-search=%28PC255%29",
    "https://blog.f6s.com/feed/",
    "https://startupsavant.com/feed",
]


def probe(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
        ctype = r.headers.get("Content-Type", "")[:30]
        if r.status_code != 200:
            return (url, f"HTTP {r.status_code}", 0, ctype)
        feed = feedparser.parse(r.content)
        n = len(feed.entries)
        if n:
            return (url, "OK", n, feed.entries[0].get("link", "")[:70])
        return (url, "BO'SH", 0, ctype)
    except Exception as e:
        return (url, type(e).__name__, 0, str(e)[:40])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        for res in ex.map(probe, CANDIDATES):
            results.append(res)

    print("--- ISHLAYDI ---")
    for url, status, n, extra in results:
        if status == "OK":
            print(f"  {n:>4} ta  {url}\n           {extra}")
    print("\n--- ISHLAMAYDI ---")
    for url, status, n, extra in results:
        if status != "OK":
            print(f"  {status:<18} {url}")
