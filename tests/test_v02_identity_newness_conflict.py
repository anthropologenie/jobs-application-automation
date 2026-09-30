"""Canonical identity, newness and source-conflict behaviour (Phase B §24-§27)."""

import json

from store import repository as repo
from v02_support import BASE_TEXT, EN, fresh_service, no_network, observation  # noqa: F401

ATS = "https://boards.greenhouse.io/syntheticproductco/jobs/9000001"
LI = "https://www.linkedin.com/jobs/view/4000000001"


def svc():
    s = fresh_service()
    s.classify_company("Synthetic Product Co", "PRODUCT", "INFERRED_FROM_EVIDENCE", "machine")
    return s


def board(**kw):
    base = dict(source="linkedin-search", source_kind="JOB_BOARD", source_url=LI, source_external_id="4000000001",
                raw_text=BASE_TEXT, language_detection=EN)
    base.update(kw)
    return observation(**base)


def test_first_observation_is_new_with_date_precision():
    s = svc()
    r = s.ingest(board(source_posted_date="2026-09-20"))
    req = r["requisition"]
    assert req["newness_state"] == "NEW" and req["date_precision"] == "DATE" and req["newness_confidence"] == "MEDIUM"
    r2 = svc().ingest(board(source_posted_date="2026-09-20T05:10:00+00:00"))
    assert r2["requisition"]["newness_confidence"] == "HIGH"


def test_same_requisition_across_sources_is_one_canonical_opportunity():
    s = svc()
    a = s.ingest(observation(source_url=ATS, raw_text=BASE_TEXT, language_detection=EN))
    b = s.ingest(board(apply_url=ATS))
    assert a["requisition_id"] == b["requisition_id"]
    assert len([r for r in repo.requisitions(s.conn) if not r["duplicate_of"]]) == 1
    obs = repo.observations_for(s.conn, [a["requisition_id"]])
    assert {o["source"] for o in obs} == {"ats:greenhouse", "linkedin-search"}


def test_employer_url_becomes_canonical_even_when_board_seen_first():
    s = svc()
    first = s.ingest(board(apply_url=ATS, observed_at="2026-09-19T06:00:00+00:00"))
    assert "linkedin" not in first["requisition"]["canonical_url"] or first["requisition"]["canonical_url_authority"] == 1
    s.ingest(observation(source_url=ATS, raw_text=BASE_TEXT, language_detection=EN, run_id="t-run-2"))
    req = repo.get_requisition(s.conn, first["requisition_id"])
    assert "greenhouse" in req["canonical_url"]
    assert req["first_seen_at"] == "2026-09-19T06:00:00+00:00"


def test_two_existing_requisitions_merge_as_suppressed_duplicate_not_deleted():
    s = svc()
    li_only = s.ingest(board())                                   # LinkedIn, no apply URL
    ats_only = s.ingest(observation(source_url=ATS, raw_title="AI Engineer (Platform)", raw_text=BASE_TEXT, language_detection=EN))
    assert li_only["requisition_id"] != ats_only["requisition_id"]
    s.ingest(board(apply_url=ATS, run_id="t-run-2", observed_at="2026-09-21T06:00:00+00:00"))
    dup = [r for r in repo.requisitions(s.conn) if r["duplicate_of"]]
    assert len(dup) == 1 and dup[0]["duplicate_of"] == ats_only["requisition_id"]
    assert s.current_evaluation(dup[0]["requisition_id"])["queue_lane"] == "SUPPRESSED_DUPLICATE"
    # nothing moved or deleted: the duplicate keeps its own sighting, the family holds all three
    assert len(repo.observations_for(s.conn, [dup[0]["requisition_id"]])) == 1
    assert len(repo.observations_for(s.conn, [dup[0]["requisition_id"], ats_only["requisition_id"]])) == 3


