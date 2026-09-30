"""SQLite migration runner, configurable runtime path, legacy guard, legacy 77-row archive."""

import sqlite3

import pytest

from evaluation.queue import plan_day
from evaluation.service import EvaluationService
from store import repository as repo
from store.db import connect
from store.lock import RunLock, RunLocked
from store.migrate import MigrationError, MigrationRunner, discover, migrate
from store.paths import LEGACY_DB_PATH, LegacyDatabaseRefused, resolve_db_path
from v02_support import BASE_TEXT, EN, no_network, observation  # noqa: F401


def test_runtime_path_is_configurable(monkeypatch, tmp_path):
    monkeypatch.setenv("JOBOPS_DB_PATH", str(tmp_path / "x.db"))
    assert resolve_db_path() == tmp_path / "x.db"
    monkeypatch.delenv("JOBOPS_DB_PATH")
    assert resolve_db_path().name == "jobops.db" and "runtime" in str(resolve_db_path())


def test_legacy_database_is_refused_without_owner_flag():
    with pytest.raises(LegacyDatabaseRefused):
        connect(LEGACY_DB_PATH)
    with pytest.raises(LegacyDatabaseRefused):
        migrate(str(LEGACY_DB_PATH))


def test_migrations_apply_once_record_history_and_backup(tmp_path):
    db = tmp_path / "rt" / "jobops.db"
    first = migrate(str(db), backup_dir=str(tmp_path / "bk"))
    # 0102 (P3): nullable observation.raw_work_mode column.
    assert first["applied"] == ["0100_v2_core.sql", "0101_legacy_archive.py", "0102_observation_work_mode.sql"]
    again = migrate(str(db), backup_dir=str(tmp_path / "bk"))
    assert again["applied"] == []
    conn = sqlite3.connect(db)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 102
    assert [r[0] for r in conn.execute("SELECT version FROM schema_migrations ORDER BY version")] == ["0100", "0101", "0102"]
    assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_checksum_drift_stops_the_runner(tmp_path):
    mig = tmp_path / "m"
    mig.mkdir()
    (mig / "0001_a.sql").write_text("CREATE TABLE a (x INTEGER);\n")
    conn = connect(":memory:")
    MigrationRunner(conn, directory=mig).apply_pending()
    (mig / "0001_a.sql").write_text("CREATE TABLE a (x INTEGER, y INTEGER);\n")
    with pytest.raises(MigrationError):
        MigrationRunner(conn, directory=mig).apply_pending()


def test_failed_migration_rolls_back(tmp_path):
    mig = tmp_path / "m"
    mig.mkdir()
    (mig / "0001_bad.sql").write_text("CREATE TABLE ok_table (x INTEGER);\nTHIS IS NOT SQL;\n")
    conn = connect(":memory:")
    with pytest.raises(sqlite3.Error):
        MigrationRunner(conn, directory=mig).apply_pending()
    assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='ok_table'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 0


def test_pre_migration_backup_is_taken_when_tables_exist(tmp_path):
    db = tmp_path / "legacy_copy.db"
    raw = sqlite3.connect(db)
    raw.execute("CREATE TABLE scraped_jobs (id INTEGER PRIMARY KEY, external_id TEXT, source TEXT)")
    raw.commit()
    raw.close()
    migrate(str(db), backup_dir=str(tmp_path / "bk"))
    assert list((tmp_path / "bk").glob("*.bak"))


def _legacy_scratch_db(tmp_path, rows=77):
    """A synthetic stand-in for the legacy DB shape. The real legacy DB is never opened."""
    db = tmp_path / "scratch_with_legacy.db"
    raw = sqlite3.connect(db)
    raw.execute("CREATE TABLE scraped_jobs (id INTEGER PRIMARY KEY, external_id TEXT UNIQUE, source TEXT, job_title TEXT)")
    raw.executemany("INSERT INTO scraped_jobs VALUES (?,?,?,?)",
                    [(i, f"remoteok:{i}", "RemoteOK", f"Legacy role {i}") for i in range(1, rows + 1)])
    raw.commit()
    raw.close()
    return db


def test_legacy_77_rows_are_archived_not_evaluated_and_excluded_from_lanes(tmp_path):
    db = _legacy_scratch_db(tmp_path)
    migrate(str(db), backup_dir=str(tmp_path / "bk"))
    conn = connect(db)
    assert conn.execute("SELECT COUNT(*) FROM legacy_scraped_job").fetchone()[0] == 77
    assert conn.execute("SELECT COUNT(*) FROM scraped_jobs").fetchone()[0] == 77     # preserved in place
    svc = EvaluationService(conn)
    svc.classify_company("Synthetic Product Co", "PRODUCT", "INFERRED_FROM_EVIDENCE", "machine")
    svc.ingest(observation(source_url="https://boards.greenhouse.io/s/jobs/1", raw_text=BASE_TEXT, language_detection=EN))
    plan = plan_day(svc, "2026-09-21")
    total = sum(len(v) for v in plan["lanes"].values()) + len(plan["review_carried"])
    assert total == 1                                                                 # only the v2 requisition
    assert conn.execute("SELECT COUNT(*) FROM evaluation").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("DELETE FROM legacy_scraped_job")


def test_append_only_and_immutability_triggers():
    conn = connect(":memory:")
    MigrationRunner(conn).apply_pending()
    svc = EvaluationService(conn)
    svc.ingest(observation(raw_text=BASE_TEXT, language_detection=EN))
    for stmt in ("UPDATE evidence SET quoted_span='x'", "DELETE FROM evidence",
                 "UPDATE observation SET raw_text='x'", "DELETE FROM observation",
                 "UPDATE evaluation SET queue_lane='SHORTLIST'", "DELETE FROM evaluation"):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(stmt)


def test_no_fourth_verdict_can_be_stored():
    conn = connect(":memory:")
    MigrationRunner(conn).apply_pending()
    svc = EvaluationService(conn)
    ev = svc.ingest(observation(raw_text=BASE_TEXT, language_detection=EN))["evaluation"]
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO evaluation_dimension VALUES (?, 'extra', 'FLAG', 'X', '[]')", (ev["evaluation_id"],))


def test_human_only_writes():
    conn = connect(":memory:")
    MigrationRunner(conn).apply_pending()
    svc = EvaluationService(conn)
    rid = svc.ingest(observation(raw_text=BASE_TEXT, language_detection=EN))["requisition_id"]
    with pytest.raises(PermissionError):
        repo.record_review_decision(conn, rid, "ACCEPT", actor="machine")
    with pytest.raises(PermissionError):
        repo.record_application_event(conn, rid, "SUBMITTED_BY_HUMAN", actor="machine", event_at="2026-09-21")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO application VALUES ('a1', ?, 'SUBMITTED_BY_HUMAN', 'agent', 'x', 'x', NULL, NULL)", (rid,))


def test_run_lock_is_exclusive(tmp_path):
    with RunLock(tmp_path / "run.lock"):
        with pytest.raises(RunLocked):
            with RunLock(tmp_path / "run.lock"):
                pass
    with RunLock(tmp_path / "run.lock"):
        pass


def test_discover_orders_numerically():
    assert [p.name for p in discover()] == ["0100_v2_core.sql", "0101_legacy_archive.py",
                                            "0102_observation_work_mode.sql"]
