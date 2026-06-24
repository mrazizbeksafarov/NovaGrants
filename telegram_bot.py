import os
import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

def send_telegram_message(text, target_chat_id=None):
    if not BOT_TOKEN or BOT_TOKEN == "your_telegram_bot_token_here" or not CHANNEL_ID:
        print("Telegram Token yoki Channel ID topilmadi. Xabar konsolga chiqariladi:")
        print("=" * 40)
        print(text)
        print("=" * 40)
        return True

    final_chat_id = target_chat_id if target_chat_id else CHANNEL_ID
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": final_chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("Xabar kanalga muvaffaqiyatli yuborildi!")
            return True
        else:
            print(f"Xabar yuborishda xatolik: {response.text}")
            return False
    except Exception as e:
        print(f"Telegram API ulanishida xatolik: {e}")
        return False

if __name__ == "__main__":
    send_telegram_message("Assalomu alaykum! Bu test xabar.")
