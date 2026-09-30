"""Lanes and daily REVIEW capacity: cap 10, deterministic ordering, 3-day carry, STRONG exemption."""

from evaluation.queue import order_key, plan_day
from digest import render_daily, render_parked
from v02_support import BASE_TEXT, EN, fresh_service, no_network, observation  # noqa: F401

MODERATE_JD = "Integrate LLM APIs into our product and write prompt templates for summarization features."


def _review_posting(svc, n, *, strong=True, remote=True, at="2026-09-20T06:00:00+00:00"):
    text = BASE_TEXT.replace("Salary: ₹26 LPA fixed base.", "Salary: ₹20 LPA fixed base.")  # BELOW_TARGET -> REVIEW
    if not remote:
        text = text.replace("Location: Remote - India.", "Location: Bengaluru, hybrid - 2 days per week in office.")
    if not strong:
        text = text.replace(text.split("\n")[-1], MODERATE_JD)
    return svc.ingest(observation(source_url=f"https://boards.greenhouse.io/q/jobs/{1000 + n}", raw_text=text,
                                  raw_title=f"AI Engineer {n}",
                                  language_detection=EN, observed_at=at))["requisition_id"]


def _svc():
    svc = fresh_service()
    svc.classify_company("Synthetic Product Co", "PRODUCT", "INFERRED_FROM_EVIDENCE", "machine")
    return svc


def test_review_cap_is_ten_and_shortlist_is_uncapped():
    svc = _svc()
    for i in range(12):
        svc.ingest(observation(source_url=f"https://boards.greenhouse.io/q/jobs/{i}", raw_text=BASE_TEXT,
                               raw_title=f"AI Engineer {i}", language_detection=EN))
    for i in range(14):
        _review_posting(svc, 100 + i)
    plan = plan_day(svc, "2026-09-21")
    assert len(plan["lanes"]["SHORTLIST"]) == 12
    assert len(plan["review_today"]) == 10
    assert len(plan["review_carried"]) == 4


def test_ordering_remote_before_bengaluru_hybrid_and_deterministic():
    svc = _svc()
    hybrid = _review_posting(svc, 1, remote=False)
    remote = _review_posting(svc, 2, remote=True)
    plan = plan_day(svc, "2026-09-21")
    ids = [it["requisition_id"] for it in plan["review_today"]]
    assert ids.index(remote) < ids.index(hybrid)
    assert [it["requisition_id"] for it in plan_day(svc, "2026-09-21")["review_today"]] == ids


def test_strong_before_moderate():
    svc = _svc()
    moderate = _review_posting(svc, 1, strong=False)
    strong = _review_posting(svc, 2, strong=True)
    ids = [it["requisition_id"] for it in plan_day(svc, "2026-09-21")["review_today"]]
    assert ids.index(strong) < ids.index(moderate)


def test_overflow_carries_three_days_then_parks_but_strong_is_exempt():
    svc = _svc()
    for i in range(10):
        _review_posting(svc, i, strong=True, at="2026-09-19T06:00:00+00:00")  # older: surfaced first
    moderate = _review_posting(svc, 50, strong=False, at="2026-09-20T06:00:00+00:00")
    strong_late = _review_posting(svc, 51, strong=True, at="2026-09-20T07:00:00+00:00")
    days = ["2026-09-21", "2026-09-22", "2026-09-23", "2026-09-24"]
    plans = [plan_day(svc, d) for d in days]
    # moderate never makes the top 10 (10 older STRONG items + strong_late outrank it)
    assert all(moderate not in [it["requisition_id"] for it in p["review_today"]] for p in plans)
    carried_days = [next((it["carry_days"] for it in p["review_carried"] if it["requisition_id"] == moderate), None) for p in plans[:3]]
    assert carried_days == [1, 2, 3]
    assert moderate in [it["requisition_id"] for it in plans[3]["overflow_parked_today"]]
    assert moderate in [it["requisition_id"] for it in plan_day(svc, "2026-09-25")["lanes"]["PARKED"]]
    # the STRONG overflow item is never parked by overflow
    for p in plans:
        assert strong_late not in [it["requisition_id"] for it in p["overflow_parked_today"]]
    assert "PARKED" in render_parked(plans[3]) and "daily digest" in render_daily(plans[3])


def test_planning_twice_on_one_day_does_not_double_count_carry():
    svc = _svc()
    for i in range(11):
        _review_posting(svc, i)
    plan_day(svc, "2026-09-21")
    again = plan_day(svc, "2026-09-21")
    assert [it["carry_days"] for it in again["review_carried"]] == [1]


def test_human_decision_removes_item_from_pending_review():
    svc = _svc()
    rid = _review_posting(svc, 1)
    svc.record_review_decision(rid, "SKIP", actor="human")
    plan = plan_day(svc, "2026-09-21")
    assert rid not in [it["requisition_id"] for it in plan["review_today"] + plan["review_carried"]]


def test_order_key_has_no_numeric_score():
    svc = _svc()
    svc.ingest(observation(raw_text=BASE_TEXT, language_detection=EN))
    item = {"relevance": "STRONG", "newness": "NEW", "evidence_completeness": 0, "work_arrangement": "REMOTE",
            "compensation_band": "IN_TARGET", "employer_preference": "PREFERRED_PRODUCT",
            "first_seen_at": "2026-09-20", "requisition_id": "req_1"}
    key = order_key(item, svc.policy)
    assert key[:6] == (0, 0, 0, 0, 0, 1)
