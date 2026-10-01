"""
Round-3 blind corpus regression harness (P8 Task 0; persists the P7b measurement method).

Replays data/fixtures/round3/blind_cases_round3.json (frozen, SHA-256 in
blind_cases_round3.sha256) against any supported policy version through the
engine's public interface (EvaluationService.ingest / current_evaluation,
evaluation.queue.plan_day) on fresh in-memory SQLite. Not collected by pytest
(no test_ prefix); tests/test_p8_policy_025.py and `python3 tests/r3_blind_harness.py`
drive it.

STATUS: Round 3 is a CONSUMED tuning/regression corpus. It informed the 0.2.5 fix
pass (P8), so it is a regression diagnostic only and never the Gate E acceptance
measurement for 0.2.5 (that is a fresh, independent Round-4 holdout).

Inputs are read, never written:
  * the frozen corpus (SHA verified before and after every replay);
  * the author expected-output correction overlay
    data/fixtures/round3/blind_round3_expected_output_corrections.json
    (Addendum H; applies_to_hash = the frozen corpus SHA). It is applied to an
    in-memory copy of each case's `expected` only.

Adapter (the accepted P4b/P5 adapter from tests/r2_blind_harness.py, imported unchanged:
obs_fields, prepare, project(..., "p5")), plus the Round-3 additions fixed in P7b:
  * posting-case clock: evaluation_date, falling back to posted_date;
  * each case's own fx_table is loaded through add_fx_rate;
  * posting cases: source_external_id = case id (every case is its own requisition);
  * a sequence run is "<seq>-<observed_on>"; sequences use the posting's requisition_id URL key;
  * S-06 style `enrichment.owner_employer_classification` -> owner classification before that sighting;
  * queue sequences (queue_expectations): after each planned day the owner SKIPs every shown item.

Scoring (P7b Part B): the five Gate-E dimensions, must_have_flags / must_not_have_flags,
excluded (= lane EXCLUDED), relevance and experience_label where asserted.
Safety: false EXCLUDED = lane EXCLUDED where expected.excluded is false;
false SHORTLIST = lane SHORTLIST where the expectation has a FAIL/UNKNOWN dimension,
a review-routing must-have flag, a STRETCH experience label, or excluded = true.
REVIEW noise = lane REVIEW where every asserted dimension is PASS, no review-routing
flag or STRETCH is expected, the case is not excluded, and the engine raised an
eligibility UNKNOWN on an asserted-PASS dimension or an unexpected review flag
(relevance routing such as RELEVANCE_TITLE_PRIOR is not eligibility noise).
"""

import argparse
import copy
import hashlib
import json
import socket
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.policy_loader import load_policy_version  # noqa: E402
from evaluation.queue import plan_day  # noqa: E402
from store import repository as repo  # noqa: E402
from r2_blind_harness import obs_fields, prepare, project  # noqa: E402  (accepted adapter, unchanged)
from v02_support import fresh_service, observation  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent
R3_DIR = REPO_ROOT / "data" / "fixtures" / "round3"
CORPUS = R3_DIR / "blind_cases_round3.json"
SHA_FILE = R3_DIR / "blind_cases_round3.sha256"
OVERLAY = R3_DIR / "blind_round3_expected_output_corrections.json"
EXPECTED_SHA = "25aef0e0c0096d31231cc8ea96ea8c4796ba981c0160daa148ebeecad7c639cb"
DIMS = ("geography", "compensation", "employment_type", "employer_type", "language")
RELEVANCE_ROUTING_FLAGS = ("RELEVANCE_TITLE_PRIOR", "EXPERIENCE_STRETCH")  # relevance/fit routing, not eligibility
_CLASS = {"product": "PRODUCT", "ai_native": "AI_NATIVE", "gcc": "GCC", "enterprise": "ENTERPRISE_DIRECT",
          "staffing": "STAFFING", "consultancy": "CONSULTANCY", "engineering_led": "ENGINEERING_LED",
          "it_services": "IT_SERVICES", "third_party_payroll": "THIRD_PARTY_PAYROLL"}


def corpus_sha() -> str:
    return hashlib.sha256(CORPUS.read_bytes()).hexdigest()


def verify_corpus() -> None:
    recorded = SHA_FILE.read_text(encoding="utf-8").split()[0]
    actual = corpus_sha()
    if not (actual == recorded == EXPECTED_SHA):
        raise AssertionError(f"Round-3 corpus changed: {actual} (recorded {recorded}, frozen {EXPECTED_SHA})")


