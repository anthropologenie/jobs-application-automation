#!/usr/bin/env python3
"""
P0-06 bounded LinkedIn ingestion run

    python3 -m ingestion.run_linkedin_ingestion --plan
    python3 -m ingestion.run_linkedin_ingestion --dry-run  -q "AI Quality Engineer" -n 3
    python3 -m ingestion.run_linkedin_ingestion            -q "AI Quality Engineer" -n 3

`--plan` prints the exact command, the volume ceiling, the write boundary, the
provenance destination and the duplicate-detection contract WITHOUT contacting
LinkedIn. Run it before any live run.

`--dry-run` performs the fetch and the gate evaluation and writes the full
provenance record, but writes no database row.

Neither flag can raise a cap. Caps live in
ingestion/linkedin-ingestion-0.1.0.json and `--limit` may only lower the
per-run result ceiling, never lift it.

Author: Karthik Shetty
Created: 2026-08-31
"""

import argparse
import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ingestion.config import load_config
from ingestion.persistence import CandidateStore
from ingestion.pipeline import LinkedInIngestionPipeline, QuerySpec
from ingestion.linkedin_cli import RuntimeUnavailable


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="P0-06 bounded LinkedIn ingestion (OR-08 Path A)")
    parser.add_argument("-q", "--query", help="Keyword query. Defaults to the "
                                              "first career-doc bucket.")
    parser.add_argument("-l", "--location", help="LinkedIn place string.")
    parser.add_argument("--jobage", type=int, help="Posted within N days.")
    parser.add_argument("-n", "--limit", type=int,
                        help="Lower the per-run result ceiling. Cannot raise it.")
    parser.add_argument("--no-remote-filter", action="store_true",
                        help="Do not pass --remote remote to the CLI.")
    parser.add_argument("--plan", action="store_true",
                        help="Print the run plan and exit. Contacts nothing.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch and gate, but write no database row.")
    parser.add_argument("--no-backup", action="store_true",
                        help="Skip the pre-write database backup.")
    parser.add_argument("--db", help="Database path override.")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def build_query(config, args) -> QuerySpec:
    caps = config.caps
    limit = caps.max_results_per_run
    if args.limit is not None:
        if args.limit > caps.max_results_per_run:
            raise SystemExit(
                f"--limit {args.limit} exceeds max_results_per_run="
                f"{caps.max_results_per_run}. Caps are ceilings; raising one is "
                "an authorized edit to ingestion/linkedin-ingestion-0.1.0.json.")
        limit = args.limit
    return QuerySpec(
        location=args.location or config.default_location,
        query=args.query or config.query_buckets[0],
        jobage=args.jobage if args.jobage is not None else config.default_jobage_days,
        remote=None if args.no_remote_filter else config.remote_filter,
        page=1,
        limit=limit,
    )


def print_plan(config, query: QuerySpec, store: CandidateStore, pipeline) -> None:
    caps = config.caps
    argv = [config.runtime, *config.runtime_args, config.entrypoint,
            "search", "--location", query.location]
    if query.query:
        argv += ["--query", query.query]
    if query.jobage is not None:
        argv += ["--jobage", str(query.jobage)]
    if query.remote:
        argv += ["--remote", query.remote]
    argv += ["--page", str(query.page), "--limit", str(query.limit),
             "--format", "json"]

    plan = {
        "run_id": pipeline.run_id,
        "exact_command": " ".join(argv),
        "cwd": str(config.skill_dir),
        "runtime_on_path": pipeline.cli.runtime_available(),
        "expected_max_source_postings": min(query.limit or caps.max_results_per_run,
                                            caps.max_results_per_run,
                                            caps.max_pages_per_query * config.results_per_page),
        "max_detail_calls": caps.max_detail_calls_per_run,
        "min_interval_seconds": caps.min_interval_seconds,
        "daily_caps": {"search": caps.daily_max_search_calls,
                       "detail": caps.daily_max_detail_calls},
        "database_write_boundary": {
            "database": str(store.db_path),
            "table_written": config.candidate_table,
            "statement": "INSERT OR IGNORE INTO scraped_jobs (...)",
            "columns_written": ["external_id", "source", "job_title", "company",
                                "job_url", "location", "description", "tags",
                                "salary_range", "posted_date"],
            "tables_not_touched": ["opportunities", "interactions", "documents",
                                   "everything else"],
            "scoring_columns_left_null": ["match_score", "classification",
                                          "matched_skills", "matched_domains",
                                          "red_flags", "recommendation"],
            "row_counts_before": store.row_counts(),
        },
        "raw_provenance_destination": {
            "raw_payloads": str(pipeline.raw_store.run_dir),
            "candidate_ledger": str(pipeline.ledger.candidates_dir /
                                    f"{pipeline.run_id}.jsonl"),
            "run_manifest": str(pipeline.ledger.runs_dir / f"{pipeline.run_id}.json"),
        },
        "duplicate_detection": {
            "layer": "L1 - namespaced source-native id",
            "key": "scraped_jobs.external_id = 'linkedin:<job id>' (UNIQUE)",
            "mechanism": "INSERT OR IGNORE; a re-run inserts zero duplicate rows",
            "p0_07_not_implemented": ["L2 URL canonicalization", "L3 company+title+location",
                                      "L4 ATS requisition id", "matching against opportunities",
                                      "identity_uncertain surfacing", "cross-source matching"],
        },
        "verdict_representation": {
            "values": ["PASS", "UNKNOWN", "FAIL"],
            "authority": "policy.HardEligibilityGate reading "
                         "policy/jobops-policy-0.1.0.json",
            "recorded_in": "the candidate ledger's gate_verdict field, with "
                           "reason_codes, rules_fired, dimension_verdicts and evidence",
            "retention": "every verdict is retained; a FAIL is kept with its reason "
                         "codes and stays visible to the human (P0_SPEC 5.2)",
            "not_persisted_to_db": "scraped_jobs has no verdict column and P0-06 "
                                   "applies no migration. Surfacing verdicts in the "
                                   "review queue is a P0-08 dependency.",
        },
        "scoring": "none - P0-06 does not score",
    }
    print(json.dumps(plan, indent=2))


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")

    config = load_config()
    query = build_query(config, args)
    store = CandidateStore(Path(args.db) if args.db else None)
    pipeline = LinkedInIngestionPipeline(config=config, store=store,
                                         dry_run=args.dry_run)

    if args.plan:
        print_plan(config, query, store, pipeline)
        return 0

    try:
        pipeline.cli.preflight()
    except RuntimeUnavailable as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, indent=2),
              file=sys.stderr)
        return 2

    if not args.dry_run and not args.no_backup:
        backup = store.backup()
        print(f"database backup: {backup}", file=sys.stderr)

    summary = pipeline.run([query])
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
