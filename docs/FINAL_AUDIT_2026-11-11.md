# NovaGrants — yakuniy audit

Sana: 2026-11-11, Asia/Tashkent. Holat: lokal `codex/reliability-audit` branchi.

## Baholash

Manbalarni yig'ishdan kanalga yuborishgacha bo'lgan asosiy yo'l yangilandi,
regressiyalar tekshirildi va yangi API formatlari sxema bilan tekshirildi.
Kod sezilarli yaxshilandi. **Production'da to'liq tasdiqlangan yoki mutlaq
takrorsiz tizim** deb baholanmaydi: quyidagi qoldiq P1 cheklovlari bor.

Joriy CLI akkauntining repo uchun `push` huquqi yo'q. Kod remote'ga
chiqarilmadi; ishlayotgan kanal va baza sxemasi o'zgartirilmadi. Hech bir
sinov ommaviy kanalga xabar yubormadi. Foydalanuvchi ko'rsatgan shaxsiy chatga
HTML, widget va rich namunalari yuborilib, keyingi tuzatishlar o'sha xabarda tahrirlandi. GitHub/Linux tekshiruvlari yangi
workflow'da tayyor, mahalliy ikkala Python sinovi esa Windows'da bajarildi.

## Audit qamrovi va usuli

12 runtime modulining boshqaruv oqimi, manba katalogi, HTTP/rate-limit,
deadline, dedup, AI shartnomasi, Supabase persistence, xabar qurish/yuborish,
migratsiyalar va workflow'lar ko'rib chiqildi. Yangi `opportunity_content.py`
va `rich_schema.py` ham auditga kiritildi. Legacy skriptlar odatiy test
to'plamiga kirmaydi: ayrimlari tashqi xabar yuboradi va eski interfeysga tayanadi.

Dalillar: oldingi [production auditi](AUDIT_2026-11-11.md),
[manbalar hisoboti](SOURCES_2026-11-11.md), jonli manba smoke testi,
avtomatlashtirilgan regressiya sinovlari, statik analiz, dependency advisories
va qo'lda ko'rib chiqilgan saqlash/yuborish holatlari.

## Amalga oshirilgan asosiy tuzatishlar

