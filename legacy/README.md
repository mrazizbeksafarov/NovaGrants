# legacy/ — eski skriptlar

Bu papkadagi fayllar loyihaning **eski tuzilishiga** mo'ljallangan bir martalik
sinov skriptlari. Ular endi ISHLAMAYDI, chunki quyidagi funksiyalar qayta yozilgan:

| Eski funksiya | Yangi o'rni |
|---|---|
| `scraper.fetch_grants()` | `scraper.fetch_all()` |
| `ai_agent.format_grant_post()` | `ai_agent.format_grants_post()` |
| `ai_agent.format_multiple_grants_post()` | `ai_agent.format_grants_post()` |
| `database.is_grant_posted()` | `database.get_seen_url_keys()` |
| `database.mark_grant_posted()` | `database.save_grant()` |

Tarix uchun saqlanyapti. Kerak bo'lmasa, papkani butunlay o'chirib tashlash mumkin.

Yangi sinov vositalari `tools/` papkasida:

```bash
python tools/check_sources.py    # manbalar ishlayaptimi
python tools/test_resolver.py    # asl havola qazish sinovi
python main.py --dry-run         # butun quvur, kanalga yubormasdan
```
