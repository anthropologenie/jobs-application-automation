"""
P9 outputs for one run: <out>/<date>/{digest.md, excluded.csv, decisions.csv, metrics.json, jd/<job_id>.txt}.

Rendering only. Every verdict, lane, flag and quote comes from the stored evaluation and evidence; quotes are
verbatim spans of the supplied record. No wall-clock value is written, so the same run renders byte-identically.
"""

import csv
import io
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from .sourcing import ALL_DIMS, DIMS

TARGETS = (25, 30)
DIM_LABEL = {"geography": "geography", "compensation": "compensation", "employment_type": "employment",
             "employer_type": "employer", "language": "language", "employment_relationship": "relationship"}


def _csv(rows: List[List[Any]]) -> str:
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(rows)
    return buf.getvalue()


def _one_line(text: str, limit: int = 220) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


# ---------------------------------------------------------------- metrics

def metrics(res: Dict[str, Any]) -> Dict[str, Any]:
    jobs = res["run_jobs"]
    lanes = Counter(j["lane"] for j in jobs)
    rejected = [m for m in res["mapping"] if m["requisition_id"] is None]
    per_dim = {DIM_LABEL[d]: {v: sum(1 for j in jobs if j["dims"][d]["verdict"] == v) for v in ("FAIL", "UNKNOWN", "PASS")}
               for d in ALL_DIMS}
    jobs_in = len(res["records"])
    shortlist = len([j for j in jobs if j["lane"] == "SHORTLIST" and j["jd_status"] == "JD_COMPLETE"])
    review = lanes["REVIEW"] + len([j for j in jobs if j["lane"] == "SHORTLIST" and j["jd_status"] != "JD_COMPLETE"])
    viable = shortlist + review
    rate = viable / jobs_in if jobs_in else 0.0
    out = {
        "date": res["date"], "policy_version": res["policy_version"], "policy_sha256": res["policy_sha256"],
        "gate_e": "pending (Round 4 not yet measured)", "input": res["input_name"], "input_sha256": res["input_sha256"],
        "jobs_in": jobs_in, "rejected_records": len(rejected), "unique_jobs": len(jobs),
        "duplicates": res["duplicate_records"] + lanes["SUPPRESSED_DUPLICATE"],
        "duplicate_records_collapsed": res["duplicate_records"],
        "suppressed_duplicate_requisitions": lanes["SUPPRESSED_DUPLICATE"],
        "ambiguous_identity": sum(1 for j in jobs if j["identity_uncertain"]),
        "jd_missing": sum(1 for j in jobs if j["jd_status"] == "JD_MISSING"),
        "jd_truncated": sum(1 for j in jobs if j["jd_status"] == "JD_TRUNCATED"),
        "apply_url_missing": sum(1 for j in jobs if not j["application_url"]),
        "SHORTLIST": shortlist, "REVIEW": review, "PARKED": lanes["PARKED"], "EXCLUDED": lanes["EXCLUDED"],
        "SUPPRESSED_DUPLICATE": lanes["SUPPRESSED_DUPLICATE"],
        "shortlist_plus_review": viable,
        "queue_today": {"review_cap": res["review_cap"], "shortlist_pending": len(res["shortlist"]),
                        "review_shown": len(res["review_shown"]), "review_overflow": len(res["review_overflow"]),
                        "review_held_incomplete_jd": len(res["review_held"]),
                        "overflow_parked_today": len(res["overflow_parked_today"])},
        "per_dimension": per_dim,
        "observed_conversion_rate": round(rate, 4),
    }
    for t in TARGETS:
        out[f"gap_to_{t}"] = max(0, t - viable)
        out[f"estimated_source_jobs_for_{t}"] = math.ceil(t / rate) if rate else None
    out["below_25"] = viable < 25
    out["bottleneck"] = bottleneck(jobs, res)
    return out


def bottleneck(jobs: List[Dict[str, Any]], res: Dict[str, Any]) -> Dict[str, Any]:
    """The single largest observed cause of a job not reaching SHORTLIST (diagnostic only)."""
    causes: Counter = Counter()
    for j in jobs:
        if j["lane"] == "EXCLUDED":
            for d in DIMS:
                if j["dims"][d]["verdict"] == "FAIL":
                    causes[f"{DIM_LABEL[d]} FAIL"] += 1
            if j["dims"]["employment_relationship"]["verdict"] == "FAIL":
                causes["relationship FAIL"] += 1
        elif j["lane"] == "REVIEW":
            for d in DIMS:
                if j["dims"][d]["verdict"] == "UNKNOWN":
                    causes[f"{DIM_LABEL[d]} UNKNOWN"] += 1
        elif j["lane"] == "PARKED":
            causes[f"relevance {j['relevance']} (parked)"] += 1
        if j["jd_status"] == "JD_MISSING":
            causes["missing JD"] += 1
    dupes = res["duplicate_records"] + sum(1 for j in jobs if j["lane"] == "SUPPRESSED_DUPLICATE")
    if dupes:
        causes["duplicate suppression"] += dupes
    if not causes:
        return {"cause": None, "count": 0, "top": []}
    top = sorted(causes.items(), key=lambda kv: (-kv[1], kv[0]))
    return {"cause": top[0][0], "count": top[0][1], "top": [{"cause": c, "count": n} for c, n in top[:5]]}


