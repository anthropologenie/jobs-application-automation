#!/usr/bin/env python3
"""
P0-02 Hard Eligibility Gate - deterministic policy conformance tests

Covers the 12 conformance vectors already validated against ruleset 0.1.0, the
precedence cases, and the negative properties that make the gate trustworthy:
UNKNOWN never becomes PASS or FAIL by default, absent evidence never becomes
favourable, company type never vetoes, and the dormant conversion rule stays
dormant.

Run:
    python3 -m pytest tests/test_p0_02_gate.py -v

Authority for every expectation here is policy/jobops-policy-0.1.0.json and the
rulings it cites. No expectation is copied from data/resume_config.json.

Author: Karthik Shetty
Created: 2026-08-29
"""

import ast
import json
from pathlib import Path

import pytest

from policy import HardEligibilityGate, PolicyDriftError, load_ruleset
from policy.normalization import NormalizedCompensation
from policy.ruleset import PolicyRuleset

REPO_ROOT = Path(__file__).resolve().parent.parent
RULESET_PATH = REPO_ROOT / "policy" / "jobops-policy-0.1.0.json"


@pytest.fixture(scope="module")
def gate():
    return HardEligibilityGate()


@pytest.fixture(scope="module")
def ruleset():
    return load_ruleset()


# --------------------------------------------------------------------------
# Postings for the owner-specified vectors. Written as raw postings so the
# normalization layer is exercised too, not bypassed.
# --------------------------------------------------------------------------

REMOTE = "Fully remote"

VECTORS = [
    # id,  posting,                                                             verdict,  reason codes,                    rules
    ("1  Remote + Rs22 LPA",
     {"work_mode_text": REMOTE, "compensation_text": "₹22 LPA"},
     "PASS", ["WM-PASS-REMOTE", "COMP-PASS-AT-OR-ABOVE-FLOOR"], ["WM-R1", "COMP-R1"]),
    ("2  Remote + Rs20 LPA (at threshold)",
     {"work_mode_text": REMOTE, "compensation_text": "₹20 LPA"},
     "PASS", ["WM-PASS-REMOTE", "COMP-PASS-AT-OR-ABOVE-FLOOR"], ["WM-R1", "COMP-R1"]),
    ("3  Remote + Rs19 LPA",
     {"work_mode_text": REMOTE, "compensation_text": "₹19 LPA"},
     "FAIL", ["COMP-FAIL-BELOW-FLOOR"], ["WM-R1", "COMP-R2"]),
    ("4  Remote + unstated salary",
     {"work_mode_text": REMOTE},
     "UNKNOWN", ["COMP-UNKNOWN-ABSENT"], ["WM-R1", "COMP-R5"]),
    ("5  Remote + Rs18-24 LPA (straddles)",
     {"work_mode_text": REMOTE, "compensation_text": "₹18–24 LPA"},
     "UNKNOWN", ["COMP-UNKNOWN-RANGE-STRADDLES"], ["WM-R1", "COMP-R3"]),
    ("6  Hybrid + Rs30 LPA",
     {"work_mode_text": "Hybrid", "compensation_text": "₹30 LPA"},
     "FAIL", ["WM-FAIL-HYBRID"], ["WM-R2", "COMP-R1"]),
    ("7  On-site + Rs30 LPA",
     {"work_mode_text": "On-site", "compensation_text": "₹30 LPA"},
     "FAIL", ["WM-FAIL-ONSITE"], ["WM-R3", "COMP-R1"]),
    ("8  Remote + services company + Rs25 LPA",
     {"work_mode_text": REMOTE, "compensation_text": "₹25 LPA",
      "company_type_signal": "SERVICES_STAFFING"},
     "PASS", ["WM-PASS-REMOTE", "COMP-PASS-AT-OR-ABOVE-FLOOR"], ["WM-R1", "COMP-R1"]),
    ("9  Remote + $60,000/year",
     {"work_mode_text": REMOTE, "compensation_text": "$60,000/year"},
     "UNKNOWN", ["COMP-UNKNOWN-NO-INR-BASIS"], ["WM-R1", "COMP-R7"]),
    ("10 Remote + $30/hour, no basis",
     {"work_mode_text": REMOTE, "compensation_text": "$30/hour"},
     "UNKNOWN", ["COMP-UNKNOWN-NOT-ANNUALIZABLE"], ["WM-R1", "COMP-R9"]),
    ("11 Remote + competitive salary",
     {"work_mode_text": REMOTE, "compensation_text": "Competitive salary"},
     "UNKNOWN", ["COMP-UNKNOWN-NON-NUMERIC"], ["WM-R1", "COMP-R4"]),
    ("12 Remote + external-site-only evidence",
     {"work_mode_text": REMOTE, "compensation_text": "₹26 LPA (Glassdoor estimate)",
      "compensation_source": "external",
      "compensation_evidence_class": "EXTERNAL_BENCHMARK"},
     "UNKNOWN", ["COMP-UNKNOWN-EXTERNAL-BENCHMARK-ONLY"], ["WM-R1", "COMP-R6"]),
    # Precedence cases
    ("13 Hybrid + unstated salary",
     {"work_mode_text": "Hybrid"},
     "FAIL", ["WM-FAIL-HYBRID"], ["WM-R2", "COMP-R5"]),
    ("14 On-site + unstated salary",
     {"work_mode_text": "Work from office"},
     "FAIL", ["WM-FAIL-ONSITE"], ["WM-R3", "COMP-R5"]),
    ("15 Ambiguous work mode + Rs25 LPA",
     {"work_mode_text": "Remote depending on location", "compensation_text": "₹25 LPA"},
     "UNKNOWN", ["WM-UNKNOWN-AMBIGUOUS"], ["WM-R4", "COMP-R1"]),
    ("16 Remote + Rs19 LPA + services company",
     {"work_mode_text": REMOTE, "compensation_text": "₹19 LPA",
      "company_type_signal": "SERVICES_STAFFING"},
     "FAIL", ["COMP-FAIL-BELOW-FLOOR"], ["WM-R1", "COMP-R2"]),
    ("17 Remote + Rs25 LPA + unknown company type",
     {"work_mode_text": REMOTE, "compensation_text": "₹25 LPA",
      "company_type_signal": "UNKNOWN"},
     "PASS", ["WM-PASS-REMOTE", "COMP-PASS-AT-OR-ABOVE-FLOOR"], ["WM-R1", "COMP-R1"]),
    ("18 Remote + unknown salary + services company",
     {"work_mode_text": REMOTE, "company_type_signal": "SERVICES_STAFFING"},
     "UNKNOWN", ["COMP-UNKNOWN-ABSENT"], ["WM-R1", "COMP-R5"]),
]


