"""
Daily queue planning (Phase B §22-§23; P1a OI-046, OI-040).

Lanes come from current evaluations; this module only applies capacity and
presentation:

  * SHORTLIST is uncapped.
  * REVIEW is capped at review_daily_cap per day (10), ordered by the policy's
    categorical keys: relevance, newness, evidence completeness, preference
    (REMOTE > BENGALURU_HYBRID, then compensation band, then employer), then
    first_seen_at and requisition_id. No composite score.
  * Grouping (policy queue.group_identity_uncertain_review, 0.2.1): REVIEW
    requisitions flagged IDENTITY_UNCERTAIN and linked by a PROBABLE_DUPLICATE
    identity link are presented as ONE review item with a group_id and member
    ids, and consume ONE cap slot. This is presentation only: no requisition,
    observation, evidence or evaluation is merged or dropped.
  * Items not surfaced carry forward; each planning day not surfaced adds one
    carry day. Beyond review_carry_days, a non-STRONG item moves to PARKED
    (overflow) and appears in the weekly PARKED digest. STRONG relevance is
    exempt and keeps carrying. Nothing is discarded.
  * Requisitions with a human review decision leave the pending REVIEW pool.
  * Legacy scraped_jobs rows are not requisitions and never appear here.
  * FX freshness (0.2.1): any item whose FX snapshot is more than
    fx_digest_warning_age_days old (and not stale) is listed in fx_warnings.
"""

from datetime import date
from typing import Any, Dict, List

from store import repository as repo


def order_key(item: Dict[str, Any], policy) -> tuple:
    key = []
    for spec in policy.section("queue")["ordering"]:
        name, order = spec["key"], spec["order"]
        value = item[name]
        if isinstance(order, list):
            key.append(order.index(value) if value in order else len(order))
        else:
            key.append(value)
    return tuple(key)


def _item(req: Dict[str, Any], evaluation: Dict[str, Any]) -> Dict[str, Any]:
    r = evaluation["result"]
    pref = r.get("preference_attributes", {})
    return {"requisition_id": req["requisition_id"],
            "relevance": r["relevance"]["relevance_label"],
            "newness": req["newness_state"],
            "evidence_completeness": r.get("evidence_completeness", {}).get("unknown_dimension_count", 0),
            "work_arrangement": pref.get("work_arrangement", "UNKNOWN"),
            "compensation_band": pref.get("compensation_band", "UNKNOWN"),
            "employer_preference": pref.get("employer_preference", "UNKNOWN"),
            "first_seen_at": req["first_seen_at"],
            "lane": evaluation["queue_lane"],
            "flags": list(r.get("flags", [])),
            "fx_freshness": r.get("fx_freshness"),
            "evaluation_id": evaluation["evaluation_id"],
            "group_id": None,
            "member_requisition_ids": [req["requisition_id"]]}


