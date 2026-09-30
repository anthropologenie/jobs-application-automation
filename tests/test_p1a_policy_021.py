"""
P1a acceptance tests for jobops-policy@0.2.1 (pinned explicitly; independent of the default).

Covers OI-039 (CTC), OI-040 (FX age, injectable clock, digest warning), OI-044
(no-JD senior Tier 1), OI-046 (grouped identity-uncertain review), explicit
confirmations of OI-036/037/038/041/042/043/045, 0.2.0 replayability and the
policy-file hash invariants.
"""

import hashlib
import json

import pytest

from digest import render_daily
from evaluation.policy_loader import POLICY_PATHS, V01_POLICY_PATH, load_policy_version
from evaluation.queue import plan_day
from store import repository as repo
from v02_support import BASE_TEXT, EN, fresh_service, no_network, observation  # noqa: F401

V20, V21 = "jobops-policy@0.2.0", "jobops-policy@0.2.1"
P21 = load_policy_version(V21)
P20 = load_policy_version(V20)
V020_SHA = "65f74aec883d475989ea0594fac070f547c96a697bc1f7f4b46cf8e0d5dd567a"
V010_SHA = "afe05e5a31777410668180a2d50a06da7cfa21736159946273060be6bf1c051f"


def svc(policy=P21, today="2026-09-21"):
    s = fresh_service(policy)
    s.clock = lambda: today
    s.classify_company("Synthetic Product Co", "PRODUCT", "INFERRED_FROM_EVIDENCE", "machine")
    return s


def evaluate(comp_line=None, geo_line=None, policy=P21, today="2026-09-21", fx=None, **obs):
    text = BASE_TEXT
    if comp_line is not None:
        text = text.replace("Salary: ₹26 LPA fixed base.", comp_line)
    if geo_line is not None:
        text = text.replace("Location: Remote - India.", geo_line)
    s = svc(policy, today)
    for f in fx or []:
        s.add_fx_rate(*f)
    return s.ingest(observation(raw_text=text, language_detection=EN, **obs))["evaluation"]["result"]


def comp(r):
    return r["eligibility_dimensions"]["compensation"]["verdict"], sorted(
        f for f in r["flags"] if f in {"BELOW_TARGET", "CTC_BASIS_UNVERIFIED", "IN_TARGET", "ABOVE_TARGET",
                                       "COMPENSATION_REVIEW", "CTC_RANGE_STRADDLES_FLOOR", "FX_STALE",
                                       "MONTHLY_ASSUMED", "COMP_BASIS_UNSTATED", "SALARY_RANGE_STRADDLES_FLOOR"})


# --------------------------------------------------------------- invariants

def test_v020_is_byte_identical_and_both_hashes_are_recorded():
    assert hashlib.sha256(POLICY_PATHS[V20].read_bytes()).hexdigest() == V020_SHA
    doc = json.loads(POLICY_PATHS[V21].read_text(encoding="utf-8"))
    assert doc["artifact"]["v0_2_0_artifact"]["sha256"] == V020_SHA
    assert doc["artifact"]["v0_1_artifact"]["sha256"] == V010_SHA
    assert hashlib.sha256(V01_POLICY_PATH.read_bytes()).hexdigest() == V010_SHA


def test_021_keeps_thresholds_and_verdicts():
    d20 = json.loads(POLICY_PATHS[V20].read_text(encoding="utf-8"))
    d21 = json.loads(POLICY_PATHS[V21].read_text(encoding="utf-8"))
    assert d21["relevance"]["thresholds"] == d20["relevance"]["thresholds"]
    assert d21["relevance"]["title_tiers"] == d20["relevance"]["title_tiers"]
    assert len(d21["relevance"]["title_tiers"]["TIER_1"]) == 20
    assert d21["artifact"]["verdicts"] == ["PASS", "FAIL", "UNKNOWN"]
    for k in ("floor", "target_min", "target_max", "review_daily_cap", "review_carry_days", "language_confidence_threshold"):
        assert d21["parameters"][k] == d20["parameters"][k]


# ---------------------------------------------------------------- OI-039 CTC

