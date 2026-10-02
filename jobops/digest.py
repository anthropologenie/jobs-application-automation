"""
P9 / P10 outputs for one run: <out>/<date>/{digest.md, excluded.csv, decisions.csv, metrics.json, jd/<job_id>.txt}.

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
from .tiers import TIER_LABEL, TIERS, count_by_tier, largest_blocker

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
    }
    # P9 counts kept for continuity. SHORTLIST + REVIEW is NOT an estimate of actionable supply (P10 §20); the
    # P9 source-jobs estimate built on it is replaced by the READY-ISH estimate below.
    for t in TARGETS:
        out[f"gap_to_{t}"] = max(0, t - viable)
    out["below_25"] = viable < 25
    out["shortlist_plus_review_note"] = "P9 count only; not an estimate of immediately actionable supply"
    out.update(tier_metrics(res, jobs, shortlist, jobs_in))
    out["bottleneck"] = bottleneck(jobs, res)
    out["excluded_by_dimension"], out["excluded_by_rule"] = excluded_by_dimension(res)
    return out


def review_population(res: Dict[str, Any]) -> List[Dict[str, Any]]:
    """This export's REVIEW jobs as counted by the REVIEW metric: REVIEW lane + SHORTLIST held for an incomplete JD."""
    return [j for j in res["run_jobs"]
            if j["lane"] == "REVIEW" or (j["lane"] == "SHORTLIST" and j["jd_status"] != "JD_COMPLETE")]


def tier_metrics(res: Dict[str, Any], jobs, shortlist: int, jobs_in: int) -> Dict[str, Any]:
    review = review_population(res)
    tiers = count_by_tier(review)
    ready = shortlist + tiers["T1"] + tiers["T2"]
    rate = ready / jobs_in if jobs_in else 0.0
    out: Dict[str, Any] = {"review_tiers": tiers, "READY_ISH": ready,
                           "ready_ish_definition": "SHORTLIST + T1 + T2 (diagnostic presentation metric; "
                                                   "not SHORTLIST, not 'ready to apply')",
                           "ready_ish_conversion_rate": round(rate, 4), "ready_ish_below_25": ready < 25}
    for t in TARGETS:
        out[f"ready_ish_gap_to_{t}"] = max(0, t - ready)
        # Illustrative one-day estimate; not an application-supply forecast.
        out[f"illustrative_source_jobs_for_{t}_ready_ish"] = math.ceil(t / rate) if ready else None
    out["largest_blocker_outside_ready_ish"] = largest_blocker([j for j in review if j["tier"] in ("T3", "T4")])
    out["largest_blocker_in_review"] = largest_blocker(review)
    units_shown, units_over = res["review_units_shown"], res["review_units_overflow"]
    shown_ids = {m["job_id"] for u in units_shown for m in u["members"]}
    over_ids = {m["job_id"] for u in units_over for m in u["members"]}
    q = {"shown_by_tier": count_by_tier([m for u in units_shown for m in u["members"]]),
         "overflow_by_tier": count_by_tier([m for u in units_over for m in u["members"]]),
         "shown_units": len(units_shown), "overflow_units": len(units_over),
         # Divergence between the tiered presentation and plan_day's own surfaced set (OR-65 carry counting).
         "engine_surfaced_not_shown": len(set(res["engine_review_today"]) & over_ids),
         "engine_carried_but_shown": len(set(res["engine_review_carried"]) & shown_ids)}
    out["review_queue_tiers"] = q
    return out


