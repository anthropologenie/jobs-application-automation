"""
P10 tests: REVIEW presentation tiers, tiered cap fill, digest metrics, and parity with P9.

Fixtures: tests/fixtures/p9/ (P9 synthetic, unchanged) and tests/fixtures/p10/tiers_export.json (independently
authored by make_tiers_export.py). Every run writes to a pytest tmp_path; sockets are refused by the autouse
no_network fixture, and the live data/jobs-tracker.db is never opened.

Parity: tests/fixtures/p10/p9_engine_reference.json is the engine state (verdicts, flags, lanes, relevance,
experience, newness, queue / carry / OR-88 state) produced by the unmodified P9 code over the four P9 fixture days.
P10 must reproduce it exactly: tiers are presentation only.
"""

import copy
import csv
import json
import math
import re
import sys
from pathlib import Path

import pytest

import jobops.tiers as tiers
from jobops.cli import main
from p10_engine_snapshot import DAYS, REFERENCE, engine_snapshot, four_day_snapshots
from v02_support import no_network  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
P10 = Path(__file__).resolve().parent / "fixtures" / "p10"
TIERS_EXPORT = P10 / "tiers_export.json"
DAY = DAYS[0]
TIER_HEADINGS = ["REVIEW — T1 Nearly Ready", "REVIEW — T2 Stretch Experience Only",
                 "REVIEW — T3 Location / Work Mode Unclear", "REVIEW — T4 Other"]


def run(inp, out, day, *extra):
    return main(["source", "--input", str(inp), "--policy", "0.2.6", "--out", str(out), "--date", day, *extra])


def metrics_of(out, day=DAY):
    return json.loads((Path(out) / day / "metrics.json").read_text(encoding="utf-8"))


def digest_of(out, day=DAY):
    return (Path(out) / day / "digest.md").read_text(encoding="utf-8")


def section(text, title):
    if f"## {title}" not in text:
        return ""
    return text.split(f"## {title}", 1)[1].split("\n## ", 1)[0]


def card_ids(text):
    return re.findall(r"^### .+?  `(req_\d+)`", text, flags=re.M)


def overflow_lines(text):
    return re.findall(r"^- `(req_\d+)` .+? \((T\d);", section(text, "REVIEW — Overflow"), flags=re.M)


def shown_tiers(text):
    """(job_id, tier) of shown REVIEW cards in digest order."""
    out = []
    for heading in TIER_HEADINGS:
        body = section(text, heading)
        for jid, tier in re.findall(r"`(req_\d+)`\n(?:.*\n){3}- \*\*Tier:\*\* (T\d)", body):
            out.append((jid, tier))
    return out


# ---------------------------------------------------------------- synthetic views (unit level)

DIMS = ("geography", "compensation", "employment_type", "employer_type", "language", "employment_relationship")


def view(job_id="req_0000001", relevance="STRONG", newness="NEW", experience="REASONABLE", jd="JD_COMPLETE",
         identity=False, review_flags=(), **dims):
    """A job view as jobops.sourcing.job_view builds it: every dimension PASS unless overridden."""
    d = {k: {"verdict": "PASS", "rule_id": "X", "flags": [], "note": "", "quotes": []} for k in DIMS}
    d["compensation"]["flags"] = ["IN_TARGET"]
    for k, (verdict, flags) in dims.items():
        d[k] = {"verdict": verdict, "rule_id": "X", "flags": list(flags), "note": "", "quotes": []}
    rf = set(review_flags)
    for k in DIMS:
        rf |= {f for f in d[k]["flags"] if f not in ("IN_TARGET", "ABOVE_TARGET", "CTC_BASIS_UNVERIFIED")}
    if identity:
        rf.add("IDENTITY_UNCERTAIN")
    if experience == "STRETCH":
        rf.add("EXPERIENCE_STRETCH")
    return {"job_id": job_id, "relevance": relevance, "newness": newness, "experience": experience,
            "jd_status": jd, "identity_uncertain": identity, "review_flags": sorted(rf), "dims": d}


