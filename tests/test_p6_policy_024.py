"""
P6 tests for jobops-policy@0.2.4 (OR-74..OR-82).

  * golden cases (tests/fixtures/policy_v024_golden_cases.json): queue evidence completeness (OR-80, F3) and
    single-country remote geography (OR-79, F2), hand-written from the rulings;
  * mutation pairs for both families;
  * the evidence-gap taxonomy has exactly two classes and every UNKNOWN rule is tagged (drift guard);
  * the informational flag set is exactly OR-81 (F4);
  * 0.2.3 -> 0.2.4 attribution on the frozen Round-2 corpus: postings unchanged, only SEQ-07 ordering changes;
  * Gate E on the frozen Round-2 corpus (OR-82): PASS, with every mismatch classified;
  * integrity: historical policies and blind fixtures byte-identical; rulings log append-only.
"""

import copy
import hashlib
import json
import subprocess
from pathlib import Path

import pytest

import r2_blind_harness as r2
import r2_replay
from evaluation import policy_loader
from evaluation.policy_loader import PolicyDriftError, load_policy_version, policy_from_doc
from evaluation.queue import plan_day
from v02_support import fresh_service, no_network, observation  # noqa: F401

V23, V24 = "jobops-policy@0.2.3", "jobops-policy@0.2.4"
ROOT = Path(__file__).resolve().parent.parent
DOC = json.loads((Path(__file__).resolve().parent / "fixtures" / "policy_v024_golden_cases.json")
                 .read_text(encoding="utf-8"))
DATE = DOC["artifact"]["default_evaluation_date"]
OBS = {"source": "ats:greenhouse", "source_kind": "EMPLOYER_ATS", "completeness": "FULL_JD",
       "observed_at": "2026-09-28T06:00:00+00:00", "run_id": "p6-run-1"}


def _ingest_all(items, version, policy=None):
    s = fresh_service(policy or load_policy_version(version))
    s.clock = lambda: DATE
    rid_of = {}
    for it in items:
        o = it["observation"]
        s.classify_company(o["raw_company"], it["classification"], "OWNER_CONFIRMED", "owner")
        res = s.ingest(observation(**{**OBS, **o, "source_url": f"https://careers.x.example/jobs/{it['key']}"}))
        rid_of[it["key"]] = res["requisition_id"]
    return s, rid_of


def _review_order(s, rid_of):
    key_of = {v: k for k, v in rid_of.items()}
    plan = plan_day(s, DATE)
    return [key_of[m] for u in plan["review_today"] + plan["review_carried"] for m in u["member_requisition_ids"]
            if m in key_of]


# ------------------------------------------------------------------ golden

def test_golden_fixture_shape():
    fam = lambda f: [c for c in DOC["cases"] if c["family"] == f]  # noqa: E731
    for f in ("queue", "geography"):
        assert len(fam(f)) >= 10
        assert sum(c["adversarial"] for c in fam(f)) * 2 >= len(fam(f)), f
    assert len({c["case_id"] for c in DOC["cases"]}) == len(DOC["cases"])


@pytest.mark.parametrize("case", [c for c in DOC["cases"] if c["family"] == "queue"],
                         ids=[c["case_id"] for c in DOC["cases"] if c["family"] == "queue"])
def test_queue_golden(case):
    exp = case["expected"]
    s, rid_of = _ingest_all(case["items"], V24)
    for key, n in exp.get("missing", {}).items():
        ec = s.current_evaluation(rid_of[key])["result"]["evidence_completeness"]
        assert ec["missing_evidence_count"] == n, (key, ec)
        assert set(ec["missing_dimensions"]) | set(ec["known_dimensions"]) == set(ec["unknown_dimensions"])
    if "order_024" in exp:
        assert _review_order(s, rid_of) == exp["order_024"]
    if "order_023" in exp:  # older policies keep their ordering
        s3, rid3 = _ingest_all(case["items"], V23)
        assert _review_order(s3, rid3) == exp["order_023"]
        assert "missing_evidence_count" not in s3.current_evaluation(rid3[case["items"][0]["key"]])["result"][
            "evidence_completeness"]