# ----------------------------------------------------------------- digest

def _card(j: Dict[str, Any], extra: str = "") -> List[str]:
    verdicts = " · ".join(f"{DIM_LABEL[d]} {j['dims'][d]['verdict']}" for d in DIMS)
    lines = [f"### {j['title']} — {j['company'] or '(company not stated)'}  `{j['job_id']}`{extra}",
             f"- **Where / mode:** {j['location'] or '—'} / {j['work_mode'] or '—'}",
             f"- **Pay (as stated):** {j['compensation'] or '—'}",
             f"- **Relevance:** {j['relevance']} · **Newness:** {j['newness']} · **Experience:** {j['experience']}",
             f"- **Apply:** {j['application_url'] or 'apply_url_missing'}",
             f"- **Eligibility:** {verdicts}"]
    reasons = []
    for d in ALL_DIMS:
        v = j["dims"][d]
        if v["verdict"] != "PASS":
            why = v["note"] or ", ".join(v["flags"]) or v["rule_id"]
            reasons.append(f"{DIM_LABEL[d]} {v['verdict']} ({v['rule_id']}): {_one_line(why, 160)}")
    if j["jd_status"] != "JD_COMPLETE":
        reasons.append(f"{j['jd_status']}: the description is incomplete, verify before applying")
    if j["identity_uncertain"]:
        reasons.append("IDENTITY_UNCERTAIN: may be the same job as another listing (grouped card)")
    if reasons:
        lines.append("- **Why:** " + "; ".join(reasons))
    quotes = []
    for d in ALL_DIMS:
        if j["dims"][d]["verdict"] != "PASS":
            quotes += j["dims"][d]["quotes"][:1]
    quotes += j["relevance_quotes"][:1]
    for q in dict.fromkeys(quotes):
        lines.append(f"  > {_one_line(q)}")
    flags = [f for f in j["review_flags"]] + [f for f in j["info_flags"]]
    if flags:
        lines.append(f"- **Flags:** {', '.join(flags)}")
    return lines + [""]


def render_digest(res: Dict[str, Any], m: Dict[str, Any]) -> str:
    q = m["queue_today"]
    lines = [f"# JobOps digest — {res['date']}", "",
             f"- Input: `{res['input_name']}` (SHA-256 `{res['input_sha256']}`)",
             f"- Policy: {res['policy_version'].split('@')[1]}",
             f"- Policy SHA: {res['policy_sha256']}",
             "- Gate E: pending — Round 4 has not yet been measured",
             "- Nothing here applies, submits or contacts anyone. You decide and apply yourself.", "",
             "## Metrics", "",
             f"| jobs in | unique | duplicates | ambiguous identity | missing JD | truncated JD | no apply URL |",
             f"|---:|---:|---:|---:|---:|---:|---:|",
             f"| {m['jobs_in']} | {m['unique_jobs']} | {m['duplicates']} | {m['ambiguous_identity']} | {m['jd_missing']} | "
             f"{m['jd_truncated']} | {m['apply_url_missing']} |", "",
             "| SHORTLIST | REVIEW | PARKED | EXCLUDED | SHORTLIST + REVIEW | gap to 25 | gap to 30 |",
             "|---:|---:|---:|---:|---:|---:|---:|",
             f"| {m['SHORTLIST']} | {m['REVIEW']} | {m['PARKED']} | {m['EXCLUDED']} | {m['shortlist_plus_review']} | "
             f"{m['gap_to_25']} | {m['gap_to_30']} |", ""]
    if m["rejected_records"]:
        lines += [f"- **{m['rejected_records']} record(s) could not be used** (schema problems; see metrics.json).", ""]
    if m["below_25"]:
        est = m["estimated_source_jobs_for_25"]
        lines.append(f"- **Fewer than 25 viable candidates today ({m['shortlist_plus_review']}).** At today's observed "
                     f"conversion ({m['observed_conversion_rate']:.0%}) about {est if est else 'n/a'} source jobs would be "
                     "needed for 25. This is an estimate from one day, not a guarantee.")
    b = m["bottleneck"]
    if b["cause"]:
        lines.append(f"- **Largest bottleneck:** {b['cause']} ({b['count']} jobs). Diagnostic only; the policy is not "
                     "changed from one day's result.")
    lines += [f"- **Review queue:** {q['review_shown']} shown (cap {q['review_cap']}), {q['review_overflow']} overflow "
              f"carried to tomorrow, {q['overflow_parked_today']} parked today after 3 carry days (OR-88), "
              f"{q['review_held_incomplete_jd']} held for an incomplete JD.", ""]
    lines += ["## SHORTLIST", ""]
    lines += [ln for j in res["shortlist"] for ln in _card(j)] or ["_None today._", ""]
    lines += ["## REVIEW (shown today)", ""]
    lines += [ln for j in res["review_shown"] for ln in _card(j)] or ["_None today._", ""]
    if res["review_held"]:
        lines += ["## REVIEW — held from SHORTLIST (incomplete JD; outside the daily cap)", ""]
        lines += [ln for j in res["review_held"] for ln in _card(j)]
    if res["review_overflow"]:
        lines += ["## REVIEW overflow (carried to tomorrow)", ""]
        lines += [f"- `{j['job_id']}` {j['title']} — {j['company']} ({j['relevance']}, {j['newness']})"
                  for j in res["review_overflow"]] + [""]
    parked = [j for j in res["run_jobs"] if j["lane"] == "PARKED"]
    lines += [f"## PARKED ({len(parked)} from this export, {q['overflow_parked_today']} by overflow today)", ""]
    lines += [f"- `{j['job_id']}` {j['title']} — {j['company']} (relevance {j['relevance']})" for j in parked]
    lines += [f"- `{j['job_id']}` {j['title']} — {j['company']} (REVIEW item parked after 3 carry days, OR-88)"
              for j in res["overflow_parked_today"]]
    lines += ["", f"## EXCLUDED ({m['EXCLUDED']})", "",
              "Listed with failing dimension and evidence in `excluded.csv`. Audit them for false exclusions.", ""]
    return "\n".join(lines).rstrip() + "\n"


