"""
SQLite persistence for JobOps v2: configurable runtime path, migration runner,
backups, run lock and repository functions.

The runtime database lives outside Git tracking (default data/runtime/jobops.db,
overridable with JOBOPS_DB_PATH). The legacy v0.1 database data/jobs-tracker.db
is never opened by this package unless an explicit allow_legacy flag is passed
by an owner command.
"""

from .paths import LEGACY_DB_PATH, LegacyDatabaseRefused, resolve_db_path  # noqa: F401
