#!/usr/bin/env python3
"""
Identity Ruleset Loader - P0-07 artifact access layer

Loads and version-pins identity/jobops-identity-0.1.0.json, which is the
identity authority for cross-source deduplication.

This module is the ONLY place that reads the identity artifact. No host rule,
tracking parameter, legal suffix, ATS pattern, outcome name, layer confidence
or reason code is defined here - every one of them is read from the artifact,
so a deduplication decision can be explained by reading a JSON file rather
than by reading Python.

Authority:
    identity/jobops-identity-0.1.0.json   (identity_version jobops-identity@0.1.0)
    P0_IMPLEMENTATION_SPEC.md 8           (layers, uncertainty, dedup scope)

Explicitly NOT an authority for policy. Eligibility thresholds, work-mode
vocabulary and verdict rules live in policy/jobops-policy-0.1.0.json and are
never read here. data/resume_config.json is never read anywhere.

Author: Karthik Shetty
Created: 2026-09-02
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Pinned deliberately, for the same reason the policy loader pins its ruleset:
# adopting a new identity version is an authorized decision plus a test pass,
# not a file drop that silently changes what counts as the same job.
EXPECTED_IDENTITY_VERSION = "jobops-identity@0.1.0"

DEFAULT_IDENTITY_PATH = Path(__file__).resolve().parent / "jobops-identity-0.1.0.json"


class IdentityDriftError(RuntimeError):
    """
    Raised when the identity artifact and this implementation disagree.

    Divergence must be loud. A layer the resolver does not know how to
    evaluate, or an unexpected artifact version, stops resolution rather than
    being skipped: silently skipping an identity layer is how a deduplicator
    starts asserting sameness it cannot support.
    """


class IdentityRuleset:
    """Read-only accessor for the versioned identity artifact."""

    def __init__(self, path: Optional[Path] = None, *,
                 expected_version: str = EXPECTED_IDENTITY_VERSION):
        self.path = Path(path) if path else DEFAULT_IDENTITY_PATH
        if not self.path.exists():
            raise FileNotFoundError(f"Identity artifact not found: {self.path}")

        with open(self.path, "r", encoding="utf-8") as f:
            self._doc: Dict[str, Any] = json.load(f)

        self.version: str = self._doc["artifact"]["identity_version"]
        if expected_version and self.version != expected_version:
            raise IdentityDriftError(
                f"Identity artifact version mismatch: artifact is "
                f"{self.version!r}, this implementation is written against "
                f"{expected_version!r}. Adopting a new identity version is an "
                "authorized change plus a test pass, not an automatic upgrade."
            )

        declared = {layer["id"] for layer in self._doc["layers"]}
        if declared != {"L1", "L2", "L3", "L4"}:
            raise IdentityDriftError(
                f"Identity artifact declares layers {sorted(declared)}; this "
                "resolver implements exactly L1, L2, L3 and L4 (P0_SPEC 8.2)."
            )

        logger.info("Loaded identity ruleset %s from %s", self.version, self.path)

    # ---------------------------------------------------------------- layers

    @property
    def layers(self) -> List[Dict[str, Any]]:
        return list(self._doc["layers"])

    def layer(self, layer_id: str) -> Dict[str, Any]:
        for entry in self._doc["layers"]:
            if entry["id"] == layer_id:
                return entry
        raise IdentityDriftError(f"Identity artifact declares no layer {layer_id!r}")

    def suppression_grade_layers(self) -> List[str]:
        """
        The layers P0_SPEC 8.4 grants suppression confidence: L1, L2, L4.

        L3 is deliberately absent. An exact company+title+location match is
        medium confidence and becomes a probable duplicate for review.
        """
        return [e["id"] for e in self._doc["layers"] if e.get("suppression_grade")]

    def layer_order(self) -> List[str]:
        """Layers most-reliable-first, suppression-grade before L3."""
        suppression = self.suppression_grade_layers()
        rest = [e["id"] for e in self._doc["layers"] if e["id"] not in suppression]
        return suppression + rest

    # -------------------------------------------------------------- outcomes

    @property
    def outcomes(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._doc["outcomes"])

    def outcome(self, key: str) -> Dict[str, Any]:
        try:
            return dict(self._doc["outcomes"][key])
        except KeyError as exc:
            raise IdentityDriftError(
                f"Identity artifact declares no outcome {key!r}") from exc

    def outcome_name(self, key: str) -> str:
        return self.outcome(key)["name"]

    @property
    def overall_outcome_precedence(self) -> List[str]:
        """
        How a candidate's outcome is chosen across several matched records.

        DEFINITE first: a clean L1/L2/L4 match against one record is
        established evidence, and a near-match against a different record does
        not unestablish it. The near-match is retained and reported, never
        discarded and never allowed to mask the stronger match.
        """
        return list(self._doc["overall_outcome_precedence"])

    def outcome_by_name(self, name: str) -> Dict[str, Any]:
        for entry in self._doc["outcomes"].values():
            if entry["name"] == name:
                return dict(entry)
        raise IdentityDriftError(f"Unknown identity outcome {name!r}")

    # ------------------------------------------------------- canonicalization

    @property
    def url(self) -> Dict[str, Any]:
        return self._doc["url_canonicalization"]

    @property
    def tracking_parameters(self) -> set:
        return {p.lower() for p in self.url["tracking_parameters"]}

    @property
    def host_families(self) -> List[Dict[str, Any]]:
        return list(self.url["host_families"])

    @property
    def bare_listing_patterns(self) -> List[re.Pattern]:
        return [re.compile(p) for p in self.url["bare_listing_paths"]]

    @property
    def allowed_schemes(self) -> set:
        return set(self.url["allowed_schemes"])

    # ------------------------------------------------------------------- ats

    @property
    def ats_systems(self) -> List[Dict[str, Any]]:
        return list(self._doc["ats_systems"])

    # --------------------------------------------------------- normalization

    def text_rules(self, dimension: str) -> Dict[str, Any]:
        try:
            return dict(self._doc["text_normalization"][dimension])
        except KeyError as exc:
            raise IdentityDriftError(
                f"Identity artifact declares no text normalization for "
                f"{dimension!r}") from exc

    @property
    def legal_suffixes(self) -> List[str]:
        return list(self.text_rules("company")["legal_suffixes"])

    @property
    def location_unknown_tokens(self) -> set:
        return {t for t in self.text_rules("location")["unknown_tokens"]}

    # ----------------------------------------------------------------- rules

    @property
    def near_match_rules(self) -> List[Dict[str, Any]]:
        return list(self._doc["near_match_rules"])

    @property
    def distinctness_rules(self) -> List[Dict[str, Any]]:
        return list(self._doc["distinctness_rules"])

    @property
    def conflict_rules(self) -> List[Dict[str, Any]]:
        return list(self._doc["conflict_rules"])

    def conflict_reason_code(self, rule_id: str) -> str:
        for rule in self._doc["conflict_rules"]:
            if rule["id"] == rule_id:
                return rule["reason_code"]
        raise IdentityDriftError(f"Identity artifact declares no conflict rule {rule_id!r}")

    @property
    def match_scope_tables(self) -> List[str]:
        return list(self._doc["match_scope"]["tables"])

    @property
    def scope_is_read_only(self) -> bool:
        return bool(self._doc["match_scope"]["read_only"])

    # ---------------------------------------------------------- reason codes

    @property
    def reason_code_registry(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._doc["reason_codes"])

    def assert_reason_code(self, code: str) -> str:
        """A code the registry does not declare is a drift, not a new code."""
        if code not in self._doc["reason_codes"]:
            raise IdentityDriftError(
                f"Reason code {code!r} is not in the identity artifact's registry. "
                "Reason codes are declared in the artifact, never invented in code.")
        return code

    @property
    def raw(self) -> Dict[str, Any]:
        return self._doc


def load_identity_ruleset(path: Optional[Path] = None) -> IdentityRuleset:
    return IdentityRuleset(path)
