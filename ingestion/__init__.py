"""
JobOps Ingestion Package - P0-06 minimum LinkedIn ingestion (Path A)

    linkedin-search CLI -> raw capture -> normalization -> P0-02 gate
                        -> candidate persistence

Authority:
    OWNER_RULINGS_LOG.md OR-08          - Path A, radar-scoped deferral
    P0_IMPLEMENTATION_SPEC.md 7          - ingestion contract, caps, provenance
    ingestion/linkedin-ingestion-0.1.0.json - the volume ceilings

This package holds no policy. It never reads data/resume_config.json. Every
verdict is produced by policy.HardEligibilityGate reading
policy/jobops-policy-0.1.0.json, and P0-06 performs no scoring.

Deduplication here is the existing repository identity contract only - L1
(source_portal, external_id) via scraped_jobs.external_id UNIQUE. P0-07 owns
everything else; see ingestion/pipeline.py's docstring for the exact boundary.
"""

__version__ = "1.0.0"
__author__ = "Karthik Shetty"

from .config import IngestionConfig, IngestionConfigError, VolumeCaps, load_config
from .extraction import is_remote_flag, work_mode_from_candidate_fields
from .linkedin_cli import LinkedInSearchCLI, RuntimeUnavailable, SourceRateLimited
from .merge import MergedRecord, SourceRecord, merge_source_records
from .persistence import CandidateRow, CandidateStore, PersistenceError
from .pipeline import LinkedInIngestionPipeline, QuerySpec
from .provenance import RawSourceStore, RunLedger, SourceProvenance
from .rate_limit import CapReached, RateLimiter

__all__ = [
    "IngestionConfig", "IngestionConfigError", "VolumeCaps", "load_config",
    "is_remote_flag", "work_mode_from_candidate_fields",
    "LinkedInSearchCLI", "RuntimeUnavailable", "SourceRateLimited",
    "MergedRecord", "SourceRecord", "merge_source_records",
    "CandidateRow", "CandidateStore", "PersistenceError",
    "LinkedInIngestionPipeline", "QuerySpec",
    "RawSourceStore", "RunLedger", "SourceProvenance",
    "CapReached", "RateLimiter",
]
