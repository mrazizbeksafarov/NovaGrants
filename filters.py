"""Nomzodlarni saralash: bu haqiqiy ochiq imkoniyatmi yoki shunchaki yangilikmi?

Bu bosqich AI dan OLDIN ishlaydi. Maqsad — Gemini ga yuborilayotgan ro'yxatni
tozalash: yangiliklar, reklama va muddati o'tgan e'lonlar shu yerda tushib qoladi.
Shu tufayli AI arzonroq ishlaydi va kanalga axlat tushmaydi.
"""

import re
from datetime import datetime, timezone, timedelta

# Ochiq imkoniyatga ishora qiluvchi so'zlar (inglizcha + o'zbekcha + ruscha)
POSITIVE = re.compile(
    r"\b("
    r"scholarship|scholarships|scholars|grant|grants|fellowship|fellowships|fellow"
    r"|bursary|stipend"
    r"|fully[\s-]funded|full[\s-]funded|funded|funding|tuition|assistantship"
    r"|call\s+for\s+(applications?|proposals?|papers?|nominations?)"
    r"|applications?\s+(are\s+)?(open|invited|now\s+open)|apply\s+now|now\s+accepting"
    r"|internship|traineeship|exchange\s+program|summer\s+school|winter\s+school"
    r"|competition|contest|olympiad|hackathon|challenge|award|prize"
    r"|accelerator|incubator|pre-?seed|residency|mobility\s+program"
    r"|phd\s+position|postdoc|masters?\s+program|undergraduate\s+program"
    r"|erasmus|chevening|fulbright|daad|mext|gks|vlir|nuffic|humphrey|mandela\s+washington"
    # o'zbekcha
    r"|grant|stipendiya|ariza|tanlov|musobaqa|konkurs|imkoniyat|dastur|amaliyot"
    r"|hujjat\s+qabul|qabul\s+boshlandi|ro'yxatdan\s+o'tish|bepul\s+ta'lim"
    # ruscha
    r"|стипенди|грант|конкурс|заявк|обучени|бесплатн|стажировк"
    r")\b",
    re.I,
)

# Yangilik/reklama belgilari — ochiq chaqiruv emas
NEGATIVE = re.compile(
    r"("
    r"raise[sd]?\s+\$|raises\s+€|secures\s+\$|closes\s+\$?\d+.{0,10}(round|funding)"
    r"|series\s+[a-e]\b|seed\s+round|funding\s+round|valuation|acquire[sd]?\b|acquisition"
    # DIQQAT: \bipo\b — ikkala tomonda ham chegara SHART.
    # Aks holda "WIPO" (Butunjahon intellektual mulk tashkiloti) ham ushlanib,
    # uning barcha amaliyot va fellowship e'lonlari yo'qoladi.
    r"|\bipo\b|merger|layoffs?|appoints?\b|steps?\s+down|resigns?\b|partners?\s+with"
    r"|launches\s+new\s+(feature|product|app)|announces\s+partnership"
    r"|webinar\s+(recap|replay)|recap\b|highlights\s+from|thank\s+you\s+for\s+attending"
    r"|winners?\s+announced|congratulations\s+to|meet\s+the\s+(winners|cohort)"
    r"|has\s+(been\s+)?closed|applications?\s+(are\s+)?closed|deadline\s+(has\s+)?passed"
    r"|sotuv|chegirma|reklama|obuna\s+bo'ling|kanalimizga"
    # o'zbekcha "natija/tabrik" e'lonlari — bular imkoniyat emas, hisobot
    r"|natijalar[i]?\s+e'lon\s+qilindi|natijalari\s+ma'lum|g'oliblar\s+aniqlandi"
    r"|tabriklaymiz|muvaffaqiyatli\s+(o'tkazildi|yakunlandi)|yakunlandi\b"
    r"|qabul\s+qilingan\s+talabalarimiz|erishdi\b"
    r")",
    re.I,
)

# O'zbekistonlik yosh uchun aniq qimmatli imkoniyat belgilari.
# Sarlavhada signal bo'lmasa ham, shulardan biri uchrasa yozuvni saqlab qolamiz —
# aynan shu ro'yxat Schwarzman, Knight-Hennessy kabi grantlarning tushib
# qolishining oldini oladi (ularning sarlavhasi shunchaki dastur nomi bo'ladi).
HIGH_VALUE = re.compile(
    r"("
    r"fully[\s-]funded|full\s+scholarship|tuition\s+(waiver|free|covered|fee\s+waiver)"
    r"|chevening|fulbright|erasmus|daad|mext|\bgks\b|schwarzman|rhodes\s+scholar"
    r"|gates\s+cambridge|knight[\s-]?hennessy|yenching|humphrey|mandela\s+washington"
    r"|open\s+to\s+all\s+nationalities|all\s+nationalities|international\s+students"
    r"|developing\s+countries|worldwide|no\s+application\s+fee"
    r"|to'liq\s+grant|to‘liq\s+grant|toʻliq\s+grant|to'liq\s+moliyalash|bepul\s+ta'lim"
    r"|100%\s*grant|full\s+grant"
    r")",
    re.I,
)

