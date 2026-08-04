"""2-bosqich: grants.gov API, HTML ro'yxat sahifalari, qo'shimcha RSS va Telegram kanallar."""

import sys, os, json, re, concurrent.futures
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests, feedparser
from bs4 import BeautifulSoup

H = {"User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
     "Accept": "application/rss+xml, application/xml, text/html;q=0.9, */*;q=0.8"}

MORE_RSS = [
    "https://www.opportunitiesforafricans.com/feed/",
    "https://opportunitydesk.org/feed/",
    "https://www.unigo.com/rss",
    "https://www.scholarshipportal.com/rss",
    "https://scholarshipowl.com/blog/feed/",
    "https://www.internationalscholarships.com/rss",
    "https://www.scholarshipsinusa.com/feed/",
    "https://scholarshipregion.com/feed/",
    "https://www.scholarshipscafe.com/feed/",
    "https://freeeducator.com/feed/",
    "https://scholarshipfellow.com/feed/",
    "https://www.opportunitydesk.info/feed/",
    "https://opportunitiesforafricans.com/feed",
    "https://www.youthvillage.co.za/feed/",
    "https://www.msu.ac.zw/feed/",
    "https://fellowshipbard.com/feed/",
    "https://www.grantforwomen.com/feed/",
    "https://ngofundinghub.com/feed/",
    "https://www.fundsforngos.org/feed/",
    "https://ngosource.org/feed",
    "https://www.developmentaid.org/feed",
    "https://reliefweb.int/updates/rss.xml",
    "https://www.eu-startups.com/feed/",
    "https://startupgrind.com/feed/",
    "https://www.f6s.com/rss",
    "https://sciencegrants.org/feed/",
    "https://researchprofessionalnews.com/feed/",
    "https://www.natureindex.com/rss",
    "https://phdportal.com/rss",
    "https://www.mastersportal.com/rss",
    "https://euraxess.ec.europa.eu/rss.xml",
    "https://www.eurekalert.org/rss/grants.xml",
    "https://www.insidehighered.com/rss.xml",
    "https://www.timeshighereducation.com/feeds/rss/news",
    "https://www.studyineurope.eu/feed",
    "https://www.studying-in-germany.org/feed/",
    "https://www.studyinjapan.go.jp/en/rss.xml",
    "https://www.studyinkorea.go.kr/rss",
    "https://www.turkiyeburslari.gov.tr/rss",
    "https://uzedu.uz/rss",
    "https://edu.uz/rss",
    "https://yoshlar.gov.uz/rss",
    "https://kun.uz/uz/news/rss",
]

TG_CHANNELS = [
    "scholarshipsads", "opportunitydesk", "opportunities_corners", "scholarship_positions",
    "grantsandscholarships", "worldscholarshipforum", "scholarshipregion", "globalopportunities",
    "opportunitycell", "youthopportunities", "chanceforyouth", "internationalopportunities",
    "scholarshipcorner", "grantsuz", "stipendiya_uz", "erasmusuz", "study_abroad_uz",
    "uzbekistan_grants", "imkoniyat_uz", "talabalar_uz", "bilimdon_uz", "grant_uz",
    "itparkuz", "startup_uz", "uzvc", "aloqaventures", "udevs_news",
]


def probe_rss(url):
    try:
        r = requests.get(url, headers=H, timeout=20, allow_redirects=True)
        if r.status_code != 200:
            return (url, f"HTTP {r.status_code}", 0, "")
        f = feedparser.parse(r.content)
        if f.entries:
            return (url, "OK", len(f.entries), f.entries[0].get("link", "")[:70])
        return (url, "BO'SH", 0, "")
    except Exception as e:
        return (url, type(e).__name__, 0, "")


def probe_tg(ch):
    try:
        r = requests.get(f"https://t.me/s/{ch}", headers=H, timeout=20)
        if r.status_code != 200:
            return (ch, f"HTTP {r.status_code}", 0, "")
        soup = BeautifulSoup(r.text, "html.parser")
        msgs = soup.find_all("div", class_="tgme_widget_message_text")
        if not msgs:
            return (ch, "PREVIEW YO'Q", 0, "")
        ext = [a["href"] for a in soup.select("div.tgme_widget_message_text a[href^='http']")
               if "t.me" not in a["href"]]
        title = soup.select_one("div.tgme_channel_info_header_title")
        return (ch, "OK", len(msgs), f"{len(ext)} havola | {title.get_text(strip=True) if title else ''}"[:60])
    except Exception as e:
        return (ch, type(e).__name__, 0, "")


def probe_grants_gov_api():
    print("\n=== grants.gov rasmiy API ===")
    try:
        r = requests.post("https://api.grants.gov/v1/api/search2",
                          json={"rows": 10, "keyword": "", "oppNum": "", "eligibilities": "",
                                "agencies": "", "oppStatuses": "posted", "aln": "", "fundingCategories": ""},
                          headers={"Content-Type": "application/json"}, timeout=25)
        print("  status:", r.status_code)
        d = r.json()
        hits = d.get("data", {}).get("oppHits", [])
        print("  jami topildi:", d.get("data", {}).get("hitCount"))
        for h in hits[:5]:
            print(f"    [{h.get('id')}] {h.get('title','')[:60]} | yopiladi: {h.get('closeDate')}")
        print("  havola namunasi: https://grants.gov/search-results-detail/" + str(hits[0].get("id")) if hits else "")
    except Exception as e:
        print("  XATO:", type(e).__name__, str(e)[:120])


def probe_html_listing(url, link_sel):
    try:
        r = requests.get(url, headers=H, timeout=25)
        soup = BeautifulSoup(r.text, "html.parser")
        links = soup.select(link_sel)
        hrefs = []
        for a in links:
            h = a.get("href", "")
            if h.startswith("http") and h not in hrefs:
                hrefs.append(h)
        print(f"  {url}\n    HTTP {r.status_code}, {len(r.text)} bayt, {len(hrefs)} havola")
        for h in hrefs[:3]:
            print(f"      {h[:90]}")
    except Exception as e:
        print(f"  {url}\n    XATO: {type(e).__name__} {str(e)[:60]}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")

    probe_grants_gov_api()

    print("\n=== HTML ro'yxat sahifalari (RSS o'lgan saytlar) ===")
    probe_html_listing("https://www.scholars4dev.com/category/scholarships/", "h2 a, h3 a, .entry-title a")
    probe_html_listing("https://www.afterschoolafrica.com/category/scholarships/", "h2 a, h3 a, .entry-title a")
    probe_html_listing("https://philanthropynewsdigest.org/rfps", "a[href*='/rfps/']")

    print("\n=== Qo'shimcha RSS ===")
    res = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        for x in ex.map(probe_rss, MORE_RSS):
            res.append(x)
    for url, st, n, s in res:
        if st == "OK":
            print(f"  OK {n:>4} ta  {url}\n              {s}")

    print("\n=== Telegram kanallar ===")
    tres = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        for x in ex.map(probe_tg, TG_CHANNELS):
            tres.append(x)
    for ch, st, n, s in tres:
        if st == "OK":
            print(f"  OK  {ch:<28} {n:>3} post | {s}")
    print("  --- ishlamaydi ---")
    print("  " + ", ".join(ch for ch, st, n, s in tres if st != "OK"))
