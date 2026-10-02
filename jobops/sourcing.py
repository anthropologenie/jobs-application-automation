"""
P9 `jobops source`: one manually triggered, offline run over a downloaded export.

    export -> normalise -> EvaluationService.ingest (identity, dedupe, newness, evidence, policy, relevance)
           -> evaluation.queue.plan_day (cap, carry, OR-88) -> digest / CSVs / metrics / JD files

The engine is consumed, never re-implemented: every verdict, lane, newness state and queue decision
comes from evaluation/*. This module only maps the export in and renders the result out.

State lives in <out>/state/ (a v2 SQLite store plus a JSON run ledger), never in data/jobs-tracker.db.
Idempotence: a (date, input SHA) pair already in the ledger is not re-ingested, and plan_day is
idempotent for a day, so re-running the same input on the same date reproduces the same outputs.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from evaluation.policy_loader import POLICY_PATHS, load_policy_version, sha256_file
from evaluation.queue import plan_day
from evaluation.service import EvaluationService
from store import repository as repo
from store.db import connect
from store.migrate import MigrationRunner

from . import normalize

STATE_DB = "jobops-p9.sqlite"
LEDGER = "runs.json"
DIMS = ("geography", "compensation", "employment_type", "employer_type", "language")
ALL_DIMS = DIMS + ("employment_relationship",)


class RunRefused(RuntimeError):
    """The run would make the state inconsistent (e.g. an earlier date after a later one)."""


def policy_version(arg: str) -> str:
    version = arg if arg.startswith("jobops-policy@") else f"jobops-policy@{arg}"
    if version not in POLICY_PATHS:
        raise RunRefused(f"unsupported policy {arg!r}; supported: {sorted(POLICY_PATHS)}")
    return version


# ------------------------------------------------------------ cap adapter

class _CapPolicy:
    """Read-only view of the policy whose only difference is the daily REVIEW presentation cap."""

    def __init__(self, policy, cap: int):
        self._policy, self._cap = policy, cap

    def resolve(self, operand):
        if operand == "$review_daily_cap":
            return self._cap
        return self._policy.resolve(operand)

    def __getattr__(self, name):
        return getattr(self._policy, name)


class _CapService:
    """plan_day sees the cap override; evaluations still run on the real, unmodified policy."""

    def __init__(self, service, cap: int):
        self._service = service
        self.conn = service.conn
        self.policy = _CapPolicy(service.policy, cap)

    def current_evaluation(self, requisition_id):
        return self._service.current_evaluation(requisition_id)


def plan(service, day: str, cap: Optional[int]) -> Dict[str, Any]:
    if cap is None:
        return plan_day(service, day)
    return plan_day(_CapService(service, cap), day)


# ------------------------------------------------------------------ state

def open_state(out: Path, version: str):
    state = Path(out) / "state"
    state.mkdir(parents=True, exist_ok=True)
    conn = connect(state / STATE_DB)
    MigrationRunner(conn).apply_pending()
    return conn, state


def load_ledger(state: Path) -> Dict[str, Any]:
    path = state / LEDGER
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"runs": []}


def save_ledger(state: Path, ledger: Dict[str, Any]) -> None:
    (state / LEDGER).write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# -------------------------------------------------------------------- run

def run_source(input_path: Path, version: str, out: Path, day: str, cap: Optional[int]) -> Dict[str, Any]:
    input_path = Path(input_path)
    input_sha = normalize.file_sha256(input_path)
    records = normalize.map_schema(normalize.read_export(input_path), input_path.name)
    policy = load_policy_version(version)
    conn, state = open_state(out, version)
    try:
        ledger = load_ledger(state)
        if ledger.get("policy_version") and ledger["policy_version"] != version:
            raise RunRefused(f"state at {state} was built with {ledger['policy_version']}; use a new --out for {version}")
        later = [r["date"] for r in ledger["runs"] if r["date"] > day]
        if later:
            raise RunRefused(f"state already has a run on {max(later)}; runs must be in date order (got {day})")
        run_id = f"p9-{day}-{input_sha[:12]}"
        service = EvaluationService(conn, policy, clock=lambda: day)
        already = any(r["run_id"] == run_id for r in ledger["runs"])
        mapping: List[Dict[str, Any]] = []
        if already:
            mapping = next(r for r in ledger["runs"] if r["run_id"] == run_id)["records"]
        else:
            for rec in records:
                if rec["problems"]:
                    mapping.append({"index": rec["index"], "requisition_id": None, "problems": rec["problems"]})
                    continue
                res = service.ingest(normalize.to_observation(rec, run_id=run_id, day=day))
                mapping.append({"index": rec["index"], "requisition_id": res["requisition_id"],
                                "attached_to": res["attached_to"], "created": res["created"], "problems": []})
            ledger["policy_version"] = version
            ledger["runs"].append({"date": day, "run_id": run_id, "input_sha256": input_sha,
                                   "input_name": input_path.name, "records": mapping})
            save_ledger(state, ledger)
        result = collect(service, policy, records, mapping, day, cap)
        result.update(input_name=input_path.name, input_sha256=input_sha, run_id=run_id, reran=already,
                      policy_version=version, policy_sha256=sha256_file(POLICY_PATHS[version]), date=day,
                      review_cap=cap if cap is not None else policy.resolve("$review_daily_cap"))
        return result
    finally:
        conn.close()


# ---------------------------------------------------------------- collect

def _richest_observation(conn, rid: str) -> Dict[str, Any]:
    family = [rid] + [r[0] for r in conn.execute(
        "SELECT requisition_id FROM requisition WHERE duplicate_of=? ORDER BY requisition_id", (rid,))]
    rank = {"FULL_JD": 0, "PARTIAL": 1, "SEARCH_ONLY": 2}
    obs = repo.observations_for(conn, family)
    return sorted(obs, key=lambda o: (rank[o["completeness"]], -o["seq"]))[0]


def _quotes(conn, ids: List[str]) -> List[str]:
    if not ids:
        return []
    marks = ",".join("?" for _ in ids)
    rows = conn.execute(f"SELECT quoted_span FROM evidence WHERE evidence_id IN ({marks}) ORDER BY ordinal", ids)
    out = []
    for (q,) in rows:
        if q and q not in out:
            out.append(q)
    return out


def _rule_text(rule: Dict[str, Any]) -> str:
    """The rule's own note, else its condition as written in the policy (no paraphrase is invented)."""
    if rule.get("note"):
        return rule["note"]
    parts = []
    for k, v in rule.get("when", {}).items():
        if isinstance(v, dict):
            parts += [f"{k} {op} {val}" for op, val in v.items()]
        else:
            parts.append(f"{k}={v}")
    return ", ".join(parts)


