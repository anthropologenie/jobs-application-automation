#!/usr/bin/env python3
"""
Evidence-preserving merge of the search record and the detail record - D1 fix

The defect this module exists to remove
---------------------------------------
The pipeline used to combine the two source records as

    {**posting, **(detail or {})}

which gives the detail response unconditional authority over every field it
carries a key for. In the first real LinkedIn run that erased genuine evidence:
the search results stated

    date = "2026-08-27"
    date = "2026-08-28"
    date = "2026-08-28"

and the detail endpoint stated

    date = null

so three postings were persisted with posted_date NULL despite the source
having supplied a real date for every one of them.

The invariant
-------------
    MORE DETAIL IS NOT AUTOMATICALLY MORE AUTHORITY.

A later response may enrich an earlier one. It may not erase it. A missing key,
a null and a blank string are all "this record supplied nothing", and nothing
never overwrites something.

This is deliberately NOT a universal "never overwrite" rule. A detail response
that supplies a real value for a field the search left empty is exactly the
enrichment the detail call is for, and a detail response that supplies a better
value for a field the search answered poorly is allowed to replace it. Merge
authority is decided per field, and the two rules in use are declared in
FIELD_PRECEDENCE below.

Three-state discipline (P0_IMPLEMENTATION_SPEC.md 4.4) is preserved exactly:

    key absent everywhere   -> absent from the merged record ("not captured")
    key present, no value   -> present and None          ("the source stated none")
    key present with value  -> present with the value

Losing evidence is unrecoverable, so a suppressed observation is not discarded
silently: every field carries a provenance entry naming which record supplied
the winning value, what each record observed, and whether the observations
disagreed.

Author: Karthik Shetty
Created: 2026-09-02
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------- precedence

ENRICH = "enrich"
FIRST_OBSERVATION = "first_observation"

PRECEDENCE_RULES = {
    ENRICH: "The last record that supplied a value wins. A record that supplied "
            "nothing never displaces one that did.",
    FIRST_OBSERVATION: "The first record that supplied a value wins. Later "
                       "records may not displace it merely by arriving later.",
}

DEFAULT_PRECEDENCE = ENRICH

# Per-field overrides. Kept minimal on purpose: this is an evidence-preservation
# fix, not a general merge refactor, and every entry here has to earn its place.
#
#   url  Both records carry a legitimate posting URL. The search result gave
#        https://in.linkedin.com/jobs/view/<slug>-<id> and the detail response
#        gave https://www.linkedin.com/jobs/view/<id>. Neither is wrong, so
#        arrival order is not a reason to prefer one - and the pipeline's own
#        provenance already declares job_url as derived from results[].url.
#        The first observation is therefore kept as the stored source URL, the
#        detail URL stays visible in field provenance and in the retained raw
#        payload, and identity across the two forms is the identity layer's
#        job, not this module's.
FIELD_PRECEDENCE = {
    "url": FIRST_OBSERVATION,
}

# Observation states, recorded per record per field.
STATE_VALUE = "value"
STATE_STATED_NONE = "stated_none"
STATE_BLANK = "blank"
STATE_NOT_CAPTURED = "not_captured"


def _observation_state(record: Mapping[str, Any], field_name: str) -> str:
    if field_name not in record:
        return STATE_NOT_CAPTURED
    value = record[field_name]
    if value is None:
        return STATE_STATED_NONE
    if isinstance(value, str) and not value.strip():
        return STATE_BLANK
    return STATE_VALUE


@dataclass(frozen=True)
class SourceRecord:
    """One observation of a posting, named so provenance can point at it."""
    name: str
    values: Mapping[str, Any]
    observed_at: Optional[str] = None


@dataclass(frozen=True)
class MergedRecord:
    """The merged values, plus the provenance that explains every one of them."""
    values: Dict[str, Any]
    field_provenance: Dict[str, Dict[str, Any]]
    conflicts: List[Dict[str, Any]] = field(default_factory=list)

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def __contains__(self, key: str) -> bool:
        return key in self.values

    def as_dict(self) -> Dict[str, Any]:
        return {
            "field_provenance": {k: dict(v) for k, v in self.field_provenance.items()},
            "conflicts": [dict(c) for c in self.conflicts],
        }


def merge_source_records(
        records: Sequence[SourceRecord],
        precedence: Optional[Mapping[str, str]] = None) -> MergedRecord:
    """
    Merge observations of one posting without letting any of them erase another.

    Records are supplied earliest-observation first. The merged key set is the
    union of every record's keys, so a key nobody captured stays absent while a
    key someone captured as null stays present and null.
    """
    rules = dict(FIELD_PRECEDENCE if precedence is None else precedence)
    merged: Dict[str, Any] = {}
    provenance: Dict[str, Dict[str, Any]] = {}
    conflicts: List[Dict[str, Any]] = []

    field_names: List[str] = []
    for record in records:
        for name in record.values:
            if name not in field_names:
                field_names.append(name)

    for name in field_names:
        rule = rules.get(name, DEFAULT_PRECEDENCE)
        observations: List[Dict[str, Any]] = []
        supplied: List[SourceRecord] = []

        for record in records:
            state = _observation_state(record.values, name)
            if state == STATE_NOT_CAPTURED:
                continue
            observations.append({
                "record": record.name,
                "observed_at": record.observed_at,
                "state": state,
                "value": record.values[name],
            })
            if state == STATE_VALUE:
                supplied.append(record)

        if supplied:
            winner = supplied[0] if rule == FIRST_OBSERVATION else supplied[-1]
            merged[name] = winner.values[name]
            value_from = winner.name
        else:
            # Every record that carried the key stated none. That is the source
            # speaking, and it is preserved as null rather than dropped.
            merged[name] = None
            value_from = None

        distinct_values = []
        for observation in observations:
            if observation["state"] == STATE_VALUE and \
                    observation["value"] not in distinct_values:
                distinct_values.append(observation["value"])

        suppressed = [o for o in observations
                      if o["value"] != merged[name] or o["state"] != STATE_VALUE]
        disagreement = len(distinct_values) > 1
        erasure_prevented = bool(supplied) and any(
            o["state"] in (STATE_STATED_NONE, STATE_BLANK) for o in observations)

        provenance[name] = {
            "value_from": value_from,
            "rule": rule,
            "observations": observations,
            "disagreement": disagreement,
            "erasure_prevented": erasure_prevented,
        }

        if disagreement or erasure_prevented:
            conflicts.append({
                "field": name,
                "resolved_value": merged[name],
                "value_from": value_from,
                "rule": rule,
                "reason": "value_disagreement" if disagreement
                          else "empty_observation_did_not_erase_evidence",
                "suppressed_observations": suppressed,
            })

    return MergedRecord(values=merged, field_provenance=provenance,
                        conflicts=conflicts)
