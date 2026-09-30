"""Consistent SQLite backups (backup API) with rotation."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional


def backup_database(conn: sqlite3.Connection, db_name: str, dest_dir: Path, label: str,
                    keep: int = 5) -> Optional[Path]:
    """Copy the live connection's database; keep the newest `keep` files for this label."""
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    target = dest_dir / f"{db_name}.{label}.{stamp}.bak"
    dest = sqlite3.connect(str(target))
    try:
        conn.backup(dest)
        ok = dest.execute("PRAGMA integrity_check").fetchone()[0]
        if ok != "ok":
            raise RuntimeError(f"backup integrity_check failed: {ok}")
    finally:
        dest.close()
    rotate(dest_dir, f"{db_name}.{label}.", keep)
    return target


def rotate(dest_dir: Path, prefix: str, keep: int) -> List[Path]:
    files = sorted(p for p in Path(dest_dir).glob(prefix + "*.bak"))
    removed = files[:-keep] if keep > 0 else []
    for p in removed:
        p.unlink()
    return removed
