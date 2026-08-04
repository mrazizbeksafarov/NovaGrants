# Nova Grants Bot

O'zbekiston yoshlari uchun xalqaro grant, stipendiya va fellowship imkoniyatlarini
avtomatik topib, [@Nova_Grants](https://t.me/Nova_Grants) kanaliga chiqaradigan bot.

**Uchta asosiy kafolat:**

1. **Faqat asl havola.** Kanalga aggregator saytlarning reklamaga to'la maqolasi emas,
   grantning rasmiy sahifasi tushadi. AI havolaga umuman tegmaydi — u faqat
   imkoniyat *raqamini* qaytaradi, havolani tizim o'zi qo'yadi. Ya'ni AI havolani
   o'zgartirishi texnik jihatdan mumkin emas.
2. **Takror yo'q.** Bitta imkoniyat necha marta, necha manbada chiqmasin — kanalga
   bir marta tushadi. Yagona istisno: muddati yaqinlashganda yuboriladigan eslatma.
3. **Zamonaviy ko'rinish.** Telegram Bot API 10.1+ "rich messages" — sarlavhalar,
   ro'yxatlar, yig'iladigan bo'limlar. Eski mijozlar uchun HTML zaxirasi
   avtomatik ishlaydi.

---

## Qanday ishlaydi

```
1. YIG'ISH     26 ta manba (RSS + Telegram)          →  ~350 yozuv
2. SARALASH    yangilik/reklama/qo'llanma tashlanadi →  ~210 yozuv
3. ESKIRIB     avval ko'rilgan maqolalar tashlanadi  →  faqat yangilari
4. QAZISH      maqola ichidan ASL havola topiladi    →  rasmiy sayt
5. TAKROR      3 qatlamli tekshiruv                  →  betakror ro'yxat
6. POST        Gemini mazmun yozadi → rich message → kanal
7. ESLATMA     muddati yaqinlashganlar haqida
```

### 4-bosqich: asl havola qazish (`link_resolver.py`)

Muammo shundaki, RSS'dagi havola aggregator maqolasiga olib boradi:

```
❌ https://opportunitydesk.org/2026/08/03/kas-saiia-scholarships-2027/   ← reklama
✅ https://pages.services/briefings.themidpoint.org.za/2027-kas-saiia-.../ ← ariza sahifasi
```

Modul maqolani ochib, ichidagi barcha havolalarni baholaydi: anchor matni
("Official website", "Apply now", "Rasmiy veb-sayt"), URL yo'li, domen turi va
maqoladagi o'rni. Eng yuqori ballisi tanlanadi, redirect'lar ochiladi.
Agar topilgan havola yana aggregator bo'lsa — yana bir bosqich chuqurroq qaziydi.

Asl havola topilmasa, yozuv **umuman post qilinmaydi**.

### 5-bosqich: takrorga qarshi 3 qatlam (`database.py`)

| Qatlam | Nima ushlaydi |
|---|---|
| `source_key` | Avval ko'rilgan maqola — qayta ochilmaydi ham (tarmoq tejaladi) |
| `url_key` | 8 ta aggregator bitta rasmiy saytga olib borsa, faqat bittasi o'tadi |
| `fingerprint` | Sarlavha barmoq izi — havolalar biroz farq qilsa ham ushlaydi |

`url_key` — bu URL ning normallashgan ko'rinishi:
`http://www.Example.com/Grant/?utm_source=rss` → `example.com/grant`

---

## Ishga tushirish

### 1. Bazani tayyorlash (bir marta)

Supabase → SQL Editor → [`migration.sql`](migration.sql) faylini to'liq nusxalab
**Run** bosing. U yangi ustunlarni qo'shadi va eski yozuvlarni moslashtiradi.

### 2. Kalitlar

`.env.example` ni `.env` deb nusxalab to'ldiring. GitHub Actions uchun esa:
**Settings → Secrets and variables → Actions** ga quyidagilarni qo'shing:

`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHANNEL_ID`, `GEMINI_API_KEY`,
`SUPABASE_URL`, `SUPABASE_KEY`

### 3. Ishga tushirish

```bash
pip install -r requirements.txt
python main.py --dry-run    # kanalga yubormasdan sinash
python main.py              # haqiqiy yurish
```

GitHub Actions har kuni **08:00 (Toshkent)** da avtomatik ishga tushadi.
Qo'lda ishga tushirish: Actions → Nova Grants Bot → Run workflow
(u yerda "quruq sinov" tugmasi ham bor).

---

## Fayllar

| Fayl | Vazifasi |
|---|---|
| `main.py` | Quvurni boshqaradi |
| `sources.py` | Manba katalogi (har biri jonli tekshirilgan) |
| `scraper.py` | RSS / Telegram / grants.gov API dan yig'ish |
| `filters.py` | Bu imkoniyatmi yoki yangilikmi — hal qiladi, muddatni topadi |
| `link_resolver.py` | **Asl havolani qazish** va URL normallashtirish |
| `database.py` | Supabase, takrorga qarshi 3 qatlam |
| `ai_agent.py` | Gemini bilan tuzilgan mazmun (havolasiz!) |
| `post_builder.py` | Mazmundan rich bloklar + HTML zaxira quradi |
| `telegram_bot.py` | Kanalga yuborish, limitlarga rioya |
| `migration.sql` | Baza sxemasini yangilash |
| `tools/` | Manbalarni tekshirish va API sxemasini o'rganish skriptlari |

### Telegram rich messages

Bot API 10.1+ (2026-yil iyun) "rich messages" qo'shdi. Botda **hech narsa
yoqish shart emas** — BotFather sozlamasi ham, obuna ham kerak emas. Faqat
media bloklari uchun botda o'sha chatga media yuborish huquqi talab qilinadi
(bizda media yo'q).

Maydon nomlari **faqat rasmiy hujjatdan** olinadi (`InputRichBlock*`):

| Blok | Tuzilishi |
|---|---|
| `heading` | `{"type","text","size"}` — size 1–6, **1 eng katta** |
| `paragraph` / `footer` | `{"type","text"}` |
| `divider` | `{"type"}` |
| `list` | `{"type","items"}`, item: `{"blocks":[...]}` |
| `details` | `{"type","summary","blocks"}` + ixtiyoriy `is_open: true` |
| havola | `{"type":"url","url":...,"text":...}` |

`InputRichMessage` da `html`, `markdown` yoki `blocks` dan **aynan bittasi**
bo'lishi kerak. `text` degan maydon yo'q.

> ⚠️ **Jonli API'ni "probe" qilib sxema aniqlash CHALG'ITADI.** Telegram
> noma'lum maydonlarni parse bosqichida rad etmaydi va mazmun tekshiruvini chat
> topilgandan keyin bajaradi. Shuning uchun `{"header": ...}` (to'g'risi
> `summary`) va `items: [{"text": ...}]` (to'g'risi `{"blocks": [...]}`) —
> ikkalasi ham `chat_id=1` bilan "yaroqli" ko'rindi, lekin haqiqiy kanalda
> `RICH_MESSAGE_CONTENT_REQUIRED` xatosini berdi.
>
> Shu sabab `tools/check_rich_spec.py` yozildi — u bloklarni hujjat sxemasiga
> solishtiradi. Blok tuzilishini o'zgartirsangiz, avval shuni ishga tushiring.

Cheklovlar (hujjatdan): **32 768 belgi**, **500 blok** (ichkilari bilan),
16 daraja ichma-ichlik, 50 media, jadvalda 20 ustun. Mijozlar ~8000 belgidan
keyin "Show more" tugmasini ko'rsatadi.

Rich message ishlamasa, `publish()` avtomatik HTML ko'rinishga o'tadi —
ikkalasi ham `post_builder.py` da bir manbadan quriladi, shuning uchun mazmun
va havolalar bir xil bo'ladi.

---

## Sozlash

`main.py` boshida:

```python
MAX_RESOLVE_PER_RUN = 70   # bir yurishda nechta maqola ochiladi
MAX_POST_PER_RUN    = 24   # bir kunda kanalga nechta yangi imkoniyat
RESOLVE_WORKERS     = 5    # parallel oqim
```

`ai_agent.py`:

```python
MODEL_CHAIN = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-flash-latest"]
BATCH_SIZE  = 8            # bitta AI so'roviga nechta grant
```

### Manba qo'shish

`sources.py` ga yozuv qo'shing va tekshiring:

```bash
python tools/check_sources.py
```

Agar sayt aggregator bo'lsa (ya'ni grantni "qayta hikoya qiladi"), uning domenini
`link_resolver.py` dagi `AGGREGATORS` ro'yxatiga ham qo'shing — aks holda uning
o'z havolasi kanalga tushib qoladi.

---

## Nima uchun ba'zi manbalar yo'q

`sources.py` dagi `DISABLED` lug'atida har bir olib tashlangan manba sababi bilan
yozilgan. Ikki turkum:

- **Texnik**: RSS o'chirilgan, HTTP 403/404, Cloudflare himoyasi
- **Mavzu**: TechCrunch, Hacker News, Crunchbase kabi yangilik lentalari —
  ularda grant yo'q, "startup $5M jalb qildi" tipidagi postlar bor

---

## Limitlar

**Telegram Bot API**: bitta chatga sekundiga 1 xabar, guruhga daqiqasiga 20 ta,
xabar uzunligi 4096 belgi. `telegram_bot.py` postni grant chegarasida bo'ladi —
HTML tegi hech qachon o'rtasidan kesilmaydi — va 429 kelsa `retry_after` qadar kutadi.

**Gemini**: `thinking_level="low"` sozlamasi bilan bitta so'rov ~470 token
(sozlamasiz 1620 edi). Model band bo'lsa (`503`) avtomatik zaxira modelga o'tadi.

**Manba saytlar**: bitta domenga 3 soniyada bir marta murojaat qilinadi. `429`
qaytargan sayt 2 daqiqaga chetlab o'tiladi.