PAY_NOT_STATED = ("UNKNOWN", ["COMP_UNDISCLOSED"])
EMPLOYER_UNCLASSIFIED = ("UNKNOWN", ["EMPLOYER_UNCLASSIFIED"])

TIER_CASES = [
    # T1 boundary
    ("t1_pay_not_stated", view(compensation=PAY_NOT_STATED), "T1"),
    ("t1_employer_unclassified", view(employer_type=EMPLOYER_UNCLASSIFIED), "T1"),
    ("t1_both", view(compensation=PAY_NOT_STATED, employer_type=EMPLOYER_UNCLASSIFIED), "T1"),
    ("t1_unknown_fit_experience", view(experience="UNKNOWN_FIT", compensation=PAY_NOT_STATED), "T1"),
    # arbitrary UNKNOWNs never T1
    ("language_unknown", view(language=("UNKNOWN", ["LANGUAGE_UNCERTAIN"])), "T4"),
    ("relationship_unknown", view(employment_relationship=("UNKNOWN", ["EOR"])), "T4"),
    ("employment_unknown", view(employment_type=("UNKNOWN", ["EMPLOYMENT_UNSTATED"])), "T4"),
    ("employer_staffing", view(employer_type=("UNKNOWN", ["STAFFING"])), "T4"),
    ("pay_non_numeric", view(compensation=("UNKNOWN", ["COMP_NON_NUMERIC"])), "T4"),
    ("pay_below_target_pass", view(compensation=("PASS", ["BELOW_TARGET"])), "T4"),
    ("identity_conflict", view(compensation=PAY_NOT_STATED, identity=True), "T4"),
    ("source_conflict", view(compensation=PAY_NOT_STATED, review_flags=["SOURCE_CONFLICT"]), "T4"),
    ("jd_missing", view(compensation=PAY_NOT_STATED, jd="JD_MISSING"), "T4"),
    ("jd_truncated", view(jd="JD_TRUNCATED"), "T4"),
    # T2 boundary
    ("t2_stretch_only", view(experience="STRETCH"), "T2"),
    ("t2_stretch_pay_employer", view(experience="STRETCH", compensation=PAY_NOT_STATED,
                                     employer_type=EMPLOYER_UNCLASSIFIED), "T2"),
    ("stretch_identity", view(experience="STRETCH", identity=True), "T4"),
    ("stretch_jd_truncated", view(experience="STRETCH", jd="JD_TRUNCATED"), "T4"),
    ("stretch_geography_unknown", view(experience="STRETCH", geography=("UNKNOWN", ["HYBRID_DAYS_UNSPECIFIED"])), "T3"),
    # T3 boundary
    ("geography_unknown", view(geography=("UNKNOWN", ["WORK_ARRANGEMENT_ABSENT"])), "T3"),
    ("work_mode_conflict", view(geography=("UNKNOWN", ["WORK_MODE_CONFLICT"])), "T3"),
    ("geography_unknown_and_jd_missing", view(geography=("UNKNOWN", ["GEO_REGION_AMBIGUOUS"]), jd="JD_MISSING"), "T3"),
    ("geography_unknown_and_language", view(geography=("UNKNOWN", ["CITY_HUB_LISTED"]),
                                            language=("UNKNOWN", ["LANGUAGE_UNCERTAIN"])), "T3"),
    # T4 boundary
    ("t4_employment_and_pay", view(employment_type=("UNKNOWN", ["EMPLOYMENT_UNSTATED"]), compensation=PAY_NOT_STATED), "T4"),
]


@pytest.mark.parametrize("name,v,expected", TIER_CASES, ids=[c[0] for c in TIER_CASES])
def test_tier_boundaries(name, v, expected):
    assert tiers.tier_of(v) == expected


def test_tier_does_not_mutate_the_view():
    v = view(compensation=PAY_NOT_STATED, employer_type=EMPLOYER_UNCLASSIFIED)
    before = copy.deepcopy(v)
    tiers.tier_of(v)
    tiers.blockers(v)
    assert v == before