# Jismoniy shaxs emas, TASHKILOT topshiradigan grantlar (NSF, UKRI, ERC uslubi).
# O'zbekistonlik talaba yoki yosh mutaxassis bularga ariza topshira olmaydi.
INSTITUTIONAL_ONLY = re.compile(
    r"("
    r"principal\s+investigator|\bco-?PI\b|host\s+institution|lead\s+(applicant\s+)?organi[sz]ation"
    r"|eligible\s+(organi[sz]ations|institutions|applicants\s+are\s+(universities|institutions))"
    r"|research\s+organi[sz]ations\s+(may|can|are)|only\s+(universities|institutions|organi[sz]ations)"
    r"|uk-?based\s+(organi[sz]ations|researchers|institutions)|us-?based\s+(institutions|organi[sz]ations)"
    r"|accredited\s+institution|consortium\s+of\s+(at\s+least|partners)"
    r"|state\s+(agencies|governments)\s+(may|are)|nonprofits?\s+(may|are\s+eligible\s+to)\s+apply"
    r"|institutions\s+of\s+higher\s+education\s+(may|are)"
    r")",
    re.I,
)

# Jismoniy shaxsga qaratilganini bildiruvchi signal — yuqoridagini bekor qiladi
INDIVIDUAL_SIGNAL = re.compile(
    r"(students?|applicants?\s+must\s+be|young\s+(people|professionals|leaders)|youth"
    r"|candidates?\s+(must|should)|individuals?\s+(may|can|are\s+invited)"
    r"|bachelor|master|undergraduate|postgraduate|phd\s+(student|candidate|position)"
    r"|age\s+(limit|between|of)|aged?\s+\d{2}[\s-]|under\s+\d{2}\s+years"
    r"|talaba|yosh(lar)?|nomzod|ishtirokchi)",
    re.I,
)

# Grant emas, "kontent": namuna hujjatlar, qo'llanmalar va ro'yxat-maqolalar.
# Bularda bitta aniq ariza havolasi bo'lmaydi — kanalga tushishi mumkin emas.
NOT_AN_OPPORTUNITY = re.compile(
    r"("
    r"sample\s+(grant\s+)?proposal|proposal\s+(template|sample|example)|template\s+for"
    r"|how\s+to\s+(write|apply|prepare|get|find)|guide\s+to\b|a\s+complete\s+guide"
    r"|tips\s+(for|to)\b|everything\s+you\s+need\s+to\s+know|what\s+is\s+a\b"
    r"|top\s+\d+\s|best\s+\d+\s|\d+\s+(best|top)\s|list\s+of\s+\d+"
    r"|frequently\s+asked|faq\b|glossary|checklist"
    r"|qanday\s+(qilib|yozish)|qo'llanma|namuna\s+hujjat"
    r")",
    re.I,
)

# "Ariza topshirish" bilan bog'liq aniq signal — kuchli ishonch beradi
STRONG = re.compile(
    r"(deadline|apply\s+by|application\s+deadline|closing\s+date|last\s+date"
    r"|eligibility|eligible\s+(candidates|applicants|countries)|how\s+to\s+apply"
    r"|oxirgi\s+muddat|muddat|talablar|kimlar\s+ishtirok)",
    re.I,
)

# Sanani matndan topish uchun naqshlar
_MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9, "october": 10, "oct": 10,
    "november": 11, "nov": 11, "december": 12, "dec": 12,
}
_DATE_PATTERNS = [
    # 31 December 2026 / 31 Dec, 2026
    re.compile(r"\b(\d{1,2})\s+([a-z]{3,9})[,\s]+(\d{4})\b", re.I),
    # December 31, 2026 / Dec 31 2026
    re.compile(r"\b([a-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?[,\s]+(\d{4})\b", re.I),
    # 2026-12-31
    re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"),
    # 31/12/2026 yoki 31.12.2026
    re.compile(r"\b(\d{1,2})[./](\d{1,2})[./](\d{4})\b"),
]
_DEADLINE_CONTEXT = re.compile(
    r"(deadline|apply\s+by|closing\s+date|closes\s+on|last\s+date|due\s+(by|date)"
    r"|application[s]?\s+close|oxirgi\s+muddat|muddat)[^.\n]{0,80}",
    re.I,
)