@pytest.mark.parametrize("case", [c for c in DOC["cases"] if c["family"] == "geography"],
                         ids=[c["case_id"] for c in DOC["cases"] if c["family"] == "geography"])
def test_geography_golden(case):
    s, rid_of = _ingest_all(case["items"], V24)
    g = s.current_evaluation(rid_of["G"])["result"]["eligibility_dimensions"]["geography"]
    assert (g["verdict"], g["rule_id"]) == (case["expected"]["geography"], case["expected"]["rule"]), g["facts"]


# ---------------------------------------------------------------- mutations

JD = "We build RAG assistants and run LLM-as-judge hallucination evals on golden datasets."
BASE = {"raw_title": "AI Engineer", "raw_company": "Mut Co", "raw_salary": "Base: ₹30 LPA",
        "raw_employment_type": "Full-time, permanent"}
GEO_MUTATIONS = [
    ("canada-vs-canada-india-welcome", "Remote — Canada", "", " Candidates in India are welcome.", "FAIL", "PASS"),
    ("remote-vs-remote-india-eligible", "Remote", "", " Candidates in India are eligible.", "UNKNOWN", "PASS"),
    ("emea-vs-emea-india-eligible", "Remote — EMEA", "", " Candidates in India are eligible.", "FAIL", "PASS"),  # OR-83
    ("apac-vs-apac-india-eligible", "Remote — APAC", "", " Candidates in India are eligible.", "UNKNOWN", "PASS"),
    ("india-welcome-vs-plus-authorization", "Remote — Canada", " Candidates in India are welcome.",
     " Candidates in India are welcome. You must be authorized to work in Canada.", "PASS", "FAIL"),
    ("india-office-vs-india-candidates", "Remote — Canada", " We have an office in India.",
     " India candidates are welcome.", "FAIL", "PASS"),
    ("germany-vs-germany-worldwide", "Remote, Germany", "", " Worldwide candidates are eligible.", "FAIL", "PASS"),
]


def _geo(location, extra, version=V24):
    it = {"key": "G", "classification": "PRODUCT",
          "observation": {**BASE, "raw_location": location, "raw_text": JD + extra}}
    s, rid = _ingest_all([it], version)
    return s.current_evaluation(rid["G"])["result"]["eligibility_dimensions"]["geography"]["verdict"]


@pytest.mark.parametrize("mid,loc,a,b,va,vb", GEO_MUTATIONS, ids=[m[0] for m in GEO_MUTATIONS])
def test_geography_mutation(mid, loc, a, b, va, vb):
    assert (_geo(loc, a), _geo(loc, b)) == (va, vb)


def _item(key, company, classification="PRODUCT", **over):
    o = {**BASE, "raw_company": company, "raw_location": "Remote - India", "raw_work_mode": "Remote",
         "raw_text": JD, **over}
    return {"key": key, "classification": classification, "observation": {k: v for k, v in o.items() if v is not None}}


def test_queue_mutation_known_vs_missing_flips_order():
    blr = {"raw_location": "Bengaluru", "raw_work_mode": "Hybrid", "raw_text": JD + " Two office days a week at our office."}
    known = [_item("A", "A Co", "CONSULTANCY", **blr), _item("B", "B Co", raw_salary=None)]
    missing = [_item("A", "A Co", "PRODUCT", raw_salary=None, **blr), _item("B", "B Co", raw_salary=None)]
    assert _review_order(*_ingest_all(known, V24)) == ["A", "B"]      # consultancy is known -> 0 missing
    assert _review_order(*_ingest_all(missing, V24)) == ["B", "A"]    # both missing -> REMOTE first


def test_queue_mutation_evidence_gap_tags_drive_ordering():
    """Re-tagging one rule in a variant policy changes the ordering: the tags, not rule ids, decide."""
    doc = copy.deepcopy(load_policy_version(V24).doc)
    for r in doc["rules"]["employer_type"]:
        if r["rule_id"] == "EMPR-R02":
            r["evidence_gap"] = "missing"
    variant = policy_from_doc(doc)
    blr = {"raw_location": "Bengaluru", "raw_work_mode": "Hybrid", "raw_text": JD + " Two office days a week at our office."}
    items = [_item("A", "A Co", "CONSULTANCY", **blr), _item("B", "B Co", raw_salary=None)]
    assert _review_order(*_ingest_all(items, V24)) == ["A", "B"]
    assert _review_order(*_ingest_all(items, V24, variant)) == ["B", "A"]