@pytest.mark.parametrize("label,posting,expected_verdict,expected_codes,expected_rules",
                         VECTORS, ids=[v[0] for v in VECTORS])
def test_conformance_vectors(gate, label, posting, expected_verdict,
                             expected_codes, expected_rules):
    """Each owner-specified vector yields its verdict, reason codes and rule ids."""
    result = gate.evaluate_posting({"candidate_id": label, **posting})

    assert result.verdict == expected_verdict, f"{label}: wrong verdict"
    assert sorted(result.reason_codes) == sorted(expected_codes), f"{label}: wrong codes"
    assert result.rules_fired == expected_rules, f"{label}: wrong rules fired"
    assert result.ruleset_version == "jobops-policy@0.1.0"
    assert result.verdict in ("PASS", "UNKNOWN", "FAIL")


@pytest.mark.parametrize("label,posting,expected_verdict,_codes,_rules",
                         VECTORS, ids=[v[0] for v in VECTORS])
def test_human_review_and_scoring_eligibility(gate, label, posting, expected_verdict,
                                              _codes, _rules):
    """Every UNKNOWN requires review; only PASS is eligible for scoring."""
    result = gate.evaluate_posting({"candidate_id": label, **posting})

    if expected_verdict == "UNKNOWN":
        assert result.requires_human_review is True
    assert result.eligible_for_scoring is (expected_verdict == "PASS")


