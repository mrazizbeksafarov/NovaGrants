import time
import threading
import os
import schedule
from flask import Flask
from database import init_db, is_grant_posted, mark_grant_posted
from scraper import fetch_grants
from ai_agent import format_multiple_grants_post
from telegram_bot import send_telegram_message

# Render uchun "Soxta Veb-sayt"
app = Flask(__name__)

@app.route('/')
def home():
    return "<h1>GrantBot is running smoothly in the background! 🚀</h1>"

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

def run_schedule():
    # Bazani tayyorlash
    init_db()
    
    print("Bot Orqa Fonda (Background) ishga tushdi. Dastlabki tekshiruv...")
    job() # Bir marta darhol ishlatamiz
    
    # Haftada 2 marta ishlash uchun sozlaymiz (Chorshanba va Shanba kunlari)
    schedule.every().wednesday.at("10:00").do(job)
    schedule.every().saturday.at("10:00").do(job)
    print("Kutish rejimiga o'tildi (Har Chorshanba va Shanba 10:00 da tekshiriladi).")
    
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    # 1. Botni alohida "Thread" (Parallel oqim) ga o'tkazib ishga tushiramiz
    t = threading.Thread(target=run_schedule)
    t.daemon = True # Asosiy dastur o'chsa, bu ham o'chadi
    t.start()
    
    # 2. Asosiy oqimda (Main Thread) Flask web-serverni ishga tushiramiz (Render uchun)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