def excluded_by_dimension(res: Dict[str, Any]):
    """Counts from the excluded.csv rows: one row per failing dimension of an EXCLUDED job (a job can fail several)."""
    rows = excluded_rows(res)[1:]
    by_dim = Counter(r[4] for r in rows)
    by_rule = Counter(r[6].split(":", 1)[0] for r in rows)
    return ({DIM_LABEL[d]: by_dim[DIM_LABEL[d]] for d in ALL_DIMS},
            {k: by_rule[k] for k in sorted(by_rule)})


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
    # "not stated" is a display statement only; the verdicts below are the engine's.
    lines = [f"### {j['title']} — {j['company'] or '(company not stated)'}  `{j['job_id']}`{extra}",
             f"- **Where:** {j['location'] or 'not stated'} · **Mode:** {j['work_mode'] or 'not stated'}",
             f"- **Pay:** {j['compensation'] or 'not stated'}",
             f"- **Relevance:** {j['relevance']} · **Newness:** {j['newness']} · **Experience:** {j['experience']}"]
    if j.get("tier"):
        lines += [f"- **Tier:** {TIER_LABEL[j['tier']]}",
                  f"- **Blockers:** {'; '.join(j['blockers']) if j['blockers'] else 'none recorded'}"]
    lines += [f"- **Apply:** {j['application_url'] or 'apply_url_missing'}",
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


def _engine_note(unit: Dict[str, Any]) -> str:
    if unit["engine"] == "carried":
        return f"engine queue: carried (carry day {unit['carry_days']}; OR-65 / OR-88 count it as not surfaced)"
    return "engine queue: surfaced today (no carry day added)"


def _short_engine(unit: Dict[str, Any]) -> str:
    return "engine: surfaced" if unit["engine"] == "surfaced" else f"engine: carried, day {unit['carry_days']}"


def _unit_cards(unit: Dict[str, Any]) -> List[str]:
    lines = []
    if unit["engine"] == "carried":
        lines += [f"_{_engine_note(unit)}_", ""]
    for j in unit["members"]:
        lines += _card(j)
    return lines


def _tier_table(counts: Dict[str, int]) -> List[str]:
    return (["| Tier | Count |", "|------|------:|"]
            + [f"| {TIER_LABEL[t]} | {counts[t]} |" for t in TIERS] + [""])


def render_digest(res: Dict[str, Any], m: Dict[str, Any]) -> str:
    q = m["queue_today"]
    qt = m["review_queue_tiers"]
    tiers = m["review_tiers"]
    lines = [f"# JobOps digest — {res['date']}", "",
             f"- Input: `{res['input_name']}` (SHA-256 `{res['input_sha256']}`)",
             f"- Policy: {res['policy_version'].split('@')[1]}",
             f"- Policy SHA: {res['policy_sha256']}",
             "- Gate E: pending — Round 4 has not yet been measured",
             "- Nothing here applies, submits or contacts anyone. You decide and apply yourself.", "",
             f"REVIEW tiers for this export's {m['REVIEW']} REVIEW jobs (presentation only; verdicts and lanes "
             "are unchanged):", ""]
    lines += _tier_table(tiers)
    lines += ["## Metrics", "",
              f"| jobs in | unique | duplicates | ambiguous identity | missing JD | truncated JD | no apply URL |",
              f"|---:|---:|---:|---:|---:|---:|---:|",
              f"| {m['jobs_in']} | {m['unique_jobs']} | {m['duplicates']} | {m['ambiguous_identity']} | {m['jd_missing']} | "
              f"{m['jd_truncated']} | {m['apply_url_missing']} |", "",
              "| SHORTLIST | REVIEW | PARKED | EXCLUDED |",
              "|---:|---:|---:|---:|",
              f"| {m['SHORTLIST']} | {m['REVIEW']} | {m['PARKED']} | {m['EXCLUDED']} |", "",
              "| SHORTLIST | T1 | T2 | T3 | T4 | READY-ISH |",
              "|---:|---:|---:|---:|---:|---:|",
              f"| {m['SHORTLIST']} | {tiers['T1']} | {tiers['T2']} | {tiers['T3']} | {tiers['T4']} | {m['READY_ISH']} |", "",
              "- **SHORTLIST:** actionable under the current policy without resolving an UNKNOWN.",
              "- **T1:** potentially actionable after resolving only employer-unclassified / pay-not-stated uncertainty.",
              "- **T2:** as T1, plus a STRETCH experience consideration.",
              "- **READY-ISH = SHORTLIST + T1 + T2.** A diagnostic presentation metric: the remaining uncertainty is "
              "narrow and named on each card. It is not SHORTLIST and not \"ready to apply\".",
              f"- SHORTLIST + REVIEW = {m['shortlist_plus_review']}: a P9 count, not an estimate of actionable supply.", ""]
    if m["rejected_records"]:
        lines += [f"- **{m['rejected_records']} record(s) could not be used** (schema problems; see metrics.json).", ""]
    if m["READY_ISH"]:
        lines.append(f"- **Illustrative one-day estimate — not an application-supply forecast.** Today "
                     f"{m['READY_ISH']} of {m['jobs_in']} source jobs were READY-ISH "
                     f"({m['ready_ish_conversion_rate']:.1%}); at that rate about "
                     f"{m['illustrative_source_jobs_for_25_ready_ish']} source jobs would give 25 READY-ISH and "
                     f"{m['illustrative_source_jobs_for_30_ready_ish']} would give 30.")
    else:
        lines.append("- **READY-ISH is 0 today**, so no source-volume estimate can be made.")
    if m["ready_ish_below_25"]:
        lb = m["largest_blocker_outside_ready_ish"]
        lines.append("- **READY-ISH is below 25.**" + (
            f" The largest blocker among T3 / T4 jobs is **{lb['blocker']}** ({lb['count']} jobs). More source volume "
            "alone does not remove this blocker." if lb else ""))
    lr = m["largest_blocker_in_review"]
    if lr:
        lines.append(f"- **Most frequent REVIEW blocker:** {lr['blocker']} ({lr['count']} jobs).")
    b = m["bottleneck"]
    if b["cause"]:
        lines.append(f"- **Largest bottleneck:** {b['cause']} ({b['count']} jobs). Diagnostic only. No policy change "
                     "is implied.")
    lines += [f"- **Review queue:** {q['review_shown']} shown in {qt['shown_units']} of {q['review_cap']} cap slots, "
              f"filled T1 → T2 → T3 → T4; {q['review_overflow']} in overflow (still REVIEW, carried to tomorrow); "
              f"{q['overflow_parked_today']} parked today after 3 carry days (OR-88); "
              f"{q['review_held_incomplete_jd']} held for an incomplete JD.", ""]
    if qt["engine_surfaced_not_shown"] or qt["engine_carried_but_shown"]:
        lines += [f"- **Engine queue note:** {qt['engine_carried_but_shown']} shown job(s) count as *carried* in the "
                  f"engine's queue, and {qt['engine_surfaced_not_shown']} overflow job(s) count as *surfaced* "
                  "(plan_day orders by its policy keys; tiers only change what is displayed). Carry days and OR-88 "
                  "parking follow the engine's count. See open item OI-057.", ""]
    lines += ["### Eligibility by dimension", "", "| dimension | PASS | UNKNOWN | FAIL |", "|---|---:|---:|---:|"]
    lines += [f"| {d} | {c['PASS']} | {c['UNKNOWN']} | {c['FAIL']} |" for d, c in m["per_dimension"].items()] + [""]
    lines += ["## SHORTLIST", ""]
    lines += [ln for j in res["shortlist"] for ln in _card(j)] or ["_None today._", ""]
    for t in TIERS:
        lines += [f"## REVIEW — {TIER_LABEL[t].replace(' — ', ' ', 1)}", ""]
        units = [u for u in res["review_units_shown"] if u["tier"] == t]
        lines += [ln for u in units for ln in _unit_cards(u)] or ["_None shown today._", ""]
    if res["review_held"]:
        lines += ["## REVIEW — held from SHORTLIST (incomplete JD; outside the daily cap)", ""]
        lines += [ln for j in res["review_held"] for ln in _card(j)]
    lines += ["## REVIEW — Overflow", "",
              "Still REVIEW: carried to tomorrow (a non-STRONG item carried three days is PARKED, OR-88). "
              "`engine:` is plan_day's own status for the item (surfaced today, or carried with its carry day).", "",
              "| Tier | Overflow |", "|------|------:|"]
    lines += [f"| {TIER_LABEL[t]} | {qt['overflow_by_tier'][t]} |" for t in TIERS] + [""]
    for u in res["review_units_overflow"]:
        for j in u["members"]:
            lines.append(f"- `{j['job_id']}` {j['title']} — {j['company']} ({j['tier']}; {j['relevance']}, "
                         f"{j['newness']}; {'; '.join(j['blockers']) or 'none recorded'}; {_short_engine(u)})")
    lines.append("")
    parked = [j for j in res["run_jobs"] if j["lane"] == "PARKED"]
    lines += [f"## PARKED ({len(parked)} from this export, {q['overflow_parked_today']} by overflow today)", ""]
    lines += [f"- `{j['job_id']}` {j['title']} — {j['company']} (relevance {j['relevance']})" for j in parked]
    lines += [f"- `{j['job_id']}` {j['title']} — {j['company']} (REVIEW item parked after 3 carry days, OR-88)"
              for j in res["overflow_parked_today"]]
    lines += ["", f"## EXCLUDED ({m['EXCLUDED']})", "",
              "Listed with failing dimension and evidence in `excluded.csv`. Audit them for false exclusions.", "",
              "## EXCLUDED by Dimension", "",
              "Rows of `excluded.csv`; a job failing several dimensions counts once per dimension.", "",
              "| dimension | jobs |", "|---|---:|"]
    lines += [f"| {d} | {n} |" for d, n in m["excluded_by_dimension"].items()]
    if m["excluded_by_rule"]:
        lines += ["", "| rule | jobs |", "|---|---:|"] + [f"| {r} | {n} |" for r, n in m["excluded_by_rule"].items()]
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
