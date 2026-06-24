import time
import threading
import os
import schedule
from datetime import datetime, timezone, timedelta
from flask import Flask
from database import init_db, is_grant_posted, mark_grant_posted, get_last_post_time
from scraper import fetch_grants
from ai_agent import format_multiple_grants_post
from telegram_bot import send_telegram_message

# Render uchun Flask veb-server (Render tekin rejimda port tinglashi shart)
app = Flask(__name__)

@app.route('/')
def home():
    return "<h1>Nova Grants Bot ishlayapti! ✅</h1><p>Har kuni soat 10:00 (UZT) da yangi grantlar e'lon qilinadi.</p>"

@app.route('/health')
def health():
    return "OK", 200

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

def should_run_on_startup():
    """
    Render har safar qayta ishga tushganda (deploy, restart, wake-up) 
    post yubormaslik uchun: oxirgi post vaqtini tekshiramiz.
    Agar oxirgi 6 soat ichida post yuborilgan bo'lsa — YUBORMAYMIZ.
    """
    last_time = get_last_post_time()
    if last_time is None:
        # Bazada hech qanday yozuv yo'q — birinchi marta ishga tushyapti
        print("Bazada hali hech qanday grant yo'q. Birinchi postni tayyorlaymiz...")
        return True
    
    now = datetime.now(timezone.utc)
    hours_since_last = (now - last_time).total_seconds() / 3600
    print(f"Oxirgi post {hours_since_last:.1f} soat oldin yuborilgan.")
    
    if hours_since_last < 6:
        print("Oxirgi 6 soat ichida post yuborilgan. Takroriy post yuborilmaydi.")
        return False
    else:
        print("6 soatdan ko'proq vaqt o'tgan. Yangi grantlarni tekshiramiz...")
        return True

def run_schedule():
    """Bot jadvalini ishga tushirish."""
    init_db()
    
    print("=" * 50)
    print("Nova Grants Bot ishga tushdi!")
    print(f"Hozirgi vaqt (UTC): {datetime.now(timezone.utc).isoformat()}")
    print("=" * 50)
    
    # Faqat zarur bo'lsa dastlabki postni yuboramiz
    if should_run_on_startup():
        job()
    
    # Har kuni ertalab soat 10:00 (O'zbekiston vaqti = UTC 05:00) da tekshiramiz
    schedule.every().day.at("05:00").do(job)
    print("Jadval o'rnatildi: Har kuni soat 10:00 (UZT) da grantlar tekshiriladi.")
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    # 1. Botni alohida thread'da ishga tushiramiz
    t = threading.Thread(target=run_schedule)
    t.daemon = True
    t.start()
    
    # 2. Flask web-serverni ishga tushiramiz (Render uchun)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
