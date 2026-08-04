"""Telegram kanalga xabar yuborish.

Telegram Bot API cheklovlari (rasmiy hujjatdan, core.telegram.org/bots/faq):
  • sendMessage matni — 4096 belgi (UTF-16 birlikda; emoji 2 birlik sanaladi)
  • bitta chatga    — sekundiga 1 xabar (qisqa portlashlarga ruxsat, keyin 429)
  • guruh/kanalga   — daqiqasiga 20 xabar
  • ommaviy tarqatish — sekundiga ~30 xabar
  • 429 javobida    — parameters.retry_after soniya kutish shart

Shuning uchun:
  • Uzun post GRANT CHEGARASIDA bo'linadi — HTML tegi hech qachon o'rtasidan kesilmaydi
  • Xabarlar orasida 3 soniya tanaffus (daqiqasiga 20 dan ancha past)
  • 429 kelsa retry_after qadar kutib qayta yuboriladi
  • Faqat Telegram ruxsat bergan teglar qoldiriladi
"""

import os
import re
import time

import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")

# Xabar uzunligi chegarasi jonli API'da o'lchandi (tools/probe_telegram.py):
# 32768 belgi o'tadi, 32769 da "text is too long". Bu Bot API 10.x yangiligi —
# ilgari 4096 edi. Mijozlar ~8000 belgidan keyin "Show more" tugmasini ko'rsatadi.
API_LIMIT = 32768
SAFE_LIMIT = 7500            # "Show more" chegarasidan pastda — post to'liq ko'rinadi
PAUSE_BETWEEN = 3.0          # xabarlar orasidagi tanaffus (sekundiga 1 xabar limiti)
MAX_SEND_RETRY = 3
MAX_BLOCKS_PER_MESSAGE = 90  # bitta rich xabarga sig'adigan blok soni

# Telegram HTML rejimida ruxsat etilgan teglar (rasmiy hujjat: core.telegram.org/bots/api)
# blockquote va "blockquote expandable" (yig'iladigan iqtibos) hamda tg-emoji —
# Telegram keyingi versiyalarda qo'shgan imkoniyatlar.
ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del",
                "a", "code", "pre", "blockquote", "span", "tg-spoiler", "tg-emoji"}

# O'z-o'zini yopadigan yoki juftlik talab qilmaydigan teglar yo'q, lekin
# ehtiyot uchun <br/> kabi holatlarni ham hisobga olamiz.
_TAG = re.compile(r"</?([a-zA-Z0-9\-]+)(\s[^>]*?)?(/)?>")


def utf16_len(text: str) -> int:
    """Telegram uzunlikni UTF-16 birlikda o'lchaydi (emoji = 2)."""
    return len(text.encode("utf-16-le")) // 2


def sanitize_html(text: str) -> str:
    """Telegram qo'llab-quvvatlamaydigan teglarni olib tashlaydi (matni qoladi)."""
    def repl(m):
        return m.group(0) if m.group(1).lower() in ALLOWED_TAGS else ""
    return _TAG.sub(repl, text)


def split_message(text: str, limit: int = SAFE_LIMIT) -> list:
    """Matnni Telegram limitiga moslab bo'ladi — HTML tuzilishini buzmasdan.

    Avval bo'sh qator bilan ajratilgan bloklarga (har bir grant — alohida blok)
    bo'lamiz va bloklarni to'ldirib boramiz. Bitta blokning o'zi limitdan katta
    bo'lsagina qator bo'yicha, u ham katta bo'lsa teg chegarasida kesamiz.
    """
    text = text.strip()
    if utf16_len(text) <= limit:
        return [text] if text else []

    chunks, current = [], ""

    def flush():
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
        current = ""

    for block in re.split(r"\n\s*\n", text):
        block = block.strip()
        if not block:
            continue

        if utf16_len(block) > limit:
            flush()
            chunks.extend(_split_oversized(block, limit))
            continue

        candidate = f"{current}\n\n{block}" if current else block
        if utf16_len(candidate) > limit:
            flush()
            current = block
        else:
            current = candidate

    flush()
    return _rebalance_tags(chunks)


