#!/usr/bin/env python3
"""
Canonicalization - the L2 identity URL and the L3 normalized text keys

Two jobs here, both of them deliberately narrow:

  1. Turn a posting URL into a canonical identity URL, or refuse. Refusal is a
     first-class outcome: P0_IMPLEMENTATION_SPEC.md 8.2 requires that fragment-only
     and listing-page URLs be REJECTED as identities rather than stored as ones,
     because a company board URL used as an identity merges every posting that
     employer has.

  2. Turn company, title and location into conservative normalized keys, or
     report that a component is not evaluable.

Nothing here matches, scores or decides. It produces keys and reasons; the
resolver compares them.

Two invariants this module never breaks
---------------------------------------
  * The original URL is never destroyed. `CanonicalUrl.original` carries the
    string exactly as it was supplied, alongside the derived identity URL. The
    original exists for provenance; the canonical one exists for identity, and
    a caller can always show both.

  * An absent value is never positive evidence. A missing location, an empty
    company or an unparseable URL yields None plus a reason code - never a
    wildcard that happens to match everything.

Every host rule, tracking parameter, legal suffix and reason code is read from
identity/jobops-identity-0.1.0.json. Nothing identity-bearing is hardcoded here.

Author: Karthik Shetty
Created: 2026-09-02
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit

from .ruleset import IdentityRuleset

logger = logging.getLogger(__name__)

_DEFAULT_PORTS = {"http": "80", "https": "443"}


# ==========================================================================
# URL canonicalization - L2
# ==========================================================================

@dataclass(frozen=True)
class CanonicalUrl:
    """
    The result of asking "can this URL serve as a posting identity?".

    `original` and `identity_url` are separate fields on purpose. The original
    is raw-source evidence and is retained verbatim; the identity URL is a
    derived key. A rejected URL still carries its original and its reasons, so
    a reviewer can see both what arrived and why it was not usable.
    """
    original: Optional[str]
    identity_url: Optional[str] = None
    host_family: Optional[str] = None
    source_portal: Optional[str] = None
    external_id: Optional[str] = None
    id_derived: bool = False
    reason_codes: Tuple[str, ...] = ()

    @property
    def is_identity(self) -> bool:
        return self.identity_url is not None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "original_source_url": self.original,
            "canonical_identity_url": self.identity_url,
            "host_family": self.host_family,
            "source_portal": self.source_portal,
            "external_id": self.external_id,
            "id_derived": self.id_derived,
            "reason_codes": list(self.reason_codes),
        }


def _split(url: str):
    """
    Parse a URL, tolerating a missing scheme.

    Portals quote posting URLs both ways ("in.linkedin.com/jobs/view/..." and
    "https://in.linkedin.com/jobs/view/..."). Assuming https for a bare
    host/path is a parsing convenience, not an identity claim - the host and
    path, which carry the identity, are unchanged either way.
    """
    parts = urlsplit(url)
    if not parts.scheme and not parts.netloc:
        head = url.lstrip("/").split("/", 1)[0]
        if "." in head:
            parts = urlsplit("https://" + url.lstrip("/"))
    return parts


def _normalize_host(netloc: str, scheme: str) -> str:
    host = netloc.lower()
    if "@" in host:                      # credentials are not identity
        host = host.rsplit("@", 1)[1]
    if ":" in host:
        host, _, port = host.rpartition(":")
        if port and port != _DEFAULT_PORTS.get(scheme):
            host = f"{host}:{port}"
    return host


def _clean_query(query: str, ruleset: IdentityRuleset) -> str:
    """
    Drop declared tracking parameters; keep everything else, sorted.

    Unrecognized parameters are kept deliberately. `?id=NIM2919` is the whole
    identity of that posting, and a canonicalizer that dropped unknown
    parameters would merge every posting on that host into one.
    """
    if not query:
        return ""
    tracking = ruleset.tracking_parameters
    kept = [(k, v) for k, v in parse_qsl(query, keep_blank_values=True)
            if k.lower() not in tracking]
    if not kept:
        return ""
    if ruleset.url.get("sort_query_parameters", True):
        kept.sort()
    return urlencode(kept)


def _strip_trailing_slash(path: str) -> str:
    if len(path) > 1 and path.endswith("/"):
        return path.rstrip("/") or "/"
    return path


def _match_family(host: str, ruleset: IdentityRuleset) -> Tuple[Optional[Dict[str, Any]],
                                                                Optional[re.Match]]:
    for family in ruleset.host_families:
        match = re.match(family["host_pattern"], host)
        if match:
            return family, match
    return None, None


def canonicalize_url(url: Optional[str],
                     ruleset: IdentityRuleset) -> CanonicalUrl:
    """
    Derive the canonical identity URL for a posting URL, or refuse with reasons.

    Refusal cases, all of them declared in the artifact and all of them
    reported rather than silently swallowed: no URL, a non-http scheme, an
    unparseable string, a host root, a URL distinguished only by a fragment, a
    bare listing path, and - for a host whose posting form the artifact
    declares - a path that is not that posting form.
    """
    if url is None or not str(url).strip():
        return CanonicalUrl(original=url,
                            reason_codes=(ruleset.assert_reason_code("ID-URL-ABSENT"),))

    original = str(url).strip()
    try:
        parts = _split(original)
    except ValueError:
        return CanonicalUrl(original=original,
                            reason_codes=(ruleset.assert_reason_code("ID-URL-UNPARSEABLE"),))

    scheme = (parts.scheme or "https").lower()
    if scheme not in ruleset.allowed_schemes:
        return CanonicalUrl(
            original=original,
            reason_codes=(ruleset.assert_reason_code("ID-URL-UNSUPPORTED-SCHEME"),))

    host = _normalize_host(parts.netloc, scheme)
    if not host:
        return CanonicalUrl(original=original,
                            reason_codes=(ruleset.assert_reason_code("ID-URL-UNPARSEABLE"),))

    had_fragment = bool(parts.fragment)          # removed, and remembered
    path = _strip_trailing_slash(parts.path or "/")
    query = _clean_query(parts.query, ruleset)
    canonical_scheme = ruleset.url.get("canonical_scheme", "https")

    family, host_match = _match_family(host, ruleset)

    if family is not None:
        posting = re.match(family["posting_path_pattern"], path)
        if posting is None:
            codes: List[str] = []
            if path in ("", "/"):
                codes.append(ruleset.assert_reason_code("ID-URL-ROOT-ONLY"))
                if had_fragment:
                    codes.append(ruleset.assert_reason_code("ID-URL-FRAGMENT-ONLY"))
            else:
                codes.append(ruleset.assert_reason_code("ID-URL-NOT-A-POSTING-PATH"))
            return CanonicalUrl(original=original, host_family=family["name"],
                                source_portal=family.get("source_portal"),
                                reason_codes=tuple(codes))

        external_id = None
        id_derived = False
        group = family.get("external_id_group")
        if group is not None:
            external_id = posting.group(group)

        canonical_host = family.get("canonical_host") or host
        if external_id is not None and family.get("canonical_path_template"):
            # The source-native id IS the identity, so the canonical path is
            # rebuilt from it and the human-readable slug and any remaining
            # query are dropped. This is what makes
            # in.linkedin.com/jobs/view/<slug>-<id> and
            # www.linkedin.com/jobs/view/<id> one identity.
            canonical_path = family["canonical_path_template"].format(
                external_id=external_id)
            canonical_query = ""
            id_derived = True
        else:
            canonical_path = path
            canonical_query = query

        identity = f"{canonical_scheme}://{canonical_host}{canonical_path}"
        if canonical_query:
            identity = f"{identity}?{canonical_query}"
        return CanonicalUrl(original=original, identity_url=identity,
                            host_family=family["name"],
                            source_portal=family.get("source_portal"),
                            external_id=external_id, id_derived=id_derived)

    # Undeclared host. www is the only subdomain removed; see the artifact's
    # strip_leading_www_note for why blanket subdomain stripping is unsafe.
    if ruleset.url.get("strip_leading_www", True) and host.startswith("www."):
        host = host[4:]

    if path in ("", "/") and ruleset.url.get("reject_root_path", True):
        codes = [ruleset.assert_reason_code("ID-URL-ROOT-ONLY")]
        if had_fragment:
            codes.append(ruleset.assert_reason_code("ID-URL-FRAGMENT-ONLY"))
        return CanonicalUrl(original=original, reason_codes=tuple(codes))

    if not query and any(p.match(path) for p in ruleset.bare_listing_patterns):
        return CanonicalUrl(
            original=original,
            reason_codes=(ruleset.assert_reason_code("ID-URL-LISTING-PAGE"),))

    identity = f"{canonical_scheme}://{host}{path}"
    if query:
        identity = f"{identity}?{query}"
    return CanonicalUrl(original=original, identity_url=identity)


# ==========================================================================
# ATS requisition identity - L4
# ==========================================================================

@dataclass(frozen=True)
class AtsRequisition:
    """
    An ATS requisition identity, always namespaced by system and tenant.

    A bare requisition id is never exposed as a key. The artifact's ats_note
    states the reason: unrelated ATS systems issue the same number, so
    `requisition_id` alone would merge two unrelated jobs.
    """
    system: Optional[str] = None
    tenant: Optional[str] = None
    requisition_id: Optional[str] = None

    @property
    def is_present(self) -> bool:
        return bool(self.system and self.requisition_id)

    @property
    def key(self) -> Optional[Tuple[str, str, str]]:
        if not self.is_present:
            return None
        return (self.system, (self.tenant or "").lower(), self.requisition_id)

    def as_dict(self) -> Dict[str, Any]:
        return {"ats_system": self.system, "ats_tenant": self.tenant,
                "requisition_id": self.requisition_id}


def requisition_from_url(url: Optional[str],
                         ruleset: IdentityRuleset) -> AtsRequisition:
    """Extract an ATS system, tenant and requisition id from a posting URL."""
    if url is None or not str(url).strip():
        return AtsRequisition()
    try:
        parts = _split(str(url).strip())
    except ValueError:
        return AtsRequisition()

    host = _normalize_host(parts.netloc, (parts.scheme or "https").lower())
    path = _strip_trailing_slash(parts.path or "/")

    for system in ruleset.ats_systems:
        host_match = re.match(system["host_pattern"], host)
        if not host_match:
            continue

        tenant = None
        if system.get("tenant_group") and "tenant_pattern" not in system:
            tenant = host_match.group(system["tenant_group"])
        elif system.get("tenant_pattern"):
            tenant_match = re.match(system["tenant_pattern"], path)
            if tenant_match:
                tenant = tenant_match.group(system.get("tenant_group", 1))

        requisition = None
        req_match = re.search(system["requisition_pattern"], path)
        if req_match:
            requisition = req_match.group(system.get("requisition_group", 1))

        if requisition is None:
            # Host is a known ATS but the path carries no requisition. Reporting
            # the system without an id would create a key of (system, tenant,
            # None) that every other id-less posting on that tenant matches.
            return AtsRequisition(system=system["name"], tenant=tenant)
        return AtsRequisition(system=system["name"], tenant=tenant,
                              requisition_id=requisition)
    return AtsRequisition()


# ==========================================================================
# Text normalization - L3
# ==========================================================================

def _base_normalize(value: Optional[str]) -> Optional[str]:
    """lowercase, punctuation to space, collapse whitespace. Nothing else."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    lowered = "".join(ch.lower() if (ch.isalnum() or ch.isspace()) else " "
                      for ch in text)
    collapsed = re.sub(r"\s+", " ", lowered).strip()
    return collapsed or None


