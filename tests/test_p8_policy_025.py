"""
P8 tests for jobops-policy@0.2.5 (Round-3 fix pass: general extraction rules and OR-88).

  * golden cases (tests/fixtures/policy_v025_golden_cases.json): seven fix families with positive and negative
    phrasings written independently of the Round-3 corpus;
  * mutation checks (P8 §17): removing one fix family in memory (tests/p8_mutations.py) makes that family's own
    golden cases fail in the expected direction; regression guards hold either way;
  * OR-88 queue scenarios (below / at / over the cap, STRONG exemption, D..D+2 carry) and OR-87 newness order;
  * P5 / P6 golden fixtures still hold under 0.2.5;
  * Round 1 and Round 2: no lane changes from 0.2.4 to 0.2.5 (so no new false EXCLUDED / SHORTLIST); Round-2
    Gate E still passes;
  * Round 3 (consumed, regression only, tests/r3_blind_harness.py): the 0.2.4 run reproduces P7b Part B and
    the 0.2.5 run leaves only the three owner-pending cases;
  * integrity: historical artifacts and frozen fixtures byte-identical, no Round-3 special-casing, OI-053 open.
"""

import copy
import hashlib
import json
import re
from pathlib import Path

import pytest

import r2_blind_harness as r2
import r2_replay
import r3_blind_harness as r3
import test_p5_policy_023 as p5
import test_p6_policy_024 as p6
from evaluation import policy_loader
from evaluation.policy_loader import load_policy_version
from evaluation.queue import plan_day
from p8_mutations import MUTATIONS, mutated_policy
from store import repository as repo
from v02_support import fresh_service, no_network, observation  # noqa: F401

V24, V25 = "jobops-policy@0.2.4", "jobops-policy@0.2.5"
ROOT = Path(__file__).resolve().parent.parent
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "policy_v025_golden_cases.json"
DOC = json.loads(FIXTURE.read_text(encoding="utf-8"))
ART = DOC["artifact"]
DATE = ART["default_evaluation_date"]
CASES = DOC["cases"]
FAMILIES = ("india_eligibility", "region_residence_authorization", "office_days", "location_pay",
            "client_placement", "language_preference")


def _run(case, policy):
    s = fresh_service(policy)
    s.clock = lambda: DATE
    obs = {**ART["base_observation"], **case["observation"]}
    obs["raw_text"] = ART["jd_prefix"] + " " + case["observation"]["raw_text"] \
        if case["observation"].get("raw_text") else ART["jd_prefix"]
    obs = {k: v for k, v in obs.items() if v is not None}
    s.classify_company(obs["raw_company"], case["classification"], "OWNER_CONFIRMED", "owner")
    if case.get("fx"):
        fx = case["fx"]
        s.add_fx_rate(fx["currency"], fx["rate"], fx["snapshot_date"], "p8-golden")
    return s.ingest(observation(**obs))["evaluation"]["result"]


def _focus(case):
    return next(iter(case["expected"]["rules"]))


# ------------------------------------------------------------------ golden

def test_fixture_shape():
    assert DOC["case_count"] == len(CASES) >= 60
    assert len({c["case_id"] for c in CASES}) == len(CASES)
    for fam in FAMILIES:
        mine = [c for c in CASES if c["family"] == fam]
        assert sum(c["polarity"] == "positive" for c in mine) >= 3, fam
        assert sum(c["polarity"] == "negative" for c in mine) >= 2, fam
        flips = [c for c in mine if c["mutation"]["fails_without_fix"]]
        assert any(c["polarity"] == "positive" for c in flips), f"{fam}: no positive case exercises the fix"
        assert any(c["polarity"] in ("negative", "preference") for c in flips), f"{fam}: no negative exercises it"
    assert len(DOC["queue_scenarios"]) >= 5


@pytest.mark.parametrize("case", CASES, ids=[c["case_id"] for c in CASES])
def test_golden_025(case):
    r = _run(case, load_policy_version(V25))
    assert r["policy_version"] == V25
    p5._check(case["expected"], r)


