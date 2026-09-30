#!/usr/bin/env python3
"""
Policy Ruleset Loader - P0-01 artifact access layer

Loads and validates the versioned, machine-readable policy ruleset that is the
executable policy authority for the P0 hard eligibility gate.

This module is the ONLY place that reads the policy artifact. No threshold,
reason code, rule id, or verdict value is defined here - every one of them is
read from the artifact. Code in this repository must not hardcode policy
constants; it asks this module instead.

Authority:
    policy/jobops-policy-0.1.0.json  (ruleset_version jobops-policy@0.1.0)
    OWNER_RULINGS_LOG.md             (OR-03a, OR-03b, OR-04, OQ-01, OQ-02)

Explicitly NOT an authority for policy:
    data/resume_config.json - stale configuration, superseded by OR-03a.
    This module never reads it.

Author: Karthik Shetty
Created: 2026-08-29
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# The ruleset this implementation was written and tested against. Pinned
# deliberately: a newer ruleset version must not be picked up silently, because
# adopting one is an authorized decision plus a test pass, not a file drop.
EXPECTED_RULESET_VERSION = "jobops-policy@0.1.0"

DEFAULT_RULESET_PATH = Path(__file__).resolve().parent / "jobops-policy-0.1.0.json"


class PolicyDriftError(RuntimeError):
    """
    Raised when the policy artifact and this implementation disagree.

    This exception exists so that divergence is loud. A rule the gate does not
    know how to evaluate, a dormant rule that became live, or an unexpected
    ruleset version must stop evaluation rather than be silently skipped -
    silently skipping a rule is exactly how a gate starts lying.
    """


class PolicyRuleset:
    """
    Read-only accessor for the versioned policy artifact.

    Every value the gate needs comes from here, so there is one policy source
    and one place to look when a verdict has to be explained.
    """

    def __init__(self, path: Optional[Path] = None, *,
                 expected_version: str = EXPECTED_RULESET_VERSION):
        self.path = Path(path) if path else DEFAULT_RULESET_PATH

        if not self.path.exists():
            raise FileNotFoundError(f"Policy ruleset not found: {self.path}")

        with open(self.path, "r", encoding="utf-8") as f:
            self._doc: Dict[str, Any] = json.load(f)

        self.version: str = self._doc["artifact"]["ruleset_version"]
        if expected_version and self.version != expected_version:
            raise PolicyDriftError(
                f"Ruleset version mismatch: artifact is {self.version!r}, this "
                f"implementation is written against {expected_version!r}. "
                "Adopting a new ruleset version is an authorized change plus a "
                "test pass, not an automatic upgrade."
            )

        logger.info("Loaded policy ruleset %s from %s", self.version, self.path)

    # ---------------------------------------------------------------- verdicts

    @property
    def primary_verdicts(self) -> List[str]:
        return list(self._doc["verdicts"]["primary"])

    @property
    def precedence_order(self) -> List[str]:
        """Verdict dominance, strongest first. Read from the artifact, not assumed."""
        rule = self._doc["verdicts"]["precedence"]["rule"]
        # "FAIL dominates UNKNOWN dominates PASS."
        order = [tok for tok in rule.replace(".", "").split() if tok in self.primary_verdicts]
        if order != ["FAIL", "UNKNOWN", "PASS"]:
            raise PolicyDriftError(
                f"Unrecognised precedence declaration: {rule!r}. The gate "
                "implements FAIL > UNKNOWN > PASS and cannot honour another order."
            )
        return order

    # ------------------------------------------------------------- compensation

    @property
    def threshold_value(self) -> int:
        return int(self._doc["dimensions"]["compensation"]["threshold"]["value"])

    @property
    def threshold_currency(self) -> str:
        return self._doc["dimensions"]["compensation"]["threshold"]["currency"]

    @property
    def threshold_period(self) -> str:
        return self._doc["dimensions"]["compensation"]["threshold"]["period"]

    @property
    def threshold_display(self) -> str:
        return self._doc["dimensions"]["compensation"]["threshold"]["display"]

    @property
    def compensation_rules(self) -> List[Dict[str, Any]]:
        return list(self._doc["dimensions"]["compensation"]["rules"])

    @property
    def compensation_states(self) -> List[str]:
        return list(self._doc["dimensions"]["compensation"]["compensation_states"])

    @property
    def non_numeric_claim_examples(self) -> List[str]:
        for rule in self.compensation_rules:
            if rule["id"] == "COMP-R4":
                return list(rule.get("examples", []))
        return []

    # ---------------------------------------------------------------- work mode

    @property
    def work_mode_rules(self) -> List[Dict[str, Any]]:
        return list(self._doc["dimensions"]["work_mode"]["rules"])

    @property
    def work_mode_values(self) -> List[str]:
        return list(self._doc["dimensions"]["work_mode"]["normalized_values"])

    @property
    def work_mode_classification(self) -> List[Dict[str, Any]]:
        return list(self._doc["dimensions"]["work_mode"]["normalization"]["classification"])

    def work_mode_phrases(self, target_class: str) -> List[str]:
        """Every example phrase the artifact classifies as `target_class`."""
        phrases: List[str] = []
        for entry in self.work_mode_classification:
            if entry["class"] != target_class:
                continue
            phrases.extend(entry.get("examples", []))
        return phrases

    # ------------------------------------------------------------- company type

    @property
    def company_type_is_gating(self) -> bool:
        return bool(self._doc["dimensions"]["company_type"]["gating"])

    @property
    def company_type_values(self) -> List[str]:
        return list(self._doc["dimensions"]["company_type"]["normalized_values"])

    # ------------------------------------------------------- currency conversion

    @property
    def currency_conversion_status(self) -> str:
        return self._doc["currency_conversion"]["status"]

    @property
    def conversion_is_configured(self) -> bool:
        return self.currency_conversion_status == "CONFIGURED"

    # ------------------------------------------------------------ reason codes

    @property
    def reason_code_registry(self) -> Dict[str, Dict[str, Any]]:
        return {entry["code"]: entry for entry in self._doc["reason_code_registry"]}

    def reason_code_verdict(self, code: str) -> str:
        try:
            return self.reason_code_registry[code]["verdict"]
        except KeyError:
            raise PolicyDriftError(f"Reason code not in registry: {code!r}") from None

    # ------------------------------------------------------------- conformance

    @property
    def validation_cases(self) -> List[Dict[str, Any]]:
        return list(self._doc["validation_cases"]["cases"])

    @property
    def raw(self) -> Dict[str, Any]:
        """The parsed artifact. Read-only by convention - do not mutate."""
        return self._doc


def load_ruleset(path: Optional[Path] = None) -> PolicyRuleset:
    """Load the pinned policy ruleset. Convenience wrapper over PolicyRuleset."""
    return PolicyRuleset(path)
