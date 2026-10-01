"""
P5 tests for jobops-policy@0.2.3 (Owner Addendum E, OR-66..OR-73).

  * golden cases (tests/fixtures/policy_v023_golden_cases.json), hand-written from the rulings;
  * mutation pairs: a small textual change must produce the stated policy transition;
  * F4 / enrichment sequences (absent detail is neither a conflict nor an update);
  * the experience threshold is a policy parameter, not a literal;
  * version integrity: 0.2.0 / 0.2.1 / 0.2.2 byte-identical; 0.2.2 stays the default while 0.2.3 is not accepted;
  * frozen Round-2 replay: fixture unchanged, no errors, the measured 0.2.3 result does not regress, and every
    false EXCLUDED is one of the explained, documented cases.
"""

import copy
import hashlib
import json
from pathlib import Path

import pytest

import r2_blind_harness as r2
from evaluation import policy_loader
from evaluation.policy_loader import load_policy_version, policy_from_doc
from store import repository as repo
from v02_support import fresh_service, no_network, observation  # noqa: F401

V22, V23 = "jobops-policy@0.2.2", "jobops-policy@0.2.3"
ROOT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "policy_v023_golden_cases.json"
DOC = json.loads(FIXTURE.read_text(encoding="utf-8"))
DATE = DOC["artifact"]["default_evaluation_date"]
BASE_OBS = {"source": "ats:greenhouse", "source_kind": "EMPLOYER_ATS", "completeness": "FULL_JD",
            "observed_at": "2026-09-28T06:00:00+00:00", "run_id": "p5-run-1"}

# Round-2 replay under 0.2.3 as measured in P5 (docs/reports/JOBOPS_P5_FIX_REPORT_2026-09-30.md).
# A ratchet, not an acceptance claim: the posting-mismatch count may only go down.
R2_023_MAX_POSTING_MISMATCHES = 57
R2_023_MAX_SEQUENCE_MISMATCHES = 1
# False EXCLUDED cases that remain under 0.2.3, each explained in the P5 report (none is an engine defect).
R2_023_EXPLAINED_FALSE_EXCLUDED = {
    "R2-023": "OR-50: 'Remote — Canada' names a region that excludes India -> FAIL (fixture expects UNKNOWN)",
}


def _service(version, classification=None, company=None):
    s = fresh_service(load_policy_version(version))
    s.clock = lambda: DATE
    if classification:
        s.classify_company(company, classification, "OWNER_CONFIRMED", "owner")
    return s


def _run(obs_fields, version=V23, classification="PRODUCT"):
    fields = {**BASE_OBS, **obs_fields}
    if fields.get("raw_text") is None:
        fields["completeness"] = "SEARCH_ONLY"
    s = _service(version, classification, fields.get("raw_company"))
    res = s.ingest(observation(**fields))
    return res["evaluation"]["result"], res


# ------------------------------------------------------------------ golden

def _check(expected, r):
    dims = r["eligibility_dimensions"]
    for k, v in expected.get("dimensions", {}).items():
        assert dims[k]["verdict"] == v, (k, dims[k])
    for k, v in expected.get("rules", {}).items():
        assert dims[k]["rule_id"] == v, (k, dims[k])
    for f in expected.get("flags_include", []):
        assert f in r["flags"], (f, r["flags"])
    for f in expected.get("flags_exclude", []):
        assert f not in r["flags"], (f, r["flags"])
    if "lane" in expected:
        assert r["lane"] == expected["lane"], (r["lane"], r["lane_rule"], r["flags"])
    if "relevance_label" in expected:
        assert r["relevance"]["relevance_label"] == expected["relevance_label"], r["relevance"]["reason"]
    if "experience_signal" in expected:
        assert r["relevance"]["experience_signal"] == expected["experience_signal"]
    if "office_days" in expected:
        assert dims["geography"]["facts"]["office_days"] == expected["office_days"], dims["geography"]["facts"]
    if "detected_language" in expected or "min_confidence" in expected:
        facts = dims["language"]["facts"]
        if "detected_language" in expected:
            assert facts["document_language"] == ("ENGLISH" if expected["detected_language"] == "en" else "NON_ENGLISH")
        if "min_confidence" in expected:
            assert facts["document_confidence"] >= expected["min_confidence"], facts


