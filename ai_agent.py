"""Gemini orqali post mazmunini tayyorlash.

MUHIM ARXITEKTURA QARORI — AI HAVOLAGA UMUMAN TEGMAYDI.
AI faqat matn yozadi va har bir imkoniyatga kirish RAQAMI (index) bilan murojaat
qiladi. Havolani biz o'zimizda saqlangan asl URL dan qo'yamiz (post_builder.py).
Shu sabab AI havolani o'ylab topishi yoki o'zgartirishi TEXNIK JIHATDAN mumkin emas.

Qaror sababi: oldingi versiyada AI ga URL yozdirilardi va u ba'zan havolani
o'zgartirib yuborardi. Endi bunday xato imkoniyati yo'q.

Optimizatsiyalar (o'lchangan):
  • thinking_level="low"  — 1624 → 471 token, 30.7s → 18.3s
  • model zaxirasi        — 503/429 da avtomatik boshqa modelga o'tadi
  • model bo'yicha sozlama — Gemini 2.5 "thinking_level" ni qabul qilmaydi
"""

import os
import re
import json
import time
from typing import List, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from filters import validate_deadline_iso

load_dotenv()

MODEL_CHAIN = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-flash-latest"]
MAX_ATTEMPTS = 4
BATCH_SIZE = 8               # bitta so'rovga nechta imkoniyat

# "thinking" sozlamasini qabul qilmagan modellar
_NO_THINKING_CONFIG = set()

_api_key = os.getenv("GEMINI_API_KEY")
if _api_key and _api_key != "your_google_gemini_api_key_here":
    client = genai.Client(api_key=_api_key)
else:
    client = None
    print("DIQQAT: GEMINI_API_KEY topilmadi — zaxira formatlagich ishlatiladi.")


class GrantCard(BaseModel):
    index: int = Field(description="Kirishda berilgan imkoniyat raqami (1, 2, 3...). "
                                   "Faqat shu raqam orqali murojaat qil, URL yozma.")
    name: str = Field(description="Imkoniyat nomi. Original nomni saqla, tarjima qilma.")
    summary: str = Field(description="1-2 jumla o'zbekcha: bu nima va nima beradi.")
    benefits: List[str] = Field(default_factory=list,
                                description="2-4 ta qisqa punkt: to'liq grant, stipendiya, "
                                            "yo'l xarajati, viza va h.k.")
    eligibility: str = Field(default="", description="Kimlar qatnasha oladi — qisqa.")
    deadline_iso: Optional[str] = Field(default=None,
                                        description="Oxirgi muddat ISO 8601 da "
                                                    "(2026-10-31T23:59:59Z). Noma'lum bo'lsa null.")


class PostContent(BaseModel):
    headline: str = Field(description="Post sarlavhasi — har safar boshqacha, jonli va aniq.")
    cards: List[GrantCard] = Field(default_factory=list,
                                   description="Faqat mos kelgan imkoniyatlar. "
                                               "Mos kelmasa bo'sh ro'yxat qaytar.")


SYSTEM_INSTRUCTION = """
Sen 'Nova Grants' Telegram kanalining muharririsan. O'zingni AI yoki bot deb tanishtirma.

KIM UCHUN
Auditoriya — O'zbekistondagi talabalar, yosh mutaxassislar va tadbirkorlar.
Ular JISMONIY SHAXS sifatida ariza topshiradi.

USLUB
Zamonaviy, jiddiy, aniq. Emoji ishlatma. Suv gap va ortiqcha maqtov yo'q.
O'zbek tilida yoz. Imkoniyat nomini tarjima qilma — original nomda qoldir
(masalan "Chevening Scholarships 2027", "Erasmus Mundus").

HAVOLA
Havola yozma. Har bir imkoniyatga faqat uning RAQAMI (index) bilan murojaat qil.
Havolani tizim o'zi qo'yadi.

QAT'IY TASHLA
1. Tashkilot/universitet topshiradigan institutsional grantlar.
   Belgilari: "principal investigator", "host institution", "eligible organizations",
   "consortium". Bunga bir kishi ariza topshira olmaydi.
2. O'zbekiston fuqarosi qatnasha olmaydiganlar: "for Nigerians only",
   "open to EU citizens only", "must be a US permanent resident".
3. Muddati o'tib ketganlar.
4. Yangilik, hisobot, "natijalar e'lon qilindi", "g'oliblar aniqlandi",
   "vebinar bo'lib o'tdi" tipidagilar.
5. Qo'llanma, namuna hujjat, "Top 10 ro'yxat" maqolalari.

QOLDIR
Stipendiya, fellowship, amaliyot, almashuv dasturi, yozgi maktab, xalqaro
tanlov va musobaqa, akselerator, yosh tadbirkorlar uchun moliyalashtirish —
bir kishi o'zi ariza topshira oladigan har qanday imkoniyat.

SIFAT MUHIMROQ
Yarim-yorti mos kelganini "shunchaki bo'lsin" deb qo'shma.
Bitta ham mos imkoniyat bo'lmasa, cards ni bo'sh ro'yxat qilib qaytar.

benefits — aniq faktlar bo'lsin ("oyiga $2,000 stipendiya", "aviabilet qoplanadi"),
umumiy gap emas ("ajoyib imkoniyat").
"""


