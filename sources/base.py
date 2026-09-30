"""The observation contract every future source adapter must produce."""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, Optional, Protocol

SOURCE_KINDS = ("EMPLOYER_ATS", "COMPANY_SITE", "JOB_BOARD", "AGGREGATOR", "IMPORT")
COMPLETENESS = ("FULL_JD", "PARTIAL", "SEARCH_ONLY")


@dataclass(frozen=True)
class ObservationInput:
    """
    One sighting of a posting, exactly as a source reported it.

    Fields a source did not supply are None ("not captured"). Nothing is
    defaulted from another source; merging across sightings is the evaluation
    layer's job, never the adapter's.
    """
    source: str                      # e.g. "ats:greenhouse", "linkedin-search"
    source_kind: str                 # one of SOURCE_KINDS
    observed_at: str                 # ISO-8601 UTC
    run_id: str
    completeness: str                # one of COMPLETENESS
    source_external_id: Optional[str] = None
    source_url: Optional[str] = None
    apply_url: Optional[str] = None
    raw_title: Optional[str] = None
    raw_company: Optional[str] = None
    raw_location: Optional[str] = None
    raw_work_mode: Optional[str] = None   # structured work-mode field (e.g. "Remote", "Hybrid"), kept
                                         # separate from the location; read by policies >= 0.2.2
    raw_salary: Optional[str] = None
    raw_employment_type: Optional[str] = None
    raw_text: Optional[str] = None   # the JD body; None when not captured
    source_posted_date: Optional[str] = None
    source_updated_date: Optional[str] = None
    language_detection: Optional[Dict[str, Any]] = field(default=None)

    def __post_init__(self) -> None:
        if self.source_kind not in SOURCE_KINDS:
            raise ValueError(f"unknown source_kind {self.source_kind!r}")
        if self.completeness not in COMPLETENESS:
            raise ValueError(f"unknown completeness {self.completeness!r}")

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SourceAdapter(Protocol):
    """Future adapters implement this. None exist in Phase B."""

    name: str
    source_kind: str

    def observations(self, run_id: str) -> Iterable[ObservationInput]:
        ...