@pytest.mark.parametrize("case", CASES, ids=[c["case_id"] for c in CASES])
def test_mutation_removing_the_fix(case):
    """P8 §17: with only this case's fix family removed, the case behaves as recorded (and fails if it flips)."""
    m = case["mutation"]
    r = _run(case, mutated_policy(m["remove_fix"]))
    d = r["eligibility_dimensions"][_focus(case)]
    got = {"verdict": d["verdict"], "rule": d["rule_id"], "lane": r["lane"]}
    assert got == m["expected_without_fix"], got
    exp = case["expected"]
    differs = (got["verdict"], got["rule"], got["lane"]) != (exp["dimensions"][_focus(case)], exp["rules"][_focus(case)],
                                                             exp["lane"])
    assert differs == m["fails_without_fix"]


def test_every_mutation_family_is_exercised():
    removed = {c["mutation"]["remove_fix"] for c in CASES if c["mutation"]["fails_without_fix"]}
    assert removed | {"d3_parking"} == set(MUTATIONS), set(MUTATIONS) - removed


def test_preference_never_fails_and_never_excludes():
    """OI-053 (open): an India preference is UNKNOWN -> REVIEW until the owner rules; never FAIL / EXCLUDED."""
    pref = [c for c in CASES if c["polarity"] == "preference"]
    for c in pref:
        r = _run(c, load_policy_version(V25))
        assert r["eligibility_dimensions"]["geography"]["verdict"] != "FAIL" and r["lane"] != "EXCLUDED", c["case_id"]


def test_language_preference_is_informational_only():
    pol = load_policy_version(V25)
    assert "LANGUAGE_PREFERENCE" in pol.info_flags and "LANGUAGE_PREFERENCE" not in pol.review_flags
    for c in (c for c in CASES if c["family"] == "language_preference" and c["polarity"] == "positive"):
        r = _run(c, pol)
        assert "LANGUAGE_PREFERENCE" in r["flags"] and r["lane"] == "SHORTLIST", c["case_id"]


# ---------------------------------------------------------------- OR-88 queue

_STRONG_JD = ART["jd_prefix"]


def _queue_item(key, kind):
    obs = {"source": "ats:greenhouse", "source_kind": "EMPLOYER_ATS", "raw_company": f"Queue Co {key}",
           "raw_salary": "Competitive", "raw_employment_type": "Full-time, permanent",
           "source_url": f"https://careers.queue-{key.lower()}.example/jobs/{key}"}
    if kind == "strong_remote":
        obs.update(raw_title="AI Engineer", raw_location="Remote - India", raw_work_mode="Remote",
                   completeness="FULL_JD", raw_text=_STRONG_JD)
    elif kind == "strong_hybrid":
        obs.update(raw_title="AI Engineer", raw_location="Bengaluru", raw_work_mode="Hybrid", completeness="FULL_JD",
                   raw_text=_STRONG_JD + " You will be in the office two days a week.")
    else:  # tier1_no_jd: NOT_ASSESSED -> REVIEW (LANE-R03), non-STRONG
        obs.update(raw_title="AI Engineer", raw_location="Remote - India", raw_work_mode="Remote",
                   completeness="SEARCH_ONLY", raw_text=None, source="linkedin", source_kind="JOB_BOARD",
                   apply_url=obs.pop("source_url"))
    return obs


def _expand(tokens):
    out = []
    for t in tokens:
        if ":" in t:
            prefix, n = t.split(":")
            out += [f"{prefix}{i:02d}" for i in range(1, int(n) + 1)]
        else:
            out.append(t)
    return out


def _expect_keys(v):
    if isinstance(v, list):
        return sorted(v)
    return sorted(_expand(v.split("+")))


def _run_queue(scenario, policy):
    s = fresh_service(policy)
    days = ["2026-09-24", "2026-09-25", "2026-09-26", "2026-09-27"]
    rid_of, out = {}, {}
    for i, spec in enumerate(scenario["days"]):
        day = days[i]
        s.clock = lambda d=day: d
        for key in _expand(spec["add"]):
            kind = "tier1_no_jd" if key == "N" else ("strong_hybrid" if key == "H" else "strong_remote")
            res = s.ingest(observation(**{**_queue_item(key, kind), "observed_at": f"{day}T06:00:00+00:00",
                                          "run_id": f"{scenario['id']}-{day}"}))
            rid_of[key] = res["requisition_id"]
        key_of = {v: k for k, v in rid_of.items()}
        plan = plan_day(s, day)
        keys = lambda units: sorted(key_of[m] for u in units for m in u["member_requisition_ids"])  # noqa: E731
        out[str(i)] = {"shown": keys(plan["review_today"]), "carried": keys(plan["review_carried"]),
                       "parked": keys(plan["overflow_parked_today"])}
        for u in plan["review_today"]:  # the owner acts on every item shown
            for m in u["member_requisition_ids"]:
                s.record_review_decision(m, "SKIP", actor="human", note="P8 queue scenario")
    return out