# ------------------------------------------------------------ taxonomy / flags

def test_evidence_gap_has_exactly_two_classes_and_every_unknown_rule_is_tagged():
    doc = load_policy_version(V24).doc
    gaps = {r.get("evidence_gap") for t in doc["rules"].values() for r in t if r["verdict"] == "UNKNOWN"}
    assert gaps == {"missing", "known"}
    assert all("evidence_gap" not in r for t in doc["rules"].values() for r in t if r["verdict"] != "UNKNOWN")
    assert policy_loader.EVIDENCE_GAPS == ("missing", "known")


@pytest.mark.parametrize("mutation", ["third_class", "untagged", "tag_on_pass"])
def test_evidence_gap_drift_guard(mutation):
    doc = copy.deepcopy(load_policy_version(V24).doc)
    rule = next(r for r in doc["rules"]["employer_type"] if r["rule_id"] == "EMPR-R02")
    if mutation == "third_class":
        rule["evidence_gap"] = "known_ambiguity"
    elif mutation == "untagged":
        rule.pop("evidence_gap")
    else:
        next(r for r in doc["rules"]["employer_type"] if r["verdict"] == "PASS")["evidence_gap"] = "known"
    with pytest.raises(PolicyDriftError):
        policy_from_doc(doc)


def test_known_examples_from_the_ruling_are_tagged_known_and_missing_examples_missing():
    rules = {r["rule_id"]: r for t in load_policy_version(V24).doc["rules"].values() for r in t}
    for rid in ("EMPR-R02", "EMPR-R01", "EOR-R01"):          # consultancy, staffing, EOR
        assert rules[rid]["evidence_gap"] == "known"
    for rid in ("COMP-R06", "GEO-R16", "EMPR-R04"):          # salary undisclosed, arrangement absent, unclassified
        assert rules[rid]["evidence_gap"] == "missing"


def test_informational_flags_are_exactly_or81():
    info = set(load_policy_version(V24).doc["flags"]["informational"])
    expected = {"ABOVE_TARGET", "IN_TARGET", "CTC_BASIS_UNVERIFIED", "MONTHLY_ASSUMED", "COMP_BASIS_UNSTATED",
                "LANGUAGE_PREFERENCE", "TIMEZONE_OVERLAP_US", "TIMEZONE_OVERLAP_UK", "TIMEZONE_OVERLAP_EU",
                "TIMEZONE_OVERLAP_APAC", "EXPERIENCE_SUBSTANTIAL_MISMATCH"}
    assert expected <= info
    assert {f for f in info - expected} == {f for f in info if f.startswith("SENIORITY_")}


def test_relevance_definition_unchanged_from_023():
    """OR-78: no threshold, vocabulary or short-JD change in 0.2.4."""
    assert load_policy_version(V24).doc["relevance"] == load_policy_version(V23).doc["relevance"]


def test_024_differs_from_023_only_in_approved_places():
    a, b = load_policy_version(V23).doc, load_policy_version(V24).doc
    changed = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    assert changed == {"artifact", "parameters", "rules", "queue", "lexicon"}
    assert set(b["parameters"]) - set(a["parameters"]) == {"completeness_counts_missing_only"}
    assert {k for k in set(a["lexicon"]) | set(b["lexicon"]) if a["lexicon"].get(k) != b["lexicon"].get(k)} == \
        {"explicit_eligibility", "explicit_eligibility_note"}
    strip = lambda t: [{k: v for k, v in r.items() if k != "evidence_gap"} for r in t]  # noqa: E731
    for dim in a["rules"]:
        extra = [r["rule_id"] for r in strip(b["rules"][dim]) if r not in strip(a["rules"][dim])]
        assert extra == ([] if dim != "geography" else ["GEO-R26", "GEO-R27"]), dim


# ------------------------------------------------------ frozen Round-2 replay

