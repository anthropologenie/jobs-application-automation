"""
Repository functions over the v2 schema. Callers own transactions.

Human-only writes (review decisions, application events) require actor='human'
explicitly and are additionally enforced by CHECK constraints. Nothing here
submits an application or contacts anyone.
"""

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _next(conn: sqlite3.Connection, table: str, id_col: str, prefix: str) -> str:
    n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] + 1
    while True:
        candidate = f"{prefix}{n:07d}"
        if not conn.execute(f"SELECT 1 FROM {table} WHERE {id_col}=?", (candidate,)).fetchone():
            return candidate
        n += 1


# ---------------------------------------------------------------- runs

def ensure_run(conn, run_id: str, started_at: Optional[str] = None) -> None:
    conn.execute("INSERT OR IGNORE INTO run (run_id, started_at) VALUES (?, ?)",
                 (run_id, started_at or now_iso()))


# ------------------------------------------------------------- companies

def upsert_company(conn, canonical_name: str, normalized_name: str) -> str:
    row = conn.execute("SELECT company_id FROM company WHERE normalized_name=?", (normalized_name,)).fetchone()
    if row:
        return row["company_id"]
    cid = _next(conn, "company", "company_id", "co_")
    ts = now_iso()
    conn.execute("INSERT INTO company VALUES (?,?,?,?,?,?)", (cid, canonical_name, normalized_name, None, ts, ts))
    return cid


def add_ats_identity(conn, company_id: str, ats_type: str, ats_slug: str, observation_id: Optional[str]) -> None:
    conn.execute("INSERT OR IGNORE INTO company_ats_identity (ats_type, ats_slug, company_id, discovered_via_observation_id) "
                 "VALUES (?,?,?,?)", (ats_type, ats_slug.lower(), company_id, observation_id))


def add_classification(conn, company_id: str, classification: str, basis: str, decided_by: str,
                       evidence: Optional[Dict[str, Any]] = None, decided_at: Optional[str] = None) -> str:
    if basis == "OWNER_CONFIRMED" and decided_by != "owner":
        raise ValueError("an OWNER_CONFIRMED classification must be decided_by='owner'")
    cid = _next(conn, "company_classification", "classification_id", "cls_")
    conn.execute("INSERT INTO company_classification VALUES (?,?,?,?,?,?,?,?)",
                 (cid, company_id, classification, basis, json.dumps(evidence or {}), decided_by,
                  decided_at or now_iso(), None))
    return cid


def classifications(conn, company_id: Optional[str]) -> List[Dict[str, Any]]:
    if not company_id:
        return []
    return [dict(r) for r in conn.execute(
        "SELECT * FROM company_classification WHERE company_id=? ORDER BY classification_id", (company_id,))]


# ---------------------------------------------------------- requisitions

def create_requisition(conn, **fields) -> str:
    rid = _next(conn, "requisition", "requisition_id", "req_")
    ts = now_iso()
    cols = {"requisition_id": rid, "created_at": ts, "updated_at": ts, **fields}
    conn.execute(f"INSERT INTO requisition ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})",
                 list(cols.values()))
    return rid


def update_requisition(conn, requisition_id: str, **fields) -> None:
    fields["updated_at"] = now_iso()
    sets = ",".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE requisition SET {sets} WHERE requisition_id=?", [*fields.values(), requisition_id])


def get_requisition(conn, requisition_id: str) -> Dict[str, Any]:
    row = conn.execute("SELECT * FROM requisition WHERE requisition_id=?", (requisition_id,)).fetchone()
    return dict(row) if row else None


def requisitions(conn) -> List[Dict[str, Any]]:
    return [dict(r) for r in conn.execute("SELECT * FROM requisition ORDER BY requisition_id")]


def find_by_keys(conn, keys: Iterable) -> Dict[str, List]:
    found: Dict[str, List] = {}
    for key_type, key_value in keys:
        row = conn.execute("SELECT requisition_id FROM requisition_key WHERE key_type=? AND key_value=?",
                           (key_type, key_value)).fetchone()
        if row:
            found.setdefault(row["requisition_id"], []).append((key_type, key_value))
    return found


def add_keys(conn, requisition_id: str, keys: Iterable) -> None:
    for key_type, key_value in keys:
        conn.execute("INSERT OR IGNORE INTO requisition_key VALUES (?,?,?)", (key_type, key_value, requisition_id))


def keys_of(conn, requisition_id: str) -> List:
    return [(r["key_type"], r["key_value"]) for r in conn.execute(
        "SELECT key_type, key_value FROM requisition_key WHERE requisition_id=?", (requisition_id,))]


