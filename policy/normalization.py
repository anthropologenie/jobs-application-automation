#!/usr/bin/env python3
"""
Evidence Normalization - raw posting fields to canonical gate inputs

Separated from policy evaluation on purpose (P0_IMPLEMENTATION_SPEC.md 2.3):
normalization does field mapping and unit/currency canonicalization; it decides
no verdicts. Its governing rule is the one the specification states for the
extractor - record what was found and where, never a value that was not found.

Normalization NEVER fills an absent value, never defaults, and never infers.
A phrase it cannot classify becomes AMBIGUOUS or UNDETERMINED, which the gate
turns into UNKNOWN - it never becomes the favourable reading.

Classification vocabulary is read from the policy artifact, not hardcoded here.

Author: Karthik Shetty
Created: 2026-08-29
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .ruleset import PolicyRuleset

logger = logging.getLogger(__name__)

# Currency symbols/codes recognised as stated by a source. Not a conversion
# table - no rate is attached to any of these (OQ-02 / CURRENCY-SOURCE).
_CURRENCY_TOKENS = {
    "₹": "INR", "rs.": "INR", "rs": "INR", "inr": "INR",
    "$": "USD", "usd": "USD", "us$": "USD",
    "€": "EUR", "eur": "EUR",
    "£": "GBP", "gbp": "GBP",
}

# Period markers as written in postings. "lpa"/"lakh per annum" is an
# annual unit, not an assumption about the figure.
_PERIOD_MARKERS = [
    ("per_annum", ["lpa", "per annum", "per year", "/year", "/yr", "p.a.", "pa.", "annually", "annual", "a year"]),
    ("per_month", ["per month", "/month", "/mo", "monthly", "a month"]),
    ("per_day",   ["per day", "/day", "daily", "a day"]),
    ("per_hour",  ["per hour", "/hour", "/hr", "hourly", "an hour"]),
]

# "LPA" and "lakh" denote lakhs of rupees - a currency-bearing Indian unit.
# Reading them as INR is unit decoding, not an inference about an unstated
# currency. A bare number with no currency token and no such unit stays
# UNDETERMINED.
_INR_UNIT_MARKERS = ["lpa", "lakh", "lakhs", "lac", "lacs"]
_LAKH = 100_000

_RANGE_SEPARATORS = ["–", "—", "-", " to ", " through "]


def _squash(text: str) -> str:
    """Lowercase, drop punctuation that only varies formatting, collapse spaces."""
    lowered = text.lower().replace("(", " ").replace(")", " ")
    lowered = re.sub(r"[^a-z0-9%$€£₹.,/\s-]", " ", lowered)
    lowered = lowered.replace("-", " ")
    return re.sub(r"\s+", " ", lowered).strip()


def _has_marker(squashed: str, marker: str) -> bool:
    """
    True when `marker` occurs in `squashed` as a token, not as a substring.

    Plain containment is unsafe for this vocabulary and fails in the favourable
    direction: "lac" occurs inside "black" and "slack", and "rs." inside "yrs.".
    Either accidental match silently rewrites a figure - a spurious lakh unit
    multiplies it by 100,000, turning a below-floor salary into a PASS, and a
    spurious INR reading turns a non-INR posting that must be UNKNOWN under
    COMP-R7 into a confirmed INR one. A digit may still abut a marker, so that
    "22lpa" reads the same as "22 lpa".
    """
    return re.search(rf"(?<![a-z]){re.escape(marker)}(?![a-z])", squashed) is not None


def _pattern_key(example: str, words: int = 4) -> str:
    """
    Turn an artifact classification example into a matching key.

    The artifact writes examples as human phrases, some carrying a parenthetical
    gloss and some a placeholder ("X", "N days in office"). A parenthetical is
    dropped as a gloss, unless the text outside it is bare "Remote" - there the
    parenthetical carries the whole qualifier ("Remote (must be within X)") and
    is the only discriminating part. Placeholders are removed, then the leading
    words are kept, so the vocabulary stays sourced from the policy artifact
    rather than being retyped here.
    """
    match = re.match(r"^([^(]*)\(([^)]*)\)", example.strip())
    if match:
        outside, inside = match.group(1).strip(), match.group(2).strip()
        example = f"{outside} {inside}" if outside.lower() == "remote" else outside

    squashed = _squash(example)
    squashed = re.sub(r"\b[xn]\b", "", squashed).strip()
    return " ".join(squashed.split()[:words])


# Distinct from None. Three-state discipline (P0_IMPLEMENTATION_SPEC.md 4.4):
# None means "the source stated none"; NOT_CAPTURED means "this run did not
# capture it" and is rendered as an absent key. Conflating the two would let a
# later reader mistake a gap in this run for a fact about the posting.
NOT_CAPTURED = object()


@dataclass
class EvidenceItem:
    """One piece of located evidence, with the provenance the spec 4.4 requires."""
    dimension: str
    evidence_class: str
    verbatim_text: Optional[str]
    source: Optional[str]
    source_ref: Optional[str] = None
    source_fetched_at: Optional[str] = None
    extractor_version: Optional[str] = None
    posting_stated_at: Any = NOT_CAPTURED

    def as_dict(self) -> Dict[str, Any]:
        record: Dict[str, Any] = {
            "dimension": self.dimension,
            "evidence_class": self.evidence_class,
            "verbatim_text": self.verbatim_text,
            "source": self.source,
            "source_ref": self.source_ref,
            "source_fetched_at": self.source_fetched_at,
            "extractor_version": self.extractor_version,
        }
        # Absent key, not null, when the posting date was never captured.
        if self.posting_stated_at is not NOT_CAPTURED:
            record["posting_stated_at"] = self.posting_stated_at
        return record


@dataclass
class NormalizedCompensation:
    """
    Canonical compensation, exactly as stated by the source.

    inr_equivalent_value stays None while no conversion source is authorized
    (OQ-02). It is never a placeholder or an estimate.
    """
    state: str
    currency: Optional[str] = None
    period: Optional[str] = None
    annual_min: Optional[int] = None
    annual_max: Optional[int] = None
    stated_value_min: Optional[float] = None
    stated_value_max: Optional[float] = None
    inr_equivalent_value: Optional[int] = None
    conversion_basis: Optional[str] = None
    conversion_date_or_validity: Optional[str] = None
    conversion_confidence_status: str = "NOT_APPLICABLE_ALREADY_INR"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "currency": self.currency,
            "period": self.period,
            "annual_min": self.annual_min,
            "annual_max": self.annual_max,
            "stated_value_min": self.stated_value_min,
            "stated_value_max": self.stated_value_max,
            "inr_equivalent_value": self.inr_equivalent_value,
            "conversion_basis": self.conversion_basis,
            "conversion_date_or_validity": self.conversion_date_or_validity,
            "conversion_confidence_status": self.conversion_confidence_status,
        }


@dataclass
class NormalizedPosting:
    """Canonical gate input. Produced here, consumed by the gate - never the reverse."""
    candidate_id: Optional[str]
    work_mode: str
    compensation: NormalizedCompensation
    company_type_signal: Optional[str] = None
    evidence: List[EvidenceItem] = field(default_factory=list)
    unresolved_evidence: List[Dict[str, Any]] = field(default_factory=list)


class EvidenceNormalizer:
    """
    Turns a raw posting into a NormalizedPosting.

    Callers that already hold structured evidence may pass it through the
    `work_mode` / `compensation` keys and skip text classification entirely.
    """

    def __init__(self, ruleset: PolicyRuleset):
        self.ruleset = ruleset
        # Checked in this order. AMBIGUOUS precedes REMOTE so that a qualified
        # phrase such as "Remote depending on location" can never fall through
        # to REMOTE, and HYBRID precedes ONSITE so "N days in office" is not
        # read as an on-site assertion.
        self._wm_patterns = [
            ("AMBIGUOUS", [_pattern_key(p) for p in ruleset.work_mode_phrases("AMBIGUOUS")]),
            ("HYBRID", [_pattern_key(p) for p in ruleset.work_mode_phrases("HYBRID")]),
            ("ONSITE", [_pattern_key(p) for p in ruleset.work_mode_phrases("ONSITE")]),
        ]
        self._non_numeric_keys = [_squash(p) for p in ruleset.non_numeric_claim_examples]

    def _provenance_fields(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        The provenance every evidence item carries regardless of dimension.

        posting_stated_at is included only when the caller actually captured it,
        so an absent key stays distinguishable from a stated null (spec 4.4).
        """
        fields: Dict[str, Any] = {"extractor_version": self.ruleset.version}
        if "posting_stated_at" in raw:
            fields["posting_stated_at"] = raw["posting_stated_at"]
        return fields

    # ---------------------------------------------------------------- work mode

    def classify_work_mode(self, text: Optional[str]) -> str:
        """
        Classify a work-mode phrase into a normalized value.

        Returns ABSENT when there is nothing to classify. Never returns REMOTE
        for a qualified or conditional phrase - there is no remote-by-default
        fallback anywhere in this method.
        """
        if not text or not text.strip():
            return "ABSENT"

        squashed = _squash(text)
        for normalized, keys in self._wm_patterns:
            for key in keys:
                if key and key in squashed:
                    return normalized

        if re.search(r"\bremote\b|\bwork from anywhere\b", squashed):
            return "REMOTE"
        return "ABSENT"

    def _normalize_work_mode(self, raw: Dict[str, Any],
                             evidence: List[EvidenceItem],
                             unresolved: List[Dict[str, Any]]) -> str:
        """
        Resolve work mode across the posting body and any portal-asserted field.

        Implements the artifact's WM-N1 conflict rule: a portal filter is not a
        posting assertion, so a disagreement resolves to AMBIGUOUS and is
        escalated - it does not silently pick either side.
        """
        if raw.get("work_mode") in self.ruleset.work_mode_values:
            evidence.append(EvidenceItem(
                dimension="work_mode",
                evidence_class="STRUCTURED_FIELD",
                verbatim_text=raw.get("work_mode_text"),
                source=raw.get("work_mode_source", "portal_structured_field"),
                source_ref=raw.get("source_ref"),
                source_fetched_at=raw.get("source_fetched_at"),
                **self._provenance_fields(raw),
            ))
            return raw["work_mode"]

        body_text = raw.get("work_mode_text")
        body_class = self.classify_work_mode(body_text)
        if body_text:
            evidence.append(EvidenceItem(
                dimension="work_mode",
                evidence_class="JD_STATEMENT",
                verbatim_text=body_text,
                source=raw.get("work_mode_source", "jd_body"),
                source_ref=raw.get("source_ref"),
                source_fetched_at=raw.get("source_fetched_at"),
                **self._provenance_fields(raw),
            ))

        portal_claim = raw.get("portal_work_mode_field")
        if not portal_claim:
            return body_class

        portal_class = self.classify_work_mode(portal_claim)
        evidence.append(EvidenceItem(
            dimension="work_mode",
            evidence_class="PORTAL_SEARCH_FILTER",
            verbatim_text=portal_claim,
            source="portal_search_result",
            source_ref=raw.get("source_ref"),
            source_fetched_at=raw.get("source_fetched_at"),
            **self._provenance_fields(raw),
        ))

        if body_class == "ABSENT":
            return portal_class
        if portal_class == "REMOTE" and body_class in ("HYBRID", "ONSITE"):
            unresolved.append({
                "rule": "WM-N1",
                "dimension": "work_mode",
                "conflict": "portal field asserts remote; posting body asserts "
                            f"{body_class.lower()}",
                "portal_verbatim": portal_claim,
                "body_verbatim": body_text,
                "resolution": "AMBIGUOUS - escalated for human review",
            })
            return "AMBIGUOUS"
        return body_class

    # ------------------------------------------------------------- compensation

    def _parse_amount(self, token: str) -> Optional[float]:
        cleaned = token.replace(",", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return None

    def parse_compensation(self, text: Optional[str]) -> NormalizedCompensation:
        """
        Parse a stated compensation phrase into canonical form.

        Resolves to a state name declared by the policy artifact. Anything that
        cannot be established from the text itself - no figure, no currency, no
        period, an unannualizable unit - resolves to a state the gate treats as
        UNKNOWN. Nothing here produces a favourable reading of missing data.
        """
        if not text or not text.strip():
            return NormalizedCompensation(state="ABSENT")

        squashed = _squash(text)

        for key in self._non_numeric_keys:
            if key and key in squashed:
                return NormalizedCompensation(state="NON_NUMERIC_CLAIM")

        numbers = re.findall(r"\d[\d,]*\.?\d*", squashed)
        if not numbers:
            # A phrase with no figure at all. It says something about pay but
            # states no amount, so it is a non-numeric claim, not an absence.
            return NormalizedCompensation(state="NON_NUMERIC_CLAIM")

        currency = None
        for token, code in _CURRENCY_TOKENS.items():
            if _has_marker(squashed, token):
                currency = code
                break

        period = None
        for candidate, markers in _PERIOD_MARKERS:
            if any(_has_marker(squashed, marker) for marker in markers):
                period = candidate
                break

        is_lakh_unit = any(_has_marker(squashed, marker) for marker in _INR_UNIT_MARKERS)
        if currency is None and is_lakh_unit:
            currency = "INR"

        if currency is None or period is None:
            return NormalizedCompensation(
                state="UNIT_UNDETERMINED", currency=currency, period=period)

        # Range vs point figure.
        # Separator is looked for in the ORIGINAL text: _squash removes en and
        # em dashes, so a range would otherwise collapse to its first figure.
        values: List[float] = []
        range_text = None
        for sep in _RANGE_SEPARATORS:
            if sep in text:
                range_text = sep
                break
        parsed = [self._parse_amount(n) for n in numbers]
        parsed = [p for p in parsed if p is not None and p > 0]
        if not parsed:
            return NormalizedCompensation(state="UNIT_UNDETERMINED",
                                          currency=currency, period=period)

        # A span carrying more figures than a point or a two-ended range can
        # account for is not resolved by picking one of them. Reading the first
        # figure of "3 yrs experience, ₹25 LPA" as the salary would veto a
        # qualifying posting; reading the largest would manufacture a PASS.
        # The artifact's discipline for a figure that cannot be established
        # from the source is UNKNOWN, not a guess (COMP-R10).
        if len(parsed) > 2 or (len(parsed) == 2 and not range_text):
            return NormalizedCompensation(state="UNIT_UNDETERMINED",
                                          currency=currency, period=period)

        if range_text and len(parsed) == 2:
            values = [min(parsed), max(parsed)]
        else:
            values = [parsed[0], parsed[0]]

        multiplier = _LAKH if is_lakh_unit else 1
        stated_min, stated_max = values[0], values[1]

        if period != "per_annum":
            # No annualization without a basis stated by the source (OQ-02).
            return NormalizedCompensation(
                state="NON_ANNUAL_NOT_ANNUALIZABLE",
                currency=currency, period=period,
                stated_value_min=stated_min, stated_value_max=stated_max,
                conversion_confidence_status="NOT_CONVERTED_NO_BASIS"
                if currency != "INR" else "NOT_APPLICABLE_ALREADY_INR",
            )

        if currency != "INR":
            return NormalizedCompensation(
                state="NON_INR_ANNUAL",
                currency=currency, period=period,
                stated_value_min=stated_min, stated_value_max=stated_max,
                inr_equivalent_value=None,
                conversion_basis=None,
                conversion_date_or_validity=None,
                conversion_confidence_status="NOT_CONVERTED_NO_BASIS",
            )

        return NormalizedCompensation(
            state="CONFIRMED_ANNUAL_INR",
            currency="INR", period="per_annum",
            annual_min=int(stated_min * multiplier),
            annual_max=int(stated_max * multiplier),
            stated_value_min=stated_min, stated_value_max=stated_max,
            conversion_confidence_status="NOT_APPLICABLE_ALREADY_INR",
        )

    def _normalize_compensation(self, raw: Dict[str, Any],
                                evidence: List[EvidenceItem]) -> NormalizedCompensation:
        evidence_class = raw.get("compensation_evidence_class")
        text = raw.get("compensation_text")
        source = raw.get("compensation_source", "jd_body")

        # A third-party estimate is not gate evidence in 0.1.0. It is recorded
        # as context; the gate still has no employer-confirmed figure.
        if evidence_class == "EXTERNAL_BENCHMARK" or source == "external":
            evidence.append(EvidenceItem(
                dimension="compensation", evidence_class="EXTERNAL_BENCHMARK",
                verbatim_text=text, source="external",
                source_ref=raw.get("compensation_source_ref"),
                source_fetched_at=raw.get("source_fetched_at"),
                **self._provenance_fields(raw),
            ))
            return NormalizedCompensation(state="EXTERNAL_BENCHMARK_ONLY")

        if isinstance(raw.get("compensation"), NormalizedCompensation):
            comp = raw["compensation"]
        elif isinstance(raw.get("compensation"), dict):
            comp = NormalizedCompensation(**raw["compensation"])
        else:
            comp = self.parse_compensation(text)

        if text:
            inferred_class = {
                "CONFIRMED_ANNUAL_INR": "EXPLICIT_RANGE"
                if comp.annual_min != comp.annual_max else "EXPLICIT_POINT",
                "NON_NUMERIC_CLAIM": "NON_NUMERIC_CLAIM",
            }.get(comp.state, "EXPLICIT_POINT")
            evidence.append(EvidenceItem(
                dimension="compensation",
                evidence_class=evidence_class or inferred_class,
                verbatim_text=text, source=source,
                source_ref=raw.get("compensation_source_ref"),
                source_fetched_at=raw.get("source_fetched_at"),
                **self._provenance_fields(raw),
            ))
        return comp

    # ------------------------------------------------------------------ public

    def normalize(self, raw: Dict[str, Any]) -> NormalizedPosting:
        """Normalize one raw posting. Performs no policy evaluation."""
        evidence: List[EvidenceItem] = []
        unresolved: List[Dict[str, Any]] = []

        work_mode = self._normalize_work_mode(raw, evidence, unresolved)
        compensation = self._normalize_compensation(raw, evidence)

        company_type = raw.get("company_type_signal")
        if company_type is not None and company_type not in self.ruleset.company_type_values:
            company_type = "UNKNOWN"

        return NormalizedPosting(
            candidate_id=raw.get("candidate_id"),
            work_mode=work_mode,
            compensation=compensation,
            company_type_signal=company_type,
            evidence=evidence,
            unresolved_evidence=unresolved,
        )
