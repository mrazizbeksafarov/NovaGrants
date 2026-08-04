"""Rich message sxemasining ichki tuzilishi: heading.size, list, details, havola.

Yana chat_id = 1 — hech narsa yuborilmaydi.
"chat not found" javobi = sxema TO'G'RI.
"""

import os, sys, json
import requests
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding="utf-8")
load_dotenv()
BASE = f"https://api.telegram.org/bot{os.getenv('TELEGRAM_BOT_TOKEN')}"
SAFE = 1


def p(blocks):
    try:
        d = requests.post(f"{BASE}/sendRichMessage",
                          json={"chat_id": SAFE, "rich_message": {"blocks": blocks}},
                          timeout=20).json()
    except Exception as e:
        return f"XATO {type(e).__name__}"
    return d.get("description", "")


def row(label, blocks):
    d = p(blocks)
    mark = "✅" if "chat not found" in d else "❌"
    print(f"  {mark} {label:<50} {d[:70]}")


print("=" * 92)
print("HEADING — size qiymatlari")
print("=" * 92)
for size in ["h1", "h2", "h3", "large", "medium", "small", "title", "subtitle", 1, 2, 3]:
    row(f'size={size!r}', [{"type": "heading", "size": size, "text": "Sarlavha"}])

print()
print("=" * 92)
print("LIST — tuzilishi")
print("=" * 92)
for label, blk in [
    ('items: ["a","b"]', {"type": "list", "items": ["a", "b"]}),
    ('items: [{text}]', {"type": "list", "items": [{"text": "a"}]}),
    ('items: [{blocks}]', {"type": "list", "items": [{"blocks": [{"type": "paragraph", "text": "a"}]}]}),
    ('ordered=True', {"type": "list", "ordered": True, "items": ["a"]}),
    ('is_ordered=True', {"type": "list", "is_ordered": True, "items": ["a"]}),
    ('style="ordered"', {"type": "list", "style": "ordered", "items": ["a"]}),
]:
    row(label, [blk])

print()
print("=" * 92)
print("DETAILS — yig'iladigan bo'lim (eng muhimi)")
print("=" * 92)
for label, blk in [
    ('header + blocks', {"type": "details", "header": "Batafsil",
                         "blocks": [{"type": "paragraph", "text": "ichki matn"}]}),
    ('summary + blocks', {"type": "details", "summary": "Batafsil",
                          "blocks": [{"type": "paragraph", "text": "ichki matn"}]}),
    ('title + blocks', {"type": "details", "title": "Batafsil",
                        "blocks": [{"type": "paragraph", "text": "ichki matn"}]}),
    ('text + blocks', {"type": "details", "text": "Batafsil",
                       "blocks": [{"type": "paragraph", "text": "ichki matn"}]}),
    ('is_open', {"type": "details", "header": "X", "is_open": False,
                 "blocks": [{"type": "paragraph", "text": "y"}]}),
]:
    row(label, [blk])

print()
print("=" * 92)
print("HAVOLA (RichTextUrl) va bir nechta matn bo'lagi")
print("=" * 92)
for label, txt in [
    ('url obyekti', {"type": "url", "url": "https://example.org", "text": "Ariza topshirish"}),
    ('bold ichida url', {"type": "bold", "text": {"type": "url", "url": "https://example.org", "text": "X"}}),
    ('massiv: [str, url]', ["Oddiy matn ", {"type": "url", "url": "https://example.org", "text": "havola"}]),
    ('massiv: [bold, str]', [{"type": "bold", "text": "Qalin"}, " oddiy"]),
]:
    row(label, [{"type": "paragraph", "text": txt}])

print()
print("=" * 92)
print("TO'LIQ POST NAMUNASI — grant e'loni")
print("=" * 92)
demo = [
    {"type": "heading", "size": "h2", "text": "Yangi grant imkoniyatlari"},
    {"type": "divider"},
    {"type": "paragraph", "text": [
        {"type": "bold", "text": "Chevening Scholarships 2027"},
    ]},
    {"type": "details", "header": "Batafsil ma'lumot", "blocks": [
        {"type": "paragraph", "text": "Buyuk Britaniyada to'liq moliyalashtiriladigan magistratura."},
        {"type": "list", "items": ["O'qish to'lovi to'liq", "Oylik stipendiya", "Yo'l xarajati"]},
    ]},
    {"type": "paragraph", "text": [
        {"type": "url", "url": "https://www.chevening.org/apply/", "text": "Ariza topshirish"}]},
    {"type": "footer", "text": "@Nova_Grants"},
]
d = p(demo)
print(f"  natija: {d}")
print(f"  {'✅ SXEMA TO_G_RI — shu tuzilma ishlaydi' if 'chat not found' in d else '❌ sxemada xato bor'}")
print()
print("  JSON:")
print(json.dumps(demo, ensure_ascii=False, indent=2)[:1400])