def add_identity_link(conn, a: str, b: str, outcome: str, layer: str, reason: str) -> None:
    lid = _next(conn, "identity_link", "link_id", "idl_")
    conn.execute("INSERT INTO identity_link VALUES (?,?,?,?,?,?,?,?)",
                 (lid, a, b, outcome, layer, reason, "machine:identity", now_iso()))


# ---------------------------------------------------------- observations

def insert_observation(conn, requisition_id: str, obs: Dict[str, Any], tier: int, content_hash: str,
                       date_precision: str) -> str:
    oid = _next(conn, "observation", "observation_id", "obs_")
    seq = conn.execute("SELECT COALESCE(MAX(seq),0)+1 FROM observation").fetchone()[0]
    conn.execute(
        "INSERT INTO observation (observation_id, requisition_id, run_id, source, source_kind, source_external_id, "
        "source_url, apply_url, observed_at, raw_title, raw_company, raw_location, raw_salary, raw_employment_type, "
        "raw_text, source_posted_date, source_updated_date, date_precision, completeness, source_authority_tier, "
        "language_detection_json, content_hash, seq, raw_work_mode) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (oid, requisition_id, obs["run_id"], obs["source"], obs["source_kind"], obs.get("source_external_id"),
         obs.get("source_url"), obs.get("apply_url"), obs["observed_at"], obs.get("raw_title"),
         obs.get("raw_company"), obs.get("raw_location"), obs.get("raw_salary"), obs.get("raw_employment_type"),
         obs.get("raw_text"), obs.get("source_posted_date"), obs.get("source_updated_date"), date_precision,
         obs["completeness"], tier, json.dumps(obs.get("language_detection")) if obs.get("language_detection") else None,
         content_hash, seq, obs.get("raw_work_mode")))
    return oid


def observations_for(conn, requisition_ids: List[str]) -> List[Dict[str, Any]]:
    marks = ",".join("?" for _ in requisition_ids)
    rows = conn.execute(f"SELECT * FROM observation WHERE requisition_id IN ({marks}) ORDER BY seq",
                        requisition_ids).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["language_detection"] = json.loads(d["language_detection_json"]) if d["language_detection_json"] else None
        out.append(d)
    return out


# -------------------------------------------------------------- evidence

def has_evidence(conn, observation_id: str, extractor_version: str) -> bool:
    return conn.execute("SELECT 1 FROM evidence WHERE observation_id=? AND extractor_version=? LIMIT 1",
                        (observation_id, extractor_version)).fetchone() is not None


def insert_evidence(conn, requisition_id: str, observation_id: str, extractor_version: str,
                    source: str, drafts, content_hash: str) -> None:
    ts = now_iso()
    for ordinal, d in enumerate(drafts):
        eid = _next(conn, "evidence", "evidence_id", "ev_")
        conn.execute(
            "INSERT INTO evidence (evidence_id, requisition_id, observation_id, extractor_version, ordinal, dimension, "
            "evidence_type, strength, state, source, source_field, quoted_span, normalized_value_json, extracted_at, "
            "content_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (eid, requisition_id, observation_id, extractor_version, ordinal, d.dimension, d.evidence_type,
             d.strength, "STATED", source, d.source_field, d.quoted_span,
             json.dumps(d.value, ensure_ascii=False, sort_keys=True), ts, content_hash))


def evidence_for(conn, observation_ids: List[str], extractor_version: str) -> List[Dict[str, Any]]:
    marks = ",".join("?" for _ in observation_ids)
    rows = conn.execute(f"SELECT * FROM evidence WHERE observation_id IN ({marks}) AND extractor_version=? "
                        f"ORDER BY observation_id, ordinal", [*observation_ids, extractor_version]).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["value"] = json.loads(d["normalized_value_json"])
        out.append(d)
    return out


# ------------------------------------------------------------ evaluations

def find_evaluation(conn, requisition_id: str, policy_version: str, evidence_hash: str) -> Optional[Dict[str, Any]]:
    row = conn.execute("SELECT * FROM evaluation WHERE requisition_id=? AND policy_version=? AND evidence_hash=?",
                       (requisition_id, policy_version, evidence_hash)).fetchone()
    return _eval_row(row)