def test_round2_attribution_023_to_024():
    doc = r2.load_doc()
    for c in doc["posting_cases"]:
        a, b = r2.run_case(c, V23), r2.run_case(c, V24)
        assert a["actual"] == b["actual"], c["id"]
        assert {k: v["rule_id"] for k, v in a["dimensions_raw"].items()} == \
               {k: v["rule_id"] for k, v in b["dimensions_raw"].items()}, c["id"]
    changed = [s["id"] for s in doc["sequences"]
               if json.dumps(r2.run_sequence(s, V23, resolved=True)["mismatches"], sort_keys=True, default=str)
               != json.dumps(r2.run_sequence(s, V24, resolved=True)["mismatches"], sort_keys=True, default=str)]
    assert changed == ["R2-SEQ-07"]


@pytest.fixture(scope="module")
def gate_024():
    return r2_replay.gate_report(V24, r2_replay.load_classification())


def test_gate_e_024_passes(gate_024):
    g = gate_024["gate_E"]
    assert g["gate_E"] == "PASS", g
    for d, v in gate_024["gate_E_dimensions"].items():
        assert v["accuracy"] >= 0.95, (d, v["accuracy"])
    assert all(s["passed"] for s in gate_024["sequences"].values())


def test_every_round2_mismatch_is_classified_and_none_is_an_engine_bug(gate_024):
    cls = r2_replay.load_classification()
    allowed = {"ENGINE_BUG", "CASE_ERROR", "SPEC_AMBIGUITY", "SUPERSEDED_RULING", "ADAPTER_LIMIT"}
    assert {c["class"] for c in cls.values()} <= allowed - {"ENGINE_BUG"}
    for d, v in gate_024["gate_E_dimensions"].items():
        for m in v["mismatches"]:
            assert m["classification"], (d, m)
        for cid in v["unscorable"]:
            assert cls[f"{cid}|fx"]["class"] == "ADAPTER_LIMIT"
    for m in gate_024["relevance_diagnostic"]["mismatches"]:
        assert m["classification"]["class"] == "SPEC_AMBIGUITY"
    for m in gate_024["lane_diagnostic_where_relevance_matches"]["mismatches"]:
        assert m["classification"], m
    assert all(f["explained"] for f in gate_024["safety"]["false_EXCLUDED"])
    assert gate_024["safety"]["false_SHORTLIST"] == []
    assert gate_024["gate_R"].startswith("PENDING REAL-JD LABELS")


def test_gate_e_baseline_023_is_reproducible():
    g = r2_replay.gate_report(V23, r2_replay.load_classification())
    assert g["gate_E"]["dimensions_pass"] and g["gate_E"]["sequences_unexplained"] == ["R2-SEQ-07"]


# ------------------------------------------------------------------ integrity

HASHES = {"policy/jobops-policy-0.2.0.json": "65f74aec883d475989ea0594fac070f547c96a697bc1f7f4b46cf8e0d5dd567a",
          "policy/jobops-policy-0.2.1.json": "af19a3fd998e945cba19ce68f0e36f2eba4156e8bfd5255ac4ea7dacf7f5ea7d",
          "policy/jobops-policy-0.2.2.json": "3743bbaebce2b5f3143ec0a211d6c63aa35b8113dce03b1622876ef43eeed734",
          "policy/jobops-policy-0.2.3.json": "918bf66e7d83d06d7ff7b10c6d8b1309cbabd033331315510851110856659d77",
          "tests/fixtures/policy_v02_blind_cases.json": "44de6af6d8b9bb505044d0b6b871e24cf88a19262bfb90b2b5cf2f6aecdf331a",
          "tests/fixtures/policy_v02_blind_round2_cases.json":
              "f54eb41bc805a28162e69e77495557b3647dd82e3b7c110c2987981edee421e5"}


@pytest.mark.parametrize("path,sha", sorted(HASHES.items()))
def test_frozen_artifacts_are_byte_identical(path, sha):
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha


def test_rulings_recorded_and_log_is_append_only():
    text = (ROOT / "OWNER_RULINGS_LOG.md").read_text(encoding="utf-8")
    for n in range(74, 83):
        assert f"OR-{n} —" in text, n
    try:
        head = subprocess.run(["git", "show", "HEAD:OWNER_RULINGS_LOG.md"], cwd=ROOT, capture_output=True,
                              check=True).stdout.decode("utf-8")
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git history not available in this copy")
    assert text.startswith(head)


