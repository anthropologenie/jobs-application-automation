"""
Newness (Phase B §24-§25): NEW | UPDATED | SEEN_BEFORE per canonical requisition.

UPDATED only when a material field (title, location, compensation, employment
type, JD hash) present in BOTH this sighting and the latest earlier sighting
from the SAME source has a different value. A field absent before and present
now is enrichment, never an update. A disagreement between different sources is
a SOURCE_CONFLICT (evaluation), not an update, under 0.2.0 / 0.2.1.

0.2.2 (OR-64, newness.cross_source_update): a sighting from a strictly
higher-authority source that changes the ACCEPTED value of a material field is
also UPDATED; one that leaves the accepted value unchanged is not.
"""

from typing import Any, Dict, List, Optional

from . import dimensions as D
from .textutil import content_hash, date_precision, epoch, normalize_words


def material_snapshot(obs: Dict[str, Any], rows: List[Dict[str, Any]], policy, places) -> Dict[str, Any]:
    geo_rows = [r for r in rows if r["dimension"] == "geography" and not r["value"]["is_listing"]]
    geo_facts = D.summarize_geography(geo_rows, [], places)
    arrangement = D.geography_comparable(geo_facts)
    listing = normalize_words(obs.get("raw_location")) or None
    comp_clauses = [r["value"] for r in rows if r["dimension"] == "compensation" and r["value"]["kind"] == "FIGURE"]
    comp = tuple(sorted((c["currency"], c["min"], c["max"], c["period"], c["basis"]) for c in comp_clauses)) or None
    emp = D.employment_comparable(D.summarize_employment([r for r in rows if r["dimension"] == "employment_type"], policy))
    return {
        "title": normalize_words(obs.get("raw_title")) or None,
        # Location is compared like-for-like only: a stated work arrangement
        # against a stated arrangement, a portal listing string against a
        # listing string. A listing never "changes" a JD statement.
        "location": {"arrangement": list(arrangement) if arrangement else None, "listing": listing},
        "compensation": [list(c) for c in comp] if comp else None,
        "employment_type": list(emp) if emp else None,
        "jd_hash": content_hash(obs["raw_text"]) if obs.get("raw_text") else None,
    }


def changed_fields(current: Dict[str, Any], previous: Optional[Dict[str, Any]], fields: List[str]) -> List[str]:
    if previous is None:
        return []
    changed = []
    for f in fields:
        a, b = current.get(f), previous.get(f)
        if isinstance(a, dict) and isinstance(b, dict):
            if any(a.get(k) is not None and b.get(k) is not None and a[k] != b[k] for k in a):
                changed.append(f)
        elif a is not None and b is not None and a != b:
            changed.append(f)
    return changed


def _accepted(observations: List[Dict[str, Any]], snapshots: Dict[str, Dict[str, Any]], field: str):
    """The observation whose value of `field` is accepted: highest source authority, then most recent."""
    having = [o for o in observations if has_field(snapshots[o["observation_id"]], field)]
    if not having:
        return None
    return sorted(having, key=lambda o: (o["source_authority_tier"], -epoch(o["observed_at"]), -o["seq"]))[0]


def cross_source_changes(current: Dict[str, Any], observations: List[Dict[str, Any]],
                         snapshots: Dict[str, Dict[str, Any]], cfg: Dict[str, Any]) -> List[str]:
    """
    OR-64 (0.2.2): fields whose ACCEPTED value changes because this sighting, from
    a strictly higher-authority source than the one previously accepted,
    disagrees with it. A disagreement that does not change the accepted value
    (e.g. a board contradicting an ATS) is not an update; the evaluation still
    reports it as SOURCE_CONFLICT. Location is compared on the stated
    arrangement only; raw listing strings and the JD hash are formatted
    differently by every source and are not compared across sources.
    """
    prior = [o for o in observations if o["observation_id"] != current["observation_id"]]
    changed = []
    for field in cfg["fields"]:
        before = _accepted(prior, snapshots, field)
        after = _accepted(observations, snapshots, field)
        if before is None or after is None or after["observation_id"] != current["observation_id"]:
            continue
        if before["source"] == current["source"] or not current["source_authority_tier"] < before["source_authority_tier"]:
            continue
        a, b = snapshots[current["observation_id"]], snapshots[before["observation_id"]]
        if field == "location" and cfg.get("location_compare") == "arrangement":
            a, b = {field: a[field]["arrangement"]}, {field: b[field]["arrangement"]}
        if field in changed_fields(a, b, [field]):
            changed.append(field)
    return changed


def has_field(snapshot: Dict[str, Any], field: str) -> bool:
    value = snapshot.get(field)
    if isinstance(value, dict):
        return any(v is not None for v in value.values())
    return value is not None


def confidence(state: str, precision: str) -> str:
    if state == "NEW":
        return {"TIMESTAMP": "HIGH", "DATE": "MEDIUM"}.get(precision, "LOW")
    return "HIGH"


def classify(created: bool, requisition: Optional[Dict[str, Any]], run_id: str,
             changes: List[str], posted_precision: str) -> Dict[str, Any]:
    if created:
        state, reason = "NEW", ["first observation of this canonical requisition"]
    elif changes:
        state, reason = "UPDATED", [f"material change: {f}" for f in changes]
    elif requisition["first_seen_run_id"] == run_id and requisition["newness_state"] == "NEW":
        state, reason = "NEW", ["seen again within the run that first observed it"]
    elif requisition["last_seen_run_id"] == run_id and requisition["newness_state"] == "UPDATED":
        state, reason = "UPDATED", ["updated earlier in this run"]
    else:
        state, reason = "SEEN_BEFORE", ["no material change (evidence enrichment is not an update)"]
    return {"newness_state": state, "newness_confidence": confidence(state, posted_precision),
            "newness_reason": reason}


__all__ = ["material_snapshot", "changed_fields", "cross_source_changes", "classify", "date_precision"]