@pytest.mark.parametrize("name,v,expected", [
    ("t1", view(compensation=PAY_NOT_STATED, employer_type=EMPLOYER_UNCLASSIFIED),
     ["pay not stated", "employer unclassified"]),
    ("t2", view(experience="STRETCH"), ["experience stretch"]),
    ("work_mode", view(geography=("UNKNOWN", ["WORK_MODE_CONFLICT"])), ["work mode conflict"]),
    ("geo", view(geography=("UNKNOWN", ["HYBRID_DAYS_UNSPECIFIED"])), ["geography unclear (hybrid days unspecified)"]),
    ("lang", view(language=("UNKNOWN", ["LANGUAGE_UNCERTAIN"])), ["language unknown"]),
    ("rel", view(employment_relationship=("UNKNOWN", ["EOR"])), ["employer of record"]),
    ("jd_missing", view(jd="JD_MISSING"), ["JD missing"]),
    ("jd_truncated", view(jd="JD_TRUNCATED"), ["JD truncated"]),
    ("identity", view(identity=True), ["identity uncertain"]),
    ("clean", view(), []),
], ids=lambda x: x if isinstance(x, str) else None)
def test_blockers_are_derived_from_stored_flags_only(name, v, expected):
    assert tiers.blockers(v) == expected


# ---------------------------------------------------------------- ordering (unit level)

def ordered(*views):
    for v in views:
        tiers.annotate(v)
    units = [{"unit_id": v["job_id"], "engine": "surfaced", "carry_days": None, "members": [v]} for v in views]
    return [u["members"][0]["job_id"] for u in tiers.order_units(units)]


def check_tier_beats_tier():
    # Each lower tier carries the strongest ordering attributes, so only the tier can put it first.
    t1 = view("req_0000009", relevance="MODERATE", newness="SEEN_BEFORE", compensation=PAY_NOT_STATED)
    t2 = view("req_0000008", relevance="MODERATE", newness="UPDATED", experience="STRETCH")
    t3 = view("req_0000007", geography=("UNKNOWN", ["WORK_ARRANGEMENT_ABSENT"]))
    t4 = view("req_0000001", language=("UNKNOWN", ["LANGUAGE_UNCERTAIN"]))
    assert ordered(t4, t3, t2, t1) == ["req_0000009", "req_0000008", "req_0000007", "req_0000001"]


def check_strong_beats_moderate():
    assert ordered(view("req_0000001", relevance="MODERATE", compensation=PAY_NOT_STATED),
                   view("req_0000002", relevance="STRONG", newness="SEEN_BEFORE", compensation=PAY_NOT_STATED)
                   ) == ["req_0000002", "req_0000001"]


def check_newness_order():
    assert ordered(view("req_0000001", newness="SEEN_BEFORE", compensation=PAY_NOT_STATED),
                   view("req_0000002", newness="UPDATED", compensation=PAY_NOT_STATED),
                   view("req_0000003", newness="NEW", compensation=PAY_NOT_STATED)
                   ) == ["req_0000003", "req_0000002", "req_0000001"]


def check_job_id_tiebreak():
    assert ordered(view("req_0000005", compensation=PAY_NOT_STATED), view("req_0000004", compensation=PAY_NOT_STATED)
                   ) == ["req_0000004", "req_0000005"]


def check_pay_tiebreak():
    # Otherwise equivalent T1 jobs: stated in-target / above-target pay first, pay not stated after.
    in_target = view("req_0000009", employer_type=EMPLOYER_UNCLASSIFIED)
    above = view("req_0000008", employer_type=EMPLOYER_UNCLASSIFIED, compensation=("PASS", ["ABOVE_TARGET"]))
    not_stated = view("req_0000001", employer_type=EMPLOYER_UNCLASSIFIED, compensation=PAY_NOT_STATED)
    assert ordered(not_stated, in_target, above) == ["req_0000008", "req_0000009", "req_0000001"]


