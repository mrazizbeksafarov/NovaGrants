"""Audit discovery decisions; keyword hints are not eligibility ground truth."""

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from filters import discovery_decision
from scraper import fetch_all


def analyse(items):
    rows = []
    for item in items:
        state, reason = discovery_decision(item.get("title", ""), item.get("summary", ""), item.get("topic", ""),
            refresh_details=item.get("kind") == "official" and item.get("fetch_details"))
        rows.append({"title": item.get("title"), "source": item.get("source_id"),
                     "url": item.get("url"), "state": state, "reason": reason})
    return {"generated_at": datetime.now(timezone.utc).isoformat(),
            "scope": "discovery_only; final eligibility/funding decisions are in selection_report.json",
            "counts": dict(Counter(row["state"] for row in rows)), "decisions": rows}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = analyse(fetch_all())
    print(json.dumps(result["counts"], ensure_ascii=True))
    print("Discovery candidates still require official evidence and publication screening.")
    if args.json:
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
