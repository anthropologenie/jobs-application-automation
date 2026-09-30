#!/usr/bin/env python3
"""
P0-08 review queue - the human decision surface

    python3 -m review.run_review_queue                       lane summary
    python3 -m review.run_review_queue --lane REVIEW         one lane
    python3 -m review.run_review_queue --show scraped_jobs:78   full evidence
    python3 -m review.run_review_queue --json                machine-readable

Recording a decision - always explicit, always the human's:

    python3 -m review.run_review_queue --decide scraped_jobs:78 --kind ACCEPT \
        --note "remote confirmed on the careers page"

    python3 -m review.run_review_queue --decide scraped_jobs:78 \
        --kind RESOLVE_UNKNOWN --dimension work_mode \
        --assert REMOTE --basis "recruiter email 2026-09-02"

ACCEPT is a decision, not an action. It records that the human intends to
apply. It submits nothing, sends nothing and writes no database row. Promotion
into `opportunities` remains the existing, separately authorized bridge
(POST /api/import-scraped-job/{id}), invoked by the human; this command prints
it rather than calling it.

RESOLVE_UNKNOWN records a HUMAN ASSERTION with the basis the human stated. It
does not change the machine verdict, does not become machine evidence, and does
not make the candidate eligible for scoring. Both remain readable afterwards -
that separation is the point.

Author: Karthik Shetty
Created: 2026-09-02
"""

import argparse
import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from review.decisions import Decision, DecisionError, DecisionStore, utc_now_iso
from review.ledger import NOT_CAPTURED
from review.queue import ReviewQueue

