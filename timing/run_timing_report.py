#!/usr/bin/env python3
"""
P0-10 time instrumentation - the report, and the one command that records a submission

    python3 -m timing.run_timing_report                     the report
    python3 -m timing.run_timing_report --json              machine-readable
    python3 -m timing.run_timing_report --candidate scraped_jobs:78
                                                            one timeline

Recording an actual submission - always the human's own statement:

    python3 -m timing.run_timing_report --record-submission scraped_jobs:78 \
        --submitted-at 2026-09-07T10:30:00+00:00 \
        --method "company careers portal" --note "referral link"

    python3 -m timing.run_timing_report --record-submission scraped_jobs:78 \
        --submitted-now

This command does NOT submit an application. It writes one line to
data/application/submissions.jsonl saying that the human submitted it
themselves, somewhere else. JobOps contacts no employer, calls no ATS, and has
no code path that could: nothing in this repository submits anything.

An ACCEPT decision is not a submission and never becomes one. If a candidate
has a standing ACCEPT and no submission record, that is reported as exactly
that - never as a zero-minute time-to-submit.

Correcting a record is append-only: pass --supersedes with the id of the
record being replaced. The replaced record stays in the file and stays
readable.

Author: Karthik Shetty
Created: 2026-09-07
"""

import argparse
import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from timing.clock import utc_now_iso
from timing.lifecycle import LifecycleReader
from timing.metrics import TimingReport
from timing.ruleset import MEASURED, NOT_AVAILABLE, load_timing_ruleset
from timing.submissions import (
    SOURCE_HUMAN_STATED,
    SOURCE_RECORDED_NOW,
    SubmissionError,
    SubmissionEvent,
    SubmissionStore,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="P0-10 per-candidate time instrumentation "
                    "(read-only unless --record-submission)")
    parser.add_argument("--json", action="store_true",
                        help="Emit JSON instead of text.")
    parser.add_argument("--candidate", metavar="CANDIDATE_REF",
                        help="Show one candidate's full lifecycle timeline.")

    record = parser.add_argument_group(
        "recording an actual submission (the human's own statement)")
    record.add_argument("--record-submission", metavar="CANDIDATE_REF",
                        dest="record_submission",
                        help="Record that YOU submitted this application.")
    record.add_argument("--submitted-at",
                        help="When the application was actually submitted, "
                             "ISO 8601. Required unless --submitted-now.")
    record.add_argument("--submitted-now", action="store_true",
                        help="The submission just happened; use this moment.")
    record.add_argument("--method", help="Where it was submitted, e.g. "
                                         "'company careers portal'.")
    record.add_argument("--note", help="Free text.")
    record.add_argument("--supersedes", help="Correct an earlier submission "
                                             "record by its submission_id.")

    parser.add_argument("--db", help="Database path override.")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


# ---------------------------------------------------------------- rendering

def _state(record) -> str:
    return record.get("state", "?")


def _minutes(value) -> str:
    if value is None:
        return "—"
    if value < 90:
        return f"{value:.1f} min"
    if value < 60 * 48:
        return f"{value / 60:.1f} h"
    return f"{value / 1440:.1f} d"