# --------------------------------------------------------------- csv / jd

def excluded_rows(res: Dict[str, Any]) -> List[List[Any]]:
    rows = [["job_id", "title", "company", "url", "failing_dimension", "verdict", "reason", "evidence"]]
    for j in res["run_jobs"]:
        if j["lane"] != "EXCLUDED":
            continue
        for d in ALL_DIMS:
            v = j["dims"][d]
            if v["verdict"] == "FAIL":
                rows.append([j["job_id"], j["title"], j["company"], j["application_url"] or "apply_url_missing",
                             DIM_LABEL[d], "FAIL", _one_line(f"{v['rule_id']}: {v['note'] or ', '.join(v['flags'])}", 300),
                             " | ".join(_one_line(x, 300) for x in v["quotes"][:2])])
    return rows


def decision_rows(res: Dict[str, Any]) -> List[List[Any]]:
    rows = [["job_id", "applied", "skipped", "skip_reason", "notes"]]
    seen = set()
    for j in res["shortlist"] + res["review_shown"] + res["review_held"] + res["review_overflow"]:
        if j["job_id"] not in seen:
            seen.add(j["job_id"])
            rows.append([j["job_id"], "", "", "", ""])
    return rows


def jd_file(j: Dict[str, Any], policy_version: str) -> str:
    flags = j["review_flags"] + j["info_flags"] + ([j["jd_status"]] if j["jd_status"] != "JD_COMPLETE" else [])
    head = [f"Title: {j['title']}", f"Company: {j['company'] or ''}", f"Location: {j['location'] or ''}",
            f"Application URL: {j['application_url'] or 'apply_url_missing'}", f"Policy: {policy_version}",
            f"Flags: {', '.join(flags) if flags else 'none'}", "", "-" * 60, ""]
    body = j["jd_text"] if j["jd_text"] else "JD_MISSING: the export carried no description for this job."
    return "\n".join(head) + body.rstrip() + "\n"


def _has_human_input(path: Path) -> bool:
    with open(path, newline="", encoding="utf-8") as f:
        return any(any((row.get(k) or "").strip() for k in ("applied", "skipped", "skip_reason", "notes"))
                   for row in csv.DictReader(f))


def write_outputs(res: Dict[str, Any], out: Path) -> Path:
    day_dir = Path(out) / res["date"]
    (day_dir / "jd").mkdir(parents=True, exist_ok=True)
    m = metrics(res)
    (day_dir / "metrics.json").write_text(json.dumps(m, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (day_dir / "digest.md").write_text(render_digest(res, m), encoding="utf-8")
    (day_dir / "excluded.csv").write_text(_csv(excluded_rows(res)), encoding="utf-8")
    decisions = day_dir / "decisions.csv"
    sheet = _csv(decision_rows(res))
    if decisions.exists() and _has_human_input(decisions):
        # Never overwrite a sheet the human has started filling in; the fresh blank sheet goes alongside it.
        (day_dir / "decisions.pending.csv").write_text(sheet, encoding="utf-8")
    else:
        decisions.write_text(sheet, encoding="utf-8")
    for j in res["shortlist"] + res["review_shown"] + res["review_held"] + res["review_overflow"]:
        (day_dir / "jd" / f"{j['job_id']}.txt").write_text(jd_file(j, res["policy_version"]), encoding="utf-8")
    return day_dir