def normalize_company(value: Optional[str],
                      ruleset: IdentityRuleset) -> Optional[str]:
    """
    Normalize an employer name for L3.

    Only declared legal-form suffixes are stripped, repeatedly from the end and
    never down to an empty string. Country and division qualifiers are kept:
    'SymphonyAI Group - India' does not normalize to 'symphonyai', because
    merging a subsidiary into its parent would assert an identity nobody
    established.
    """
    normalized = _base_normalize(value)
    if normalized is None:
        return None
    suffixes = sorted((s.lower() for s in ruleset.legal_suffixes),
                      key=len, reverse=True)
    changed = True
    while changed:
        changed = False
        for suffix in suffixes:
            if normalized.endswith(" " + suffix):
                trimmed = normalized[: -(len(suffix) + 1)].strip()
                if trimmed:
                    normalized = trimmed
                    changed = True
                    break
    return normalized or None


def normalize_title(value: Optional[str],
                    ruleset: IdentityRuleset) -> Optional[str]:
    """
    Normalize a job title for L3.

    No seniority stripping, no synonym expansion, no keyword extraction. Two
    titles match only when they normalize to the same string.
    """
    return _base_normalize(value)


def normalize_location(value: Optional[str],
                       ruleset: IdentityRuleset) -> Optional[str]:
    """
    Normalize a location for L3, or report it as not evaluable.

    A location that is absent, blank, or one of the artifact's declared unknown
    tokens returns None. None is never positive evidence and never matches
    another None - two postings with unknown locations are not thereby the same
    posting.
    """
    normalized = _base_normalize(value)
    if normalized is None:
        return None
    if normalized in {t.lower() for t in ruleset.location_unknown_tokens}:
        return None
    return normalized
