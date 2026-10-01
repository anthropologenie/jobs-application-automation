"""
Loader and interpreter primitives for the data-driven v0.2 policy artifact.

The artifact declares ordered rule tables whose `when` clauses are matched
against fact summaries. This module owns the tiny predicate language and the
drift guards that make a malformed or divergent artifact fail loudly:

  * only PASS / FAIL / UNKNOWN may appear as eligibility verdicts;
  * every flag a rule emits must be registered as review-routing or informational;
  * every `$param` reference must resolve;
  * rule ids are unique; the version is pinned.
"""

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
V01_POLICY_PATH = REPO_ROOT / "policy" / "jobops-policy-0.1.0.json"
# Every v2 policy version the engine can evaluate or replay. Adding a version is
# a new artifact plus tests; an existing artifact is never edited.
POLICY_PATHS = {
    "jobops-policy@0.2.0": REPO_ROOT / "policy" / "jobops-policy-0.2.0.json",
    "jobops-policy@0.2.1": REPO_ROOT / "policy" / "jobops-policy-0.2.1.json",
    "jobops-policy@0.2.2": REPO_ROOT / "policy" / "jobops-policy-0.2.2.json",
    "jobops-policy@0.2.3": REPO_ROOT / "policy" / "jobops-policy-0.2.3.json",
    "jobops-policy@0.2.4": REPO_ROOT / "policy" / "jobops-policy-0.2.4.json",
}
EVIDENCE_GAPS = ("missing", "known")  # OR-80: exactly two classes, no third
# The default for new evaluations. Switched to 0.2.1 on 2026-09-29 only after
# the full scratch suite (888 tests, including every 0.2.1 acceptance test)
# passed with 0.2.0 still the default (P1a §29). Switched to 0.2.2 on
# 2026-09-30 only after the P3 acceptance conditions passed with 0.2.1 still
# the default (363 P0 tests, golden on 0.2.0 / 0.2.1 / 0.2.2, frozen blind
# suite 144/144 and 12/12 sequences; P3 §50). 0.2.0 and 0.2.1 stay replayable
# via load_policy_version().
# Switched to 0.2.4 on 2026-09-30 (P6) only after Gate E passed on the frozen
# Round-2 corpus (OR-82: every eligibility dimension >= 95 %, zero unexplained false
# EXCLUDED / SHORTLIST, sequences passing) with the full suite green and 0.2.0-0.2.3
# byte-identical. 0.2.3 was never the default. No ingestion is wired: the default
# only selects the policy for local/replay tools and new evaluations.
DEFAULT_VERSION = "jobops-policy@0.2.4"
DEFAULT_POLICY_PATH = POLICY_PATHS[DEFAULT_VERSION]
EXPECTED_VERSION = "ANY_SUPPORTED"
VERDICTS = ("PASS", "FAIL", "UNKNOWN")
PRECEDENCE = ("FAIL", "UNKNOWN", "PASS")

_NUMERIC_OPS = {
    "lt": lambda a, b: a < b,
    "lte": lambda a, b: a <= b,
    "gt": lambda a, b: a > b,
    "gte": lambda a, b: a >= b,
}


