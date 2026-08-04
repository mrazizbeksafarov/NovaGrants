import os
import requests
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = "@Nova_Grants"

def test_direct():
    print("Kanalga to'g'ridan-to'g'ri xabar yuborib ko'ramiz (Sign Messages yoniq holatida)...")
    text = "🚀 To'g'ridan to'g'ri test: <tg-emoji emoji-id=\"5897792062291449826\">⭐</tg-emoji> Premium Emoji Ishladimi?"
    
    send_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    res = requests.post(send_url, json={
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML"
    })
    
    if res.json().get("ok"):
        print("Muvaffaqiyatli yuborildi! Kanalni tekshiring.")
    else:
        print("Xatolik:", res.json())

if __name__ == "__main__":
    test_direct()
