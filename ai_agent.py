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

MODEL_CHAIN = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash"]
MAX_ATTEMPTS = 4
BATCH_SIZE = 8               # bitta so'rovga nechta imkoniyat

# "thinking" sozlamasini qabul qilmagan modellar
_NO_THINKING_CONFIG = set()

# Bir nechta Gemini API kalitlari ro'yxati (kalitlar rotatsiyasi va 429/503 da uzluksiz o'tish)
_raw_keys = os.getenv("GEMINI_API_KEYS", "") or os.getenv("GEMINI_API_KEY", "")
API_KEYS = [k.strip() for k in re.split(r"[,;\s]+", _raw_keys) if k.strip() and "your_google" not in k]
for i in range(1, 10):
    k = os.getenv(f"GEMINI_API_KEY_{i}")
    if k and k.strip() and k.strip() not in API_KEYS:
        API_KEYS.append(k.strip())


def get_client(index: int = 0) -> Optional[genai.Client]:
    if not API_KEYS:
        return None
    key = API_KEYS[index % len(API_KEYS)]
    return genai.Client(api_key=key)


client = get_client(0)


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
Auditoriya — O'zbekistondagi talabalar, yosh mutaxassislar, olimlar va tadbirkorlar.
Ular JISMONIY SHAXS sifatida ariza topshiradi.