def test_german_jd_fails_under_024_detector():
    """OR-69 (E4): the same German JD the historical heuristic test uses is genuine non-English -> FAIL."""
    german = ("Wir suchen eine erfahrene Person für unser Team in Berlin und bieten spannende Aufgaben "
              "mit modernen Werkzeugen sowie flexible Arbeitszeiten für alle Mitarbeitenden in der Firma heute.")
    svc = fresh_service(load_policy_version(V24))
    r = svc.ingest(observation(raw_text=german))["evaluation"]["result"]
    assert r["eligibility_dimensions"]["language"]["verdict"] == "FAIL"
    assert r["eligibility_dimensions"]["language"]["rule_id"] == "LANG-R04"


def test_default_is_024_after_gate_e():
    assert policy_loader.DEFAULT_VERSION == V24


# --------------------------------------------------------- OR-83 (OI-052 = YES)

OR83_TABLE = [
    ("Remote — EMEA", "", "FAIL"),
    ("Remote — EMEA", " Candidates in India are eligible.", "PASS"),
    ("Remote — EMEA", " Worldwide candidates are eligible.", "PASS"),
    ("Remote — APAC", "", "UNKNOWN"),
    ("Remote — APAC", " Candidates in India are eligible.", "PASS"),
    ("Remote — Canada", "", "FAIL"),
    ("Remote — Canada", " Candidates in India are eligible.", "PASS"),
    ("Remote — Canada", " Worldwide candidates are eligible.", "PASS"),
    ("Remote", "", "UNKNOWN"),
    ("Remote — LATAM", " Candidates in India are eligible.", "PASS"),
    ("Remote — UK/Europe", " Candidates in India are eligible.", "PASS"),
]


@pytest.mark.parametrize("loc,extra,verdict", OR83_TABLE, ids=[f"{l}{e}".strip() for l, e, _ in OR83_TABLE])
def test_or83_owner_table(loc, extra, verdict):
    assert _geo(loc, extra) == verdict


# Removing the explicit eligibility statement restores the restrictive-region behaviour.
OR83_MUTATIONS = [
    ("Remote — EMEA", " Candidates in India are eligible.", "FAIL"),
    ("Remote — EMEA", " Worldwide candidates are eligible.", "FAIL"),
    ("Remote — LATAM", " Candidates in India are eligible.", "FAIL"),
    ("Remote — UK/Europe", " Worldwide candidates are eligible.", "FAIL"),
    ("Remote — Canada", " Candidates in India are eligible.", "FAIL"),
    ("Remote — APAC", " Candidates in India are eligible.", "UNKNOWN"),
]


@pytest.mark.parametrize("loc,statement,without", OR83_MUTATIONS,
                         ids=[f"{l}{s}".strip() for l, s, _ in OR83_MUTATIONS])
def test_or83_mutation_removing_eligibility_restores_restriction(loc, statement, without):
    assert _geo(loc, statement) == "PASS"
    assert _geo(loc, "") == without


def test_or83_recorded_and_oi052_resolved():
    rulings = (ROOT / "OWNER_RULINGS_LOG.md").read_text(encoding="utf-8")
    assert "## 80. OR-83 — Explicit India/worldwide eligibility overrides an India-excluding region (OI-052)" in rulings
    items = (ROOT / "docs" / "architecture" / "JOBOPS_V2_OPEN_ITEMS.md").read_text(encoding="utf-8")
    resolved = items.split("## P6.3 Resolved after P6", 1)[1]
    assert "| OI-052 | **RESOLVED** | **YES**" in resolved and "OR-83" in resolved
    assert "| OI-052 | YES/NO" in items  # the original open item is kept, not deleted


def test_geo_r27_is_pass_and_carries_no_evidence_gap():
    r27 = next(r for r in load_policy_version(V24).doc["rules"]["geography"] if r["rule_id"] == "GEO-R27")
    assert r27["verdict"] == "PASS" and r27["flags"] == [] and "evidence_gap" not in r27
