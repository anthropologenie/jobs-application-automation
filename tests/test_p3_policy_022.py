"""
P3 acceptance tests for jobops-policy@0.2.2 (pinned explicitly; independent of the default).

Covers what the golden fixture cannot express: artifact integrity of the older
versions, the OR-63 CTC lane rule as a direct lane assertion, OR-65 carry
counting over consecutive daily plans, the contextual 'hybrid' classifier on
the P3 §11 boundary phrases, and that 0.2.0 / 0.2.1 ignore the new
raw_work_mode input (their historical behaviour is unchanged).
"""

import hashlib
import json

import pytest

from evaluation.extract import hybrid_usage
from evaluation.policy_loader import POLICY_PATHS, load_policy_version
from evaluation.queue import plan_day
from v02_support import BASE_TEXT, EN, fresh_service, no_network, observation  # noqa: F401

V20, V21, V22 = "jobops-policy@0.2.0", "jobops-policy@0.2.1", "jobops-policy@0.2.2"
V020_SHA = "65f74aec883d475989ea0594fac070f547c96a697bc1f7f4b46cf8e0d5dd567a"
V021_SHA = "af19a3fd998e945cba19ce68f0e36f2eba4156e8bfd5255ac4ea7dacf7f5ea7d"
MODERATE_JD = "Integrate LLM APIs into our product and write prompt templates for summarization features."


def _svc(version=V22):
    svc = fresh_service(load_policy_version(version))
    svc.clock = lambda: "2026-09-21"
    svc.classify_company("Synthetic Product Co", "PRODUCT", "INFERRED_FROM_EVIDENCE", "machine")
    return svc


# ------------------------------------------------------------ artifacts

def test_older_policy_artifacts_are_byte_identical():
    assert hashlib.sha256(POLICY_PATHS[V20].read_bytes()).hexdigest() == V020_SHA
    assert hashlib.sha256(POLICY_PATHS[V21].read_bytes()).hexdigest() == V021_SHA
    doc = json.loads(POLICY_PATHS[V22].read_text(encoding="utf-8"))
    assert doc["artifact"]["v0_2_1_artifact"]["sha256"] == V021_SHA


def test_022_keeps_three_verdicts_and_moves_ctc_flag_to_informational():
    p = load_policy_version(V22)
    assert tuple(p.doc["artifact"]["verdicts"]) == ("PASS", "FAIL", "UNKNOWN")
    assert "CTC_BASIS_UNVERIFIED" in p.info_flags and "CTC_BASIS_UNVERIFIED" not in p.review_flags
    for flag in ("BELOW_TARGET", "COMPENSATION_REVIEW", "WORK_MODE_CONFLICT", "CONTRACT_DURATION_UNSTATED"):
        assert flag in p.review_flags
    # 0.2.1 is untouched: the flag still routes to REVIEW there
    assert "CTC_BASIS_UNVERIFIED" in load_policy_version(V21).review_flags


# ------------------------------------------------------ OR-63 CTC lane rule

@pytest.mark.parametrize("salary,lane,flags", [
    ("₹24L CTC", "SHORTLIST", {"CTC_BASIS_UNVERIFIED"}),
    ("₹24–30L CTC", "SHORTLIST", {"CTC_BASIS_UNVERIFIED"}),
    ("₹18L CTC", "REVIEW", {"BELOW_TARGET", "CTC_BASIS_UNVERIFIED"}),
    ("₹18–25L CTC", "REVIEW", {"COMPENSATION_REVIEW", "CTC_BASIS_UNVERIFIED"}),
    ("₹20–30L CTC", "REVIEW", {"COMPENSATION_REVIEW", "CTC_BASIS_UNVERIFIED"}),
])
def test_ctc_lane_rule_on_an_otherwise_clean_posting(salary, lane, flags):
    text = BASE_TEXT.replace("Salary: ₹26 LPA fixed base.\n", "")
    r = _svc().ingest(observation(raw_text=text, raw_salary=salary, language_detection=EN,
                                  source_url="https://boards.greenhouse.io/p3/jobs/1"))["evaluation"]["result"]
    dims = {k: v["verdict"] for k, v in r["eligibility_dimensions"].items()}
    assert set(dims.values()) == {"PASS"}, dims
    assert r["relevance"]["relevance_label"] == "STRONG"
    assert flags <= set(r["flags"])
    assert r["lane"] == lane, (salary, r["flags"], r["lane_rule"])