def load_overlay() -> dict:
    doc = json.loads(OVERLAY.read_text(encoding="utf-8"))
    if doc["applies_to_hash"] != EXPECTED_SHA:
        raise AssertionError("overlay does not apply to the frozen corpus")
    out = {}
    for c in doc["corrections"]:
        fields = {k: v for k, v in c.items() if k not in ("id", "basis")}
        if set(fields) - {"geography", "excluded"}:
            raise AssertionError(f"overlay {c['id']} changes more than geography/excluded")
        out[c["id"]] = fields
    return out


def load_corpus(apply_overlay: bool = True) -> dict:
    """The frozen corpus, with the author correction overlay applied to an in-memory copy."""
    verify_corpus()
    doc = json.loads(CORPUS.read_text(encoding="utf-8"))
    if apply_overlay:
        overlay = load_overlay()
        ids = {c["id"] for c in doc["cases"]}
        missing = set(overlay) - ids
        if missing:
            raise AssertionError(f"overlay ids not in corpus: {sorted(missing)}")
        doc = copy.deepcopy(doc)
        for c in doc["cases"]:
            if c["id"] in overlay:
                c["expected"].update(overlay[c["id"]])
    return doc


# ------------------------------------------------------------------ scoring

def compare(expected: dict, actual: dict, newness=None) -> list:
    out = []
    for field, exp in expected.items():
        if field == "must_have_flags":
            miss = [f for f in exp if f not in actual["flags"]]
            if miss:
                out.append({"field": field, "expected": exp, "missing": miss})
        elif field == "must_not_have_flags":
            pres = [f for f in exp if f in actual["flags"]]
            if pres:
                out.append({"field": field, "expected": exp, "present": pres})
        elif field == "excluded":
            act = actual["lane"] == "EXCLUDED"
            if act != exp:
                out.append({"field": field, "expected": exp, "actual": act, "lane": actual["lane"]})
        elif field == "newness":
            if newness != exp:
                out.append({"field": field, "expected": exp, "actual": newness})
        elif field in actual and actual[field] != exp:
            out.append({"field": field, "expected": exp, "actual": actual[field]})
    return out


def _unasserted_flags(result: dict, expected: dict) -> set:
    """Flags raised by an eligibility dimension the case does not assert (e.g. language on a no-JD record)."""
    dims = result["eligibility_dimensions"]
    return {f for d in DIMS if d not in expected for f in dims[d]["flags"]}


def safety(expected: dict, actual: dict, policy, ignore_flags=frozenset()) -> dict:
    lane = actual["lane"]
    review_flag_expected = any(f in policy.review_flags for f in expected.get("must_have_flags", []))
    blocks = (any(expected.get(d) in ("FAIL", "UNKNOWN") for d in DIMS) or review_flag_expected
              or expected.get("experience_label") == "STRETCH" or expected.get("excluded") is True)
    clean = (not blocks and all(expected.get(d, "PASS") == "PASS" for d in DIMS))
    # Noise is REVIEW caused by an eligibility UNKNOWN or a review flag the expectation does not have;
    # REVIEW from relevance routing (Tier 1 without JD, title prior) is not eligibility noise.
    cause = ([d for d in DIMS if actual[d] == "UNKNOWN" and expected.get(d) == "PASS"]
             + [f for f in actual["flags"] if f in policy.review_flags and f not in RELEVANCE_ROUTING_FLAGS
                and f not in ignore_flags and f not in expected.get("must_have_flags", [])])
    return {"false_excluded": lane == "EXCLUDED" and expected.get("excluded") is False,
            "false_shortlist": lane == "SHORTLIST" and blocks,
            "review_noise": lane == "REVIEW" and clean and bool(cause),
            "parked": lane == "PARKED"}


# ------------------------------------------------------------- posting cases