ORDERING_CHECKS = [check_tier_beats_tier, check_strong_beats_moderate, check_newness_order, check_job_id_tiebreak,
                   check_pay_tiebreak]


@pytest.mark.parametrize("check", ORDERING_CHECKS, ids=lambda c: c.__name__)
def test_within_and_across_tier_ordering(check):
    check()


def test_pay_tiebreak_never_lifts_below_target_over_not_stated():
    below = view("req_0000001", compensation=("PASS", ["BELOW_TARGET"]))
    not_stated = view("req_0000002", compensation=PAY_NOT_STATED)
    assert tiers.pay_rank(below) == tiers.pay_rank(not_stated) == 1
    # Even with equal tier and attributes, a disclosed below-target salary does not rank above undisclosed pay.
    below_t1 = dict(view("req_0000001", compensation=("PASS", ["BELOW_TARGET"])), tier="T1")
    not_stated_t1 = dict(view("req_0000002", compensation=PAY_NOT_STATED), tier="T1")
    assert tiers.order_key(below_t1)[:4] == tiers.order_key(not_stated_t1)[:4]


def test_pay_tiebreak_does_not_outrank_newness():
    assert ordered(view("req_0000001", newness="UPDATED", employer_type=EMPLOYER_UNCLASSIFIED),
                   view("req_0000002", newness="NEW", compensation=PAY_NOT_STATED)
                   ) == ["req_0000002", "req_0000001"]


def test_group_unit_ranks_by_its_best_member():
    a = tiers.annotate(view("req_0000003", identity=True))
    b = tiers.annotate(view("req_0000004", identity=True))
    c = tiers.annotate(view("req_0000009", compensation=PAY_NOT_STATED))
    units = tiers.order_units([{"unit_id": "grp_req_0000003", "engine": "surfaced", "carry_days": None,
                                "members": [b, a]},
                               {"unit_id": "req_0000009", "engine": "carried", "carry_days": 1, "members": [c]}])
    assert [u["tier"] for u in units] == ["T1", "T4"]
    assert [m["job_id"] for m in units[1]["members"]] == ["req_0000003", "req_0000004"]


# ---------------------------------------------------------------- tiers fixture: integration

@pytest.fixture(scope="module")
def tiers_run(tmp_path_factory):
    out = tmp_path_factory.mktemp("p10tiers")
    assert run(TIERS_EXPORT, out, DAY) == 0
    return out


def test_tiers_fixture_produces_every_tier(tiers_run):
    m = metrics_of(tiers_run)
    assert m["review_tiers"] == {"T1": 7, "T2": 2, "T3": 4, "T4": 3}
    assert sum(m["review_tiers"].values()) == m["REVIEW"]
    assert m["SHORTLIST"] == 2 and m["EXCLUDED"] == 2 and m["PARKED"] == 1


def test_ready_ish_metric_and_estimate(tiers_run):
    m = metrics_of(tiers_run)
    ready = m["SHORTLIST"] + m["review_tiers"]["T1"] + m["review_tiers"]["T2"]
    assert m["READY_ISH"] == ready == 11
    rate = ready / m["jobs_in"]
    assert m["illustrative_source_jobs_for_25_ready_ish"] == math.ceil(25 / rate)
    assert m["illustrative_source_jobs_for_30_ready_ish"] == math.ceil(30 / rate)
    assert m["ready_ish_below_25"] is True and m["ready_ish_gap_to_25"] == 14
    # The P9 SHORTLIST + REVIEW estimate is gone; the count itself is kept and labelled.
    assert "estimated_source_jobs_for_25" not in m and "observed_conversion_rate" not in m
    assert m["shortlist_plus_review"] == m["SHORTLIST"] + m["REVIEW"]
    text = digest_of(tiers_run)
    assert "Illustrative one-day estimate — not an application-supply forecast." in text
    assert "READY-ISH is below 25." in text
    assert f"The largest blocker among T3 / T4 jobs is **{m['largest_blocker_outside_ready_ish']['blocker']}**" in text
    assert "More source volume alone does not remove this blocker." in text
    for hit in re.finditer(r"ready to apply", text, flags=re.I):
        assert text[hit.start() - 5:hit.start()] == 'not "', "READY-ISH is never described as ready to apply"


