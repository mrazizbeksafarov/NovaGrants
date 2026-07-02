import os
import requests
import time
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

def split_message(text, max_length=4000):
    """Xabarni Telegram limitiga mos qilib (parchalab) ajratadi."""
    chunks = []
    while len(text) > max_length:
        split_index = text.rfind('\n\n', 0, max_length)
        if split_index == -1:
            split_index = text.rfind('\n', 0, max_length)
            if split_index == -1:
                split_index = max_length
        chunks.append(text[:split_index])
        text = text[split_index:].lstrip()
    if text:
        chunks.append(text)
    return chunks

def send_telegram_message(text, target_chat_id=None):
    """Telegram kanalga xabar yuborish (uzun bo'lsa bo'lib yuboradi)."""
    
    if not BOT_TOKEN or BOT_TOKEN == "your_telegram_bot_token_here" or not CHANNEL_ID:
        print("Telegram Token yoki Channel ID topilmadi. Xabar konsolga chiqariladi:")
        print("=" * 40)
        print(text)
        print("=" * 40)
        return True

    final_chat_id = target_chat_id if target_chat_id else CHANNEL_ID
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    
    chunks = split_message(text)
    overall_success = True
    
    for i, chunk in enumerate(chunks):
        payload = {
            "chat_id": final_chat_id,
            "text": chunk,
            "parse_mode": "HTML",
            "link_preview_options": {
                "url": "https://t.me/Nova_Grants",
                "prefer_large_media": True
            }
        }
        
        try:
            response = requests.post(url, json=payload, timeout=30)
            
            # Anti-spam: Handle 429 Too Many Requests explicitly
            if response.status_code == 429:
                retry_after = response.json().get("parameters", {}).get("retry_after", 5)
                print(f"⚠️ Telegram limiti (429). {retry_after} soniya kutamiz...")
                time.sleep(retry_after + 1)
                response = requests.post(url, json=payload, timeout=30)
                
            result = response.json()
            
            if result.get("ok"):
                print(f"✅ Xabar ({i+1}/{len(chunks)}) kanalga muvaffaqiyatli yuborildi!")
            else:
                error_desc = result.get("description", "Nomalum xatolik")
                print(f"❌ Telegram xatolik ({i+1}-qism): {error_desc}")
                
                # Agar HTML formatlashda xatolik bo'lsa, oddiy tekst sifatida qayta yuboramiz
                if "can't parse entities" in error_desc.lower():
                    print("HTML formatlash xatosi — oddiy tekst sifatida qayta yuborilmoqda...")
                    payload["parse_mode"] = None
                    if "parse_mode" in payload:
                        del payload["parse_mode"]
                    retry = requests.post(url, json=payload, timeout=30)
                    if retry.json().get("ok"):
                        print(f"✅ Xabar ({i+1}-qism) oddiy tekst sifatida yuborildi!")
                    else:
                        overall_success = False
                else:
                    overall_success = False
        except requests.Timeout:
            print("❌ Telegram API javob bermadi (timeout).")
            overall_success = False
        except Exception as e:
            print(f"❌ Telegram API ulanishida xatolik: {e}")
            overall_success = False
            
        # Xabarlar orasida Telegramni qiynamaslik uchun 3 soniya tanaffus qilinadi
        if i < len(chunks) - 1:
            time.sleep(3)
            
    return overall_success

if __name__ == "__main__":
    send_telegram_message("Assalomu alaykum! Bu test xabar.")