def run_case(case: dict, version: str) -> dict:
    p = case["posting"]
    policy = load_policy_version(version)
    service = fresh_service(policy)
    day = case.get("evaluation_date") or p.get("posted_date")
    service.clock = lambda: day
    for cur, rate in ((case.get("fx_table") or {}).get("rates_inr_per_unit") or {}).items():
        service.add_fx_rate(cur, rate, case["fx_table"]["snapshot_date"], "round3-fixture")
    prepare(service, p, set())
    res = service.ingest(observation(**obs_fields(p, observed_on=p.get("posted_date") or day,
                                                  run_id=f"r3-{case['id']}", ext_id=case["id"])))
    result = res["evaluation"]["result"]
    actual = project(result, "p5")
    exp = case["expected"]
    return {"id": case["id"], "actual": actual,
            "rules": {k: v["rule_id"] for k, v in result["eligibility_dimensions"].items()},
            "mismatches": compare(exp, actual),
            "dimension_mismatches": [d for d in DIMS if d in exp and exp[d] != actual[d]],
            **safety(exp, actual, policy, _unasserted_flags(result, exp))}


# ---------------------------------------------------------------- sequences

def _state(service, rid, with_result=False):
    ev = service.current_evaluation(rid)["result"]
    out = (project(ev, "p5"), repo.get_requisition(service.conn, rid)["newness_state"])
    return out + (ev,) if with_result else out


def run_sequence(seq: dict, version: str) -> dict:
    policy = load_policy_version(version)
    service = fresh_service(policy)
    seen = set()
    rid_of = {}
    steps, queue_days = [], []
    by_day = defaultdict(list)
    for o in seq["observations"]:
        by_day[o["observed_on"]].append(o)
    q_by_day = {q["day"]: q for q in seq.get("queue_expectations", [])}
    for day in sorted(set(by_day) | set(q_by_day)):
        service.clock = lambda d=day: d
        for o in by_day.get(day, []):
            p = o["posting"]
            enrich = (o.get("enrichment") or {}).get("owner_employer_classification")
            if enrich:
                service.classify_company(p["company"], _CLASS[enrich], "OWNER_CONFIRMED", "owner")
                seen.add(p["company"])
            prepare(service, p, seen)
            res = service.ingest(observation(**obs_fields(p, observed_on=day, run_id=f"{seq['id']}-{day}",
                                                          completeness=o.get("completeness"))))
            rid = res["requisition_id"]
            key = o.get("item") or o.get("posting_key") or p.get("requisition_id")
            rid_of[key] = rid
            actual, newness, result = _state(service, rid, with_result=True)
            exp = o.get("expected_after") or {}
            steps.append({"key": key, "day": day, "lane": actual["lane"],
                          "mismatches": compare(exp, actual, newness),
                          **safety(exp, actual, policy, _unasserted_flags(result, exp))})
        q = q_by_day.get(day)
        if q:
            queue_days.append(_queue_day(service, day, q, rid_of))
    after = []
    if seq.get("after_all"):
        after = _after_all(service, seq["after_all"], rid_of, max(by_day))
    mismatches = ([{**m, "step": s["key"], "day": s["day"]} for s in steps for m in s["mismatches"]]
                  + [m for qd in queue_days for m in qd["mismatches"]] + after)
    return {"id": seq["id"], "passed": not mismatches, "mismatches": mismatches, "steps": steps,
            "queue_days": queue_days}


def _queue_day(service, day, q, rid_of):
    key_of = {v: k for k, v in rid_of.items()}
    plan = plan_day(service, day)

    def keys(units):
        return [key_of.get(m, m) for u in units for m in u["member_requisition_ids"]]

    shown = keys(plan["review_today"])
    carried = keys(plan["review_carried"])
    parked = keys(plan["overflow_parked_today"])
    out = {"day": day, "shown": shown, "carried": carried, "parked": parked, "mismatches": []}
    for field, act in (("shown", shown), ("overflow_carried", carried), ("parked", parked)):
        if field in q and sorted(q[field]) != sorted(act):
            out["mismatches"].append({"field": f"queue.{field}", "day": day, "expected": q[field], "actual": act})
    if "candidates" in q and q["candidates"] != len(shown) + len(carried) + len(parked):
        out["mismatches"].append({"field": "queue.candidates", "day": day, "expected": q["candidates"],
                                  "actual": len(shown) + len(carried) + len(parked)})
    for u in plan["review_today"]:  # owner acts on every item shown
        for m in u["member_requisition_ids"]:
            service.record_review_decision(m, "SKIP", actor="human", note="R3 harness: owner acts on every item shown")
    return out


