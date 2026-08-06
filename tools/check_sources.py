"""Manbalarni jonli tekshirish: qaysi feed/kanal ishlaydi, nechta yozuv beradi.

Ishlatish:
    python tools/check_sources.py
"""

import sys
import os
import concurrent.futures

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import feedparser
import requests
from bs4 import BeautifulSoup

from sources import SOURCES

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


def check_rss(src):
    url = src["url"]
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return (src["id"], "HTTP " + str(r.status_code), 0, "")
        feed = feedparser.parse(r.content)
        n = len(feed.entries)
        sample = feed.entries[0].get("link", "") if n else ""
        if n == 0:
            return (src["id"], "BO'SH", 0, (r.text[:60].replace("\n", " ")))
        return (src["id"], "OK", n, sample)
    except Exception as e:
        return (src["id"], type(e).__name__, 0, str(e)[:60])


def check_telegram(src):
    ch = src["channel"]
    try:
        r = requests.get(f"https://t.me/s/{ch}", headers=HEADERS, timeout=20)
        if r.status_code != 200:
            return (src["id"], "HTTP " + str(r.status_code), 0, "")
        soup = BeautifulSoup(r.text, "html.parser")
        msgs = soup.find_all("div", class_="tgme_widget_message_text")
        links = soup.select("div.tgme_widget_message_text a[href^='http']")
        ext = [a["href"] for a in links if "t.me" not in a["href"]]
        if not msgs:
            return (src["id"], "PREVIEW YO'Q", 0, "")
        return (src["id"], "OK", len(msgs), f"{len(ext)} ta tashqi havola")
    except Exception as e:
        return (src["id"], type(e).__name__, 0, str(e)[:60])


def check_grantsgov(src):
    try:
        r = requests.post(src["url"], json={"rows": 5, "keyword": "", "oppStatuses": "posted"},
                          headers={**HEADERS, "Content-Type": "application/json"}, timeout=20)
        hits = r.json().get("data", {}).get("oppHits", [])
        return (src["id"], "OK" if hits else "BO'SH", len(hits), "")
    except Exception as e:
        return (src["id"], type(e).__name__, 0, str(e)[:60])


def check(src):
    # Ilgari bu yerda `rss` bo'lmagan hamma narsa telegram deb hisoblanardi va
    # grants.gov yozuvida `KeyError: 'channel'` bilan butun skript qulardi.
    fn = {"rss": check_rss, "telegram": check_telegram, "grantsgov": check_grantsgov}
    handler = fn.get(src.get("type"))
    if not handler:
        return (src["id"], f"NOMA'LUM TUR: {src.get('type')}", 0, "")
    try:
        return handler(src)
    except Exception as e:
        return (src["id"], type(e).__name__, 0, str(e)[:60])


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"{len(SOURCES)} ta manba tekshirilmoqda...\n")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        for res in ex.map(check, SOURCES):
            results.append(res)

    ok = [r for r in results if r[1] == "OK"]
    bad = [r for r in results if r[1] != "OK"]

    print(f"--- ISHLAYDI ({len(ok)}) ---")
    for sid, status, n, sample in sorted(ok, key=lambda x: -x[2]):
        print(f"  {sid:<20} {n:>4} ta   {sample[:70]}")

    print(f"\n--- ISHLAMAYDI ({len(bad)}) ---")
    for sid, status, n, sample in bad:
        print(f"  {sid:<20} {status:<18} {sample[:60]}")
