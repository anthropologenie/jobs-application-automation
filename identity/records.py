#!/usr/bin/env python3
"""
IdentityRecord - one comparable representation of a job, whatever produced it

The resolver compares IdentityRecords and nothing else. Building one is the
only place that knows the shape of a scraped_jobs row, an opportunities row or
a freshly ingested posting, which is what makes the identity scheme
source-agnostic by construction (JOBOPS_SCALING_EXECUTION_PLAN.md P0-07): a new
source needs a builder, not a redesign.

What a record deliberately does NOT carry
-----------------------------------------
Application status, stage, gate verdict, score, recommendation, dates, notes,
or any human decision. Identity is not application outcome. Those fields are
not inputs to any comparison here and cannot be written by anything here, so
no deduplication decision can depend on - or disturb - them.

Provenance carried on every record
----------------------------------
    record_kind / record_ref     which table and row this is
    source                       the source string as the row states it
    source_portal / external_id  the L1 key, when one is available
    original_source_url          the URL exactly as stored - never rewritten
    canonical_identity_url       the derived L2 key, or None with reasons
    ats_system / ats_tenant /
      requisition_id             the L4 key, when present
    normalized_company/title/
      location                   the L3 components, or None where not evaluable

Author: Karthik Shetty
Created: 2026-09-02
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple

from .canonical import (
    AtsRequisition,
    CanonicalUrl,
    canonicalize_url,
    normalize_company,
    normalize_location,
    normalize_title,
    requisition_from_url,
)
from .ruleset import IdentityRuleset

logger = logging.getLogger(__name__)

RECORD_KIND_SCRAPED_JOB = "scraped_job"
RECORD_KIND_OPPORTUNITY = "opportunity"
RECORD_KIND_CANDIDATE = "candidate"

# scraped_jobs.external_id is a single UNIQUE column shared by every source, so
# P0-06 namespaces LinkedIn ids into it as `linkedin:<id>`. Older RemoteOK rows
# predate that convention and hold a bare id; their portal comes from the
# `source` column instead. Both are read here, neither is rewritten.
_NAMESPACED_EXTERNAL_ID = re.compile(r"^([a-z0-9_-]+):(.+)$", re.IGNORECASE)


def normalize_portal(source: Optional[str]) -> Optional[str]:
    """
    Fold a source label onto a portal token: 'LinkedIn' and 'linkedin' are one
    portal. Nothing is mapped across portals - 'Naukri' never becomes anything
    but 'naukri'.
    """
    if source is None or not str(source).strip():
        return None
    return re.sub(r"\s+", "-", str(source).strip().lower())


@dataclass(frozen=True)
class IdentityRecord:
    """One job as the identity layers see it."""
    record_kind: str
    record_ref: str
    source: Optional[str] = None
    source_portal: Optional[str] = None
    external_id: Optional[str] = None
    url: Optional[CanonicalUrl] = None
    ats: AtsRequisition = field(default_factory=AtsRequisition)
    company: Optional[str] = None
    title: Optional[str] = None
    location: Optional[str] = None
    normalized_company: Optional[str] = None
    normalized_title: Optional[str] = None
    normalized_location: Optional[str] = None
    row_id: Optional[int] = None
    # Provenance only. The timestamp the SOURCE row carries for when this job
    # was observed. It is never compared, never a match key, and never used to
    # break a tie - a newer record is not a more authoritative identity.
    source_observed_at: Optional[str] = None

    # ------------------------------------------------------------------ keys

    @property
    def l1_key(self) -> Optional[Tuple[str, str]]:
        if self.source_portal and self.external_id:
            return (self.source_portal, str(self.external_id))
        return None

    @property
    def l2_key(self) -> Optional[str]:
        return self.url.identity_url if self.url else None

    @property
    def l3_key(self) -> Optional[Tuple[str, str, str]]:
        """None unless all three components are evaluable (artifact: L3
        requires_all_components)."""
        if self.normalized_company and self.normalized_title and self.normalized_location:
            return (self.normalized_company, self.normalized_title,
                    self.normalized_location)
        return None

    @property
    def l4_key(self) -> Optional[Tuple[str, str, str]]:
        return self.ats.key

    @property
    def host_family(self) -> Optional[str]:
        return self.url.host_family if self.url else None

    @property
    def original_source_url(self) -> Optional[str]:
        return self.url.original if self.url else None

    @property
    def canonical_identity_url(self) -> Optional[str]:
        return self.l2_key

    def as_dict(self) -> Dict[str, Any]:
        return {
            "record_kind": self.record_kind,
            "record_ref": self.record_ref,
            "row_id": self.row_id,
            "source": self.source,
            "source_portal": self.source_portal,
            "external_id": self.external_id,
            "url": self.url.as_dict() if self.url else None,
            "ats": self.ats.as_dict(),
            "company": self.company,
            "title": self.title,
            "location": self.location,
            "normalized_company": self.normalized_company,
            "normalized_title": self.normalized_title,
            "normalized_location": self.normalized_location,
            "source_observed_at": self.source_observed_at,
        }


def _build(ruleset: IdentityRuleset, *, record_kind: str, record_ref: str,
           source: Optional[str], external_id: Optional[str],
           url: Optional[str], company: Optional[str], title: Optional[str],
           location: Optional[str], row_id: Optional[int] = None,
           source_observed_at: Optional[str] = None) -> IdentityRecord:
    canonical = canonicalize_url(url, ruleset)

    portal = normalize_portal(source)
    native_id: Optional[str] = None
    if external_id:
        namespaced = _NAMESPACED_EXTERNAL_ID.match(str(external_id))
        if namespaced:
            portal = normalize_portal(namespaced.group(1)) or portal
            native_id = namespaced.group(2)
        else:
            native_id = str(external_id)

    if native_id is None and canonical.external_id:
        # The URL demonstrably carries the source-native id in its path (the
        # host family declares where). Reading it is evidence, not inference,
        # and it is the only way an opportunities row - which has no
        # external_id column - can participate in L1 at all.
        native_id = canonical.external_id
        portal = canonical.source_portal or portal
    elif native_id is not None and canonical.source_portal:
        portal = canonical.source_portal or portal

    return IdentityRecord(
        record_kind=record_kind,
        record_ref=record_ref,
        row_id=row_id,
        source=source,
        source_portal=portal,
        external_id=native_id,
        url=canonical,
        ats=requisition_from_url(url, ruleset),
        company=company,
        title=title,
        location=location,
        normalized_company=normalize_company(company, ruleset),
        normalized_title=normalize_title(title, ruleset),
        normalized_location=normalize_location(location, ruleset),
        source_observed_at=source_observed_at,
    )


def record_from_scraped_job(row: Mapping[str, Any],
                            ruleset: IdentityRuleset) -> IdentityRecord:
    """Build a record from a scraped_jobs row. Scoring columns are not read."""
    return _build(
        ruleset,
        record_kind=RECORD_KIND_SCRAPED_JOB,
        record_ref=f"scraped_jobs:{row['id']}",
        row_id=int(row["id"]),
        source=row.get("source"),
        external_id=row.get("external_id"),
        url=row.get("job_url"),
        company=row.get("company"),
        title=row.get("job_title"),
        location=row.get("location"),
        source_observed_at=row.get("scraped_at"),
    )


def record_from_opportunity(row: Mapping[str, Any],
                            ruleset: IdentityRuleset) -> IdentityRecord:
    """
    Build a record from an opportunities row.

    `status` is not read. An applied, rejected or archived opportunity is in
    identity scope exactly like any other (P0_SPEC 8.4) - which is the point:
    matching one is what stops something already applied to being re-surfaced.
    Its status plays no part in whether it matches, and nothing here can
    change it.
    """
    return _build(
        ruleset,
        record_kind=RECORD_KIND_OPPORTUNITY,
        record_ref=f"opportunities:{row['id']}",
        row_id=int(row["id"]),
        source=row.get("source"),
        external_id=None,          # the table has no such column
        url=row.get("job_url"),
        company=row.get("company"),
        title=row.get("role"),
        location=None,             # the table has no location column
        source_observed_at=row.get("discovered_date"),
    )


def record_from_candidate(ruleset: IdentityRuleset, *, record_ref: str,
                          source: Optional[str] = None,
                          external_id: Optional[str] = None,
                          url: Optional[str] = None,
                          company: Optional[str] = None,
                          title: Optional[str] = None,
                          location: Optional[str] = None,
                          source_observed_at: Optional[str] = None) -> IdentityRecord:
    """
    Build a record for a candidate that is not yet in any table - a freshly
    ingested posting, or one from a source that does not exist yet.

    This is the source-agnostic entry point. A second portal needs a call to
    this function, not a change to any identity layer.
    """
    return _build(ruleset, record_kind=RECORD_KIND_CANDIDATE,
                  record_ref=record_ref, source=source, external_id=external_id,
                  url=url, company=company, title=title, location=location,
                  source_observed_at=source_observed_at)
