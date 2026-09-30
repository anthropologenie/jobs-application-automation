#!/usr/bin/env python3
"""
Raw-source retention and run-level evidence (P0_IMPLEMENTATION_SPEC.md 7.5)

Everything the specification requires to be answerable about an ingested
candidate is answerable from what this module writes:

    Which source produced it?      source_portal / source_mechanism
    What was the source URL?       source_url (the posting URL as the CLI gave it)
    When was it observed?          source_fetched_at
    What raw payload was received? the file at raw_payload_ref, byte-for-byte
    Which extractor processed it?  extractor_version / normalizer_version
    Which fields were derived?     derived_fields, naming the raw key each came from
    Which gate verdict resulted?   gate_verdict, with reason codes and rules fired

Two disciplines are structural rather than conventional here:

  * Run-scoped paths. Raw payloads are written under the run id, so a later run
    physically cannot overwrite an earlier run's source evidence.
  * Never backfilled. A record written before a provenance field existed simply
    lacks it. Nothing in this module fills a field after the fact.

The store is a filesystem store on purpose. P0_SPEC 7.5 defines raw_payload_ref
as a "pointer to the retained raw record", and a run-scoped path satisfies that
without a schema column - so P0-06 needs no migration (CONFLICT-2 leaves
migration authority with the Repository Owner).

Author: Karthik Shetty
Created: 2026-08-31
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

SOURCE_PORTAL = "linkedin-search"
SOURCE_MECHANISM = "cli"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_run_id(prefix: str = "linkedin") -> str:
    """A sortable, collision-resistant run id. Also the raw-store directory name."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}-{stamp}-{os.getpid()}"


class RawSourceStore:
    """
    Retains verbatim CLI output, one file per invocation.

    Files are never rewritten: a name that already exists gets a numeric
    suffix rather than replacing the earlier capture, because the earlier
    capture is source evidence and losing it is unrecoverable.
    """

    def __init__(self, root: Path, run_id: str):
        self.run_dir = Path(root) / "raw" / SOURCE_PORTAL / run_id
        self.store_root = Path(root)
        self.run_id = run_id

    def _unique_path(self, name: str) -> Path:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        path = self.run_dir / name
        if not path.exists():
            return path
        stem, suffix = path.stem, path.suffix
        n = 2
        while (self.run_dir / f"{stem}.{n}{suffix}").exists():
            n += 1
        return self.run_dir / f"{stem}.{n}{suffix}"

    def write(self, name: str, payload: Dict[str, Any]) -> str:
        """
        Retain one raw capture. Returns the store-relative raw_payload_ref.

        The ref is relative to the store root so it stays valid if the
        repository is moved or the store is archived.
        """
        path = self._unique_path(name)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        return str(path.relative_to(self.store_root))

    def read(self, ref: str) -> Dict[str, Any]:
        with open(self.store_root / ref, "r", encoding="utf-8") as f:
            return json.load(f)


@dataclass
class SourceProvenance:
    """The 7.5 provenance block carried by every ingested record."""
    source_portal: str
    source_mechanism: str
    source_query: Dict[str, Any]
    source_fetched_at: str
    raw_payload_ref: str
    cli_version: Dict[str, Any]
    source_url: Optional[str] = None
    detail_raw_payload_ref: Optional[str] = None
    detail_fetched_at: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        record: Dict[str, Any] = {
            "source_portal": self.source_portal,
            "source_mechanism": self.source_mechanism,
            "source_query": dict(self.source_query),
            "source_fetched_at": self.source_fetched_at,
            "raw_payload_ref": self.raw_payload_ref,
            "cli_version": dict(self.cli_version),
            "source_url": self.source_url,
        }
        # Absent key, not null, when no detail call was made for this posting.
        # Three-state discipline (P0_SPEC 4.4): "this run did not capture it" is
        # a different fact from "the source stated none".
        if self.detail_raw_payload_ref is not None:
            record["detail_raw_payload_ref"] = self.detail_raw_payload_ref
            record["detail_fetched_at"] = self.detail_fetched_at
        return record


class RunLedger:
    """
    Run-level evidence: the counts, the query, the errors, the terminating
    condition, and one candidate record per posting.

    This is the minimum run-level observability P0-06 owes. It is deliberately
    not the P0-10 time-instrumentation system: it records wall-clock start and
    end for the run only, and does not instrument per-stage human time.
    """

    def __init__(self, root: Path, run_id: str):
        self.root = Path(root)
        self.run_id = run_id
        self.runs_dir = self.root / "runs"
        self.candidates_dir = self.root / "candidates"
        self.started_at = utc_now_iso()
        self.finished_at: Optional[str] = None
        self.candidates: List[Dict[str, Any]] = []
        self.errors: List[Dict[str, Any]] = []
        self.terminating_condition: str = "completed"
        self.queries: List[Dict[str, Any]] = []
        self.counts: Dict[str, int] = {
            "returned_by_linkedin": 0,
            "normalized": 0,
            "rejected_unparseable": 0,
            "gate_pass": 0,
            "gate_unknown": 0,
            "gate_fail": 0,
            "persisted": 0,
            "skipped_existing": 0,
            "detail_fetched": 0,
        }

    def record_error(self, stage: str, detail: Dict[str, Any]) -> None:
        """Record an error verbatim. Errors never abort the batch (P0_SPEC 7.4)."""
        self.errors.append({"stage": stage, "at": utc_now_iso(), **detail})

    def record_candidate(self, record: Dict[str, Any]) -> None:
        self.candidates.append(record)

    def flush(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """Write the candidate ledger and the run manifest. Returns their paths."""
        self.finished_at = self.finished_at or utc_now_iso()
        self.candidates_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)

        candidates_path = self.candidates_dir / f"{self.run_id}.jsonl"
        with open(candidates_path, "w", encoding="utf-8") as f:
            for record in self.candidates:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        manifest = {
            "run_id": self.run_id,
            "source_portal": SOURCE_PORTAL,
            "source_mechanism": SOURCE_MECHANISM,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "queries": self.queries,
            "counts": dict(self.counts),
            "terminating_condition": self.terminating_condition,
            "errors": self.errors,
            "candidates_ref": str(candidates_path.relative_to(self.root)),
            **(extra or {}),
        }
        manifest_path = self.runs_dir / f"{self.run_id}.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        return {"manifest": str(manifest_path), "candidates": str(candidates_path)}

    def summary(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "counts": dict(self.counts),
            "terminating_condition": self.terminating_condition,
            "error_count": len(self.errors),
        }
