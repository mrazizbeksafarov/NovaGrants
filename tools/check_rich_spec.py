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

# core.telegram.org/bots/api — InputRichBlock* ta'riflari.
# (majburiy_maydonlar, ixtiyoriy_maydonlar)
SPEC = {
    "heading":    ({"type", "text", "size"}, set()),
    "paragraph":  ({"type", "text"}, set()),
    "footer":     ({"type", "text"}, set()),
    "divider":    ({"type"}, set()),
    "list":       ({"type", "items"}, set()),
    "details":    ({"type", "summary", "blocks"}, {"is_open"}),
    "blockquote": ({"type", "blocks"}, {"credit"}),
    "pullquote":  ({"type", "text"}, {"credit"}),
}

RICHTEXT_TYPES = {
    "bold", "italic", "underline", "strikethrough", "spoiler", "datetime",
    "textmention", "subscript", "superscript", "marked", "code", "customemoji",
    "mathematicalexpression", "url", "emailaddress", "phonenumber",
    "bankcardnumber", "mention", "hashtag", "cashtag", "botcommand",
    "anchor", "anchorlink", "reference", "referencelink",
}

problems = []


def check_richtext(value, path):
    """RichText: satr | massiv | {"type": ..., "text": ...}"""
    if isinstance(value, str):
        return
    if isinstance(value, list):
        for i, v in enumerate(value):
            check_richtext(v, f"{path}[{i}]")
        return
    if isinstance(value, dict):
        t = value.get("type")
        if t not in RICHTEXT_TYPES:
            problems.append(f"{path}: noma'lum RichText turi {t!r}")
        if t == "url" and "url" not in value:
            problems.append(f"{path}: url turida `url` maydoni yo'q")
        if "text" in value:
            check_richtext(value["text"], f"{path}.text")
        return
    problems.append(f"{path}: RichText bo'la olmaydi ({type(value).__name__})")


def check_blocks(blocks, path="blocks"):
    if not isinstance(blocks, list):
        problems.append(f"{path}: massiv bo'lishi kerak")
        return

    for i, b in enumerate(blocks):
        p = f"{path}[{i}]"
        if not isinstance(b, dict):
            problems.append(f"{p}: obyekt bo'lishi kerak")
            continue

        t = b.get("type")
        if t not in SPEC:
            problems.append(f"{p}: noma'lum blok turi {t!r}")
            continue

        required, optional = SPEC[t]
        missing = required - set(b)
        extra = set(b) - required - optional
        if missing:
            problems.append(f"{p} ({t}): MAJBURIY maydon yo'q: {sorted(missing)}")
        if extra:
            problems.append(f"{p} ({t}): hujjatda yo'q maydon: {sorted(extra)}")

        if t == "heading":
            size = b.get("size")
            if not isinstance(size, int) or not (1 <= size <= 6):
                problems.append(f"{p}: size 1-6 oralig'ida butun son bo'lishi kerak, hozir {size!r}")

        if "text" in b:
            check_richtext(b["text"], f"{p}.text")
        if t == "details":
            check_richtext(b.get("summary"), f"{p}.summary")
            if b.get("is_open") not in (None, True):
                problems.append(f"{p}: is_open faqat True bo'la oladi (yoki umuman bo'lmasin)")
            check_blocks(b.get("blocks", []), f"{p}.blocks")
        if t == "blockquote":
            check_blocks(b.get("blocks", []), f"{p}.blocks")
        if t == "list":
            for j, item in enumerate(b.get("items", [])):
                ip = f"{p}.items[{j}]"
                if not isinstance(item, dict) or "blocks" not in item:
                    problems.append(f"{ip}: InputRichBlockListItem bo'lishi kerak "
                                    f"({{'blocks': [...]}}), hozir {list(item) if isinstance(item, dict) else type(item).__name__}")
                    continue
                extra_i = set(item) - {"blocks", "has_checkbox", "is_checked", "value", "type"}
                if extra_i:
                    problems.append(f"{ip}: hujjatda yo'q maydon: {sorted(extra_i)}")
                check_blocks(item["blocks"], f"{ip}.blocks")


def count_blocks(blocks):
    n = 0
    for b in blocks:
        n += 1
        if b.get("type") == "details":
            n += count_blocks(b.get("blocks", []))
        if b.get("type") == "blockquote":
            n += count_blocks(b.get("blocks", []))
        if b.get("type") == "list":
            for it in b.get("items", []):
                n += 1 + count_blocks(it.get("blocks", []))
    return n


if __name__ == "__main__":
    cards = [{
        "name": "Chevening Scholarships 2027",
        "url": "https://www.chevening.org/apply/",
        "summary": "Buyuk Britaniyada to'liq moliyalashtiriladigan magistratura.",
        "benefits": ["O'qish to'lovi to'liq", "Oylik stipendiya", "Aviabilet"],
        "eligibility": "O'zbekiston fuqarolari",
        "deadline_iso": "2026-11-05T23:59:59Z",
    }] * 4

    blocks, html = build_post("Bu haftaning imkoniyatlari", cards)

    check_blocks(blocks)

    total = count_blocks(blocks)
    print(f"Bloklar soni: {total} (Telegram chegarasi: 500)")
    if total > 500:
        problems.append(f"Bloklar soni chegaradan oshdi: {total} > 500")

    print(f"HTML zaxira uzunligi: {len(html)} (chegara: 32768)")
    print()

    if problems:
        print(f"❌ {len(problems)} ta muammo topildi:")
        for p in problems:
            print(f"   {p}")
        sys.exit(1)

    print("✅ Barcha bloklar rasmiy hujjat sxemasiga mos.")
