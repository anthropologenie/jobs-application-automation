"""
Frozen Round-2 corpus under the P6 split gates (OR-82), target jobops-policy@0.2.4.

Three families per posting case, each compared to the frozen fixture (owner-resolution overlay for the four
UNDETERMINED cases):
  * gate_e     - the five eligibility dimensions (Gate E). FX-unscorable compensation is skipped (ADAPTER_LIMIT).
  * relevance  - diagnostic only (Gate R is owner-labelled real JDs, OR-78 / OR-82).
  * lane       - diagnostic, scored only where relevance labels match.
Every known mismatch is a strict xfail whose reason is "<CLASS>:<id> — <quoted rule>", taken from
tests/fixtures/policy_v02_blind_round2_p6_classification.json. Sequences must pass.
"""

import pytest

import r2_blind_harness as r2
import r2_replay
from v02_support import no_network  # noqa: F401

V24 = "jobops-policy@0.2.4"
DOC = r2.load_doc()
CLS = r2_replay.load_classification()
DIMS = r2_replay.GATE_E_DIMS


def _mark(cid, facets):
    for f in facets:
        c = CLS.get(f"{cid}|{f}")
        if c:
            quote = c["rule"].split(":")[0][:90]
            return [pytest.mark.xfail(strict=True, reason=f"{c['class']}:{cid} — {quote}")]
    return []


def _params(facets):
    return [pytest.param(c, id=c["id"], marks=_mark(c["id"], facets)) for c in DOC["posting_cases"]]


_CACHE = {}


def _run(case):
    if case["id"] not in _CACHE:
        _CACHE[case["id"]] = r2.run_case(case, V24)
    return _CACHE[case["id"]]


def test_fixture_frozen():
    assert r2.fixture_sha() == r2.EXPECTED_SHA


@pytest.mark.parametrize("case", _params(DIMS))
def test_gate_e(case):
    rec = _run(case)
    exp, _ = r2_replay._expected_for(case)
    skip = set(rec["unscorable_fields"])
    bad = {d: (exp[d], rec["actual"][d]) for d in DIMS if d in exp and d not in skip and exp[d] != rec["actual"][d]}
    assert not bad, bad


@pytest.mark.parametrize("case", _params(["relevance"]))
def test_relevance_diagnostic(case):
    rec = _run(case)
    exp, _ = r2_replay._expected_for(case)
    if "relevance" in exp:
        assert rec["actual"]["relevance"] == exp["relevance"]


@pytest.mark.parametrize("case", _params(["lane"]))
def test_lane_where_relevance_matches(case):
    rec = _run(case)
    exp, _ = r2_replay._expected_for(case)
    if "lane" in exp and "lane" not in rec["unscorable_fields"] and exp.get("relevance") in (None, rec["actual"]["relevance"]):
        assert rec["actual"]["lane"] == exp["lane"]


@pytest.mark.parametrize("seq", DOC["sequences"], ids=[s["id"] for s in DOC["sequences"]])
def test_sequences(seq):
    assert not r2.run_sequence(seq, V24, resolved=True)["mismatches"]