@pytest.mark.parametrize("line,expected", [
    ("Compensation: ₹17 LPA CTC.", ("FAIL", [])),
    ("Compensation: ₹18 LPA CTC.", ("PASS", ["BELOW_TARGET", "CTC_BASIS_UNVERIFIED"])),
    ("Compensation: ₹20 LPA CTC.", ("PASS", ["BELOW_TARGET", "CTC_BASIS_UNVERIFIED"])),
    ("Compensation: ₹23 LPA CTC.", ("PASS", ["BELOW_TARGET", "CTC_BASIS_UNVERIFIED"])),
    ("Compensation: ₹24 LPA CTC.", ("PASS", ["CTC_BASIS_UNVERIFIED"])),
    ("Compensation: ₹18–22 LPA CTC.", ("PASS", ["BELOW_TARGET", "CTC_BASIS_UNVERIFIED"])),
    ("Compensation: ₹24–30 LPA CTC.", ("PASS", ["CTC_BASIS_UNVERIFIED"])),
    ("Compensation: ₹15–20 LPA CTC.", ("UNKNOWN", ["CTC_RANGE_STRADDLES_FLOOR"])),
    ("Salary: ₹24 LPA fixed base; ₹20 LPA CTC.", ("PASS", ["IN_TARGET"])),
])
def test_ctc_consistency_021(line, expected):
    assert comp(evaluate(line)) == expected


def test_ctc_never_labelled_in_target_and_never_haircut():
    r = evaluate("Compensation: ₹30 LPA CTC.")
    assert r["compensation_normalized"]["min_inr"] == 3000000 and r["compensation_normalized"]["basis"] == "CTC"
    assert "IN_TARGET" not in r["flags"] and "ABOVE_TARGET" not in r["flags"]


def test_020_replay_keeps_its_own_ctc_behaviour():
    assert comp(evaluate("Compensation: ₹20 LPA CTC.", policy=P20)) == ("PASS", ["CTC_BASIS_UNVERIFIED"])


# ------------------------------------------------------------------ OI-040 FX

USD = "Base salary: USD 150,000–180,000 per year."
WORLD = "Location: Remote (worldwide) - we hire anywhere."


def fx(date):
    return [("USD", 80.0, date, "SYNTHETIC_FIXTURE")]


@pytest.mark.parametrize("snapshot,age,verdict,stale", [
    ("2026-09-08", 13, "PASS", False), ("2026-09-07", 14, "PASS", False),
    ("2026-09-06", 15, "UNKNOWN", True), ("2026-08-01", 51, "UNKNOWN", True)])
def test_fx_age_against_injected_evaluation_date(snapshot, age, verdict, stale):
    r = evaluate(USD, WORLD, fx=fx(snapshot), today="2026-09-21")
    assert r["eligibility_dimensions"]["compensation"]["verdict"] == verdict
    assert ("FX_STALE" in r["flags"]) == stale
    assert r["eligibility_overall"] != "FAIL"


def test_fx_age_follows_the_clock_not_the_observation_date():
    s = svc(P21, "2026-09-21")
    s.add_fx_rate("USD", 80.0, "2026-09-10", "SYNTHETIC_FIXTURE")
    text = BASE_TEXT.replace("Salary: ₹26 LPA fixed base.", USD).replace("Location: Remote - India.", WORLD)
    rid = s.ingest(observation(raw_text=text, language_detection=EN))["requisition_id"]
    assert "FX_STALE" not in s.current_evaluation(rid)["result"]["flags"]
    s.clock = lambda: "2026-09-30"                                   # 20 days later
    later = s.current_evaluation(rid)["result"]
    assert "FX_STALE" in later["flags"] and later["lane"] == "REVIEW"


def test_inr_is_unaffected_by_stale_fx():
    r = evaluate(None, None, fx=fx("2026-01-01"), today="2026-09-21")
    assert comp(r) == ("PASS", ["IN_TARGET"])


def test_020_has_no_fx_age_limit():
    r = evaluate(USD, WORLD, policy=P20, fx=fx("2026-09-06"), today="2026-09-21")
    assert r["eligibility_dimensions"]["compensation"]["verdict"] == "PASS"