| Soha | Tuzatilgan nosozlik yoki yaxshilanish |
|---|---|
| Manbalar | 23 → 30 faol manba; 53 URL sinovi; ikki eskirgan rasmiy kanal manzili yangilandi |
| Manba tekshiruvi | HTTP 200 HTML endi ishlaydigan RSS deb olinmaydi; stale/empty/HTTP holatlari JSON'da ajratiladi |
| Dalillar | RSS to'liq matnidan eligibility va deadline saqlanadi, muharrirga 700 emas 1800 belgigacha yetkaziladi |
| Havola qazish | RSS ichidagi application URL'lar qayta ishlatiladi; Telegram aggregator-only postlari yo'qolmaydi |
| Havola mosligi | `submit` ichidagi MIT xatosi; sponsor nomi bilan mezbon universitet farqi; yaroqsiz birinchi nomzoddan keyingi linklar tuzatildi |
| AI linklari | Faqat modelga ko'rsatilgan URL nomzodlari qabul qilinadi; redirect qayta tekshiriladi |
| AI shartnomasi | Pydantic validatsiya, haqiqiy index, bo'sh rad etish va nosozlik farqi; mavjud matndan olingan moslik iqtibosi talab etiladi |
| AI nosozligi | Saralanmagan xom matn bilan fallback nashr yo'q; vaqt va urinish soni cheklangan |
| AI sarlavhasi | Aralash digestdagi qisman stipendiyalarni “barchasi to'liq moliyalashtirilgan” deb ko'rsatadigan AI sarlavhasi o'rniga sanalgan, faktga neytral sarlavha ishlatiladi |
| Takrorlar | URL, canonical, tashkilotga bog'langan title fingerprint, program va slug orqali bog'langan guruhlar tuziladi |
| Yagona yozuv | Guruhda eng ko'p dalili bor manba tanlanadi, muvaffaqiyatli postdan so'ng qolgan manbalar alias sifatida saqlanadi |
| False-positive dedup | Bir xil umumiy sarlavhali, turli tashkilotlarning grantlari title fingerprint sabab birlashtirilmaydi |
| Transitiv takror | Keyin kelgan uchinchi maqola ikki oldingi guruhni bog'lasa, connected-component usuli bitta guruh qiladi |
| Baza | Jonli `UNIQUE(url)` bilan mos source-alias yozish; posted qatorni pasaytirmaslik; insert race qayta o'qish |
| Baza xatolari | Tasdiqlanmagan yozish va dedup o'qishlari fail-fast; eslatma belgisi ham tasdiqlanadi |
| Deadline | O'tgan sana/vaqt, ISO garbage, o'zbekcha oylar va event-start/deadline farqi tuzatildi |
| Rate-limit | Katta Retry-After ertaroq qayta urinishga aylantirilmaydi; parallel resolverlar shared cooldown'ni qayta tekshiradi |
| Telegram | HTML zaxira uchun 4096 limiti, UTF-16 bo'lish va HTML entity/tag chegaralari tuzatildi |
| Noaniq yuborish | Timeout/ulanish/5xx'da shu yurish ichida ko'r-ko'rona retry yoki HTML dublikat yuborilmaydi |
| Ko'rinish | Yig'iladigan tafsilotlar saqlandi; aniq muddat tashqarida, native ariza tugmasi va post ichidagi navigatsiya qo'shildi; emoji yo'q |
| Moslashuv | Yangi bloklar aniq rad etilsa eski rich formatga, u ham rad etilsa HTML'ga o'tish saqlangan |
| Sxema | Bot API 10.4'ning ishlatilayotgan kichik qismi offline tekshiriladi; noto'g'ri `customemoji` kabi nomlar rad etiladi |
| CI | Push/PR Python 3.11/3.13 testlari, statik correctness, yuqori severity security va dependency audit tayyor |
| Dependencies | Xavfsiz pytest/pip versiyalari va 51 paketlik tekshirilgan constraints snapshot qo'shildi |

## Telegram imkoniyatlari tekshiruvi

