"""
P8b tests for jobops-policy@0.2.6: the owner rulings OR-89 (OI-053), OR-90 (OI-054) and OR-91 (OI-055).

  * ruling golden cases (tests/fixtures/policy_v026_golden_cases.json), positive and negative per ruling;
  * in-memory mutations (tests/p8b_mutations.py): removing a ruling's implementation fails its cases;
  * supersessions: OD25 and P8-PRF-01..03 keep their historical expectation under the versions they still
    govern and carry an explicit, ruling-referenced expectation from 0.2.6 on (never edited in place);
  * every other P5 / P6 / P8 golden expectation, the P8 queue scenarios and the OR-83 table hold under 0.2.6;
  * Round 1 / Round 2: no lane change 0.2.5 -> 0.2.6; Round 3 (regression only): only R3-012 remains (OI-054);
  * integrity: 0.2.0-0.2.5 byte-identical, 0.2.6 differs from 0.2.5 only in approved places, default unchanged.
"""

import hashlib
import json
from pathlib import Path

import pytest

import r2_blind_harness as r2
import r2_replay
import r3_blind_harness as r3
import test_p5_policy_023 as p5
import test_p6_policy_024 as p6
import test_p8_policy_025 as p8
import test_policy_v02_blind as r1
from evaluation import policy_loader
from evaluation.policy_loader import load_policy_version
from p8b_mutations import MUTATIONS, mutated_policy
from v02_support import fresh_service, no_network, observation  # noqa: F401

V25, V26 = "jobops-policy@0.2.5", "jobops-policy@0.2.6"
ROOT = Path(__file__).resolve().parent.parent
DOC = json.loads((Path(__file__).resolve().parent / "fixtures" / "policy_v026_golden_cases.json").read_text(encoding="utf-8"))
CASES = DOC["cases"]
SUPERSEDED = {(s["fixture"].rsplit("/", 1)[1], s["case_id"]): s for s in DOC["supersessions"]}


def _geo(r):
    g = r["eligibility_dimensions"]["geography"]
    return {"verdict": g["verdict"], "rule": g["rule_id"], "lane": r["lane"]}


# ------------------------------------------------------------- ruling cases

def test_fixture_shape():
    assert DOC["case_count"] == len(CASES) and len({c["case_id"] for c in CASES}) == len(CASES)
    for oi in ("OI-053", "OI-054", "OI-055"):
        mine = [c for c in CASES if c["oi"] == oi]
        assert any(c["polarity"] == "positive" for c in mine) and any(c["polarity"] == "negative" for c in mine), oi
    for ruling in ("OR-89", "OR-91"):  # the behaviour-changing rulings are exercised by their cases
        assert any(c["ruling"] == ruling and c["mutation"].get("fails_without_ruling") for c in CASES), ruling
    assert all(c["mutation"]["remove"] is None for c in CASES if c["oi"] == "OI-054")


@pytest.mark.parametrize("case", CASES, ids=[c["case_id"] for c in CASES])
def test_ruling_case_under_026(case):
    r = p8._run(case, load_policy_version(V26))
    assert r["policy_version"] == V26
    p5._check(case["expected"], r)


@pytest.mark.parametrize("case", [c for c in CASES if c["mutation"]["remove"]],
                         ids=[c["case_id"] for c in CASES if c["mutation"]["remove"]])
def test_ruling_mutation(case):
    m = case["mutation"]
    got = _geo(p8._run(case, mutated_policy(m["remove"])))
    assert got == m["expected_without_ruling"]
    exp = case["expected"]
    assert ((got["verdict"], got["rule"], got["lane"]) != (exp["dimensions"]["geography"], exp["rules"]["geography"],
                                                           exp["lane"])) == m["fails_without_ruling"]


def test_every_mutation_is_exercised():
    assert {c["mutation"]["remove"] for c in CASES if c["mutation"].get("fails_without_ruling")} == set(MUTATIONS)


def test_oi054_unnamed_country_never_fails_under_any_supported_policy():
    case = next(c for c in CASES if c["case_id"] == "B54-01")
    for v in (V25, V26):
        r = p8._run(case, load_policy_version(v))
        assert _geo(r) == {"verdict": "UNKNOWN", "rule": "GEO-R05", "lane": "REVIEW"}, v