def test_ready_ish_zero_gives_no_estimate(tmp_path):
    recs = json.loads(TIERS_EXPORT.read_text(encoding="utf-8"))
    keep = [r for r in recs if r["id"] in ("p10-015", "p10-016", "p10-018")]  # T4, T4, EXCLUDED
    inp = tmp_path / "zero.json"
    inp.write_text(json.dumps(keep, ensure_ascii=False), encoding="utf-8")
    assert run(inp, tmp_path / "o", DAY) == 0
    m = metrics_of(tmp_path / "o")
    assert m["READY_ISH"] == 0 and m["illustrative_source_jobs_for_25_ready_ish"] is None
    assert "READY-ISH is 0 today" in digest_of(tmp_path / "o")


def test_digest_structure(tiers_run):
    text = digest_of(tiers_run)
    order = ["| Tier | Count |", "## Metrics", "## SHORTLIST"] + [f"## {h}" for h in TIER_HEADINGS] + [
        "## REVIEW — Overflow", "## PARKED", "## EXCLUDED (", "## EXCLUDED by Dimension"]
    positions = [text.index(h) for h in order]
    assert positions == sorted(positions)
    assert "Gate E: pending" in text and "Gate E: PASS" not in text
    assert "Diagnostic only. No policy change is implied." in text
    m = metrics_of(tiers_run)
    for t, label in tiers.TIER_LABEL.items():
        assert f"| {label} | {m['review_tiers'][t]} |" in text


def test_every_review_card_has_tier_and_blockers(tmp_path):
    assert run(TIERS_EXPORT, tmp_path, DAY, "--review-cap", "40") == 0
    text = digest_of(tmp_path)
    m = metrics_of(tmp_path)
    for heading in TIER_HEADINGS + ["REVIEW — held from SHORTLIST (incomplete JD; outside the daily cap)"]:
        body = section(text, heading)
        cards = body.split("\n### ")[1:]
        for c in cards:
            assert "- **Tier:** " in c and "- **Blockers:** " in c, c[:80]
    assert len(shown_tiers(text)) == m["REVIEW"]
    for jid, tier in shown_tiers(text):
        body = text.split(f"`{jid}`", 1)[1].split("\n### ", 1)[0]
        blockers = re.search(r"- \*\*Blockers:\*\* (.+)", body).group(1).split("; ")
        if tier == "T1":
            assert set(blockers) <= {"employer unclassified", "pay not stated"}, (jid, blockers)
        if tier == "T2":
            assert "experience stretch" in blockers and set(blockers) <= {
                "employer unclassified", "pay not stated", "experience stretch"}, (jid, blockers)
        if tier == "T3":
            assert any(b.startswith("geography unclear") or b == "work mode conflict" for b in blockers)


def test_pay_and_mode_not_stated_are_display_only(tmp_path):
    assert run(TIERS_EXPORT, tmp_path, DAY, "--review-cap", "40") == 0
    text = digest_of(tmp_path)
    pikestaff = text.split("`req_0000014`", 1)[1].split("\n### ", 1)[0]  # no work mode in the export
    assert "**Mode:** not stated" in text.split("`req_0000014`", 1)[0].rsplit("### ", 1)[1] + pikestaff
    hollowmere = text.split("`req_0000003`", 1)[1].split("\n### ", 1)[0]  # no salary in the export
    assert "- **Pay:** not stated" in hollowmere
    assert "compensation UNKNOWN" in hollowmere  # the engine's verdict is shown as is
    snap = engine_snapshot(tmp_path)
    assert snap["req_0000003"]["dims"]["compensation"][0] == "UNKNOWN"
    assert snap["req_0000014"]["dims"]["geography"][0] == "UNKNOWN"


