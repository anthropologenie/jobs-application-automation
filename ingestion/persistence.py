#!/usr/bin/env python3
"""
Candidate persistence - writes to scraped_jobs, and nothing else

The write path is the one the repository already uses for scraped candidates:
`INSERT OR IGNORE INTO scraped_jobs (...)`, the same contract
scrapers/remoteok_integration.py uses. No new table, no new column, no
migration, and no mutation of any other table (CONFLICT-2 leaves migration
authority with the Repository Owner; migration 004 stays out of scope).

Duplicate behaviour comes from that existing contract and nothing more:
scraped_jobs.external_id is UNIQUE, LinkedIn ids are namespaced into it as
`linkedin:<id>`, and INSERT OR IGNORE therefore makes a re-run of the same
bounded query insert zero additional rows.

That is an identity check, not a deduplication system. P0-07 owns the rest -
see the module docstring of ingestion/pipeline.py for the exact boundary.

Author: Karthik Shetty
Created: 2026-08-31
"""

import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "data" / "jobs-tracker.db"

# Columns this pipeline writes. Every scorer-owned column - match_score,
# classification, matched_skills, matched_domains, red_flags, recommendation -
# is deliberately absent: P0-06 does not score, and writing a placeholder into
# a scoring column would make an unscored candidate indistinguishable from a
# scored one.
_INSERT_COLUMNS = (
    "external_id", "source", "job_title", "company", "job_url",
    "location", "description", "tags", "salary_range", "posted_date",
)


class PersistenceError(RuntimeError):
    """Raised when the database is not in a state this pipeline may write to."""


@dataclass
class CandidateRow:
    """One scraped_jobs row, exactly as it will be written."""
    external_id: str
    source: str
    job_title: str
    company: str
    job_url: str
    location: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None
    salary_range: Optional[str] = None
    posted_date: Optional[str] = None

    def values(self) -> tuple:
        return tuple(getattr(self, column) for column in _INSERT_COLUMNS)

    def as_dict(self) -> Dict[str, Any]:
        return {column: getattr(self, column) for column in _INSERT_COLUMNS}


class CandidateStore:
    """Read/write access to scraped_jobs for the LinkedIn ingestion pipeline."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        if not self.db_path.exists():
            raise PersistenceError(f"Database not found: {self.db_path}")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # ------------------------------------------------------------- inspection

    def verify_schema(self) -> None:
        """
        Confirm the table and every column this pipeline writes already exist.

        A missing column is reported, never created: adding one is a migration,
        and migrations are the Repository Owner's authority (CONFLICT-2).
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='scraped_jobs'"
            ).fetchone()
            if row is None:
                raise PersistenceError(
                    "Table scraped_jobs does not exist. P0-06 creates no tables.")
            existing = {r["name"] for r in conn.execute("PRAGMA table_info(scraped_jobs)")}
        missing = [c for c in _INSERT_COLUMNS if c not in existing]
        if missing:
            raise PersistenceError(
                f"scraped_jobs is missing columns {missing}. P0-06 applies no "
                "migration - report this as a dependency instead.")

    def row_counts(self) -> Dict[str, int]:
        """Pre-run / post-run row counts, for the run summary's audit trail."""
        with self._connect() as conn:
            return {
                "scraped_jobs": conn.execute(
                    "SELECT COUNT(*) FROM scraped_jobs").fetchone()[0],
                "scraped_jobs_linkedin": conn.execute(
                    "SELECT COUNT(*) FROM scraped_jobs WHERE source = 'LinkedIn'"
                ).fetchone()[0],
                "opportunities": conn.execute(
                    "SELECT COUNT(*) FROM opportunities").fetchone()[0],
            }

    def existing_external_ids(self, external_ids: List[str]) -> set:
        """
        Which of these ids scraped_jobs already holds.

        This is the L1 identity check the existing import contract already
        provides. It is used to avoid re-fetching detail for a posting already
        held, and to report skipped_existing honestly.
        """
        if not external_ids:
            return set()
        with self._connect() as conn:
            placeholders = ",".join("?" for _ in external_ids)
            rows = conn.execute(
                f"SELECT external_id FROM scraped_jobs WHERE external_id IN ({placeholders})",
                external_ids).fetchall()
        return {r["external_id"] for r in rows}

    # ---------------------------------------------------------------- backup

    def backup(self, label: str = "pre-p0-06") -> Path:
        """
        Take a consistent copy before writing, using sqlite's own backup API.

        Matches the procedure the repository already followed before migration
        005 (data/jobs-tracker.db.backup-pre005-sqlite-*): a live-safe copy
        rather than a file copy, so WAL contents are included without the WAL
        being checkpointed or otherwise touched.
        """
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        target = self.db_path.with_name(f"{self.db_path.name}.backup-{label}-{stamp}")
        source = self._connect()
        try:
            destination = sqlite3.connect(str(target))
            try:
                source.backup(destination)
            finally:
                destination.close()
        finally:
            source.close()
        logger.info("Database backup written: %s", target)
        return target

    # ----------------------------------------------------------------- write

    def insert_candidates(self, rows: List[CandidateRow]) -> Dict[str, Any]:
        """
        Insert candidates under the existing INSERT OR IGNORE identity contract.

        Returns which external_ids were inserted and which were already held.
        The distinction is derived from the ids present before the write, not
        from rowcount arithmetic, so it stays correct if two rows in the same
        batch carry the same id.
        """
        if not rows:
            return {"inserted": [], "skipped_existing": [], "inserted_count": 0,
                    "skipped_count": 0}

        ids = [r.external_id for r in rows]
        already_present = self.existing_external_ids(ids)

        columns = ", ".join(_INSERT_COLUMNS)
        placeholders = ", ".join("?" for _ in _INSERT_COLUMNS)
        statement = (f"INSERT OR IGNORE INTO scraped_jobs ({columns}) "
                     f"VALUES ({placeholders})")

        conn = self._connect()
        try:
            with conn:
                conn.executemany(statement, [r.values() for r in rows])
        finally:
            conn.close()

        inserted = [i for i in ids if i not in already_present]
        skipped = [i for i in ids if i in already_present]
        return {
            "inserted": inserted,
            "skipped_existing": skipped,
            "inserted_count": len(inserted),
            "skipped_count": len(skipped),
        }

    def fetch_by_external_ids(self, external_ids: List[str]) -> List[sqlite3.Row]:
        if not external_ids:
            return []
        with self._connect() as conn:
            placeholders = ",".join("?" for _ in external_ids)
            return conn.execute(
                f"SELECT * FROM scraped_jobs WHERE external_id IN ({placeholders})",
                external_ids).fetchall()
