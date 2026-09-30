#!/usr/bin/env python3
"""
Per-candidate lifecycle - the timeline, assembled from events that exist

    P0-08 queue build       machine verdict, identity outcome, lane,
                            human decision, application state
    run manifests           run start / finish
    opportunities           promotion into the application workflow
    submissions.jsonl       the human-recorded submission

    =>  one timeline per candidate, in which every event is either OBSERVED
        with the timestamp that was actually written, or ABSENT and named

This module reads. It writes nothing, opens the database read-only, and does
not build a second copy of P0-08's logic: lanes, suppression, verdicts and
decisions all come from the queue build, so a timeline cannot disagree with the
queue the human actually worked from.

The rule the whole module exists to enforce
-------------------------------------------
An interval is computed only when BOTH of its endpoints were recorded. There is
no substitution, no default and no fallback. A missing endpoint yields
NOT_AVAILABLE and the timeline says which event is missing; endpoints in the
wrong order yield INCONSISTENT and the timeline says so, rather than a negative
duration being turned into a plausible positive one by an abs().

Elapsed, not effort
-------------------
Every interval here is elapsed wall-clock time between two recorded moments. It
spans nights, weekends and everything else the human was doing. None of these
is a measurement of active human attention, and no field in this module is
named as though it were.

Author: Karthik Shetty
Created: 2026-09-07
"""

import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from review.queue import QueueBuild, ReviewQueue

from .clock import (
    is_out_of_order,
    minutes_between,
    parse_date_only,
    parse_timestamp,
    utc_day,
)
from .ruleset import (
    INCONSISTENT,
    MEASURED,
    NOT_AVAILABLE,
    NOT_MEASURABLE,
    TimingRuleset,
    load_timing_ruleset,
)
from .submissions import SubmissionStore

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "jobs-tracker.db"

# The P0-08 decision kind that means "the human decided to apply". It is the
# START of time-to-submit and, per the timing artifact's non_events, can never
# be its end.
ACCEPT = "ACCEPT"
RESOLVE_UNKNOWN = "RESOLVE_UNKNOWN"

SUPPRESSED_LANE = "SUPPRESSED_DUPLICATE"
NOT_EVALUATED_LANE = "NOT_EVALUATED"


def _event(timestamp: Optional[str], *, origin: str,
           store: str, note: Optional[str] = None) -> Dict[str, Any]:
    """One event on a timeline: observed with its timestamp, or absent."""
    parsed = parse_timestamp(timestamp) if timestamp else None
    return {
        "observed": parsed is not None,
        "at": parsed.isoformat() if parsed else None,
        "origin": origin,
        "store": store,
        "note": note,
    }


def _interval(name: str, start: Dict[str, Any], end: Dict[str, Any], *,
              start_event: str, end_event: str,
              measures: str = "elapsed_lifecycle") -> Dict[str, Any]:
    """
    One interval, with the state that honestly describes it.

    MEASURED only when both endpoints exist and are in order. Otherwise
    NOT_AVAILABLE (naming the missing endpoint) or INCONSISTENT. Never 0, and
    never a negative or absolute-valued duration.
    """
    start_at = parse_timestamp(start["at"]) if start["observed"] else None
    end_at = parse_timestamp(end["at"]) if end["observed"] else None

    record: Dict[str, Any] = {
        "id": name,
        "start_event": start_event,
        "end_event": end_event,
        "start_at": start["at"],
        "end_at": end["at"],
        "measures": measures,
        "is_active_human_effort": False,
        "minutes": None,
        "state": NOT_AVAILABLE,
        "missing": [],
    }

    if start_at is None:
        record["missing"].append(start_event)
    if end_at is None:
        record["missing"].append(end_event)
    if record["missing"]:
        record["note"] = ("Not computed: " + ", ".join(record["missing"]) +
                          " was never recorded. A missing event is not a "
                          "zero-length interval.")
        return record

    if is_out_of_order(start_at, end_at):
        record["state"] = INCONSISTENT
        record["note"] = (f"{end_event} is earlier than {start_event}. The "
                          "interval is withheld rather than reported as a "
                          "negative or absolute duration.")
        return record

    record["state"] = MEASURED
    record["minutes"] = minutes_between(start_at, end_at)
    return record


