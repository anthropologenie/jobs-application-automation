#!/usr/bin/env python3
"""
IdentityResolver - P0-07 cross-source deduplication

Answers one question, and produces the evidence for its answer:

    Is this candidate the same job as something the system already holds?

Layers, most reliable first (P0_IMPLEMENTATION_SPEC.md 8.2):

    L1  (source_portal, external_id)                        high
    L2  canonical identity URL                              medium-high
    L4  (ats_system, ats_tenant, requisition_id)            high when present
    L3  (normalized_company, title, location) - all three   medium

Confidence is not a number here. L1, L2 and L4 are the layers
P0_IMPLEMENTATION_SPEC.md 8.4 grants suppression confidence; L3 is not, so an
exact L3 match is a PROBABLE_DUPLICATE for a human, never a DEFINITE one.

What this resolver refuses to do
--------------------------------
  * It never merges. It detects, classifies and reports. Deleting, merging or
    rewriting a row is not implemented, and the store it reads through is
    opened read-only, so no code path exists by which it could happen.
  * It never asserts identity on partial evidence. A near-match is
    IDENTITY_UNCERTAIN: retained, linked to its probable match, surfaced
    (P0_SPEC 8.3). P0 does not auto-merge on fuzzy evidence, and nothing here
    computes a similarity score for anything.
  * It never treats an absent value as agreement. Two unknown locations are not
    a matching location.
  * It never touches application state. Status, stage, gate verdict, score and
    human decisions are not inputs and cannot be outputs. Identity is not
    application outcome.
  * It never re-evaluates eligibility. A candidate's verdict is whatever the
    P0-02 gate said; this stage cannot turn an UNKNOWN into a PASS because it
    holds no verdict field at all.

Every outcome name, layer confidence, conflict rule and reason code is read
from identity/jobops-identity-0.1.0.json.

Author: Karthik Shetty
Created: 2026-09-02
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from .index import IdentityIndex
from .records import IdentityRecord
from .ruleset import IdentityDriftError, IdentityRuleset, load_identity_ruleset

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class IdentityMatch:
    """
    One candidate/record pair that produced identity evidence.

    `evidence` carries the compared values verbatim, so the reviewer's question
    - why did the system consider these two postings the same job? - is
    answered by the record itself rather than by re-running anything.
    """
    layer: str
    outcome: str
    record_ref: str
    record_kind: str
    row_id: Optional[int]
    reason_codes: List[str]
    evidence: Dict[str, Any]
    conflicts: List[Dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "layer": self.layer,
            "outcome": self.outcome,
            "matched_record_ref": self.record_ref,
            "matched_record_kind": self.record_kind,
            "matched_row_id": self.row_id,
            "reason_codes": list(self.reason_codes),
            "evidence": dict(self.evidence),
            "conflicts": [dict(c) for c in self.conflicts],
        }


@dataclass(frozen=True)
class IdentityResolution:
    """The full, explainable answer for one candidate."""
    identity_version: str
    resolved_at: str
    candidate: IdentityRecord
    outcome: str
    matched_layer: Optional[str]
    matched_record_ref: Optional[str]
    matches: List[IdentityMatch]
    considered: List[Dict[str, Any]]
    reason_codes: List[str]
    identity_uncertain: bool
    requires_human_review: bool
    suppress_from_review: bool
    has_uncertain_match: bool
    index_counts: Dict[str, int]

    @property
    def matched_record_kind(self) -> Optional[str]:
        for match in self.matches:
            if match.record_ref == self.matched_record_ref:
                return match.record_kind
        return None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "identity_version": self.identity_version,
            "resolved_at": self.resolved_at,
            "candidate": self.candidate.as_dict(),
            "outcome": self.outcome,
            "matched_layer": self.matched_layer,
            "matched_record_ref": self.matched_record_ref,
            "matched_record_kind": self.matched_record_kind,
            "identity_uncertain": self.identity_uncertain,
            "requires_human_review": self.requires_human_review,
            "suppress_from_review": self.suppress_from_review,
            "has_uncertain_match": self.has_uncertain_match,
            "reason_codes": list(self.reason_codes),
            "matches": [m.as_dict() for m in self.matches],
            "considered": [dict(c) for c in self.considered],
            "index_counts": dict(self.index_counts),
        }


class IdentityResolver:
    """Resolves candidates against an IdentityIndex. Holds no database handle."""

    def __init__(self, index: IdentityIndex,
                 ruleset: Optional[IdentityRuleset] = None):
        self.index = index
        self.ruleset = ruleset or load_identity_ruleset()
        self._suppression_layers = set(self.ruleset.suppression_grade_layers())
        self._layer_order = self.ruleset.layer_order()
        self._precedence = self.ruleset.overall_outcome_precedence

        self.DEFINITE = self.ruleset.outcome_name("definite_duplicate")
        self.PROBABLE = self.ruleset.outcome_name("probable_duplicate")
        self.UNCERTAIN = self.ruleset.outcome_name("identity_uncertain")
        self.DISTINCT = self.ruleset.outcome_name("distinct")

        for name in (self.DEFINITE, self.PROBABLE, self.UNCERTAIN, self.DISTINCT):
            if name not in self._precedence:
                raise IdentityDriftError(
                    f"Outcome {name!r} is missing from overall_outcome_precedence.")

    # ------------------------------------------------------------- conflicts

    def _conflicts(self, candidate: IdentityRecord,
                   other: IdentityRecord) -> List[Dict[str, Any]]:
        """
        Contradictions between two records at high-confidence layers.

        Only high-confidence layers can contradict. Differing company or title
        text alongside an L1/L2/L4 match is a noted difference, not a
        contradiction: employers rename and postings get re-titled, and neither
        is evidence of a different job.
        """
        found: List[Dict[str, Any]] = []

        if (candidate.l1_key and other.l1_key
                and candidate.source_portal == other.source_portal
                and candidate.external_id != other.external_id):
            found.append({
                "rule": "CF-L1",
                "reason_code": self.ruleset.conflict_reason_code("CF-L1"),
                "candidate_value": candidate.l1_key,
                "matched_value": other.l1_key,
            })

        if (candidate.l2_key and other.l2_key
                and candidate.host_family is not None
                and candidate.host_family == other.host_family
                and candidate.url.id_derived and other.url.id_derived
                and candidate.l2_key != other.l2_key):
            found.append({
                "rule": "CF-L2",
                "reason_code": self.ruleset.conflict_reason_code("CF-L2"),
                "candidate_value": candidate.l2_key,
                "matched_value": other.l2_key,
            })

        if (candidate.l4_key and other.l4_key
                and candidate.l4_key[:2] == other.l4_key[:2]
                and candidate.l4_key[2] != other.l4_key[2]):
            found.append({
                "rule": "CF-L4",
                "reason_code": self.ruleset.conflict_reason_code("CF-L4"),
                "candidate_value": candidate.l4_key,
                "matched_value": other.l4_key,
            })
        return found

    # --------------------------------------------------------------- matching

    def _layer_evidence(self, layer: str, candidate: IdentityRecord,
                        other: IdentityRecord) -> Dict[str, Any]:
        if layer == "L1":
            return {"key": "(source_portal, external_id)",
                    "candidate_value": list(candidate.l1_key),
                    "matched_value": list(other.l1_key),
                    "candidate_original_source_url": candidate.original_source_url,
                    "matched_original_source_url": other.original_source_url}
        if layer == "L2":
            return {"key": "canonical_identity_url",
                    "candidate_value": candidate.l2_key,
                    "matched_value": other.l2_key,
                    "candidate_original_source_url": candidate.original_source_url,
                    "matched_original_source_url": other.original_source_url}
        if layer == "L3":
            return {"key": "(normalized_company, normalized_title, normalized_location)",
                    "candidate_value": list(candidate.l3_key),
                    "matched_value": list(other.l3_key),
                    "candidate_raw": [candidate.company, candidate.title,
                                      candidate.location],
                    "matched_raw": [other.company, other.title, other.location]}
        if layer == "L4":
            return {"key": "(ats_system, ats_tenant, requisition_id)",
                    "candidate_value": list(candidate.l4_key),
                    "matched_value": list(other.l4_key),
                    "candidate_original_source_url": candidate.original_source_url,
                    "matched_original_source_url": other.original_source_url}
        raise IdentityDriftError(f"No evidence shape for layer {layer!r}")

    def _exact_matches(self, candidate: IdentityRecord) -> Dict[str, List[IdentityRecord]]:
        lookup = {
            "L1": self.index.by_l1(candidate.l1_key),
            "L2": self.index.by_l2(candidate.l2_key),
            "L4": self.index.by_l4(candidate.l4_key),
            "L3": self.index.by_l3(candidate.l3_key),
        }
        return {layer: [r for r in records if r.record_ref != candidate.record_ref]
                for layer, records in lookup.items()}

    def _candidate_reason_codes(self, candidate: IdentityRecord) -> List[str]:
        """Why a layer could not be evaluated for this candidate at all."""
        codes: List[str] = []
        if candidate.l1_key is None:
            codes.append(self.ruleset.assert_reason_code("ID-L1-ABSENT"))
        if candidate.url is not None:
            codes.extend(self.ruleset.assert_reason_code(c)
                         for c in candidate.url.reason_codes)
        if candidate.l4_key is None:
            codes.append(self.ruleset.assert_reason_code("ID-L4-ABSENT"))
        if candidate.l3_key is None:
            codes.append(self.ruleset.assert_reason_code("ID-L3-NOT-EVALUABLE"))
        return codes

    def resolve(self, candidate: IdentityRecord,
                index: Optional[IdentityIndex] = None) -> IdentityResolution:
        """Resolve one candidate. Reads nothing, writes nothing, mutates nothing."""
        active = index if index is not None else self.index
        previous, self.index = self.index, active
        try:
            return self._resolve(candidate)
        finally:
            self.index = previous

    def _resolve(self, candidate: IdentityRecord) -> IdentityResolution:
        exact = self._exact_matches(candidate)
        matches: List[IdentityMatch] = []
        considered: List[Dict[str, Any]] = []
        seen_pairs: set = set()

        # Strongest layer first, so one pair is reported under the best evidence
        # that supports it rather than once per layer.
        for layer in self._layer_order:
            for other in exact[layer]:
                if other.record_ref in seen_pairs:
                    continue
                seen_pairs.add(other.record_ref)
                conflicts = self._conflicts(candidate, other)
                reason_codes = [self.ruleset.assert_reason_code(
                    self.ruleset.layer(layer)["reason_code"])]
                if conflicts:
                    outcome = self.UNCERTAIN
                    reason_codes.extend(c["reason_code"] for c in conflicts)
                elif layer in self._suppression_layers:
                    outcome = self.DEFINITE
                else:
                    outcome = self.PROBABLE
                matches.append(IdentityMatch(
                    layer=layer, outcome=outcome, record_ref=other.record_ref,
                    record_kind=other.record_kind, row_id=other.row_id,
                    reason_codes=reason_codes,
                    evidence=self._layer_evidence(layer, candidate, other),
                    conflicts=conflicts))

        # Near-matches. Company and title agree; the location is what decides,
        # and an absent location decides nothing (artifact NM-L3-PARTIAL).
        for other in self.index.by_company_title(candidate.normalized_company,
                                                 candidate.normalized_title):
            if other.record_ref == candidate.record_ref or other.record_ref in seen_pairs:
                continue
            seen_pairs.add(other.record_ref)
            evidence = {
                "key": "(normalized_company, normalized_title)",
                "candidate_value": [candidate.normalized_company,
                                    candidate.normalized_title],
                "candidate_normalized_location": candidate.normalized_location,
                "matched_normalized_location": other.normalized_location,
                "candidate_raw": [candidate.company, candidate.title,
                                  candidate.location],
                "matched_raw": [other.company, other.title, other.location],
            }
            if candidate.normalized_location and other.normalized_location:
                # Both evaluable and different (an equal pair is an exact L3
                # match and was already handled above): counter-evidence.
                considered.append({
                    "record_ref": other.record_ref,
                    "record_kind": other.record_kind,
                    "outcome": self.DISTINCT,
                    "reason_codes": [self.ruleset.assert_reason_code(
                        "ID-L3-LOCATION-DIFFERS")],
                    "evidence": evidence,
                })
                continue
            conflicts = self._conflicts(candidate, other)
            reason_codes = [self.ruleset.assert_reason_code("ID-L3-PARTIAL")]
            reason_codes.extend(c["reason_code"] for c in conflicts)
            matches.append(IdentityMatch(
                layer="L3", outcome=self.UNCERTAIN, record_ref=other.record_ref,
                record_kind=other.record_kind, row_id=other.row_id,
                reason_codes=reason_codes, evidence=evidence, conflicts=conflicts))

        return self._finalize(candidate, matches, considered)

    def _finalize(self, candidate: IdentityRecord, matches: List[IdentityMatch],
                  considered: List[Dict[str, Any]]) -> IdentityResolution:
        reason_codes = list(self._candidate_reason_codes(candidate))

        best: Optional[IdentityMatch] = None
        if matches:
            def rank(match: IdentityMatch):
                return (self._precedence.index(match.outcome),
                        self._layer_order.index(match.layer),
                        match.record_ref)
            best = sorted(matches, key=rank)[0]
            outcome = best.outcome
            for code in best.reason_codes:
                if code not in reason_codes:
                    reason_codes.append(code)
        else:
            outcome = self.DISTINCT
            reason_codes.insert(0, self.ruleset.assert_reason_code("ID-NO-MATCH"))

        spec = self.ruleset.outcome_by_name(outcome)
        return IdentityResolution(
            identity_version=self.ruleset.version,
            resolved_at=_utc_now_iso(),
            candidate=candidate,
            outcome=outcome,
            matched_layer=best.layer if best else None,
            matched_record_ref=best.record_ref if best else None,
            matches=matches,
            considered=considered,
            reason_codes=reason_codes,
            identity_uncertain=bool(spec["identity_uncertain"]),
            requires_human_review=bool(spec["requires_human_review"]),
            suppress_from_review=bool(spec["suppress_from_review"]),
            has_uncertain_match=any(m.outcome == self.UNCERTAIN for m in matches),
            index_counts=self.index.counts(),
        )

    # ---------------------------------------------------------------- batches

    def resolve_batch(self,
                      candidates: Sequence[IdentityRecord]) -> List[IdentityResolution]:
        """
        Resolve a run's candidates, including against each other.

        A working index is built from the base index's records, and each
        candidate joins it once resolved. That is what makes the SECOND
        occurrence of the same posting inside one run a DEFINITE_DUPLICATE
        rather than a second independent candidate - which is the behaviour
        re-running ingestion depends on (P0_SPEC 13, X7).

        The base index is never modified.
        """
        working = IdentityIndex(self.index.records)
        resolutions: List[IdentityResolution] = []
        for candidate in candidates:
            resolutions.append(self.resolve(candidate, index=working))
            working.add(candidate)
        return resolutions


def resolve_candidate(candidate: IdentityRecord, index: IdentityIndex,
                      ruleset: Optional[IdentityRuleset] = None) -> IdentityResolution:
    return IdentityResolver(index, ruleset).resolve(candidate)