def test_oi053_preference_never_overrides_an_exclusion():
    for c in (c for c in CASES if c["oi"] == "OI-053" and c["polarity"] == "negative"):
        r = p8._run(c, load_policy_version(V26))
        assert r["eligibility_dimensions"]["geography"]["verdict"] != "PASS" and r["lane"] != "SHORTLIST", c["case_id"]


# -------------------------------------------------------------- supersessions

@pytest.mark.parametrize("sup", DOC["supersessions"], ids=[s["case_id"] for s in DOC["supersessions"]])
def test_supersession_is_auditable(sup):
    """The historical expectation is kept verbatim and still governs the old versions; 0.2.6 follows the ruling."""
    if sup["fixture"].endswith("policy_v023_golden_cases.json"):
        case = next(c for c in p5.DOC["cases"] if c["case_id"] == sup["case_id"])
        assert case["expected"] == sup["historical_expected"]
        for v in sup["historical_versions"]:
            p5._check(sup["historical_expected"], p5._run(case["observation"], v, case.get("classification"))[0])
        p5._check(sup["expected_from_0_2_6"], p5._run(case["observation"], V26, case.get("classification"))[0])
    else:
        case = next(c for c in p8.CASES if c["case_id"] == sup["case_id"])
        assert case["expected"] == sup["historical_expected"]
        for v in sup["historical_versions"]:
            p5._check(sup["historical_expected"], p8._run(case, load_policy_version(v)))
        p5._check(sup["expected_from_0_2_6"], p8._run(case, load_policy_version(V26)))
    assert sup["superseded_by"].split()[0] in ("OR-89", "OR-91")


# ------------------------------------------- earlier golden fixtures on 0.2.6

@pytest.mark.parametrize("case", p5.DOC["cases"], ids=[c["case_id"] for c in p5.DOC["cases"]])
def test_p5_golden_under_026(case):
    sup = SUPERSEDED.get(("policy_v023_golden_cases.json", case["case_id"]))
    r, _ = p5._run(case["observation"], V26, case.get("classification"))
    p5._check(sup["expected_from_0_2_6"] if sup else case["expected"], r)


@pytest.mark.parametrize("case", p8.CASES, ids=[c["case_id"] for c in p8.CASES])
def test_p8_golden_under_026(case):
    sup = SUPERSEDED.get(("policy_v025_golden_cases.json", case["case_id"]))
    p5._check(sup["expected_from_0_2_6"] if sup else case["expected"], p8._run(case, load_policy_version(V26)))


@pytest.mark.parametrize("scenario", p8.DOC["queue_scenarios"], ids=[q["id"] for q in p8.DOC["queue_scenarios"]])
def test_p8_queue_scenarios_under_026(scenario):
    p8._check_queue(scenario["expect"], p8._run_queue(scenario, load_policy_version(V26)))


@pytest.mark.parametrize("case", [c for c in p6.DOC["cases"] if c["family"] == "geography"],
                         ids=[c["case_id"] for c in p6.DOC["cases"] if c["family"] == "geography"])
def test_p6_geography_golden_under_026(case):
    s, rid_of = p6._ingest_all(case["items"], V26)
    g = s.current_evaluation(rid_of["G"])["result"]["eligibility_dimensions"]["geography"]
    assert (g["verdict"], g["rule_id"]) == (case["expected"]["geography"], case["expected"]["rule"])


@pytest.mark.parametrize("loc,extra,verdict", p6.OR83_TABLE, ids=[f"{l}{e}".strip() for l, e, _ in p6.OR83_TABLE])
def test_or83_owner_table_under_026(loc, extra, verdict):
    assert p6._geo(loc, extra, V26) == verdict


# ------------------------------------------------------ Round 1 / 2 / 3

def test_round1_and_round2_no_lane_change_025_to_026():
    changed = {c["id"]: (p8._r1_lane(c, V25), p8._r1_lane(c, V26)) for c in r1.DOC["cases"]}
    for c in r2.load_doc()["posting_cases"]:
        changed[c["id"]] = (r2.run_case(c, V25)["actual"]["lane"], r2.run_case(c, V26)["actual"]["lane"])
    assert {k: v for k, v in changed.items() if v[0] != v[1]} == {}
    rep = r2_replay.gate_report(V26, r2_replay.load_classification())
    assert rep["gate_E"]["gate_E"] == "PASS"


