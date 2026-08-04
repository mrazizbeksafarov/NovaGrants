import os
import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

new_description = """
🌍 Nova Grants — dunyodagi eng nufuzli ta'lim grantlari, yirik stipendiyalar, xalqaro stajirovkalar va startap dasturlari haqidagi 1-raqamli platforma!

🎯 Biz har kuni yuzlab xalqaro manbalarni kuzatib, siz uchun faqat eng ishonchli va daromadli imkoniyatlarni saralab beramiz. 

🚀 Katta imkoniyatlar sari qadam tashlang!
Biz bilan birga o'z kelajagingizni quring.
"""

url = f"https://api.telegram.org/bot{BOT_TOKEN}/setChatDescription"
payload = {
    "chat_id": CHANNEL_ID,
    "description": new_description.strip()
}

response = requests.post(url, json=payload)
print("Telegram API Response:", response.json())
