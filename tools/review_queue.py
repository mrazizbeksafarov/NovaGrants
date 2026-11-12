"""Read-only list of persisted screening reviews and their source evidence."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database


def list_reviews(limit=50):
    response = database.execute_query(database.supabase.table(database.TABLE).select("title,url,source_url,posted_date")
        .eq("status", "review").order("posted_date", desc=True).limit(limit))
    rows = []
    for row in response.data or []:
        try:
            payload = json.loads(row.get("source_url", "")) if row.get("url", "").startswith("urn:novagrants:review:") else {}
        except (ValueError, TypeError):
            payload = {}
        grant = payload.get("grant") or {}
        rows.append({"title": row.get("title"), "reason": payload.get("reason", "legacy_review"),
                     "url": grant.get("url") or row.get("url"),
                     "source_url": grant.get("source_url") or row.get("source_url"),
                     "evidence_url": grant.get("official_evidence_url"), "created_at": row.get("posted_date")})
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    database.init_db(strict=True)
    print(json.dumps(list_reviews(min(200, max(1, args.limit))), ensure_ascii=True, indent=2))
