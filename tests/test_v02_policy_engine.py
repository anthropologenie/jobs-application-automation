"""Policy engine v0.2: data-driven rules, drift guards, extraction robustness, dimension independence."""

import copy
import json

import pytest

from evaluation.compensation import parse_clauses
from evaluation.policy_loader import (DEFAULT_POLICY_PATH, PolicyDriftError, load_policy_v02,
                                      policy_from_doc)
from v02_support import BASE_TEXT, EN, fresh_service, no_network, observation  # noqa: F401

POLICY = load_policy_v02()
DOC = json.loads(DEFAULT_POLICY_PATH.read_text(encoding="utf-8"))


def evaluate(text=BASE_TEXT, **obs):
    svc = fresh_service()
    svc.classify_company("Synthetic Product Co", "PRODUCT", "INFERRED_FROM_EVIDENCE", "machine")
    return svc.ingest(observation(raw_text=text, language_detection=EN, **obs))["evaluation"]["result"]


def swap(line_prefix, new_line, text=BASE_TEXT):
    lines = [new_line if l.startswith(line_prefix) else l for l in text.split("\n")]
    return "\n".join(l for l in lines if l is not None)


# ------------------------------------------------------------ artifact / guards

def test_only_three_eligibility_verdicts_exist():
    assert DOC["artifact"]["verdicts"] == ["PASS", "FAIL", "UNKNOWN"]
    for table in DOC["rules"].values():
        assert {r["verdict"] for r in table} <= {"PASS", "FAIL", "UNKNOWN"}


def test_a_fourth_verdict_is_refused():
    doc = copy.deepcopy(DOC)
    doc["rules"]["geography"][0]["verdict"] = "FLAG"
    with pytest.raises(PolicyDriftError):
        policy_from_doc(doc)


def test_precedence_must_be_fail_unknown_pass():
    doc = copy.deepcopy(DOC)
    doc["artifact"]["precedence"] = ["UNKNOWN", "FAIL", "PASS"]
    with pytest.raises(PolicyDriftError):
        policy_from_doc(doc)


def test_unregistered_flag_is_refused():
    doc = copy.deepcopy(DOC)
    doc["rules"]["compensation"][0]["flags"] = ["INVENTED_FLAG"]
    with pytest.raises(PolicyDriftError):
        policy_from_doc(doc)


def test_unknown_parameter_reference_is_refused():
    doc = copy.deepcopy(DOC)
    doc["rules"]["compensation"][8]["when"]["max_inr"] = {"lt": "$no_such_param"}
    with pytest.raises(PolicyDriftError):
        policy_from_doc(doc)


def test_policy_values_are_data_not_code():
    p = DOC["parameters"]
    assert (p["floor"], p["target_min"], p["target_max"]) == (1800000, 2400000, 2800000)
    assert p["review_daily_cap"] == 10 and p["review_carry_days"] == 3
    assert p["language_confidence_threshold"] == 0.95
    assert p["bengaluru_hybrid_max_office_days"] == 3 and p["short_term_contract_months"] == 6
    assert "EMEA" in DOC["geo"]["regions"] and "IN" not in DOC["geo"]["regions"]["EMEA"]["members"]
    assert "IN" in DOC["geo"]["regions"]["APAC"]["members"]
    assert len(DOC["relevance"]["title_tiers"]["TIER_1"]) == 20


def test_changing_the_floor_in_data_changes_the_verdict():
    doc = copy.deepcopy(DOC)
    doc["parameters"]["floor"] = 2000000
    variant = policy_from_doc(doc, expected_version=None)
    svc = fresh_service(variant)
    svc.classify_company("Synthetic Product Co", "PRODUCT", "INFERRED_FROM_EVIDENCE", "machine")
    r = svc.ingest(observation(raw_text=swap("Salary:", "Salary: ₹19 LPA fixed base."), language_detection=EN))
    assert r["evaluation"]["result"]["eligibility_dimensions"]["compensation"]["verdict"] == "FAIL"
    assert evaluate(swap("Salary:", "Salary: ₹19 LPA fixed base."))["eligibility_dimensions"]["compensation"]["verdict"] == "PASS"