def _open_tag_stack(text: str) -> list:
    """Matn oxirida ochiq qolgan teglar ro'yxati (ichkaridan tashqariga)."""
    stack = []
    for m in _TAG.finditer(text):
        name = (m.group(1) or "").lower()
        if name not in ALLOWED_TAGS or m.group(3):     # noma'lum yoki <br/> turi
            continue
        if m.group(0).startswith("</"):
            for i in range(len(stack) - 1, -1, -1):
                if stack[i][0] == name:
                    stack.pop(i)
                    break
        else:
            stack.append((name, m.group(0)))
    return stack


def _rebalance_tags(chunks: list) -> list:
    """Bo'lish paytida ochiq qolgan teglarni yopadi va keyingi qismda qayta ochadi.

    Telegram tugallanmagan tegli xabarni "can't parse entities" xatosi bilan rad
    etadi. Bu ayniqsa <blockquote expandable> kabi ko'p qatorli teglarda muhim.
    """
    fixed, carry = [], []
    for chunk in chunks:
        if carry:
            chunk = "".join(tag for _, tag in carry) + chunk

        stack = _open_tag_stack(chunk)
        if stack:
            chunk += "".join(f"</{name}>" for name, _ in reversed(stack))

        fixed.append(chunk)
        carry = stack
    return fixed


def _split_oversized(block: str, limit: int) -> list:
    """Bitta blok ham limitdan katta bo'lsa — qator, keyin teg chegarasida kesamiz."""
    out, current = [], ""
    for line in block.split("\n"):
        candidate = f"{current}\n{line}" if current else line
        if utf16_len(candidate) > limit:
            if current:
                out.append(current)
                current = line
            else:
                # Bitta qatorning o'zi juda uzun — teg ichida kesib qo'ymaslik uchun
                # teg chegaralarida bo'lamiz
                out.extend(_hard_split(line, limit))
                current = ""
        else:
            current = candidate
    if current.strip():
        out.append(current)
    return out


def _hard_split(line: str, limit: int) -> list:
    """Oxirgi chora: teglarni butun saqlagan holda bo'lish."""
    parts, current = [], ""
    # Matnni teg va oddiy matn bo'laklariga ajratamiz
    for piece in re.split(r"(<[^>]+>)", line):
        if not piece:
            continue
        if utf16_len(current) + utf16_len(piece) > limit and current:
            parts.append(current)
            current = ""
        if utf16_len(piece) > limit:              # juda uzun oddiy matn
            while piece:
                room = limit - utf16_len(current)
                cut = piece[:max(room, 1)]
                current += cut
                piece = piece[len(cut):]
                if piece:
                    parts.append(current)
                    current = ""
        else:
            current += piece
    if current:
        parts.append(current)
    return parts