def _check_queue(expect, got):
    for day, e in expect.items():
        assert {k: _expect_keys(v) for k, v in e.items()} == got[day], (day, got[day])


@pytest.mark.parametrize("scenario", DOC["queue_scenarios"], ids=[q["id"] for q in DOC["queue_scenarios"]])
def test_or88_queue_scenario(scenario):
    _check_queue(scenario["expect"], _run_queue(scenario, load_policy_version(V25)))


@pytest.mark.parametrize("scenario", DOC["queue_scenarios"], ids=[q["id"] for q in DOC["queue_scenarios"]])
def test_or88_mutation_and_024_unchanged(scenario):
    """Without the OR-88 fix (in memory) and under the frozen 0.2.4, the pre-OR-88 behaviour is reproduced."""
    _check_queue(scenario["expect_without_fix"], _run_queue(scenario, mutated_policy("d3_parking")))
    _check_queue(scenario["expect_without_fix"], _run_queue(scenario, load_policy_version(V24)))


def test_or88_flips_below_and_at_cap_only():
    flips = {q["id"] for q in DOC["queue_scenarios"]
             if any(q["expect"][d] != q["expect_without_fix"][d] for d in q["expect_without_fix"] if d in q["expect"])}
    assert flips == {"P8-Q1", "P8-Q2"}


def test_newness_order_new_updated_seen_before_under_025():
    """OR-87: NEW > UPDATED > SEEN_BEFORE among items of equal relevance; cap 10."""
    s = fresh_service(load_policy_version(V25))
    early, day = "2026-09-23", "2026-09-24"
    s.clock = lambda: early
    for key, over in (("B", {}), ("C", {"raw_salary": "₹30 LPA"})):
        s.ingest(observation(**{**_queue_item(key, "tier1_no_jd"), **over, "observed_at": f"{early}T06:00:00+00:00",
                                "run_id": "p8-newness-early"}))
    s.clock = lambda: day
    rid = {}
    # B re-sighted unchanged (SEEN_BEFORE); C with a changed figure (UPDATED, OR-55); A first seen today (NEW).
    for key, over in (("B", {}), ("C", {"raw_salary": "₹34 LPA"}), ("A", {})):
        res = s.ingest(observation(**{**_queue_item(key, "tier1_no_jd"), **over,
                                      "observed_at": f"{day}T06:00:00+00:00", "run_id": "p8-newness"}))
        rid[key] = res["requisition_id"]
    for i in range(1, 10):
        s.ingest(observation(**{**_queue_item(f"S{i:02d}", "strong_remote"), "observed_at": f"{day}T06:00:00+00:00",
                                "run_id": "p8-newness"}))
    states = {k: repo.get_requisition(s.conn, v)["newness_state"] for k, v in rid.items()}
    assert states == {"A": "NEW", "B": "SEEN_BEFORE", "C": "UPDATED"}
    plan = plan_day(s, day)
    key_of = {v: k for k, v in rid.items()}
    shown = [key_of[m] for u in plan["review_today"] for m in u["member_requisition_ids"] if m in key_of]
    carried = [key_of[m] for u in plan["review_carried"] for m in u["member_requisition_ids"] if m in key_of]
    assert shown == ["A"] and carried == ["C", "B"]
    assert load_policy_version(V25).doc["queue"]["ordering"] == load_policy_version(V24).doc["queue"]["ordering"]


# --------------------------------------------- earlier golden fixtures on 0.2.5

@pytest.mark.parametrize("case", p5.DOC["cases"], ids=[c["case_id"] for c in p5.DOC["cases"]])
def test_p5_golden_holds_under_025(case):
    r, _ = p5._run(case["observation"], V25, case.get("classification"))
    p5._check(case["expected"], r)