def test_artifact_validation_cases_match_gate(gate, ruleset):
    """
    The gate agrees with the conformance vectors carried inside the artifact.

    This is the drift check between P0-01's declared expectations and P0-02's
    behaviour: if either side moves, this test fails.
    """
    by_input = {
        "V-01": {"work_mode_text": REMOTE, "compensation_text": "₹22 LPA"},
        "V-02": {"work_mode_text": REMOTE, "compensation_text": "₹20 LPA"},
        "V-03": {"work_mode_text": REMOTE, "compensation_text": "₹19 LPA"},
        "V-04": {"work_mode_text": REMOTE},
        "V-05": {"work_mode_text": REMOTE, "compensation_text": "₹18–24 LPA"},
        "V-06": {"work_mode_text": "Hybrid", "compensation_text": "₹30 LPA"},
        "V-07": {"work_mode_text": "On-site", "compensation_text": "₹30 LPA"},
        "V-08": {"work_mode_text": REMOTE, "compensation_text": "₹25 LPA",
                 "company_type_signal": "SERVICES_STAFFING"},
        "V-09": {"work_mode_text": REMOTE, "compensation_text": "$60,000/year"},
        "V-10": {"work_mode_text": REMOTE, "compensation_text": "$30/hour"},
        "V-11": {"work_mode_text": REMOTE, "compensation_text": "Competitive salary"},
        "V-12": {"work_mode_text": REMOTE, "compensation_text": "₹26 LPA (estimate)",
                 "compensation_source": "external"},
    }
    assert len(ruleset.validation_cases) == 12

    for case in ruleset.validation_cases:
        posting = by_input[case["id"]]
        result = gate.evaluate_posting({"candidate_id": case["id"], **posting})

        assert result.verdict == case["expected_verdict"], case["id"]
        assert sorted(result.reason_codes) == sorted(case["expected_reason_codes"]), case["id"]
        assert result.requires_human_review == case["requires_human_review"], case["id"]
        assert result.eligible_for_scoring == case["eligible_for_scoring"], case["id"]
        assert result.rules_fired[0] == case["work_mode"]["rule"], case["id"]
        assert result.rules_fired[1] == case["compensation"]["rule"], case["id"]


# --------------------------------------------------------------------------
# UNKNOWN stays controlled - no best-case defaults anywhere
# --------------------------------------------------------------------------

MISSING_OR_AMBIGUOUS = [
    ("nothing stated at all", {}),
    ("empty strings", {"work_mode_text": "", "compensation_text": ""}),
    ("salary stated, work mode absent", {"compensation_text": "₹30 LPA"}),
    ("work mode absent, salary absent", {"company_type_signal": "PRODUCT"}),
    ("remote-friendly only", {"work_mode_text": "Remote-friendly",
                              "compensation_text": "₹30 LPA"}),
    ("location-dependent", {"work_mode_text": "Location-dependent",
                            "compensation_text": "₹30 LPA"}),
    ("remote with travel", {"work_mode_text": "Remote with occasional travel to office",
                            "compensation_text": "₹30 LPA"}),
    ("bare number, no currency or period", {"work_mode_text": REMOTE,
                                            "compensation_text": "2500000"}),
]


@pytest.mark.parametrize("label,posting", MISSING_OR_AMBIGUOUS,
                         ids=[c[0] for c in MISSING_OR_AMBIGUOUS])
def test_missing_or_ambiguous_evidence_never_passes(gate, label, posting):
    """Absent or ambiguous evidence is never read favourably - never PASS."""
    result = gate.evaluate_posting({"candidate_id": label, **posting})

    assert result.verdict != "PASS", f"{label} produced a PASS from weak evidence"
    assert result.verdict == "UNKNOWN"
    assert result.requires_human_review is True
    assert result.reason_codes, "every UNKNOWN must carry a reason code"


@pytest.mark.parametrize("phrase", [
    "Remote-friendly", "Remote-first", "Remote depending on location",
    "Location-dependent", "Remote (must be within EU)",
    "Remote with occasional travel to the office",
])
def test_conditional_remote_never_resolves_to_remote(gate, phrase):
    """No remote-by-default fallback: qualified phrasing stays AMBIGUOUS."""
    result = gate.evaluate_posting({"work_mode_text": phrase,
                                    "compensation_text": "₹30 LPA"})
    assert result.normalized_work_mode == "AMBIGUOUS"
    assert result.verdict == "UNKNOWN"
    assert "WM-UNKNOWN-AMBIGUOUS" in result.reason_codes


def test_absent_work_mode_is_unknown_not_remote(gate):
    """A missing work mode is UNKNOWN, never REMOTE - even on a remote-job source."""
    result = gate.evaluate_posting({"compensation_text": "₹30 LPA",
                                    "source_ref": "https://remoteok.com/jobs/1"})
    assert result.normalized_work_mode == "ABSENT"
    assert result.verdict == "UNKNOWN"
    assert "WM-UNKNOWN-ABSENT" in result.reason_codes


