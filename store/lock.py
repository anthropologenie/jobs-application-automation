"""Exclusive run lock (fcntl.flock). A second holder gets RunLocked immediately."""

import fcntl
import os
from pathlib import Path


class RunLocked(RuntimeError):
    pass


class RunLock:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._fd = None

    def __enter__(self) -> "RunLock":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(self.path), os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            raise RunLocked(f"another JobOps run holds {self.path}")
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode())
        self._fd = fd
        return self

    def __exit__(self, *exc) -> None:
        if self._fd is not None:
            fcntl.flock(self._fd, fcntl.LOCK_UN)
            os.close(self._fd)
            self._fd = None
