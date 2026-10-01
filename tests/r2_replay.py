"""
Replay the frozen Round-2 corpus against one policy version and print/save metrics.

Usage: python3 tests/r2_replay.py <policy-version> [--projection p4b|p5] [--out file.json]
Example: python3 tests/r2_replay.py jobops-policy@0.2.3 --out /tmp/r2_023.json

Measurement only: asserts nothing, changes nothing. The fixture hash is verified
before and after the replay; network sockets are refused.
"""

import argparse
import collections
import json
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _refuse(*a, **k):
    raise AssertionError(f"network access attempted: {a!r}")


socket.socket.connect = _refuse
socket.socket.connect_ex = _refuse
socket.create_connection = _refuse

import r2_blind_harness as h  # noqa: E402

ELIG = ("geography", "compensation", "employment_type", "employer_type", "language")


def categorize(case, rec):
    """Mismatch categories for one scored posting case (a case can be in several)."""
    exp = case["expected"]
    act = rec["actual"]
    fields = {m["field"] for m in rec["mismatches"]}
    cats = []
    if "lane" in fields:
        if act["lane"] == "EXCLUDED":
            cats.append("false_EXCLUDED")
        elif act["lane"] == "SHORTLIST":
            cats.append("false_SHORTLIST")
        elif act["lane"] == "REVIEW":
            cats.append("incorrect_REVIEW")
        elif act["lane"] == "PARKED":
            cats.append("incorrect_PARKED")
    non_lane = fields - {"lane"}
    if non_lane == {"relevance"}:
        cats.append("pure_relevance")
    if non_lane == {"language"}:
        cats.append("pure_language")
    if not non_lane and "lane" in fields:
        cats.append("pure_lane_projection")
    if rec.get("unscorable_fields"):
        cats.append("adapter_fx_unscorable_fields")
    return cats


def summarize(version, projection):
    doc = h.load_doc()
    by = {c["id"]: c for c in doc["posting_cases"]}
    before = h.fixture_sha()
    assert before == h.EXPECTED_SHA, before
    cases, seqs = h.run_all(version, projection)
    seqs_res = [h.run_sequence(s, version, projection, resolved=True) for s in doc["sequences"]]
    after = h.fixture_sha()
    assert after == h.EXPECTED_SHA, after
    det = [c for c in cases if not c.get("undetermined")]
    raw_mis = [c for c in det if c["mismatches"]]
    adj_mis = [c for c in cases if c.get("mismatches_resolution_adjusted")]
    field_counts = collections.Counter(m["field"] for c in det for m in c["mismatches"])
    cat_counts = collections.Counter()
    per_case = {}
    for c in raw_mis:
        cats = categorize(by[c["id"]], c)
        cat_counts.update(cats)
        per_case[c["id"]] = cats
    out = {
        "policy_version": version, "projection": projection, "fixture_sha256": after,
        "postings_total": len(cases),
        "raw": {"determined": len(det), "mismatched": len(raw_mis), "matched": len(det) - len(raw_mis),
                "mismatch_pct_of_124": round(100 * len(raw_mis) / len(cases), 2)},
        "resolution_adjusted": {"mismatched": len(adj_mis), "matched": len(cases) - len(adj_mis),
                                "mismatch_pct_of_124": round(100 * len(adj_mis) / len(cases), 2)},
        "sequences_total": len(seqs),
        "sequences_raw_mismatched": sum(1 for s in seqs if s["mismatches"]),
        "sequences_resolution_adjusted_mismatched": sum(1 for s in seqs_res if s["mismatches"]),
        "field_counts_raw": dict(field_counts),
        "category_counts_raw": dict(cat_counts),
        "errors": [c["id"] for c in cases if c.get("error")] + [s["id"] for s in seqs if s.get("error")],
        "mismatching_cases": {c["id"]: {"categories": per_case.get(c["id"], []),
                                        "mismatches": c["mismatches"], "unscorable": c.get("unscorable_fields")}
                              for c in raw_mis},
        "resolution_adjusted_mismatching": {c["id"]: c["mismatches_resolution_adjusted"] for c in adj_mis},
        "unscorable_cases": {c["id"]: c.get("unscorable_fields") for c in cases if c.get("unscorable_fields")},
        "sequences": {s["id"]: s for s in seqs},
        "sequences_resolution_adjusted": {s["id"]: s["mismatches"] for s in seqs_res},
        "cases": {c["id"]: c for c in cases},
    }
    return out