def test_unknown_is_distinguishable_from_fail(gate):
    """UNKNOWN and FAIL are different states with different codes."""
    unknown = gate.evaluate_posting({"work_mode_text": REMOTE})
    failed = gate.evaluate_posting({"work_mode_text": REMOTE,
                                    "compensation_text": "₹19 LPA"})

    assert unknown.verdict == "UNKNOWN" and failed.verdict == "FAIL"
    assert unknown.reason_codes != failed.reason_codes
    assert unknown.requires_human_review is True
    assert failed.requires_human_review is False


def test_unknown_salary_never_outranks_confirmed_qualifying(gate):
    """
    OR-03b / T-12: an absent salary yields no favourable contribution.

    The UNKNOWN candidate is not scoring-eligible while the confirmed one is, so
    it cannot be ordered above it in any shortlist built from gate output.
    """
    confirmed = gate.evaluate_posting({"candidate_id": "confirmed",
                                       "work_mode_text": REMOTE,
                                       "compensation_text": "₹25 LPA"})
    unknown = gate.evaluate_posting({"candidate_id": "unknown",
                                     "work_mode_text": REMOTE})

    assert confirmed.eligible_for_scoring is True
    assert unknown.eligible_for_scoring is False
    assert unknown.normalized_compensation["annual_min"] is None
    assert unknown.normalized_compensation["annual_max"] is None


def test_fail_is_never_scoring_eligible_at_any_compensation(gate):
    """T-18: no compensation figure revives a work-mode veto."""
    for amount in ("₹30 LPA", "₹99 LPA", "₹2,00,00,000 per annum"):
        result = gate.evaluate_posting({"work_mode_text": "Hybrid",
                                        "compensation_text": amount})
        assert result.verdict == "FAIL"
        assert result.eligible_for_scoring is False
        assert "COMP-PASS-AT-OR-ABOVE-FLOOR" not in result.reason_codes


# --------------------------------------------------------------------------
# Precedence
# --------------------------------------------------------------------------

def test_precedence_fail_dominates_unknown(gate):
    result = gate.evaluate_posting({"work_mode_text": "Hybrid"})
    assert result.dimension_verdicts == {"work_mode": "FAIL", "compensation": "UNKNOWN"}
    assert result.verdict == "FAIL"


def test_precedence_unknown_dominates_pass(gate):
    result = gate.evaluate_posting({"work_mode_text": REMOTE,
                                    "compensation_text": "Competitive salary"})
    assert result.dimension_verdicts == {"work_mode": "PASS", "compensation": "UNKNOWN"}
    assert result.verdict == "UNKNOWN"


def test_pass_dimension_never_cancels_a_fail(gate):
    result = gate.evaluate_posting({"work_mode_text": REMOTE,
                                    "compensation_text": "₹19 LPA"})
    assert result.dimension_verdicts["work_mode"] == "PASS"
    assert result.verdict == "FAIL"
    assert "WM-PASS-REMOTE" not in result.reason_codes


def test_threshold_is_inclusive_at_the_boundary(gate):
    """₹20,00,000 exactly passes; one rupee below fails."""
    at = gate.evaluate_posting({"work_mode_text": REMOTE,
                                "compensation_text": "₹20,00,000 per annum"})
    below = gate.evaluate_posting({"work_mode_text": REMOTE,
                                   "compensation_text": "₹19,99,999 per annum"})
    assert at.verdict == "PASS"
    assert below.verdict == "FAIL"


def test_straddling_range_is_neither_min_nor_max(gate):
    """OQ-01: not FAIL on the minimum, not PASS on the maximum, no midpoint."""
    result = gate.evaluate_posting({"work_mode_text": REMOTE,
                                    "compensation_text": "₹18–24 LPA"})
    assert result.verdict == "UNKNOWN"
    assert result.rules_fired[1] == "COMP-R3"
    assert result.normalized_compensation["annual_min"] == 1800000
    assert result.normalized_compensation["annual_max"] == 2400000


# --------------------------------------------------------------------------
# Company type stays a signal
# --------------------------------------------------------------------------

