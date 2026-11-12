# Nova Grants

O'zbekistondan ariza topshiradigan talabalar, tadqiqotchilar va yosh mutaxassislar
uchun xalqaro imkoniyatlarni saralab, [@Nova_Grants](https://t.me/Nova_Grants)
kanaliga kunlik digest chiqaradigan bot.

## Nashr mezoni

Dastur shaxs ariza topshira oladigan, ochiq qabulga va tasdiqlangan amaliy yoki
moliyaviy foydaga ega bo'lishi kerak. Fuqarolik, hozirgi yashash/o'qish joyi,
qabul talablari, moliyalashtirish va majburiy xarajatlar alohida tekshiriladi.
Kelajakdagi xorijiy qabul/ilmiy mezbon taklifi avvaldan xorijda yashashga teng emas.

- **Rasmiy dalil:** aggregator kashf qilish uchun; qaror dastur tashkilotchisi sahifasidan olinadi.
- **Auditoriyaga moslik:** O'zbekistondan topshirish tasdiqlanadi. Mavjud AQSh rezidentligi yoki xorijiy OTMda avvaldan o'qish shartli dasturlar avtomatik chiqmaydi.
- **Moliyalashtirish:** to'liq yordam, faqat kontrakt, qisman grant, stipendiya va chegirma bir-biridan ajratiladi. Pul miqdori/manbasi tekshiriladi.
- **Pullik xususiy forum:** avtomatik nashr qilinmaydi. Universitet/davlat ariza to'lovi manbasi va xarajati bilan alohida baholanadi.
- **Saralash qarori:** mos, asosli rad, tekshiruv yoki qayta urinish. Model tilga olmagan nomzod doimiy rad etilmaydi.
- **Ustuvorlik:** dastur foydasi, moliyalashtirish, tashkilot va muddat. Matn uzunligi reklama ustunligini bermaydi.
- **Eslatma:** eski bazadagi grant ham amaldagi saralashdan qayta o'tadi.

## Quvur

```text
30 manba -> mavzu / sana -> manba identifikatori -> rasmiy havola
         -> takror guruhlari -> rasmiy sahifa dalillari
         -> tuzilgan AI saralashi -> mustaqil nashr siyosati
         -> ustuvorlik -> bitta xabarga mos digest
         -> saqlangan niyat / claim -> Telegram -> baza tasdig'i
```

Kunlik jurnal Toshkent sanasi bilan ishlaydi. Tasdiqlangan postdan keyingi baza
xatosida faqat yozuvlar tiklanadi; post qayta yuborilmaydi. Noma'lum Telegram
natijasi avtomatik qayta yuborilmaydi. Vaqtinchalik baza xatosi cheklangan
urinishlar bilan tiklanadi. Bitta buzilgan manba yoki sahifa qolganlarini tashlab
yubormaydi. Yaroqli digest bo'lsa ayrim AI nomzodlari keyinga qoldirilib, yurish
ogohlantirish bilan tugaydi.

## Ishga tushirish

Python 3.11/3.13 qo'llanadi; production runtime 3.13.18 bilan pin qilingan.

```bash
python -m venv .venv
python -m pip install --upgrade 'pip>=26.2,<27'
python -m pip install -r requirements.txt -c constraints.txt
# Ixtiyoriy TLS mijozi:
python -m pip install -r requirements-optional.txt -c constraints.txt
```

`.env.example` nusxasini `.env` qilib to'ldiring. Kalitlarni kodga yoki oddiy
Variables'ga joylamang; GitHub Actions'da encrypted Secrets ishlatiladi.
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`, `SUPABASE_URL`, `SUPABASE_KEY` va
kamida bitta AI provayderi kerak. `ADMIN_ID` operatsion xabarlar uchun.

Standart ishlaydigan asosiy model: `gemini-3.6-flash`, medium thinking. Gemini
javob bermasa Groq `openai/gpt-oss-120b` ishlatiladi. `GEMINI_MODELS`,
`GEMINI_THINKING_LEVEL`, `AI_TIMEOUT_SECONDS`, `GROQ_MODEL` bilan sozlanadi.
Model o'zgarishi yangi sinov va CI bilan chiqariladi.

Mavjud Supabase `posted_grants` jadvali va uning indekslari talab qilinadi.
`migration.sql` mavjud jadval uchun. Ishlayotgan bazada tarixiy migratsiyalarni
ko'r-ko'rona qayta ishga tushirmang.

```bash
python main.py --dry-run  # Telegram/baza yozuvlarisiz, jonli manba va AI bilan
python main.py            # haqiqiy yurish
```

Actions'da **Nova Grants Bot -> Run workflow**. Kunlik cron `20 0 * * *`;
GitHub navbati sabab boshlanish vaqti kafolatlanmaydi. Har yurish artefaktida
`bot_run.log` va `selection_report.json` saqlanadi. Hisobotda nomzodning bosqichi,
qarori va sababi bor; kalit va providerning xom payloadi saqlanmaydi.

## Tekshirish va xizmat ko'rsatish

```bash
python -m pytest tests/ -q
python tools/check_rich_spec.py
python tools/audit_coverage.py --json discovery_audit.json
python tools/review_queue.py --limit 50
```

300 dan ortiq tarmoqsiz regression/integratsiya testi manba, eligibility,
residence, fees, funding, ranking, deadline, dedup, jurnal va uzilishlarni qamraydi.
CI Python 3.11/3.13, Ruff, Bandit va dependency auditni bajaradi. `main` talab
qilingan CI tekshiruvlari bilan himoyalangan.

Foydalanuvchi digestni o'chirganini **aniq tasdiqlagandagina**, xabar ID'i jurnalga
mosligi tekshirilib eski niyat arxivlanishi mumkin:

```bash
python tools/requeue_deleted_digest.py --message-id MESSAGE_ID --confirmed-deleted
```

Bu avtomatik retry emas: faqat o'chirilgan digest yozuvlarini qayta navbatga
qaytaradi, boshqa postlarga tegmaydi. Eski yozuvlar tarixi saqlanadi.

## Audit va amaliy chegaralar

- [Saralashning to'liq auditi](docs/SELECTION_AUDIT_2026-11-12.md)
- [Uzilishlarga qarshi himoya](docs/RELIABILITY_2026-11-12.md)
- [Yuborish jurnali va tiklash](docs/delivery-journal.md)
- [Oldingi incident](docs/INCIDENT_2026-11-12.md)
- [Manbalar snapshot'i](docs/SOURCES_2026-11-11.md)

Bir URL'dagi yangi yillik qabul eski legacy yozuv bilan to'qnashsa, jim takror
deb tashlanmaydi; yangi qabulni tasdiqlash uchun review navbatiga olinadi. Hamma
saytni o'qish yoki barcha tabiiy til shartlarini mutlaq xatosiz tushunish
kafolatlanmaydi. Noaniq moslik va yetishmagan dalil avtomatik nashrga sabab emas.
