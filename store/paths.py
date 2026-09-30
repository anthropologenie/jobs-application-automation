"""Runtime path resolution. One place decides where the database lives."""

import os
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RUNTIME_DB = REPO_ROOT / "data" / "runtime" / "jobops.db"
DEFAULT_BACKUP_DIR = REPO_ROOT / "data" / "runtime" / "backups"
LEGACY_DB_PATH = REPO_ROOT / "data" / "jobs-tracker.db"
ENV_DB = "JOBOPS_DB_PATH"
ENV_BACKUP = "JOBOPS_BACKUP_DIR"


class LegacyDatabaseRefused(RuntimeError):
    """The v2 store refuses to open the legacy runtime DB without explicit owner intent."""


def resolve_db_path(explicit: Optional[str] = None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get(ENV_DB)
    return Path(env).expanduser() if env else DEFAULT_RUNTIME_DB


def resolve_backup_dir(explicit: Optional[str] = None) -> Path:
    if explicit:
        return Path(explicit).expanduser()
    env = os.environ.get(ENV_BACKUP)
    return Path(env).expanduser() if env else DEFAULT_BACKUP_DIR


def guard_not_legacy(path: Path, allow_legacy: bool = False) -> None:
    if str(path) == ":memory:":
        return
    try:
        same = Path(path).resolve() == LEGACY_DB_PATH.resolve()
    except OSError:
        same = False
    if same and not allow_legacy:
        raise LegacyDatabaseRefused(
            f"{path} is the legacy v0.1 database. The v2 store does not open it "
            "unless the owner passes allow_legacy=True / --allow-legacy-db.")