@pytest.mark.parametrize("company_type", [
    "SERVICES_STAFFING", "PRODUCT", "CONSULTING", "ENTERPRISE_DIRECT", "UNKNOWN", None,
])
def test_company_type_never_changes_the_verdict(gate, company_type):
    """OR-04: identical postings must not diverge at the gate on company type."""
    result = gate.evaluate_posting({"work_mode_text": REMOTE,
                                    "compensation_text": "₹25 LPA",
                                    "company_type_signal": company_type})
    assert result.verdict == "PASS"
    assert result.rules_fired == ["WM-R1", "COMP-R1"]
    assert all(not code.startswith("CT-") for code in result.reason_codes)


def test_company_type_is_recorded_but_not_gating(gate, ruleset):
    result = gate.evaluate_posting({"work_mode_text": REMOTE,
                                    "compensation_text": "₹25 LPA",
                                    "company_type_signal": "SERVICES_STAFFING"})
    assert ruleset.company_type_is_gating is False
    assert result.company_type_signal == "SERVICES_STAFFING"
    assert "company_type" not in result.dimension_verdicts


def test_gate_evaluates_exactly_two_dimensions(gate):
    """No contract, engagement-type or role-exclusion dimension exists (OR-07 open)."""
    result = gate.evaluate_posting({"work_mode_text": REMOTE,
                                    "compensation_text": "₹25 LPA",
                                    "contract_duration_months": 3,
                                    "employment_type": "contract"})
    assert set(result.dimension_verdicts) == {"work_mode", "compensation"}
    assert result.verdict == "PASS", "contract fields must not affect the P0-02 gate"


# --------------------------------------------------------------------------
# Currency: no conversion, no invented rate
# --------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected_rule", [
    ("$60,000/year", "COMP-R7"),
    ("USD 90000 per annum", "COMP-R7"),
    ("€70,000 per year", "COMP-R7"),
    ("£65,000 annually", "COMP-R7"),
    ("$30/hour", "COMP-R9"),
    ("$500/day", "COMP-R9"),
    ("$8,000 per month", "COMP-R9"),
])
def test_non_inr_compensation_is_unknown_without_conversion(gate, text, expected_rule):
    """OQ-02 / CURRENCY-SOURCE: no conversion is performed, so the answer is UNKNOWN."""
    result = gate.evaluate_posting({"work_mode_text": REMOTE, "compensation_text": text})
    assert result.verdict == "UNKNOWN"
    assert result.rules_fired[1] == expected_rule
    assert result.normalized_compensation["inr_equivalent_value"] is None
    assert result.normalized_compensation["conversion_basis"] is None


def test_comp_r8_remains_dormant(ruleset):
    """The conversion rule must not be activated by implementation."""
    r8 = next(r for r in ruleset.compensation_rules if r["id"] == "COMP-R8")
    assert r8["active_in_this_version"] is False
    assert ruleset.currency_conversion_status == "REQUIRES_CONFIGURATION"
    assert ruleset.conversion_is_configured is False


def test_no_fx_provider_or_rate_in_implementation():
    """No provider, rate table or hardcoded exchange rate was introduced."""
    doc = json.loads(RULESET_PATH.read_text(encoding="utf-8"))
    source = doc["currency_conversion"]["source"]
    assert source["provider"] is None
    assert source["cadence"] is None
    assert source["rate_table"] is None

    banned = ("exchange_rate", "usd_inr", "inr_per_usd", "fx_rate", "openexchange",
              "fixer.io", "exchangerate-api")
    for module in ("ruleset.py", "normalization.py", "gate.py"):
        text = (REPO_ROOT / "policy" / module).read_text(encoding="utf-8").lower()
        for token in banned:
            assert token not in text, f"{module} references {token}"


def test_dormant_rule_cannot_be_forced_to_fire(gate):
    """
    If a state matched only the dormant rule, the gate stops rather than convert.

    Guards the "silently activate dormant rules" failure mode directly.
    """
    class ConfiguredRuleset:
        def __init__(self, inner):
            self._inner = inner

        def __getattr__(self, name):
            return getattr(self._inner, name)

        @property
        def conversion_is_configured(self):
            return True

    forced = HardEligibilityGate.__new__(HardEligibilityGate)
    forced.ruleset = ConfiguredRuleset(gate.ruleset)
    comp = NormalizedCompensation(state="NON_INR_ANNUAL", currency="USD",
                                  period="per_annum", stated_value_min=60000,
                                  stated_value_max=60000)
    with pytest.raises(PolicyDriftError, match="dormant"):
        forced._evaluate_compensation(comp)


# --------------------------------------------------------------------------
# Policy authority and drift protection
# --------------------------------------------------------------------------

