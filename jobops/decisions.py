"""
P9 `jobops decisions --import`: record what the human decided, in the local P9 state only.

    applied = yes  -> review decision ACCEPT + application event SUBMITTED_BY_HUMAN (the human applied elsewhere)
    skipped = yes  -> review decision SKIP, note = "skip_reason | notes"
    both blank     -> nothing recorded (the job stays pending)

Nothing is submitted, sent or fetched. Rows already imported are not imported twice (a ledger keyed by the
row content). These are human-labelled operational data; they are not Gate R and nothing is tuned from them.
"""

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from store import repository as repo

from .normalize import TRUTHY
from .sourcing import load_ledger, open_state

LEDGER = "decisions_imported.json"
COLUMNS = ["job_id", "applied", "skipped", "skip_reason", "notes"]


class DecisionError(ValueError):
    pass


def import_decisions(csv_path: Path, out: Path, decided_on: str = None) -> Dict[str, Any]:
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            raise DecisionError(f"{Path(csv_path).name}: missing column(s) {missing}; expected {COLUMNS}")
        rows = list(reader)
    run_ledger_path = Path(out) / "state"
    if not (run_ledger_path / "runs.json").exists():
        raise DecisionError(f"no P9 state under {run_ledger_path}; run `jobops source` with this --out first")
    version = load_ledger(run_ledger_path)["policy_version"]
    conn, state = open_state(out, version)
    ledger_path = state / LEDGER
    done = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.exists() else []
    when = decided_on or datetime.now(timezone.utc).date().isoformat()
    summary = {"applied": 0, "skipped": 0, "blank": 0, "already_imported": 0, "errors": []}
    try:
        known = {r["requisition_id"] for r in repo.requisitions(conn)}
        for n, row in enumerate(rows, start=2):
            rid = (row.get("job_id") or "").strip()
            applied = (row.get("applied") or "").strip().lower() in TRUTHY
            skipped = (row.get("skipped") or "").strip().lower() in TRUTHY
            if not applied and not skipped:
                summary["blank"] += 1
                continue
            if rid not in known:
                summary["errors"].append(f"line {n}: unknown job_id {rid!r}")
                continue
            if applied and skipped:
                summary["errors"].append(f"line {n}: {rid} is marked both applied and skipped")
                continue
            note = " | ".join(x for x in ((row.get("skip_reason") or "").strip(), (row.get("notes") or "").strip()) if x)
            key = hashlib.sha256(json.dumps([rid, applied, skipped, note]).encode()).hexdigest()
            if key in done:
                summary["already_imported"] += 1
                continue
            conn.execute("BEGIN IMMEDIATE")
            try:
                if applied:
                    repo.record_review_decision(conn, rid, "ACCEPT", actor="human", note=note or None,
                                                machine_context={"p9": "decisions import"})
                    repo.record_application_event(conn, rid, "SUBMITTED_BY_HUMAN", actor="human",
                                                  event_at=when, method="manual (outside JobOps)", note=note or None)
                    summary["applied"] += 1
                else:
                    repo.record_review_decision(conn, rid, "SKIP", actor="human", note=note or None,
                                                machine_context={"p9": "decisions import"})
                    summary["skipped"] += 1
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            done.append(key)
        ledger_path.write_text(json.dumps(done, indent=2) + "\n", encoding="utf-8")
    finally:
        conn.close()
    return summary
