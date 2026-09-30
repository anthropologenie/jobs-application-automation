#!/usr/bin/env python3
"""
Review Ruleset Loader - P0-08 artifact access layer

Loads and version-pins review/jobops-review-0.1.0.json, which declares the
review PRESENTATION contract: the lanes, how a verdict maps to one, how a lane
is ordered, what a human decision may record, and what the queue is forbidden
to do.

This module is the only place that reads the review artifact. It holds no
policy: a verdict, a reason code, a threshold and a work-mode value are read
from the candidate ledger exactly as the gate wrote them, and the identity
layer's suppression grades are read from the identity artifact. Nothing in
P0-08 redeclares any of them.

Authority:
    review/jobops-review-0.1.0.json    (review_version jobops-review@0.1.0)
    P0_IMPLEMENTATION_SPEC.md 9        (review queue)

Author: Karthik Shetty
Created: 2026-09-02
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

EXPECTED_REVIEW_VERSION = "jobops-review@0.1.0"
DEFAULT_REVIEW_PATH = Path(__file__).resolve().parent / "jobops-review-0.1.0.json"


class ReviewDriftError(RuntimeError):
    """
    Raised when the review artifact and this implementation disagree.

    A lane the queue does not know how to fill, a decision kind it does not
    know how to record, or an unexpected artifact version stops queue
    construction rather than being skipped. A review surface that silently
    drops a lane is a review surface that hides candidates.
    """


class ReviewRuleset:
    """Read-only accessor for the versioned review artifact."""

    def __init__(self, path: Optional[Path] = None, *,
                 expected_version: str = EXPECTED_REVIEW_VERSION):
        self.path = Path(path) if path else DEFAULT_REVIEW_PATH
        if not self.path.exists():
            raise FileNotFoundError(f"Review artifact not found: {self.path}")

        with open(self.path, "r", encoding="utf-8") as f:
            self._doc: Dict[str, Any] = json.load(f)

        self.version: str = self._doc["artifact"]["review_version"]
        if expected_version and self.version != expected_version:
            raise ReviewDriftError(
                f"Review artifact version mismatch: artifact is {self.version!r}, "
                f"this implementation is written against {expected_version!r}."
            )
        logger.info("Loaded review ruleset %s from %s", self.version, self.path)

    # ----------------------------------------------------------------- lanes

    @property
    def lanes(self) -> List[Dict[str, Any]]:
        return list(self._doc["lanes"])

    @property
    def lane_ids(self) -> List[str]:
        return [lane["id"] for lane in self._doc["lanes"]]

    def lane(self, lane_id: str) -> Dict[str, Any]:
        for lane in self._doc["lanes"]:
            if lane["id"] == lane_id:
                return dict(lane)
        raise ReviewDriftError(f"Review artifact declares no lane {lane_id!r}")

    @property
    def active_lane_ids(self) -> List[str]:
        """
        The lanes the human is actually asked to work through.

        SUPPRESSED_DUPLICATE is declared inactive: its members are retained and
        retrievable, but they are not put in front of the human again.
        """
        return [lane["id"] for lane in self._doc["lanes"] if lane.get("active")]

    def lane_for_verdict(self, verdict: Optional[str],
                         reason_codes: Optional[List[str]] = None) -> str:
        """
        Map a gate verdict onto a lane, using only what the artifact declares.

        A verdict this artifact cannot place is drift, not a default: silently
        bucketing an unrecognized verdict is how a candidate disappears.
        """
        if verdict is None:
            return "NOT_EVALUATED"
        codes = set(reason_codes or ())
        fallback: Optional[str] = None
        for lane in self._doc["lanes"]:
            if lane.get("verdict") != verdict:
                continue
            declared = lane.get("reason_codes_any")
            if declared is None:
                fallback = fallback or lane["id"]
                continue
            if codes.intersection(declared):
                return lane["id"]
        if fallback is not None:
            return fallback
        raise ReviewDriftError(
            f"Review artifact declares no lane for verdict {verdict!r}. "
            "A verdict with no lane would vanish from the queue.")

    def order_key_spec(self, lane_id: str) -> List[str]:
        return list(self.lane(lane_id)["order_by"])

    # ------------------------------------------------------------- decisions

    @property
    def decision_kinds(self) -> List[Dict[str, Any]]:
        return list(self._doc["decision_kinds"])

    @property
    def decision_kind_ids(self) -> List[str]:
        return [kind["id"] for kind in self._doc["decision_kinds"]]

    def decision_kind(self, kind_id: str) -> Dict[str, Any]:
        for kind in self._doc["decision_kinds"]:
            if kind["id"] == kind_id:
                return dict(kind)
        raise ReviewDriftError(
            f"Review artifact declares no decision kind {kind_id!r}. Decision "
            "kinds are declared in the artifact, never invented in code.")

    def required_fields(self, kind_id: str) -> List[str]:
        return list(self.decision_kind(kind_id).get("requires", []))

    # ------------------------------------------------------------ duplicates

    def duplicate_presentation(self, outcome: str) -> Dict[str, Any]:
        table = self._doc["duplicate_presentation"]
        if outcome not in table:
            raise ReviewDriftError(
                f"Review artifact declares no presentation for identity outcome "
                f"{outcome!r}.")
        return dict(table[outcome])

    def suppresses(self, outcome: str, layer: Optional[str]) -> bool:
        """
        Whether an identity outcome removes a candidate from the active queue.

        Both conditions come from the artifact: the outcome must be declared
        suppressing, AND the matching layer must be one the artifact lists.
        P0-08 never decides on its own that a layer is strong enough.
        """
        rule = self.duplicate_presentation(outcome)
        if not rule.get("suppress_from_active_queue"):
            return False
        allowed = rule.get("requires_layer_in")
        if allowed is None:
            return True
        return layer in allowed

    # --------------------------------------------------------------- sources

    @property
    def source_of_truth(self) -> Dict[str, Any]:
        return dict(self._doc["source_of_truth"])

    @property
    def prohibited(self) -> List[str]:
        return list(self._doc["prohibited"])

    @property
    def raw(self) -> Dict[str, Any]:
        return self._doc


def load_review_ruleset(path: Optional[Path] = None) -> ReviewRuleset:
    return ReviewRuleset(path)
