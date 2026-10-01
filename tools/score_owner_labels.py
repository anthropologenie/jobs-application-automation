#!/usr/bin/env python3
"""
Score owner labels against the engine (Gate R instrument, P6).

    python3 tools/score_owner_labels.py data/replay/run1/owner_labels.csv [--out report.md] [--json]

Reads the owner-label CSV written by tools/replay_real_jds.py after the owner has filled owner_relevance
(STRONG|MODERATE|WEAK), owner_eligibility (PASS|FAIL|UNKNOWN) and owner_lane (SHORTLIST|REVIEW|PARKED|EXCLUDED).
Optional per-dimension owner columns (owner_geography, owner_compensation, owner_employment_type,
owner_employer_type, owner_language) are scored when present. Rows without owner labels are counted, not scored.

Reports relevance confusion, eligibility agreement, the safety rows (engine EXCLUDED + owner eligible, engine
SHORTLIST + owner ineligible) and JD length vs owner relevance. There is deliberately no single composite
quality score (OR-82): Gate R and Gate E are separate, and each table is read on its own.
"""

import argparse
import csv
import json
import statistics
from pathlib import Path
from typing import Any, Dict, List

REL = ("STRONG", "MODERATE", "WEAK")
ENGINE_REL = ("STRONG", "MODERATE", "WEAK", "NOT_ASSESSED")
ELIG = ("PASS", "FAIL", "UNKNOWN")
DIMS = ("geography", "compensation", "employment_type", "employer_type", "language")


def _norm(v):
    return (v or "").strip().upper()


