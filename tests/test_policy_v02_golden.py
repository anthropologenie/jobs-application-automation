"""
Executable, versioned golden cases (tests/fixtures/policy_v02_golden_cases.json).

Every case runs under every supported v2 policy version (0.2.0, 0.2.1, 0.2.2)
unless it lists `policy_versions` (P3: cases written for behaviour introduced
in 0.2.2 run under 0.2.2 only; older versions are proven unchanged by the
pre-existing cases, whose 0.2.0 / 0.2.1 expectations are untouched). A case
with `expected` must hold under every version it runs under; a case with
`expected_by_version` is checked against the expectation for the version under
test. The evaluation-date clock is injected (fixture default or per-case override).

Single-observation cases assert all six eligibility dimensions, the overall
verdict, relevance label/tier/clusters/experience/seniority, preference
attributes, the exact flag set, newness and lane. Multi-observation cases are
ingested in sequence and checked after every step.
"""

import json
from pathlib import Path

import pytest

from evaluation.policy_loader import POLICY_PATHS, load_policy_version
from identity.canonical import canonicalize_url
from identity.ruleset import load_identity_ruleset
from store import repository as repo
from v02_support import no_network, fresh_service, observation  # noqa: F401

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "policy_v02_golden_cases.json"
DOC = json.loads(FIXTURE.read_text(encoding="utf-8"))
DEFAULT_DATE = DOC["artifact"]["default_evaluation_date"]
VERSIONS = sorted(POLICY_PATHS)
SINGLE = [c for c in DOC["cases"] if "observation" in c]
MULTI = [c for c in DOC["cases"] if "observations" in c]


def _versions(case):
    return case.get("policy_versions") or VERSIONS


def _params(cases):
    return [pytest.param(c, v, id=f"{c['case_id']}@{v.split('@')[1]}") for c in cases for v in _versions(c)]


def _expected(case, version):
    by_version = case.get("expected_by_version")
    return by_version[version] if by_version else case["expected"]


def _service(case, version):
    date = case.get("evaluation_date", DEFAULT_DATE)
    service = fresh_service(load_policy_version(version))
    service.clock = lambda: date
    reg = case.get("registry")
    if reg:
        service.classify_company(reg["company"], reg["classification"], reg["basis"], "machine:registry")
    if case.get("owner_classification"):
        service.classify_company(reg["company"], case["owner_classification"], "OWNER_CONFIRMED", "owner")
    fx = case.get("fx_snapshot")
    if fx:
        service.add_fx_rate(fx["currency"], fx["rate"], fx["snapshot_date"], fx["source"])
    return service


def test_fixture_shape():
    assert DOC["case_count"] == len(DOC["cases"]) >= 70
    assert set(DOC["artifact"]["policy_versions_under_test"]) == set(VERSIONS)
    required = {"case_id", "posting_text", "geography_evidence", "compensation_evidence", "employment_evidence",
                "employer_evidence", "language_evidence", "experience_evidence", "relevance_evidence"}
    for c in DOC["cases"]:
        assert required <= set(c), c["case_id"]
        assert ("expected" in c) != ("expected_by_version" in c), c["case_id"]
        assert set(_versions(c)) <= set(VERSIONS), c["case_id"]
        if "expected_by_version" in c:
            assert set(c["expected_by_version"]) == set(_versions(c)), c["case_id"]
            distinct = {json.dumps(v, sort_keys=True) for v in c["expected_by_version"].values()}
            assert len(distinct) > 1, f"{c['case_id']}: identical per-version expectations must be shared"
        assert "OPEN:" not in json.dumps(c.get("expected") or c.get("expected_by_version")), c["case_id"]