@pytest.mark.parametrize("case", [c for c in p6.DOC["cases"] if c["family"] == "geography"],
                         ids=[c["case_id"] for c in p6.DOC["cases"] if c["family"] == "geography"])
def test_p6_geography_golden_holds_under_025(case):
    s, rid_of = p6._ingest_all(case["items"], V25)
    g = s.current_evaluation(rid_of["G"])["result"]["eligibility_dimensions"]["geography"]
    assert (g["verdict"], g["rule_id"]) == (case["expected"]["geography"], case["expected"]["rule"]), g["facts"]


@pytest.mark.parametrize("case", [c for c in p6.DOC["cases"] if c["family"] == "queue" and "order_024" in c["expected"]],
                         ids=[c["case_id"] for c in p6.DOC["cases"] if c["family"] == "queue"
                              and "order_024" in c["expected"]])
def test_p6_queue_golden_holds_under_025(case):
    s, rid_of = p6._ingest_all(case["items"], V25)
    assert p6._review_order(s, rid_of) == case["expected"]["order_024"]


@pytest.mark.parametrize("loc,extra,verdict", p6.OR83_TABLE, ids=[f"{l}{e}".strip() for l, e, _ in p6.OR83_TABLE])
def test_or83_owner_table_under_025(loc, extra, verdict):
    assert p6._geo(loc, extra, V25) == verdict


# ------------------------------------------------- Round 1 / Round 2 regression

def _r1_lane(case, version):
    import test_policy_v02_blind as r1
    p = case["posting"]
    service = fresh_service(load_policy_version(version))
    service.clock = lambda: p.get("evaluation_date") or r1.DEFAULT_DATE
    r1._prepare(service, p, set(), set())
    res = service.ingest(observation(**r1._obs_fields(p, idx=case["id"])))
    return res["evaluation"]["result"]["lane"]


def test_round1_no_lane_change_024_to_025():
    import test_policy_v02_blind as r1
    changed = {c["id"]: (_r1_lane(c, V24), _r1_lane(c, V25)) for c in r1.DOC["cases"]}
    changed = {k: v for k, v in changed.items() if v[0] != v[1]}
    assert changed == {}


def test_round2_no_lane_change_and_gate_e_still_passes():
    changed = {}
    for c in r2.load_doc()["posting_cases"]:
        a, b = r2.run_case(c, V24)["actual"]["lane"], r2.run_case(c, V25)["actual"]["lane"]
        if a != b:
            changed[c["id"]] = (a, b)
    assert changed == {}
    rep = r2_replay.gate_report(V25, r2_replay.load_classification())
    assert rep["gate_E"]["gate_E"] == "PASS"
    assert not rep["gate_E"]["unexplained_false_excluded"] and not rep["gate_E"]["unexplained_false_shortlist"]


# ---------------------------------------------- Round 3 (consumed; regression only)

@pytest.fixture(scope="module")
def r3_runs():
    return {v: r3.run_all(v) for v in (V24, V25)}


def test_r3_harness_reproduces_p7b_part_b_under_024(r3_runs):
    out = r3_runs[V24]
    assert {d: (v["correct"], v["total"]) for d, v in out["dimensions"].items()} == {
        "geography": (97, 107), "compensation": (106, 107), "employment_type": (106, 107),
        "employer_type": (106, 106), "language": (105, 105)}
    assert out["dimension_mismatch_cases"] == ["R3-003", "R3-005", "R3-010", "R3-012", "R3-014", "R3-015", "R3-018",
                                               "R3-020", "R3-033", "R3-034", "R3-059", "R3-078"]
    assert sorted(set(out["any_mismatch_cases"]) - set(out["dimension_mismatch_cases"])) == ["R3-087"]
    assert out["false_excluded"] == ["R3-005"] and out["false_shortlist"] == []
    assert {k for k, v in out["sequences"].items() if not v["passed"]} == {"S-02", "S-08"}


# Remaining Round-3 discrepancies under 0.2.5, each explained in docs/reports/JOBOPS_P8_ROUND3_FIX_REPORT_2026-10-01.md.
R3_PENDING = {
    "R3-010": "INTENTIONAL_PENDING_OI:OI-053 (India preference/priority) -> UNKNOWN GEO-R29",
    "R3-012": "INTENTIONAL_PENDING_OI:OI-054 (authorization in 'the country where the job is posted', no country stated)",
    "R3-018": "INTENTIONAL_PENDING_OI:OI-055 (structured Hybrid + JD five office days: OR-15 FAIL vs accepted OD25 conflict)",
}


