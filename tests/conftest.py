"""Pytest configuration: make the repository root importable.

The repository has no packaging metadata (no setup.py / pyproject.toml), so the
root is put on sys.path here rather than adding packaging infrastructure that
nothing else in the repository uses.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
