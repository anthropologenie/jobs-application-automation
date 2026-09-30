#!/usr/bin/env python3
"""
The submission event ledger - the one thing P0-10 persists

The gap this closes
-------------------
Nothing in JobOps records the moment an application was actually submitted to
an employer. P0-08 records that a human DECIDED to apply. The bridge records
that a candidate ENTERED the application workflow. `opportunities.status`
records a workflow state whose transitions nothing defines and whose companion
`applied_date` is a DATE - day precision, no time of day.

None of those is a submission. Treating any of them as one would produce a
time-to-submit that a human could improve by pressing a button earlier, which
is precisely the metric this instrumentation must not create.

So there is exactly one way a submission enters this system: a human runs the
record command and states that they submitted it.

Why a fourth store
------------------
P0-08 argued that a human decision must live apart from a machine verdict so
the two can never be confused. The same argument applies once more, and the
prompt for this work states it as a requirement: machine verdict, human
decision, application state and submission event are four separate facts.

    data/ingestion/candidates/<run>.jsonl   machine verdict     (P0-06/P0-02)
    data/review/decisions.jsonl             human decision      (P0-08)
    data/jobs-tracker.db :: opportunities   application state   (existing)
    data/application/submissions.jsonl      submission event    (P0-10, here)

Folding submissions into `decisions.jsonl` would merge realities two and four
into one store and make "the human decided to apply" and "the human applied"
grep-identical. They are not the same event and they are not kept in the same
file. This store is append-only, candidate-keyed, and written by P0-10 alone;
it competes with nothing, because no other store records this fact at all.

What recording a submission does NOT do
---------------------------------------
It does not submit anything. JobOps has no submission path, contacts no
employer, calls no ATS and makes no external request - recording is a note in a
file about something the human already did elsewhere. It does not change a
machine verdict, machine evidence or machine provenance; it does not turn an
UNKNOWN into a PASS; it does not edit a human decision; it does not write to
the database or to any store another task owns.

Author: Karthik Shetty
Created: 2026-09-07
"""

import hashlib
import json
import logging
import os
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from .clock import TimestampError, parse_timestamp, utc_now, utc_now_iso
from .ruleset import TimingDriftError, TimingRuleset, load_timing_ruleset

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SUBMISSION_ROOT = REPO_ROOT / "data" / "application"

EVENT_APPLICATION_SUBMITTED = "APPLICATION_SUBMITTED"
ACTOR_HUMAN = "human"

# A human cannot have already submitted something in the future. A little slack
# absorbs clock skew between a stated timestamp and this process's clock;
# anything beyond it is a typo or a fabricated duration, and is refused.
FUTURE_TOLERANCE = timedelta(minutes=5)

# How submitted_at was obtained. Recorded on every record, because "the human
# typed this moment from memory" and "this record IS the observation" are
# different evidential claims and a later reader deserves to know which.
SOURCE_HUMAN_STATED = "human_stated"
SOURCE_RECORDED_NOW = "recorded_now"


class SubmissionError(RuntimeError):
    """Raised when a submission cannot be recorded as declared."""


@dataclass(frozen=True)
class SubmissionEvent:
    """One human-recorded submission, exactly as it will be appended."""
    candidate_ref: str
    submitted_at: str
    submitted_at_source: str = SOURCE_HUMAN_STATED
    actor: str = ACTOR_HUMAN
    method: Optional[str] = None
    note: Optional[str] = None
    decision_ref: Optional[str] = None
    supersedes: Optional[str] = None
    recorded_at: Optional[str] = None
    submission_id: Optional[str] = None

    def payload(self) -> Dict[str, Any]:
        record: Dict[str, Any] = {
            "submission_id": self.submission_id,
            "event": EVENT_APPLICATION_SUBMITTED,
            "candidate_ref": self.candidate_ref,
            # When the human says the application was actually submitted.
            "submitted_at": self.submitted_at,
            "submitted_at_source": self.submitted_at_source,
            # When this record was appended. Kept separately and never used as
            # the submission moment, so a late record stays visibly late.
            "recorded_at": self.recorded_at or utc_now_iso(),
            "actor": self.actor,
            "method": self.method,
            "note": self.note,
            # A REFERENCE to the standing decision, not a copy of it. The
            # decision, its note and the machine context it captured stay in
            # decisions.jsonl, which this store never reads for content and
            # never writes.
            "decision_ref": self.decision_ref,
            # Stated on every record so that no reader, and no grep, has to
            # infer any of it.
            "recorded_by": "human",
            "is_machine_evidence": False,
            "submitted_by_jobops": False,
            "external_request_made": False,
            "changes_machine_verdict": False,
            "changes_human_decision": False,
            "meaning": "A human recorded that they submitted this application "
                       "themselves, outside JobOps. Recording is not submitting.",
        }
        if self.supersedes is not None:
            record["supersedes"] = self.supersedes
        return record