@pytest.mark.parametrize("snapshot,warned", [("2026-09-14", False), ("2026-09-13", True), ("2026-09-07", True), ("2026-09-06", False)])
def test_digest_fx_warning_after_7_days_while_usable(snapshot, warned):
    s = svc(P21, "2026-09-21")
    s.add_fx_rate("USD", 80.0, snapshot, "SYNTHETIC_FIXTURE")
    text = BASE_TEXT.replace("Salary: ₹26 LPA fixed base.", USD).replace("Location: Remote - India.", WORLD)
    s.ingest(observation(raw_text=text, language_detection=EN))
    plan = plan_day(s, "2026-09-21")
    assert bool(plan["fx_warnings"]) == warned
    assert ("FX freshness warning" in render_daily(plan)) == warned


# ------------------------------------------------------------- OI-044 no JD

@pytest.mark.parametrize("title", ["Staff AI Engineer", "Principal AI Engineer", "AI Engineer - Architect"])
def test_no_jd_senior_tier1_goes_to_review(title):
    s = svc()
    r = s.ingest(observation(source="board:x", source_kind="JOB_BOARD", completeness="SEARCH_ONLY", raw_title=title,
                             raw_location="Bengaluru, Karnataka, India", source_external_id=title))["evaluation"]["result"]
    assert r["relevance"]["relevance_label"] == "NOT_ASSESSED"
    assert r["relevance"]["title_signal"] == "TIER_1"
    assert r["lane"] == "REVIEW" and r["lane_rule"] == "LANE-R03"


# ------------------------------------------------------ OI-046 grouped review

def _uncertain_pair(s):
    a = s.ingest(observation(source_url="https://boards.greenhouse.io/g/jobs/1", raw_text=BASE_TEXT, language_detection=EN))
    b = s.ingest(observation(source="linkedin-search", source_kind="JOB_BOARD", source_url="https://www.linkedin.com/jobs/view/42",
                             source_external_id="42", raw_text=BASE_TEXT, language_detection=EN))
    return a["requisition_id"], b["requisition_id"]


def _review_item(s, n):
    text = BASE_TEXT.replace("Salary: ₹26 LPA fixed base.", "Salary: ₹20 LPA fixed base.")
    return s.ingest(observation(source_url=f"https://boards.greenhouse.io/q/jobs/{100 + n}", raw_title=f"AI Engineer {n}",
                                raw_text=text, language_detection=EN, observed_at="2026-09-19T06:00:00+00:00"))["requisition_id"]


def test_identity_uncertain_pair_is_one_group_one_slot_members_kept():
    s = svc()
    a, b = _uncertain_pair(s)
    others = [_review_item(s, n) for n in range(10)]
    plan = plan_day(s, "2026-09-21")
    units = plan["review_today"] + plan["review_carried"]
    groups = [u for u in units if u.get("group_id")]
    assert len(groups) == 1
    g = groups[0]
    assert g["member_requisition_ids"] == sorted([a, b]) and len(g["members"]) == 2
    assert len(plan["review_today"]) == 10                         # cap counts units, not requisitions
    assert len(units) == 11                                        # 10 singles + 1 group
    listed = {m for u in units for m in u["member_requisition_ids"]}
    assert {a, b} | set(others) == listed                          # nobody dropped
    # records are untouched: two requisitions, two evaluations, both flagged
    for rid in (a, b):
        ev = s.current_evaluation(rid)
        assert "IDENTITY_UNCERTAIN" in ev["result"]["flags"] and ev["queue_lane"] == "REVIEW"
        assert repo.get_requisition(s.conn, rid)["duplicate_of"] is None
        assert len(repo.observations_for(s.conn, [rid])) == 1
    assert s.current_evaluation(a)["evaluation_id"] != s.current_evaluation(b)["evaluation_id"]


def test_group_ordering_uses_best_member_and_is_deterministic():
    s = svc()
    a, b = _uncertain_pair(s)                                      # STRONG, IN_TARGET, REMOTE, NEW
    plan = plan_day(s, "2026-09-21")
    assert plan["review_today"][0]["group_id"] == "grp_" + min(a, b)
    assert plan_day(s, "2026-09-21")["review_today"][0]["member_requisition_ids"] == sorted([a, b])
    assert "group:" in render_daily(plan)


