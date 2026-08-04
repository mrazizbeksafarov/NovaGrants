-- Nova Grants — migratsiyaning TUGALLANMAGAN qismi.
--
-- Ustunlar qo'shilgan, lekin INDEKSLAR yaratilmagan. Natijada bazaga yozish
-- umuman ishlamayapti:
--     42P10: there is no unique or exclusion constraint matching
--            the ON CONFLICT specification
--
-- Ya'ni bot hech nimani eslab qololmaydi va HAR KUNI BIR XIL GRANTLARNI
-- QAYTA POST QILADI. Shuni tuzatadigan yagona narsa — quyidagi indekslar.
--
-- Tekshirildi: takrorlangan url_key yo'q (2813 yozuvdan 0 ta), shuning uchun
-- yagona indeks muammosiz yaratiladi.
--
-- Supabase -> SQL Editor -> hammasini nusxalang -> Run.

-- 1) ENG MUHIMI: url_key bo'yicha yagona indeks.
--    upsert(on_conflict='url_key') aynan shuni talab qiladi.
create unique index if not exists idx_pg_url_key_uniq
  on public.posted_grants (url_key)
  where url_key is not null and url_key <> '';

-- 2) Tezlik uchun qolgan indekslar
create index if not exists idx_pg_source_key  on public.posted_grants (source_key);
create index if not exists idx_pg_fingerprint on public.posted_grants (fingerprint);
create index if not exists idx_pg_deadline    on public.posted_grants (deadline)
  where reminder_sent = false;

-- 3) Tekshirish: quyidagi so'rov 4 ta qator qaytarishi kerak
select indexname
from pg_indexes
where schemaname = 'public'
  and tablename  = 'posted_grants'
  and indexname in ('idx_pg_url_key_uniq', 'idx_pg_source_key',
                    'idx_pg_fingerprint', 'idx_pg_deadline')
order by indexname;