class PolicyDriftError(RuntimeError):
    """The artifact and this interpreter disagree. Evaluation stops."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class PolicyV02:
    """Read-only accessor over the parsed v0.2 artifact."""

    def __init__(self, doc: Dict[str, Any], path: Optional[Path] = None, *,
                 expected_version: Optional[str] = EXPECTED_VERSION):
        self.doc = doc
        self.path = path
        self.version = doc["artifact"]["ruleset_version"]
        if expected_version == "ANY_SUPPORTED":
            if self.version not in POLICY_PATHS:
                raise PolicyDriftError(f"policy version {self.version!r} is not a supported v2 version")
        elif expected_version and self.version != expected_version:
            raise PolicyDriftError(
                f"policy version {self.version!r} != expected {expected_version!r}")
        self.params: Dict[str, Any] = dict(doc["parameters"])
        self.review_flags = frozenset(doc["flags"]["review_routing"])
        self.info_flags = frozenset(doc["flags"]["informational"])
        self._validate()
        self._compiled: Dict[str, Any] = {}

    # ------------------------------------------------------------ validation

    def _validate(self) -> None:
        declared = tuple(self.doc["artifact"]["verdicts"])
        if declared != VERDICTS:
            raise PolicyDriftError(f"verdict set must be exactly {VERDICTS}, got {declared}")
        if tuple(self.doc["artifact"]["precedence"]) != PRECEDENCE:
            raise PolicyDriftError("precedence must be FAIL > UNKNOWN > PASS")
        overlap = self.review_flags & self.info_flags
        if overlap:
            raise PolicyDriftError(f"flags registered twice: {sorted(overlap)}")
        seen = set()
        dims = self.doc["eligibility_dimensions"]
        if set(dims) != set(self.doc["rules"]):
            raise PolicyDriftError("rule tables do not match eligibility_dimensions")
        for dim in dims:
            table = self.doc["rules"][dim]
            if not table or table[-1]["when"] != {}:
                raise PolicyDriftError(f"{dim}: rule table must end with a catch-all rule")
            for rule in table:
                rid = rule["rule_id"]
                if rid in seen:
                    raise PolicyDriftError(f"duplicate rule id {rid}")
                seen.add(rid)
                if rule["verdict"] not in VERDICTS:
                    raise PolicyDriftError(f"{rid}: verdict {rule['verdict']!r} is not an eligibility verdict")
                for flag in rule.get("flags", []):
                    self.assert_flag(flag, rid)
                self._check_params(rule["when"], rid)
                if self.params.get("completeness_counts_missing_only"):
                    gap = rule.get("evidence_gap")
                    if rule["verdict"] == "UNKNOWN" and gap not in EVIDENCE_GAPS:
                        raise PolicyDriftError(f"{rid}: UNKNOWN rule needs evidence_gap in {EVIDENCE_GAPS}")
                    if rule["verdict"] != "UNKNOWN" and gap is not None:
                        raise PolicyDriftError(f"{rid}: evidence_gap is only for UNKNOWN rules")
        for rule in self.doc["lanes"]["rules"]:
            if rule["lane"] not in self.doc["lanes"]["order"]:
                raise PolicyDriftError(f"{rule['rule_id']}: unknown lane {rule['lane']}")
        for flag in ("EXPERIENCE_STRETCH",):
            self.assert_flag(flag, "experience_fit")

    def _check_params(self, when: Dict[str, Any], rid: str) -> None:
        for value in when.values():
            if isinstance(value, dict):
                for op, operand in value.items():
                    if isinstance(operand, str) and operand.startswith("$"):
                        if operand[1:] not in self.params:
                            raise PolicyDriftError(f"{rid}: unknown parameter {operand}")

    def assert_flag(self, flag: str, where: str = "") -> None:
        if flag not in self.review_flags and flag not in self.info_flags:
            raise PolicyDriftError(f"{where}: flag {flag!r} is not registered")

    # --------------------------------------------------------------- access

    def param(self, name: str) -> Any:
        return self.params[name]

    def resolve(self, operand: Any) -> Any:
        if isinstance(operand, str) and operand.startswith("$"):
            return self.params[operand[1:]]
        return operand

    @property
    def dimensions(self) -> List[str]:
        return list(self.doc["eligibility_dimensions"])

    def rules(self, dimension: str) -> List[Dict[str, Any]]:
        return self.doc["rules"][dimension]

    def section(self, name: str) -> Any:
        return self.doc[name]

    def regex(self, key: str, pattern: str) -> "re.Pattern[str]":
        cache_key = (key, pattern)
        if cache_key not in self._compiled:
            langs = "|".join(self.doc["lexicon"]["language"]["names"])
            self._compiled[cache_key] = re.compile(pattern.replace("{langs}", langs), re.I)
        return self._compiled[cache_key]

    def regexes(self, key: str, patterns: List[str]) -> List["re.Pattern[str]"]:
        return [self.regex(key, p) for p in patterns]

    # ------------------------------------------------------------- matching

    def matches(self, when: Dict[str, Any], facts: Dict[str, Any]) -> bool:
        for field, expected in when.items():
            actual = facts.get(field)
            if isinstance(expected, dict):
                for op, operand in expected.items():
                    if op == "in":
                        if actual not in operand:
                            return False
                    elif op == "is_null":
                        if (actual is None) != bool(operand):
                            return False
                    elif op in _NUMERIC_OPS:
                        if actual is None or not _NUMERIC_OPS[op](actual, self.resolve(operand)):
                            return False
                    else:
                        raise PolicyDriftError(f"unknown predicate operator {op!r}")
            elif actual != expected:
                return False
        return True

    def first_match(self, dimension: str, facts: Dict[str, Any]) -> Dict[str, Any]:
        for rule in self.rules(dimension):
            if self.matches(rule["when"], facts):
                return rule
        raise PolicyDriftError(f"{dimension}: no rule matched (catch-all missing)")


@lru_cache(maxsize=8)
def _load(path_str: str) -> PolicyV02:
    path = Path(path_str)
    with open(path, "r", encoding="utf-8") as f:
        return PolicyV02(json.load(f), path)


def load_policy_v02(path: Optional[Path] = None) -> PolicyV02:
    """The default v2 policy (DEFAULT_VERSION), or the artifact at `path`."""
    return _load(str(Path(path) if path else DEFAULT_POLICY_PATH))


def load_policy_version(version: str) -> PolicyV02:
    """A specific supported version, e.g. for replay under jobops-policy@0.2.0."""
    if version not in POLICY_PATHS:
        raise PolicyDriftError(f"unsupported policy version {version!r}")
    policy = _load(str(POLICY_PATHS[version]))
    if policy.version != version:
        raise PolicyDriftError(f"{POLICY_PATHS[version]} declares {policy.version!r}, expected {version!r}")
    return policy


def policy_from_doc(doc: Dict[str, Any], *, expected_version: Optional[str] = None) -> PolicyV02:
    """Build a policy from an in-memory document (used by replay tests with a variant policy)."""
    return PolicyV02(doc, None, expected_version=expected_version)
