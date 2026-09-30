"""Markdown rendering of queue plans. Output is a string; nothing is sent anywhere."""

from typing import Any, Dict, List


def _row(it: Dict[str, Any]) -> str:
    ref = it["requisition_id"]
    if it.get("group_id"):
        ref = f"{it['group_id']} (group: {', '.join(it['member_requisition_ids'])})"
    return (f"| {ref} | {it['relevance']} | {it['newness']} | "
            f"{it['work_arrangement']} | {it['compensation_band']} | {it.get('carry_days', '')} |")


def _table(items: List[Dict[str, Any]]) -> List[str]:
    lines = ["| Requisition | Relevance | Newness | Work arrangement | Compensation | Carry days |",
             "|---|---|---|---|---|---|"]
    return lines + [_row(i) for i in items] if items else ["_none_"]


def render_daily(plan: Dict[str, Any]) -> str:
    out = [f"# JobOps daily digest — {plan['day']}", "",
           "Final application submission is always done by the human. This digest only lists.", ""]
    if plan.get("fx_warnings"):
        out += ["> **FX freshness warning:** the FX snapshot used for these items is more than 7 days old "
                "(still usable up to 14 days). Update the owner-maintained FX table.", ""]
        out += [f"> - {w['requisition_id']}: snapshot {w['fx_snapshot_date']} ({w['fx_age_days']} days old)"
                for w in plan["fx_warnings"]] + [""]
    for title, items in (("Shortlist", plan["lanes"]["SHORTLIST"]),
                         (f"Review today (cap {plan['cap']})", plan["review_today"]),
                         ("Review carried forward", plan["review_carried"]),
                         ("Moved to PARKED by overflow today", plan["overflow_parked_today"])):
        out += [f"## {title} ({len(items)})", ""] + _table(items) + [""]
    out += [f"Excluded: {len(plan['lanes']['EXCLUDED'])} · Suppressed duplicates: "
            f"{len(plan['lanes']['SUPPRESSED_DUPLICATE'])} · Parked: {len(plan['lanes']['PARKED'])}", ""]
    return "\n".join(out)


def render_parked(plan: Dict[str, Any]) -> str:
    items = plan["lanes"]["PARKED"]
    return "\n".join([f"# JobOps weekly PARKED digest — {plan['day']}", ""] + _table(items) + [""])