def test_020_does_not_group():
    s = svc(P20)
    a, b = _uncertain_pair(s)
    units = plan_day(s, "2026-09-21")["review_today"]
    assert sorted(u["requisition_id"] for u in units) == sorted([a, b])
    assert all(u["group_id"] is None for u in units)


# ------------------------------------------ explicit confirmations OI-036..045

def test_oi036_exact_18l_is_below_target():
    assert comp(evaluate("Salary: ₹18 LPA fixed base.")) == ("PASS", ["BELOW_TARGET"])


def test_oi037_25_32_is_in_target():
    assert comp(evaluate("Salary: ₹25–32 LPA fixed base.")) == ("PASS", ["IN_TARGET"])


def test_oi038_monthly_assumed_is_informational():
    r = evaluate("Salary: ₹2,00,000 per month fixed base.")
    assert comp(r) == ("PASS", ["IN_TARGET", "MONTHLY_ASSUMED"]) and r["lane"] == "SHORTLIST"


@pytest.mark.parametrize("geo", ["Location: This role is fully remote.", "Location: London. This role is remote."])
def test_oi041_remote_without_india_evidence_is_unknown(geo):
    r = evaluate(None, geo)
    assert r["eligibility_dimensions"]["geography"]["verdict"] == "UNKNOWN" and "GEO_REGION_AMBIGUOUS" in r["flags"]


def test_oi042_unspecified_basis_uses_salary_rules():
    r = evaluate("Salary: ₹26 LPA.")
    assert comp(r) == ("PASS", ["COMP_BASIS_UNSTATED", "IN_TARGET"]) and r["lane"] == "SHORTLIST"
    assert "COMP_BASIS_UNSTATED" in P21.info_flags


@pytest.mark.parametrize("years", ["0–2", "1–2", "2–3"])
def test_oi043_at_or_below_three_is_direct(years):
    s = svc()
    text = BASE_TEXT.replace("Experience: 3 years building AI applications.", f"Experience: {years} years.")
    res = s.ingest(observation(raw_text=text, language_detection=EN))["evaluation"]["result"]
    assert res["relevance"]["experience_signal"] == "DIRECT"


@pytest.mark.parametrize("line,verdict", [("German required.", "FAIL"), ("German mandatory.", "FAIL"),
                                          ("Knowledge of German.", "UNKNOWN"), ("German-speaking team.", "UNKNOWN"),
                                          ("German is a plus.", "PASS")])
def test_oi045_requirement_confidence(line, verdict):
    s = svc()
    text = BASE_TEXT.replace("Working language: English.", line)
    r = s.ingest(observation(raw_text=text, language_detection=EN))["evaluation"]["result"]
    assert r["eligibility_dimensions"]["language"]["verdict"] == verdict


@pytest.mark.parametrize("line", ["Salary: 24,00,000 per annum.", "Salary: 24 LPA.", "Salary: ₹24L.", "Salary: ₹24 LPA."])
def test_indian_salary_formats(line):
    assert evaluate(line)["eligibility_dimensions"]["compensation"]["verdict"] == "PASS"


def test_years_is_not_a_currency_marker():
    r = evaluate("Salary: competitive.", None)
    assert r["eligibility_dimensions"]["compensation"]["verdict"] == "UNKNOWN"
    assert "COMP_NON_NUMERIC" in r["flags"]


def test_work_authorization_in_posting_country_021():
    geo = "Location: Toronto, Canada. This role is remote. You must be legally authorized to work in the country where this job is posted."
    assert evaluate(None, geo)["eligibility_dimensions"]["geography"]["verdict"] == "FAIL"
    assert evaluate(None, geo, policy=P20)["eligibility_dimensions"]["geography"]["verdict"] == "UNKNOWN"
    india = "Location: Bengaluru, Karnataka, India. This role is remote. You must be legally authorized to work in the country where this job is posted."
    assert evaluate(None, india)["eligibility_dimensions"]["geography"]["verdict"] == "PASS"