def test_golden_fixture_shape():
    cases = DOC["cases"]
    assert DOC["case_count"] == len(cases)
    area = lambda a: [c for c in cases if c["area"].startswith(a)]  # noqa: E731
    assert len(area("E1")) + len(area("E5")) >= 20
    assert sum(1 for c in area("E1") if c["adversarial"]) >= 10
    assert len(area("E4")) >= 15 and len(area("E8")) + len(area("E7")) >= 15 and len(area("E6")) >= 20
    assert any(not c["adversarial"] for c in area("E8")) and any(c["adversarial"] for c in area("E8"))
    assert len({c["case_id"] for c in cases}) == len(cases)


@pytest.mark.parametrize("case", DOC["cases"], ids=[c["case_id"] for c in DOC["cases"]])
def test_golden_023(case):
    r, _ = _run(case["observation"], V23, case.get("classification"))
    assert r["policy_version"] == V23
    _check(case["expected"], r)
    # Auditability: every eligibility decision names the rule that made it.
    assert all(d["rule_id"] for d in r["eligibility_dimensions"].values())


def test_g072_placement_is_employer_fail_under_023():
    """Golden G072 keeps its historical 0.2.0-0.2.2 expectation; under 0.2.3 OR-70 makes the employer FAIL."""
    c = next(c for c in DOC["cases"] if c["case_id"] == "G072@0.2.3")
    r, _ = _run(c["observation"], V23, "STAFFING")
    assert r["eligibility_dimensions"]["employer_type"]["rule_id"] == "EMPR-R09"
    r22, _ = _run(c["observation"], V22, "STAFFING")
    assert r22["eligibility_dimensions"]["employer_type"]["verdict"] == "UNKNOWN"  # history unchanged


# --------------------------------------------------------------- mutations

AI = "We build RAG assistants and run LLM-as-judge hallucination evals on golden datasets. "
CLEAN = {"raw_title": "AI Evaluation Engineer", "raw_company": "Synthetic Product Co", "raw_location": "Remote - India",
         "raw_work_mode": "Remote", "raw_salary": "Base: ₹30 LPA", "raw_employment_type": "Full-time, permanent"}
BLR = {**CLEAN, "raw_location": "Bengaluru", "raw_work_mode": "Hybrid"}

