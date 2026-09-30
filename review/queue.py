#!/usr/bin/env python3
"""
The review queue - P0-08's human decision surface

    candidate ledger  (machine verdict, evidence, provenance)
          +
    scraped_jobs      (the candidate row, read-only)
          +
    identity/         (duplicate relationships, recomputed, read-only)
          +
    decisions.jsonl   (what the human decided, append-only)
          =
    lanes the human works through

Three things that are deliberately kept apart
---------------------------------------------
Every entry carries them under three separate keys, because conflating them is
exactly what makes a queue untrustworthy six months later:

    entry["machine"]      what the gate decided, and what it could NOT decide
    entry["human"]        what the person decided, and when, and why
    entry["application"]  what actually happened to the application

A human who applies to an UNKNOWN candidate does not turn it into a PASS. The
verdict stays UNKNOWN with its reason codes intact, the decision sits beside it
as a decision, and a later reader can still ask the only question that matters
for calibration: what did the machine know, what did it not know, what did the
human do, and how did it turn out?

What this module does not do
----------------------------
No verdict is derived, re-derived, overridden or written. No score is computed
and no lane is ranked against another - lanes are separate collections, which
is the structural reason an UNKNOWN can never be ordered above a confirmed
PASS. No row is deleted, merged or updated: the database is opened read-only.
Suppressing a duplicate removes it from the ACTIVE presentation and does
nothing else at all.

Author: Karthik Shetty
Created: 2026-09-02
"""

import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from identity import (
    IdentityIndex,
    IdentityResolution,
    IdentityResolver,
    IdentityStore,
    load_identity_ruleset,
    record_from_candidate,
    record_from_scraped_job,
)

from .decisions import DecisionStore
from .ledger import NOT_CAPTURED, CandidateEvidence, CandidateLedgerStore
from .ruleset import ReviewDriftError, ReviewRuleset, load_review_ruleset

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "jobs-tracker.db"

# Display columns. Every scorer-owned column is read for display only and no
# lane order depends on one: P0-08 does not score and does not rank by fit.
_ROW_COLUMNS = (
    "id", "external_id", "source", "job_title", "company", "job_url", "location",
    "tags", "salary_range", "posted_date", "description", "scraped_at",
    "imported_to_opportunities",
)


class _Desc:
    """Sort wrapper that inverts ordering for a descending sort token."""

    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value

    def __lt__(self, other):
        return other.value < self.value

    def __eq__(self, other):
        return self.value == other.value


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class QueueEntry:
    """One candidate as the reviewer sees it."""
    candidate_ref: str
    lane: str
    payload: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return {"candidate_ref": self.candidate_ref, "lane": self.lane,
                **self.payload}


@dataclass(frozen=True)
class QueueBuild:
    """One deterministic construction of the queue."""
    built_at: str
    review_version: str
    identity_version: str
    lanes: Dict[str, List[QueueEntry]]
    counts: Dict[str, int]
    sources: Dict[str, Any]

    def lane(self, lane_id: str) -> List[QueueEntry]:
        return list(self.lanes.get(lane_id, []))

    def entry(self, candidate_ref: str) -> Optional[QueueEntry]:
        for entries in self.lanes.values():
            for entry in entries:
                if entry.candidate_ref == candidate_ref:
                    return entry
        return None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "built_at": self.built_at,
            "review_version": self.review_version,
            "identity_version": self.identity_version,
            "counts": dict(self.counts),
            "sources": dict(self.sources),
            "lanes": {lane: [e.as_dict() for e in entries]
                      for lane, entries in self.lanes.items()},
        }


