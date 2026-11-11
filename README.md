# Nova Grants

O'zbekiston fuqarolari ariza topshira oladigan xalqaro stipendiya, fellowship,
amaliyot, yozgi maktab, tanlov va yoshlar dasturlarini topib,
[@Nova_Grants](https://t.me/Nova_Grants) kanaliga saralab beradigan bot.

**2026-11-11 yangilanishi:** kod lokal `codex/reliability-audit` branchida.
Production hali yangilanmagan. [Yakuniy audit](docs/FINAL_AUDIT_2026-11-11.md),
[manbalar tekshiruvi](docs/SOURCES_2026-11-11.md),
[xabar ko'rinishi namunasi](docs/post_preview.html).

## Qanday ishlaydi

```text
30 manba → mavzu / muddat filtri → avvalgi source kalitlari
         → rasmiy havola → bog'langan takror guruhlari
         → eligibility dalili bilan Gemini saralashi
         → rich xabar → kanal → Supabase yozuvi
Supabase muddati yaqin posted yozuvlar → eslatma
```

- **30 manba:** 14 RSS, 16 Telegram; 10 rasmiy va 20 aggregator.
- **Rasmiy link:** feed ichidagi ariza URL'lari ham ishlatiladi; aggregator URL'lari postga qo'yilmaydi.
- **Yagona vakil:** bir dastur haqidagi bog'langan yozuvlardan eng ko'p dalili bor manba tanlanadi; postdan keyin qolganlari alias sifatida eslab qolinadi.
- **Tashkilot doirasi:** umumiy bir xil sarlavha turli tashkilotlardagi grantlarni avtomatik birlashtirmaydi.
- **Moslik dalili:** AI kartochkasi manba matnidan aynan olingan eligibility iqtibosini qaytarishi kerak. Fuqarolik va yashash talablari alohida tekshiriladi.
- **Vaqtinchalik xato:** resolution/AI nosozligi doimiy rad etish deb saqlanmaydi; baza yozish xatosi yashirilmaydi.
- **Emojisiz uslub:** sarlavha, yig'iladigan tafsilotlar, tashqarida ko'rinadigan muddat, bitta ariza tugmasi.

Barcha dunyo dasturlarini topish yoki barcha vaziyatlarda takror bo'lmasligi
kafolatlanmaydi. Muhim qoldiq cheklovlar auditda dalillari bilan yozilgan.

## O'rnatish

Python 3.11 yoki 3.13 bilan:

```bash
python -m venv .venv
# Windows: .venv/Scripts/activate
# Linux/macOS: source .venv/bin/activate
python -m pip install --upgrade 'pip>=26.2,<27'
python -m pip install -r requirements.txt -c constraints.txt
# Ixtiyoriy brauzer TLS mijozi:
python -m pip install -r requirements-optional.txt -c constraints.txt
```

`constraints.txt` — tekshirilgan paketlar snapshot'i. Yangilashdan keyin testlar
va dependency audit qayta bajarilishi kerak.

`.env.example` ni `.env` deb nusxalab to'ldiring. Production uchun:
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`, `GEMINI_API_KEY` (yoki `GEMINI_API_KEYS`),
`SUPABASE_URL`, `SUPABASE_KEY`. `ADMIN_ID` — ixtiyoriy kunlik/nosozlik hisoboti.

Baza: `posted_grants` jadvali mavjud bo'lishi kerak. `migration.sql` mavjud
jadvalni yangilaydi; toza Supabase loyihasi uchun boshlang'ich CREATE TABLE
skripti hozir alohida tayyorlanmagan. Ishlayotgan baza va ruxsatlarni bilmasdan
migratsiyani qayta ishga tushirmang; tarixiy `migration_fix.sql` ma'lumot uchun
saqlangan. RLS/key roli masalasi yakuniy auditda ko'rsatilgan.

```bash
python main.py --dry-run
python main.py
```

`--dry-run` Telegram'ga hech narsa yubormaydi va bazani o'zgartirmaydi.
U manba saytlarini o'qiydi, sozlangan bo'lsa Gemini va Supabase o'qishlaridan
foydalanadi. AI kaliti bo'lmasa tekshirilmagan mazmun nashr qilinmaydi.

## Telegram formati

Rasmiy [Bot API hujjati](https://core.telegram.org/bots/api) asosida ishlatilayotgan
bloklar `rich_schema.py` da tekshiriladi. Rich xabar rad etilsa avval yangi
ko'rinish elementlari olib tashlangan eski rich format, keyin oddiy HTML
zaxirasi sinaladi. Timeout yoki noaniq yuborish natijasida avtomatik boshqa
formatda qayta post qilinmaydi.

HTML zaxira `sendMessage` uchun alohida 4096 chegarasiga mos bo'linadi.
Rich bloklar soni, ichma-ichligi, matn va tugma strukturalari alohida tekshiriladi.
Kanalga yuboriladigan xabarlar uchun callback server talab qilmaydigan ariza
amali va ichki navigatsiya tanlangan. Shaxsiy-chat HTML widgetlari kanalga yuborilmaydi.
Har bir grantda bitta ariza tugmasi bor: takroriy link va nusxalash tugmasi yo'q.
Original postni kanal manbasi bilan tarqatish Telegram'ning native Forward amali orqali ishlaydi.

## Tekshirish

```bash
python -m pytest tests/ -q
python tools/check_rich_spec.py
python -m pip check
python tools/check_sources.py --json docs/source_health_latest.json
python tools/preview_post.py
```

Windows'da host pytest plaginlari xalaqit qilsa:

```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
.\.venv\Scripts\python.exe -m pytest tests/ -q
```

143 ta tarmoqsiz regression/integratsiya testi Python 3.11 va 3.13'da o'tgan.
Testlar haqiqiy `.env`/kalitlarni yuklamaydi, socket ulanishlarini bloklaydi.
Jonli manba tekshiruvi va URL smoke natijalari `docs/` ichida sanasi bilan saqlangan.
Yangi testlar, statik correctness/security va dependency audit push/PR workflow'iga qo'shilgan.

## Sozlash

```text
main.py:     MAX_RESOLVE_PER_RUN=80, MAX_POST_PER_RUN=32, RESOLVE_WORKERS=14
scraper.py:  MAX_PER_SOURCE=60, MAX_AGE_DAYS=60
.env:        GEMINI_THINKING_LEVEL=medium, AI_TIMEOUT_SECONDS=240
ai_agent.py: BATCH_SIZE=8; muharrirga maksimal 8, link tanlashga 2 urinish
```

Bir nechta manbalar resolution limitini round-robin bo'yicha bo'lishadi.
Yangi kalitda 3.6 Flash ikki takroriy saralash sinovidan o'tdi; standart zanjir 3.8 Flash → 3.7 Flash → 3.6 Flash (medium), GEMINI_MODELS bilan boshqariladi. Keng sifat benchmarki hali bajarilmagan.

GitHub Actions `20 0 * * *` (05:20 Toshkent) cron'i bilan navbatga qo'yiladi.
Haqiqiy boshlanish vaqti kafolatlanmaydi. Qo'lda Actions → Nova Grants Bot →
Run workflow, kerak bo'lsa `dry_run=true`.

## Fayllar

| Fayl | Vazifa |
|---|---|
| `sources.py` | Manbalar, o'chirish sabablari va source-specific siyosatlar |
| `scraper.py` | RSS/Telegram/API yig'ish va yangilik chegarasi |
| `opportunity_content.py` | Uzun maqoladan eligibility/deadline dalillarini saqlash |
| `filters.py` | Mavzu va muddat filtrlari |
| `http_client.py` | HTTP va ixtiyoriy TLS mijozi |
| `link_resolver.py` | Rasmiy URL, redirect, kalitlar va dastur identifikatori |
| `database.py` | Dedup o'qish, tasdiqlangan saqlash va eslatma holati |
| `ai_agent.py` | Tuzilgan javob, moslik iqtibosi va AI urinish chegaralari |
| `post_builder.py` | Bir mazmundan rich bloklar va HTML |
| `rich_schema.py` | Yuboriladigan rich formatning lokal validatori |
| `telegram_bot.py` | Xabar bo'lish, yuborish va aniq/noaniq xato farqi |
| `main.py` | Yig'ishdan nashrgacha quvur va kunlik hisobot |
| `tests/` | Tarmoqsiz testlar |
| `tools/` | Manba/sxema tekshiruvi va mahalliy ko'rinish |
| `docs/` | Auditlar, tekshiruv dalillari va namuna |

`legacy/` dagi skriptlarni avtomatik ishga tushirmang: ayrimlari tashqi kanalga
xabar yuboradi va eski interfeyslar uchun yozilgan.