QAMROV (O'ZBEKISTON FUQAROLARI UCHUN)
1. Mahalliy O'zbekiston imkoniyatlari: "El-yurt umidi", Yoshlar ishlari agentligi,
   IT Park tanlovlari, vazirlik va davlat stipendiyalari, startap akseleratorlar.
2. Xalqaro nufuzli dasturlar: O'zbekiston fuqarolari qatnasha oladigan barcha xalqaro
   hukumat grantlari (Turkiye Burslari, Stipendium Hungaricum, Chevening, Fulbright,
   DAAD, Erasmus Mundus, MEXT, GKS, CSC va h.k.), xalqaro amaliyotlar, yozgi maktablar.

USLUB
Zamonaviy, jiddiy, aniq. Emoji ishlatma. Suv gap va ortiqcha maqtov yo'q.
O'zbek tilida yoz. Imkoniyat nomini tarjima qilma — original nomda qoldir
(masalan "Chevening Scholarships 2027", "Stipendium Hungaricum", "Erasmus Mundus").

HAVOLA
Havola yozma. Har bir imkoniyatga faqat uning RAQAMI (index) bilan murojaat qil.
Havolani tizim o'zi qo'yadi.

QAT'IY TASHLA
1. Tashkilot/universitet topshiradigan institutsional grantlar.
   Belgilari: "principal investigator", "host institution", "eligible organizations",
   "consortium". Bunga bir kishi ariza topshira olmaydi.
2. O'zbekiston fuqarosi qatnasha OLMAYDIGAN cheklovli grantlar:
   "for African citizens only", "for Nigerian students", "open to EU citizens only",
   "must be a US permanent resident", "ASEAN nationals only".
3. Muddati o'tib ketganlar.
4. Yangilik, hisobot, "natijalar e'lon qilindi", "g'oliblar aniqlandi",
   "vebinar bo'lib o'tdi" tipidagilar.
5. Qo'llanma, namuna hujjat, "Top 10 ro'yxat" maqolalari.

QOLDIR
Stipendiya, fellowship, amaliyot, almashuv dasturi, yozgi maktab, xalqaro
tanlov va musobaqa, akselerator, yosh tadbirkorlar uchun moliyalashtirish —
O'zbekistonlik bir kishi o'zi ariza topshira oladigan har qanday imkoniyat.

SIFAT MUHIMROQ
Yarim-yorti mos kelganini "shunchaki bo'lsin" deb qo'shma.
Bitta ham mos imkoniyat bo'lmasa, cards ni bo'sh ro'yxat qilib qaytar.

benefits — aniq faktlar bo'lsin ("oyiga $2,000 stipendiya", "aviabilet qoplanadi",
"kontrakt 100% to'lanadi"), umumiy gap emas ("ajoyib imkoniyat").
"""


def _config_for(model: str) -> types.GenerateContentConfig:
    """Har bir model o'z sozlamasini talab qiladi.

    Gemini 3.8 va 3.7 flagmanlarida thinking_level='high' chuqur fikrlash va
    O'zbekiston fuqarolariga moslikni benuqson tahlil qilishni ta'minlaydi.
    """
    kwargs = dict(
        system_instruction=SYSTEM_INSTRUCTION,
        response_mime_type="application/json",
        response_schema=PostContent,
        temperature=0.2,
    )

    if model in _NO_THINKING_CONFIG:
        pass
    elif "3.8" in model or "3.7" in model:
        try:
            kwargs["thinking_config"] = types.ThinkingConfig(thinking_level="high")
        except Exception:
            pass
    elif "3.6" in model or "3.5" in model or "flash" in model:
        try:
            kwargs["thinking_config"] = types.ThinkingConfig(thinking_level="medium")
        except Exception:
            pass

    return types.GenerateContentConfig(**kwargs)


def resolve_official_url_with_ai(title: str, text: str, candidates: list) -> Optional[str]:
    """Gemini 3.8 Flash (thinking_level='high') orqali maqola ichidagi asl rasmiy havolani aniqlaydi.

    Agregator, ijtimoiy tarmoq yoki reklama havolalarini qat'iyan rad etadi.
    Faqat original tashkilot yoki dasturning haqiqiy veb-saytini tanlaydi.
    """
    if not API_KEYS or not candidates:
        return None

    valid_candidates = []
    for c in candidates:
        u = str(c or "").strip()
        if u.startswith(("http://", "https://")) and u not in valid_candidates:
            valid_candidates.append(u)

    if not valid_candidates:
        return None

    prompt = (
        f"Imkoniyat sarlavhasi: {title}\n"
        f"Matn qismi:\n{(text or '')[:1000]}\n\n"
        f"Nomzod havolalar ro'yxati:\n" + "\n".join(f"- {c}" for c in valid_candidates[:14]) + "\n\n"
        "Vazifa: Ushbu grant/stipendiya/tanlovning RASMIY TASHKILOT yoki UNIVERSITET veb-saytiga "
        "tegishli asl ariza yoki rasmiy e'lon sahifasi havolasini tanla. "
        "Hech qanday agregator (opportunitydesk, scholarshiproar, grantlar, edugrants va h.k.), "
        "telegram kanallar yoki ijtimoiy tarmoqlarni tanlama.\n"
        "QAT'IY QOIDA: Tanlangan havola sarlavhadagi tashkilot/universitetga tegishli bo'lishi shart! "
        "Begona tashkilot/dastur havolasini (masalan, Imperial College postiga Gates Cambridge havolasini) "
        "aslo tanlama. Agar nomzodlar orasida aynan shu grantning rasmiy arizasi bo'lmasa, NONE deb yoz.\n"
        "Javobni FAQAT bitta to'liq URL yoki NONE qilib qaytar."
    )

    for i in range(len(API_KEYS)):
        cli = get_client(i)
        if not cli:
            continue
        for model in MODEL_CHAIN[:2]:
            try:
                cfg_kwargs = {"temperature": 0.0}
                if "3.8" in model or "3.7" in model:
                    try:
                        cfg_kwargs["thinking_config"] = types.ThinkingConfig(thinking_level="high")
                    except Exception:
                        pass
                resp = cli.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(**cfg_kwargs)
                )
                ans = (resp.text or "").strip()
                if ans and ans != "NONE" and ans.startswith("http"):
                    clean_ans = ans.split()[0].rstrip(".,;)\"'>")
                    return clean_ans
            except Exception:
                continue

    return None


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

    if not API_KEYS:
        return _attach_urls(_fallback_content(grants), grants)

    prompt = _build_prompt(grants)
    chain = list(MODEL_CHAIN)
    last_error = None
    num_keys = max(1, len(API_KEYS))
    total_attempts = MAX_ATTEMPTS * num_keys

    for attempt in range(total_attempts):
        cli = get_client(attempt % num_keys)
        model = chain[(attempt // num_keys) % len(chain)]
        try:
            resp = cli.models.generate_content(
                model=model, contents=prompt, config=_config_for(model))
        except Exception as e:
            last_error = e
            msg = str(e)

            if "hinking" in msg and "not supported" in msg and model not in _NO_THINKING_CONFIG:
                _NO_THINKING_CONFIG.add(model)
                print(f"  {model} 'thinking' sozlamasini qo'llamaydi — sozlamasiz qayta urinamiz.")
                continue

            if any(c in msg for c in ("503", "429", "500", "UNAVAILABLE", "RESOURCE_EXHAUSTED")):
                wait = 2 * ((attempt % num_keys) + 1)
                print(f"  {model} (kalit #{attempt % num_keys + 1}) band. Keyingi kalit/modelga o'tamiz...")
                time.sleep(wait)
                continue

            print(f"  AI xatoligi ({model}): {type(e).__name__}: {msg[:120]}")
            continue

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