def test_r3_under_025_only_owner_pending_cases_remain(r3_runs):
    out = r3_runs[V25]
    assert set(out["dimension_mismatch_cases"]) == set(R3_PENDING)
    assert set(out["any_mismatch_cases"]) == set(R3_PENDING)
    assert out["false_excluded"] == [] and out["false_shortlist"] == [] and out["review_noise"] == []
    rules = {k: out["cases"][k]["rules"]["geography"] for k in R3_PENDING}
    assert rules == {"R3-010": "GEO-R29", "R3-012": "GEO-R05", "R3-018": "GEO-R25"}
    assert all(out["cases"][k]["actual"]["geography"] == "UNKNOWN" for k in R3_PENDING)


def test_r3_sequences_under_025(r3_runs):
    seqs = r3_runs[V25]["sequences"]
    assert {k for k, v in seqs.items() if not v["passed"]} == {"S-02"}  # OI-055, same pattern as R3-018
    assert all(m["field"] in ("geography", "excluded") for m in seqs["S-02"]["mismatches"])
    assert seqs["S-08"]["passed"]  # OR-88


def test_r3_corpus_and_overlay_unchanged():
    r3.verify_corpus()
    assert hashlib.sha256(r3.OVERLAY.read_bytes()).hexdigest() == \
        "886bae12aa40d7622cb0dbad0a91262068dd2112c6fc1998625832487ee5c876"


# ------------------------------------------------------------------ integrity

HASHES = {"policy/jobops-policy-0.2.0.json": "65f74aec883d475989ea0594fac070f547c96a697bc1f7f4b46cf8e0d5dd567a",
          "policy/jobops-policy-0.2.1.json": "af19a3fd998e945cba19ce68f0e36f2eba4156e8bfd5255ac4ea7dacf7f5ea7d",
          "policy/jobops-policy-0.2.2.json": "3743bbaebce2b5f3143ec0a211d6c63aa35b8113dce03b1622876ef43eeed734",
          "policy/jobops-policy-0.2.3.json": "918bf66e7d83d06d7ff7b10c6d8b1309cbabd033331315510851110856659d77",
          "policy/jobops-policy-0.2.4.json": "735934bf33533a31d207349cf689a3df6dafcdacc9c6a11b889b92e5af8c8136",
          "tests/fixtures/policy_v02_blind_cases.json": None,
          "tests/fixtures/policy_v02_blind_round2_cases.json": None,
          "data/fixtures/round3/blind_cases_round3.json": r3.EXPECTED_SHA}


@pytest.mark.parametrize("path,sha", sorted(HASHES.items()))
def test_frozen_artifacts_are_byte_identical(path, sha):
    if sha is None:  # the blind fixtures carry their own recorded hash
        sha = (ROOT / (path.replace(".json", ".sha256"))).read_text(encoding="utf-8").split()[0]
    assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha


def test_025_registered_but_not_default():
    assert V25 in policy_loader.POLICY_PATHS
    assert policy_loader.DEFAULT_VERSION == V24  # 0.2.5 awaits its fresh Round-4 Gate E measurement
    assert load_policy_version(V25).doc["artifact"]["v0_2_4_artifact"]["sha256"] == HASHES[
        "policy/jobops-policy-0.2.4.json"]


