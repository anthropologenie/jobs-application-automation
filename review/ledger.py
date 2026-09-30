#!/usr/bin/env python3
"""
Reading the machine verdict - the candidate ledger is the source of truth

Where the verdict actually lives
--------------------------------
Not in the database. `scraped_jobs` has no verdict, reason-code, evidence or
provenance column, and P0-06 deliberately added none: P0_IMPLEMENTATION_SPEC.md
7.5 defines `raw_payload_ref` as "a pointer to the retained raw record" and
takes a run-scoped file path as satisfying it, so ingestion needed no migration
and CONFLICT-2 left migration authority with the Repository Owner.

So the authoritative, durable record of what the gate decided is:

    data/ingestion/candidates/<run_id>.jsonl     one JSON object per candidate
    data/ingestion/runs/<run_id>.json            the run manifest
    data/ingestion/raw/<portal>/<run_id>/*.json  the verbatim source payloads

Those files are append-only and run-scoped. A later run physically cannot
overwrite an earlier run's evidence, which is what makes them a reproducible
source of truth rather than a log.

This module READS them. It writes nothing, anywhere.

Re-evaluation, not rewriting
----------------------------
P0_SPEC 5.3 makes a surfaced verdict immutable against later ruleset changes: a
re-evaluation produces a NEW record and does not rewrite the old one. So a
candidate seen in several runs has several verdict records. The queue presents
the most recent as current and keeps the earlier ones as `verdict_history`,
because "the ruleset changed and the answer changed" is exactly the fact a
later reviewer needs and exactly the fact an overwrite would destroy.

Three-state discipline
----------------------
A key absent from a ledger record means that run did not capture it - not that
the source stated nothing. Records written before the P0-07 D1 fix carry no
`field_provenance` key at all, and this module reports that as "not captured"
rather than manufacturing an empty one.

Author: Karthik Shetty
Created: 2026-09-02
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LEDGER_ROOT = REPO_ROOT / "data" / "ingestion"

# A value the ledger never captured. Distinct from None, which means the source
# stated none (P0_SPEC 4.4). Rendered as a string so it survives JSON.
NOT_CAPTURED = "NOT_CAPTURED"


class LedgerError(RuntimeError):
    """Raised when the evidence store cannot be read as the queue expects."""


@dataclass(frozen=True)
class LedgerObservation:
    """One candidate record from one run - one observation of one posting."""
    run_id: str
    record: Dict[str, Any]
    ledger_path: str

    @property
    def external_id(self) -> Optional[str]:
        return self.record.get("external_id") or self.record.get("candidate_id")

    @property
    def gate_verdict(self) -> Optional[Dict[str, Any]]:
        verdict = self.record.get("gate_verdict")
        return verdict if isinstance(verdict, dict) else None

    @property
    def evaluated_at(self) -> Optional[str]:
        verdict = self.gate_verdict
        return verdict.get("evaluated_at") if verdict else None

    @property
    def source_fetched_at(self) -> Optional[str]:
        provenance = self.record.get("provenance") or {}
        return provenance.get("source_fetched_at")

    def sort_key(self) -> tuple:
        """Runs are ordered by observation time, then by run id for stability."""
        return (self.source_fetched_at or "", self.evaluated_at or "", self.run_id)


@dataclass(frozen=True)
class CandidateEvidence:
    """
    Everything the machine recorded about one posting, across every run.

    `current` is the most recent observation. `history` is every earlier one,
    oldest first, retained rather than collapsed.
    """
    external_id: str
    observations: List[LedgerObservation]

    @property
    def current(self) -> LedgerObservation:
        return self.observations[-1]

    @property
    def history(self) -> List[LedgerObservation]:
        return self.observations[:-1]

    @property
    def first_observed_at(self) -> Optional[str]:
        for observation in self.observations:
            if observation.source_fetched_at:
                return observation.source_fetched_at
        return None

    @property
    def last_observed_at(self) -> Optional[str]:
        for observation in reversed(self.observations):
            if observation.source_fetched_at:
                return observation.source_fetched_at
        return None

    @property
    def run_ids(self) -> List[str]:
        return [observation.run_id for observation in self.observations]

    def get(self, key: str, default: Any = NOT_CAPTURED) -> Any:
        """
        Read a top-level field from the current observation.

        Defaults to NOT_CAPTURED rather than None, so "this run did not record
        it" stays distinguishable from "the source stated none".
        """
        record = self.current.record
        return record[key] if key in record else default

    @property
    def verdict_history(self) -> List[Dict[str, Any]]:
        """Every earlier verdict, retained. P0_SPEC 5.3: never rewritten."""
        history = []
        for observation in self.history:
            verdict = observation.gate_verdict
            if verdict:
                history.append({
                    "run_id": observation.run_id,
                    "verdict": verdict.get("verdict"),
                    "ruleset_version": verdict.get("ruleset_version"),
                    "evaluated_at": verdict.get("evaluated_at"),
                    "reason_codes": list(verdict.get("reason_codes") or ()),
                })
        return history


class CandidateLedgerStore:
    """Read-only access to the ingestion evidence store."""

    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root else DEFAULT_LEDGER_ROOT
        self.candidates_dir = self.root / "candidates"
        self.runs_dir = self.root / "runs"

    def ledger_paths(self) -> List[Path]:
        if not self.candidates_dir.exists():
            return []
        return sorted(self.candidates_dir.glob("*.jsonl"))

    def _iter_observations(self) -> Iterator[LedgerObservation]:
        for path in self.ledger_paths():
            run_id = path.stem
            with open(path, "r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, 1):
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as exc:
                        # Reported, never skipped silently: an unreadable line
                        # is missing evidence, and missing evidence that nobody
                        # is told about is the failure mode this whole store
                        # exists to prevent.
                        raise LedgerError(
                            f"{path}:{line_number} is not valid JSON: {exc}") from exc
                    yield LedgerObservation(run_id=run_id, record=record,
                                            ledger_path=str(path))

    def load(self) -> Dict[str, CandidateEvidence]:
        """Group every observation by external id, oldest run first."""
        grouped: Dict[str, List[LedgerObservation]] = {}
        for observation in self._iter_observations():
            external_id = observation.external_id
            if not external_id:
                raise LedgerError(
                    f"A ledger record in run {observation.run_id} carries no "
                    "external_id or candidate_id and cannot be keyed.")
            grouped.setdefault(external_id, []).append(observation)

        return {
            external_id: CandidateEvidence(
                external_id=external_id,
                observations=sorted(observations, key=lambda o: o.sort_key()))
            for external_id, observations in grouped.items()
        }

    def run_manifests(self) -> List[Dict[str, Any]]:
        if not self.runs_dir.exists():
            return []
        manifests = []
        for path in sorted(self.runs_dir.glob("*.json")):
            with open(path, "r", encoding="utf-8") as handle:
                manifests.append(json.load(handle))
        return manifests

    def counts(self) -> Dict[str, int]:
        evidence = self.load()
        return {
            "ledger_files": len(self.ledger_paths()),
            "candidates": len(evidence),
            "observations": sum(len(e.observations) for e in evidence.values()),
        }
