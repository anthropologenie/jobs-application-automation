#!/usr/bin/env python3
"""
The human decision ledger - the one thing P0-08 persists

Why a separate, append-only file store
--------------------------------------
Three reasons, in order of importance.

1. A human decision must never be mistakable for a machine verdict. Keeping
   them in physically separate stores makes that structural rather than
   conventional: nothing in this module can reach the gate's verdict, and
   nothing that reads a verdict can reach a decision by accident.

2. It requires no schema change. `scraped_jobs` has no decision column and
   adding one is a migration; CONFLICT-2 leaves migration authority with the
   Repository Owner, and P0-08 does not need it. This store follows the
   precedent P0-06 set and P0_SPEC 7.5 sanctioned - a run-scoped/append-only
   path under data/ - so the queue ships with zero database writes.

3. Append-only means a decision is never lost. A reversal is a NEW record
   naming the one it supersedes. What the human thought on Tuesday is still
   readable on Friday, which is the whole point of recording it.

What a decision may NOT do
--------------------------
It cannot change a verdict. It cannot make an UNKNOWN eligible for scoring. It
cannot become machine evidence. A RESOLVE_UNKNOWN records what the human
asserts and the basis they stated for it, clearly labelled as a human
assertion, alongside - never on top of - the machine's UNKNOWN and the reason
codes that produced it.

Nothing here submits an application, contacts anyone, or sends any message.

Author: Karthik Shetty
Created: 2026-09-02
"""

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .ruleset import ReviewDriftError, ReviewRuleset, load_review_ruleset

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DECISION_ROOT = REPO_ROOT / "data" / "review"

ACTOR_HUMAN = "human"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DecisionError(RuntimeError):
    """Raised when a decision cannot be recorded as declared."""


@dataclass(frozen=True)
class Decision:
    """One human decision, exactly as it will be appended."""
    candidate_ref: str
    kind: str
    decided_at: str
    actor: str = ACTOR_HUMAN
    note: Optional[str] = None
    supersedes: Optional[str] = None
    dimension: Optional[str] = None
    human_assertion: Optional[str] = None
    human_basis: Optional[str] = None
    related_record_ref: Optional[str] = None
    machine_context: Dict[str, Any] = field(default_factory=dict)
    decision_id: Optional[str] = None

    def payload(self) -> Dict[str, Any]:
        record: Dict[str, Any] = {
            "decision_id": self.decision_id,
            "candidate_ref": self.candidate_ref,
            "kind": self.kind,
            "decided_at": self.decided_at,
            "actor": self.actor,
            "note": self.note,
            "machine_context": dict(self.machine_context),
            # Stated on every record so no reader has to infer it, and so a
            # grep of this file can never be mistaken for evidence of an
            # automated action.
            "asserted_by": "human",
            "is_machine_evidence": False,
            "submitted_application": False,
            "contacted_anyone": False,
        }
        for key in ("supersedes", "dimension", "human_assertion", "human_basis",
                    "related_record_ref"):
            value = getattr(self, key)
            if value is not None:
                record[key] = value
        return record


class DecisionStore:
    """Append-only JSONL store of human review decisions."""

    def __init__(self, root: Optional[Path] = None,
                 ruleset: Optional[ReviewRuleset] = None):
        self.root = Path(root) if root else DEFAULT_DECISION_ROOT
        self.path = self.root / "decisions.jsonl"
        self.ruleset = ruleset or load_review_ruleset()

    # ------------------------------------------------------------------ read

    def load(self) -> List[Dict[str, Any]]:
        """Every decision ever recorded, in the order it was recorded."""
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
                    raise DecisionError(
                        f"{self.path}:{line_number} is not valid JSON: {exc}") from exc
        return records

    def by_candidate(self) -> Dict[str, List[Dict[str, Any]]]:
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for record in self.load():
            grouped.setdefault(record["candidate_ref"], []).append(record)
        return grouped

    def current_for(self, candidate_ref: str) -> Optional[Dict[str, Any]]:
        """
        The decision standing for a candidate right now.

        The latest record that nothing later supersedes. Superseded records are
        not deleted and stay visible in history.
        """
        records = self.by_candidate().get(candidate_ref, [])
        superseded = {r["supersedes"] for r in records if r.get("supersedes")}
        standing = [r for r in records if r["decision_id"] not in superseded]
        return standing[-1] if standing else None

    def history_for(self, candidate_ref: str) -> List[Dict[str, Any]]:
        return list(self.by_candidate().get(candidate_ref, []))

    # ----------------------------------------------------------------- write

    def _next_id(self, record: Dict[str, Any], position: int) -> str:
        """
        A content-and-position derived id.

        Deterministic, so replaying the same decisions into an empty store
        yields the same ids, and collision-resistant enough to reference from a
        superseding record.
        """
        material = json.dumps(
            {k: v for k, v in record.items() if k != "decision_id"},
            sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(f"{position}:{material}".encode("utf-8")).hexdigest()
        return f"dec-{position:06d}-{digest[:12]}"

    def _validate(self, decision: Decision) -> None:
        kind = self.ruleset.decision_kind(decision.kind)   # drift if unknown

        if kind.get("submits_anything"):
            raise DecisionError(
                f"Decision kind {decision.kind!r} is declared as submitting "
                "something. P0-08 implements no submission of any kind.")

        missing = []
        for required in self.ruleset.required_fields(decision.kind):
            if not getattr(decision, required, None):
                missing.append(required)
        if missing:
            raise DecisionError(
                f"{decision.kind} requires {missing}; the artifact declares them "
                "so a decision cannot be recorded without the context that "
                "makes it meaningful later.")

        if not decision.candidate_ref:
            raise DecisionError("A decision must name the candidate it is about.")

        if decision.supersedes:
            known = {r["decision_id"] for r in self.load()}
            if decision.supersedes not in known:
                raise DecisionError(
                    f"Cannot supersede unknown decision {decision.supersedes!r}.")

    def record(self, decision: Decision) -> Dict[str, Any]:
        """
        Append one decision. Never edits, never deletes, never reorders.

        The file is opened in append mode and one line is written, so a partial
        failure cannot corrupt an earlier decision.
        """
        self._validate(decision)
        existing = self.load()
        payload = decision.payload()
        payload["decision_id"] = self._next_id(payload, len(existing))

        self.root.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        logger.info("Recorded %s for %s", payload["kind"], payload["candidate_ref"])
        return payload

    def counts(self) -> Dict[str, int]:
        records = self.load()
        by_kind: Dict[str, int] = {}
        for record in records:
            by_kind[record["kind"]] = by_kind.get(record["kind"], 0) + 1
        return {"total": len(records), **by_kind}
