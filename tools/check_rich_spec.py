"""Rich bloklarni RASMIY HUJJAT sxemasiga solishtirish.

NEGA KERAK: Telegram noma'lum maydonlarni parse bosqichida rad etmaydi.
Ya'ni {"header": ...} deb yozsangiz ham API "to'g'ri" deb javob beradi, lekin
haqiqiy yuborishda RICH_MESSAGE_CONTENT_REQUIRED bo'lib chiqadi. Aynan shu xato
bir marta jonli kanalda sodir bo'lgan.

Bu tekshiruv maydon nomlarini hujjatdagi ta'rifga qarab solishtiradi va
noto'g'risini darrov ko'rsatadi.

    python tools/check_rich_spec.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

from post_builder import build_post

from rich_schema import validate_blocks, rich_usage

problems = []


def check_blocks(blocks, path="blocks"):
    problems.extend(validate_blocks(blocks))


def count_blocks(blocks):
    return rich_usage(blocks)[0]


if __name__ == "__main__":
    # Havolalar HAR XIL bo'lishi shart — post_builder.usable_cards() bir xil
    # URL li kartochkalarni takror deb tashlaydi.
    cards = [{
        "name": f"Chevening Scholarships 202{i}",
        "url": f"https://www.chevening.org/apply/?year=202{i}&lang=uz",
        "summary": "Buyuk Britaniyada to'liq moliyalashtiriladigan magistratura.",
        "benefits": ["O'qish to'lovi to'liq", "Oylik stipendiya", "Aviabilet"],
        "eligibility": "O'zbekiston fuqarolari",
        "deadline_iso": "2026-11-05T23:59:59Z",
    } for i in range(4, 8)]

    blocks, html = build_post("Bu haftaning imkoniyatlari", cards)

    check_blocks(blocks)

    total = count_blocks(blocks)
    print(f"Bloklar soni: {total} (Telegram chegarasi: 500)")
    if total > 500:
        problems.append(f"Bloklar soni chegaradan oshdi: {total} > 500")

    print(f"HTML zaxira uzunligi: {len(html)} (sendMessage 4096 bo'yicha bo'linadi)")
    print()

    if problems:
        print(f"❌ {len(problems)} ta muammo topildi:")
        for p in problems:
            print(f"   {p}")
        sys.exit(1)

    print("✅ Barcha bloklar rasmiy hujjat sxemasiga mos.")