def job_view(service, policy, rid: str, jd_status_of: Dict[str, str]) -> Dict[str, Any]:
    conn = service.conn
    ev = service.current_evaluation(rid)
    r = ev["result"]
    req = repo.get_requisition(conn, rid)
    obs = _richest_observation(conn, rid)
    rules = {x["rule_id"]: x for table in policy.doc["rules"].values() for x in table}
    dims = {}
    for d in ALL_DIMS:
        v = r["eligibility_dimensions"][d]
        ids = r["selected_evidence"].get(d, {}).get("evidence_ids", [])
        dims[d] = {"verdict": v["verdict"], "rule_id": v["rule_id"], "flags": v["flags"],
                   "note": _rule_text(rules.get(v["rule_id"], {})), "quotes": _quotes(conn, ids)}
    jd = jd_status_of.get(rid) or {"FULL_JD": "JD_COMPLETE", "PARTIAL": "JD_TRUNCATED",
                                   "SEARCH_ONLY": "JD_MISSING"}[obs["completeness"]]
    app_url = obs.get("apply_url") or obs.get("source_url")
    return {
        "job_id": rid, "title": obs.get("raw_title"), "company": obs.get("raw_company"),
        "location": obs.get("raw_location"), "work_mode": obs.get("raw_work_mode"),
        "compensation": obs.get("raw_salary"), "employment_type": obs.get("raw_employment_type"),
        "application_url": app_url, "jd_text": obs.get("raw_text"), "jd_status": jd,
        "lane": ev["queue_lane"], "relevance": r["relevance"]["relevance_label"],
        "relevance_terms": r["relevance"].get("specific_terms", []),
        "relevance_quotes": [s["quoted_span"] for s in r["relevance"].get("evidence_spans", [])][:2],
        "experience": r["relevance"].get("experience_signal"), "newness": req["newness_state"],
        "dims": dims, "overall": r["eligibility_overall"],
        "review_flags": r["review_flags"],
        "info_flags": sorted(f for f in r["flags"] if f in policy.info_flags),
        "identity_uncertain": "IDENTITY_UNCERTAIN" in r["flags"],
        "duplicate_of": req["duplicate_of"],
    }