def _groups(conn, pending: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
    """Connected components of IDENTITY_UNCERTAIN pending items over PROBABLE_DUPLICATE links."""
    by_id = {it["requisition_id"]: it for it in pending}
    uncertain = {rid for rid, it in by_id.items() if "IDENTITY_UNCERTAIN" in it["flags"]}
    parent = {rid: rid for rid in by_id}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in conn.execute("SELECT requisition_a, requisition_b FROM identity_link "
                             "WHERE outcome='PROBABLE_DUPLICATE' ORDER BY link_id"):
        if a in uncertain and b in uncertain:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
    comps: Dict[str, List[Dict[str, Any]]] = {}
    for rid in sorted(by_id):
        comps.setdefault(find(rid), []).append(by_id[rid])
    return list(comps.values())


def _unit(members: List[Dict[str, Any]], policy) -> Dict[str, Any]:
    """One review unit. A group takes the ordering attributes of its best-ranked member."""
    members = sorted(members, key=lambda it: order_key(it, policy))
    if len(members) == 1:
        return {**members[0], "_members": members}
    head = members[0]
    ids = sorted(m["requisition_id"] for m in members)
    return {**head, "group_id": "grp_" + ids[0], "member_requisition_ids": ids,
            "requisition_id": "grp_" + ids[0], "_members": members,
            "relevance": head["relevance"]}


def _fx_warnings(items: List[Dict[str, Any]], day: str, policy) -> List[Dict[str, Any]]:
    warn = policy.params.get("fx_digest_warning_age_days")
    limit = policy.params.get("fx_max_age_days")
    if warn is None:
        return []
    out = []
    for it in items:
        fx = it.get("fx_freshness")
        if not fx:
            continue
        age = (date.fromisoformat(day) - date.fromisoformat(fx["fx_snapshot_date"][:10])).days
        if age > warn and (limit is None or age <= limit):
            out.append({"requisition_id": it["requisition_id"], "fx_snapshot_date": fx["fx_snapshot_date"],
                        "fx_age_days": age})
    return out


def plan_day(service, day: str) -> Dict[str, Any]:
    """Plan one day's queue. Persists carry state; deterministic for a given DB state and day."""
    policy = service.policy
    qcfg = policy.section("queue")
    cap = policy.resolve(qcfg["review_daily_cap"])
    carry_limit = policy.resolve(qcfg["carry_days"])
    strong_exempt = qcfg["strong_relevance_exempt_from_overflow_parking"]
    grouping = bool(qcfg.get("group_identity_uncertain_review"))
    decided = repo.decided_requisitions(service.conn)
    lanes: Dict[str, List[Dict[str, Any]]] = {k: [] for k in
                                             ("SHORTLIST", "REVIEW", "PARKED", "EXCLUDED", "SUPPRESSED_DUPLICATE")}
    pending: List[Dict[str, Any]] = []
    all_items: List[Dict[str, Any]] = []
    for req in repo.requisitions(service.conn):
        ev = service.current_evaluation(req["requisition_id"])
        item = _item(req, ev)
        all_items.append(item)
        state = repo.queue_state(service.conn, req["requisition_id"])
        if item["lane"] == "REVIEW":
            if req["requisition_id"] in decided:
                continue
            if state["overflow_parked_on"]:
                lanes["PARKED"].append({**item, "parked_by": "overflow", "parked_on": state["overflow_parked_on"]})
                continue
            pending.append({**item, "_state": state})
        else:
            lanes[item["lane"]].append(item)

    groups = _groups(service.conn, pending) if grouping else [[it] for it in pending]
    units = sorted((_unit(g, policy) for g in groups), key=lambda u: order_key(u, policy))
    surfaced, carried, overflow = units[:cap], [], []
    service.conn.execute("BEGIN IMMEDIATE")
    try:
        for unit in surfaced:
            for m in unit["_members"]:
                st = m.pop("_state")
                st.update(first_review_day=st["first_review_day"] or day, last_surfaced_day=day, last_planned_day=day)
                repo.save_queue_state(service.conn, st)
            lanes["REVIEW"].append(_public(unit))
        for unit in units[cap:]:
            members = unit["_members"]
            unit_strong = any(m["relevance"] == "STRONG" for m in members)
            park = False
            carry_days = 0
            for m in members:
                st = m["_state"]
                if st["last_planned_day"] != day:
                    st["carry_days"] += 1
                st.update(first_review_day=st["first_review_day"] or day, last_planned_day=day)
                carry_days = max(carry_days, st["carry_days"])
            if carry_days > carry_limit and not (strong_exempt and unit_strong):
                park = True
            for m in members:
                st = m.pop("_state")
                if park:
                    st["overflow_parked_on"] = day
                repo.save_queue_state(service.conn, st)
            public = {**_public(unit), "carry_days": carry_days}
            if park:
                public["parked_by"] = "overflow"
                overflow.append(public)
                lanes["PARKED"].append(public)
            else:
                carried.append(public)
        service.conn.execute("COMMIT")
    except Exception:
        service.conn.execute("ROLLBACK")
        raise
    return {"day": day, "cap": cap, "lanes": lanes, "review_today": lanes["REVIEW"],
            "review_carried": carried, "overflow_parked_today": overflow,
            "fx_warnings": _fx_warnings(all_items, day, policy), "policy_version": policy.version}


def _public(unit: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: v for k, v in unit.items() if not k.startswith("_")}
    if len(unit["_members"]) > 1:
        out["members"] = [{k: v for k, v in m.items() if not k.startswith("_")} for m in unit["_members"]]
    return out
