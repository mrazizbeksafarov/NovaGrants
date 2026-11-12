"""Post qurish: AI ning tuzilgan javobidan Telegram formatiga o'tkazish.

IKKI KO'RINISH bir manbadan quriladi:
  1. Rich message bloklari — Telegram Bot API 10.1+ (sarlavha, ro'yxat,
     yig'iladigan bo'lim, ajratgich, footer). Zamonaviy va o'qishga qulay.
  2. HTML matn — zaxira. Rich message ishlamasa yoki eski mijozda ochilsa.

NEGA AI EMAS, BIZ QURAMIZ:
AI faqat matn yozadi (nom, tavsif, foydalar). HAVOLANI BIZ QO'YAMIZ — o'zimizda
saqlanган asl URL dan. Shu sabab AI havolani o'ylab topishi yoki o'zgartirishi
texnik jihatdan mumkin emas.

Sxema RASMIY HUJJATDAN olingan (core.telegram.org/bots/api, InputRichBlock*):
  heading   — {"type": "heading", "text": RichText, "size": 1-6}  (1 eng katta)
  paragraph — {"type": "paragraph", "text": RichText}
  footer    — {"type": "footer", "text": RichText}
  divider   — {"type": "divider"}
  list      — {"type": "list", "items": [InputRichBlockListItem]}
              har bir item: {"blocks": [InputRichBlock]}
  details   — {"type": "details", "summary": RichText, "blocks": [...], "is_open": bool}
  RichText  — satr | RichText massivi | {"type": "bold"|"url"|..., "text": ...}

DIQQAT — jonli API'ni "probe" qilish bu yerda CHALG'ITADI. Telegram noma'lum
maydonlarni parse bosqichida rad etmaydi, shuning uchun {"header": ...} yoki
{"items": [{"text": ...}]} kabi noto'g'ri shakllar ham "to'g'ri" ko'rinadi.
Xato faqat haqiqiy yuborishda RICH_MESSAGE_CONTENT_REQUIRED bo'lib chiqadi.
Shuning uchun maydon nomlari faqat hujjatdan olinadi.
"""

import re
from datetime import datetime, timezone
from rich_schema import valid_web_url

CHANNEL_TAG = "@Nova_Grants"
BRAND_LABEL = "NOVA GRANTS"
CTA = "Ariza topshirish va batafsil ma'lumot"


