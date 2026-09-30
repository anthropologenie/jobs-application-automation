#!/usr/bin/env python3
"""
JobOps v2 migration runner.

    python3 -m store.migrate --status              # default: $JOBOPS_DB_PATH or data/runtime/jobops.db
    python3 -m store.migrate --apply
    python3 -m store.migrate --db /path/to.db --apply

Migrations live in store/migrations as NNNN_description.sql or .py (with an
apply(conn) function), applied in numeric order. Each one:

  1. is checksummed; a recorded migration whose file changed stops the runner;
  2. is preceded by a backup-API copy when the database already has tables;
  3. runs inside BEGIN IMMEDIATE ... COMMIT together with its history row;
  4. is followed by PRAGMA integrity_check and foreign_key_check.

Forward-only: recovery is restoring the pre-migration backup. The legacy v0.1
database (data/jobs-tracker.db) is refused unless --allow-legacy-db is passed
by the owner.
"""

import argparse
import hashlib
import importlib.util
import json
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from store.backup import backup_database  # noqa: E402
from store.db import connect  # noqa: E402
from store.paths import resolve_backup_dir, resolve_db_path  # noqa: E402

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

HISTORY_DDL = """CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY, filename TEXT NOT NULL, sha256 TEXT NOT NULL,
  applied_at TEXT NOT NULL, applied_by TEXT NOT NULL, duration_ms INTEGER NOT NULL,
  backup_ref TEXT)"""


class MigrationError(RuntimeError):
    pass


def discover(directory: Path = MIGRATIONS_DIR) -> List[Path]:
    files = [p for p in directory.iterdir()
             if p.suffix in (".sql", ".py") and p.name[:4].isdigit() and p.name[4] == "_"]
    versions = [p.name[:4] for p in files]
    if len(versions) != len(set(versions)):
        raise MigrationError(f"duplicate migration numbers in {directory}")
    return sorted(files, key=lambda p: p.name)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class MigrationRunner:
    def __init__(self, conn: sqlite3.Connection, *, db_label: str = "jobops",
                 backup_dir: Optional[Path] = None, applied_by: str = "store.migrate",
                 directory: Path = MIGRATIONS_DIR):
        self.conn = conn
        self.db_label = db_label
        self.backup_dir = backup_dir
        self.applied_by = applied_by
        self.directory = directory
        conn.execute(HISTORY_DDL)

    def applied(self) -> Dict[str, Dict[str, str]]:
        rows = self.conn.execute("SELECT version, filename, sha256 FROM schema_migrations").fetchall()
        return {r["version"]: {"filename": r["filename"], "sha256": r["sha256"]} for r in rows}

    def status(self) -> List[Dict[str, str]]:
        done = self.applied()
        out = []
        for path in discover(self.directory):
            v = path.name[:4]
            state = "pending"
            if v in done:
                state = "applied" if done[v]["sha256"] == _sha(path) else "CHECKSUM_MISMATCH"
            out.append({"version": v, "file": path.name, "state": state})
        return out

    def _has_user_tables(self) -> bool:
        row = self.conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' "
                                "AND name NOT IN ('schema_migrations') AND name NOT LIKE 'sqlite_%'").fetchone()
        return row[0] > 0

    def apply_pending(self) -> List[str]:
        done = self.applied()
        applied_now = []
        for path in discover(self.directory):
            v = path.name[:4]
            sha = _sha(path)
            if v in done:
                if done[v]["sha256"] != sha:
                    raise MigrationError(f"migration {path.name} changed after it was applied")
                continue
            backup_ref = None
            if self.backup_dir and self._has_user_tables():
                backup_ref = str(backup_database(self.conn, self.db_label, self.backup_dir, f"pre-{v}"))
            started = time.monotonic()
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                if path.suffix == ".sql":
                    for statement in _statements(path.read_text(encoding="utf-8")):
                        self.conn.execute(statement)
                else:
                    spec = importlib.util.spec_from_file_location(f"jobops_migration_{v}", path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    module.apply(self.conn)
                self.conn.execute(
                    "INSERT INTO schema_migrations VALUES (?,?,?,?,?,?,?)",
                    (v, path.name, sha, datetime.now(timezone.utc).isoformat(), self.applied_by,
                     int((time.monotonic() - started) * 1000), backup_ref))
                self.conn.execute(f"PRAGMA user_version = {int(v)}")
                self.conn.execute("COMMIT")
            except Exception:
                self.conn.execute("ROLLBACK")
                raise
            self.check_integrity()
            applied_now.append(path.name)
        return applied_now

    def check_integrity(self) -> None:
        ok = self.conn.execute("PRAGMA integrity_check").fetchone()[0]
        if ok != "ok":
            raise MigrationError(f"integrity_check failed: {ok}")
        bad = self.conn.execute("PRAGMA foreign_key_check").fetchall()
        if bad:
            raise MigrationError(f"foreign_key_check failed: {[tuple(r) for r in bad]}")


def _statements(sql: str) -> List[str]:
    """Split a script on statement boundaries, keeping CREATE TRIGGER bodies whole."""
    out, buf = [], []
    for line in sql.splitlines():
        stripped = line.strip()
        if not buf and (not stripped or stripped.startswith("--")):
            continue
        buf.append(line)
        candidate = "\n".join(buf)
        if sqlite3.complete_statement(candidate):
            out.append(candidate.strip())
            buf = []
    if "\n".join(buf).strip():
        raise MigrationError("unterminated SQL statement in migration")
    return out


def migrate(db_path: Optional[str] = None, *, allow_legacy: bool = False,
            backup_dir: Optional[str] = None) -> Dict[str, object]:
    path = resolve_db_path(db_path)
    conn = connect(path, allow_legacy=allow_legacy)
    try:
        runner = MigrationRunner(conn, db_label=Path(path).stem,
                                 backup_dir=resolve_backup_dir(backup_dir))
        applied = runner.apply_pending()
        return {"db": str(path), "applied": applied, "status": runner.status()}
    finally:
        conn.close()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="JobOps v2 migration runner")
    parser.add_argument("--db")
    parser.add_argument("--backup-dir")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--allow-legacy-db", action="store_true",
                        help="Owner-only: permit operating on data/jobs-tracker.db")
    args = parser.parse_args(argv)
    if args.apply:
        print(json.dumps(migrate(args.db, allow_legacy=args.allow_legacy_db,
                                 backup_dir=args.backup_dir), indent=2))
        return 0
    path = resolve_db_path(args.db)
    conn = connect(path, allow_legacy=args.allow_legacy_db)
    try:
        print(json.dumps({"db": str(path), "status": MigrationRunner(conn).status()}, indent=2))
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
