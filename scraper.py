import feedparser
import requests
from bs4 import BeautifulSoup
import re

# Manbalar ro'yxati (RSS va Telegram)
SOURCES = [
    # Mahalliy RSS (O'zbekiston)
    {"type": "rss", "url": "https://grantlar.uz/feed/"},
    
    # Xalqaro RSS (Startaplar va Global grantlar)
    {"type": "rss", "url": "https://opportunitydesk.org/feed"},
    {"type": "rss", "url": "https://www.youthop.com/feed"},
    {"type": "rss", "url": "https://www.scholarshipsads.com/feed"},
    {"type": "rss", "url": "https://opportunitiesforyouth.org/feed/"},
    
    # Mahalliy Telegram Kanallari (Startap va Ta'lim)
    {"type": "telegram", "channel": "edugrantsuz"},
    {"type": "telegram", "channel": "grantlar"},
    {"type": "telegram", "channel": "erasmus_uz"},
    {"type": "telegram", "channel": "grantsuzb"}
]

def scrape_rss(url):
    grants = []
    try:
        feed = feedparser.parse(url)
        # Oxirgi 5 ta eng yangi grantlarni olamiz
        for entry in feed.entries[:5]:
            grant_id = entry.get("id", entry.get("link"))
            title = entry.get("title", "")
            link = entry.get("link", "")
            summary = entry.get("summary", "")
            
            # HTML teglarni tozalash (agar kerak bo'lsa)
            clean_summary = BeautifulSoup(summary, "html.parser").get_text(separator="\n").strip() if summary else title
            
            grants.append({
                "id": grant_id,
                "title": title,
                "url": link,
                "summary": clean_summary[:1000] # Maksimal 1000 belgi
            })
    except Exception as e:
        print(f"RSS xatolik ({url}): {e}")
    return grants

def scrape_telegram(channel_username):
    grants = []
    url = f"https://t.me/s/{channel_username}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            # Telegram post xabarlarini topamiz
            messages = soup.find_all('div', class_='tgme_widget_message_text')
            dates = soup.find_all('a', class_='tgme_widget_message_date')
            
            # Eng oxirgi 5 ta postni olamiz
            for msg, date_tag in zip(messages[-5:], dates[-5:]):
                msg_text = msg.get_text(separator="\n", strip=True)
                
                # Agar post juda qisqa bo'lsa, uni o'tkazib yuboramiz (faqat rasm bo'lishi mumkin)
                if len(msg_text) < 50:
                    continue
                
                # Post ID va Linkni olish
                post_link = date_tag.get("href") if date_tag else f"https://t.me/{channel_username}"
                post_id = post_link
                
                # Sarlavhani ajratib olish (birinchi qator yoki birinchi 50 belgi)
                lines = msg_text.split('\n')
                title = lines[0] if len(lines) > 0 else "Kanal yangiligi"
                if len(title) > 80:
                    title = title[:77] + "..."
                
                grants.append({
                    "id": post_id,
                    "title": f"[{channel_username}] {title}",
                    "url": post_link,
                    "summary": msg_text[:1000]
                })
    except Exception as e:
        print(f"Telegram Web xatolik ({channel_username}): {e}")
    
    return grants

def fetch_grants():
    all_grants = []
    print("Ma'lumotlar yig'ilmoqda...")
    
    for source in SOURCES:
        if source["type"] == "rss":
            # print(f"RSS o'qilmoqda: {source['url']}")
            grants = scrape_rss(source["url"])
            all_grants.extend(grants)
        elif source["type"] == "telegram":
            # print(f"Telegram o'qilmoqda: @{source['channel']}")
            grants = scrape_telegram(source["channel"])
            all_grants.extend(grants)
            
    return all_grants

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    grants = fetch_grants()
    print(f"\nJami topilgan ma'lumotlar soni: {len(grants)}\n")
    if grants:
        print("Namuna (1-grant):")
        print(f"Sarlavha: {grants[-1]['title']}")
        print(f"Havola: {grants[-1]['url']}")
        print(f"Qisqacha: {grants[-1]['summary'][:100]}...")