def _esc(text: str) -> str:
    """HTML uchun xavfsiz matn."""
    return (str(text or "")
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


def _esc_attr(url: str) -> str:
    """href="..." ichiga qo'yish uchun xavfsiz URL.

    Bu ILGARI QILINMAGAN edi va jiddiy oqibati bor edi: ko'p parametrli
    havolada (`?a=1&b=2`) xom `&` qoladi, qo'shtirnoq esa atributni yorib
    yuboradi. Telegram bunday xabarni "can't parse entities" bilan rad etadi,
    zaxira yo'l esa BARCHA teglarni o'chirib yuborardi — ya'ni post havolasiz
    chiqardi. Aynan "faqat asl havola" kafolatining teskarisi.
    """
    return (str(url or "")
            .replace("&", "&amp;")
            .replace('"', "&quot;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


def _clean(text: str, limit: int = 400) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text[:limit].rsplit(" ", 1)[0] + "..." if len(text) > limit else text


def _deadline_label(iso: str) -> str:
    """2026-11-05T23:59:59Z -> '5-noyabr, 2026'."""
    if not iso:
        return ""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", str(iso))
    if not m:
        return str(iso)
    months = ["yanvar", "fevral", "mart", "aprel", "may", "iyun",
              "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return f"{d}-{months[mo - 1]}, {y}" if 1 <= mo <= 12 else f"{y}-{mo:02d}-{d:02d}"


# ──────────────────────────────────────────────────────────────────
# 1-ko'rinish: Rich message bloklari
# ──────────────────────────────────────────────────────────────────
def usable_cards(cards: list) -> list:
    """Nomi va havolasi bor, takrorlanmagan kartochkalar.

    AI ba'zan bitta indexni ikki marta qaytaradi — bunda bitta grant postda
    ikki marta chiqib qolardi. Shu yerda bir marta filtrlab, ikkala ko'rinish
    (rich va HTML) uchun bir xil ro'yxat ishlatamiz.
    """
    out, seen = [], set()
    for card in cards or []:
        name = _clean(card.get("name"), 140)
        url = str(card.get("url") or "").strip()
        if not name or not valid_web_url(url):
            continue
        if url in seen:
            continue
        seen.add(url)
        out.append(card)
    return out


def build_rich_blocks(headline: str, cards: list) -> list:
    """Tuzilgan kartochkalardan rich message bloklarini quradi."""
    blocks = []
    cards = usable_cards(cards)
    if cards:
        blocks.append({"type": "photo", "photo": {"type": "photo", "media": "attach://nova_cover"}})

    if headline:
        blocks.append({"type": "heading", "size": 2, "text": _clean(headline, 120)})
        blocks.append({"type": "divider"})

    if len(cards) >= 3:
        def cell(text, header=False):
            return {"text": text, "align": "left", "valign": "middle", **({"is_header": True} if header else {})}
        rows = [[cell("Dastur", True), cell("Muddat", True)]]
        for i, card in enumerate(cards, 1):
            rows.append([cell({"type": "anchor_link", "text": _clean(card.get("name"), 65), "anchor_name": f"grant-{i}"}),
                         cell(_deadline_label(card.get("deadline_iso")) or "Ko'rsatilmagan")])
        # Ro'yxat qisqa va post ichidagi navigatsiya — yig'ilmaydi, doim ko'rinadi.
        blocks.append({"type": "table", "cells": rows, "is_compact": True, "is_striped": True,
                       "caption": f"Dasturlar ro'yxati · {len(cards)}"})

    for i, card in enumerate(cards, 1):
        name = _clean(card.get("name"), 140)
        url = card.get("url", "")

        if len(cards) >= 3:
            blocks.append({"type": "anchor", "name": f"grant-{i}"})
        display_name = f"{i:02d} · {name}" if len(cards) > 1 else name
        blocks.append({"type": "heading", "size": 3, "text": display_name})

        benefits = [b for b in (card.get("benefits") or []) if str(b).strip()][:5]
        if benefits:
            blocks.append({"type": "blockquote", "blocks": [
                {"type": "paragraph", "text": {"type": "bold", "text": _clean(benefits[0], 160)}}]})

        summary = _clean(card.get("summary"), 300)
        if summary:
            blocks.append({"type": "paragraph", "text": summary})

        # Yig'iladigan bo'lim: tafsilotlar postni cho'zmasin
        inner = []
        if len(benefits) > 1:
            # Har bir list elementi InputRichBlockListItem: ichida `blocks` bo'ladi
            inner.append({"type": "list", "items": [
                {"blocks": [{"type": "paragraph", "text": _clean(b, 160)}]}
                for b in benefits[1:]
            ]})

        eligibility = re.sub(r"\s+", " ", str(card.get("eligibility") or "")).strip()
        if eligibility:
            inner.append({"type": "paragraph",
                          "text": [{"type": "bold", "text": "Kimlar uchun: "}, eligibility]})

        if inner:
            # `summary` majburiy (hujjatda Optional emas) — `header` degan maydon yo'q.
            # `is_open` turi hujjatda "True", ya'ni faqat True uzatiladi. Bizga
            # yig'ilgan holat kerak, shuning uchun maydonni umuman qo'shmaymiz.
            blocks.append({"type": "details", "summary": "Dastur shartlari",
                           "blocks": inner})

        # The deadline stays visible even while the long details are collapsed.
        deadline = _deadline_label(card.get("deadline_iso"))
        if deadline:
            value = str(card["deadline_iso"])
            try:
                dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                deadline_text = {"type": "date_time", "text": deadline,
                                 "unix_time": int(dt.timestamp()), "date_time_format": "r"}
            except ValueError:
                deadline_text = deadline
            # The client can render a relative date as an absolute date too.
            # One date node prevents "18-yanvar · 18-yanvar" on those clients.
            deadline_line = [{"type": "bold", "text": "Muddat: "}, deadline_text]
            blocks.append({"type": "paragraph", "text": deadline_line})
        else:
            blocks.append({"type": "footer", "text": "Muddat ko'rsatilmagan"})

        # One native application action; do not encourage copying or duplicate links.
        buttons = [{"text": "Ariza va tafsilotlar", "style": "primary", "url": url}]
        blocks.append({"type": "buttons", "buttons": buttons})
        blocks.append({"type": "divider"})

    if blocks and blocks[-1].get("type") == "divider":
        blocks.pop()

    if blocks:
        blocks.append({"type": "footer", "text": CHANNEL_TAG})

    return blocks


# ──────────────────────────────────────────────────────────────────
# 2-ko'rinish: HTML zaxira
# ──────────────────────────────────────────────────────────────────
def build_html(headline: str, cards: list) -> str:
    """Xuddi shu ma'lumotdan oddiy HTML post. Rich message ishlamasa ishlatiladi."""
    parts = []
    cards = usable_cards(cards)
    if cards:
        parts.append(f"<b>{BRAND_LABEL}</b>\n")

    if headline:
        parts.append(f"<b>{_esc(_clean(headline, 120))}</b>\n")

    for i, card in enumerate(cards, 1):
        name = _clean(card.get("name"), 140)
        url = card.get("url", "")

        display_name = f"{i:02d} · {name}" if len(cards) > 1 else name
        parts.append(f"<b>{_esc(display_name)}</b>")

        benefits = [b for b in (card.get("benefits") or []) if str(b).strip()][:5]
        if benefits:
            parts.append(f"<blockquote><b>{_esc(_clean(benefits[0], 160))}</b></blockquote>")

        summary = _clean(card.get("summary"), 300)
        if summary:
            parts.append(_esc(summary))

        detail_lines = []
        for b in benefits[1:]:
            detail_lines.append(f"• {_esc(_clean(b, 160))}")

        eligibility = re.sub(r"\s+", " ", str(card.get("eligibility") or "")).strip()
        if eligibility:
            detail_lines.append(f"<b>Kimlar uchun:</b> {_esc(eligibility)}")

        if detail_lines:
            # Yig'iladigan iqtibos — ichida bo'sh qator BO'LMASLIGI kerak
            parts.append("<blockquote expandable>" + "\n".join(detail_lines) + "</blockquote>")

        deadline = _deadline_label(card.get("deadline_iso"))
        if deadline:
            parts.append(f"<b>Muddat:</b> {_esc(deadline)}")
        else:
            parts.append("<i>Muddat ko'rsatilmagan</i>")

        parts.append(f'<a href="{_esc_attr(url)}">{CTA}</a>')
        parts.append("")

    if not parts:
        return ""

    parts.append(CHANNEL_TAG)
    return "\n".join(parts).strip()


def build_post(headline: str, cards: list) -> tuple:
    """Qaytaradi: (rich_bloklar, html_matn). Ikkalasi bir manbadan."""
    return build_rich_blocks(headline, cards), build_html(headline, cards)


if __name__ == "__main__":
    import sys, json
    sys.stdout.reconfigure(encoding="utf-8")

    demo_cards = [{
        "name": "Chevening Scholarships 2027",
        "url": "https://www.chevening.org/apply/",
        "summary": "Buyuk Britaniyada bir yillik magistratura uchun to'liq grant.",
        "benefits": ["O'qish to'lovi to'liq qoplanadi", "Oylik stipendiya",
                     "Aviabilet va viza xarajati"],
        "eligibility": "Bakalavr diplomi va 2 yil ish tajribasi bo'lgan O'zbekiston fuqarolari",
        "deadline_iso": "2026-11-05T23:59:59Z",
    }]

    blocks, html = build_post("Bu haftaning to'liq grantlari", demo_cards)
    print("--- RICH BLOKLAR ---")
    print(json.dumps(blocks, ensure_ascii=False, indent=2))
    print("\n--- HTML ZAXIRA ---")
    print(html)
