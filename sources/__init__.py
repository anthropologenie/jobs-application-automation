"""
Discovery source seam (Phase B: interface only).

No adapter is implemented here and nothing in this package performs network
I/O. Later phases (P2) add employer-ATS, public-source and the existing
low-volume LinkedIn adapter behind `SourceAdapter`, each after a recorded
reconnaissance (docs/architecture/JOBOPS_V2_REPO_LAYOUT.md §5). Apify, if ever
used, is an optional file import only (OR-23).
"""

from .base import COMPLETENESS, SOURCE_KINDS, ObservationInput, SourceAdapter  # noqa: F401