_REL = ["STRONG", "MODERATE", "WEAK", "NOT_ASSESSED"]
_NEW = ["NEW", "UPDATED", "SEEN_BEFORE"]


def _sort(jobs):
    return sorted(jobs, key=lambda j: (_REL.index(j["relevance"]) if j["relevance"] in _REL else 9,
                                      _NEW.index(j["newness"]) if j["newness"] in _NEW else 9, j["job_id"]))


def collect(service, policy, records, mapping, day: str, cap: Optional[int]) -> Dict[str, Any]:
    conn = service.conn
    by_index = {r["index"]: r for r in records}
    jd_status_of: Dict[str, str] = {}
    run_rids: List[str] = []
    duplicate_records = 0
    for m in mapping:
        rid = m["requisition_id"]
        if rid is None:
            continue
        status = by_index[m["index"]]["jd_status"]
        # A requisition is as complete as its best sighting in this run.
        order = ["JD_COMPLETE", "JD_TRUNCATED", "JD_MISSING"]
        if rid not in jd_status_of or order.index(status) < order.index(jd_status_of[rid]):
            jd_status_of[rid] = status
        if rid in run_rids:
            duplicate_records += 1
        else:
            run_rids.append(rid)
    planned = plan(service, day, cap)
    decided = repo.decided_requisitions(conn)
    views: Dict[str, Dict[str, Any]] = {}

    def view(rid):
        if rid not in views:
            views[rid] = job_view(service, policy, rid, jd_status_of)
        return views[rid]

    run_jobs = [view(rid) for rid in run_rids]
    # SHORTLIST: uncapped, every undecided requisition the engine shortlists. A shortlisted job whose JD is
    # missing or truncated is held in REVIEW (P9 §13: incomplete evidence never shortlists); its verdicts
    # and lane are not changed.
    shortlist, held = [], []
    for item in planned["lanes"]["SHORTLIST"]:
        if item["requisition_id"] in decided:
            continue
        v = view(item["requisition_id"])
        (held if v["jd_status"] != "JD_COMPLETE" else shortlist).append(v)
    unit_ids = lambda units: [m for u in units for m in u["member_requisition_ids"]]  # noqa: E731
    # P10 tiering (presentation only). plan_day above has already run unchanged and persisted carry / OR-88
    # state for its own surfaced set; here today's pending REVIEW pool (its surfaced + carried units, never its
    # parked ones) is re-ordered T1 -> T2 -> T3 -> T4 and the first `cap` units are shown. Lanes, verdicts and
    # queue state are not touched; each unit records what plan_day did with it so the digest can say so.
    from .tiers import annotate, order_units
    for rid in run_rids:
        v = view(rid)
        if v["lane"] == "REVIEW" or (v["lane"] == "SHORTLIST" and v["jd_status"] != "JD_COMPLETE"):
            annotate(v)
    for v in held:
        annotate(v)
    pool = [{"unit_id": u["requisition_id"], "engine": "surfaced", "carry_days": None,
             "members": [annotate(view(m)) for m in u["member_requisition_ids"]]} for u in planned["review_today"]]
    pool += [{"unit_id": u["requisition_id"], "engine": "carried", "carry_days": u.get("carry_days"),
              "members": [annotate(view(m)) for m in u["member_requisition_ids"]]} for u in planned["review_carried"]]
    units = order_units(pool)
    cap_n = planned["cap"]
    units_shown, units_overflow = units[:cap_n], units[cap_n:]
    review_shown = [m for u in units_shown for m in u["members"]]
    review_overflow = [m for u in units_overflow for m in u["members"]]
    parked_today = [view(m) for m in unit_ids([u for u in planned["lanes"]["PARKED"]
                                               if u.get("parked_by") == "overflow" and u.get("parked_on") == day])]
    parked_today += [view(m) for m in unit_ids(planned["overflow_parked_today"])
                     if m not in {p["job_id"] for p in parked_today}]
    parked_today = sorted(parked_today, key=lambda j: j["job_id"])
    return {"records": records, "mapping": mapping, "run_jobs": run_jobs, "duplicate_records": duplicate_records,
            "shortlist": _sort(shortlist), "review_held": _sort(held), "review_shown": review_shown,
            "review_overflow": review_overflow, "overflow_parked_today": parked_today,
            "review_units_shown": units_shown, "review_units_overflow": units_overflow,
            "engine_review_today": unit_ids(planned["review_today"]),
            "engine_review_carried": unit_ids(planned["review_carried"]),
            "plan_cap": planned["cap"]}
