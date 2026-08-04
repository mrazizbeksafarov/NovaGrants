"""Asl havola qazish sinovi: aggregator maqolasidan rasmiy sayt topiladimi?"""

import sys, os, concurrent.futures, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

from scraper import fetch_all
from link_resolver import resolve_grant, host_of, is_aggregator
from filters import looks_like_opportunity

LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 24

items = fetch_all()
print()

# Faqat aggregator manbalar — asosiy sinov shular ustida
cands = [i for i in items if i["kind"] == "aggregator"
         and looks_like_opportunity(i["title"], i.get("summary", ""), i.get("topic", ""))]
print(f"Filtrdan o'tgan aggregator yozuvlari: {len(cands)} / {len(items)}")

random.seed(7)
sample = random.sample(cands, min(LIMIT, len(cands)))

print(f"\n{len(sample)} ta yozuvda asl havola qidirilmoqda...\n")

with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
    resolved = list(ex.map(resolve_grant, sample))

ok = 0
for g in resolved:
    src_host = host_of(g.get("source_url", ""))
    if g.get("url"):
        ok += 1
        mark = "✅"
        detail = f"{host_of(g['url'])}\n         {g['url'][:100]}"
    else:
        mark = "❌"
        detail = "(asl havola topilmadi — bu yozuv tashlab yuboriladi)"
    print(f"{mark} [{g['source_id']}] {g['title'][:62]}")
    print(f"     manba : {src_host}")
    print(f"     asl   : {detail}")
    print()

print(f"NATIJA: {ok}/{len(resolved)} yozuvda asl havola topildi "
      f"({100 * ok // max(len(resolved), 1)}%)")

leaked = [g for g in resolved if g.get("url") and is_aggregator(g["url"])]
print(f"Aggregator havolasi sizib chiqqani: {len(leaked)} ta (0 bo'lishi kerak)")
