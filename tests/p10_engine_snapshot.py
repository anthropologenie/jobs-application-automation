"""
P10 parity helper (not collected by pytest: no test_ prefix).

`engine_snapshot` reads ONLY the engine's own state (the v2 store under <out>/state/), never the digest, so the
same function describes a P9 run and a P10 run. Per requisition it records the current evaluation's verdicts,
rule ids, flags, lane, relevance and experience, the newness state, and the plan_day queue state (carry days,
surfaced / planned day, OR-88 parking). No wall-clock value is included.

`tests/fixtures/p10/p9_engine_reference.json` was produced by `python3 tests/p10_engine_snapshot.py` against the
unmodified P9 code at 6913f12 (before any P10 change): the four P9 fixture days, default cap, one snapshot per day.
"""

import json
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures" / "p9"
REFERENCE = ROOT / "tests" / "fixtures" / "p10" / "p9_engine_reference.json"
DAYS = ["2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04"]
INPUTS = ["day1_export.json", "day2_export.csv", "day3_export.json", "day4_export.json"]


def engine_snapshot(out) -> dict:
    conn = sqlite3.connect(Path(out) / "state" / "jobops-p9.sqlite")
    conn.row_factory = sqlite3.Row
    try:
        snap = {}
        for req in conn.execute("SELECT requisition_id, newness_state, duplicate_of FROM requisition "
                                "ORDER BY requisition_id"):
            rid = req["requisition_id"]
            ev = conn.execute("SELECT queue_lane, result_json FROM evaluation WHERE requisition_id=? "
                              "ORDER BY seq DESC LIMIT 1", (rid,)).fetchone()
            r = json.loads(ev["result_json"])
            qs = conn.execute("SELECT carry_days, first_review_day, last_planned_day, last_surfaced_day, "
                              "overflow_parked_on FROM queue_state WHERE requisition_id=?", (rid,)).fetchone()
            snap[rid] = {
                "lane": ev["queue_lane"],
                "dims": {d: [v["verdict"], v["rule_id"], sorted(v["flags"])]
                         for d, v in sorted(r["eligibility_dimensions"].items())},
                "relevance": r["relevance"]["relevance_label"],
                "experience": r["relevance"].get("experience_signal"),
                "flags": sorted(r["flags"]),
                "review_flags": sorted(r["review_flags"]),
                "newness": req["newness_state"],
                "duplicate_of": req["duplicate_of"],
                "queue_state": dict(qs) if qs else None,
            }
        return snap
    finally:
        conn.close()


def four_day_snapshots(out, run) -> dict:
    """Run the four P9 fixture days into `out` with `run(input, out, day)`; snapshot the engine after each."""
    snaps = {}
    for day, name in zip(DAYS, INPUTS):
        assert run(FIX / name, out, day) == 0, day
        snaps[day] = engine_snapshot(out)
    return snaps


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "tests"))
    from jobops.cli import main

    def _run(inp, out, day):
        return main(["source", "--input", str(inp), "--policy", "0.2.6", "--out", str(out), "--date", day])

    with tempfile.TemporaryDirectory() as tmp:
        snaps = four_day_snapshots(Path(tmp), _run)
    REFERENCE.parent.mkdir(parents=True, exist_ok=True)
    REFERENCE.write_text(json.dumps({"generated_from": "P9 code at 6913f12 (unmodified)", "snapshots": snaps},
                                    indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(REFERENCE, sum(len(s) for s in snaps.values()), "requisition-days")
