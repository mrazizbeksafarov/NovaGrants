# Nova Grants Bot

O'zbekiston yoshlari uchun xalqaro grant, stipendiya va fellowship imkoniyatlarini
avtomatik topib, [@Nova_Grants](https://t.me/Nova_Grants) kanaliga chiqaradigan bot.

> **2026-08-06 auditi.** Quvur jonli o'lchandi va bir nechta jiddiy nosozlik
> tuzatildi. Eng muhimlari: takror tekshiruvi chop etilgan grantning bazadagi
> qatorini buzardi (eslatmalar shu sabab ishlamasdi), eslatmalarda aggregator
> havolasi filtri yo'q edi, HTML zaxirasida URL escape qilinmagani uchun post
> **havolasiz** chiqishi mumkin edi. Batafsil — quyidagi bo'limlarda.
>
> O'lchangan natija: asl havola topish **58% → 80%**, yig'ilgan yozuv
> **312 → 427**, 5 yillik o'lik kanallar olib tashlandi.

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
1. YIG'ISH     26 ta manba (RSS + Telegram, sahifalash)  →  ~440 yozuv
2. YANGILIK    60 kundan eski e'lonlar tashlanadi        →  faqat tirik e'lon
3. SARALASH    yangilik/reklama/qo'llanma tashlanadi     →  ~300 yozuv
4. ESKIRIB     avval ko'rilgan maqolalar tashlanadi      →  faqat yangilari
5. QAZISH      maqola ichidan ASL havola topiladi        →  rasmiy sayt
6. TAKROR      3 qatlamli tekshiruv                      →  betakror ro'yxat
7. POST        Gemini mazmun yozadi → rich message → kanal
8. ESLATMA     muddati yaqinlashganlar haqida
```

### 1-bosqich: sahifalash (`scraper.py`)

WordPress feed'lari bir sahifada atigi 10 ta yozuv beradi, lekin `?paged=2`
va `?paged=3` yana 10 tadan **noyob** yozuv qaytaradi. Manbaga `"pages": 3`
qo'yilsa, o'sha ishonchli manbadan uch barobar ko'p qamrov olinadi — yangi
manba qidirishdan ko'ra arzon va aniqroq yo'l.

### 2-bosqich: yangilik chegarasi

Ilgari na RSS, na Telegram uchun sana tekshirilmasdi. Natijada 2021-yilda
to'xtab qolgan kanallar besh yillik postlarini "yangi imkoniyat" sifatida
quvurga tiqib turardi. Endi `MAX_AGE_DAYS = 60` dan eski yozuv olinmaydi.
Sanasi noma'lum yozuv o'tkaziladi — ko'p feed'da sana bo'lmaydi.

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

### 6-bosqich: takrorga qarshi 3 qatlam (`database.py`)

| Qatlam | Nima ushlaydi |
|---|---|
| `source_key` | Avval ko'rilgan maqola — qayta ochilmaydi ham (tarmoq tejaladi) |
| `url_key` | 8 ta aggregator bitta rasmiy saytga olib borsa, faqat bittasi o'tadi |
| `fingerprint` | Sarlavha barmoq izi — havolalar biroz farq qilsa ham ushlaydi |

`url_key` — bu URL ning normallashgan ko'rinishi:
`http://www.Example.com/Grant/?utm_source=rss` → `example.com/grant`

`fingerprint` **ataylab cheklangan**: 2 tadan kam mazmunli so'z qolsa bo'sh
qaytaradi. "Oxford Scholarship" va "Oxford Fellowship" ni bitta grant deb
hisoblab qo'yish — o'tkazib yuborilgan takrordan xavfliroq, chunki haqiqiy
imkoniyat jimgina yo'qoladi.

> **"posted" yozuv hech qachon pasaytirilmaydi.**
> Ilgari 5-bosqich takror topilgan grantni `status="skipped"` bilan qayta
> yozardi va upsert mavjud qatorni ustidan bosardi: `deadline` NULL bo'lardi,
> `reminder_sent` False ga qaytardi. Ya'ni **2+ manbada chiqqan har qanday
> grant eslatma ololmasdi**. Endi takror faqat MANBA MAQOLASI kaliti bilan
> `status="duplicate"` qilib yoziladi, grantning o'z qatoriga tegilmaydi.

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
python -m pytest tests/ -q  # tarmoqsiz testlar (~1s)
python main.py --dry-run    # kanalga yubormasdan sinash
python main.py              # haqiqiy yurish
```

GitHub Actions har kuni **~08:10 (Toshkent)** da avtomatik ishga tushadi.
Qo'lda ishga tushirish: Actions → Nova Grants Bot → Run workflow
(u yerda "quruq sinov" tugmasi ham bor).

> Cron `20 0 * * *` (00:20 UTC) qilib qo'yilgan, garchi maqsad 08:10 Toshkent
> (03:10 UTC) bo'lsa ham. Sabab: GitHub Actions rejalashtirilgan yurishni
> navbatda ushlab turadi — o'lchangan kechikish 2s42d–3s17d. Ilgari `0 3`
> turardi va postlar 08:00 emas, ~10:45 da chiqardi.

### Testlar

`tests/test_pipeline.py` — tarmoqsiz, ~1 soniya. Har bir test **jonli kanalda
sodir bo'lgan** nosozlikni qaytarib kelmasligini tekshiradi: xom `&` tufayli
havolaning yo'qolishi, o'tib ketgan muddat, "How I Won..." tipidagi maqolalar,
bo'lingan xabarda ochiq qolgan teglar. Yangi xato topsangiz — avval shu yerga
test yozing. CI botdan **oldin** shu testlarni ishga tushiradi.

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
| `tests/` | Tarmoqsiz testlar — CI da botdan oldin ishlaydi |
| `tools/` | Manbalarni tekshirish va API sxemasini o'rganish skriptlari |

### Telegram rich messages

Rich messages Bot API **10.1** (2026-yil 11-iyun) da qo'shildi, **10.2**
(14-iyul) da kengaytirildi. Botda **hech narsa yoqish shart emas** —
BotFather sozlamasi ham, obuna ham kerak emas. Faqat media bloklari uchun
botda o'sha chatga media yuborish huquqi talab qilinadi (bizda media yo'q).

Maydon nomlari **faqat rasmiy hujjatdan** olinadi (`InputRichBlock*`,
2026-08-06 da `core.telegram.org/bots/api` dan tasdiqlangan):

| Blok | Sinf | Tuzilishi |
|---|---|---|
| `heading` | `InputRichBlockSectionHeading` | `{"type","text","size"}` — size 1–6, **1 eng katta** |
| `paragraph` | `InputRichBlockParagraph` | `{"type","text"}` |
| `footer` | `InputRichBlockFooter` | `{"type","text"}` |
| `divider` | `InputRichBlockDivider` | `{"type"}` |
| `list` | `InputRichBlockList` | `{"type","items"}`, item: `{"blocks":[...]}` |
| `details` | `InputRichBlockDetails` | `{"type","summary","blocks"}` + ixtiyoriy `is_open: true` |
| havola | `RichTextUrl` | `{"type":"url","url":...,"text":...}` |

Diqqat: sinf nomi `InputRichBlockSectionHeading` bo'lsa ham, JSON dagi
`type` qiymati **`"heading"`**. Ikkalasini adashtirmang.

10.2 da qo'shilgan, hozircha ishlatilmaydigan bloklar: `blockquote`,
`pullquote`, `table`, `photo`/`collage`/`slideshow`, `pre`, `map`,
`thinking`, hamda `sendRichMessageDraft`. Ro'yxat elementlari `has_checkbox`,
`is_checked` va tartib raqami (`value`, `type`) ni ham qo'llab-quvvatlaydi.

> ⚠️ **Rich message `t.me/s/<kanal>` web ko'rinishida OCHILMAYDI** — u yerda
> "Please open Telegram to view this post" chiqadi. Ya'ni kanal Google'da
> indekslanmaydi va havola preview'i ishlamaydi. Bu Telegram'ning cheklovi,
> koddagi xato emas. O'sish web orqali muhim bo'lsa, `publish()` ni HTML
> rejimiga o'tkazish kerak bo'ladi.

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
MAX_POST_PER_RUN    = 32   # bir kunda kanalga nechta yangi imkoniyat
RESOLVE_WORKERS     = 5    # parallel oqim
```

`scraper.py`:

```python
MAX_PER_SOURCE = 60        # bitta manbadan ko'pi bilan shuncha yozuv
MAX_AGE_DAYS   = 60        # bundan eski e'lon umuman olinmaydi
```

`ai_agent.py`:

```python
MODEL_CHAIN = ["gemini-3.5-flash", "gemini-2.5-flash", "gemini-flash-latest"]
BATCH_SIZE  = 8            # bitta AI so'roviga nechta grant
temperature = 0.35         # faktlar barqaror bo'lishi uchun (0.9 emas)
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
yozilgan. Uch turkum:

- **Texnik**: RSS o'chirilgan, HTTP 403/404, Cloudflare himoyasi
- **Mavzu**: TechCrunch, Hacker News, Crunchbase kabi yangilik lentalari —
  ularda grant yo'q, "startup $5M jalb qildi" tipidagi postlar bor
- **O'lik**: oxirgi posti bir necha yil oldin bo'lgan Telegram kanallari

### Rasmiy manbalar nega kam

2026-08-06 da 40+ rasmiy sayt jonli tekshirildi — `chevening.org`, `daad.de`,
`britishcouncil.org`, `turkiyeburslari.gov.tr`, `stipendiumhungaricum.hu`,
`euraxess`, `salto-youth`, `unjobs`, `jobs.ac.uk`, `mastersportal` va h.k.
**Deyarli hech birida ishlaydigan RSS yo'q**: 404, JS bilan yuklanadigan
sahifa yoki bot himoyasi. `api.reliefweb.int` v1 o'chirilgan (410), EU
Funding & Tenders API kalit talab qiladi.

Shu sabab qamrov aggregatorlar + **sahifalash** orqali kengaytirildi:
tekshirilgan manbadan 10 emas, 30 ta yozuv olinadi. Ishlaydigan rasmiy
manbalar — `uz.usembassy.gov` (Fulbright, UGRAD) va `youth.europa.eu`.

Yangi manba qo'shishdan oldin `python tools/check_sources.py` ni ishga
tushiring: u har bir manbaning holatini va yozuv sonini ko'rsatadi.

---

## Limitlar

**Telegram Bot API**: bitta chatga sekundiga 1 xabar, guruhga daqiqasiga 20 ta,
xabar uzunligi 4096 belgi. `telegram_bot.py` postni grant chegarasida bo'ladi —
HTML tegi hech qachon o'rtasidan kesilmaydi — va 429 kelsa `retry_after` qadar kutadi.

**Gemini**: `thinking_level="low"` sozlamasi bilan bitta so'rov ~470 token
(sozlamasiz 1620 edi). Model band bo'lsa (`503`) avtomatik zaxira modelga o'tadi.

**Manba saytlar**: bitta domenga 3 soniyada bir marta murojaat qilinadi. `429`
qaytargan sayt 2 daqiqaga chetlab o'tiladi. RSS yig'ishda `429`/`503` kelsa
`Retry-After` ga rioya qilib 2 marta qayta uriniladi.

---

## Nosozlik bildirishnomasi

`.env` da `ADMIN_ID` bo'lsa, yurish oxirida muammo topilganda botga shaxsiy
xabar keladi:

- asl havola topish darajasi 35% dan pastga tushsa
- aggregator havolasi xavfsizlik to'ridan o'tib ketsa
- nomzodlar bor edi, lekin hech biri post qilinmasa

Sozlanmagan bo'lsa jimgina o'tkazib yuboriladi.
