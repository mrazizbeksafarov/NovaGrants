import feedparser
import requests
from bs4 import BeautifulSoup
import re

SOURCES = [
    # 🎓 1. Global Ta'lim va Yoshlar Grantlari (Mega Baza)
    {"type": "rss", "url": "https://www.scholars4dev.com/feed/"},
    {"type": "rss", "url": "https://opportunitydesk.org/feed"},
    {"type": "rss", "url": "https://www.youthop.com/feed"},
    {"type": "rss", "url": "https://opportunitiescorners.com/feed/"},
    {"type": "rss", "url": "https://scholarshiproar.com/feed/"},
    {"type": "rss", "url": "https://www.wemakescholars.com/blog/feed"},
    {"type": "rss", "url": "https://scholarshipdb.net/scholarships?q=&rss=1"},
    {"type": "rss", "url": "https://scholarship-positions.com/feed/"},
    {"type": "rss", "url": "https://www.advance-africa.com/advance-africa.xml"},
    {"type": "rss", "url": "https://oyaop.com/feed/"},
    {"type": "rss", "url": "https://opportunitiesforyouth.org/feed/"},

    # 🌍 2. Mintaqaviy Gigantlar (Yevropa, Osiyo, Afrika, MENA)
    {"type": "rss", "url": "https://www.opportunitiesforafricans.com/feed/"},
    {"type": "rss", "url": "https://afterschoolafrica.com/feed/"},
    {"type": "rss", "url": "https://www.salto-youth.net/tools/european-training-calendar/rss/"},
    {"type": "rss", "url": "https://opportunitiescircle.com/feed/"},
    {"type": "rss", "url": "https://www.heysuccess.com/blog/feed"},

    # 👑 3. Nufuzli Fellowship va Liderlik dasturlari
    {"type": "rss", "url": "https://www.profellow.com/feed/"},
    {"type": "rss", "url": "https://armacad.info/rss"},
    {"type": "rss", "url": "http://www.mladiinfo.eu/feed/"},

    # 🚀 4. Startaplar, Akseleratorlar va Investitsiyalar (VC)
    {"type": "rss", "url": "https://techcrunch.com/category/startups/feed/"},
    {"type": "rss", "url": "https://blog.ycombinator.com/feed/"},
    {"type": "rss", "url": "https://news.crunchbase.com/feed/"},
    {"type": "rss", "url": "https://wellfound.com/blog/feed"},
    {"type": "rss", "url": "https://www.eu-startups.com/feed/"},
    {"type": "rss", "url": "https://sifted.eu/feed/"},
    {"type": "rss", "url": "https://www.wamda.com/feed"},
    {"type": "rss", "url": "https://disrupt-africa.com/feed/"},
    {"type": "rss", "url": "https://e27.co/feed/"},
    {"type": "rss", "url": "https://www.dealstreetasia.com/feed/"},
    {"type": "rss", "url": "https://www.techinasia.com/feed"},
    {"type": "rss", "url": "https://magazine.startus.cc/feed/"},
    {"type": "rss", "url": "https://blog.gust.com/feed/"},

    # 🎨🔬 5. Maxsus Yo'nalishlar (Ayollar, San'at, Ilm-fan)
    {"type": "rss", "url": "https://philanthropywomen.org/feed/"},
    {"type": "rss", "url": "https://awdf.org/feed/"},
    {"type": "rss", "url": "https://www.arts.gov/rss.xml"},
    {"type": "rss", "url": "https://www.ukri.org/feed/"},
    {"type": "rss", "url": "https://terravivagrants.org/feed/"},
    {"type": "rss", "url": "https://www.grants.gov/rss/GG_OppModByCategory.xml"},

    # 🤝 6. Ijtimoiy Loyihalar va NGO Grantlari
    {"type": "rss", "url": "https://www.fundsforngos.org/feed/"},
    {"type": "rss", "url": "https://www.grants.gov/rss"},
    {"type": "rss", "url": "https://www.devex.com/news/rss"},

    # 🇺🇿 Mahalliy RSS (O'zbekiston)
    {"type": "rss", "url": "https://grantlar.uz/feed/"},

    # 📱 Mahalliy Telegram Kanallari (Startap va Ta'lim)
    {"type": "telegram", "channel": "edugrandsuz"},
    {"type": "telegram", "channel": "grantlar"},
    {"type": "telegram", "channel": "erasmus_uz"},
    {"type": "telegram", "channel": "grantsuzb"},
    {"type": "telegram", "channel": "startupbaseuz"},
    {"type": "telegram", "channel": "itpark_uz"},
    {"type": "telegram", "channel": "yoshlaragentligi"},
    {"type": "telegram", "channel": "uzvc_uz"},
    {"type": "telegram", "channel": "aloqaventures"},
    {"type": "telegram", "channel": "startupmix"},
    {"type": "telegram", "channel": "udevs_news"},
    {"type": "telegram", "channel": "udevs_jobs"},

    # 🌐 Yangi Global RSS Manbalar (Tech/VC)
    {"type": "rss", "url": "https://techcrunch.com/funding/feed/"},
    {"type": "rss", "url": "https://new.nsf.gov/rss"},
    {"type": "rss", "url": "http://firstround.com/review/feed.xml"},
    {"type": "rss", "url": "http://vccafe.com/feed/"},
    {"type": "rss", "url": "https://news.ycombinator.com/rss"},

    # 🌐 Yangi Global Telegram Kanallar
    {"type": "telegram", "channel": "theglobalscholarship"},
    {"type": "telegram", "channel": "opportunitiescorners"},
    {"type": "telegram", "channel": "startups"},
    {"type": "telegram", "channel": "solofounders"}
]

def scrape_rss(url):
    grants = []
    try:
        feed = feedparser.parse(url)
        # Oxirgi 20 ta eng yangi grantlarni olamiz
        for entry in feed.entries[:20]:
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
            
            # Eng oxirgi 20 ta postni olamiz
            for msg, date_tag in zip(messages[-20:], dates[-20:]):
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

def fetch_single_source(source):
    if source["type"] == "rss":
        return scrape_rss(source["url"])
    elif source["type"] == "telegram":
        return scrape_telegram(source["channel"])
    return []

def fetch_grants():
    all_grants = []
    print(f"Ma'lumotlar yig'ilmoqda... Jami manbalar: {len(SOURCES)}")
    
    import concurrent.futures
    # 10 ta parallel oqimda (thread) ishlatish
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_source = {executor.submit(fetch_single_source, src): src for src in SOURCES}
        
        for future in concurrent.futures.as_completed(future_to_source):
            src = future_to_source[future]
            try:
                data = future.result()
                if data:
                    all_grants.extend(data)
            except Exception as exc:
                name = src.get('url') or src.get('channel')
                print(f"{name} manbasini o'qishda kutilmagan xatolik: {exc}")
                
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