def looks_like_opportunity(title: str, summary: str, topic: str = "") -> bool:
    """Bu yozuv ochiq imkoniyatga o'xshaydimi?"""
    text = f"{title}\n{summary}"

    # Qo'llanma / namuna / "Top 20" ro'yxati — sarlavhada bo'lsa darrov rad etamiz
    if NOT_AN_OPPORTUNITY.search(title or ""):
        return False

    # Tashkilotlar uchun grant — jismoniy shaxsga ishora bo'lmasa rad etamiz
    if INSTITUTIONAL_ONLY.search(text) and not INDIVIDUAL_SIGNAL.search(text):
        return False

    if NEGATIVE.search(text):
        # Salbiy signal bor — faqat juda kuchli ijobiy signal bo'lsa o'tkazamiz
        return bool(STRONG.search(text) and POSITIVE.search(text))

    if not POSITIVE.search(text):
        return False

    if POSITIVE.search(title or ""):
        return True

    # Sarlavhada signal yo'q. Telegram postlarida sarlavha ko'pincha emoji yoki
    # qisqa gap bo'ladi, shuning uchun tanadagi dalilga qaraymiz. Quyidagilardan
    # BIRORTASI yetarli:
    #   • ariza/muddat/talab haqida aniq gap (STRONG)
    #   • "to'liq grant", "fully funded", nufuzli dastur nomi (HIGH_VALUE)
    #   • imkoniyat so'zlari kamida ikki xil joyda uchrashi
    if STRONG.search(text) or HIGH_VALUE.search(text):
        return True

    return len(set(m.group(0).lower() for m in POSITIVE.finditer(text))) >= 2


def _try_build(y, m, d):
    try:
        if not (1 <= m <= 12 and 1 <= d <= 31):
            return None
        return datetime(y, m, d, 23, 59, 59, tzinfo=timezone.utc)
    except ValueError:
        return None


def extract_deadline(text: str):
    """Matndan oxirgi muddatni topadi. Topilmasa None.

    Avval "deadline: ..." kontekstidagi sanani qidiradi, topilmasa umuman
    matndagi kelajakdagi eng yaqin sanani oladi.
    """
    if not text:
        return None

    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=730)          # 2 yildan uzoq sanalar shubhali

    def scan(chunk):
        found = []
        for pat in _DATE_PATTERNS:
            for m in pat.finditer(chunk):
                g = m.groups()
                dt = None
                if pat is _DATE_PATTERNS[0]:
                    mon = _MONTHS.get(g[1].lower())
                    if mon:
                        dt = _try_build(int(g[2]), mon, int(g[0]))
                elif pat is _DATE_PATTERNS[1]:
                    mon = _MONTHS.get(g[0].lower())
                    if mon:
                        dt = _try_build(int(g[2]), mon, int(g[1]))
                elif pat is _DATE_PATTERNS[2]:
                    dt = _try_build(int(g[0]), int(g[1]), int(g[2]))
                else:
                    dt = _try_build(int(g[2]), int(g[1]), int(g[0]))
                if dt and now - timedelta(days=1) <= dt <= horizon:
                    found.append(dt)
        return found

    # 1) "deadline ..." atrofidagi sanalar ustuvor
    contexts = [m.group(0) for m in _DEADLINE_CONTEXT.finditer(text)]
    for ctx in contexts:
        hits = scan(ctx)
        if hits:
            return min(hits)

    # 2) Umumiy matn
    hits = scan(text)
    return min(hits) if hits else None


def validate_deadline_iso(iso):
    """AI bergan muddatni tekshiradi. Ishonchsiz bo'lsa None qaytaradi.

    Kanalda "Oxirgi muddat: 10-avgust, 2024" chiqib qolgan edi — AI yilni
    noto'g'ri o'qigan va hech kim tekshirmagan. Endi o'tib ketgan yoki juda
    uzoq sanalar rad etiladi.
    """
    if not iso or not isinstance(iso, str) or len(iso) < 10:
        return None

    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", iso.strip())
    if not m:
        return None

    dt = _try_build(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    if not dt:
        return None

    now = datetime.now(timezone.utc)
    if dt < now - timedelta(days=1):
        return None                              # o'tib ketgan
    if dt > now + timedelta(days=900):
        return None                              # ~2.5 yildan uzoq — shubhali
    return iso


def deadline_passed(text: str) -> bool:
    """Matnda faqat o'tib ketgan sana bo'lsa True (ya'ni e'lon eskirgan)."""
    if not text:
        return False
    if re.search(r"(applications?\s+(are\s+)?closed|deadline\s+(has\s+)?passed|muddat\s+tugagan)", text, re.I):
        return True
    return False


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    samples = [
        ("Chevening Scholarships 2027 Now Open", "Deadline: 5 November 2026. Fully funded UK study."),
        ("UK AI chip startup Olix raises €27M", "The company secured a Series B round led by..."),
        ("Winners announced for the Global Youth Prize", "Congratulations to the winners!"),
        ("MEXT Scholarship 2027", "Applications are invited. Apply by 2026-12-15."),
        ("Yangi grant dasturi e'lon qilindi", "Hujjat qabul boshlandi, oxirgi muddat 30.09.2026"),
    ]
    for t, s in samples:
        print(f"{'✅' if looks_like_opportunity(t, s) else '❌'}  {t}")
        print(f"     muddat: {extract_deadline(t + ' ' + s)}")