MUTATIONS = [
    # id, base fields, (text A, expected A), (text B, expected B); expected = {dimension: verdict | flag checks}
    ("hybrid-technical-vs-work", {**CLEAN, "raw_location": "Bengaluru", "raw_work_mode": None},
     (AI + "You will own hybrid search relevance.", {"geography": "UNKNOWN", "flag_absent": "WORK_MODE_CONFLICT"}),
     (AI + "This is a hybrid role: 2 days a week in our Bengaluru office.", {"geography": "PASS"})),
    ("not-hybrid-vs-hybrid", CLEAN,
     (AI + "This is not a hybrid role.", {"geography": "PASS", "flag_absent": "WORK_MODE_CONFLICT"}),
     (AI + "This is a hybrid role: Tuesdays and Thursdays at our Bengaluru office.",
      {"geography": "UNKNOWN", "flag": "WORK_MODE_CONFLICT"})),
    ("hybrid-3-vs-4-days", BLR,
     (AI + "Hybrid: 3 days/week at our HSR office.", {"geography": "PASS"}),
     (AI + "Hybrid: 4 days/week at our HSR office.", {"geography": "FAIL"})),
    ("weekdays-2-vs-4", BLR,
     (AI + "Office on Tuesdays and Thursdays.", {"geography": "PASS"}),
     (AI + "Office on Tuesdays, Wednesdays, Thursdays and Fridays.", {"geography": "FAIL"})),
    ("contract-testing-vs-contract-role", {**CLEAN, "raw_employment_type": "Full-time"},
     (AI + "Own contract testing with Pact.", {"employment_type": "PASS"}),
     (AI + "This is a 12-month contract role.", {"employment_type": "FAIL"})),
    ("fixed-term-long-vs-short", {**CLEAN, "raw_employment_type": "Fixed-term employment"},
     (AI + "A 12-month contract; you will be employed directly by us.", {"employment_type": "UNKNOWN",
                                                                        "flag": "LONG_TERM_DIRECT_CONTRACT"}),
     (AI + "A 4-month contract; you will be employed directly by us.", {"employment_type": "FAIL"})),
    ("own-payroll-vs-third-party-payroll", CLEAN,
     (AI + "You will be on our own payroll.", {"employer_type": "PASS", "employment_relationship": "PASS"}),
     (AI + "You will be on third-party payroll.", {"employer_type": "FAIL", "employment_relationship": "FAIL"})),
    ("fixed-15-vs-25-plus-variable", {**CLEAN, "raw_text": AI},
     ("Fixed: ₹15 LPA + Variable: ₹5 LPA", {"compensation": "FAIL"}),
     ("Fixed: ₹25 LPA + Variable: ₹5 LPA", {"compensation": "PASS", "flag": "IN_TARGET"})),
    ("lakh-users-vs-lakh-salary", {**CLEAN, "raw_salary": None},
     (AI + "Our assistant serves 25 lakh users.", {"compensation": "UNKNOWN"}),
     (AI + "Salary: ₹25 lakh per annum.", {"compensation": "PASS"})),
    ("27L-vs-17L-plus-bonus", {**CLEAN, "raw_text": AI},
     ("₹27L fixed + 15% bonus", {"compensation": "PASS"}),
     ("₹17L fixed + 15% bonus", {"compensation": "FAIL"})),
    ("remote-vs-remote-plus-chennai-5-days", {**CLEAN, "raw_location": "Remote, India", "raw_work_mode": None},
     (AI, {"geography": "PASS"}),
     (AI + "The team works from our Chennai centre five days a week.",
      {"geography": "UNKNOWN", "flag": "WORK_MODE_CONFLICT"})),
    ("tier1-no-ai-vs-one-ai-term", {**CLEAN, "raw_title": "AI Engineer"},
     ("Build Power BI dashboards and SQL reports.", {"lane": "PARKED", "flag_absent": "RELEVANCE_TITLE_PRIOR"}),
     ("Build Power BI dashboards and SQL reports; call an LLM API.", {"lane": "REVIEW",
                                                                       "flag": "RELEVANCE_TITLE_PRIOR"})),
    ("english-jargon-vs-german", CLEAN,
     (AI + "You will tune pgvector, vLLM and LangGraph agents on Kubernetes with pytest.", {"language": "PASS"}),
     ("Sie entwickeln die Plattform und bauen mit unseren Teams die Evaluationspipelines für die Kunden auf, "
      "und wir bieten ein kollegiales Team mit sehr guten Arbeitszeiten.", {"language": "FAIL"})),
    ("german-required-vs-plus", CLEAN,
     (AI + "German is required.", {"language": "FAIL"}),
     (AI + "German is a plus.", {"language": "PASS", "flag": "LANGUAGE_PREFERENCE"})),
    ("japanese-mandatory-vs-plus", CLEAN,
     (AI + "Japanese (JLPT N2 or above) is mandatory.", {"language": "FAIL"}),
     (AI + "Japanese is a plus.", {"language": "PASS"})),
]


def _mutant(base, text):
    fields = dict(base)
    if "raw_text" in base and base["raw_text"] == AI and text and not text.startswith(AI):
        fields["raw_salary"] = text  # compensation mutations vary the salary line
    else:
        fields["raw_text"] = text
    return fields


def _assert_expect(r, exp):
    dims = r["eligibility_dimensions"]
    for k, v in exp.items():
        if k == "flag":
            assert v in r["flags"], (v, r["flags"])
        elif k == "flag_absent":
            assert v not in r["flags"], (v, r["flags"])
        elif k == "lane":
            assert r["lane"] == v, (r["lane"], r["flags"])
        else:
            assert dims[k]["verdict"] == v, (k, dims[k]["rule_id"], dims[k]["facts"])


@pytest.mark.parametrize("mid,base,a,b", MUTATIONS, ids=[m[0] for m in MUTATIONS])
def test_mutation_pair(mid, base, a, b):
    ra, _ = _run(_mutant(base, a[0]))
    rb, _ = _run(_mutant(base, b[0]))
    _assert_expect(ra, a[1])
    _assert_expect(rb, b[1])


# ------------------------------------------------------ F4 / enrichment

def _seq_service():
    s = fresh_service(load_policy_version(V23))
    s.classify_company("Helixa Care", "PRODUCT", "OWNER_CONFIRMED", "owner")
    return s


def _obs(**kw):
    base = {"raw_title": "AI Quality Engineer", "raw_company": "Helixa Care", "raw_location": "Bengaluru",
            "raw_work_mode": "Hybrid", "apply_url": None, "source_url": "https://careers.helixa.example/jobs/HLX-1"}
    base.update(kw)
    return observation(**base)


JD2 = ("Hybrid: in the Koramangala office two days a week. We build RAG assistants and run LLM-as-judge "
       "hallucination evals on golden datasets. Base: ₹30 LPA. Employment type: Full-time, permanent.")


