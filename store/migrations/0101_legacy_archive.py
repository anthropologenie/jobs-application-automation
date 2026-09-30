"""
0101_legacy_archive: mark every pre-v0.2 scraped_jobs row as LEGACY (Phase B §29, OI-034).

Legacy rows are preserved exactly where they are. They are listed here so v2
queue calculations can prove their exclusion; they are never evaluated under
v0.2 and never receive a v2 lane. On a fresh v2 database there is no
scraped_jobs table and the archive is simply empty.
"""

from datetime import datetime, timezone

REASON = "pre-v0.2 legacy row; not re-evaluated under v0.2 (Phase B §29, OI-034)"


def apply(conn) -> None:
    conn.execute("""
        CREATE TABLE legacy_scraped_job (
          scraped_job_id INTEGER PRIMARY KEY,
          external_id TEXT,
          source TEXT,
          archived_at TEXT NOT NULL,
          reason TEXT NOT NULL
        )""")
    conn.execute("""CREATE TRIGGER legacy_scraped_job_no_delete BEFORE DELETE ON legacy_scraped_job
                    BEGIN SELECT RAISE(ABORT, 'legacy archive is append-only'); END""")
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='scraped_jobs'").fetchone()
    if exists:
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO legacy_scraped_job (scraped_job_id, external_id, source, archived_at, reason) "
            "SELECT id, external_id, source, ?, ? FROM scraped_jobs", (now, REASON))
