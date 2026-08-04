"""Qamrov auditi: har bosqichda nima tushib qolyapti va NEGA?

Maqsad — O'zbekiston uchun foydali grant filtrlarga ilinib qolmayotganini tekshirish.
Tarmoqqa faqat yig'ish bosqichida chiqadi (asl havola qazilmaydi), shuning uchun tez.

Ishlatish:
    python tools/audit_coverage.py
"""

import sys, os, re, random
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

from scraper import fetch_all
from filters import (
    looks_like_opportunity, deadline_passed, extract_deadline,
    POSITIVE, NEGATIVE, STRONG, NOT_AN_OPPORTUNITY, INSTITUTIONAL_ONLY, INDIVIDUAL_SIGNAL,
)

# O'zbekistonlik uchun qimmatli imkoniyat belgilari — "oltin standart".
# Agar shulardan biri filtrdan o'tmasa, bu ANIQ xato (false negative).
HIGH_VALUE = re.compile(
    r"\b(fully[\s-]funded|full\s+scholarship|tuition\s+(waiver|free|covered)"
    r"|chevening|fulbright|erasmus|daad|mext|gks\b|stipendium|schwarzman|rhodes"
    r"|gates\s+cambridge|knight[\s-]hennessy|yenching|humphrey|mandela\s+washington"
    r"|scholarship\s+for\s+international|open\s+to\s+all\s+nationalities"
    r"|international\s+students\s+(are\s+)?(eligible|welcome|can\s+apply)"
    r"|all\s+nationalities|worldwide|developing\s+countries"
    r"|summer\s+school|exchange\s+program|youth\s+exchange"
    r"|to'liq\s+moliyalash|bepul\s+ta'lim|to'liq\s+grant)\b",
    re.I,
)

# O'zbekiston aniq nomma-nom tilga olingan holatlar
UZ_MENTION = re.compile(r"(uzbek|o'zbek|ozbek|central\s+asia|markaziy\s+osiyo|cis\b|узбек)", re.I)


def why_rejected(title, summary):
    """Yozuv nega rad etilganini aniqlaydi."""
    text = f"{title}\n{summary}"
    if deadline_passed(text):
        return "muddati o'tgan"
    if NOT_AN_OPPORTUNITY.search(title or ""):
        return "qo'llanma/namuna/ro'yxat maqolasi"
    if INSTITUTIONAL_ONLY.search(text) and not INDIVIDUAL_SIGNAL.search(text):
        return "tashkilotlar uchun (jismoniy shaxs emas)"
    if NEGATIVE.search(text):
        if not (STRONG.search(text) and POSITIVE.search(text)):
            return "yangilik/reklama belgisi"
    if not POSITIVE.search(text):
        return "imkoniyat so'zlari yo'q"
    if not POSITIVE.search(title or "") and not STRONG.search(text):
        return "sarlavhada signal yo'q, tanada ham kuchsiz"
    return "(sabab aniqlanmadi)"


items = fetch_all()
print()

kept, dropped = [], []
for it in items:
    if looks_like_opportunity(it.get("title", ""), it.get("summary", ""), it.get("topic", "")):
        kept.append(it)
    else:
        it["_reason"] = why_rejected(it.get("title", ""), it.get("summary", ""))
        dropped.append(it)

print("=" * 78)
print(f"JAMI {len(items)} ta yozuv  →  o'tdi {len(kept)} ta, tashlandi {len(dropped)} ta")
print("=" * 78)

print("\n── TASHLANISH SABABLARI ──")
for reason, n in Counter(d["_reason"] for d in dropped).most_common():
    print(f"  {n:>4}  {reason}")

# ─────────────────────────────────────────────────────────────────
# ENG MUHIM TEKSHIRUV: qimmatli imkoniyat tashlanib ketdimi?
# ─────────────────────────────────────────────────────────────────
false_negatives = [
    d for d in dropped
    if HIGH_VALUE.search(f"{d.get('title','')}\n{d.get('summary','')}")
    and d["_reason"] not in ("muddati o'tgan", "qo'llanma/namuna/ro'yxat maqolasi")
]

print("\n" + "=" * 78)
print(f"XAVFLI: qimmatli belgilarga ega, lekin TASHLANGAN yozuvlar — {len(false_negatives)} ta")
print("=" * 78)
for d in false_negatives[:20]:
    print(f"\n  [{d['source_id']}] {d.get('title','')[:78]}")
    print(f"     sabab: {d['_reason']}")
    snippet = re.sub(r"\s+", " ", d.get("summary", ""))[:190]
    print(f"     matn : {snippet}")

# O'zbekiston tilga olingan yozuvlar
uz_kept = [k for k in kept if UZ_MENTION.search(f"{k.get('title','')}\n{k.get('summary','')}")]
uz_dropped = [d for d in dropped if UZ_MENTION.search(f"{d.get('title','')}\n{d.get('summary','')}")]

print("\n" + "=" * 78)
print(f"O'ZBEKISTON/Markaziy Osiyo tilga olingan: o'tdi {len(uz_kept)}, tashlandi {len(uz_dropped)}")
print("=" * 78)
for d in uz_dropped[:10]:
    print(f"  ❌ [{d['source_id']}] {d.get('title','')[:70]}")
    print(f"       sabab: {d['_reason']}")

# Muddat aniqlanish darajasi
with_deadline = sum(1 for k in kept if extract_deadline(f"{k.get('title','')}\n{k.get('summary','')}"))
print(f"\n── O'tganlarning {with_deadline}/{len(kept)} tasida muddat aniqlandi "
      f"({100 * with_deadline // max(len(kept), 1)}%)")

# Manba bo'yicha samaradorlik
print("\n── MANBA SAMARADORLIGI (o'tgan / jami) ──")
per_src = defaultdict(lambda: [0, 0])
for it in items:
    per_src[it["source_id"]][1] += 1
for k in kept:
    per_src[k["source_id"]][0] += 1
for sid, (ok, total) in sorted(per_src.items(), key=lambda x: -x[1][0]):
    bar = "█" * int(12 * ok / max(total, 1))
    print(f"  {sid:<24} {ok:>3}/{total:<3} {bar}")