def score(rows: List[Dict[str, str]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {"rows": len(rows)}
    # ------------------------------------------------------------ relevance
    labelled = [r for r in rows if _norm(r.get("owner_relevance")) in REL]
    out["relevance_labelled"] = len(labelled)
    cm = {e: {o: 0 for o in REL} for e in ENGINE_REL}
    for r in labelled:
        e = _norm(r["engine_relevance"])
        if e in cm:
            cm[e][_norm(r["owner_relevance"])] += 1
    out["relevance_confusion"] = cm
    tp = cm["STRONG"]["STRONG"]
    eng_strong = sum(cm["STRONG"].values())
    own_strong = sum(cm[e]["STRONG"] for e in ENGINE_REL)
    out["strong_precision"] = round(tp / eng_strong, 4) if eng_strong else None
    out["strong_recall"] = round(tp / own_strong, 4) if own_strong else None
    for label in ("MODERATE", "WEAK"):
        own = sum(cm[e][label] for e in ENGINE_REL)
        out[f"{label.lower()}_agreement"] = f"{cm[label][label]}/{own}"
    out["relevance_disagreements"] = [
        {"posting_id": r["posting_id"], "title": r["title"], "engine": _norm(r["engine_relevance"]),
         "owner": _norm(r["owner_relevance"]), "jd_word_count": r.get("jd_word_count")}
        for r in labelled if _norm(r["engine_relevance"]) != _norm(r["owner_relevance"])][:25]
    # ----------------------------------------------------------- eligibility
    el = [r for r in rows if _norm(r.get("owner_eligibility")) in ELIG]
    out["eligibility_labelled"] = len(el)
    out["eligibility_agreement"] = f"{sum(_norm(r['engine_eligibility']) == _norm(r['owner_eligibility']) for r in el)}/{len(el)}"
    per_dim = {}
    for d in DIMS:
        col = f"owner_{d}"
        scored = [r for r in rows if _norm(r.get(col)) in ELIG and r.get(f"engine_{d}")]
        if scored:
            per_dim[d] = f"{sum(_norm(r[f'engine_{d}']) == _norm(r[col]) for r in scored)}/{len(scored)}"
    out["per_dimension_agreement"] = per_dim or "no owner per-dimension columns supplied"
    excl = [r for r in el if _norm(r["engine_lane"]) == "EXCLUDED"]
    out["engine_excluded_vs_owner_eligibility"] = {v: sum(_norm(r["owner_eligibility"]) == v for r in excl) for v in ELIG}
    parked = [r for r in rows if _norm(r["engine_lane"]) == "PARKED"]
    out["engine_parked_vs_owner"] = {
        "owner_relevance": {v: sum(_norm(r.get("owner_relevance")) == v for r in parked) for v in REL},
        "owner_eligibility": {v: sum(_norm(r.get("owner_eligibility")) == v for r in parked) for v in ELIG}}
    # --------------------------------------------------------------- safety
    out["safety_engine_excluded_owner_eligible"] = [
        {"posting_id": r["posting_id"], "title": r["title"], "owner_eligibility": _norm(r["owner_eligibility"]),
         "engine_flags": r.get("engine_flags")}
        for r in el if _norm(r["engine_lane"]) == "EXCLUDED" and _norm(r["owner_eligibility"]) in ("PASS", "UNKNOWN")]
    out["safety_engine_shortlist_owner_ineligible"] = [
        {"posting_id": r["posting_id"], "title": r["title"], "owner_eligibility": _norm(r["owner_eligibility"])}
        for r in el if _norm(r["engine_lane"]) == "SHORTLIST" and _norm(r["owner_eligibility"]) == "FAIL"]
    out["engine_shortlist_owner_unknown"] = [r["posting_id"] for r in el
                                             if _norm(r["engine_lane"]) == "SHORTLIST"
                                             and _norm(r["owner_eligibility"]) == "UNKNOWN"]
    # ------------------------------------------------------------ JD length
    lengths = [int(r["jd_word_count"]) for r in rows if str(r.get("jd_word_count", "")).isdigit()]
    if lengths:
        q = statistics.quantiles(lengths, n=4) if len(lengths) >= 2 else [lengths[0]] * 3
        out["jd_length"] = {"min": min(lengths), "q1": q[0], "median": statistics.median(lengths), "q3": q[2],
                            "max": max(lengths)}
        by = {}
        for r in labelled:
            if str(r.get("jd_word_count", "")).isdigit():
                by.setdefault(_norm(r["owner_relevance"]), []).append(int(r["jd_word_count"]))
        out["jd_length_by_owner_relevance"] = {k: {"n": len(v), "median_words": statistics.median(v)}
                                               for k, v in sorted(by.items())}
        out["jd_length_note"] = "Descriptive only: association between JD length and owner relevance is not causation."
    return out


def to_markdown(s: Dict[str, Any]) -> str:
    cm = s["relevance_confusion"]
    lines = ["# Owner-label scoring (Gate R instrument)", "",
             f"Rows: {s['rows']} · relevance-labelled: {s['relevance_labelled']} · "
             f"eligibility-labelled: {s['eligibility_labelled']}", "",
             "No composite score: Gate R (relevance) and Gate E (eligibility/safety) are read separately (OR-82).", "",
             "## Relevance confusion (rows = engine, columns = owner)", "",
             "| engine \\ owner | STRONG | MODERATE | WEAK |", "|---|---|---|---|"]
    lines += [f"| {e} | " + " | ".join(str(cm[e][o]) for o in REL) + " |" for e in ENGINE_REL]
    lines += ["", f"- STRONG precision: {s['strong_precision']} · STRONG recall: {s['strong_recall']}",
              f"- MODERATE agreement: {s['moderate_agreement']} · WEAK agreement: {s['weak_agreement']}", "",
              "### Disagreement examples", ""]
    lines += [f"- {d['posting_id']} {d['title']}: engine {d['engine']} vs owner {d['owner']} "
              f"({d['jd_word_count']} words)" for d in s["relevance_disagreements"]] or ["- none"]
    lines += ["", "## Eligibility", "", f"- Overall eligibility agreement: {s['eligibility_agreement']}",
              f"- Per-dimension agreement: {s['per_dimension_agreement']}",
              f"- Engine EXCLUDED vs owner eligibility: {s['engine_excluded_vs_owner_eligibility']}",
              f"- Engine PARKED vs owner labels: {s['engine_parked_vs_owner']}", "",
              "## SAFETY (most important rows)", "", "### Engine EXCLUDED but owner says eligible (PASS / UNKNOWN)", ""]
    lines += [f"- {r['posting_id']} {r['title']} (owner {r['owner_eligibility']}; flags {r['engine_flags']})"
              for r in s["safety_engine_excluded_owner_eligible"]] or ["- none"]
    lines += ["", "### Engine SHORTLIST but owner says ineligible (FAIL)", ""]
    lines += [f"- {r['posting_id']} {r['title']}" for r in s["safety_engine_shortlist_owner_ineligible"]] or ["- none"]
    lines += ["", f"Engine SHORTLIST with owner UNKNOWN: {s['engine_shortlist_owner_unknown'] or 'none'}"]
    if "jd_length" in s:
        lines += ["", "## JD length", "", f"- Words: {s['jd_length']}",
                  f"- Median words by owner relevance: {s['jd_length_by_owner_relevance']}", f"- {s['jd_length_note']}"]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("labels", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    with open(a.labels, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    s = score(rows)
    text = json.dumps(s, indent=1) if a.json else to_markdown(s)
    if a.out:
        a.out.write_text(text, encoding="utf-8")
    print(text)
    return s


if __name__ == "__main__":
    main()
