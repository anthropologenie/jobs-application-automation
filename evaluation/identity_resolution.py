"""
Canonical requisition identity (Phase B §27).

Suppression-grade keys (reused from identity/ canonicalization):
    L1  (source, source-native id)
    L2  canonical posting URL           (source_url and apply_url)
    L4  ATS system + tenant + req id    (source_url and apply_url)
A sighting matching one requisition by any of these attaches to it. Matching
two different requisitions means they are the same job: the lower-authority one
is marked duplicate_of the canonical one (SUPPRESSED_DUPLICATE) and nothing is
deleted or moved.

Company + title + geo-normalised location alone is NOT suppression-grade: the
sighting becomes its own requisition, both are flagged IDENTITY_UNCERTAIN, and a
PROBABLE_DUPLICATE link is recorded for the human. Titles that merely look
similar are never merged.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

from identity.canonical import canonicalize_url, normalize_company, normalize_title, requisition_from_url

from store import repository as repo

AUTHORITY_ATS = 1


def observation_keys(obs: Dict[str, Any], id_rules) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]], Optional[str]]:
    """Returns (keys, ats_identities[(system, tenant)], best employer URL)."""
    keys: List[Tuple[str, str]] = []
    ats: List[Tuple[str, str]] = []
    employer_url = None
    if obs.get("source_external_id"):
        keys.append(("L1", f"{obs['source']}|{obs['source_external_id']}"))
    for field in ("source_url", "apply_url"):
        url = obs.get(field)
        if not url:
            continue
        canon = canonicalize_url(url, id_rules)
        if canon.is_identity:
            keys.append(("L2", canon.identity_url))
        req = requisition_from_url(url, id_rules)
        if req.is_present:
            keys.append(("L4", "|".join(req.key)))
            if req.tenant:
                ats.append((req.system, req.tenant))
            employer_url = employer_url or (canon.identity_url if canon.is_identity else url)
    if obs.get("source_kind") in ("EMPLOYER_ATS", "COMPANY_SITE") and obs.get("source_url"):
        canon = canonicalize_url(obs["source_url"], id_rules)
        employer_url = canon.identity_url if canon.is_identity else obs["source_url"]
    return sorted(set(keys)), sorted(set(ats)), employer_url


def l3_key(obs: Dict[str, Any], location_ref: Optional[str], id_rules) -> Optional[str]:
    company = normalize_company(obs.get("raw_company"), id_rules)
    title = normalize_title(obs.get("raw_title"), id_rules)
    if not (company and title and location_ref):
        return None
    return f"{company}|{title}|{location_ref}"


def root_of(conn, requisition_id: str) -> str:
    seen = set()
    while True:
        req = repo.get_requisition(conn, requisition_id)
        if not req["duplicate_of"] or requisition_id in seen:
            return requisition_id
        seen.add(requisition_id)
        requisition_id = req["duplicate_of"]


def _add_identity_flag(conn, requisition_id: str, flag: str) -> None:
    req = repo.get_requisition(conn, requisition_id)
    flags = set(json.loads(req["identity_flags_json"]))
    if flag not in flags:
        flags.add(flag)
        repo.update_requisition(conn, requisition_id, identity_flags_json=json.dumps(sorted(flags)),
                                identity_confidence="UNCERTAIN")


def resolve(conn, obs: Dict[str, Any], keys, location_ref: Optional[str], id_rules) -> Dict[str, Any]:
    """Find the requisition for this sighting. Does not create one (caller does)."""
    matched = repo.find_by_keys(conn, keys)
    roots = sorted({root_of(conn, rid) for rid in matched})
    affected: List[str] = []
    if len(roots) > 1:
        ranked = sorted(roots, key=lambda r: ((repo.get_requisition(conn, r)["canonical_url_authority"] or 9), r))
        canonical, others = ranked[0], ranked[1:]
        for other in others:
            repo.update_requisition(conn, other, duplicate_of=canonical)
            repo.add_identity_link(conn, canonical, other, "DEFINITE_DUPLICATE", "L1/L2/L4",
                                   "one sighting carries suppression-grade keys of both requisitions")
            affected.append(other)
        roots = [canonical]
    if roots:
        target = roots[0]
        own_l4 = [k for k in keys if k[0] == "L4"]
        existing_l4 = [k for k in repo.keys_of(conn, target) if k[0] == "L4"]
        for _, value in own_l4:
            system_tenant = value.rsplit("|", 1)[0]
            for _, ev in existing_l4:
                if ev.rsplit("|", 1)[0] == system_tenant and ev != value:
                    _add_identity_flag(conn, target, "IDENTITY_UNCERTAIN")
        return {"requisition_id": target, "created": False, "affected": affected, "probable_of": []}
    l3 = l3_key(obs, location_ref, id_rules)
    probable = []
    if l3:
        probable = [r["requisition_id"] for r in conn.execute(
            "SELECT requisition_id FROM requisition WHERE l3_key=? AND duplicate_of IS NULL ORDER BY requisition_id",
            (l3,))]
    return {"requisition_id": None, "created": True, "affected": affected, "probable_of": probable, "l3_key": l3}


def link_probable(conn, new_id: str, probable_of: List[str]) -> List[str]:
    for other in probable_of:
        repo.add_identity_link(conn, other, new_id, "PROBABLE_DUPLICATE", "L3",
                               "company + title + normalised location match without a suppression-grade key")
        _add_identity_flag(conn, other, "IDENTITY_UNCERTAIN")
    if probable_of:
        _add_identity_flag(conn, new_id, "IDENTITY_UNCERTAIN")
    return list(probable_of)