class SubmissionStore:
    """Append-only JSONL store of human-recorded submission events."""

    def __init__(self, root: Optional[Path] = None,
                 ruleset: Optional[TimingRuleset] = None):
        self.root = Path(root) if root else DEFAULT_SUBMISSION_ROOT
        self.path = self.root / "submissions.jsonl"
        self.ruleset = ruleset or load_timing_ruleset()
        # Drift check: this store may only write an event the artifact declares.
        self.ruleset.event(EVENT_APPLICATION_SUBMITTED)

    # ------------------------------------------------------------------ read

    def load(self) -> List[Dict[str, Any]]:
        """Every submission event ever recorded, in the order recorded."""
        if not self.path.exists():
            return []
        records: List[Dict[str, Any]] = []
        with open(self.path, "r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise SubmissionError(
                        f"{self.path}:{line_number} is not valid JSON: {exc}") from exc
        return records

    def by_candidate(self) -> Dict[str, List[Dict[str, Any]]]:
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for record in self.load():
            grouped.setdefault(record["candidate_ref"], []).append(record)
        return grouped

    def current_for(self, candidate_ref: str) -> Optional[Dict[str, Any]]:
        """
        The submission record standing for a candidate right now.

        The latest record that nothing later supersedes. A correction is a new
        record naming the one it replaces; the replaced record is not deleted
        and stays readable, so "recorded 14:00, corrected to 10:30" remains a
        visible history rather than a silently better number.
        """
        records = self.by_candidate().get(candidate_ref, [])
        superseded = {r["supersedes"] for r in records if r.get("supersedes")}
        standing = [r for r in records if r["submission_id"] not in superseded]
        return standing[-1] if standing else None

    def history_for(self, candidate_ref: str) -> List[Dict[str, Any]]:
        return list(self.by_candidate().get(candidate_ref, []))

    def standing(self) -> Dict[str, Dict[str, Any]]:
        """The standing submission for every candidate that has one."""
        return {ref: self.current_for(ref) for ref in self.by_candidate()}

    def counts(self) -> Dict[str, int]:
        records = self.load()
        return {
            "records": len(records),
            "standing": len([r for r in self.standing().values() if r]),
            "corrections": len([r for r in records if r.get("supersedes")]),
        }

    # ----------------------------------------------------------------- write

    def _next_id(self, record: Dict[str, Any], position: int) -> str:
        """Content-and-position derived id, in P0-08's DecisionStore pattern."""
        material = json.dumps(
            {k: v for k, v in record.items() if k != "submission_id"},
            sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(f"{position}:{material}".encode("utf-8")).hexdigest()
        return f"sub-{position:06d}-{digest[:12]}"

    def _validate(self, event: SubmissionEvent) -> None:
        if event.candidate_ref is None or not str(event.candidate_ref).strip():
            raise SubmissionError(
                "A submission must name the candidate it is about.")

        if event.submitted_at_source not in (SOURCE_HUMAN_STATED, SOURCE_RECORDED_NOW):
            raise SubmissionError(
                f"submitted_at_source {event.submitted_at_source!r} is not one of "
                f"{SOURCE_HUMAN_STATED!r} or {SOURCE_RECORDED_NOW!r}.")

        try:
            submitted_at = parse_timestamp(event.submitted_at, field="submitted_at")
        except TimestampError as exc:
            raise SubmissionError(str(exc)) from exc
        if submitted_at is None:
            raise SubmissionError(
                "A submission must carry the moment it was submitted. There is "
                "no default: an unstated submission time is a missing event, "
                "not a zero-length one.")
        if submitted_at > utc_now() + FUTURE_TOLERANCE:
            raise SubmissionError(
                f"submitted_at {event.submitted_at!r} is in the future. A "
                "submission that has not happened yet is an intention, and "
                "intentions are recorded as an ACCEPT decision in P0-08.")

        if event.actor != ACTOR_HUMAN:
            raise SubmissionError(
                f"actor {event.actor!r} is not {ACTOR_HUMAN!r}. Only a human "
                "submits an application, so only a human can record having "
                "done so.")

        if event.supersedes:
            known = {r["submission_id"] for r in self.load()}
            if event.supersedes not in known:
                raise SubmissionError(
                    f"Cannot supersede unknown submission {event.supersedes!r}.")

    def record(self, event: SubmissionEvent) -> Dict[str, Any]:
        """
        Append one submission event. Never edits, never deletes, never reorders.

        The file is opened in append mode and one line is written, so a partial
        failure cannot corrupt an earlier record.
        """
        self._validate(event)
        existing = self.load()
        payload = event.payload()
        payload["submission_id"] = self._next_id(payload, len(existing))

        self.root.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        logger.info("Recorded a human-stated submission for %s",
                    payload["candidate_ref"])
        return payload
