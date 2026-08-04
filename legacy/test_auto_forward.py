import os
import requests
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
USER_CHAT_ID = "7987189270"
CHANNEL_ID = "@Nova_Grants"

def test_auto_forward():
    print("1. Bot xabarni avval Damingizga yubormoqda...")
    text = "🔥 <tg-emoji emoji-id=\"5897792062291449826\">⭐</tg-emoji> Test Forward Emoji"
    
    send_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    res1 = requests.post(send_url, json={
        "chat_id": USER_CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    })
    
    if not res1.json().get("ok"):
        print("Xatolik:", res1.json())
        return
        
    msg_id = res1.json()["result"]["message_id"]
    print(f"DM ga bordi! Message ID: {msg_id}")
    
    print("\n2. Endi bot o'sha xabarni darhol kanalga FORWARD qilmoqda...")
    fwd_url = f"https://api.telegram.org/bot{BOT_TOKEN}/forwardMessage"
    res2 = requests.post(fwd_url, json={
        "chat_id": CHANNEL_ID,
        "from_chat_id": USER_CHAT_ID,
        "message_id": msg_id
    })
    print("Forward qabul qilindimi?:", res2.json().get("ok"))
    
    print("\n3. Yoki COPY qilmoqda (xuddi yozgandek)...")
    cpy_url = f"https://api.telegram.org/bot{BOT_TOKEN}/copyMessage"
    res3 = requests.post(cpy_url, json={
        "chat_id": CHANNEL_ID,
        "from_chat_id": USER_CHAT_ID,
        "message_id": msg_id
    })
    print("Copy qabul qilindimi?:", res3.json().get("ok"))

if __name__ == "__main__":
    test_auto_forward()
