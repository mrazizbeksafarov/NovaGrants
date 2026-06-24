import os
import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

def send_telegram_message(text, target_chat_id=None):
    """Telegram kanalga xabar yuborish. Pastda Nova_Grants preview ko'rsatiladi."""
    
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
        "link_preview_options": {
            "url": "https://t.me/Nova_Grants",
            "prefer_large_media": True
        }
    }
    
    try:
        response = requests.post(url, json=payload, timeout=30)
        result = response.json()
        
        if result.get("ok"):
            print("✅ Xabar kanalga muvaffaqiyatli yuborildi!")
            return True
        else:
            error_desc = result.get("description", "Nomalum xatolik")
            print(f"❌ Telegram xatolik: {error_desc}")
            
            # Agar HTML formatlashda xatolik bo'lsa, oddiy tekst sifatida qayta yuboramiz
            if "can't parse entities" in error_desc.lower():
                print("HTML formatlash xatosi — oddiy tekst sifatida qayta yuborilmoqda...")
                payload["parse_mode"] = None
                del payload["parse_mode"]
                retry = requests.post(url, json=payload, timeout=30)
                if retry.json().get("ok"):
                    print("✅ Xabar oddiy tekst sifatida yuborildi!")
                    return True
            return False
    except requests.Timeout:
        print("❌ Telegram API javob bermadi (timeout).")
        return False
    except Exception as e:
        print(f"❌ Telegram API ulanishida xatolik: {e}")
        return False

if __name__ == "__main__":
    send_telegram_message("Assalomu alaykum! Bu test xabar.")
