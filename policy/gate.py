#!/usr/bin/env python3
"""
P0-02 Hard Eligibility Gate

Deterministic, pre-scoring policy enforcement. Evaluates a posting against the
versioned policy artifact and emits exactly one primary verdict - PASS, UNKNOWN
or FAIL - with the reason codes, rule ids and provenance needed to explain it.

The gate is a policy-enforcement mechanism. It is not a scorer, not an
Opportunity Quality model, and not a ranking model. It has no dependency on
scrapers/simple_scorer.py and no code path by which a score can revive a FAIL
(P0_IMPLEMENTATION_SPEC.md 2.2).

Every policy value - the compensation threshold, rule ids, reason codes,
verdict precedence, work-mode mapping, dormancy of the conversion rule - is
read from policy/jobops-policy-0.1.0.json via policy.ruleset. Nothing policy
-bearing is hardcoded in this module, and data/resume_config.json is never read.

Usage:
    from policy import HardEligibilityGate

    gate = HardEligibilityGate()
    result = gate.evaluate_posting({
        "candidate_id": "job-123",
        "work_mode_text": "Fully remote",
        "compensation_text": "Rs 22 LPA",
    })
    result.verdict        # the primary verdict
    result.reason_codes   # the codes the artifact's registry defines
    result.rules_fired    # the rule ids that produced it

Author: Karthik Shetty
Created: 2026-08-29
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .normalization import (
    EvidenceNormalizer,
    NormalizedCompensation,
    NormalizedPosting,
)
from .ruleset import PolicyDriftError, PolicyRuleset, load_ruleset

logger = logging.getLogger(__name__)


# Predicate strings exactly as declared in the policy artifact, mapped to their
# evaluation. Keyed on the literal declaration so that a predicate the artifact
# introduces later has no handler here and raises PolicyDriftError instead of
# being quietly skipped.
_PredicateFn = Callable[[NormalizedCompensation, int, PolicyRuleset], bool]

_COMPENSATION_PREDICATES: Dict[str, _PredicateFn] = {
    "annual_min >= T":
        lambda c, t, r: c.annual_min is not None and c.annual_min >= t,
    "annual_max < T":
        lambda c, t, r: c.annual_max is not None and c.annual_max < t,
    "annual_min < T AND annual_max >= T":
        lambda c, t, r: (c.annual_min is not None and c.annual_max is not None
                         and c.annual_min < t <= c.annual_max),
    "currency_conversion.status != 'CONFIGURED'":
        lambda c, t, r: not r.conversion_is_configured,
    "currency_conversion.status == 'CONFIGURED'":
        lambda c, t, r: r.conversion_is_configured,
}


@dataclass
class GateResult:
    """
    One gate evaluation, carrying the provenance the artifact requires.

    Immutable in intent: re-evaluating under a new ruleset version produces a
    new GateResult and never rewrites an existing one.
    """
    candidate_id: Optional[str]
    verdict: str
    ruleset_version: str
    evaluated_at: str
    reason_codes: List[str]
    dimension_verdicts: Dict[str, str]
    rules_fired: List[str]
    normalized_work_mode: str
    normalized_compensation: Dict[str, Any]
    work_mode_provenance: Optional[Dict[str, Any]]
    compensation_provenance: Optional[Dict[str, Any]]
    requires_human_review: bool
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    unresolved_evidence: List[Dict[str, Any]] = field(default_factory=list)
    company_type_signal: Optional[str] = None

    @property
    def eligible_for_scoring(self) -> bool:
        """
        Only a PASS may proceed to scoring.

        UNKNOWN is not eligible: it goes to human review first (OR-03b). FAIL is
        never eligible at any score.
        """
        return self.verdict == "PASS"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "verdict": self.verdict,
            "ruleset_version": self.ruleset_version,
            "evaluated_at": self.evaluated_at,
            "reason_codes": list(self.reason_codes),
            "dimension_verdicts": dict(self.dimension_verdicts),
            "rules_fired": list(self.rules_fired),
            "normalized_work_mode": self.normalized_work_mode,
            "normalized_compensation": dict(self.normalized_compensation),
            "work_mode_provenance": self.work_mode_provenance,
            "compensation_provenance": self.compensation_provenance,
            "requires_human_review": self.requires_human_review,
            "evidence": list(self.evidence),
            "unresolved_evidence": list(self.unresolved_evidence),
            "company_type_signal": self.company_type_signal,
            "eligible_for_scoring": self.eligible_for_scoring,
        }


class HardEligibilityGate:
    """
    Evaluates postings against the versioned policy ruleset.

    Construction validates that this implementation and the artifact still
    agree; a disagreement raises PolicyDriftError rather than degrading to a
    partial evaluation.
    """

    def __init__(self, ruleset: Optional[PolicyRuleset] = None,
                 ruleset_path: Optional[Path] = None):
        self.ruleset = ruleset or load_ruleset(ruleset_path)
        self.normalizer = EvidenceNormalizer(self.ruleset)
        self._verify_implementation_matches_policy()

    # ----------------------------------------------------------- drift guards

    def _verify_implementation_matches_policy(self) -> None:
        """
        Fail loudly if the artifact declares something this gate cannot honour.

        Silent divergence is the failure mode this whole component exists to
        prevent, so every check here raises rather than warns.
        """
        rs = self.ruleset

        rs.precedence_order  # raises if the declared precedence is not FAIL > UNKNOWN > PASS

        known_modes = set(rs.work_mode_values)
        for rule in rs.work_mode_rules:
            mode = rule["match"]["normalized_work_mode"]
            if mode not in known_modes:
                raise PolicyDriftError(
                    f"Work-mode rule {rule['id']} matches undeclared value {mode!r}")
            self._check_reason_code(rule.get("reason_code"), rule["verdict"], rule["id"])

        known_states = set(rs.compensation_states)
        for rule in rs.compensation_rules:
            state = rule["match"].get("compensation_state")
            if state not in known_states:
                raise PolicyDriftError(
                    f"Compensation rule {rule['id']} matches undeclared state {state!r}")
            predicate = rule["match"].get("predicate")
            if predicate is not None and predicate not in _COMPENSATION_PREDICATES:
                raise PolicyDriftError(
                    f"Compensation rule {rule['id']} declares predicate "
                    f"{predicate!r}, which this gate has no handler for. Add a "
                    "handler and a test before evaluating under this ruleset."
                )
            if rule["verdict"] in rs.primary_verdicts:
                self._check_reason_code(rule.get("reason_code"), rule["verdict"], rule["id"])
            elif rule.get("active_in_this_version", True):
                # A non-primary verdict such as COMP-R8's deferral is only
                # tolerable while the rule is dormant.
                raise PolicyDriftError(
                    f"Rule {rule['id']} is active but declares non-primary "
                    f"verdict {rule['verdict']!r}, which this gate does not implement."
                )

        if rs.company_type_is_gating:
            raise PolicyDriftError(
                "Policy artifact now marks company_type as gating. OR-04 rules "
                "it non-gating and this gate implements no company-type veto. "
                "Resolve by ruling, not by code."
            )

        logger.info("Gate implementation verified against ruleset %s", rs.version)

    def _check_reason_code(self, code: Optional[str], verdict: str, rule_id: str) -> None:
        if code is None:
            return
        registered = self.ruleset.reason_code_verdict(code)
        if registered != verdict:
            raise PolicyDriftError(
                f"Rule {rule_id} emits {code!r} for verdict {verdict!r}, but the "
                f"registry records that code as {registered!r}."
            )

    # ------------------------------------------------------ dimension evaluation

    def _evaluate_work_mode(self, normalized_mode: str) -> Dict[str, Any]:
        for rule in self.ruleset.work_mode_rules:
            if rule["match"]["normalized_work_mode"] == normalized_mode:
                return {"rule_id": rule["id"], "verdict": rule["verdict"],
                        "reason_code": rule["reason_code"]}
        raise PolicyDriftError(
            f"No work-mode rule covers normalized value {normalized_mode!r}")

    def _evaluate_compensation(self, comp: NormalizedCompensation) -> Dict[str, Any]:
        """
        First declared rule whose state and predicate both match wins.

        A rule marked inactive in this ruleset version can never fire. If such a
        rule is the only match, that is a policy/implementation conflict and the
        evaluation stops - it is not silently activated.
        """
        threshold = self.ruleset.threshold_value
        blocked_by_dormant: Optional[str] = None

        for rule in self.ruleset.compensation_rules:
            if rule["match"].get("compensation_state") != comp.state:
                continue
            predicate = rule["match"].get("predicate")
            if predicate is not None:
                if not _COMPENSATION_PREDICATES[predicate](comp, threshold, self.ruleset):
                    continue
            if not rule.get("active_in_this_version", True):
                blocked_by_dormant = rule["id"]
                continue
            return {"rule_id": rule["id"], "verdict": rule["verdict"],
                    "reason_code": rule["reason_code"]}

        if blocked_by_dormant:
            raise PolicyDriftError(
                f"Compensation state {comp.state!r} matches only {blocked_by_dormant}, "
                "which is dormant in this ruleset version. Activating it requires an "
                "Owner ruling (CURRENCY-SOURCE), not a code change."
            )
        raise PolicyDriftError(
            f"No compensation rule covers state {comp.state!r} - the gate refuses "
            "to guess a verdict for an uncovered state."
        )

    def _resolve_verdict(self, dimension_verdicts: Dict[str, str]) -> str:
        """FAIL dominates UNKNOWN dominates PASS, in the order the artifact declares."""
        values = set(dimension_verdicts.values())
        for verdict in self.ruleset.precedence_order:
            if verdict in values:
                return verdict
        raise PolicyDriftError(f"No verdict resolvable from {dimension_verdicts!r}")

    # ------------------------------------------------------------------ public

    def evaluate(self, posting: NormalizedPosting) -> GateResult:
        """Evaluate an already-normalized posting. Performs no normalization."""
        wm = self._evaluate_work_mode(posting.work_mode)
        comp = self._evaluate_compensation(posting.compensation)

        dimension_verdicts = {
            "work_mode": wm["verdict"],
            "compensation": comp["verdict"],
        }
        verdict = self._resolve_verdict(dimension_verdicts)

        # A verdict is explained by the dimensions that produced it: the vetoing
        # dimensions for FAIL, the unresolved ones for UNKNOWN, both for PASS.
        # A PASS code is never emitted alongside a FAIL.
        if verdict == "PASS":
            reason_codes = [wm["reason_code"], comp["reason_code"]]
        else:
            reason_codes = [d["reason_code"] for d in (wm, comp)
                            if d["verdict"] == verdict and d["reason_code"]]

        evidence = [e.as_dict() for e in posting.evidence]
        wm_provenance = next((e for e in evidence if e["dimension"] == "work_mode"), None)
        comp_provenance = next((e for e in evidence if e["dimension"] == "compensation"), None)

        requires_review = verdict == "UNKNOWN" or bool(posting.unresolved_evidence)

        return GateResult(
            candidate_id=posting.candidate_id,
            verdict=verdict,
            ruleset_version=self.ruleset.version,
            evaluated_at=datetime.now(timezone.utc).isoformat(),
            reason_codes=reason_codes,
            dimension_verdicts=dimension_verdicts,
            rules_fired=[wm["rule_id"], comp["rule_id"]],
            normalized_work_mode=posting.work_mode,
            normalized_compensation=posting.compensation.as_dict(),
            work_mode_provenance=wm_provenance,
            compensation_provenance=comp_provenance,
            requires_human_review=requires_review,
            evidence=evidence,
            unresolved_evidence=list(posting.unresolved_evidence),
            company_type_signal=posting.company_type_signal,
        )

    def evaluate_posting(self, raw: Dict[str, Any]) -> GateResult:
        """Normalize a raw posting, then evaluate it. The usual entry point."""
        return self.evaluate(self.normalizer.normalize(raw))