GATE_E_DIMS = ("geography", "compensation", "employment_type", "employer_type", "language")
GATE_E_THRESHOLD = 0.95


def _expected_for(case):
    """Fixture expectation; for an UNDETERMINED case, the owner-resolution overlay on the author's subset."""
    if case["expected"] != "UNDETERMINED":
        return case["expected"], "fixture"
    resolved = h.overlay_expected(case["id"], case.get("determined_subset"))
    return (resolved, "owner_resolution") if resolved else (case.get("determined_subset") or {}, "determined_subset")


def gate_report(version, classification=None):
    """
    P6 split gates (OR-82). Gate E = per-dimension eligibility accuracy + safety; relevance and lane are
    diagnostics only. No aggregate posting pass/fail figure is produced.
    `classification` maps "<case>|<facet>" -> {"class": ..., ...}; it only labels mismatches, it never
    changes a numerator or a denominator.
    """
    classification = classification or {}
    doc = h.load_doc()
    assert h.fixture_sha() == h.EXPECTED_SHA
    policy = h.load_policy_version(version)
    dims = {d: {"numerator": 0, "denominator": 0, "mismatches": [], "unscorable": []} for d in GATE_E_DIMS}
    rel = {"agree": 0, "scored": 0, "mismatches": [], "no_expectation": []}
    lane_same_rel = {"agree": 0, "scored": 0, "mismatches": []}
    excl = {"agree": 0, "scored": 0, "mismatches": []}
    false_excluded, false_shortlist = [], []
    for case in doc["posting_cases"]:
        rec = h.run_case(case, version, "p5")
        exp, basis = _expected_for(case)
        act = rec["actual"]
        skip = set(rec.get("unscorable_fields") or [])
        for d in GATE_E_DIMS:
            if d not in exp:
                continue
            if d in skip:
                dims[d]["unscorable"].append(case["id"])
                continue
            dims[d]["denominator"] += 1
            if act[d] == exp[d]:
                dims[d]["numerator"] += 1
            else:
                dims[d]["mismatches"].append({"id": case["id"], "expected": exp[d], "actual": act[d],
                                              "rule": rec["dimensions_raw"][d if d != "employment_type" else
                                                                           "employment_type"]["rule_id"],
                                              "classification": classification.get(f"{case['id']}|{d}")})
        if "relevance" in exp:
            rel["scored"] += 1
            if act["relevance"] == exp["relevance"]:
                rel["agree"] += 1
            else:
                rel["mismatches"].append({"id": case["id"], "expected": exp["relevance"], "actual": act["relevance"],
                                          "classification": classification.get(f"{case['id']}|relevance")})
        else:
            rel["no_expectation"].append(case["id"])
        if "lane" in exp and "lane" not in skip:
            excl["scored"] += 1
            if (act["lane"] == "EXCLUDED") == (exp["lane"] == "EXCLUDED"):
                excl["agree"] += 1
            else:
                excl["mismatches"].append({"id": case["id"], "expected": exp["lane"], "actual": act["lane"]})
            if exp.get("relevance") in (None, act["relevance"]):
                lane_same_rel["scored"] += 1
                if act["lane"] == exp["lane"]:
                    lane_same_rel["agree"] += 1
                else:
                    lane_same_rel["mismatches"].append({"id": case["id"], "expected": exp["lane"],
                                                        "actual": act["lane"],
                                                        "classification": classification.get(f"{case['id']}|lane")})
        expected_fail = any(exp.get(d) == "FAIL" for d in GATE_E_DIMS) or exp.get("lane") == "EXCLUDED"
        if act["lane"] == "EXCLUDED" and not expected_fail and "lane" not in skip:
            cls = classification.get(f"{case['id']}|false_excluded")
            false_excluded.append({"id": case["id"], "expected_lane": exp.get("lane"),
                                   "fail_rules": {d: v["rule_id"] for d, v in rec["dimensions_raw"].items()
                                                  if v["verdict"] == "FAIL"},
                                   "classification": cls,
                                   "explained": bool(cls) and cls.get("class") != "ENGINE_BUG"})
        blocks = (any(exp.get(d) in ("FAIL", "UNKNOWN") for d in GATE_E_DIMS if d not in skip)
                  or any(f in policy.review_flags for f in exp.get("must_have_flags", [])))
        if act["lane"] == "SHORTLIST" and blocks:
            cls = classification.get(f"{case['id']}|false_shortlist")
            false_shortlist.append({"id": case["id"], "classification": cls,
                                    "explained": bool(cls) and cls.get("class") != "ENGINE_BUG"})
    seqs = [h.run_sequence(s, version, "p5", resolved=True) for s in doc["sequences"]]
    seq_out = {s["id"]: {"passed": not s["mismatches"], "mismatches": s["mismatches"],
                         "classification": classification.get(f"{s['id']}|sequence")} for s in seqs}
    for d in dims.values():
        d["accuracy"] = round(d["numerator"] / d["denominator"], 4) if d["denominator"] else None
    gate = {
        "dimensions_pass": all(d["accuracy"] is not None and d["accuracy"] >= GATE_E_THRESHOLD for d in dims.values()),
        "unexplained_false_excluded": [f["id"] for f in false_excluded if not f["explained"]],
        "unexplained_false_shortlist": [f["id"] for f in false_shortlist if not f["explained"]],
        "sequences_unexplained": [k for k, v in seq_out.items() if not v["passed"] and not (
            v["classification"] and v["classification"].get("class") != "ENGINE_BUG")],
    }
    gate["gate_E"] = "PASS" if (gate["dimensions_pass"] and not gate["unexplained_false_excluded"]
                                and not gate["unexplained_false_shortlist"] and not gate["sequences_unexplained"]) \
        else "FAIL"
    assert h.fixture_sha() == h.EXPECTED_SHA
    return {"policy_version": version, "fixture_sha256": h.EXPECTED_SHA, "gate_E_dimensions": dims,
            "safety": {"false_EXCLUDED": false_excluded, "false_SHORTLIST": false_shortlist},
            "sequences": seq_out, "gate_E": gate,
            "relevance_diagnostic": rel, "lane_diagnostic_where_relevance_matches": lane_same_rel,
            "excluded_vs_not_excluded_diagnostic": excl,
            "gate_R": "PENDING REAL-JD LABELS (Round-2 relevance is diagnostic only, OR-82)"}