def test_search_only_board_sighting_missing_office_days_is_not_a_conflict():
    s = _seq_service()
    s.clock = lambda: "2026-09-22"
    r1 = s.ingest(_obs(source="ats", source_kind="EMPLOYER_ATS", completeness="FULL_JD", raw_text=JD2,
                       observed_at="2026-09-22T06:00:00+00:00", run_id="r1"))
    assert r1["evaluation"]["result"]["lane"] == "SHORTLIST"
    s.clock = lambda: "2026-09-25"
    r2_ = s.ingest(_obs(source="linkedin", source_kind="JOB_BOARD", completeness="SEARCH_ONLY", raw_text=None,
                        source_url=None, apply_url="https://careers.helixa.example/jobs/HLX-1",
                        observed_at="2026-09-25T06:00:00+00:00", run_id="r2"))
    ev = s.current_evaluation(r2_["requisition_id"])["result"]
    assert "SOURCE_CONFLICT" not in ev["flags"] and ev["lane"] == "SHORTLIST"
    assert repo.get_requisition(s.conn, r2_["requisition_id"])["newness_state"] == "SEEN_BEFORE"


def test_same_source_search_only_to_full_jd_is_enrichment_not_update():
    s = _seq_service()
    s.clock = lambda: "2026-09-24"
    s.ingest(_obs(source="linkedin", source_kind="JOB_BOARD", completeness="SEARCH_ONLY", raw_text=None,
                  source_url=None, apply_url="https://careers.helixa.example/jobs/HLX-1",
                  observed_at="2026-09-24T06:00:00+00:00", run_id="r1"))
    s.clock = lambda: "2026-09-26"
    res = s.ingest(_obs(source="linkedin", source_kind="JOB_BOARD", completeness="FULL_JD", raw_text=JD2,
                        source_url=None, apply_url="https://careers.helixa.example/jobs/HLX-1",
                        observed_at="2026-09-26T06:00:00+00:00", run_id="r2"))
    assert repo.get_requisition(s.conn, res["requisition_id"])["newness_state"] == "SEEN_BEFORE"
    assert s.current_evaluation(res["requisition_id"])["result"]["lane"] == "SHORTLIST"


def test_a_stated_office_day_change_is_still_an_update():
    s = _seq_service()
    s.clock = lambda: "2026-09-22"
    s.ingest(_obs(source="ats", source_kind="EMPLOYER_ATS", completeness="FULL_JD", raw_text=JD2,
                  observed_at="2026-09-22T06:00:00+00:00", run_id="r1"))
    s.clock = lambda: "2026-09-25"
    res = s.ingest(_obs(source="ats", source_kind="EMPLOYER_ATS", completeness="FULL_JD",
                        raw_text=JD2.replace("two days a week", "four days a week"),
                        observed_at="2026-09-25T06:00:00+00:00", run_id="r2"))
    assert repo.get_requisition(s.conn, res["requisition_id"])["newness_state"] == "UPDATED"
    ev = s.current_evaluation(res["requisition_id"])["result"]
    assert ev["eligibility_dimensions"]["geography"]["verdict"] == "FAIL" and ev["lane"] == "EXCLUDED"


# ------------------------------------------------ experience parameter (E3)

def test_experience_threshold_is_a_policy_parameter():
    doc = copy.deepcopy(load_policy_version(V23).doc)
    assert doc["parameters"]["relevant_ai_experience_years"] == 3
    refs = [r["when"] for r in doc["experience_fit"]["rules"] if r["when"]]
    assert all("$relevant_ai_experience_years" in json.dumps(w) for w in refs if "lte" in json.dumps(w))
    doc["parameters"]["relevant_ai_experience_years"] = 5
    variant = policy_from_doc(doc)
    s = fresh_service(variant)
    s.clock = lambda: DATE
    res = s.ingest(observation(**{**BASE_OBS, **CLEAN, "raw_text": AI + "Experience: 1-4 years."}))
    assert res["evaluation"]["result"]["relevance"]["experience_signal"] == "DIRECT"
    r, _ = _run({**CLEAN, "raw_text": AI + "Experience: 1-4 years."})
    assert r["relevance"]["experience_signal"] == "REASONABLE"


def test_stretch_never_excludes_by_itself():
    r, _ = _run({**CLEAN, "raw_text": AI + "Experience: 12+ years."})
    assert r["relevance"]["experience_signal"] == "STRETCH"
    assert r["eligibility_overall"] == "PASS" and r["lane"] == "REVIEW"