def _post(payload: dict, method: str = "sendMessage") -> tuple:
    """Bitta so'rov yuboradi. Qaytaradi: (muvaffaqiyat, xato_matni)."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    try:
        resp = requests.post(url, json=payload, timeout=30)
    except requests.Timeout:
        return False, "timeout"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

    if resp.status_code == 429:
        retry_after = 5
        try:
            retry_after = resp.json().get("parameters", {}).get("retry_after", 5)
        except Exception:
            pass
        return False, f"429:{retry_after}"

    try:
        data = resp.json()
    except Exception:
        return False, f"HTTP {resp.status_code}"

    if data.get("ok"):
        return True, ""
    return False, data.get("description", f"HTTP {resp.status_code}")


def send_telegram_message(text: str, target_chat_id: str = None) -> bool:
    """Kanalga xabar yuboradi. Uzun bo'lsa bo'lib, limitlarga rioya qilib yuboradi."""
    if not text or not text.strip():
        print("Bo'sh xabar — yuborilmadi.")
        return False

    text = sanitize_html(text)

    if not BOT_TOKEN or BOT_TOKEN == "your_telegram_bot_token_here" or not CHANNEL_ID:
        print("Telegram sozlamalari topilmadi. Xabar konsolga chiqariladi:")
        print("=" * 60)
        print(text)
        print("=" * 60)
        return True

    chat_id = target_chat_id or CHANNEL_ID
    chunks = split_message(text)
    print(f"Xabar {len(chunks)} qismga bo'lindi (eng kattasi {max(utf16_len(c) for c in chunks)} belgi).")

    all_ok = True
    for i, chunk in enumerate(chunks, 1):
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        }

        sent = False
        for attempt in range(MAX_SEND_RETRY):
            ok, err = _post(payload)
            if ok:
                print(f"  ✅ {i}/{len(chunks)}-qism yuborildi")
                sent = True
                break

            if err.startswith("429:"):
                wait = int(err.split(":")[1]) + 1
                print(f"  ⏳ Limit (429). {wait}s kutilmoqda...")
                time.sleep(wait)
                continue

            if "can't parse entities" in err.lower():
                print(f"  ⚠️  HTML xatosi: {err}. Teglarsiz qayta yuborilmoqda...")
                payload.pop("parse_mode", None)
                payload["text"] = re.sub(r"<[^>]+>", "", chunk)
                continue

            print(f"  ❌ {i}-qism xatosi: {err}")
            time.sleep(2)

        if not sent:
            all_ok = False

        if i < len(chunks):
            time.sleep(PAUSE_BETWEEN)

    return all_ok


# ──────────────────────────────────────────────────────────────────
# Rich messages (Bot API 10.1+) — sarlavha, ro'yxat, yig'iladigan bo'lim
# ──────────────────────────────────────────────────────────────────
_rich_supported = None       # None = hali tekshirilmagan


def rich_messages_available() -> bool:
    """sendRichMessage bu bot API'sida bormi — bir marta tekshirib eslab qoladi."""
    global _rich_supported
    if _rich_supported is not None:
        return _rich_supported
    if not BOT_TOKEN:
        _rich_supported = False
        return False

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendRichMessage",
            json={}, timeout=15)
        # Metod yo'q bo'lsa 404 "Not Found" keladi. Boshqa xato = metod bor.
        _rich_supported = resp.status_code != 404
    except Exception:
        _rich_supported = False

    print(f"Rich messages: {'mavjud' if _rich_supported else 'mavjud emas — HTML ishlatiladi'}")
    return _rich_supported


def _split_blocks(blocks: list, limit: int = MAX_BLOCKS_PER_MESSAGE) -> list:
    """Bloklarni bo'ladi — imkoniyat chegarasida (heading size=3 dan oldin)."""
    if len(blocks) <= limit:
        return [blocks]

    groups, current = [], []
    for block in blocks:
        starts_card = block.get("type") == "heading" and block.get("size") == 3
        if starts_card and len(current) >= limit:
            groups.append(current)
            current = []
        current.append(block)
    if current:
        groups.append(current)
    return groups