def load_classification():
    path = h.FIXTURES / "policy_v02_blind_round2_p6_classification.json"
    if not path.exists():
        return {}
    doc = json.loads(path.read_text(encoding="utf-8"))
    return {f"{e['id']}|{e['facet']}": e for e in doc["classifications"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("version")
    ap.add_argument("--projection", default="p5", choices=("p4b", "p5", "p6"))
    ap.add_argument("--out")
    a = ap.parse_args()
    if a.projection == "p6":
        out = gate_report(a.version, load_classification())
        if a.out:
            Path(a.out).write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
        brief = {"policy_version": out["policy_version"],
                 "gate_E_dimensions": {d: f"{v['numerator']}/{v['denominator']} = {v['accuracy']}"
                                           f" (unscorable {len(v['unscorable'])})"
                                       for d, v in out["gate_E_dimensions"].items()},
                 "false_EXCLUDED": [(f["id"], f["fail_rules"], (f["classification"] or {}).get("class"))
                                    for f in out["safety"]["false_EXCLUDED"]],
                 "false_SHORTLIST": [(f["id"], (f["classification"] or {}).get("class"))
                                     for f in out["safety"]["false_SHORTLIST"]],
                 "sequences_failing": {k: v["mismatches"] for k, v in out["sequences"].items() if not v["passed"]},
                 "gate_E": out["gate_E"],
                 "relevance_diagnostic": f"{out['relevance_diagnostic']['agree']}/{out['relevance_diagnostic']['scored']}",
                 "lane_diag_where_relevance_matches": f"{out['lane_diagnostic_where_relevance_matches']['agree']}/"
                                                      f"{out['lane_diagnostic_where_relevance_matches']['scored']}",
                 "excluded_vs_not": f"{out['excluded_vs_not_excluded_diagnostic']['agree']}/"
                                    f"{out['excluded_vs_not_excluded_diagnostic']['scored']}",
                 "gate_R": out["gate_R"]}
        print(json.dumps(brief, indent=1, default=str))
        return
    out = summarize(a.version, a.projection)
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("policy_version", "projection", "postings_total", "raw",
                                          "resolution_adjusted", "sequences_total", "sequences_raw_mismatched",
                                          "sequences_resolution_adjusted_mismatched", "field_counts_raw",
                                          "category_counts_raw", "errors")}, indent=1))


if __name__ == "__main__":
    main()
