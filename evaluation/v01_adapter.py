"""
Replay adapter: stored v2 evidence -> the unchanged v0.1 gate (policy/gate.py).

Proves that an older policy version can be replayed against stored evidence
without recrawling. The v0.1 gate and artifact are used exactly as they are;
nothing here modifies them. v0.1 evaluates only work mode and compensation and
has no relevance model, so relevance is recorded as NOT_ASSESSED.
"""

from typing import Any, Dict

from policy import HardEligibilityGate

from store import repository as repo

from .selection import select
from .textutil import stable_hash

V01_VERSION = "jobops-policy@0.1.0"
_V01_LANES = {"PASS": "SHORTLIST", "UNKNOWN": "REVIEW"}


class V01ReplayPolicy:
    is_v01_adapter = True
    version = V01_VERSION

    def __init__(self):
        self.gate = HardEligibilityGate()

    def evaluate_requisition(self, service, requisition_id: str) -> Dict[str, Any]:
        req, observations, evidence, _ = service._bundle(requisition_id, service.policy)
        geo = select(observations, evidence, "geography", allow_context=False)
        comp = select(observations, evidence, "compensation", allow_context=False)
        posting: Dict[str, Any] = {"candidate_id": requisition_id}
        geo_row = next((r for r in (geo["rows"] if geo else []) if r["value"]["mode"]), None)
        if geo_row:
            posting["work_mode_text"] = geo_row["quoted_span"]
        comp_row = next((r for r in (comp["rows"] if comp else []) if r["value"]["kind"] == "FIGURE"), None)
        if comp_row:
            posting["compensation_text"] = comp_row["quoted_span"]
        gate = self.gate.evaluate_posting(posting).as_dict()
        verdict = gate["verdict"]
        lane = _V01_LANES.get(verdict) or (
            "BELOW_THRESHOLD" if "COMP-FAIL-BELOW-FLOOR" in gate["reason_codes"] else "EXCLUDED")
        inputs = {"policy_version": V01_VERSION, "posting": posting,
                  "evidence_ids": [r["evidence_id"] for r in ([geo_row] if geo_row else []) + ([comp_row] if comp_row else [])]}
        result = {
            "policy_version": V01_VERSION, "evaluator_version": "v01_adapter@1.0.0",
            "evidence_hash": stable_hash(inputs),
            "eligibility_dimensions": {dim: {"verdict": v, "rule_id": rule, "flags": []}
                                       for (dim, v), rule in zip(gate["dimension_verdicts"].items(), gate["rules_fired"])},
            "eligibility_overall": verdict,
            "relevance": {"relevance_label": "NOT_ASSESSED"},
            "flags": sorted(gate["reason_codes"]), "lane": lane, "v01_gate_result": gate,
        }
        existing = repo.find_evaluation(service.conn, requisition_id, V01_VERSION, result["evidence_hash"])
        if existing:
            return existing
        service.conn.execute("BEGIN IMMEDIATE")
        try:
            stored = repo.insert_evaluation(service.conn, requisition_id, result)
            service.conn.execute("COMMIT")
        except Exception:
            service.conn.execute("ROLLBACK")
            raise
        return stored