def html_to_plain(html: str) -> str:
    """HTML dan oddiy matn — rich message'ning `text` maydoni uchun."""
    text = re.sub(r"<[^>]+>", "", html or "")
    text = (text.replace("&amp;", "&").replace("&lt;", "<")
                .replace("&gt;", ">").replace("&quot;", '"'))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def send_rich_message(blocks: list, plain_text: str = "", target_chat_id: str = None) -> bool:
    """Rich message yuboradi. Ishlamasa False qaytaradi (chaqiruvchi HTML ga o'tadi).

    `text` maydoni SHART: Telegram bloklarнинг o'zini yetarli deb hisoblamaydi va
    "RICH_MESSAGE_CONTENT_REQUIRED" xatosini beradi. Bu chat_id=1 bilan
    tekshirganda ko'rinmaydi — chat topilmagani uchun mazmun tekshiruvigacha
    yetib bormaydi. Xato faqat haqiqiy yuborishda chiqadi.
    """
    if not blocks or not BOT_TOKEN or not CHANNEL_ID:
        return False
    if not rich_messages_available():
        return False

    chat_id = target_chat_id or CHANNEL_ID
    groups = _split_blocks(blocks)

    for i, group in enumerate(groups, 1):
        rich = {"blocks": group}
        if plain_text:
            rich["text"] = plain_text[:API_LIMIT]
        payload = {"chat_id": chat_id, "rich_message": rich}

        sent = False
        for attempt in range(MAX_SEND_RETRY):
            ok, err = _post(payload, method="sendRichMessage")
            if ok:
                print(f"  ✅ {i}/{len(groups)}-qism yuborildi (rich, {len(group)} blok)")
                sent = True
                break
            if err.startswith("429:"):
                wait = int(err.split(":")[1]) + 1
                print(f"  ⏳ Limit (429). {wait}s kutilmoqda...")
                time.sleep(wait)
                continue
            print(f"  ⚠️  Rich xabar yuborilmadi: {err}")
            return False                          # HTML zaxirasiga o'tamiz

        if not sent:
            return False
        if i < len(groups):
            time.sleep(PAUSE_BETWEEN)

    return True


def validate_rich_blocks(blocks: list, plain_text: str = "") -> tuple:
    """Bloklar TUZILISHINI tekshiradi — hech narsa yubormasdan.

    Mavjud bo'lmagan chat_id=1 ga so'rov yuboriladi va "chat not found" javobi
    sxema to'g'ri ekanini bildiradi.

    CHEKLOV: bu faqat TUZILMANI tekshiradi. Telegram mazmun tekshiruvini chat
    topilgandan KEYIN bajaradi, shuning uchun "RICH_MESSAGE_CONTENT_REQUIRED"
    kabi xatolar bu yerda ko'rinmaydi. Aynan shu sabab quruq sinov "yaroqli"
    deb ko'rsatgan post haqiqiy yuborishda rad etilgan edi.
    Shu bois publish() da HTML zaxirasi doim saqlanadi.
    """
    if not blocks or not BOT_TOKEN:
        return False, "token yoki blok yo'q"

    rich = {"blocks": blocks}
    if plain_text:
        rich["text"] = plain_text[:API_LIMIT]

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendRichMessage",
            json={"chat_id": 1, "rich_message": rich}, timeout=20)
        desc = resp.json().get("description", "")
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"

    return ("chat not found" in desc), desc


def publish(blocks: list, html_text: str, target_chat_id: str = None) -> bool:
    """Avval rich message bilan urinadi, bo'lmasa HTML ga qaytadi.

    Ikkala ko'rinish ham post_builder.py da BIR MANBADAN quriladi, shuning uchun
    qaysi yo'l ishlashidan qat'i nazar mazmun va HAVOLALAR bir xil bo'ladi.
    """
    if blocks and send_rich_message(blocks, html_to_plain(html_text), target_chat_id):
        return True
    if blocks:
        print("  Rich message ishlamadi — HTML ko'rinishga o'tilmoqda.")
    return send_telegram_message(html_text, target_chat_id)


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    print("--- Bo'lish sinovi ---")
    demo = "\n\n".join(
        f"<b>Grant {i}</b>\n<i>Tavsif matni bu yerda.</i>\n"
        f'<a href="https://example.org/grant/{i}">Batafsil va ariza topshirish</a>'
        for i in range(1, 61)
    )
    parts = split_message(demo)
    print(f"Umumiy uzunlik: {utf16_len(demo)}, qismlar: {len(parts)}")
    for p in parts:
        opened = len(re.findall(r"<a\s", p))
        closed = p.count("</a>")
        status = "OK" if opened == closed else "TEG BUZILDI!"
        print(f"  {utf16_len(p):>5} belgi | <a>={opened} </a>={closed} | {status}")

    print("\n--- Teg tozalash sinovi ---")
    print(sanitize_html('<b>qoladi</b> <script>alert(1)</script> <div>tashlanadi</div> <a href="#">havola</a>'))