@pytest.mark.parametrize("case,version", _params(SINGLE))
def test_single_observation_case(case, version):
    service = _service(case, version)
    obs = dict(case["observation"])
    result = service.ingest(observation(**obs))
    r = result["evaluation"]["result"]
    assert r["policy_version"] == version
    exp = _expected(case, version)
    got_dims = {k: v["verdict"] for k, v in r["eligibility_dimensions"].items()}
    assert got_dims == exp["eligibility_dimensions"], (case["case_id"], r["eligibility_dimensions"])
    assert r["eligibility_overall"] == exp["eligibility_overall"]
    rel = r["relevance"]
    for key, value in exp["relevance"].items():
        assert rel[key] == value, (case["case_id"], key, rel[key], rel.get("evidence_spans"))
    for key, value in exp["preference_attributes"].items():
        assert r["preference_attributes"][key] == value, (case["case_id"], key)
    assert sorted(r["flags"]) == exp["flags"], (case["case_id"], r["flags"])
    assert result["requisition"]["newness_state"] == exp["newness"]
    assert r["lane"] == exp["lane"], (case["case_id"], r["lane"], r["lane_rule"])
    if rel["relevance_label"] in ("STRONG", "MODERATE", "WEAK"):
        text = obs.get("raw_text") or ""
        for span in rel["evidence_spans"]:
            assert span["quoted_span"] in text, "evidence spans must be verbatim JD text"


@pytest.mark.parametrize("case,version", _params(MULTI))
def test_multi_observation_case(case, version):
    service = _service(case, version)
    expected = _expected(case, version)
    req_of_seq = {}
    for obs in case["observations"]:
        seq = obs["seq"]
        before = {r["requisition_id"]: len(repo.evaluations_for(service.conn, r["requisition_id"]))
                  for r in repo.requisitions(service.conn)}
        result = service.ingest(observation(**obs))
        req_of_seq[seq] = result["requisition_id"]
        for step in [s for s in expected["steps"] if s["after_seq"] == seq]:
            rid = req_of_seq[step.get("requisition_of_seq", seq)]
            if "same_requisition_as_seq" in step:
                other = step["same_requisition_as_seq"]
                if other is None:
                    assert rid not in [req_of_seq[s] for s in req_of_seq if s != seq]
                else:
                    assert rid == req_of_seq[other], (case["case_id"], step)
            ev = service.current_evaluation(rid)
            r = ev["result"]
            req = repo.get_requisition(service.conn, rid)
            if "lane" in step:
                assert r["lane"] == step["lane"], (case["case_id"], step, r["lane"], r["flags"])
            if "newness" in step:
                assert req["newness_state"] == step["newness"], (case["case_id"], step, req["newness_reason_json"])
            if "newness_reason_include" in step:
                assert step["newness_reason_include"] in req["newness_reason_json"]
            if "eligibility_overall" in step:
                assert r["eligibility_overall"] == step["eligibility_overall"]
            if "relevance_label" in step:
                assert r["relevance"]["relevance_label"] == step["relevance_label"]
            for f in step.get("flags_include", []):
                assert f in r["flags"], (case["case_id"], step, r["flags"])
            if "work_arrangement" in step:
                assert r["preference_attributes"]["work_arrangement"] == step["work_arrangement"]
            if "new_evaluation_written" in step:
                grew = len(repo.evaluations_for(service.conn, rid)) > before.get(rid, 0)
                assert grew == step["new_evaluation_written"], (case["case_id"], step)
    final = expected
    roots = [r for r in repo.requisitions(service.conn) if not r["duplicate_of"]]
    assert len(roots) == final["requisition_count"]
    if "canonical_url_from_seq" in final:
        seq = final["canonical_url_from_seq"]
        obs = next(o for o in case["observations"] if o["seq"] == seq)
        expected_url = canonicalize_url(obs["source_url"], load_identity_ruleset()).identity_url
        assert repo.get_requisition(service.conn, req_of_seq[seq])["canonical_url"] == expected_url
    if "first_seen_at" in final:
        req = repo.get_requisition(service.conn, req_of_seq[1])
        assert req["first_seen_at"] == final["first_seen_at"]
        assert json.loads(req["source_first_seen_json"]) == final["source_first_seen"]