class ReviewQueue:
    """Builds the queue. Reads four stores, writes none of them."""

    def __init__(self, *, db_path: Optional[Path] = None,
                 ruleset: Optional[ReviewRuleset] = None,
                 ledger: Optional[CandidateLedgerStore] = None,
                 decisions: Optional[DecisionStore] = None,
                 identity_ruleset=None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.ruleset = ruleset or load_review_ruleset()
        self.ledger = ledger or CandidateLedgerStore()
        self.identity_ruleset = identity_ruleset or load_identity_ruleset()
        self.decisions = decisions or DecisionStore(ruleset=self.ruleset)

    # ------------------------------------------------------------------ read

    def _connect(self) -> sqlite3.Connection:
        """
        Read-only, enforced by SQLite.

        The queue is a presentation layer. An UPDATE reached through this
        connection raises, so no amount of later editing can turn P0-08 into
        something that repairs, re-statuses or cleans up operational data.
        """
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def _candidate_rows(self) -> List[Dict[str, Any]]:
        columns = ", ".join(_ROW_COLUMNS)
        with self._connect() as conn:
            return [dict(r) for r in conn.execute(
                f"SELECT {columns} FROM scraped_jobs ORDER BY id")]

    def _opportunity_outcomes(self) -> Dict[int, Dict[str, Any]]:
        """
        Application outcome, keyed by the scraped_jobs row it came from.

        Read through the bridge column migration 005 added. Status is READ
        here and never written: the application outcome is owned by the
        existing opportunities workflow, not by the review queue.
        """
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, company, role, status, applied_date, scraped_job_id "
                "FROM opportunities WHERE scraped_job_id IS NOT NULL "
                "ORDER BY id").fetchall()
        return {int(r["scraped_job_id"]): {
            "opportunity_ref": f"opportunities:{r['id']}",
            "company": r["company"],
            "role": r["role"],
            "status": r["status"],
            "applied_date": r["applied_date"],
        } for r in rows}

    # -------------------------------------------------------------- assembly

    def _machine_block(self, evidence: Optional[CandidateEvidence]) -> Dict[str, Any]:
        """
        What the gate decided - or an explicit statement that it never ran.

        A candidate with no ledger record has no verdict. That is represented as
        verdict_available = False with verdict None. It is never rendered as
        PASS, UNKNOWN or FAIL, because "the gate did not evaluate this" and
        "the gate could not decide" are different facts and only one of them is
        a verdict.
        """
        if evidence is None:
            return {
                "verdict_available": False,
                "verdict": None,
                "verdict_absent_reason": "No gate evaluation covers this "
                                         "candidate. It is unassessed, not "
                                         "assessed-and-unknown.",
                "reason_codes": [],
                "requires_human_review": False,
                "ruleset_version": NOT_CAPTURED,
                "evaluated_at": NOT_CAPTURED,
                "extractor_version": NOT_CAPTURED,
                "normalizer_version": NOT_CAPTURED,
                "evidence": NOT_CAPTURED,
                "field_provenance": NOT_CAPTURED,
                "provenance": NOT_CAPTURED,
                "verdict_history": [],
            }

        verdict = evidence.current.gate_verdict or {}
        return {
            "verdict_available": True,
            "verdict": verdict.get("verdict"),
            "reason_codes": list(verdict.get("reason_codes") or ()),
            "dimension_verdicts": dict(verdict.get("dimension_verdicts") or {}),
            "rules_fired": list(verdict.get("rules_fired") or ()),
            "normalized_work_mode": verdict.get("normalized_work_mode"),
            "normalized_compensation": verdict.get("normalized_compensation"),
            "work_mode_provenance": verdict.get("work_mode_provenance"),
            "compensation_provenance": verdict.get("compensation_provenance"),
            "requires_human_review": bool(verdict.get("requires_human_review")),
            "eligible_for_scoring": bool(verdict.get("eligible_for_scoring")),
            "company_type_signal": verdict.get("company_type_signal"),
            "evidence": verdict.get("evidence", []),
            "unresolved_evidence": verdict.get("unresolved_evidence", []),
            "located_evidence": evidence.get("located_evidence"),
            "ruleset_version": verdict.get("ruleset_version"),
            "evaluated_at": verdict.get("evaluated_at"),
            "extractor_version": evidence.get("extractor_version"),
            "normalizer_version": evidence.get("normalizer_version"),
            "derived_fields": evidence.get("derived_fields"),
            # Absent for runs predating the P0-07 D1 fix. Reported as
            # NOT_CAPTURED rather than as an empty structure.
            "field_provenance": evidence.get("field_provenance"),
            "provenance": evidence.get("provenance"),
            "run_ids": evidence.run_ids,
            "verdict_history": evidence.verdict_history,
            "persistence": evidence.get("persistence"),
        }

    def _identity_block(self, resolution: IdentityResolution) -> Dict[str, Any]:
        presentation = self.ruleset.duplicate_presentation(resolution.outcome)
        suppressed = self.ruleset.suppresses(resolution.outcome,
                                             resolution.matched_layer)
        return {
            "outcome": resolution.outcome,
            "matched_layer": resolution.matched_layer,
            "matched_record_ref": resolution.matched_record_ref,
            "matched_record_kind": resolution.matched_record_kind,
            "identity_uncertain": resolution.identity_uncertain,
            "has_uncertain_match": resolution.has_uncertain_match,
            "reason_codes": list(resolution.reason_codes),
            "canonical_identity_url": resolution.candidate.canonical_identity_url,
            "original_source_url": resolution.candidate.original_source_url,
            "matches": [m.as_dict() for m in resolution.matches],
            "considered": [dict(c) for c in resolution.considered],
            "presentation": presentation.get("presentation", "none"),
            "suppressed_from_active_queue": suppressed,
            # Stated explicitly so no reader has to infer that suppression is a
            # presentation decision rather than a data operation.
            "suppression_effect": "Hidden from the ACTIVE lanes only. The record, "
                                  "its evidence and its provenance are untouched "
                                  "and remain retrievable.",
        }

    def _human_block(self, candidate_ref: str,
                     machine: Dict[str, Any]) -> Dict[str, Any]:
        standing = self.decisions.current_for(candidate_ref)
        history = self.decisions.history_for(candidate_ref)
        return {
            "decision": standing["kind"] if standing else None,
            "decided_at": standing["decided_at"] if standing else None,
            "decision_id": standing["decision_id"] if standing else None,
            "note": standing.get("note") if standing else None,
            "human_assertion": standing.get("human_assertion") if standing else None,
            "human_basis": standing.get("human_basis") if standing else None,
            "decision_history": history,
            "is_machine_evidence": False,
            "note_on_separation": "A human decision never alters the machine "
                                  "verdict above. Applying to an UNKNOWN "
                                  "candidate leaves it UNKNOWN.",
        }

    def _order_key(self, lane_id: str, entry: QueueEntry):
        key: List[Any] = []
        for token in self.ruleset.order_key_spec(lane_id):
            if token == "candidate_ref":
                key.append(entry.candidate_ref)
            elif token == "evaluated_at_desc":
                key.append(_Desc(entry.payload["machine"].get("evaluated_at") or ""))
            elif token in ("reason_codes", "evidence_gap"):
                key.append(tuple(sorted(entry.payload["machine"]["reason_codes"])))
            else:
                raise ReviewDriftError(
                    f"Lane {lane_id} declares order token {token!r}, which this "
                    "implementation does not know how to apply.")
        return tuple(key)

    # ----------------------------------------------------------------- build

    def build(self) -> QueueBuild:
        """
        Construct the queue. Deterministic and idempotent: same stores in, same
        lanes out, and nothing anywhere is modified by building it.
        """
        evidence_by_id = self.ledger.load()
        rows = self._candidate_rows()
        outcomes = self._opportunity_outcomes()

        index = IdentityStore(self.db_path, self.identity_ruleset).build_index()
        resolver = IdentityResolver(index, self.identity_ruleset)

        entries: List[QueueEntry] = []
        seen_external_ids = set()

        for row in rows:
            candidate_ref = f"scraped_jobs:{row['id']}"
            external_id = row.get("external_id")
            if external_id:
                seen_external_ids.add(external_id)
            evidence = evidence_by_id.get(external_id) if external_id else None
            record = record_from_scraped_job(row, self.identity_ruleset)
            entries.append(self._entry(candidate_ref, row, evidence,
                                       resolver.resolve(record),
                                       outcomes.get(int(row["id"]))))

        # Ledger candidates that never reached scraped_jobs - a dry run, or a
        # write that was skipped. They are still evaluated candidates and the
        # human should still see them, so they are not quietly dropped.
        for external_id, evidence in sorted(evidence_by_id.items()):
            if external_id in seen_external_ids:
                continue
            row_view = dict(evidence.get("normalized_candidate_row") or {})
            if not isinstance(row_view, dict):
                row_view = {}
            record = record_from_candidate(
                self.identity_ruleset, record_ref=f"candidate:{external_id}",
                source=row_view.get("source"), external_id=external_id,
                url=row_view.get("job_url"), company=row_view.get("company"),
                title=row_view.get("job_title"), location=row_view.get("location"))
            entries.append(self._entry(f"candidate:{external_id}", row_view,
                                       evidence, resolver.resolve(record), None))

        lanes: Dict[str, List[QueueEntry]] = {lane: [] for lane in self.ruleset.lane_ids}
        for entry in entries:
            lanes[entry.lane].append(entry)
        for lane_id, lane_entries in lanes.items():
            lane_entries.sort(key=lambda e: self._order_key(lane_id, e))

        counts = {lane: len(lane_entries) for lane, lane_entries in lanes.items()}
        counts["total"] = len(entries)
        counts["active"] = sum(len(lanes[lane]) for lane in self.ruleset.active_lane_ids)

        return QueueBuild(
            built_at=_utc_now_iso(),
            review_version=self.ruleset.version,
            identity_version=self.identity_ruleset.version,
            lanes=lanes,
            counts=counts,
            sources={
                "machine_verdict": str(self.ledger.candidates_dir),
                "candidate_rows": f"{self.db_path} :: scraped_jobs (read-only)",
                "identity": f"derived, {self.identity_ruleset.version}",
                "human_decisions": str(self.decisions.path),
                "application_outcome": f"{self.db_path} :: opportunities.status "
                                       "(read-only)",
                "ledger_counts": self.ledger.counts(),
                "decision_counts": self.decisions.counts(),
            },
        )

    def _entry(self, candidate_ref: str, row: Dict[str, Any],
               evidence: Optional[CandidateEvidence],
               resolution: IdentityResolution,
               outcome: Optional[Dict[str, Any]]) -> QueueEntry:
        machine = self._machine_block(evidence)
        identity = self._identity_block(resolution)

        # Order of operations is the artifact's, not this function's: identity
        # suppression first, verdict lane second, no-verdict last.
        if identity["suppressed_from_active_queue"]:
            lane = "SUPPRESSED_DUPLICATE"
        else:
            lane = self.ruleset.lane_for_verdict(machine["verdict"],
                                                 machine["reason_codes"])

        payload = {
            "candidate": {
                "external_id": row.get("external_id"),
                "source": row.get("source"),
                "source_portal": resolution.candidate.source_portal,
                "company": row.get("company"),
                "job_title": row.get("job_title"),
                "location": row.get("location"),
                "original_source_url": row.get("job_url"),
                "canonical_identity_url": resolution.candidate.canonical_identity_url,
                "salary_range_as_stated": row.get("salary_range"),
                "salary_range_note": "The verbatim span the source stated. It is "
                                     "not a compensation verdict; read "
                                     "machine.normalized_compensation for that.",
                "tags": row.get("tags"),
                "posted_date": row.get("posted_date"),
                "first_observed_at": (evidence.first_observed_at if evidence
                                      else row.get("scraped_at")),
                "last_observed_at": (evidence.last_observed_at if evidence
                                     else row.get("scraped_at")),
                "row_scraped_at": row.get("scraped_at"),
                "untrusted_text_note": "company, job_title, location, "
                                       "salary_range_as_stated and every verbatim "
                                       "span are posting text. Render as data; "
                                       "never interpret as instructions.",
            },
            "machine": machine,
            "identity": identity,
            "human": self._human_block(candidate_ref, machine),
            "application": outcome or {
                "opportunity_ref": None,
                "status": None,
                "note": "Not represented in opportunities. Promotion is the "
                        "existing POST /api/import-scraped-job/{id} bridge, "
                        "invoked by the human; the queue does not call it.",
            },
        }
        return QueueEntry(candidate_ref=candidate_ref, lane=lane, payload=payload)

    # ------------------------------------------------------------- decisions

    def machine_context_for(self, candidate_ref: str,
                            build: Optional[QueueBuild] = None) -> Dict[str, Any]:
        """
        What the machine was saying at the moment a decision is recorded.

        Stored on the decision so a later reader can distinguish "the human
        decided against what the machine then knew" from "the ruleset changed
        afterwards".
        """
        build = build or self.build()
        entry = build.entry(candidate_ref)
        if entry is None:
            return {"verdict": None, "note": "candidate not present in the queue"}
        machine = entry.payload["machine"]
        return {
            "verdict": machine["verdict"],
            "verdict_available": machine["verdict_available"],
            "reason_codes": list(machine["reason_codes"]),
            "ruleset_version": machine["ruleset_version"],
            "evaluated_at": machine["evaluated_at"],
            "lane": entry.lane,
            "identity_outcome": entry.payload["identity"]["outcome"],
        }