def _unmeasurable_interval(name: str, *, start_event: str, end_event: str,
                           why: str) -> Dict[str, Any]:
    """An interval no mechanism in this architecture can observe."""
    return {
        "id": name,
        "start_event": start_event,
        "end_event": end_event,
        "start_at": None,
        "end_at": None,
        "measures": "elapsed_lifecycle",
        "is_active_human_effort": False,
        "minutes": None,
        "state": NOT_MEASURABLE,
        "missing": [start_event],
        "note": why,
    }


@dataclass(frozen=True)
class CandidateTimeline:
    """One candidate's lifecycle, as far as it was actually observed."""
    candidate_ref: str
    lane: str
    verdict: Optional[str]
    verdict_available: bool
    reason_codes: List[str]
    dimension_verdicts: Dict[str, str]
    identity_outcome: str
    suppressed: bool
    probable_duplicate: bool
    events: Dict[str, Dict[str, Any]]
    derived: Dict[str, Any]
    intervals: Dict[str, Dict[str, Any]]
    human: Dict[str, Any]
    application: Dict[str, Any]
    submission: Optional[Dict[str, Any]]

    @property
    def is_legacy_not_evaluated(self) -> bool:
        """A row no gate evaluation covers. Never part of the evaluated funnel."""
        return not self.verdict_available

    @property
    def in_active_funnel(self) -> bool:
        """Evaluated, and actually put in front of the human."""
        return self.verdict_available and not self.suppressed

    @property
    def standing_accept(self) -> Optional[Dict[str, Any]]:
        return self.human.get("standing_accept")

    @property
    def decision_day(self) -> Optional[str]:
        at = self.human.get("standing_decided_at")
        return utc_day(parse_timestamp(at)) if at else None

    @property
    def submission_day(self) -> Optional[str]:
        if not self.submission:
            return None
        return utc_day(parse_timestamp(self.submission["submitted_at"]))

    def as_dict(self) -> Dict[str, Any]:
        return {
            "candidate_ref": self.candidate_ref,
            "lane": self.lane,
            "verdict": self.verdict,
            "verdict_available": self.verdict_available,
            "reason_codes": list(self.reason_codes),
            "dimension_verdicts": dict(self.dimension_verdicts),
            "identity_outcome": self.identity_outcome,
            "suppressed_from_active_queue": self.suppressed,
            "probable_duplicate_needing_judgement": self.probable_duplicate,
            "legacy_not_evaluated": self.is_legacy_not_evaluated,
            "events": self.events,
            "derived": self.derived,
            "intervals": self.intervals,
            "human": self.human,
            "application": self.application,
            "submission": self.submission,
        }


