from scraper import fetch_grants
from ai_agent import format_grant_post
from telegram_bot import send_telegram_message

def test_single_post():
    print("Grantlar olinmoqda...")
    grants = fetch_grants()
    if not grants:
        print("Hech qanday grant topilmadi!")
        return
        
    # Matnlarni konsolga chiqarmaymiz, chunki Windows cp1252 da emoji va belgilarda xato beradi
    print("Topilgan grant AI ga uzatilmoqda...")
    
    post_text = format_grant_post(grants[0])
    
    print("Shaxsiy chatga yuborilmoqda...")
    send_telegram_message(post_text, target_chat_id="7987189270")
    print("Test yakunlandi.")

if __name__ == "__main__":
    test_single_post()