def test_round3_under_026_only_oi054_remains():
    out = r3.run_all(V26)
    assert out["dimension_mismatch_cases"] == ["R3-012"] and set(out["any_mismatch_cases"]) == {"R3-012"}
    assert out["cases"]["R3-012"]["rules"]["geography"] == "GEO-R05"
    assert out["cases"]["R3-012"]["actual"]["geography"] == "UNKNOWN"
    assert out["cases"]["R3-010"]["actual"]["geography"] == "PASS"  # OR-89
    assert out["cases"]["R3-018"]["rules"]["geography"] == "GEO-R07"  # OR-91
    assert out["false_excluded"] == [] and out["false_shortlist"] == [] and out["review_noise"] == []
    assert all(v["passed"] for v in out["sequences"].values())  # S-02 (OR-91), S-08 (OR-88)


# ------------------------------------------------------------------ integrity

HASHES = {"0.2.0": "65f74aec883d475989ea0594fac070f547c96a697bc1f7f4b46cf8e0d5dd567a",
          "0.2.1": "af19a3fd998e945cba19ce68f0e36f2eba4156e8bfd5255ac4ea7dacf7f5ea7d",
          "0.2.2": "3743bbaebce2b5f3143ec0a211d6c63aa35b8113dce03b1622876ef43eeed734",
          "0.2.3": "918bf66e7d83d06d7ff7b10c6d8b1309cbabd033331315510851110856659d77",
          "0.2.4": "735934bf33533a31d207349cf689a3df6dafcdacc9c6a11b889b92e5af8c8136",
          "0.2.5": "27fe5d1accff78ce9db8ccc5f42a7d905b3e709a474d93d446e19a795ad53c93"}


@pytest.mark.parametrize("version,sha", sorted(HASHES.items()))
def test_historical_policies_byte_identical(version, sha):
    path = ROOT / "policy" / f"jobops-policy-{version}.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha


def test_026_registered_not_default_and_records_025():
    assert V26 in policy_loader.POLICY_PATHS and policy_loader.DEFAULT_VERSION == "jobops-policy@0.2.4"
    assert load_policy_version(V26).doc["artifact"]["v0_2_5_artifact"]["sha256"] == HASHES["0.2.5"]


def test_026_differs_from_025_only_in_approved_places():
    a, b = load_policy_version(V25).doc, load_policy_version(V26).doc
    assert {k for k in a if a[k] != b[k]} == {"artifact", "parameters", "rules", "lexicon"}
    assert {k for k in b["parameters"] if a["parameters"].get(k) != b["parameters"][k]} == {
        "india_preference_is_eligibility", "office_days_override_hybrid_label"}
    assert {k for k in b["lexicon"] if a["lexicon"][k] != b["lexicon"][k]} == {"india_eligibility"}
    ie_a, ie_b = a["lexicon"]["india_eligibility"], b["lexicon"]["india_eligibility"]
    assert {k for k in ie_b if ie_a.get(k) != ie_b[k]} == {"india_place", "precedence", "note"}
    assert {d for d in a["rules"] if a["rules"][d] != b["rules"][d]} == {"geography"}
    strip = lambda r: {k: v for k, v in r.items() if k not in ("note", "ruling")}  # noqa: E731
    assert [strip(r) for r in a["rules"]["geography"]] == [strip(r) for r in b["rules"]["geography"]]
    assert b["flags"] == a["flags"] and b["queue"] == a["queue"] and b["relevance"] == a["relevance"]


def test_rulings_recorded_and_open_items_resolved():
    rulings = (ROOT / "OWNER_RULINGS_LOG.md").read_text(encoding="utf-8")
    added = rulings.split("# Addendum J", 1)[1]
    for n, oid, oi in ((86, "OR-89", "OI-053"), (87, "OR-90", "OI-054"), (88, "OR-91", "OI-055")):
        assert f"## {n}. {oid} — " in added and f"({oi})" in added
    assert "OD25" in added.split("## 88. OR-91", 1)[1]
    # Addendum I keeps the open questions as recorded (append-only; their RULING fields are not back-filled).
    addendum_i = rulings.split("# Addendum I", 1)[1].split("# Addendum J", 1)[0]
    assert addendum_i.count("### RULING:\n\n---") == 3
    items = (ROOT / "docs" / "architecture" / "JOBOPS_V2_OPEN_ITEMS.md").read_text(encoding="utf-8")
    resolved = items.split("## P8b Resolved", 1)[1]
    for oi, ruling in (("OI-053", "OR-89"), ("OI-054", "OR-90"), ("OI-055", "OR-91")):
        assert f"| {oi} | **RESOLVED**" in resolved and ruling in resolved