def test_excluded_by_dimension_matches_excluded_csv(tiers_run):
    rows = list(csv.DictReader(open(Path(tiers_run) / DAY / "excluded.csv", encoding="utf-8")))
    m = metrics_of(tiers_run)
    for dim in ("geography", "compensation", "employment", "employer", "language", "relationship"):
        assert m["excluded_by_dimension"][dim] == sum(1 for r in rows if r["failing_dimension"] == dim)
    assert m["excluded_by_dimension"]["geography"] == 1 and m["excluded_by_dimension"]["employment"] == 1
    assert sum(m["excluded_by_rule"].values()) == len(rows)
    text = section(digest_of(tiers_run), "EXCLUDED by Dimension")
    assert "| geography | 1 |" in text and "| employment | 1 |" in text


# ---------------------------------------------------------------- cap

def check_cap_fill(out, cap):
    text, m = digest_of(out), metrics_of(out)
    shown = shown_tiers(text)
    over = overflow_lines(text)
    order = [t for _, t in shown] + [t for _, t in over]
    assert order == sorted(order), "shown slots fill T1 -> T2 -> T3 -> T4, overflow follows"
    if over:
        assert max(t for _, t in shown) <= min(t for _, t in over)
    assert m["review_queue_tiers"]["shown_units"] == min(cap, m["review_queue_tiers"]["shown_units"]
                                                         + m["review_queue_tiers"]["overflow_units"])
    return shown, over


@pytest.mark.parametrize("cap,n_shown,n_over", [(40, 16, 0), (16, 16, 0), (10, 10, 6), (None, 10, 6), (8, 8, 8)],
                         ids=["fewer_than_cap", "exactly_cap", "more_than_cap_10", "default_cap", "more_than_cap_8"])
def test_cap_fills_by_tier_without_changing_lanes(tmp_path, cap, n_shown, n_over):
    extra = ["--review-cap", str(cap)] if cap else []
    assert run(TIERS_EXPORT, tmp_path, DAY, *extra) == 0
    shown, over = check_cap_fill(tmp_path, cap or 10)
    assert (len(shown), len(over)) == (n_shown, n_over)
    snap = engine_snapshot(tmp_path)
    assert all(snap[j]["lane"] == "REVIEW" for j, _ in shown + over), "overflow and shown stay REVIEW"
    if cap in (None, 10):
        assert [t for _, t in shown] == ["T1"] * 7 + ["T2"] * 2 + ["T3"]
        assert sorted(t for _, t in over) == ["T3"] * 3 + ["T4"] * 3


def test_cap_never_changes_engine_verdicts_or_lanes(tmp_path):
    snaps = {}
    for cap in ("3", "10", "40"):
        assert run(TIERS_EXPORT, tmp_path / cap, DAY, "--review-cap", cap) == 0
        snaps[cap] = {k: {f: v[f] for f in ("lane", "dims", "relevance", "experience", "flags", "newness")}
                      for k, v in engine_snapshot(tmp_path / cap).items()}
    assert snaps["3"] == snaps["10"] == snaps["40"]


# ---------------------------------------------------------------- P9 parity, carry, D+3

@pytest.fixture(scope="module")
def p10_four_days(tmp_path_factory):
    out = tmp_path_factory.mktemp("p10four")
    snaps = four_day_snapshots(out, run)
    return out, snaps


def test_parity_with_p9_engine_state_all_days(p10_four_days):
    """Verdicts, rule ids, flags, lanes, relevance, experience, newness and queue / carry / OR-88 state are
    identical to the unmodified P9 code, for every requisition on every one of the four P9 fixture days."""
    _, snaps = p10_four_days
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))["snapshots"]
    assert set(snaps) == set(reference) == set(DAYS)
    for day in DAYS:
        assert snaps[day].keys() == reference[day].keys(), day
        for rid in reference[day]:
            assert snaps[day][rid] == reference[day][rid], (day, rid)
    assert sum(len(s) for s in reference.values()) == 227