def test_threshold_comes_from_the_policy_artifact(ruleset):
    """₹20,00,000, read from the artifact - not the stale ₹18,00,000."""
    assert ruleset.threshold_value == 2_000_000
    assert ruleset.threshold_currency == "INR"
    assert ruleset.threshold_period == "per_annum"
    assert ruleset.threshold_value != 1_800_000


def test_implementation_never_reads_resume_config():
    """
    The stale ₹18L configuration is not an input to the gate (T-13).

    Checked against executable code with docstrings stripped: these modules
    mention data/resume_config.json in prose only to record that they never
    read it, so the prose must not be what the assertion inspects. The earlier
    form of this test ended in `or True` and could not fail.
    """
    for module in ("ruleset.py", "normalization.py", "gate.py"):
        path = REPO_ROOT / "policy" / module
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
                if (node.body and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)
                        and isinstance(node.body[0].value.value, str)):
                    node.body = node.body[1:]
        code = ast.unparse(tree)
        assert "resume_config" not in code, f"{module} reads resume_config.json"
        assert "1800000" not in code, f"{module} carries the stale ₹18L figure"
        assert "1_800_000" not in code, f"{module} carries the stale ₹18L figure"


def test_no_policy_constants_hardcoded_in_gate():
    """Thresholds and reason codes live in the artifact, not in the gate module."""
    text = (REPO_ROOT / "policy" / "gate.py").read_text(encoding="utf-8")
    assert "2000000" not in text
    assert "2_000_000" not in text
    assert "COMP-PASS-AT-OR-ABOVE-FLOOR" not in text
    assert "WM-FAIL-HYBRID" not in text


def test_gate_reads_the_pinned_ruleset(gate):
    assert gate.ruleset.version == "jobops-policy@0.1.0"
    assert gate.ruleset.path == RULESET_PATH


def test_version_mismatch_is_refused():
    """A different ruleset version is not adopted silently."""
    with pytest.raises(PolicyDriftError, match="version mismatch"):
        PolicyRuleset(RULESET_PATH, expected_version="jobops-policy@9.9.9")


def test_every_emitted_reason_code_is_registered(gate, ruleset):
    """T-17: no unexplained exclusion or escalation."""
    registry = ruleset.reason_code_registry
    for label, posting, expected_verdict, _codes, _rules in VECTORS:
        result = gate.evaluate_posting({"candidate_id": label, **posting})
        if result.verdict in ("FAIL", "UNKNOWN"):
            assert result.reason_codes, f"{label}: no reason code"
        for code in result.reason_codes:
            assert code in registry, f"{label}: {code} not registered"
            assert registry[code]["verdict"] == result.verdict


def test_provenance_is_returned_for_every_relied_upon_dimension(gate):
    """T-15 / T-16: verbatim text and source survive to the verdict record."""
    result = gate.evaluate_posting({
        "candidate_id": "prov-1",
        "work_mode_text": "Fully remote",
        "compensation_text": "₹22 LPA",
        "source_ref": "https://example.com/jobs/1",
        "compensation_source_ref": "https://example.com/jobs/1",
        "source_fetched_at": "2026-08-29T10:00:00+00:00",
    })
    assert result.work_mode_provenance["verbatim_text"] == "Fully remote"
    assert result.work_mode_provenance["source"] == "jd_body"
    assert result.compensation_provenance["verbatim_text"] == "₹22 LPA"
    assert result.compensation_provenance["source_fetched_at"] == "2026-08-29T10:00:00+00:00"
    assert result.rules_fired and result.ruleset_version


def test_result_is_not_a_bare_boolean(gate):
    """The gate returns policy provenance, not true/false."""
    result = gate.evaluate_posting({"work_mode_text": REMOTE, "compensation_text": "₹22 LPA"})
    payload = result.as_dict()
    for key in ("verdict", "ruleset_version", "reason_codes", "dimension_verdicts",
                "rules_fired", "normalized_work_mode", "normalized_compensation",
                "work_mode_provenance", "compensation_provenance",
                "requires_human_review", "evidence", "unresolved_evidence"):
        assert key in payload, f"missing {key}"
    assert not isinstance(result.verdict, bool)


