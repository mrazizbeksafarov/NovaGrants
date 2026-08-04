import os
import requests
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
USER_CHAT_ID = "7987189270"
MESSAGE_ID = 5048479  # Siz boya yuborgan test xabarning ID si

def test_forward_and_copy():
    # 1. Forward Message (Uzatilgani bilinadi)
    url_forward = f"https://api.telegram.org/bot{BOT_TOKEN}/forwardMessage"
    payload_forward = {
        "chat_id": CHANNEL_ID,
        "from_chat_id": USER_CHAT_ID,
        "message_id": MESSAGE_ID
    }
    res_fwd = requests.post(url_forward, json=payload_forward)
    print("Forward (Uzatish) natijasi:", res_fwd.json())

    # 2. Copy Message (Uzatilgani bilinmaydi, xuddi o'zi yozgandek)
    url_copy = f"https://api.telegram.org/bot{BOT_TOKEN}/copyMessage"
    payload_copy = {
        "chat_id": CHANNEL_ID,
        "from_chat_id": USER_CHAT_ID,
        "message_id": MESSAGE_ID
    }
    res_cpy = requests.post(url_copy, json=payload_copy)
    print("Copy (Ko'chirish) natijasi:", res_cpy.json())

if __name__ == "__main__":
    test_forward_and_copy()
