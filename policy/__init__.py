"""
JobOps Policy Package - versioned policy authority and the P0-02 hard gate.

Contents:
    jobops-policy-0.1.0.json - the versioned, machine-readable policy ruleset
                               (P0-01). The executable policy authority.
    ruleset.py               - loads and version-pins that artifact
    normalization.py         - raw posting -> canonical evidence (no verdicts)
    gate.py                  - P0-02 hard eligibility gate (verdicts only)

The gate runs BEFORE scoring. No score can revive a FAIL.

Authority: OWNER_RULINGS_LOG.md (OR-03a, OR-03b, OR-04, OQ-01, OQ-02) and
docs/Career_Strategy_and_Search_Preferences.md 4. Never data/resume_config.json.
"""

__version__ = "1.0.0"
__author__ = "Karthik Shetty"

from .gate import GateResult, HardEligibilityGate
from .normalization import (
    EvidenceItem,
    EvidenceNormalizer,
    NormalizedCompensation,
    NormalizedPosting,
)
from .ruleset import PolicyDriftError, PolicyRuleset, load_ruleset

__all__ = [
    "HardEligibilityGate",
    "GateResult",
    "EvidenceNormalizer",
    "NormalizedPosting",
    "NormalizedCompensation",
    "EvidenceItem",
    "PolicyRuleset",
    "PolicyDriftError",
    "load_ruleset",
]
