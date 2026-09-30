"""
F4 regression: a sparse later sighting can never downgrade an evaluation made on
richer evidence; replay of any policy version over stored evidence, no recrawl.
"""

import copy
import json

from evaluation.policy_loader import DEFAULT_POLICY_PATH, policy_from_doc
from evaluation.v01_adapter import V01ReplayPolicy
from store import repository as repo
from v02_support import BASE_TEXT, EN, fresh_service, no_network, observation  # noqa: F401

LI = "https://www.linkedin.com/jobs/view/4000000001"
ATS = "https://boards.greenhouse.io/syntheticproductco/jobs/9000001"


def svc(policy=None):
    s = fresh_service(policy)
    s.classify_company("Synthetic Product Co", "PRODUCT", "INFERRED_FROM_EVIDENCE", "machine")
    return s


def li(**kw):
    base = dict(source="linkedin-search", source_kind="JOB_BOARD", source_url=LI, source_external_id="4000000001",
                raw_location="Bengaluru, Karnataka, India")
    base.update(kw)
    return observation(**base)


def sparse(run, at):
    return li(completeness="SEARCH_ONLY", raw_text=None, run_id=run, observed_at=at, source_posted_date="2026-09-20")


def test_f4_jd_bearing_then_search_only_never_downgrades():
    s = svc()
    first = s.ingest(li(raw_text=BASE_TEXT, language_detection=EN))
    assert first["evaluation"]["queue_lane"] == "SHORTLIST"
    for i in range(3):
        again = s.ingest(sparse(f"run-{i + 2}", f"2026-09-2{i + 1}T06:00:00+00:00"))
        ev = again["evaluation"]
        assert ev["evaluation_id"] == first["evaluation"]["evaluation_id"]
        assert ev["eligibility_overall"] == "PASS" and ev["relevance_label"] == "STRONG" and ev["queue_lane"] == "SHORTLIST"
    assert len(repo.evaluations_for(s.conn, first["requisition_id"])) == 1
    assert len(repo.observations_for(s.conn, [first["requisition_id"]])) == 4     # every sighting kept


def test_f4_search_only_then_jd_bearing_upgrades():
    s = svc()
    first = s.ingest(sparse("run-1", "2026-09-20T06:00:00+00:00"))
    assert first["evaluation"]["relevance_label"] == "NOT_ASSESSED"
    second = s.ingest(li(raw_text=BASE_TEXT, language_detection=EN, run_id="run-2", observed_at="2026-09-21T06:00:00+00:00"))
    assert second["evaluation"]["relevance_label"] == "STRONG"
    assert second["evaluation"]["queue_lane"] == "SHORTLIST"
    assert second["requisition"]["newness_state"] == "SEEN_BEFORE"


def test_f4_multiple_sources_with_different_completeness():
    s = svc()
    s.ingest(sparse("run-1", "2026-09-19T06:00:00+00:00"))                                    # board, search-only
    s.ingest(observation(source_url=ATS, raw_text=BASE_TEXT, language_detection=EN, run_id="run-1",
                         observed_at="2026-09-19T07:00:00+00:00"))                             # ATS, full JD (not yet linked)
    linked = s.ingest(li(apply_url=ATS, completeness="PARTIAL", raw_text="AI Engineer role. Apply on our site.",
                         run_id="run-2", observed_at="2026-09-20T06:00:00+00:00"))            # board partial, links both
    ev = linked["evaluation"]["result"]
    assert ev["eligibility_overall"] == "PASS" and ev["relevance"]["relevance_label"] == "STRONG"
    geo_obs = ev["selected_evidence"]["geography"]["observation_id"]
    chosen = next(o for o in repo.observations_for(s.conn, [r["requisition_id"] for r in repo.requisitions(s.conn)])
                  if o["observation_id"] == geo_obs)
    assert chosen["source"] == "ats:greenhouse" and chosen["completeness"] == "FULL_JD"


def test_f4_unchanged_identity_richer_evidence():
    s = svc()
    a = s.ingest(li(completeness="PARTIAL", raw_text="Location: Remote - India.\nSalary: ₹26 LPA fixed base.", language_detection=EN))
    assert a["evaluation"]["relevance_label"] == "WEAK"
    b = s.ingest(li(raw_text=BASE_TEXT, language_detection=EN, run_id="run-2", observed_at="2026-09-21T06:00:00+00:00"))
    assert b["requisition_id"] == a["requisition_id"]
    assert b["evaluation"]["relevance_label"] == "STRONG"
    c = s.ingest(sparse("run-3", "2026-09-22T06:00:00+00:00"))
    assert c["evaluation"]["evaluation_id"] == b["evaluation"]["evaluation_id"]


def test_replay_under_variant_policy_without_recrawl_keeps_old_evaluation():
    s = svc()
    r = s.ingest(li(raw_text=BASE_TEXT.replace("₹26 LPA", "₹20 LPA"), language_detection=EN))
    v02 = r["evaluation"]
    assert v02["result"]["eligibility_dimensions"]["compensation"]["verdict"] == "PASS"
    doc = copy.deepcopy(json.loads(DEFAULT_POLICY_PATH.read_text(encoding="utf-8")))
    doc["artifact"]["ruleset_version"] = "jobops-policy@0.2.99-replay-test"
    doc["parameters"]["floor"] = 2200000
    variant = policy_from_doc(doc, expected_version=None)
    replayed = s.replay(r["requisition_id"], variant)
    assert replayed["policy_version"] == "jobops-policy@0.2.99-replay-test"
    assert replayed["result"]["eligibility_dimensions"]["compensation"]["verdict"] == "FAIL"
    # the original evaluation is untouched and still retrievable
    assert repo.evaluations_for(s.conn, r["requisition_id"], s.policy.version)[0]["evaluation_id"] == v02["evaluation_id"]
    # replay is idempotent
    assert s.replay(r["requisition_id"], variant)["evaluation_id"] == replayed["evaluation_id"]
    # replay used stored observations only
    assert len(repo.observations_for(s.conn, [r["requisition_id"]])) == 1


def test_replay_under_v01_gate_from_stored_evidence():
    s = svc()
    r = s.ingest(observation(source_url=ATS, raw_text=BASE_TEXT.replace("₹26 LPA", "₹19 LPA"), language_detection=EN))
    assert r["evaluation"]["result"]["eligibility_dimensions"]["compensation"]["verdict"] == "PASS"   # v0.2: ₹18L floor
    v01 = s.replay(r["requisition_id"], V01ReplayPolicy())
    assert v01["policy_version"] == "jobops-policy@0.1.0"
    assert v01["eligibility_overall"] == "FAIL"                                                        # v0.1: ₹20L floor
    assert "COMP-FAIL-BELOW-FLOOR" in v01["result"]["flags"]
    assert s.replay(r["requisition_id"], V01ReplayPolicy())["evaluation_id"] == v01["evaluation_id"]


def test_current_evaluation_is_deterministic_across_databases():
    def run():
        s = svc()
        s.ingest(li(raw_text=BASE_TEXT, language_detection=EN))
        rid = s.ingest(sparse("run-2", "2026-09-21T06:00:00+00:00"))["requisition_id"]
        return s.current_evaluation(rid)
    a, b = run(), run()
    assert a["evidence_hash"] == b["evidence_hash"]
    assert {k: v for k, v in a["result"].items()} == {k: v for k, v in b["result"].items()}