def _config_for(model: str) -> types.GenerateContentConfig:
    """Har bir model o'z sozlamasini talab qiladi.

    "O'ylash" (thinking) sozlamasi modellar orasida farq qiladi:
      • Gemini 3.x — thinking_level="low"  (o'lchandi: 1624 → 471 token)
      • Gemini 2.5 — thinking_budget=0     (thinking_level ni qabul qilmaydi)
    """
    kwargs = dict(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=PostContent,
        # 0.9 juda yuqori edi: sarlavha xilma-xilligi uchun to'lanadigan narx —
        # muddat, stipendiya summasi va talablardagi xatolar. 0.35 da faktlar
        # barqaror, sarlavha esa baribir har safar boshqacha chiqadi (kirish
        # ma'lumoti har kuni yangi).
        temperature=0.35,
    )

    if model in _NO_THINKING_CONFIG:
        pass
    elif model.startswith("gemini-3") or model == "gemini-flash-latest":
        kwargs["thinking_config"] = types.ThinkingConfig(thinking_level="low")
    elif "2.5" in model:
        kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=0)

    return types.GenerateContentConfig(**kwargs)


def _build_prompt(grants: list) -> str:
    lines = ["Quyidagi imkoniyatlarni ko'rib chiq va postga mos kelganlarini tanla.\n"]
    for i, g in enumerate(grants, 1):
        lines.append(f"--- Imkoniyat {i} ---")
        lines.append(f"Nomi: {g.get('title', '')}")
        if g.get("deadline_iso"):
            lines.append(f"Tizim aniqlagan muddat: {g['deadline_iso']}")
        lines.append(f"Mazmuni: {(g.get('summary') or '')[:700]}")
        lines.append("")
    lines.append("Eslatma: javobda har bir imkoniyatga uning raqami (index) bilan murojaat qil.")
    return "\n".join(lines)


def _fallback_content(grants: list) -> dict:
    """AI ishlamasa ham post chiqishi uchun oddiy mazmun."""
    cards = []
    for i, g in enumerate(grants, 1):
        cards.append({
            "index": i,
            "name": (g.get("title") or "Imkoniyat").strip()[:140],
            "summary": re.sub(r"\s+", " ", (g.get("summary") or ""))[:240],
            "benefits": [],
            "eligibility": "",
            "deadline_iso": g.get("deadline_iso"),
        })
    return {"headline": "Yangi imkoniyatlar", "cards": cards, "usage": {}}