[Bot API 10.4](https://core.telegram.org/bots/api) 2026-11-09 da chiqarilgan.
Kanal uchun native rich tugmalar, ichki navigatsiya, yig'iladigan tafsilotlar va nisbiy
muddat qo'llandi. HTML widgetlar hozir shaxsiy chat bilan cheklangan.
Kanal custom emoji'si botning Fragment username shartiga bog'liq; foydalanuvchi
tanloviga ko'ra emojisiz uslub saqlandi. Maxsus media, pulli tarqatish va
shaxsiy-chat effektlari kanal digestining sifatiga avtomatik foyda bermaydi.
Faqat nomi yangi bo'lgani uchun funksiyalar qo'shilmadi.

[Mahalliy ko'rinish namunasi](post_preview.html) va undan qurilgan payload shaxsiy chatda sinovdan o'tdi.
[Payload](post_payload_10_4.json) aynan builder bloklari bilan yaratilgan;
shaxsiy chatga yuborildi va foydalanuvchi skrinshotlari bilan ko'rinishi tasdiqlandi.

### Foydalanuvchi fikridan keyingi yakuniy UX

Har bir kartochkada **bitta “Ariza va tafsilotlar” tugmasi** qolgan. Tugma
ostidagi ayni URL takrori olib tashlangan. Oddiy link faqat yangi format
ishlamagandagi eski rich/HTML zaxirasida yaratiladi; bir vaqtning o'zida
ikkita link ko'rsatilmaydi. Native copy tugmasi ham olib tashlangan: bu kanal
manbasini chetlab qayta tarqatishni qo'shimcha osonlashtirmaslik haqidagi
marketing qarori. Bu URL'ni ko'chirib bo'lmaydi degan xavfsizlik kafolati emas.

Marketing uchun original kanal postining native Forward amali saqlanadi.
Bot API ichki tugmasidan native forward oynasini ochadigan action yo'q;
rasmiy grant URL'ini share qilish bu vazifaga tenglashtirilmadi. Kanalda
`has_protected_content=false` o'qildi; uning sozlamasi o'zgartirilmadi.
Widget'ning production forwarding cheklovi sabab u shaxsiy chat sinovi
bo'lib qoladi. Bot tokeni va foydalanuvchi ID'i ushbu dalil fayllariga yozilmadi.

## Tekshiruv natijalari

| Tekshiruv | Natija |
|---|---|
| Python 3.13.14, pytest 9.2.0 | 149/149 o'tdi |
| Python 3.11.18, pytest 9.2.0 | 149/149 o'tdi |
| Offline himoya | `.env`/haqiqiy service kalitlari yuklanmaydi; test socket ulanishlari bloklangan |
| Orchestration integratsiyasi | Yig'ish → resolve → dedup → AI → rich payload → fake DB: bitta post va alias |
| Rich sxema | Tekshiruv namunasi 70 blok; barcha ishlatilgan strukturalar yaroqli |
| Jonli source health | 30/30 ishladi; tekshiruv paytidagi snapshot |
| Jonli URL/detail smoke | 12/15 rasmiy URL; kichik, tanlangan texnik namuna |
| Jonli Telegram | Oddiy HTML, widget, rich yuborish va rich tahrirlari Bot API tomonidan qabul qilindi; foydalanuvchi skrinshotlari bor |
| Jonli Supabase o'qishi | Sxema, semantic slug, scoped fingerprint so'rovi va eslatma o'qishi ishladi; hech qanday test yozuvi qo'shilmadi |
| Chegaralangan online dry-run | 458 yozuv → 334 mavzu nomzodi → 191 yangi manba; 6/6 URL; 4 AI nomzodidan 3 kartochka, 36.38s, 3134 token; kanal/baza yozishlari yo'q |
| Ruff E9/F821/F822/F823 | 0 topilma |
| Bandit | 0 high, 0 medium; 3 low uchun quyida disposition bor |
| pip-audit | O'rnatilgan runtime muhitidagi 52 paketda ma'lum zaiflik topilmadi |
| pip check / constraints | Dependency konflikti yo'q; 3.11 va 3.13 constraints dry-run o'zgarish talab qilmadi |
| Diff / workflow YAML | Whitespace xatosi yo'q; YAML parse tekshiruvi o'tdi |

Dependency auditning dastlabki javobida ikkita advisory takror ID'lar bilan
to'rtta yozuv ko'rinishida kelgan: pip va pytest. pip 26.3 hamda pytest 9.2.0
bilan qayta tekshiruv toza. Bu kelajakdagi noma'lum zaifliklar yo'q degani emas.

### Coverage

Coverage.py branch tahlili: umumiy line+branch ko'rsatkichi **71%**,
statement qamrovi 73%, branch qamrovi 65%.
Bu testlar har bir holatni qamraydi degani emas. Eng muhim yangi regressionlar
tekshirilgan, ammo haqiqiy Telegram/Supabase protokoli, TLS fallback'lari,
eslatmalar va ayrim parsing xatolari uchun qo'shimcha integratsiya sinovlari kerak.
Modul kesimidagi tafsilotlar [coverage JSON](coverage_audit_2026-11-11.json) ichida.

### Bandit past darajali topilmalari

- `database.stats()`: hisobot uchun best-effort statistika; xato dedup yoki yozishga emas, faqat telemetry'ga tegishli.
- `_collect_candidates()`: yaroqsiz bitta URL o'tkazib yuboriladi, qolgan nomzodlar tekshiriladi.
- `_entry_age_days()`: yaroqsiz sana bo'lsa boshqa sana maydoniga o'tiladi; topilmasa sana noma'lum deb qoladi.

SHA-1 faqat takror sarlavhalar identifikatori sifatida ishlatiladi va
`usedforsecurity=False` belgilangan. Regex'dagi ko'rinmas bidi belgisi explicit
Unicode escape'ga aylantirildi. Scanner topilmalarini shunchaki yashirish uchun
umumiy `nosec` qo'shilmadi.

## Qolgan P1/P2 cheklovlar

| Ustuvorlik | Aniq cheklov | Ta'sir va keyingi yechim |
|---|---|---|
| P1 | Telegram yuborishi va DB saqlashi orasida tranzaksiya yo'q | Server postni qabul qilib javob yo'qolsa yoki keyingi DB yozishi yiqilsa, ertangi yurishda takror bo'lishi mumkin. Durable outbox, message ID va `uncertain` reconciliation kerak. Joriy tuzatish shu yurishdagi blind retry'ni to'xtatadi |
| P1 | URL va ayrim program kalitlari sikldan mustaqil | Bir xil URL'dagi keyingi yil qabuli eski posted yozuv sabab yopilib qolishi mumkin. `programme` + `application_cycle` modeliga yangi migratsiya kerak; eski URL unique constraintini ko'r-ko'rona olib tashlash mumkin emas |
| P1 | Production RLS disabled deb kuzatilgan | Anon role'ning real GRANT'lari va bot key roli tekshirilmaguncha ochiq kirish mavjudligi yoki yo'qligi tasdiqlanmaydi. Backend huquqlarini saqlagan holda RLS rejalashtirilishi kerak |
| P2 | Moslik iqtibosi mantiqiy eligibility isboti emas | Manba noto'g'ri talqin qilinishi yoki shartlar keyin o'zgarishi mumkin; rasmiy detail asosidagi labeled eligibility benchmark va uncertain review navbati kerak |
| P2 | AI sinovi kichik va bir martalik | 3.8 low/high ~90s timeout, 3.5 bir urinishda muvaffaqiyatsiz; 2.5 bir ijobiy va bir salbiy namunani 2.61s da to'g'ri ajratdi. Bu avvalgi kalitdagi tarixiy sinov. Yangi kalitda 2.5 yopilgan; standart zanjir 3.6 → 3.5 Flash-Lite → 3.8 qilib yangilandi. Keng labeled dataset va p95 hali yo'q |
| P2 | Qayta resolution navbati DB backoff bilan saqlanmaydi | Ishlamaydigan maqolalar yana resurs olishi mumkin. attempts/next_retry_at/reason ustunlari kerak |
| P2 | Tashqi URL'lar va redirectlar uchun SSRF siyosati to'liq emas | Nazoratli feed'da zararli link chiqsa, public egress/IP cheklovi va barcha redirectlarda manzil tekshiruvi kerak. Hozirgi link filtri bu xavfning to'liq yechimi emas |
| P2 | Manba holati tarmoq va vaqtga bog'liq | 30/30 lokal natija Actions IP'ida doim 30/30 bo'lishini anglatmaydi; runner'da source-health artifact bilan tasdiqlash kerak |
| P2 | Migratsiya boshlang'ich jadvalni yaratmaydi | Mavjud production jadvali borligi tekshirildi; toza Supabase loyiha uchun bootstrap sxema alohida kerak |

Bu cheklovlar yashirilmadi. Ayniqsa P1 bandlari yopilmaguncha “mutlaqo
takrorsiz”, “barcha dunyo dasturlari topiladi” yoki “production 100%” kabi
kafolat berilmaydi.

## Chiqarish va qabul qilish mezonlari

1. `codex/reliability-audit` diffini repo huquqi bor akkauntdan PR'ga chiqarish.
2. Yangi CI'ning Linux/Python matritsasi va audit job'i muvaffaqiyatli tugashi.
3. Mavjud secrets bilan `dry_run=true` yurishi; test xabari yoqilmaydi.
4. Natijadagi rasmiy URL, eligibility iqtibosi, muddat va duplicate guruhlarini qo'lda namuna asosida solishtirish.
5. Native ariza tugmasi, navigatsiya va muddatni alohida test chatda ko'rish; keyin rejalashtirilgan production yurishini kuzatish.
6. Post va DB sonlarini solishtirish; eski skipped yoki posted yozuvlarni ommaviy tozalamaslik.

## Saqlangan dalillar

- [Source health](source_health_2026-11-11.json)
- [Resolution smoke](source_resolution_2026-11-11.json)
- [Discovery probe](source_probe_2026-11-11.json), [qo'shimcha discovery](source_discovery_2026-11-11.json)
- [Static correctness](static_correctness_2026-11-11.json)
- [Static security](static_security_2026-11-11.json)
- [Dependency audit](dependency_audit_2026-11-11.json)
- [Coverage](coverage_audit_2026-11-11.json)
- [Shaxsiy Telegram sinovi](telegram_test_audit_2026-11-11.json)
- [Supabase read-only sinovi](database_read_audit_2026-11-11.json)
- [AI model/eligibility smoke](ai_quality_smoke_2026-11-11.json)
- [Chegaralangan online dry-run](bounded_dry_run_2026-11-11.json)

## Yakuniy model va dizayn yangilanishi

Yangi kalitda 2.5 modeli `NOT_FOUND` bilan yopiq. Kod va namunaviy sozlamada
2.5 yo'q. Joriy [model sinovi](model_selection_2026-11-11.json): 6 holat
(2 haqiqiy va 4 sintetik), kutilgan tanlov 1 va 3. 3.6 Flash low ikki urinishda
7.66/6.67 soniyada aynan shu yozuvlarni va kirishdan tasdiqlangan iqtiboslarni
qaytardi. 3.5 Flash-Lite bir marta 8.23s da to'g'ri javob, keyin 503; 3.8 Flash
45s chegarasida 504 berdi. Bu tezlikka asoslangan vaqtinchalik variant edi. Foydalanuvchi kunlik yurishda sifatga ustunlik bergach, yakuniy zanjir 3.8 → 3.7 → 3.6 (medium) qilindi. Keyingi
production tanlovida muntazam qayta o'lchash kerak. Bu keng accuracy benchmarki emas.

Google'ning [joriy thinking hujjati](https://ai.google.dev/gemini-api/docs/thinking)
va [3.8 migratsiya hujjati](https://ai.google.dev/gemini-api/docs/latest-model)
tekshirildi: 3.8/3.7 minimal qabul qilmaydi, shuning uchun ular uchun minimal
so'ralganda low ishlatiladi; 3.x temperature sozlamasi olib tashlandi.
Yangi key bilan haqiqiy muharrir 2 namuna ichidan faqat to'g'ri grantni 6.06s
da tanladi, 2591 token. [Yakuniy kalit sinovi](gemini_key_check_2026-11-11.json).

Dizaynda brend satri, raqamlangan dasturlar, ochiq asosiy foyda, yig'iladigan
navigatsiya va shartlar bor. Muddat yo'q bo'lsa aynan “ko'rsatilmagan” deb yoziladi.
Muhim eligibility shartlari endi 240 belgida kesilmaydi. Bitta ariza tugmasi,
emojisiz ko'rinish, copy/share action yo'qligi saqlangan. Yangi payload shaxsiy
chatdagi mavjud sinov xabarini tahrirlash orqali qabul qilindi.

Mustaqil design-ux ko'rib chiqishi HTML approximatsiyasini 7.5/10 deb,
provisional baholadi. Topilgan ikki major masala (noma'lum muddat, kesilgan
eligibility) tuzatildi. Desktop HTML ko'rinishi kuzatildi, keyingi browser
ulanishi uzilgani sabab narrow/expanded holatlari to'liq mustaqil qayta
baholanmadi. Telegram'ning oxirgi dizayn renderi uchun foydalanuvchi bahosi kerak.

Kanalga `sendWidget` bir marta foydalanuvchi topshirig'i bilan sinaldi:
`INPUT_MEDIA_WIDGET_NOT_ALLOWED`. Post yaratilmagan, o'chirish talab qilinmagan.
[API natijasi](channel_widget_test_2026-11-11.json). Bu imkoniyatni yoqadigan
`allow_widget` parametri yo'q; `allow_queries` faqat botga query'lar uchun.

### Yakuniy kunlik sifat siyosati

Oxirgi foydalanuvchi qarori: bot kuniga bir marta ishlaydi, sifat tezlikdan
ustun. Standart — **Gemini 3.8 Flash, medium**, keyin 3.7 va 3.6. Birlamchi
modelga bitta qayta urinish beriladi; jami 4 urinish. Qo'shimcha kalitlar urinish
sonini ko'paytirmaydi. Har HTTP so'rov 240s bilan cheklangan, transient xatolarda
15/30/60s backoff, workflow chegarasi 90 daqiqa. 2.5 va Flash-Lite standart
zanjirda yo'q. 3.x da temperature/top-p/top-k o'rnatilmagan.

Asos: [joriy model hujjati](https://ai.google.dev/gemini-api/docs/latest-model)
medium'ni ko'p vazifalar uchun tavsiya qiladi; [Google developer forumidagi
rasmiy javob](https://discuss.ai.google.dev/t/handling-429-503-errors-from-the-gemini-api/124640)
503'ni server yuklamasi deb izohlaydi. Boshqa Antigravity mahsulotidagi alohida
foydalanuvchi shikoyatlari aynan Developer API muammosi isboti deb olinmadi.

[3.8 medium smoke](quality_first_smoke_2026-11-11.json) so'nggi urinishda server
bandligi sabab javob bermadi. Shuning uchun 3.8'ning mazmun sifati jonli sinovda
tasdiqlandi deb yozilmaydi; ishlaydigan 3.6 fallback'i alohida tekshirilgan.

## Groq, release va tanlangan brendli digest

Foydalanuvchi tanlovi: brendli muqova + ixcham digest. `assets/nova-grants-cover.png`
imagegen orqali yaratilgan, loyiha ichida saqlangan va native rich photo bloki bilan
bitta xabarga biriktiriladi. Muqovali shaxsiy xabar Telegram tomonidan qabul qilindi.
Muqova rasmida dastur shartlari yoki moliyaviy kafolatlar yo'q. Har kartochkada
bitta ariza tugmasi, asosiy foyda, raqamlangan sarlavha va yig'iladigan shartlar bor.

Groq kaliti faqat `.env` va GitHub encrypted Secret'da saqlanadi. Asosiy provayder
Gemini 3.8 medium, keyin 3.7 va 3.6; ular tugagach optional Groq `openai/gpt-oss-120b`
ishlaydi. Groq strict JSON schema ishlatadi; index va eligibility iqtibosi bir xil
lokal semantik tekshiruvdan o'tadi. O'z URL'ini modeldan olmaymiz.
[Groq smoke](groq_quality_smoke_2026-11-11.json): 6 holatdan kutilgan 1 va 3 yozuvlar,
3.97s, 3842 token. Bu keng sifat benchmarki emas.

GitHub egasi brauzerda qayta tasdiqlagandan so'ng Gemini va Groq Secrets,
GEMINI_MODELS, GEMINI_THINKING_LEVEL=medium, AI_TIMEOUT_SECONDS=240 va GROQ_MODEL
Variables saqlandi. CLI huquqi yetishmagani uchun release fayllari akkaunt egasining
brauzer sessiyasidan alohida branchga yuklanmoqda; main faqat CI tekshiruvlaridan
keyin yangilanadi. Baza sxemasi va eski ma'lumotlar ommaviy o'zgartirilmagan.

Postdagi “Kimlar uchun” O'zbekistonlik arizachining talablari uchun; manbadagi
Davlatlar ro'yxati va O'zbekistonga moslik faqat ichki eligibility tekshiruvida qoladi; postda ta'lim, soha, yosh, tajriba, til va qabul shartlari beriladi. Boshqa davlatlar ro'yxatini reklama matniga ko'chirish talab qilinmaydi.

Release CI: Offline checks run 43075356957 Linux Python 3.11/3.13 va security/dependency audit joblari muvaffaqiyatli tugadi. Keyingi final commit uchun tekshiruv qayta ishlamoqda.
