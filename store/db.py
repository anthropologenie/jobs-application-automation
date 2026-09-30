"""Connection factory with the pragmas every v2 connection uses."""

import sqlite3
from pathlib import Path
from typing import Union

from .paths import guard_not_legacy


def connect(path: Union[str, Path], *, allow_legacy: bool = False) -> sqlite3.Connection:
    """
    Open a v2 connection. isolation_level=None: callers manage transactions
    explicitly (BEGIN IMMEDIATE ... COMMIT) so each ingest is atomic.
    """
    target = str(path)
    guard_not_legacy(Path(target) if target != ":memory:" else target, allow_legacy)
    if target != ":memory:":
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target, isolation_level=None, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    if target != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    return conn