def print_report(report) -> None:
    print(f"\nP0-10 time instrumentation · {report['timing_version']} · "
          f"review {report['review_version']} · identity "
          f"{report['identity_version']}")
    print(f"built at {report['built_at']}\n")

    print("FUNNEL — each row counts a different thing, deliberately")
    for key, metric in report["funnel"].items():
        value = metric["value"] if metric["state"] == MEASURED else metric["state"]
        print(f"  {key:52} {str(value):>6}")

    print("\nDURATIONS — elapsed lifecycle time, NOT human effort")
    for key, metric in report["durations"].items():
        if metric["state"] == MEASURED:
            print(f"  {key:52} median {_minutes(metric['median']):>9}   "
                  f"p90 {_minutes(metric['p90']):>9}   n={metric['n']}")
        else:
            print(f"  {key:52} {metric['state']}")
            if metric.get("why"):
                print(f"      {metric['why']}")
        if metric.get("candidates_with_inconsistent_events"):
            print(f"      {metric['candidates_with_inconsistent_events']} "
                  f"candidate(s) with out-of-order events, withheld: "
                  f"{', '.join(metric['inconsistent_candidates'])}")

    print("\nRATES")
    for key, metric in report["rates"].items():
        if metric["state"] == MEASURED:
            print(f"  {key:52} {metric['value']:.3f}   "
                  f"({metric['numerator']}/{metric['denominator']})")
        else:
            print(f"  {key:52} {metric['state']}   "
                  f"({metric['numerator']}/{metric['denominator']})")

    discipline = report["reporting_discipline"]
    print("\nVETO RATE PER REASON CODE (P0_SPEC 11.4 — never aggregate only)")
    codes = discipline["veto_rate_per_reason_code"]
    if codes.get("state") == NOT_AVAILABLE:
        print(f"  {codes['why']}")
    else:
        for code, metric in codes.items():
            print(f"  {code:52} {metric['numerator']}/{metric['denominator']}")

    print("\nUNKNOWN RATE PER DIMENSION (P0_SPEC 11.4)")
    dimensions = discipline["unknown_rate_per_dimension"]
    if dimensions.get("state") == NOT_AVAILABLE:
        print(f"  {dimensions['why']}")
    else:
        for dimension, metric in dimensions.items():
            print(f"  {dimension:52} {metric['numerator']}/"
                  f"{metric['denominator']}")

    print("\nTHROUGHPUT PER UTC DAY")
    for key, metric in report["throughput"].items():
        if metric["state"] == MEASURED:
            print(f"  {key:52} {metric['total']} over "
                  f"{metric['days_with_activity']} active day(s), span "
                  f"{metric['span_days']}d")
            for day, n in metric["by_day"].items():
                print(f"      {day}   {n}")
        else:
            print(f"  {key:52} {metric['state']}")

    window = report["window"]
    print(f"\nEXIT WINDOW — {window['observed_span_days_of_human_events']}d "
          f"observed of {window['required_days_for_exit_criterion']}d required "
          f"→ {'MET' if window['meets_exit_criterion_window'] else 'NOT MET'}")

    print("\nSYSTEM STAGES — from the run manifests P0-06 already writes")
    for run in report["system_stages"]["runs"]:
        print(f"  {run['run_id']}  wall {run['wall_seconds']:.1f}s  "
              f"{run['candidates_normalized']} candidate(s)  "
              f"{run['seconds_per_candidate']:.1f}s/candidate  "
              f"of which rate-limit sleep {run['rate_limit_sleep_seconds']}s")
    print(f"  per-candidate stage timers: "
          f"{report['system_stages']['per_candidate_stage_timers']['state']}")

    print("\nAPPLICATION TABLE — reported beside the funnel, never inside it")
    application = report["application_state"]
    print(f"  opportunities rows                                   "
          f"{application['opportunities_total']}")
    print(f"  linked to a candidate row                            "
          f"{application['opportunities_linked_to_a_candidate_row']}")
    print(f"  status='Applied' (a workflow state, NOT a submission) "
          f"{application['legacy_applied_rows']}")

    print("\nNOT MEASURABLE")
    for item in report["not_measurable"]:
        print(f"  · {item['quantity']}")
        print(f"    {item['why']}")
        if item.get("consequence"):
            print(f"    {item['consequence']}")

    print("\nLIMITATIONS")
    for limitation in report["limitations"]:
        print(f"  · {limitation}")
    print()


