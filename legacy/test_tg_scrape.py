import requests
from bs4 import BeautifulSoup

def test_telegram_scrape(channel_username):
    url = f"https://t.me/s/{channel_username}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    try:
        res = requests.get(url, headers=headers)
        if res.status_code != 200:
            print(f"Failed with status: {res.status_code}")
            return
            
        soup = BeautifulSoup(res.text, 'html.parser')
        messages = soup.find_all('div', class_='tgme_widget_message_text')
        
        print(f"Topilgan xabarlar soni: {len(messages)}")
        for i, msg in enumerate(messages[-3:]): # Ohirgi 3 ta
            print(f"\n--- Xabar {i+1} ---")
            print(msg.text[:200] + "...")
            
    except Exception as e:
        print(f"Xatolik: {e}")

if __name__ == "__main__":
    test_telegram_scrape("edugrandsuz")
