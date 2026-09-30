#!/usr/bin/env python3
"""
Evidence location for LinkedIn postings, and the work-mode -> is_remote mapping

Two jobs, both of them extraction rather than policy:

  1. LOCATE the verbatim spans in a posting that talk about work mode and
     compensation, so the policy normalizer has something exact to classify.
     The vocabulary used to decide whether a span talks about work mode is the
     policy artifact's own - reached through EvidenceNormalizer.classify_work_mode
     - so this module holds no work-mode phrase list of its own.

  2. MAP a normalized work mode onto the legacy opportunities.is_remote boolean
     at the one place that boolean is written, without letting the boolean
     become the system of record.

Nothing here decides a verdict. Nothing here parses a salary threshold. The
gate (policy/gate.py) remains the only policy authority, and this module never
reads data/resume_config.json.

Why a span locator exists at all
--------------------------------
EvidenceNormalizer classifies a phrase. A LinkedIn job description is not a
phrase - it is several thousand characters in which one sentence may mention
work mode and another may mention pay. Handing the whole description to the
classifier would let an incidental word anywhere in the posting decide the work
mode. So the description is split into spans, each span is classified with the
artifact's vocabulary, and one span is selected as the evidence - verbatim,
never paraphrased (P0_SPEC 4.4).

Selection can never favour REMOTE
---------------------------------
When several spans classify differently, the selected span is the one whose
class comes first in AMBIGUOUS, HYBRID, ONSITE, REMOTE. That is the same
precedence EvidenceNormalizer already applies within a single string, applied
across spans: a qualified or conditional phrase, or a stated office
requirement, is never overridden by an unconditional "remote" found elsewhere
in the same posting. The artifact's hard rule - "Ambiguous work-mode language
must never resolve to REMOTE" - therefore holds across a multi-sentence body,
not only within one sentence.

Author: Karthik Shetty
Created: 2026-08-31
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# Split a description into spans on line breaks, sentence terminators, bullets
# and pipe separators. Each resulting unit is a span that can be quoted whole.
_SPAN_SPLIT = re.compile(r"(?<=[.!?;])\s+|[\n\r•·]+|\s\|\s")

# Work-mode selection precedence across spans. REMOTE is deliberately last.
_WORK_MODE_PRECEDENCE = ("AMBIGUOUS", "HYBRID", "ONSITE", "REMOTE")

# A span is compensation evidence if it names compensation, or if it carries a
# currency/lakh marker next to a figure. Deliberately narrow: "package" and
# "pay" are excluded because they occur constantly in engineering prose, and a
# false compensation span next to unrelated digits is how a gate starts
# evaluating a version number as a salary.
_COMP_KEYWORDS = (
    "salary", "compensation", "ctc", "remuneration", "cost to company",
    "pay range", "annual pay", "base pay",
)
_COMP_FIGURE_MARKERS = (
    "₹", "rs.", "rs ", "inr", "$", "usd", "€", "eur", "£", "gbp",
    "lpa", "lakh", "lakhs", "lac ", "lacs",
)

# Compensation states in which the source actually stated a figure with an
# identifiable currency. Preferred over a non-numeric claim because 4.2 makes
# them gate-admissible evidence and a non-numeric claim explicitly is not.
_FIGURE_BEARING_STATES = (
    "CONFIRMED_ANNUAL_INR", "NON_INR_ANNUAL", "NON_ANNUAL_NOT_ANNUALIZABLE",
)

MAX_SPAN_CHARS = 600


@dataclass
class LocatedSpan:
    """One verbatim span located in a posting, with where it came from."""
    text: str
    source: str          # jd_body | portal_search_result | portal_structured_field
    field_name: str
    classification: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {"verbatim_text": self.text, "source": self.source,
                "field_name": self.field_name, "classification": self.classification}


def split_spans(text: Optional[str]) -> List[str]:
    """Split a body of text into quotable spans. Order is document order."""
    if not text:
        return []
    spans: List[str] = []
    for chunk in _SPAN_SPLIT.split(text):
        if chunk is None:
            continue
        cleaned = chunk.strip()
        if cleaned:
            spans.append(cleaned[:MAX_SPAN_CHARS])
    return spans


# --------------------------------------------------------------------- work mode

def locate_work_mode_spans(normalizer, text: Optional[str], *, source: str,
                           field_name: str) -> List[LocatedSpan]:
    """
    Every span in `text` that the policy vocabulary recognises as work mode.

    Classification is delegated to EvidenceNormalizer, so the recognised
    vocabulary is exactly what policy/jobops-policy-0.1.0.json declares.
    """
    located: List[LocatedSpan] = []
    for span in split_spans(text):
        classification = normalizer.classify_work_mode(span)
        if classification != "ABSENT":
            located.append(LocatedSpan(text=span, source=source,
                                       field_name=field_name,
                                       classification=classification))
    return located


def select_work_mode_span(spans: List[LocatedSpan]) -> Optional[LocatedSpan]:
    """
    Choose the evidence span, under a precedence that never favours REMOTE.

    Within a class, document order decides, so the selection is deterministic.
    """
    for target in _WORK_MODE_PRECEDENCE:
        for span in spans:
            if span.classification == target:
                return span
    return None


# ------------------------------------------------------------------ compensation

def _is_compensation_span(span: str) -> bool:
    lowered = span.lower()
    if any(keyword in lowered for keyword in _COMP_KEYWORDS):
        return True
    has_digit = any(ch.isdigit() for ch in lowered)
    return has_digit and any(marker in lowered for marker in _COMP_FIGURE_MARKERS)


def locate_compensation_spans(text: Optional[str], *, source: str,
                              field_name: str) -> List[LocatedSpan]:
    """Every span that talks about compensation, in document order."""
    return [LocatedSpan(text=span, source=source, field_name=field_name)
            for span in split_spans(text) if _is_compensation_span(span)]


def select_compensation_span(normalizer,
                             spans: List[LocatedSpan]) -> Optional[LocatedSpan]:
    """
    Choose the compensation evidence span.

    A span in which the source stated a figure with an identifiable currency is
    preferred over one that only claims pay is "competitive": 4.2 makes the
    first gate-admissible and the second explicitly not. Among figure-bearing
    spans, document order decides - the largest figure is never sought, because
    picking the largest is how a posting gets talked into a PASS.
    """
    for span in spans:
        state = normalizer.parse_compensation(span.text).state
        span.classification = state
        if state in _FIGURE_BEARING_STATES:
            return span
    return spans[0] if spans else None


# -------------------------------------------------- work mode -> legacy boolean

def is_remote_flag(normalized_work_mode: Optional[str]) -> int:
    """
    Map a normalized work mode onto opportunities.is_remote.

    ONLY a confirmed REMOTE sets the flag. HYBRID and ONSITE are vetoed work
    modes; AMBIGUOUS and ABSENT are unresolved, and the artifact's hard rule is
    that ambiguous work-mode language must never resolve to REMOTE. A boolean
    cannot represent "unresolved", so the unresolved cases take the value that
    asserts nothing - 0 - and the normalized enum stays the system of record
    for the decision (P0_SPEC 4.3, inventory finding F4).

    The reverse mapping does not exist and must not be written: is_remote = 0
    means "not confirmed remote", never "confirmed not remote".
    """
    return 1 if normalized_work_mode == "REMOTE" else 0


def work_mode_from_candidate_fields(normalizer, *, location: Optional[str],
                                    description: Optional[str],
                                    portal_work_mode: Optional[str] = None
                                    ) -> Tuple[str, List[LocatedSpan]]:
    """
    Derive the normalized work mode from the fields a candidate row carries.

    Used by ingestion and by the scraped_jobs -> opportunities bridge, so both
    reach the same answer from the same evidence rather than each inventing a
    rule. The posting body outranks the portal's location string; a portal
    claim of remote against a body that says hybrid or on-site resolves to
    AMBIGUOUS under the artifact's WM-N1, which the policy normalizer applies.
    """
    body_spans = locate_work_mode_spans(normalizer, description,
                                        source="jd_body", field_name="description")
    location_spans = locate_work_mode_spans(normalizer, location,
                                            source="portal_search_result",
                                            field_name="location")
    selected_body = select_work_mode_span(body_spans)
    selected_location = select_work_mode_span(location_spans)

    portal_claim = (selected_location.text if selected_location
                    else (portal_work_mode or None))

    raw: Dict[str, Any] = {}
    if selected_body:
        raw["work_mode_text"] = selected_body.text
    if portal_claim:
        raw["portal_work_mode_field"] = portal_claim

    normalized = normalizer.normalize(raw)
    return normalized.work_mode, body_spans + location_spans
