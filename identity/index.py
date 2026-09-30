#!/usr/bin/env python3
"""
The identity index - what a candidate is matched against

Two pieces:

    IdentityIndex   an in-memory, layer-keyed view over IdentityRecords
    IdentityStore   builds one by READING scraped_jobs and opportunities

Read-only by construction
-------------------------
IdentityStore opens SQLite in read-only mode (`file:...?mode=ro`). That is not
a convention that a later edit could quietly drop - the connection itself
rejects a write, so no code path through this package can delete a job, merge a
row, change an application status, rewrite a gate verdict or "clean up" an
apparent duplicate. P0-07 detects, classifies and reports; repairing historical
data is a separate concern with its own authorization.

Both tables are in scope because P0_IMPLEMENTATION_SPEC.md 8.4 requires it: a
candidate must be recognized against an existing opportunities row - applied,
rejected and archived rows included - or the system re-surfaces work already
done.

Author: Karthik Shetty
Created: 2026-09-02
"""

import logging
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .records import (
    IdentityRecord,
    record_from_opportunity,
    record_from_scraped_job,
)
from .ruleset import IdentityRuleset, load_identity_ruleset

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "jobs-tracker.db"

# The columns the index reads. Every scorer-owned and every decision-owned
# column is absent on purpose: match_score, classification, recommendation,
# status, applied_date, notes and priority are neither read nor readable here.
_SCRAPED_JOB_COLUMNS = (
    "id", "external_id", "source", "job_title", "company", "job_url", "location",
    "scraped_at")
_OPPORTUNITY_COLUMNS = ("id", "company", "role", "job_url", "source",
                        "discovered_date")


class IdentityIndexError(RuntimeError):
    """Raised when the index cannot be built from the database as it stands."""


class IdentityIndex:
    """
    Layer-keyed lookup over a set of IdentityRecords.

    Buckets are lists, not single records: the same canonical URL legitimately
    appears on more than one row today, and collapsing them here would hide
    exactly the historical duplication P0-07 is supposed to report.
    """

    def __init__(self, records: Optional[Iterable[IdentityRecord]] = None):
        self.records: List[IdentityRecord] = []
        self._by_l1: Dict[Any, List[IdentityRecord]] = defaultdict(list)
        self._by_l2: Dict[Any, List[IdentityRecord]] = defaultdict(list)
        self._by_l3: Dict[Any, List[IdentityRecord]] = defaultdict(list)
        self._by_l4: Dict[Any, List[IdentityRecord]] = defaultdict(list)
        self._by_company_title: Dict[Any, List[IdentityRecord]] = defaultdict(list)
        self._refs: set = set()
        for record in records or ():
            self.add(record)

    def add(self, record: IdentityRecord) -> None:
        if record.record_ref in self._refs:
            return
        self._refs.add(record.record_ref)
        self.records.append(record)
        if record.l1_key:
            self._by_l1[record.l1_key].append(record)
        if record.l2_key:
            self._by_l2[record.l2_key].append(record)
        if record.l3_key:
            self._by_l3[record.l3_key].append(record)
        if record.l4_key:
            self._by_l4[record.l4_key].append(record)
        if record.normalized_company and record.normalized_title:
            self._by_company_title[
                (record.normalized_company, record.normalized_title)].append(record)

    def extend(self, records: Iterable[IdentityRecord]) -> None:
        for record in records:
            self.add(record)

    # Lookups return record_ref-sorted lists so a resolution is deterministic
    # regardless of the order rows came back from the database.
    @staticmethod
    def _sorted(found: List[IdentityRecord]) -> List[IdentityRecord]:
        return sorted(found, key=lambda r: r.record_ref)

    def by_l1(self, key) -> List[IdentityRecord]:
        return self._sorted(self._by_l1.get(key, [])) if key else []

    def by_l2(self, key) -> List[IdentityRecord]:
        return self._sorted(self._by_l2.get(key, [])) if key else []

    def by_l3(self, key) -> List[IdentityRecord]:
        return self._sorted(self._by_l3.get(key, [])) if key else []

    def by_l4(self, key) -> List[IdentityRecord]:
        return self._sorted(self._by_l4.get(key, [])) if key else []

    def by_company_title(self, company, title) -> List[IdentityRecord]:
        if not company or not title:
            return []
        return self._sorted(self._by_company_title.get((company, title), []))

    def __len__(self) -> int:
        return len(self.records)

    def counts(self) -> Dict[str, int]:
        by_kind: Dict[str, int] = defaultdict(int)
        for record in self.records:
            by_kind[record.record_kind] += 1
        return {"total": len(self.records), **dict(by_kind)}


class IdentityStore:
    """Builds an IdentityIndex from scraped_jobs and opportunities, read-only."""

    def __init__(self, db_path: Optional[Path] = None,
                 ruleset: Optional[IdentityRuleset] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        if not self.db_path.exists():
            raise IdentityIndexError(f"Database not found: {self.db_path}")
        self.ruleset = ruleset or load_identity_ruleset()
        if not self.ruleset.scope_is_read_only:
            raise IdentityIndexError(
                "The identity artifact no longer declares match_scope.read_only. "
                "This implementation only ever reads; the artifact and the code "
                "must agree before either changes.")

    def _connect(self) -> sqlite3.Connection:
        """
        Open the database read-only.

        `mode=ro` is enforced by SQLite, so an INSERT, UPDATE or DELETE reached
        through this connection raises rather than executing. No historical row
        can be altered by anything downstream of here.
        """
        conn = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def row_counts(self) -> Dict[str, int]:
        with self._connect() as conn:
            return {
                "scraped_jobs": conn.execute(
                    "SELECT COUNT(*) FROM scraped_jobs").fetchone()[0],
                "opportunities": conn.execute(
                    "SELECT COUNT(*) FROM opportunities").fetchone()[0],
            }

    def load_records(self) -> List[IdentityRecord]:
        scraped_columns = ", ".join(_SCRAPED_JOB_COLUMNS)
        opportunity_columns = ", ".join(_OPPORTUNITY_COLUMNS)
        records: List[IdentityRecord] = []
        with self._connect() as conn:
            for row in conn.execute(
                    f"SELECT {scraped_columns} FROM scraped_jobs ORDER BY id"):
                records.append(record_from_scraped_job(dict(row), self.ruleset))
            for row in conn.execute(
                    f"SELECT {opportunity_columns} FROM opportunities ORDER BY id"):
                records.append(record_from_opportunity(dict(row), self.ruleset))
        return records

    def build_index(self) -> IdentityIndex:
        return IdentityIndex(self.load_records())