def generate_post_content(grants: list) -> dict:
    """Imkoniyatlar ro'yxatidan post mazmunini tayyorlaydi.

    Qaytaradi: {"headline": str, "cards": [...], "usage": {...}} yoki None.
    Har bir kartochkaga asl `url` shu yerda biriktiriladi — AI dan emas,
    bizning ma'lumotimizdan.
    """
    if not grants:
        return None

    if not client:
        return _attach_urls(_fallback_content(grants), grants)

    prompt = _build_prompt(grants)
    chain = list(MODEL_CHAIN)
    last_error = None

    for attempt in range(MAX_ATTEMPTS):
        model = chain[min(attempt, len(chain) - 1)]
        try:
            resp = client.models.generate_content(
                model=model, contents=prompt, config=_config_for(model))
        except Exception as e:
            last_error = e
            msg = str(e)

            if "hinking" in msg and "not supported" in msg and model not in _NO_THINKING_CONFIG:
                _NO_THINKING_CONFIG.add(model)
                print(f"  {model} 'thinking' sozlamasini qo'llamaydi — sozlamasiz qayta urinamiz.")
                chain.insert(attempt + 1, model)
                continue

            if any(c in msg for c in ("503", "429", "500", "UNAVAILABLE", "RESOURCE_EXHAUSTED")):
                wait = 5 * (attempt + 1)
                print(f"  {model} band. {wait}s kutib, keyingi modelga o'tamiz...")
                time.sleep(wait)
                continue

            print(f"  AI xatoligi ({model}): {type(e).__name__}: {msg[:120]}")
            break

        raw = re.sub(r"^```(?:json)?|```$", "", (resp.text or "").strip()).strip()
        if not raw:
            print(f"  {model} bo'sh javob qaytardi.")
            continue

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"  JSON o'qib bo'lmadi ({model}): {e}")
            continue

        cards = data.get("cards") or []
        if not cards:
            print("  AI mos imkoniyat topmadi — bu to'plam o'tkazib yuborildi.")
            return None

        usage = {}
        if getattr(resp, "usage_metadata", None):
            u = resp.usage_metadata
            usage = {"model": model, "prompt": u.prompt_token_count,
                     "output": u.candidates_token_count, "total": u.total_token_count}

        return _attach_urls({"headline": data.get("headline", ""),
                             "cards": cards, "usage": usage}, grants)

    print(f"  Barcha urinishlar barbod bo'ldi ({last_error}). Zaxira mazmun ishlatiladi.")
    return _attach_urls(_fallback_content(grants), grants)


def _attach_urls(content: dict, grants: list) -> dict:
    """Har bir kartochkaga ASL havolani biriktiradi.

    AI faqat index qaytaradi. Index noto'g'ri bo'lsa — kartochka tashlanadi.
    Havola AI dan EMAS, bizning ma'lumotimizdan olinadi.
    """
    valid = []
    dropped = 0
    bad_deadlines = 0

    for card in content.get("cards", []):
        try:
            idx = int(card.get("index", 0))
        except (TypeError, ValueError):
            dropped += 1
            continue

        if not (1 <= idx <= len(grants)):
            dropped += 1
            continue

        source = grants[idx - 1]
        url = source.get("url", "")
        if not url:
            dropped += 1
            continue

        card["url"] = url
        card["_source"] = source

        # Muddatni tekshiramiz. AI ba'zan yilni noto'g'ri o'qiydi — kanalda
        # "Oxirgi muddat: 10-avgust, 2024" chiqib qolgan edi. O'tib ketgan yoki
        # haddan tashqari uzoq sana rad etiladi va o'zimiz topganiga qaytamiz.
        checked = validate_deadline_iso(card.get("deadline_iso"))
        if card.get("deadline_iso") and not checked:
            print(f"  ⚠️  ishonchsiz muddat rad etildi: {card.get('deadline_iso')} "
                  f"({str(card.get('name'))[:40]})")
            bad_deadlines += 1
        card["deadline_iso"] = checked or validate_deadline_iso(source.get("deadline_iso"))

        valid.append(card)

    if dropped:
        print(f"  {dropped} ta kartochka noto'g'ri raqam sababli tashlandi.")

    content["cards"] = valid
    return content


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    demo = [
        {"title": "Chevening Scholarships 2027", "url": "https://www.chevening.org/apply/",
         "summary": "Fully funded UK master's degree. Covers tuition, monthly stipend, "
                    "return airfare. Open to citizens of Chevening-eligible countries "
                    "including Uzbekistan. Requires 2 years work experience. "
                    "Deadline: 5 November 2026.",
         "deadline_iso": "2026-11-05T23:59:59Z"},
        {"title": "NSF PESOSE Research Grant", "url": "https://nsf.gov/x",
         "summary": "Principal investigators at eligible US institutions may apply. "
                    "Host institution required."},
    ]

    res = generate_post_content(demo)
    print(json.dumps({k: v for k, v in res.items() if k != "cards"}, ensure_ascii=False, indent=2))
    for c in res["cards"]:
        print(f"\n  nomi   : {c['name']}")
        print(f"  havola : {c['url']}")
        print(f"  tavsif : {c['summary']}")
        print(f"  foyda  : {c.get('benefits')}")
        print(f"  kim    : {c.get('eligibility')}")
        print(f"  muddat : {c.get('deadline_iso')}")
