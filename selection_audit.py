"""Public-source decision trail; never serialize credentials or provider payloads."""

import json
from pathlib import Path
from datetime import datetime, timezone

_decisions = []


def reset():
    _decisions.clear()


def record(stage, grant, state, reason):
    _decisions.append({"stage": stage, "title": str(grant.get("title", ""))[:250],
                       "url": str(grant.get("url", ""))[:2000],
                       "source_url": str(grant.get("source_url", ""))[:2000],
                       "evidence_url": str(grant.get("official_evidence_url", ""))[:2000],
                       "state": state, "reason": reason})


def snapshot():
    return {"generated_at": datetime.now(timezone.utc).isoformat(), "decisions": list(_decisions)}


def write_report(path="selection_report.json"):
    try:
        Path(path).write_text(json.dumps(snapshot(), ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        print(f"Saralash hisoboti faylga saqlanmadi ({type(exc).__name__}); asosiy jurnal saqlanadi.")