def insert_evaluation(conn, requisition_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
    eid = _next(conn, "evaluation", "evaluation_id", "eval_")
    seq = conn.execute("SELECT COALESCE(MAX(seq),0)+1 FROM evaluation").fetchone()[0]
    conn.execute(
        "INSERT INTO evaluation (evaluation_id, requisition_id, policy_version, evidence_hash, evaluated_at, "
        "eligibility_overall, relevance_label, queue_lane, flags_json, result_json, evaluator_version, seq) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (eid, requisition_id, result["policy_version"], result["evidence_hash"], now_iso(),
         result["eligibility_overall"], result["relevance"]["relevance_label"], result["lane"],
         json.dumps(result["flags"]), json.dumps(result, ensure_ascii=False, sort_keys=True, default=str),
         result["evaluator_version"], seq))
    for dim, d in result["eligibility_dimensions"].items():
        conn.execute("INSERT INTO evaluation_dimension VALUES (?,?,?,?,?)",
                     (eid, dim, d["verdict"], d["rule_id"], json.dumps(d["flags"])))
    return find_evaluation(conn, requisition_id, result["policy_version"], result["evidence_hash"])


def evaluations_for(conn, requisition_id: str, policy_version: Optional[str] = None) -> List[Dict[str, Any]]:
    q = "SELECT * FROM evaluation WHERE requisition_id=?"
    args = [requisition_id]
    if policy_version:
        q += " AND policy_version=?"
        args.append(policy_version)
    return [_eval_row(r) for r in conn.execute(q + " ORDER BY seq", args)]


def _eval_row(row) -> Optional[Dict[str, Any]]:
    if row is None:
        return None
    d = dict(row)
    d["result"] = json.loads(d["result_json"])
    return d


# --------------------------------------------------------------------- FX

def add_fx_rate(conn, base_currency: str, rate: float, snapshot_date: str, source: str, entered_by: str) -> str:
    fid = _next(conn, "fx_rate", "fx_id", "fx_")
    conn.execute("INSERT INTO fx_rate VALUES (?,?,?,?,?,?,?,?)",
                 (fid, base_currency.upper(), "INR", rate, snapshot_date, source, entered_by, now_iso()))
    return fid


def fx_lookup_factory(conn, max_age_days: Optional[int] = None):
    def lookup(currency: str, as_of: str) -> Optional[Dict[str, Any]]:
        row = conn.execute("SELECT * FROM fx_rate WHERE base_currency=? AND snapshot_date<=? "
                           "ORDER BY snapshot_date DESC, fx_id DESC LIMIT 1", (currency.upper(), as_of or "9999")).fetchone()
        if row is None:
            return None
        if max_age_days is not None and as_of:
            age = (datetime.fromisoformat(as_of[:10]) - datetime.fromisoformat(row["snapshot_date"][:10])).days
            if age > max_age_days:
                return None
        return {"fx_id": row["fx_id"], "rate": row["rate"], "fx_source": row["source"],
                "fx_snapshot_date": row["snapshot_date"], "pair": f"{row['base_currency']}/INR"}
    return lookup


# --------------------------------------------------- human-only writes

def record_review_decision(conn, requisition_id: str, kind: str, *, actor: str, note: Optional[str] = None,
                           machine_context: Optional[Dict[str, Any]] = None, decided_at: Optional[str] = None) -> str:
    if actor != "human":
        raise PermissionError("review decisions are recorded only by the human reviewer")
    did = _next(conn, "review_decision", "decision_id", "dec_")
    conn.execute("INSERT INTO review_decision VALUES (?,?,?,?,?,?,?)",
                 (did, requisition_id, kind, actor, decided_at or now_iso(), note, json.dumps(machine_context or {})))
    return did


def record_application_event(conn, requisition_id: str, event: str, *, actor: str, event_at: str,
                             method: Optional[str] = None, note: Optional[str] = None) -> str:
    """Records what the human did elsewhere. Nothing is submitted by JobOps."""
    if actor != "human":
        raise PermissionError("application events are recorded only by the human")
    aid = _next(conn, "application", "application_event_id", "app_")
    conn.execute("INSERT INTO application VALUES (?,?,?,?,?,?,?,?)",
                 (aid, requisition_id, event, actor, event_at, now_iso(), method, note))
    return aid


def decided_requisitions(conn) -> set:
    return {r[0] for r in conn.execute("SELECT DISTINCT requisition_id FROM review_decision")}


# ----------------------------------------------------------- queue state

def queue_state(conn, requisition_id: str) -> Dict[str, Any]:
    row = conn.execute("SELECT * FROM queue_state WHERE requisition_id=?", (requisition_id,)).fetchone()
    return dict(row) if row else {"requisition_id": requisition_id, "carry_days": 0, "first_review_day": None,
                                  "last_planned_day": None, "last_surfaced_day": None, "overflow_parked_on": None}


def save_queue_state(conn, state: Dict[str, Any]) -> None:
    conn.execute("INSERT OR REPLACE INTO queue_state VALUES (?,?,?,?,?,?)",
                 (state["requisition_id"], state["carry_days"], state["first_review_day"],
                  state["last_planned_day"], state["last_surfaced_day"], state["overflow_parked_on"]))