def test_portal_filter_does_not_override_posting_body(gate):
    """WM-N1: a conflicting portal claim escalates rather than picking a side."""
    result = gate.evaluate_posting({
        "work_mode_text": "Hybrid - 3 days in office",
        "portal_work_mode_field": "remote",
        "compensation_text": "₹30 LPA",
    })
    assert result.normalized_work_mode == "AMBIGUOUS"
    assert result.verdict == "UNKNOWN"
    assert result.unresolved_evidence
    assert result.unresolved_evidence[0]["rule"] == "WM-N1"
    assert result.requires_human_review is True


def test_evaluation_is_deterministic(gate):
    """Same posting, same ruleset - identical record apart from the timestamp."""
    posting = {"candidate_id": "det-1", "work_mode_text": REMOTE,
               "compensation_text": "₹18–24 LPA"}
    first = gate.evaluate_posting(posting).as_dict()
    second = gate.evaluate_posting(posting).as_dict()
    first.pop("evaluated_at")
    second.pop("evaluated_at")
    assert first == second


def _imported_modules(path: Path) -> set:
    """Every module name the file imports, from its AST rather than its text."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
            names.update(f"{node.module or ''}.{alias.name}" for alias in node.names)
    return names


def test_gate_has_no_dependency_on_the_scorer():
    """
    P0_IMPLEMENTATION_SPEC.md 2.2: the gate must not depend on the scorer.

    Asserted against the parsed imports and the executable code, not against the
    file text: gate.py's docstring names scrapers/simple_scorer.py precisely to
    record that it is not depended upon, and a raw substring scan flags that
    sentence while a real import through an alias would slip past it.
    """
    for module in ("ruleset.py", "normalization.py", "gate.py"):
        path = REPO_ROOT / "policy" / module
        for imported in _imported_modules(path):
            assert "scraper" not in imported and "scorer" not in imported, (
                f"{module} imports {imported}")

        # Strip docstrings, then check nothing executable names the scorer.
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
                if (node.body and isinstance(node.body[0], ast.Expr)
                        and isinstance(node.body[0].value, ast.Constant)
                        and isinstance(node.body[0].value.value, str)):
                    node.body = node.body[1:]
        code = ast.unparse(tree)
        assert "simple_scorer" not in code, f"{module} references the scorer"
        assert "SimpleJobScorer" not in code, f"{module} references the scorer"


# --------------------------------------------------------------------------
# Evidence-parsing regressions
#
# Each case below produced a wrong compensation figure before the token-
# boundary and multi-figure fixes. They are kept as regressions because both
# failure modes were silent and at least one of them manufactured a PASS.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("text,expected_state,expected_min", [
    # "lac" occurs inside "black" and "slack". A spurious lakh unit multiplied
    # the figure by 100,000, turning ₹19,00,000 into ₹19,00,00,00,00,000 - a
    # below-floor salary reported as PASS.
    ("₹19,00,000 per annum, black-box testing role", "CONFIRMED_ANNUAL_INR", 1_900_000),
    ("₹19,00,000 per annum, Slack-based team", "CONFIRMED_ANNUAL_INR", 1_900_000),
    ("₹22,00,000 per annum, placement through partner", "CONFIRMED_ANNUAL_INR", 2_200_000),
])
def test_word_internal_unit_markers_do_not_inflate_a_figure(gate, text,
                                                            expected_state, expected_min):
    result = gate.evaluate_posting({"work_mode_text": REMOTE, "compensation_text": text})
    assert result.normalized_compensation["state"] == expected_state
    assert result.normalized_compensation["annual_min"] == expected_min


@pytest.mark.parametrize("text", [
    "3 yrs. exp required, $80,000 per annum",
    "5 yrs. experience, USD 90,000 per annum",
])
def test_word_internal_currency_markers_do_not_force_inr(gate, text):
    """
    "rs." occurs inside "yrs.". Matching it read a USD posting as INR and
    produced a confirmed INR verdict where COMP-R7 requires UNKNOWN.
    """
    result = gate.evaluate_posting({"work_mode_text": REMOTE, "compensation_text": text})
    assert result.verdict == "UNKNOWN"
    assert result.normalized_compensation["state"] != "CONFIRMED_ANNUAL_INR"
    assert result.normalized_compensation["annual_min"] is None


@pytest.mark.parametrize("text", [
    "3 yrs experience, ₹25 LPA",
    "₹22 LPA, 10% variable bonus",
    "₹18 to 24 LPA, 5 days a week",
])
def test_ambiguous_multi_figure_span_is_unknown_not_a_guess(gate, text):
    """
    A span carrying more figures than a point or a range accounts for is
    UNKNOWN. Picking the first figure vetoed qualifying postings; picking the
    largest would have manufactured a PASS. Neither reading is evidence.
    """
    result = gate.evaluate_posting({"work_mode_text": REMOTE, "compensation_text": text})
    assert result.verdict == "UNKNOWN"
    assert result.rules_fired[1] == "COMP-R10"
    assert result.normalized_compensation["annual_min"] is None
    assert result.normalized_compensation["annual_max"] is None


# --------------------------------------------------------------------------
# Acceptance matrix rows not otherwise exercised (P0_IMPLEMENTATION_SPEC.md 6)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("label,text,expected", [
    ("T-02 Remote + ₹20.01 LPA", "₹20.01 LPA", "PASS"),
    ("T-03 Remote + ₹19.99 LPA", "₹19.99 LPA", "FAIL"),
    ("T-04 Remote + ₹16 LPA", "₹16 LPA", "FAIL"),
])
def test_threshold_acceptance_rows(gate, label, text, expected):
    """Just-above passes, just-below and clearly-below are vetoed, not rounded."""
    result = gate.evaluate_posting({"candidate_id": label,
                                    "work_mode_text": REMOTE,
                                    "compensation_text": text})
    assert result.verdict == expected, label
    if expected == "FAIL":
        assert result.reason_codes == ["COMP-FAIL-BELOW-FLOOR"]


def test_t07_onsite_at_a_larger_salary_still_fails(gate):
    """T-07: the work-mode veto does not weaken as compensation rises."""
    result = gate.evaluate_posting({"work_mode_text": "On-site",
                                    "compensation_text": "₹40 LPA"})
    assert result.verdict == "FAIL"
    assert result.reason_codes == ["WM-FAIL-ONSITE"]


def test_t09_services_and_product_verdicts_are_identical(gate):
    """T-08 / T-09: the two must not diverge at the gate."""
    def evaluate(company_type):
        record = gate.evaluate_posting({"work_mode_text": REMOTE,
                                        "compensation_text": "₹25 LPA",
                                        "company_type_signal": company_type}).as_dict()
        record.pop("evaluated_at")
        record.pop("company_type_signal")
        return record

    assert evaluate("SERVICES_STAFFING") == evaluate("PRODUCT")


# --------------------------------------------------------------------------
# Provenance completeness (spec 4.4 / artifact provenance_requirements)
# --------------------------------------------------------------------------

def test_evidence_carries_every_required_provenance_field(gate, ruleset):
    """Each required evidence field is present, and extractor_version is real."""
    result = gate.evaluate_posting({
        "work_mode_text": "Fully remote",
        "compensation_text": "₹22 LPA",
        "source_ref": "https://example.com/jobs/1",
        "compensation_source_ref": "https://example.com/jobs/1",
        "source_fetched_at": "2026-08-29T10:00:00+00:00",
        "posting_stated_at": "2026-08-20",
    })
    assert result.evidence
    for item in result.evidence:
        for required in ("dimension", "evidence_class", "verbatim_text", "source",
                         "source_ref", "source_fetched_at", "extractor_version",
                         "posting_stated_at"):
            assert required in item, f"missing {required}"
        assert item["extractor_version"] == ruleset.version


def test_posting_date_three_state_is_preserved(gate):
    """
    null means the source stated none; an absent key means this run did not
    capture it. The two are different facts and are never conflated (spec 4.4).
    """
    stated_none = gate.evaluate_posting({"work_mode_text": REMOTE,
                                         "compensation_text": "₹22 LPA",
                                         "posting_stated_at": None})
    not_captured = gate.evaluate_posting({"work_mode_text": REMOTE,
                                          "compensation_text": "₹22 LPA"})

    for item in stated_none.evidence:
        assert "posting_stated_at" in item and item["posting_stated_at"] is None
    for item in not_captured.evidence:
        assert "posting_stated_at" not in item, "an uncaptured date must not be backfilled"


def test_verbatim_text_is_never_paraphrased(gate):
    """The evidence span is stored exactly as supplied."""
    span = "Compensation: ₹18–24 LPA (fixed)"
    result = gate.evaluate_posting({"work_mode_text": REMOTE, "compensation_text": span})
    assert result.compensation_provenance["verbatim_text"] == span