def _after_all(service, exp, rid_of, day):
    out = []
    for key, e in exp.items():
        if key in rid_of and isinstance(e, dict):
            actual, newness = _state(service, rid_of[key])
            out += [{**m, "step": key, "day": "after_all"} for m in compare(e, actual, newness)]
    plan = plan_day(service, day)
    key_of = {v: k for k, v in rid_of.items()}
    units = [sorted(key_of.get(m, m) for m in u["member_requisition_ids"])
             for u in plan["review_today"] + plan["review_carried"]]
    for group in exp.get("grouped_review_cards", []):
        if sorted(group) not in units:
            out.append({"field": "grouped_review_cards", "expected": group, "actual": units})
    if "review_cap_slots_used_by_group" in exp:
        groups = [u for u in plan["review_today"] if len(u["member_requisition_ids"]) > 1]
        if len(groups) != exp["review_cap_slots_used_by_group"]:
            out.append({"field": "review_cap_slots_used_by_group", "expected": exp["review_cap_slots_used_by_group"],
                        "actual": len(groups)})
    if "suppressed_duplicate" in exp:
        sup = bool(plan["lanes"]["SUPPRESSED_DUPLICATE"])
        if sup != exp["suppressed_duplicate"]:
            out.append({"field": "suppressed_duplicate", "expected": exp["suppressed_duplicate"], "actual": sup})
    return out


# ------------------------------------------------------------------- report

def run_all(version: str) -> dict:
    doc = load_corpus()
    cases = [run_case(c, version) for c in doc["cases"]]
    seqs = [run_sequence(s, version) for s in doc["sequences"]]
    verify_corpus()
    dims = {}
    for d in DIMS:
        scored = [c for c, case in zip(cases, doc["cases"]) if d in case["expected"]]
        bad = [c["id"] for c in scored if d in c["dimension_mismatches"]]
        dims[d] = {"correct": len(scored) - len(bad), "total": len(scored), "mismatches": bad}
    seq_steps = [s for q in seqs for s in q["steps"]]
    return {
        "policy_version": version, "corpus_sha256": corpus_sha(), "overlay_applied": True,
        "status": "REGRESSION DIAGNOSTIC ONLY (Round 3 is consumed; not a Gate E measurement)",
        "dimensions": dims,
        "dimension_mismatch_cases": sorted({c["id"] for c in cases if c["dimension_mismatches"]}),
        "any_mismatch_cases": {c["id"]: c["mismatches"] for c in cases if c["mismatches"]},
        "false_excluded": [c["id"] for c in cases if c["false_excluded"]]
        + [f"{q['id']}:{s['key']}" for q in seqs for s in q["steps"] if s["false_excluded"]],
        "false_shortlist": [c["id"] for c in cases if c["false_shortlist"]]
        + [f"{q['id']}:{s['key']}" for q in seqs for s in q["steps"] if s["false_shortlist"]],
        "review_noise": [c["id"] for c in cases if c["review_noise"]],
        "parked_cases": [c["id"] for c in cases if c["parked"]],
        "sequence_overflow_parked": sum(len(d["parked"]) for q in seqs for d in q["queue_days"]),
        "sequence_step_parked": sum(1 for s in seq_steps if s["parked"]),
        "sequences": {q["id"]: {"passed": q["passed"], "mismatches": q["mismatches"]} for q in seqs},
        "cases": {c["id"]: {k: c[k] for k in ("actual", "rules", "mismatches")} for c in cases},
    }


def _refuse(*a, **k):
    raise AssertionError(f"network access attempted: {a!r}")


def main():
    socket.socket.connect = _refuse
    socket.socket.connect_ex = _refuse
    socket.create_connection = _refuse
    ap = argparse.ArgumentParser()
    ap.add_argument("version")
    ap.add_argument("--out")
    a = ap.parse_args()
    out = run_all(a.version)
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    brief = {k: out[k] for k in ("policy_version", "corpus_sha256", "status", "dimension_mismatch_cases",
                                 "false_excluded", "false_shortlist", "review_noise",
                                 "sequence_overflow_parked")}
    brief["dimensions"] = {d: f"{v['correct']}/{v['total']} {v['mismatches']}" for d, v in out["dimensions"].items()}
    brief["parked_cases"] = len(out["parked_cases"])
    brief["sequences"] = {k: (v["passed"], v["mismatches"][:3]) for k, v in out["sequences"].items()}
    brief["flag_or_other_mismatch_cases"] = sorted(set(out["any_mismatch_cases"]) - set(out["dimension_mismatch_cases"]))
    print(json.dumps(brief, indent=1, default=str))


if __name__ == "__main__":
    main()
