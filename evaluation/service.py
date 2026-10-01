"""
EvaluationService: ingest observations, keep evidence, derive current evaluations,
replay any policy version. One sqlite3 connection (from store.db.connect).

Guarantees:
  * each ingest is one transaction (observation + evidence + identity + newness);
  * evaluation key = (requisition, policy_version, evidence_hash); an existing
    key is reused, never duplicated (idempotent replay);
  * the current evaluation is recomputed from the per-dimension richest valid
    evidence (selection.py), never from the newest sighting (F4);
  * no network, no application submission, no human decision is ever made here.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from geo import PlaceIndex
from identity.ruleset import load_identity_ruleset
from sources.base import ObservationInput

from store import repository as repo

from . import engine, newness
from .extract import EvidenceDraft, extract, extractor_version
from .identity_resolution import link_probable, observation_keys, resolve, root_of
from .policy_loader import load_policy_v02
from .textutil import content_hash, date_precision


def _authority(policy, source_kind: str, completeness: str) -> int:
    cfg = policy.section("source_authority")
    if source_kind in cfg["tier_by_kind"]:
        return cfg["tier_by_kind"][source_kind]
    return cfg["tier_by_completeness_for_boards"][completeness]


class EvaluationService:
    def __init__(self, conn, policy=None, *, identity_ruleset=None, clock=None):
        self.conn = conn
        self.policy = policy or load_policy_v02()
        # Injectable evaluation-date clock (ISO date string). Used for FX age (OI-040).
        self.clock = clock or (lambda: datetime.now(timezone.utc).date().isoformat())
        self.id_rules = identity_ruleset or load_identity_ruleset()
        self._places: Dict[str, PlaceIndex] = {}
        self.extra_policies: Dict[str, Any] = {}

    def places(self, policy) -> PlaceIndex:
        if policy.version not in self._places:
            self._places[policy.version] = PlaceIndex(policy.section("geo"))
        return self._places[policy.version]

    # ------------------------------------------------------------- registry

    def classify_company(self, name: str, classification: str, basis: str, decided_by: str,
                         decided_at: Optional[str] = None) -> str:
        from identity.canonical import normalize_company
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            cid = repo.upsert_company(self.conn, name, normalize_company(name, self.id_rules) or name.lower())
            repo.add_classification(self.conn, cid, classification, basis, decided_by, decided_at=decided_at)
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise
        return cid

    def add_fx_rate(self, currency: str, rate: float, snapshot_date: str, source: str, entered_by: str = "owner") -> str:
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            fid = repo.add_fx_rate(self.conn, currency, rate, snapshot_date, source, entered_by)
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise
        return fid

    # --------------------------------------------------------------- ingest

    def ingest(self, observation: ObservationInput) -> Dict[str, Any]:
        obs = observation.as_dict()
        policy = self.policy
        places = self.places(policy)
        drafts = extract(obs, policy, places)
        keys, ats, employer_url = observation_keys(obs, self.id_rules)
        location_ref = _location_ref(drafts, places)
        tier = _authority(policy, obs["source_kind"], obs["completeness"])
        precision = date_precision(obs.get("source_posted_date"))
        chash = content_hash(obs.get("raw_text"))
        c = self.conn
        c.execute("BEGIN IMMEDIATE")
        try:
            repo.ensure_run(c, obs["run_id"])
            company_id = None
            if obs.get("raw_company"):
                from identity.canonical import normalize_company
                company_id = repo.upsert_company(c, obs["raw_company"],
                                                 normalize_company(obs["raw_company"], self.id_rules) or obs["raw_company"].lower())
            res = resolve(c, obs, keys, location_ref, self.id_rules)
            created = res["created"]
            if created:
                rid = repo.create_requisition(
                    c, company_id=company_id, canonical_title=obs.get("raw_title"),
                    canonical_url=employer_url or obs.get("source_url"),
                    canonical_url_authority=1 if employer_url else tier,
                    normalized_location=location_ref, l3_key=res.get("l3_key"),
                    first_seen_at=obs["observed_at"], last_seen_at=obs["observed_at"],
                    first_seen_run_id=obs["run_id"], last_seen_run_id=obs["run_id"],
                    source_first_seen_json=json.dumps({obs["source"]: obs["observed_at"]}),
                    canonical_posting_date=obs.get("source_posted_date"), date_precision=precision,
                    newness_state="NEW", newness_confidence=newness.confidence("NEW", precision),
                    newness_reason_json=json.dumps(["first observation of this canonical requisition"]))
                affected = link_probable(c, rid, res["probable_of"]) + res["affected"]
            else:
                rid = res["requisition_id"]
                affected = res["affected"]
            repo.add_keys(c, rid, keys)
            oid = repo.insert_observation(c, rid, obs, tier, chash, precision)
            ev_version = extractor_version(policy)
            repo.insert_evidence(c, rid, oid, ev_version, obs["source"], drafts, chash)
            if company_id:
                for system, tenant in ats:
                    repo.add_ats_identity(c, company_id, system, tenant, oid)
            if not created:
                self._update_seen(rid, obs, oid, employer_url, tier, precision, policy, places)
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise
        evaluation = self.current_evaluation(rid)
        for other in affected:
            self.current_evaluation(other)
        return {"requisition_id": root_of(c, rid), "attached_to": rid, "observation_id": oid,
                "created": created, "evaluation": evaluation,
                "requisition": repo.get_requisition(c, rid)}

    def _update_seen(self, rid, obs, oid, employer_url, tier, precision, policy, places) -> None:
        c = self.conn
        req = repo.get_requisition(c, rid)
        ev_version = extractor_version(policy)
        family = [rid] + [r["requisition_id"] for r in c.execute(
            "SELECT requisition_id FROM requisition WHERE duplicate_of=?", (rid,))]
        all_obs = repo.observations_for(c, family)
        current = next(o for o in all_obs if o["observation_id"] == oid)
        rows = repo.evidence_for(c, [o["observation_id"] for o in all_obs], ev_version)
        by_obs: Dict[str, List[Dict[str, Any]]] = {}
        for r in rows:
            by_obs.setdefault(r["observation_id"], []).append(r)
        fields = policy.section("newness")["material_fields"]
        snap = newness.material_snapshot(current, by_obs.get(oid, []), policy, places)
        changes: List[str] = []
        prior_same_source = [o for o in all_obs if o["source"] == obs["source"] and o["observation_id"] != oid]
        tolerant = bool(policy.section("newness").get("absent_detail_is_enrichment"))  # 0.2.3
        for field in fields:
            for prev in reversed(prior_same_source):  # latest earlier sighting with the field
                prev_snap = newness.material_snapshot(prev, by_obs.get(prev["observation_id"], []), policy, places)
                if newness.has_field(prev_snap, field):
                    if field in newness.changed_fields(snap, prev_snap, [field], tolerant):
                        changes.append(field)
                    break
        cross = policy.section("newness").get("cross_source_update")
        if cross and cross.get("enabled") and not (cross.get("applies_after_first_run")
                                                   and req["first_seen_run_id"] == obs["run_id"]):
            snapshots = {o["observation_id"]: newness.material_snapshot(o, by_obs.get(o["observation_id"], []),
                                                                         policy, places) for o in all_obs}
            for field in newness.cross_source_changes(current, all_obs, snapshots, cross):
                if field not in changes:
                    changes.append(field)
        state = newness.classify(False, req, obs["run_id"], changes, precision)
        first_seen = json.loads(req["source_first_seen_json"])
        if obs["source"] not in first_seen or obs["observed_at"] < first_seen[obs["source"]]:
            first_seen[obs["source"]] = obs["observed_at"]
        updates = dict(
            last_seen_at=max(req["last_seen_at"], obs["observed_at"]),
            first_seen_at=min(req["first_seen_at"], obs["observed_at"]),
            last_seen_run_id=obs["run_id"], source_first_seen_json=json.dumps(first_seen, sort_keys=True),
            newness_state=state["newness_state"], newness_confidence=state["newness_confidence"],
            newness_reason_json=json.dumps(state["newness_reason"]))
        if employer_url and (req["canonical_url_authority"] or 9) > 1:
            updates.update(canonical_url=employer_url, canonical_url_authority=1)
        if obs.get("source_posted_date") and (not req["canonical_posting_date"]
                                              or obs["source_posted_date"] < req["canonical_posting_date"]):
            updates.update(canonical_posting_date=obs["source_posted_date"], date_precision=precision)
        repo.update_requisition(c, rid, **updates)

    # ----------------------------------------------------------- evaluation

    def _ensure_evidence(self, observations: List[Dict[str, Any]], policy) -> str:
        """Extract with this policy's lexicon from STORED observations (no recrawl)."""
        version = extractor_version(policy)
        missing = [o for o in observations if not repo.has_evidence(self.conn, o["observation_id"], version)]
        if missing:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                for o in missing:
                    drafts = extract(o, policy, self.places(policy))
                    repo.insert_evidence(self.conn, o["requisition_id"], o["observation_id"], version,
                                         o["source"], drafts, o["content_hash"])
                self.conn.execute("COMMIT")
            except Exception:
                self.conn.execute("ROLLBACK")
                raise
        return version

    def _bundle(self, requisition_id: str, policy):
        c = self.conn
        req = repo.get_requisition(c, requisition_id)
        if req["duplicate_of"]:
            family = [requisition_id]
        else:
            family = [requisition_id] + [r["requisition_id"] for r in c.execute(
                "SELECT requisition_id FROM requisition WHERE duplicate_of=? ORDER BY requisition_id", (requisition_id,))]
        observations = repo.observations_for(c, family)
        version = self._ensure_evidence(observations, policy)
        evidence = repo.evidence_for(c, [o["observation_id"] for o in observations], version)
        for o in observations:
            o["completeness_rank"] = policy.section("source_authority")["completeness_rank"][o["completeness"]]
        context = {
            "classification_records": repo.classifications(c, req["company_id"]),
            "identity_flags": json.loads(req["identity_flags_json"]),
            "duplicate": bool(req["duplicate_of"]),
            # Age limits are applied by the policy (compensation.summarize), not by the lookup.
            "fx_lookup": repo.fx_lookup_factory(c, None),
            "evaluation_date": self.clock(),
        }
        return req, observations, evidence, context

    def current_evaluation(self, requisition_id: str, policy=None) -> Dict[str, Any]:
        policy = policy or self.policy
        if getattr(policy, "is_v01_adapter", False):
            return policy.evaluate_requisition(self, requisition_id)
        req, observations, evidence, context = self._bundle(requisition_id, policy)
        result = engine.evaluate(observations, evidence, context, policy, self.places(policy))
        existing = repo.find_evaluation(self.conn, requisition_id, policy.version, result["evidence_hash"])
        if existing:
            return existing
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            stored = repo.insert_evaluation(self.conn, requisition_id, result)
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise
        return stored

    replay = current_evaluation

    # --------------------------------------------------------- human actions

    def record_review_decision(self, requisition_id: str, kind: str, *, actor: str, note: Optional[str] = None) -> str:
        current = self.current_evaluation(requisition_id)
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            did = repo.record_review_decision(self.conn, requisition_id, kind, actor=actor, note=note,
                                              machine_context={"evaluation_id": current["evaluation_id"],
                                                               "lane": current["queue_lane"]})
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise
        return did


def _location_ref(drafts: List[EvidenceDraft], places: PlaceIndex) -> Optional[str]:
    for d in drafts:
        if d.dimension != "geography":
            continue
        for p in d.value["places"]:
            if p["kind"] == "CITY":
                return p["ref"]
    for d in drafts:
        if d.dimension == "geography":
            for p in d.value["places"]:
                if p["kind"] in ("COUNTRY", "REGION", "WORLDWIDE"):
                    return p["ref"]
    return None
