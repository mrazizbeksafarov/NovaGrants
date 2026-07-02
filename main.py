import os
from datetime import datetime, timezone
from database import (
    init_db, get_posted_urls, mark_grant_posted, 
    get_grants_nearing_deadline, mark_reminder_sent
)
from scraper import fetch_grants
from ai_agent import format_multiple_grants_post
from telegram_bot import send_telegram_message

def process_reminders():
    """Eslatmalarni (deadlinelarni) tekshirib yuborish."""
    print("Deadline'ga yaqin qolgan grantlarni tekshirmoqda...")
    grants = get_grants_nearing_deadline(days=5)
    
    if not grants:
        print("Bugun uchun eslatma yuboriladigan grantlar yo'q.")
        return

    print(f"{len(grants)} ta eslatma topildi. Yuborilmoqda...")
    
    reminder_text = "🔴 <b>Shoshiling! Oxirgi muddat yaqinlashmoqda!</b>\n\n"
    reminder_text += "Quyidagi grantlar uchun hujjat topshirish muddati tez orada tugaydi. Imkoniyatni qo'ldan boy bermang:\n\n"
    
    for i, g in enumerate(grants):
        title = g.get('title', 'Nomalum Grant')
        url = g.get('url', '#')
        deadline = g.get('deadline', 'Nomalum').split('T')[0] # Faqat sana qismi
        
        reminder_text += f"{i+1}. <b><a href='{url}'>{title}</a></b>\n"
        reminder_text += f"⏰ <i>Oxirgi muddat: {deadline}</i>\n\n"
        
    reminder_text += "👉 Zudlik bilan rasmiy saytlariga o'tib ariza topshiring!\n\n@Nova_Grants"
    
    success = send_telegram_message(reminder_text)
    if success:
        for g in grants:
            mark_reminder_sent(g['url'])
        print("Eslatma muvaffaqiyatli yuborildi.")
    else:
        print("Eslatmani yuborishda xatolik.")

def job():
    """Yangi grantlarni topib, AI orqali formatlash va kanalga yuborish."""
    print(f"[{datetime.now(timezone.utc).isoformat()}] Yangi grantlarni tekshirmoqda...")
    
    try:
        grants = fetch_grants()
    except Exception as e:
        print(f"Grantlarni yig'ishda xatolik: {e}")
        return
    
    if not grants:
        print("Hech qanday grant topilmadi (manbalar bilan muammo).")
        return
    
    all_urls = [g['url'] for g in grants]
    posted_urls = get_posted_urls(all_urls)
    
    unposted_grants = [g for g in grants if g['url'] not in posted_urls]
                
    if unposted_grants:
        print(f"{len(unposted_grants)} ta yangi grant topildi. Post tayyorlanmoqda (10 tadan)...")
        
        chunk_size = 10
        total_saved = 0
        for i in range(0, len(unposted_grants), chunk_size):
            batch = unposted_grants[i:i+chunk_size]
            print(f"Betch ({i//chunk_size + 1}): {len(batch)} ta grant AI ga yuborilmoqda...")
            
            try:
                ai_data = format_multiple_grants_post(batch)
            except Exception as e:
                print(f"AI formatlashda xatolik: {e}")
                continue
                
            if not ai_data or "post_text" not in ai_data:
                print("AI dan noto'g'ri javob keldi. O'tkazib yuborilmoqda...")
                continue
                
            post_text = ai_data["post_text"]
            deadlines_list = ai_data.get("deadlines", [])
            
            deadline_map = {d.get("url"): d.get("deadline_iso") for d in deadlines_list if type(d) is dict}
            
            success = send_telegram_message(post_text)
            if success:
                for g in batch:
                    d_iso = deadline_map.get(g['url'])
                    mark_grant_posted(g['title'], g['url'], deadline_iso=d_iso)
                    total_saved += 1
            else:
                print("Xabar yuborilmadi, bu batch keyingi safar qayta urinib ko'riladi.")
                
        print(f"Baza yangilandi: {total_saved} ta grant saqlandi.")
    else:
        print("Hozircha yangi grant yo'q.")

def run():
    init_db()
    print("=" * 50)
    print("Nova Grants Bot (GitHub Actions) ishga tushdi!")
    print("=" * 50)
    
    # 1. Oldin eslatmalarni yuboramiz
    process_reminders()
    
    print("-" * 50)
    
    # 2. Keyin yangi grantlarni qidiramiz
    job()
    
    print("Vazifa yakunlandi.")

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    run()