def test_carry_counts_and_newness_over_days_match_p9(p10_four_days):
    out, snaps = p10_four_days
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))["snapshots"]
    for day in DAYS:
        carry = {r: (s["queue_state"] or {}).get("carry_days") for r, s in snaps[day].items()}
        assert carry == {r: (s["queue_state"] or {}).get("carry_days") for r, s in reference[day].items()}
        assert {r: s["newness"] for r, s in snaps[day].items()} == {r: s["newness"] for r, s in reference[day].items()}
    # The digest reports plan_day's own carry day for carried items.
    m2 = metrics_of(out, DAYS[1])
    assert m2["queue_today"]["review_shown"] + m2["queue_today"]["review_overflow"] > 0


def test_d3_parking_unchanged_by_tiering(p10_four_days):
    out, snaps = p10_four_days
    parked_d4 = {r for r, s in snaps[DAYS[3]].items() if (s["queue_state"] or {}).get("overflow_parked_on") == DAYS[3]}
    assert parked_d4 == {"req_0000027", "req_0000028"}  # NOT_ASSESSED, carried D, D+1, D+2 (OR-88)
    assert all(snaps[DAYS[3]][r]["relevance"] != "STRONG" for r in parked_d4)
    text = digest_of(out, DAYS[3])
    assert {"req_0000027", "req_0000028"} <= set(re.findall(r"`(req_\d+)`", section(text, "PARKED")))
    queue = set(card_ids("".join(section(text, h) for h in TIER_HEADINGS))) | {j for j, _ in overflow_lines(text)}
    assert queue and not (parked_d4 & queue)
    assert metrics_of(out, DAYS[3])["queue_today"]["overflow_parked_today"] == 2


def test_two_days_carry_on_tiers_fixture(tmp_path):
    """Day 2 re-sights the same export: newness SEEN_BEFORE; engine-carried items reach carry day 2."""
    assert run(TIERS_EXPORT, tmp_path, DAYS[0]) == 0
    s1 = engine_snapshot(tmp_path)
    assert run(TIERS_EXPORT, tmp_path, DAYS[1]) == 0
    s2 = engine_snapshot(tmp_path)
    for rid, s in s2.items():
        assert s["newness"] == "SEEN_BEFORE"
        assert {k: s[k] for k in ("lane", "dims", "relevance", "experience", "flags")} == \
               {k: s1[rid][k] for k in ("lane", "dims", "relevance", "experience", "flags")}
        q1, q2 = s1[rid]["queue_state"], s["queue_state"]
        if q1 and q1["last_surfaced_day"] != DAYS[0]:
            assert q1["carry_days"] == 1
            if q2["last_surfaced_day"] != DAYS[1]:
                assert q2["carry_days"] == 2
    text = digest_of(tmp_path, DAYS[1])
    assert "engine: carried, day 2" in text or "carry day 2" in text


def test_engine_divergence_is_reported(tiers_run):
    m = metrics_of(tiers_run)
    q = m["review_queue_tiers"]
    snap = engine_snapshot(tiers_run)
    text = digest_of(tiers_run)
    shown = {j for j, _ in shown_tiers(text)}
    over = {j for j, _ in overflow_lines(text)}
    surfaced = {r for r, s in snap.items() if (s["queue_state"] or {}).get("last_surfaced_day") == DAY}
    assert q["engine_surfaced_not_shown"] == len(surfaced & over)
    assert q["engine_carried_but_shown"] == len(shown - surfaced)
    if q["engine_surfaced_not_shown"] or q["engine_carried_but_shown"]:
        assert "OI-057" in text


# ---------------------------------------------------------------- idempotence

def _outputs(out, day=DAY):
    d = Path(out) / day
    return {p.relative_to(d).as_posix(): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file()}


def test_idempotent_same_input_same_date_same_state(tmp_path):
    assert run(TIERS_EXPORT, tmp_path, DAY) == 0
    first = _outputs(tmp_path)
    assert run(TIERS_EXPORT, tmp_path, DAY) == 0
    assert _outputs(tmp_path) == first