def test_v01_artifact_hash_is_recorded_and_unchanged():
    import hashlib
    from evaluation.policy_loader import V01_POLICY_PATH
    recorded = DOC["artifact"]["v0_1_artifact"]["sha256"]
    assert hashlib.sha256(V01_POLICY_PATH.read_bytes()).hexdigest() == recorded


# ----------------------------------------------------- compensation precedence

@pytest.mark.parametrize("text,verdict,flag", [
    ("Salary: ₹15–30 LPA fixed base.", "UNKNOWN", "SALARY_RANGE_STRADDLES_FLOOR"),
    ("Salary: ₹15–20 LPA fixed base.", "UNKNOWN", "SALARY_RANGE_STRADDLES_FLOOR"),
    ("Salary: ₹18–25 LPA fixed base.", "PASS", "COMPENSATION_REVIEW"),
    ("Salary: ₹17.5 LPA fixed base.", "FAIL", None),
    ("Salary: Rs 18-23 lakhs per annum, fixed base.", "PASS", "BELOW_TARGET"),
    ("Salary: INR 24,00,000 per annum base.", "PASS", "IN_TARGET"),
    ("Salary: upto 45 LPA.", "UNKNOWN", "COMP_UPPER_BOUND_ONLY"),
    ("CTC: ₹14 LPA.", "FAIL", None),
])
def test_hard_floor_always_wins_over_target(text, verdict, flag):
    r = evaluate(swap("Salary:", text))
    assert r["eligibility_dimensions"]["compensation"]["verdict"] == verdict
    if flag:
        assert flag in r["flags"]


def test_ctc_is_never_haircut_into_base():
    r = evaluate(swap("Salary:", "Compensation: ₹30 LPA CTC."))
    comp = r["compensation_normalized"]
    assert comp["basis"] == "CTC" and comp["min_inr"] == comp["max_inr"] == 3000000
    assert r["preference_attributes"]["compensation_band"] == "CTC_BASIS_UNVERIFIED"
    assert "IN_TARGET" not in r["flags"] and "ABOVE_TARGET" not in r["flags"]


def test_audit_c3_false_positive_compensation_spans_are_gone():
    assert parse_clauses("Validate orchestrator correctness (DAG execution, retries, compensation paths).", POLICY) == []
    assert parse_clauses("4+ Years Experience with AI-QA in Bangalore.", POLICY) == []


def test_foreign_figure_without_fx_is_unknown_never_guessed():
    r = evaluate(swap("Salary:", "Base salary: GBP 70,000 per year."))
    assert r["eligibility_dimensions"]["compensation"]["verdict"] == "UNKNOWN"
    assert "FX_RATE_UNAVAILABLE" in r["flags"]


def test_foreign_monthly_is_not_annualised():
    r = evaluate(swap("Salary:", "Base salary: USD 9,000 per month."))
    assert "COMP_NOT_ANNUALIZABLE" in r["flags"]


# ------------------------------------------------------------------ geography

@pytest.mark.parametrize("line,verdict", [
    ("Location: Remote - Canada only.", "FAIL"),
    ("Location: Remote (LATAM).", "FAIL"),
    ("Location: Remote - Asia Pacific.", "UNKNOWN"),
    ("Location: Work from home (India).", "PASS"),
    ("Location: Remote. Must be based in Chennai.", "FAIL"),
    ("Location: Bengaluru, work from office 3 days a week.", "PASS"),
    ("Location: Koramangala, Bengaluru - hybrid, 2 days a week in office.", "PASS"),
    ("Location: Gurgaon (hybrid, 2 days per week in office).", "FAIL"),
])
def test_geography_alternate_phrasings(line, verdict):
    assert evaluate(swap("Location:", line))["eligibility_dimensions"]["geography"]["verdict"] == verdict


def test_join_us_is_not_the_united_states():
    text = swap("Location:", "Location: Remote - India.") + "\nJoin us to build great things."
    assert evaluate(text)["eligibility_dimensions"]["geography"]["verdict"] == "PASS"


def test_technical_hybrid_is_not_a_work_arrangement():
    r = evaluate(BASE_TEXT)  # the JD mentions "hybrid search"
    assert r["preference_attributes"]["work_arrangement"] == "REMOTE"


