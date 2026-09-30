"""
JobOps Identity Package - P0-07 cross-source deduplication

    candidate  ->  L1 (source_portal, external_id)
               ->  L2 canonical identity URL
               ->  L4 (ats_system, ats_tenant, requisition_id)
               ->  L3 (normalized company, title, location)
               ->  DEFINITE_DUPLICATE | PROBABLE_DUPLICATE
                   | IDENTITY_UNCERTAIN | DISTINCT, with its evidence

Authority:
    P0_IMPLEMENTATION_SPEC.md 8              - layers, uncertainty, dedup scope
    P0_IMPLEMENTATION_SPEC.md 13 X7          - duplicates controlled
    identity/jobops-identity-0.1.0.json      - the identity artifact

This package holds no policy. It never reads a gate verdict, a score, an
application status or data/resume_config.json, and it has no code path that
could change one. It never merges, deletes or rewrites a row: the database is
opened read-only and the resolver's product is a decision record, not a
mutation. Historical repair is a separate, separately authorized concern.

Identity is not eligibility and it is not application outcome.
"""

__version__ = "1.0.0"
__author__ = "Karthik Shetty"

from .canonical import (
    AtsRequisition,
    CanonicalUrl,
    canonicalize_url,
    normalize_company,
    normalize_location,
    normalize_title,
    requisition_from_url,
)
from .index import IdentityIndex, IdentityIndexError, IdentityStore
from .records import (
    IdentityRecord,
    normalize_portal,
    record_from_candidate,
    record_from_opportunity,
    record_from_scraped_job,
)
from .resolver import (
    IdentityMatch,
    IdentityResolution,
    IdentityResolver,
    resolve_candidate,
)
from .ruleset import IdentityDriftError, IdentityRuleset, load_identity_ruleset

__all__ = [
    "AtsRequisition", "CanonicalUrl", "canonicalize_url",
    "normalize_company", "normalize_location", "normalize_title",
    "requisition_from_url",
    "IdentityIndex", "IdentityIndexError", "IdentityStore",
    "IdentityRecord", "normalize_portal", "record_from_candidate",
    "record_from_opportunity", "record_from_scraped_job",
    "IdentityMatch", "IdentityResolution", "IdentityResolver",
    "resolve_candidate",
    "IdentityDriftError", "IdentityRuleset", "load_identity_ruleset",
]
