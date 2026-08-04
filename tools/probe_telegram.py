"""Telegram Bot API imkoniyatlarini jonli tekshirish — HECH NARSA YUBORMASDAN.

Usul: metodni ataylab to'liqsiz parametr bilan chaqiramiz. Telegram javobidagi
xato matni metod mavjudligini va qaysi maydonlar talab qilinishini aytib beradi.
Haqiqiy xabar yuborilmaydi.
"""

import os
import sys
import json

import requests
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL = os.getenv("TELEGRAM_CHANNEL_ID")
BASE = f"https://api.telegram.org/bot{TOKEN}"

if not TOKEN:
    print("TELEGRAM_BOT_TOKEN topilmadi.")
    sys.exit(1)


def call(method, payload=None):
    try:
        r = requests.post(f"{BASE}/{method}", json=payload or {}, timeout=20)
        return r.status_code, r.json()
    except Exception as e:
        return 0, {"error": f"{type(e).__name__}: {e}"}


def show(label, method, payload=None):
    code, data = call(method, payload)
    ok = data.get("ok")
    desc = data.get("description", "")
    print(f"  {label:<34} HTTP {code} | ok={ok} | {desc[:96]}")
    return data


print("=" * 78)
print("1. BOT HOLATI")
print("=" * 78)
me = show("getMe", "getMe")
if me.get("ok"):
    u = me["result"]
    print(f"     bot: @{u.get('username')} | id={u.get('id')}")

print()
print("=" * 78)
print("2. KANAL HUQUQLARI")
print("=" * 78)
chat = show("getChat", "getChat", {"chat_id": CHANNEL})
if chat.get("ok"):
    c = chat["result"]
    print(f"     kanal: {c.get('title')} | turi={c.get('type')} | id={c.get('id')}")
    if me.get("ok"):
        mem = call("getChatMember", {"chat_id": CHANNEL, "user_id": me["result"]["id"]})[1]
        if mem.get("ok"):
            r = mem["result"]
            print(f"     bot maqomi: {r.get('status')} | post huquqi: {r.get('can_post_messages')}")

print()
print("=" * 78)
print("3. RICH MESSAGES (Bot API 10.1+) MAVJUDMI?")
print("=" * 78)
print("  Metodni bo'sh parametr bilan chaqiramiz — xato matni javob beradi.")
print("  'method not found' = qo'llab-quvvatlanmaydi | boshqa xato = MAVJUD\n")

for method in ["sendRichMessage", "sendRichMessageDraft", "editMessageRichText",
               "sendMessage", "sendDocument"]:
    show(method, method)

print()
print("=" * 78)
print("4. sendRichMessage TUZILMASI — qaysi maydonlar talab qilinadi?")
print("=" * 78)

probes = [
    ("faqat chat_id", {"chat_id": CHANNEL}),
    ("chat_id + bo'sh rich_message", {"chat_id": CHANNEL, "rich_message": {}}),
    ("rich_message.text", {"chat_id": CHANNEL, "rich_message": {"text": "sinov"}}),
    ("rich_message.blocks (bo'sh)", {"chat_id": CHANNEL, "rich_message": {"blocks": []}}),
    ("blocks: paragraph", {"chat_id": CHANNEL, "rich_message": {"blocks": [
        {"type": "paragraph", "text": {"text": "sinov matni"}}]}}),
    ("message (rich_message o'rniga)", {"chat_id": CHANNEL, "message": {"blocks": []}}),
    ("blocks yuqori darajada", {"chat_id": CHANNEL, "blocks": []}),
]
for label, payload in probes:
    show(label, "sendRichMessage", payload)

print()
print("=" * 78)
print("5. XABAR UZUNLIGI CHEGARASI")
print("=" * 78)
print("  Yaroqsiz chat_id bilan yuboramiz — matn uzunligi tekshiruvi undan oldin ishlaydi.")
for n in (4096, 4097, 8192, 32768, 32769):
    code, data = call("sendMessage", {"chat_id": 1, "text": "a" * n})
    d = data.get("description", "")
    verdict = "uzunlik RAD ETILDI" if "too long" in d.lower() or "MESSAGE_TOO_LONG" in d else "uzunlik o'tdi"
    print(f"  {n:>6} belgi -> {verdict:<20} | {d[:60]}")
