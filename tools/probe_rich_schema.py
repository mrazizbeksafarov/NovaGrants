"""sendRichMessage blok sxemasini teskari muhandislik bilan aniqlash.

XAVFSIZLIK: chat_id = 1 (mavjud bo'lmagan chat) ishlatiladi. Telegram maydonlarni
chat topishdan OLDIN tekshiradi, shuning uchun sxema xatolarini ko'ramiz, lekin
hech qanday xabar hech qayerga yuborilmaydi.
"""

import os
import sys
import json

import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BASE = f"https://api.telegram.org/bot{TOKEN}"
SAFE_CHAT = 1                       # mavjud emas — post bo'lib ketmasligi kafolati


def probe(blocks, label=""):
    payload = {"chat_id": SAFE_CHAT, "rich_message": {"blocks": blocks}}
    try:
        r = requests.post(f"{BASE}/sendRichMessage", json=payload, timeout=20)
        d = r.json()
    except Exception as e:
        return f"XATO {type(e).__name__}"
    desc = d.get("description", "")
    # "chat not found" = sxema TO'G'RI (faqat chat yo'q)
    return desc


print("=" * 80)
print("1. QAYSI 'type' QIYMATLARI QABUL QILINADI?")
print("=" * 80)
candidates = [
    "paragraph", "section_heading", "sectionHeading", "heading", "divider",
    "footer", "list", "block_quotation", "blockQuotation", "quote",
    "pull_quotation", "details", "preformatted", "anchor", "table",
    "mathematical_expression", "collage", "slideshow", "photo", "video", "thinking",
]
valid, invalid = [], []
for t in candidates:
    desc = probe([{"type": t}], t)
    if "Wrong block type" in desc or "Unsupported" in desc or "can't parse InputRichBlock" in desc:
        invalid.append((t, desc))
    else:
        valid.append((t, desc))
    print(f"  {t:<26} {desc[:74]}")

print()
print("=" * 80)
print("2. TASDIQLANGAN TURLAR UCHUN KERAKLI MAYDONLAR")
print("=" * 80)
for t, first in valid:
    print(f"\n  --- type={t} ---")
    print(f"    bo'sh                    : {first[:70]}")
    for attempt in [
        {"type": t, "text": "sinov"},
        {"type": t, "text": {"type": "plain", "text": "sinov"}},
        {"type": t, "rich_text": {"type": "plain", "text": "sinov"}},
        {"type": t, "content": "sinov"},
    ]:
        key = [k for k in attempt if k != "type"][0]
        val = json.dumps(attempt[key], ensure_ascii=False)[:34]
        print(f"    {key}={val:<36} {probe([attempt])[:62]}")

print()
print("=" * 80)
print("3. RichText TURLARI")
print("=" * 80)
base_type = valid[0][0] if valid else "paragraph"
for rt in ["plain", "bold", "italic", "url", "fixed", "text", "underline", "strikethrough"]:
    d = probe([{"type": base_type, "text": {"type": rt, "text": "sinov"}}])
    print(f"  RichText type={rt:<16} {d[:66]}")
