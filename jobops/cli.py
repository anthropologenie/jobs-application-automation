"""
Command line for P9 (Phase C-lite). Manually triggered, offline, deterministic.

    python3 -m jobops source --input <file> --policy 0.2.6 --out <dir> [--review-cap N] [--date YYYY-MM-DD]
    python3 -m jobops decisions --import <decisions.csv> --out <dir> [--date YYYY-MM-DD]

No scheduler, no network, no LLM, no application submission. The live data/jobs-tracker.db is never opened
(the v2 store refuses it, and P9 state lives under <out>/state/).
"""

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from .decisions import DecisionError, import_decisions
from .digest import metrics, write_outputs
from .normalize import SchemaError
from .sourcing import RunRefused, policy_version, run_source


def _date(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise argparse.ArgumentTypeError("expected YYYY-MM-DD")
    datetime.strptime(value, "%Y-%m-%d")
    return value


def _cap(value: str) -> int:
    n = int(value)
    if n < 1:
        raise argparse.ArgumentTypeError("--review-cap must be >= 1")
    return n


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python3 -m jobops", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="command", required=True)
    s = sub.add_parser("source", help="evaluate a downloaded job export and write the daily digest")
    s.add_argument("--input", required=True, type=Path, help="JSON / JSONL / CSV export downloaded by you")
    s.add_argument("--policy", default="0.2.6", help="policy version (default 0.2.6)")
    s.add_argument("--out", required=True, type=Path, help="output directory (state lives in <out>/state)")
    s.add_argument("--review-cap", type=_cap, default=None,
                   help="daily REVIEW presentation cap (default: the policy's queue cap, 10)")
    s.add_argument("--date", type=_date, default=None, help="run date YYYY-MM-DD (default: today, UTC)")
    d = sub.add_parser("decisions", help="import your filled-in decisions.csv into the local P9 state")
    d.add_argument("--import", dest="csv", required=True, type=Path)
    d.add_argument("--out", required=True, type=Path)
    d.add_argument("--date", type=_date, default=None, help="date recorded for 'applied' events (default today)")
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "source":
            day = args.date or datetime.now(timezone.utc).date().isoformat()
            res = run_source(args.input, policy_version(args.policy), args.out, day, args.review_cap)
            day_dir = write_outputs(res, args.out)
            m = metrics(res)
            print(f"Policy: {res['policy_version'].split('@')[1]}")
            print(f"Policy SHA: {res['policy_sha256']}")
            print("Gate E: pending")
            print(json.dumps({k: m[k] for k in ("jobs_in", "unique_jobs", "duplicates", "SHORTLIST", "REVIEW",
                                                "PARKED", "EXCLUDED", "shortlist_plus_review")}, sort_keys=True))
            if res["reran"]:
                print("Note: this input was already processed for this date; outputs were re-rendered, nothing re-ingested.")
            print(f"Digest: {day_dir / 'digest.md'}")
        else:
            summary = import_decisions(args.csv, args.out, args.date)
            print(json.dumps(summary, indent=2))
            if summary["errors"]:
                return 1
    except (SchemaError, RunRefused, DecisionError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0
