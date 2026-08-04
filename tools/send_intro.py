import os
import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

text = """
🚀 <b>Diqqat! Nova Grants loyihasi rasman yangi bosqichga ko'tarildi!</b>

Endilikda ushbu kanalda maxsus <b>Sun'iy Intellekt (AI)</b> tizimi ishga tushirildi. U tun-u kun dunyoning 50 dan ortiq eng yirik grant platformalarini (Yevropa, AQSh, Osiyo, startap fondlari va nufuzli universitetlar) bevosita kuzatib boradi.

🎯 Bizning aqlli tizim faqat <b>O'zbekistonliklar va xalqaro nomzodlar</b> qatnashishi mumkin bo'lgan eng daromadli va foydali imkoniyatlarni saralab, haftada 2 marta chiroyli <b>"Haftalik Dayjest" (To'plam)</b> ko'rinishida e'lon qilib boradi!

🔥 Biz bilan qoling, eng katta ta'lim va investitsiya imkoniyatlari endi e'tiboringizdan chetda qolmaydi!

@Nova_Grants
"""

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
payload = {
    "chat_id": CHANNEL_ID,
    "text": text,
    "parse_mode": "HTML"
}

response = requests.post(url, json=payload)
print("Telegram javobi:", response.json())