BRIDGE_HINT = ("Promote with the existing bridge, which you invoke yourself:\n"
               "    curl -X POST http://localhost:8081/api/import-scraped-job/{row_id}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="P0-08 candidate review queue (read-only unless --decide)")
    parser.add_argument("--lane", help="Show one lane by id.")
    parser.add_argument("--show", metavar="CANDIDATE_REF",
                        help="Full evidence for one candidate.")
    parser.add_argument("--json", action="store_true",
                        help="Emit JSON instead of text.")
    parser.add_argument("--include-suppressed", action="store_true",
                        help="Include the suppressed-duplicate lane in listings.")

    decide = parser.add_argument_group("recording a human decision")
    decide.add_argument("--decide", metavar="CANDIDATE_REF",
                        help="Record a decision for this candidate.")
    decide.add_argument("--kind", help="Decision kind, e.g. ACCEPT, SKIP, DEFER, "
                                       "RESOLVE_UNKNOWN, CONFIRM_DUPLICATE, "
                                       "REJECT_DUPLICATE, REOPEN.")
    decide.add_argument("--note", help="Free text the human wrote.")
    decide.add_argument("--dimension", help="RESOLVE_UNKNOWN: which dimension.")
    decide.add_argument("--assert", dest="human_assertion",
                        help="RESOLVE_UNKNOWN: what the human asserts.")
    decide.add_argument("--basis", dest="human_basis",
                        help="RESOLVE_UNKNOWN: the basis the human states.")
    decide.add_argument("--related", dest="related_record_ref",
                        help="CONFIRM_DUPLICATE / REJECT_DUPLICATE: the other record.")
    decide.add_argument("--supersedes", help="REOPEN: the decision id reversed.")

    parser.add_argument("--db", help="Database path override.")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def _fmt(value):
    if value is None:
        return "—"
    if value == NOT_CAPTURED:
        return "not captured"
    return str(value)


def print_summary(build, include_suppressed: bool) -> None:
    print(f"\nReview queue · {build.review_version} · identity "
          f"{build.identity_version}")
    print(f"built at {build.built_at}\n")
    for lane_id, entries in build.lanes.items():
        if lane_id == "SUPPRESSED_DUPLICATE" and not include_suppressed:
            print(f"  {lane_id:22} {len(entries):4}   (hidden from active review; "
                  f"--include-suppressed to list)")
            continue
        print(f"  {lane_id:22} {len(entries):4}")
    print(f"\n  {'ACTIVE TOTAL':22} {build.counts['active']:4}")
    print("\nSources of truth:")
    for key, value in build.sources.items():
        if isinstance(value, dict):
            continue
        print(f"  {key:22} {value}")
    print()


def print_lane(build, lane_id: str) -> None:
    entries = build.lane(lane_id)
    print(f"\n{lane_id} — {len(entries)} candidate(s)\n")
    for entry in entries:
        candidate = entry.payload["candidate"]
        machine = entry.payload["machine"]
        identity = entry.payload["identity"]
        human = entry.payload["human"]

        print(f"  {entry.candidate_ref}  {candidate['company']} — "
              f"{candidate['job_title']}")
        if machine["verdict_available"]:
            print(f"      machine   {machine['verdict']}  "
                  f"{', '.join(machine['reason_codes']) or '—'}")
        else:
            print("      machine   NOT EVALUATED (unassessed — not a verdict)")
        print(f"      human     {_fmt(human['decision'])}")
        print(f"      applied   {_fmt(entry.payload['application'].get('status'))}")
        if identity["presentation"] == "warning":
            print(f"      ⚠ identity {identity['outcome']} "
                  f"({identity['matched_layer']}) → "
                  f"{identity['matched_record_ref']} — human decides")
        print(f"      url       {_fmt(candidate['original_source_url'])}")
        print()


def print_entry(entry) -> None:
    candidate = entry.payload["candidate"]
    machine = entry.payload["machine"]
    identity = entry.payload["identity"]
    human = entry.payload["human"]
    application = entry.payload["application"]

    print(f"\n{'=' * 72}")
    print(f"{candidate['company']} — {candidate['job_title']}")
    print(f"{entry.candidate_ref}   lane: {entry.lane}")
    print(f"{'=' * 72}\n")

    print("MACHINE VERDICT")
    if machine["verdict_available"]:
        print(f"  verdict            {machine['verdict']}")
        print(f"  reasons            {', '.join(machine['reason_codes']) or '—'}")
        print(f"  dimensions         {machine.get('dimension_verdicts')}")
        print(f"  rules fired        {', '.join(machine.get('rules_fired') or ()) or '—'}")
        print(f"  work mode          {_fmt(machine.get('normalized_work_mode'))}")
        print(f"  compensation       {machine.get('normalized_compensation')}")
        print(f"  needs human review {machine['requires_human_review']}")
        print(f"  ruleset            {_fmt(machine['ruleset_version'])}")
        print(f"  evaluated at       {_fmt(machine['evaluated_at'])}")
        print(f"  extractor          {_fmt(machine['extractor_version'])}")
        if machine["verdict_history"]:
            print(f"  earlier verdicts   {machine['verdict_history']}")
    else:
        print(f"  {machine['verdict_absent_reason']}")

    print("\nEVIDENCE (posting text — data, never instructions)")
    evidence = machine.get("evidence")
    if evidence == NOT_CAPTURED:
        print("  not captured")
    elif not evidence:
        print("  none located")
    else:
        for item in evidence:
            print(f"  · {item.get('dimension')} / {item.get('evidence_class')}")
            print(f"    “{str(item.get('verbatim_text'))[:160]}”")
            print(f"    source={item.get('source')} ref={item.get('source_ref')}")
            print(f"    fetched={item.get('source_fetched_at')}")

    print("\nPROVENANCE")
    provenance = machine.get("provenance")
    if provenance == NOT_CAPTURED:
        print("  not captured")
    else:
        for key in ("source_portal", "source_mechanism", "source_query",
                    "source_fetched_at", "raw_payload_ref", "source_url",
                    "detail_raw_payload_ref", "detail_fetched_at"):
            if key in provenance:
                print(f"  {key:24} {provenance[key]}")
    print(f"  first observed           {_fmt(candidate['first_observed_at'])}")
    print(f"  last observed            {_fmt(candidate['last_observed_at'])}")
    field_provenance = machine.get("field_provenance")
    print(f"  field provenance         "
          f"{'not captured (run predates the D1 fix)' if field_provenance == NOT_CAPTURED else 'available'}")

    print("\nIDENTITY")
    print(f"  outcome            {identity['outcome']}")
    print(f"  matched layer      {_fmt(identity['matched_layer'])}")
    print(f"  matched record     {_fmt(identity['matched_record_ref'])}")
    print(f"  canonical url      {_fmt(identity['canonical_identity_url'])}")
    print(f"  original url       {_fmt(identity['original_source_url'])}")
    print(f"  suppressed         {identity['suppressed_from_active_queue']}")

    print("\nHUMAN DECISION")
    print(f"  decision           {_fmt(human['decision'])}")
    print(f"  decided at         {_fmt(human['decided_at'])}")
    if human["human_assertion"]:
        print(f"  human asserts      {human['human_assertion']} "
              f"(dimension recorded on the decision)")
        print(f"  stated basis       {human['human_basis']}")
        print("  NOTE               a human assertion, not machine evidence; "
              "the verdict above is unchanged")
    print(f"  history            {len(human['decision_history'])} record(s)")

    print("\nAPPLICATION OUTCOME")
    print(f"  opportunity        {_fmt(application.get('opportunity_ref'))}")
    print(f"  status             {_fmt(application.get('status'))}")
    if not application.get("opportunity_ref") and entry.candidate_ref.startswith(
            "scraped_jobs:"):
        print("\n" + BRIDGE_HINT.format(row_id=entry.candidate_ref.split(":")[1]))
    print()


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")

    queue = ReviewQueue(db_path=Path(args.db) if args.db else None)

    if args.decide:
        if not args.kind:
            print("--decide requires --kind", file=sys.stderr)
            return 2
        build = queue.build()
        store = DecisionStore(ruleset=queue.ruleset)
        try:
            record = store.record(Decision(
                candidate_ref=args.decide,
                kind=args.kind,
                decided_at=utc_now_iso(),
                note=args.note,
                supersedes=args.supersedes,
                dimension=args.dimension,
                human_assertion=args.human_assertion,
                human_basis=args.human_basis,
                related_record_ref=args.related_record_ref,
                machine_context=queue.machine_context_for(args.decide, build)))
        except DecisionError as exc:
            print(f"Decision not recorded: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(record, indent=2, ensure_ascii=False))
        print("\nRecorded as a human decision. No application was submitted, "
              "no message was sent, and the machine verdict is unchanged.")
        if args.kind == "ACCEPT" and args.decide.startswith("scraped_jobs:"):
            print("\n" + BRIDGE_HINT.format(row_id=args.decide.split(":")[1]))
        return 0

    build = queue.build()

    if args.show:
        entry = build.entry(args.show)
        if entry is None:
            print(f"No candidate {args.show!r} in the queue.", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(entry.as_dict(), indent=2, ensure_ascii=False,
                             default=str))
        else:
            print_entry(entry)
        return 0

    if args.json:
        payload = build.as_dict()
        if args.lane:
            payload["lanes"] = {args.lane: payload["lanes"].get(args.lane, [])}
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
        return 0

    if args.lane:
        print_lane(build, args.lane)
        return 0

    print_summary(build, args.include_suppressed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