# -------------------------------------------------- OR-65 carry counting

def _review(svc, n, *, strong, at):
    text = BASE_TEXT.replace("Salary: ₹26 LPA fixed base.", "Salary: ₹20 LPA fixed base.")  # BELOW_TARGET -> REVIEW
    if not strong:
        text = text.replace(text.split("\n")[-1], MODERATE_JD)
    return svc.ingest(observation(source_url=f"https://boards.greenhouse.io/p3q/jobs/{n}", raw_text=text,
                                  raw_title=f"AI Engineer {n}", language_detection=EN, observed_at=at))["requisition_id"]


def test_carry_counting_first_overflow_day_is_carry_day_one():
    """D overflow (carry 1) -> D+1 carry 2 -> D+2 carry 3 -> D+3 PARKED; STRONG exempt (OR-65)."""
    svc = _svc()
    for i in range(10):
        _review(svc, i, strong=True, at="2026-09-19T06:00:00+00:00")
    moderate = _review(svc, 50, strong=False, at="2026-09-20T06:00:00+00:00")
    strong = _review(svc, 51, strong=True, at="2026-09-20T07:00:00+00:00")
    d, d1, d2, d3 = (plan_day(svc, day) for day in ("2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24"))

    def carry(plan, rid):
        return next((it["carry_days"] for it in plan["review_carried"] if it["requisition_id"] == rid), None)

    assert [carry(p, moderate) for p in (d, d1, d2)] == [1, 2, 3]
    for p in (d, d1, d2):
        assert moderate not in [it["requisition_id"] for it in p["overflow_parked_today"]]
    assert moderate in [it["requisition_id"] for it in d3["overflow_parked_today"]]
    assert strong not in [it["requisition_id"] for p in (d, d1, d2, d3) for it in p["overflow_parked_today"]]
    assert d3["policy_version"] == V22


# ----------------------------------------- contextual 'hybrid' (P3 §9-§11)

@pytest.mark.parametrize("phrase", [
    "We use hybrid search over product docs.", "Hybrid retrieval with pgvector.",
    "hybrid BM25 + dense retrieval", "Improve hybrid ranking.", "Runs on a hybrid cloud.",
    "A hybrid architecture for routing.", "Evaluate a hybrid model.", "Hybrid Search Engineer",
    "Train hybrid embeddings.",
])
def test_technical_hybrid_is_never_a_work_mode(phrase):
    usages = hybrid_usage(phrase, load_policy_version(V22), office_cue=False, structured="")
    assert usages and "WORK" not in usages, usages


@pytest.mark.parametrize("phrase,office_cue", [
    ("We offer a hybrid work model.", False), ("This is a hybrid role.", False), ("A hybrid position.", False),
    ("Our hybrid workplace in Bengaluru.", False), ("Hybrid — 3 days in office", True),
    ("Hybrid — 2 days onsite", True), ("We follow a hybrid model with 2 days in office.", True),
])
def test_work_arrangement_hybrid_is_a_work_mode(phrase, office_cue):
    assert "WORK" in hybrid_usage(phrase, load_policy_version(V22), office_cue=office_cue, structured="")


def test_bare_hybrid_is_unclassified_in_the_jd_but_work_in_a_structured_field():
    p = load_policy_version(V22)
    assert hybrid_usage("Hybrid", p, office_cue=False, structured="") == ["UNCLASSIFIED"]
    assert hybrid_usage("Hybrid", p, office_cue=False, structured="field") == ["WORK"]
    assert hybrid_usage("AI Engineer (Hybrid)", p, office_cue=False, structured="title") == ["WORK"]


# --------------------------------- older versions ignore raw_work_mode

@pytest.mark.parametrize("version", [V20, V21])
def test_older_versions_evaluate_as_if_raw_work_mode_were_absent(version):
    kw = dict(raw_text=BASE_TEXT, language_detection=EN, source_url="https://boards.greenhouse.io/p3o/jobs/1")
    with_field = _svc(version).ingest(observation(raw_work_mode="On-site", **kw))["evaluation"]["result"]
    without = _svc(version).ingest(observation(**kw))["evaluation"]["result"]
    assert with_field["evidence_hash"] == without["evidence_hash"]
    assert with_field["eligibility_dimensions"] == without["eligibility_dimensions"]
    assert with_field["lane"] == without["lane"]