def test_timezone_never_changes_eligibility():
    base = evaluate(BASE_TEXT)
    tz = evaluate(BASE_TEXT + "\nMust overlap 4 hours with PST working hours.")
    assert tz["eligibility_dimensions"] == base["eligibility_dimensions"] or \
        {k: v["verdict"] for k, v in tz["eligibility_dimensions"].items()} == \
        {k: v["verdict"] for k, v in base["eligibility_dimensions"].items()}
    assert tz["lane"] == base["lane"] == "SHORTLIST"
    assert "TIMEZONE_OVERLAP_US" in tz["flags"]


# ------------------------------------------------------- employment / employer

def test_data_contracts_are_not_employment_contracts():
    r = evaluate(BASE_TEXT + "\nYou will design data contracts and API contracts for the platform.")
    assert r["eligibility_dimensions"]["employment_type"]["verdict"] == "PASS"


def test_contract_duration_in_years():
    r = evaluate(swap("Employment type:", "Employment type: Direct contract with Synthetic Product Co, 1 year contract."))
    assert r["eligibility_dimensions"]["employment_type"]["verdict"] == "UNKNOWN"
    assert "LONG_TERM_DIRECT_CONTRACT" in r["flags"]


def test_eor_is_not_staffing():
    r = evaluate(BASE_TEXT + "\nYou will be employed through our Employer of Record in India.")
    assert r["eligibility_dimensions"]["employment_relationship"]["verdict"] == "UNKNOWN"
    assert "EOR" in r["flags"] and "STAFFING" not in r["flags"]


def test_unclassified_employer_inferred_from_text_signal():
    svc = fresh_service()
    r = svc.ingest(observation(raw_company="Acme Staffing", raw_text=BASE_TEXT.replace(
        "Synthetic Product Co builds and sells its own AI software product.",
        "Acme is a staffing agency."), language_detection=EN))["evaluation"]["result"]
    assert r["eligibility_dimensions"]["employer_type"]["verdict"] == "UNKNOWN"
    assert "STAFFING" in r["flags"] and r["lane"] == "REVIEW"


# ------------------------------------------------------------------- language

def test_heuristic_detection_never_reaches_fail_confidence():
    german = ("Wir suchen eine erfahrene Person für unser Team in Berlin und bieten spannende Aufgaben "
              "mit modernen Werkzeugen sowie flexible Arbeitszeiten für alle Mitarbeitenden in der Firma heute.")
    svc = fresh_service()
    r = svc.ingest(observation(raw_text=german))["evaluation"]["result"]
    assert r["eligibility_dimensions"]["language"]["verdict"] == "UNKNOWN"


def test_heuristic_detects_english_paragraphs():
    svc = fresh_service()
    r = svc.ingest(observation(raw_text=BASE_TEXT + "\nWe are a small team and you will work with the founders on the "
                                                    "core product and help us to ship it to our customers."))["evaluation"]["result"]
    assert r["eligibility_dimensions"]["language"]["verdict"] == "PASS"


# -------------------------------------------------------- dimension independence

def test_relevance_and_experience_never_change_eligibility():
    strong = evaluate(BASE_TEXT)
    weak_senior = evaluate(swap("You will build", "Experience with AI tools.",
                                swap("Experience:", "Experience: 12+ years.")))
    v = lambda r: {k: d["verdict"] for k, d in r["eligibility_dimensions"].items()}  # noqa: E731
    assert v(strong) == v(weak_senior)
    assert weak_senior["relevance"]["relevance_label"] == "WEAK"
    assert weak_senior["lane"] == "PARKED" and strong["lane"] == "SHORTLIST"


def test_lane_is_derived_only_from_computed_dimensions():
    r = evaluate(BASE_TEXT)
    for key in ("eligibility_dimensions", "relevance", "preference_attributes", "evidence_completeness", "flags"):
        assert key in r
    assert r["lane_rule"].startswith("LANE-R")
    assert not any("score" in key.lower() for key in r["relevance"])
    assert not any("score" in key.lower() for key in r)