def test_025_differs_from_024_only_in_approved_places():
    a, b = load_policy_version(V24).doc, load_policy_version(V25).doc
    changed = {k for k in a if a[k] != b[k]}
    assert changed == {"artifact", "parameters", "rules", "lexicon", "flags", "queue"}
    assert {k for k in b["parameters"] if a["parameters"].get(k) != b["parameters"][k]} == {
        "bengaluru_hybrid_fail_min_office_days", "lock_lists_including_india_do_not_exclude"}
    assert {d for d in a["rules"] if a["rules"][d] != b["rules"][d]} == {"geography"}
    old_geo = {r["rule_id"]: r for r in a["rules"]["geography"]}
    new_geo = {r["rule_id"]: r for r in b["rules"]["geography"]}
    assert set(new_geo) - set(old_geo) == {"GEO-R28", "GEO-R29"} and set(old_geo) <= set(new_geo)
    assert all(new_geo[k] == old_geo[k] for k in old_geo)
    assert set(b["flags"]["review_routing"]) - set(a["flags"]["review_routing"]) == {
        "HYBRID_DAYS_BETWEEN_THRESHOLDS", "GEO_INDIA_PREFERENCE_UNRESOLVED"}
    assert b["flags"]["informational"] == a["flags"]["informational"]
    assert {k for k in b["lexicon"] if a["lexicon"].get(k) != b["lexicon"][k]} == {
        "residence_requirement", "work_authorization", "relocation_negation", "lock_negation_before",
        "lock_negation_window_words", "lock_negation_note", "india_eligibility", "office_day_normalization",
        "language", "compensation", "relationship", "relationship_negation_before",
        "relationship_negation_window_words", "relationship_negation_note"}
    assert {k for k in b["queue"] if a["queue"].get(k) != b["queue"][k]} == {"d3_parking_unconditional", "ruling",
                                                                              "d3_note"}
    # Thresholds, FX and the language FAIL threshold are untouched.
    for k in ("floor", "target_min", "target_max", "fx_max_age_days", "language_confidence_threshold",
              "bengaluru_hybrid_max_office_days", "review_daily_cap", "review_carry_days"):
        assert a["parameters"][k] == b["parameters"][k], k


def test_025_unknown_rules_tagged_and_flags_registered():
    doc = load_policy_version(V25).doc
    for table in doc["rules"].values():
        for rule in table:
            if rule["verdict"] == "UNKNOWN":
                assert rule.get("evidence_gap") in ("missing", "known"), rule["rule_id"]
    assert set(load_policy_version(V25).info_flags) == set(load_policy_version(V24).info_flags)  # OR-81


def _round3_gap_sentences():
    doc = json.loads(r3.CORPUS.read_text(encoding="utf-8"))
    ids = {"R3-003", "R3-005", "R3-010", "R3-012", "R3-014", "R3-015", "R3-018", "R3-020", "R3-033", "R3-034",
           "R3-059", "R3-078", "R3-087"}
    texts = [c["posting"].get(f) or "" for c in doc["cases"] if c["id"] in ids
             for f in ("jd_text", "compensation_text", "location_text")]
    texts += [o["posting"].get("jd_text") or "" for s in doc["sequences"] if s["id"] == "S-02" for o in s["observations"]]
    sentences = {s.strip().lower() for t in texts for s in re.split(r"(?<=[.!?;])\s+|\n", t) if len(s.strip()) >= 30}
    return sentences


def test_no_round3_special_casing():
    """P8 §20: no Round-3 case id and no Round-3 sentence in production code, the 0.2.5 artifact or its golden cases."""
    sources = [p.read_text(encoding="utf-8") for p in (ROOT / "evaluation").glob("*.py")]
    sources.append((ROOT / "policy" / "jobops-policy-0.2.5.json").read_text(encoding="utf-8"))
    sources.append(FIXTURE.read_text(encoding="utf-8"))
    for text in sources:
        assert not re.search(r"\bR3-\d{3}\b", text)
    blob = "\n".join(t.lower() for t in sources)
    leaked = [s for s in _round3_gap_sentences() if s in blob]
    assert leaked == []


def test_oi053_open_and_recorded_append_only():
    rulings = (ROOT / "OWNER_RULINGS_LOG.md").read_text(encoding="utf-8")
    section = rulings.split("# Addendum I", 1)[1]
    oi = section.split("## OI-053", 1)[1].split("\n## ", 1)[0]
    assert ("Does an India-resident preference/priority statement count as explicit India eligibility for "
            "geography purposes?") in oi
    assert "OPEN" in oi
    ruling = oi.split("### RULING:", 1)[1].split("\n###", 1)[0].split("\n---", 1)[0]
    assert ruling.strip() == "", "RULING must stay empty until the owner rules"
    items = (ROOT / "docs" / "architecture" / "JOBOPS_V2_OPEN_ITEMS.md").read_text(encoding="utf-8")
    assert "| OI-053 |" in items and "| OI-054 |" in items and "| OI-055 |" in items