class LifecycleReader:
    """Assembles candidate timelines. Reads four stores, writes none of them."""

    def __init__(self, *, db_path: Optional[Path] = None,
                 queue: Optional[ReviewQueue] = None,
                 submissions: Optional[SubmissionStore] = None,
                 ruleset: Optional[TimingRuleset] = None):
        self.ruleset = ruleset or load_timing_ruleset()
        self.queue = queue or ReviewQueue(db_path=db_path)
        self.db_path = Path(db_path) if db_path else self.queue.db_path
        self.submissions = submissions or SubmissionStore(ruleset=self.ruleset)

    # ------------------------------------------------------------------ read

    def _connect(self) -> sqlite3.Connection:
        """Read-only, enforced by SQLite. P0-10 performs zero database writes."""
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def _promotions(self) -> Dict[int, Dict[str, Any]]:
        """
        When each candidate entered the application workflow.

        `opportunities.created_at` for rows carrying the migration-005 bridge
        column. Row creation - not preparation, not readiness, not submission.
        `applied_date` is read alongside it and is deliberately kept as a DATE:
        it is a day, and a day cannot be an endpoint of a minute-resolution
        interval.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, status, created_at, applied_date, scraped_job_id "
                "FROM opportunities WHERE scraped_job_id IS NOT NULL "
                "ORDER BY id").fetchall()
        return {int(r["scraped_job_id"]): {
            "opportunity_ref": f"opportunities:{r['id']}",
            "status": r["status"],
            "created_at": r["created_at"],
            "applied_date_day_precision": (
                parse_date_only(r["applied_date"]).isoformat()
                if r["applied_date"] else None),
        } for r in rows}

    def application_state_summary(self) -> Dict[str, Any]:
        """
        What the application table actually contains, kept apart from the funnel.

        `opportunities` predates this funnel: most of its rows were created by
        hand and carry no `scraped_job_id`. Counting those as funnel output
        would inflate every conversion figure, so they are counted separately
        and labelled. `status` is reported as the workflow state it is - never
        translated into a submission.
        """
        with self._connect() as conn:
            by_status = {r["status"]: r["n"] for r in conn.execute(
                "SELECT status, COUNT(*) AS n FROM opportunities "
                "GROUP BY status ORDER BY status")}
            bridged = conn.execute(
                "SELECT COUNT(*) FROM opportunities "
                "WHERE scraped_job_id IS NOT NULL").fetchone()[0]
            total = conn.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0]
        return {
            "opportunities_total": int(total),
            "opportunities_by_status": by_status,
            "opportunities_linked_to_a_candidate_row": int(bridged),
            "opportunities_not_linked_to_any_candidate": int(total) - int(bridged),
            "legacy_applied_rows": int(by_status.get("Applied", 0)),
            "note": "opportunities.status is an application-workflow state. "
                    "'Applied' is not a submission event: nothing defines when "
                    "it is set or by whom, and applied_date is day precision. "
                    "These counts are reported beside the funnel, never inside "
                    "it.",
        }

    def _run_finished(self) -> Dict[str, Optional[str]]:
        return {m["run_id"]: m.get("finished_at")
                for m in self.queue.ledger.run_manifests()}

    # ------------------------------------------------------------- assembly

    def human_block(self, entry_human: Dict[str, Any]) -> Dict[str, Any]:
        """
        What the human decided, read from P0-08's ledger exactly as written.

        The standing ACCEPT is singled out because it is the start of
        time-to-submit. Nothing here writes, edits or reinterprets a decision.
        """
        history = list(entry_human.get("decision_history") or ())
        superseded = {r["supersedes"] for r in history if r.get("supersedes")}
        standing = [r for r in history if r["decision_id"] not in superseded]
        accepts = [r for r in standing if r["kind"] == ACCEPT]
        resolutions = [r for r in standing if r["kind"] == RESOLVE_UNKNOWN]
        return {
            "standing_decision": entry_human.get("decision"),
            "standing_decided_at": entry_human.get("decided_at"),
            "standing_decision_id": entry_human.get("decision_id"),
            "decision_count": len(history),
            "standing_accept": accepts[-1] if accepts else None,
            "standing_unknown_resolution": resolutions[-1] if resolutions else None,
            "reviewed": bool(history),
            "reviewed_note": "A candidate is counted as human-reviewed only "
                             "when a decision was recorded. Reading a candidate "
                             "without deciding leaves no trace, so this "
                             "under-counts review rather than over-counting it.",
        }

    def _timeline(self, entry, promotions: Dict[int, Dict[str, Any]],
                  run_finished: Dict[str, Optional[str]]) -> CandidateTimeline:
        machine = entry.payload["machine"]
        candidate = entry.payload["candidate"]
        identity = entry.payload["identity"]
        human = self.human_block(entry.payload["human"])

        provenance = machine.get("provenance")
        provenance = provenance if isinstance(provenance, dict) else {}

        events: Dict[str, Dict[str, Any]] = {
            "CANDIDATE_OBSERVED": _event(
                provenance.get("source_fetched_at"), origin="machine",
                store="data/ingestion/candidates/<run>.jsonl :: "
                      "provenance.source_fetched_at"),
            "CANDIDATE_DETAIL_FETCHED": _event(
                provenance.get("detail_fetched_at"), origin="machine",
                store="data/ingestion/candidates/<run>.jsonl :: "
                      "provenance.detail_fetched_at"),
            "CANDIDATE_INGESTED": _event(
                candidate.get("row_scraped_at"), origin="machine",
                store="data/jobs-tracker.db :: scraped_jobs.scraped_at",
                note="Row creation, read as UTC (SQLite CURRENT_TIMESTAMP). "
                     "For a legacy row this is the only timestamp that exists, "
                     "and it is not a discovery time."),
            "CANDIDATE_EVALUATED": _event(
                machine.get("evaluated_at") if machine.get("verdict_available")
                else None,
                origin="machine",
                store="data/ingestion/candidates/<run>.jsonl :: "
                      "gate_verdict.evaluated_at"),
            "HUMAN_DECISION": _event(
                human["standing_decided_at"], origin="human",
                store="data/review/decisions.jsonl :: decided_at",
                note="The standing decision. Superseded decisions stay in the "
                     "ledger and in decision_count."),
            "APPLICATION_PROMOTED": _event(
                None, origin="machine record of a human-invoked action",
                store="data/jobs-tracker.db :: opportunities.created_at"),
            "APPLICATION_SUBMITTED": _event(
                None, origin="human",
                store="data/application/submissions.jsonl :: submitted_at"),
        }

        # Promotion into the application workflow, if it happened.
        application = dict(entry.payload["application"])
        row_id = (int(entry.candidate_ref.split(":")[1])
                  if entry.candidate_ref.startswith("scraped_jobs:") else None)
        promotion = promotions.get(row_id) if row_id is not None else None
        if promotion:
            application.update(promotion)
            events["APPLICATION_PROMOTED"] = _event(
                promotion["created_at"],
                origin="machine record of a human-invoked action",
                store="data/jobs-tracker.db :: opportunities.created_at",
                note="Entry into the application workflow via the human-invoked "
                     "bridge. Not preparation, not readiness, not submission.")
        application["status_is_not_a_submission_event"] = (
            "opportunities.status is an application-workflow state owned by the "
            "existing workflow. No contract defines when 'Applied' is set or "
            "that it means an external submission completed, and applied_date "
            "is day precision. It is never used as a submission timestamp.")

        # The human-recorded submission, if one exists.
        submission = self.submissions.current_for(entry.candidate_ref)
        if submission:
            events["APPLICATION_SUBMITTED"] = _event(
                submission["submitted_at"], origin="human",
                store="data/application/submissions.jsonl :: submitted_at",
                note=f"submitted_at_source={submission['submitted_at_source']}; "
                     f"recorded_at={submission['recorded_at']}")

        # A derived bound, named as one. The queue is a pure projection and
        # persists nothing when built, so nothing observes the moment a human
        # was actually shown this candidate. The earliest moment it COULD have
        # appeared is when its run closed. That is a bound, and it is never
        # used as an interval endpoint.
        run_ids = machine.get("run_ids") or []
        bound = next((run_finished.get(r) for r in reversed(run_ids)
                      if run_finished.get(r)), None)
        derived = {
            "queue_availability_lower_bound": bound,
            "queue_availability_lower_bound_note":
                "Derived, not observed. The earliest moment this candidate "
                "could have appeared in a queue build (its run's finished_at). "
                "It is NOT evidence that a human saw it, and no metric uses it.",
        }

        accept_event = _event(
            human["standing_accept"]["decided_at"] if human["standing_accept"] else None,
            origin="human", store="data/review/decisions.jsonl :: ACCEPT.decided_at")
        resolve_event = _event(
            human["standing_unknown_resolution"]["decided_at"]
            if human["standing_unknown_resolution"] else None,
            origin="human",
            store="data/review/decisions.jsonl :: RESOLVE_UNKNOWN.decided_at")

        intervals = {
            "time_from_evaluation_to_decision": _interval(
                "time_from_evaluation_to_decision",
                events["CANDIDATE_EVALUATED"], events["HUMAN_DECISION"],
                start_event="CANDIDATE_EVALUATED", end_event="HUMAN_DECISION"),
            "time_from_queue_availability_to_decision": _unmeasurable_interval(
                "time_from_queue_availability_to_decision",
                start_event="QUEUE_AVAILABLE", end_event="HUMAN_DECISION",
                why="QUEUE_AVAILABLE is not observed: building the queue "
                    "persists nothing, so nothing records that this candidate "
                    "was surfaced to a human. The run-close lower bound is on "
                    "the timeline as a derived bound and is not substituted "
                    "for the missing observation."),
            "time_from_decision_to_submission": _interval(
                "time_from_decision_to_submission",
                accept_event, events["APPLICATION_SUBMITTED"],
                start_event="HUMAN_DECISION:ACCEPT",
                end_event="APPLICATION_SUBMITTED"),
            "time_from_evaluation_to_submission": _interval(
                "time_from_evaluation_to_submission",
                events["CANDIDATE_EVALUATED"], events["APPLICATION_SUBMITTED"],
                start_event="CANDIDATE_EVALUATED",
                end_event="APPLICATION_SUBMITTED"),
            "time_from_decision_to_promotion": _interval(
                "time_from_decision_to_promotion",
                accept_event, events["APPLICATION_PROMOTED"],
                start_event="HUMAN_DECISION:ACCEPT",
                end_event="APPLICATION_PROMOTED"),
            "time_from_accept_to_ready_to_submit": _unmeasurable_interval(
                "time_from_accept_to_ready_to_submit",
                start_event="HUMAN_DECISION:ACCEPT",
                end_event="APPLICATION_READY_TO_SUBMIT",
                why="No readiness event exists. opportunities.status has no "
                    "'drafted'-equivalent value; adding one is JS-11 / P1-06."),
            "system_observed_to_evaluated": _interval(
                "system_observed_to_evaluated",
                events["CANDIDATE_OBSERVED"], events["CANDIDATE_EVALUATED"],
                start_event="CANDIDATE_OBSERVED", end_event="CANDIDATE_EVALUATED",
                measures="elapsed_lifecycle_system"),
        }

        # Only an UNKNOWN can have an UNKNOWN resolved. On anything else the
        # interval is not "missing" - it does not apply.
        if machine.get("verdict") == "UNKNOWN":
            intervals["time_from_unknown_to_human_resolution"] = _interval(
                "time_from_unknown_to_human_resolution",
                events["CANDIDATE_EVALUATED"], resolve_event,
                start_event="CANDIDATE_EVALUATED",
                end_event="HUMAN_DECISION:RESOLVE_UNKNOWN")

        return CandidateTimeline(
            candidate_ref=entry.candidate_ref,
            lane=entry.lane,
            verdict=machine.get("verdict"),
            verdict_available=bool(machine.get("verdict_available")),
            reason_codes=list(machine.get("reason_codes") or ()),
            dimension_verdicts=dict(machine.get("dimension_verdicts") or {}),
            identity_outcome=identity["outcome"],
            suppressed=bool(identity["suppressed_from_active_queue"]),
            probable_duplicate=identity["presentation"] == "warning",
            events=events,
            derived=derived,
            intervals=intervals,
            human=human,
            application=application,
            submission=submission,
        )

    # ----------------------------------------------------------------- build

    def timelines(self, build: Optional[QueueBuild] = None) -> List[CandidateTimeline]:
        """One timeline per candidate the queue knows about, suppressed included."""
        build = build or self.queue.build()
        promotions = self._promotions()
        run_finished = self._run_finished()
        timelines = [self._timeline(entry, promotions, run_finished)
                     for entries in build.lanes.values() for entry in entries]
        return sorted(timelines, key=lambda t: t.candidate_ref)