def print_timeline(timeline) -> None:
    data = timeline.as_dict()
    print(f"\n{'=' * 72}")
    print(f"{data['candidate_ref']}   lane: {data['lane']}")
    print(f"{'=' * 72}\n")
    print(f"machine verdict      {data['verdict'] or 'NOT EVALUATED'}"
          f"   {', '.join(data['reason_codes']) or ''}")
    print(f"identity             {data['identity_outcome']}"
          f"{'  (suppressed from active review)' if data['suppressed_from_active_queue'] else ''}")

    print("\nEVENTS")
    for event_id, event in data["events"].items():
        if event["observed"]:
            print(f"  {event_id:26} {event['at']}   [{event['origin']}]")
        else:
            print(f"  {event_id:26} not recorded")
    print(f"  {'QUEUE_AVAILABLE':26} not observed — derived lower bound "
          f"{data['derived']['queue_availability_lower_bound']}")
    print(f"  {'REVIEW_STARTED':26} not observed — active human effort is not "
          f"measurable")

    print("\nINTERVALS (elapsed lifecycle time, not human effort)")
    for interval in data["intervals"].values():
        if interval["state"] == MEASURED:
            print(f"  {interval['id']:44} {_minutes(interval['minutes'])}")
        else:
            print(f"  {interval['id']:44} {interval['state']}")
            if interval.get("note"):
                print(f"      {interval['note']}")

    print("\nHUMAN")
    print(f"  standing decision    {data['human']['standing_decision'] or '—'}")
    print(f"  decided at           {data['human']['standing_decided_at'] or '—'}")
    print(f"  decisions recorded   {data['human']['decision_count']}")

    print("\nAPPLICATION")
    print(f"  opportunity          {data['application'].get('opportunity_ref') or '—'}")
    print(f"  workflow status      {data['application'].get('status') or '—'}")

    print("\nSUBMISSION")
    if data["submission"]:
        submission = data["submission"]
        print(f"  submitted at         {submission['submitted_at']}   "
              f"({submission['submitted_at_source']})")
        print(f"  recorded at          {submission['recorded_at']}")
        print(f"  method               {submission['method'] or '—'}")
        print(f"  submitted by JobOps  {submission['submitted_by_jobops']}")
    else:
        print("  none recorded. An ACCEPT is not a submission; no submission "
              "time is inferred.")
    print()


# ------------------------------------------------------------------ recording

def record_submission(args, reader: LifecycleReader) -> int:
    if not args.submitted_at and not args.submitted_now:
        print("--record-submission requires --submitted-at <ISO 8601>, or "
              "--submitted-now if it just happened. There is no default: an "
              "unstated submission time is a missing event.", file=sys.stderr)
        return 2
    if args.submitted_at and args.submitted_now:
        print("Pass either --submitted-at or --submitted-now, not both.",
              file=sys.stderr)
        return 2

    build = reader.queue.build()
    entry = build.entry(args.record_submission)
    if entry is None:
        print(f"No candidate {args.record_submission!r} in the queue. A "
              "submission event must name a candidate that exists, so a typo "
              "cannot create an orphan event.", file=sys.stderr)
        return 1

    standing_accept = reader.human_block(
        entry.payload["human"])["standing_accept"]

    store = SubmissionStore(ruleset=reader.ruleset)
    try:
        record = store.record(SubmissionEvent(
            candidate_ref=args.record_submission,
            submitted_at=args.submitted_at or utc_now_iso(),
            submitted_at_source=(SOURCE_RECORDED_NOW if args.submitted_now
                                 else SOURCE_HUMAN_STATED),
            method=args.method,
            note=args.note,
            decision_ref=standing_accept["decision_id"] if standing_accept else None,
            supersedes=args.supersedes))
    except SubmissionError as exc:
        print(f"Submission not recorded: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(record, indent=2, ensure_ascii=False))
    print("\nRecorded that YOU submitted this application. JobOps submitted "
          "nothing, contacted nobody, and made no external request. The "
          "machine verdict and your review decision are unchanged.")
    if not standing_accept:
        print("\nNote: this candidate has no standing ACCEPT decision, so "
              "time_from_decision_to_submission stays NOT_AVAILABLE for it. "
              "The submission is recorded as it happened; no decision "
              "timestamp is invented to complete the interval.")
    return 0


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")

    reader = LifecycleReader(db_path=Path(args.db) if args.db else None,
                             ruleset=load_timing_ruleset())

    if args.record_submission:
        return record_submission(args, reader)

    if args.candidate:
        timelines = {t.candidate_ref: t for t in reader.timelines()}
        timeline = timelines.get(args.candidate)
        if timeline is None:
            print(f"No candidate {args.candidate!r} in the queue.",
                  file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(timeline.as_dict(), indent=2, ensure_ascii=False,
                             default=str))
        else:
            print_timeline(timeline)
        return 0

    report = TimingReport(reader=reader, ruleset=reader.ruleset).build()
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
        return 0
    print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