def test_idempotent_fresh_states(tmp_path):
    for name in ("a", "b"):
        assert run(TIERS_EXPORT, tmp_path / name, DAY) == 0
    assert _outputs(tmp_path / "a") == _outputs(tmp_path / "b")


# ---------------------------------------------------------------- mutation check (P10 §35)

def _reverse_tiers(orig):
    return lambda j: (-orig(j)[0],) + orig(j)[1:]


def _drop_tier(orig):
    return lambda j: orig(j)[1:]


def _reverse_relevance(orig):
    return lambda j: (orig(j)[0], -orig(j)[1]) + orig(j)[2:]


def _drop_newness(orig):
    return lambda j: orig(j)[:2] + orig(j)[3:]


def _drop_pay(orig):
    return lambda j: orig(j)[:3] + orig(j)[4:]


MUTATIONS = {"reverse_tiers": _reverse_tiers, "drop_tier": _drop_tier, "reverse_relevance": _reverse_relevance,
             "drop_newness": _drop_newness, "drop_pay_tiebreak": _drop_pay}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_mutated_ordering_is_caught(name, monkeypatch, tmp_path):
    """Each deliberately broken order_key must make at least one ordering check fail; the patch is undone after."""
    original = tiers.order_key
    monkeypatch.setattr(tiers, "order_key", MUTATIONS[name](original))
    failures = []
    for check in ORDERING_CHECKS:
        try:
            check()
        except AssertionError:
            failures.append(check.__name__)
    if name in ("reverse_tiers", "drop_tier"):
        assert run(TIERS_EXPORT, tmp_path, DAY) == 0
        try:
            check_cap_fill(tmp_path, 10)
        except AssertionError:
            failures.append("check_cap_fill")
        assert "check_cap_fill" in failures, name
    assert failures, f"mutation {name} was not detected"
    monkeypatch.undo()
    assert tiers.order_key is original
    for check in ORDERING_CHECKS:
        check()


def test_mutated_tier_rule_is_caught(monkeypatch):
    monkeypatch.setattr(tiers, "_narrow", lambda j: True)  # every REVIEW job would pass as T1 / T2
    wrong = [n for n, v, exp in TIER_CASES if tiers.tier_of(v) != exp]
    assert {"language_unknown", "jd_missing", "identity_conflict", "geography_unknown"} <= set(wrong)


# ---------------------------------------------------------------- safety / integrity

def test_p10_run_loads_no_network_module(tmp_path):
    forbidden = {"socket", "ssl", "http", "urllib", "requests", "httpx", "aiohttp", "openai", "anthropic"}
    before = set(sys.modules)
    assert run(TIERS_EXPORT, tmp_path, DAY) == 0
    loaded = {m.split(".")[0] for m in set(sys.modules) - before}
    assert not (loaded & forbidden)


def test_companies_option_not_implemented():
    """P10 §27: company-classification input is an open item (OI-056), not a feature."""
    with pytest.raises(SystemExit):
        main(["source", "--input", str(TIERS_EXPORT), "--out", "unused", "--companies", "x.csv"])


def test_p10_fixture_is_independent_of_round3():
    text = TIERS_EXPORT.read_text(encoding="utf-8")
    assert not re.search(r"\bR3-\d{3}\b|\bS-0\d\b", text)
    import test_p8_policy_025 as p8
    assert [s for s in p8._round3_gap_sentences() if s in text.lower()] == []


def test_p10_fixture_is_regenerated_byte_identically(tmp_path, monkeypatch):
    sys.path.insert(0, str(P10))
    try:
        import make_tiers_export as gen
    finally:
        sys.path.remove(str(P10))
    monkeypatch.setattr(gen, "OUT", tmp_path / "x.json")
    gen.OUT.write_text(json.dumps(gen.RECORDS, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    assert gen.OUT.read_bytes() == TIERS_EXPORT.read_bytes()