# ----------------------------------------------- separation of concerns (§20)

def test_relevance_and_language_never_create_eligibility_fail():
    r, _ = _run({**CLEAN, "raw_title": "Accountant", "raw_text": "Prepare monthly ledgers and tax filings."})
    assert r["relevance"]["relevance_label"] == "WEAK" and r["eligibility_overall"] == "PASS"
    assert r["lane"] == "PARKED"
    r, _ = _run({**CLEAN, "raw_text": AI + "Sie arbeiten eng mit unseren Teams in Stuttgart zusammen und entwickeln "
                                           "die Plattform für die Kunden weiter."})
    assert r["eligibility_dimensions"]["language"]["verdict"] == "UNKNOWN" and r["lane"] == "REVIEW"


# ------------------------------------------------------- version integrity

HASHES = {"0.2.0": "65f74aec883d475989ea0594fac070f547c96a697bc1f7f4b46cf8e0d5dd567a",
          "0.2.1": "af19a3fd998e945cba19ce68f0e36f2eba4156e8bfd5255ac4ea7dacf7f5ea7d",
          "0.2.2": "3743bbaebce2b5f3143ec0a211d6c63aa35b8113dce03b1622876ef43eeed734"}


@pytest.mark.parametrize("version,sha", sorted(HASHES.items()))
def test_historical_policies_are_byte_identical(version, sha):
    path = ROOT / "policy" / f"jobops-policy-{version}.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha


def test_023_is_registered_but_not_default():
    assert V23 in policy_loader.POLICY_PATHS
    # P5: 0.2.3 did not pass the P5 aggregate gate and was never the default. P6 retired that gate (OR-82)
    # and made 0.2.4 the default after Gate E passed; 0.2.3 stays registered for replay only.
    assert policy_loader.DEFAULT_VERSION not in (V22, V23)
    doc = load_policy_version(V23).doc
    assert doc["artifact"]["status"].startswith("EXPERIMENTAL")
    assert {"RELEVANCE_TITLE_PRIOR", "EMPLOYMENT_SOURCE_CONFLICT"} <= set(doc["flags"]["review_routing"])


# ------------------------------------------------------ frozen Round-2 replay

@pytest.fixture(scope="module")
def r2_replay_023():
    assert r2.fixture_sha() == r2.EXPECTED_SHA
    cases, seqs = r2.run_all(V23)
    assert r2.fixture_sha() == r2.EXPECTED_SHA
    return cases, seqs


def test_round2_fixture_is_frozen():
    recorded = r2.SHA_FILE.read_text(encoding="utf-8").split()[0]
    assert recorded == r2.EXPECTED_SHA == r2.fixture_sha()


def test_round2_replay_023_runs_without_errors(r2_replay_023):
    cases, seqs = r2_replay_023
    assert len(cases) == 124 and len(seqs) == 10
    assert not [c["id"] for c in cases if c.get("error")] and not [s["id"] for s in seqs if s.get("error")]


def test_round2_replay_023_does_not_regress(r2_replay_023):
    cases, seqs = r2_replay_023
    mismatched = [c["id"] for c in cases if not c.get("undetermined") and c["mismatches"]]
    assert len(mismatched) <= R2_023_MAX_POSTING_MISMATCHES, mismatched
    assert sum(1 for s in seqs if s["mismatches"]) <= R2_023_MAX_SEQUENCE_MISMATCHES


def test_round2_replay_023_has_no_unexplained_false_excluded(r2_replay_023):
    cases, _ = r2_replay_023
    doc = r2.load_doc()
    exp = {c["id"]: c["expected"] for c in doc["posting_cases"]}
    false_excluded = {c["id"] for c in cases if not c.get("undetermined") and c["actual"]["lane"] == "EXCLUDED"
                      and exp[c["id"]].get("lane") not in (None, "EXCLUDED")}
    assert false_excluded <= set(R2_023_EXPLAINED_FALSE_EXCLUDED), false_excluded - set(R2_023_EXPLAINED_FALSE_EXCLUDED)


def test_round2_replay_022_baseline_is_reproduced():
    """The P4b raw measurement of 0.2.2 (106/124 with the P4b projection) is reproducible from the persisted harness."""
    cases = [r2.run_case(c, V22, "p4b") for c in r2.load_doc()["posting_cases"]]
    assert sum(1 for c in cases if not c["undetermined"] and c["mismatches"]) == 106
