-- Nova Grants — bazani yangilash.
-- Supabase → SQL Editor → shu faylni to'liq nusxalab "Run" bosing. Bir marta yetarli.

-- 1) Yangi ustunlar (takrorga qarshi uch qatlam)
alter table public.posted_grants add column if not exists url_key     text;
alter table public.posted_grants add column if not exists source_url  text;
alter table public.posted_grants add column if not exists source_key  text;
alter table public.posted_grants add column if not exists fingerprint text;
alter table public.posted_grants add column if not exists status      text default 'posted';

-- 2) Eski yozuvlarga status beramiz
update public.posted_grants set status = 'posted' where status is null;

-- 3) Eski yozuvlarning url_key/source_key sini to'ldiramiz.
--    Kalit = domen + yo'l (https://, www., oxirgi '/' va ?parametrlarsiz, kichik harfda).
--    Bu Python dagi url_key() bilan bir xil mantiq.
update public.posted_grants
set url_key = lower(
      regexp_replace(
        regexp_replace(
          regexp_replace(coalesce(url, ''), '^https?://(www\.)?', ''),
          '\?.*$', ''),
        '/+$', '')
    )
where url_key is null and url is not null;

update public.posted_grants
set source_key = url_key
where source_key is null;

-- 4) Indekslar — tekshiruv tez ishlashi uchun
create index if not exists idx_pg_url_key     on public.posted_grants (url_key);
create index if not exists idx_pg_source_key  on public.posted_grants (source_key);
create index if not exists idx_pg_fingerprint on public.posted_grants (fingerprint);
create index if not exists idx_pg_deadline    on public.posted_grants (deadline)
  where reminder_sent = false;

-- 5) url_key bo'yicha takrorlarni tozalab, yagona indeks qo'yamiz.
--    (upsert(on_conflict='url_key') shu indeksni talab qiladi.)
delete from public.posted_grants a
using public.posted_grants b
where a.url_key is not null
  and a.url_key <> ''
  and a.url_key = b.url_key
  and a.id > b.id;

create unique index if not exists idx_pg_url_key_uniq
  on public.posted_grants (url_key)
  where url_key is not null and url_key <> '';

-- 6) Eslatma so'rovi status + reminder_sent bo'yicha filtrlaydi.
create index if not exists idx_pg_status on public.posted_grants (status);

-- Tekshirish:
--   select status, count(*) from public.posted_grants group by status;
--
-- Kutilayotgan holatlar:
--   posted    — kanalga chiqqan grant
--   skipped   — asl havola topilmadi yoki AI rad etdi
--   duplicate — boshqa aggregatorda chiqqan, bazada allaqachon bor grant.
--               Bu qator MANBA MAQOLASI kaliti bilan saqlanadi, grantning
--               o'zi emas — shuning uchun "posted" qator buzilmaydi.
--
-- Sxema o'zgarishi SHART EMAS: `status` matn ustuni, "duplicate" o'z-o'zidan
-- ishlaydi. Yuqoridagi indeks faqat tezlik uchun.