def test_similar_titles_are_not_merged():
    s = svc()
    a = s.ingest(observation(source_url="https://boards.greenhouse.io/x/jobs/1", raw_title="AI Engineer", raw_text=BASE_TEXT, language_detection=EN))
    b = s.ingest(observation(source_url="https://boards.greenhouse.io/x/jobs/2", raw_title="AI Engineer II", raw_text=BASE_TEXT, language_detection=EN))
    assert a["requisition_id"] != b["requisition_id"]


def test_identity_uncertain_routes_to_review_and_is_not_merged():
    s = svc()
    a = s.ingest(observation(source_url="https://boards.greenhouse.io/x/jobs/1", raw_text=BASE_TEXT, language_detection=EN))
    b = s.ingest(board())
    assert a["requisition_id"] != b["requisition_id"]
    for rid in (a["requisition_id"], b["requisition_id"]):
        ev = s.current_evaluation(rid)["result"]
        assert "IDENTITY_UNCERTAIN" in ev["flags"] and ev["lane"] == "REVIEW"
    links = s.conn.execute("SELECT outcome FROM identity_link").fetchall()
    assert [l[0] for l in links] == ["PROBABLE_DUPLICATE"]


def test_conflicting_ats_requisition_ids_on_one_tenant_flag_uncertainty():
    s = svc()
    s.ingest(board(apply_url="https://boards.greenhouse.io/syntheticproductco/jobs/1"))
    r = s.ingest(board(apply_url="https://boards.greenhouse.io/syntheticproductco/jobs/2", run_id="t-run-2"))
    assert "IDENTITY_UNCERTAIN" in r["evaluation"]["result"]["flags"]


def test_source_conflict_preserves_both_and_prefers_ats_facts():
    s = svc()
    s.ingest(board(apply_url=ATS, raw_text=BASE_TEXT.replace("₹26 LPA", "₹20 LPA")))
    r = s.ingest(observation(source_url=ATS, raw_text=BASE_TEXT, language_detection=EN))
    res = r["evaluation"]["result"]
    assert "SOURCE_CONFLICT" in res["flags"] and res["lane"] == "REVIEW"
    assert res["compensation_normalized"]["min_inr"] == 2600000       # ATS value selected
    conflict = next(c for c in res["source_conflicts"] if c["dimension"] == "compensation")
    assert conflict["other_source"] == "linkedin-search"               # board value preserved in the record
    assert len(repo.observations_for(s.conn, [r["requisition_id"]])) == 2


def test_same_source_change_is_update_not_conflict():
    s = svc()
    s.ingest(observation(source_url=ATS, raw_text=BASE_TEXT, language_detection=EN))
    r = s.ingest(observation(source_url=ATS, raw_text=BASE_TEXT.replace("₹26 LPA", "₹30 LPA"), language_detection=EN,
                             run_id="t-run-2", observed_at="2026-09-22T06:00:00+00:00"))
    res = r["evaluation"]["result"]
    assert "SOURCE_CONFLICT" not in res["flags"]
    assert r["requisition"]["newness_state"] == "UPDATED"
    assert res["compensation_normalized"]["min_inr"] == 3000000        # newest same-source value wins


def test_enrichment_is_seen_before_not_updated():
    s = svc()
    s.ingest(board(completeness="SEARCH_ONLY", raw_text=None, language_detection=None, raw_location="Bengaluru, Karnataka, India"))
    r = s.ingest(board(run_id="t-run-2", observed_at="2026-09-21T06:00:00+00:00", raw_location="Bengaluru, Karnataka, India"))
    assert r["requisition"]["newness_state"] == "SEEN_BEFORE"
    assert "enrichment" in r["requisition"]["newness_reason_json"]


def test_freshness_is_kept_per_source():
    s = svc()
    s.ingest(board(apply_url=ATS, observed_at="2026-09-18T06:00:00+00:00"))
    r = s.ingest(observation(source_url=ATS, raw_text=BASE_TEXT, language_detection=EN, run_id="t-run-2"))
    first_seen = json.loads(r["requisition"]["source_first_seen_json"])
    assert first_seen == {"linkedin-search": "2026-09-18T06:00:00+00:00", "ats:greenhouse": "2026-09-20T06:00:00+00:00"}
