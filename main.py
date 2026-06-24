import os
from datetime import datetime, timezone
from database import init_db, is_grant_posted, mark_grant_posted
from scraper import fetch_grants
from ai_agent import format_multiple_grants_post
from telegram_bot import send_telegram_message

def job():
    """Yangi grantlarni topib, AI orqali formatlash va kanalga yuborish."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Yangi grantlarni tekshirmoqda...")
    
    try:
        grants = fetch_grants()
    except Exception as e:
        print(f"Grantlarni yig'ishda xatolik: {e}")
        return
    
    if not grants:
        print("Hech qanday grant topilmadi (manbalar bilan muammo bo'lishi mumkin).")
        return
    
    # Faqat hali yuborilmagan (yangi) grantlarni ajratib olamiz
    unposted_grants = []
    for grant in grants:
        if not is_grant_posted(grant['url']):
            unposted_grants.append(grant)
            if len(unposted_grants) >= 5:  # Bitta postda 5 ta grant
                break
                
    if unposted_grants:
        print(f"{len(unposted_grants)} ta yangi grant topildi. Post tayyorlanmoqda...")
        
        try:
            post_text = format_multiple_grants_post(unposted_grants)
        except Exception as e:
            print(f"AI formatlashda xatolik: {e}")
            return
        
        success = send_telegram_message(post_text)
        if success:
            for g in unposted_grants:
                mark_grant_posted(g['title'], g['url'])
            print(f"Baza yangilandi: {len(unposted_grants)} ta grant saqlandi.")
        else:
            print("Xabar yuborilmadi, keyingi safar qayta urinib ko'riladi.")
    else:
        print("Hozircha yangi grant yo'q. Hammasi allaqachon yuborilgan.")

def run():
    """Asosiy ishga tushirish funksiyasi (GitHub Actions orqali chaqiriladi)."""
    init_db()
    
    print("=" * 50)
    print("Nova Grants Bot (GitHub Actions) ishga tushdi!")
    print(f"Hozirgi vaqt (UTC): {datetime.now(timezone.utc).isoformat()}")
    print("=" * 50)
    
    job()
    print("Vazifa yakunlandi. Dastur to'xtatildi.")

if __name__ == "__main__":
    run()
