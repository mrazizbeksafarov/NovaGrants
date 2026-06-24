import time
import schedule
from database import init_db, is_grant_posted, mark_grant_posted
from scraper import fetch_grants
from ai_agent import format_multiple_grants_post
from telegram_bot import send_telegram_message

def job():
    print("Yangi grantlarni tekshirmoqda...")
    grants = fetch_grants()
    
    unposted_grants = []
    for grant in grants:
        if not is_grant_posted(grant['url']):
            unposted_grants.append(grant)
            if len(unposted_grants) >= 5: # BATCH_SIZE = 5
                break
                
    if unposted_grants:
        print(f"{len(unposted_grants)} ta yangi grant topildi. Dayjest tayyorlanmoqda...")
        post_text = format_multiple_grants_post(unposted_grants)
        
        success = send_telegram_message(post_text)
        if success:
            for g in unposted_grants:
                mark_grant_posted(g['title'], g['url'])
            print(f"Baza yangilandi: {len(unposted_grants)} ta grant saqlandi.")
        else:
            print("Xabar yuborilmadi, keyingi safar qayta urinib ko'riladi.")
    else:
        print("Hozircha yangi o'qilmagan grantlar yo'q.")

def main():
    # Bazani tayyorlash
    init_db()
    
    print("Agent ishga tushdi. Dastlabki tekshiruv...")
    job() # Bir marta darhol ishlatamiz
    
    # Haftada 2 marta ishlash uchun sozlaymiz (Chorshanba va Shanba kunlari)
    schedule.every().wednesday.at("10:00").do(job)
    schedule.every().saturday.at("10:00").do(job)
    print("Kutish rejimiga o'tildi (Har Chorshanba va Shanba 10:00 da tekshiriladi). Chiqish uchun Ctrl+C bosing.")
    
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)
        except KeyboardInterrupt:
            print("\nAgent ishlashdan to'xtatildi.")
            break

if __name__ == "__main__":
    main()
