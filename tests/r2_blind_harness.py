"""
Round-2 independent blind holdout harness (P4b measurement, persisted in P5).

Replays tests/fixtures/policy_v02_blind_round2_cases.json (frozen, SHA-256 in
policy_v02_blind_round2_cases.sha256) against any supported policy version
through the engine's public interface (EvaluationService.ingest,
current_evaluation, evaluation.queue.plan_day). It contains NO expected values:
every expectation is read from the frozen fixture. Not collected by pytest
(no test_ prefix); tests/test_policy_v02_blind_round2.py and
tests/r2_replay.py drive it.

Adapter mapping (fixed in P4b before the first execution):
  source linkedin/naukri/other -> JOB_BOARD; ats -> EMPLOYER_ATS
        (ats + source_detail "company careers page" -> COMPANY_SITE)
  completeness: sequences carry it explicitly; posting cases: FULL_JD iff jd_text non-empty
  raw_location = location_text; raw_work_mode = work_mode_text (separate, never concatenated)
  raw_salary = compensation_text; raw_employment_type = employment_text; raw_text = jd_text
  employer_type_hint -> company classification, basis OWNER_CONFIRMED (fixture convention:
        "employer_type_hint ... treated as the owner's classification"); 'unclassified' -> no record.
        'third_party_payroll' -> THIRD_PARTY_PAYROLL when the schema accepts it (migration 0103, P5);
        before 0103 no record could be written (P4b input-contract gap)
  fx_snapshot_age_days -> NOT representable: the fixture gives no rate and no owner FX table exists;
        no FX row is seeded. Fields that depend on a conversion are UNSCORABLE (see _fx_unscorable)
  evaluation clock: posting cases 2026-09-30 (fixture authored_on); sequences: run observed_on
  observed_at: posting cases posted_date T06:00Z; sequences observed_on T06:00Z
  sequence requisition_id -> one shared employer posting URL
        https://careers.<company-slug>.example/jobs/<requisition_id> (source_url for EMPLOYER_ATS /
        COMPANY_SITE, apply_url for JOB_BOARD): all sightings of one requisition share an L2 key
  queue-sequence items (R2-SEQ-07) -> source_external_id = item_key, so the stated earlier identical
        sighting (history_note) is the same requisition (P5; in P4b it became a separate requisition)
  posting cases: source_external_id = case id (every case is its own requisition)
  'enrichment' blocks: no engine input exists; ignored
  owner queue action (R2-SEQ-07 convention): after each planned day every surfaced member receives a
        SKIP review decision, so surfaced items leave the pending pool

Projections:
  "p4b" (the P4b measurement): employment_type = worst(engine employment_type, employment_relationship);
        employer_type = engine employer_type, worsened to FAIL on REL-R06/REL-R07.
  "p5" (default; P5 Task 0 "employer_type != employment_type"): as p4b, except REL-R08 (a STAFFING
        employer classification seen through the relationship table) is an employer-side signal: it is
        folded into employer_type, never into employment_type.
"""

import hashlib
import json
import re
import sqlite3
from pathlib import Path

from evaluation.policy_loader import load_policy_version
from evaluation.queue import plan_day
from store import repository as repo
from v02_support import fresh_service, observation

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FIXTURE = FIXTURES / "policy_v02_blind_round2_cases.json"
SHA_FILE = FIXTURES / "policy_v02_blind_round2_cases.sha256"
OVERLAY = FIXTURES / "policy_v02_blind_round2_owner_resolutions.json"
EXPECTED_SHA = "f54eb41bc805a28162e69e77495557b3647dd82e3b7c110c2987981edee421e5"
POSTING_EVAL_DATE = "2026-09-30"

_KIND = {"linkedin": "JOB_BOARD", "naukri": "JOB_BOARD", "other": "JOB_BOARD", "ats": "EMPLOYER_ATS"}
_CLASS = {"product": "PRODUCT", "ai_native": "AI_NATIVE", "gcc": "GCC", "enterprise": "ENTERPRISE_DIRECT",
          "staffing": "STAFFING", "consultancy": "CONSULTANCY", "engineering_led": "ENGINEERING_LED",
          "it_services": "IT_SERVICES", "third_party_payroll": "THIRD_PARTY_PAYROLL"}
_ORDER = ("FAIL", "UNKNOWN", "PASS")
DIMS = ("geography", "compensation", "employment_type", "employer_type", "language")
FX_FLAGS = ("FX_STALE", "FX_RATE_UNAVAILABLE")


def fixture_sha() -> str:
    return hashlib.sha256(FIXTURE.read_bytes()).hexdigest()


def load_doc():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def load_overlay():
    return json.loads(OVERLAY.read_text(encoding="utf-8"))["resolutions"]


def _worst(*v):
    for x in _ORDER:
        if x in v:
            return x
    raise ValueError(v)


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-") or "unknown"


def _kind(p):
    if p["source"] == "ats" and (p.get("source_detail") or "").lower() == "company careers page":
        return "COMPANY_SITE"
    return _KIND[p["source"]]


def obs_fields(p, *, observed_on, run_id, ext_id=None, completeness=None):
    jd = p.get("jd_text") or None
    completeness = completeness or ("FULL_JD" if jd else "SEARCH_ONLY")
    kind = _kind(p)
    source_url = apply_url = None
    rid = p.get("requisition_id")
    if rid:
        url = f"https://careers.{_slug(p.get('company'))}.example/jobs/{rid}"
        if kind in ("EMPLOYER_ATS", "COMPANY_SITE"):
            source_url = url
        else:
            apply_url = url
    return dict(source=p["source"], source_kind=kind, completeness=completeness,
                raw_title=p.get("title") or None, raw_company=p.get("company") or None,
                raw_location=p.get("location_text") or None, raw_work_mode=p.get("work_mode_text") or None,
                raw_salary=p.get("compensation_text") or None,
                raw_employment_type=p.get("employment_text") or None,
                raw_text=jd if completeness != "SEARCH_ONLY" else None,
                source_posted_date=p.get("posted_date"),
                observed_at=f"{observed_on}T06:00:00+00:00", run_id=run_id,
                source_url=source_url, apply_url=apply_url, source_external_id=ext_id)


def prepare(service, p, seen):
    cls = _CLASS.get(p.get("employer_type_hint"))
    company = p.get("company")
    if cls and company and company not in seen:
        try:
            service.classify_company(company, cls, "OWNER_CONFIRMED", "owner")
        except sqlite3.IntegrityError:
            # Schema without THIRD_PARTY_PAYROLL (before migration 0103): not representable, no record.
            pass
        seen.add(company)


def project(result, projection="p5"):
    d = result["eligibility_dimensions"]
    dims = {k: v["verdict"] for k, v in d.items()}
    rel = d["employment_relationship"]
    employer = dims["employer_type"]
    rel_for_employment = dims["employment_relationship"]
    if rel["verdict"] == "FAIL" and rel.get("rule_id") in ("REL-R06", "REL-R07"):
        employer = _worst(employer, "FAIL")
    if projection == "p5" and rel.get("rule_id") == "REL-R08":
        employer = _worst(employer, rel["verdict"])
        rel_for_employment = "PASS"
    out = {"geography": dims["geography"], "compensation": dims["compensation"], "language": dims["language"],
           "employment_type": _worst(dims["employment_type"], rel_for_employment),
           "employer_type": employer,
           "relevance": result["relevance"]["relevance_label"],
           "experience_label": (None if result["relevance"]["experience_signal"] == "UNKNOWN_FIT"
                                else result["relevance"]["experience_signal"]),
           "lane": result["lane"], "flags": sorted(set(result["flags"]))}
    out["overall"] = _worst(*(out[k] for k in DIMS))
    comp_facts = d["compensation"].get("facts") or {}
    out["compensation_state"] = comp_facts.get("state")
    out["compensation_currency"] = comp_facts.get("original_currency")
    out["compensation_india_band"] = bool(comp_facts.get("india_band_used"))
    return out


def raw_detail(result):
    return {k: {"verdict": v["verdict"], "rule_id": v.get("rule_id")}
            for k, v in result["eligibility_dimensions"].items()}


def _fx_unscorable(posting, expected, actual):
    """
    Fields that cannot be scored because the fixture carries an FX snapshot age but no rate while the
    governing figure is non-INR with no India band: the fixture's expected PASS / FX_STALE presumes a
    conversion the harness cannot perform (whatever the engine's intermediate state, e.g.
    FX_RATE_UNAVAILABLE or PERIOD_UNSTATED). Never guessed: skipped and reported.
    """
    if posting.get("fx_snapshot_age_days") is None:
        return set()
    needs_fx = actual.get("compensation_state") == "FX_RATE_UNAVAILABLE" or (
        actual.get("compensation_currency") not in (None, "INR") and not actual.get("compensation_india_band"))
    if not needs_fx:
        return set()
    fields = {"compensation", "flag:FX_STALE", "flag:FX_RATE_UNAVAILABLE"}
    if isinstance(expected, dict) and expected.get("compensation") == "PASS" and actual.get("lane") == "REVIEW":
        # The expected lane assumes a converted PASS figure; an actual REVIEW is explained by the
        # unconvertible figure. Any other actual lane (e.g. EXCLUDED by another dimension) is scored.
        fields.add("lane")
    return fields


def compare_case(expected, actual, skip=frozenset()):
    out = []
    for field, exp in expected.items():
        if field in skip:
            continue
        if field == "must_have_flags":
            miss = [f for f in exp if f not in actual["flags"] and f"flag:{f}" not in skip]
            if miss:
                out.append({"field": field, "expected": exp, "actual": actual["flags"], "missing": miss})
        elif field == "must_not_have_flags":
            pres = [f for f in exp if f in actual["flags"] and f"flag:{f}" not in skip]
            if pres:
                out.append({"field": field, "expected": exp, "actual": actual["flags"], "present": pres})
        elif field in actual and actual[field] != exp:
            out.append({"field": field, "expected": exp, "actual": actual[field]})
    return out


def overlay_expected(case_id, determined_subset):
    """Owner-resolution expectation for an UNDETERMINED case (P4b §10), layered on the author's subset."""
    res = load_overlay().get(case_id)
    if res is None:
        return None
    exp = dict(determined_subset or {})
    exp["lane"] = res["expected_lane"]
    if "expected_employment_type" in res:
        exp["employment_type"] = res["expected_employment_type"]
    exp["must_have_flags"] = sorted(set(exp.get("must_have_flags", [])) | set(res.get("expected_must_have_flags", [])))
    return exp


# ------------------------------------------------------------ posting cases

def run_case(case, version, projection="p5"):
    p = case["posting"]
    service = fresh_service(load_policy_version(version))
    service.clock = lambda: POSTING_EVAL_DATE
    prepare(service, p, set())
    res = service.ingest(observation(**obs_fields(p, observed_on=p.get("posted_date") or POSTING_EVAL_DATE,
                                                  run_id=f"r2-{case['id']}", ext_id=case["id"])))
    result = res["evaluation"]["result"]
    actual = project(result, projection)
    rec = {"id": case["id"], "actual": actual, "dimensions_raw": raw_detail(result),
           "newness": res["requisition"]["newness_state"],
           "relevance_reason": result["relevance"].get("reason"),
           "relevance_terms": result["relevance"].get("specific_terms")}
    if case["expected"] == "UNDETERMINED":
        rec["undetermined"] = True
        subset = case.get("determined_subset") or {}
        skip = _fx_unscorable(p, subset, actual)
        rec["mismatches_vs_determined_subset"] = compare_case(subset, actual, skip)
        resolved = overlay_expected(case["id"], subset)
        rec["mismatches_resolution_adjusted"] = compare_case(resolved, actual, skip) if resolved else None
        rec["mismatches"] = []
    else:
        rec["undetermined"] = False
        skip = _fx_unscorable(p, case["expected"], actual)
        rec["mismatches"] = compare_case(case["expected"], actual, skip)
        rec["mismatches_resolution_adjusted"] = rec["mismatches"]
    rec["unscorable_fields"] = sorted(skip)
    return rec


# ---------------------------------------------------------------- sequences

def _cmp_state(exp, actual, newness, resolved_newness=None):
    out = []
    for field, e in exp.items():
        if field in ("note", "undetermined_question", "reasoning"):
            continue
        if field == "verdict":
            for k, v in e.items():
                if actual.get(k) != v:
                    out.append({"field": f"verdict.{k}", "expected": v, "actual": actual.get(k)})
        elif field == "newness":
            e = resolved_newness if e == "UNDETERMINED" else e
            if e is None:
                continue
            if newness != e:
                out.append({"field": "newness", "expected": e, "actual": newness})
        elif field == "must_not_have_newness":
            if newness in e:
                out.append({"field": field, "expected": e, "actual": newness})
        elif field == "must_have_flags":
            miss = [f for f in e if f not in actual["flags"]]
            if miss:
                out.append({"field": field, "expected": e, "actual": actual["flags"], "missing": miss})
        elif field == "must_not_have_flags":
            pres = [f for f in e if f in actual["flags"]]
            if pres:
                out.append({"field": field, "expected": e, "actual": actual["flags"], "present": pres})
        elif field in ("relevance", "lane"):
            if actual[field] != e:
                out.append({"field": field, "expected": e, "actual": actual[field]})
    return out


def _state(service, rid, projection):
    ev = service.current_evaluation(rid)["result"]
    return project(ev, projection), repo.get_requisition(service.conn, rid)["newness_state"]


def run_sequence(seq, version, projection="p5", *, resolved=False):
    overlay = load_overlay() if resolved else {}
    service = fresh_service(load_policy_version(version))
    seen = set()
    item_rid = {}
    steps = []
    for run in seq["runs"]:
        run_date = run.get("observed_on") or run["observations"][0]["observed_on"]
        rids = []
        for o in run["observations"]:
            day = o.get("observed_on") or run_date
            ext = f"{seq['id']}:{o['item_key']}" if o.get("item_key") else None
            if o.get("history_note"):
                hist = re.search(r"first observed (\d{4}-\d{2}-\d{2})", o["history_note"]).group(1)
                service.clock = lambda d=hist: d
                prepare(service, o, seen)
                service.ingest(observation(**obs_fields(o, observed_on=hist, run_id=f"{seq['id']}-hist-{o['item_key']}",
                                                        ext_id=ext, completeness=o.get("completeness"))))
            service.clock = lambda d=day: d
            prepare(service, o, seen)
            res = service.ingest(observation(**obs_fields(o, observed_on=day, run_id=run["run_id"], ext_id=ext,
                                                          completeness=o.get("completeness"))))
            rids.append(res["requisition_id"])
            if o.get("item_key"):
                item_rid[o["item_key"]] = res["requisition_id"]
        service.clock = lambda d=run_date: d
        exp = run.get("expected") or {}
        rec = {"run_id": run["run_id"], "requisition_ids": rids, "mismatches": []}
        if "per_requisition" in exp or "requisitions_retained" in exp:
            uniq = sorted(set(rids))
            rec["states"] = {}
            if "requisitions_retained" in exp and len(uniq) != exp["requisitions_retained"]:
                rec["mismatches"].append({"field": "requisitions_retained", "expected": exp["requisitions_retained"],
                                          "actual": len(uniq)})
            for rid in uniq:
                a, n = _state(service, rid, projection)
                rec["states"][rid] = {"actual": a, "newness": n}
                for m in _cmp_state(exp.get("per_requisition", {}), a, n):
                    rec["mismatches"].append({**m, "requisition": rid})
            plan = plan_day(service, run_date)
            units = [u for u in plan["review_today"] + plan["review_carried"]
                     if set(u["member_requisition_ids"]) & set(uniq)]
            rec["review_units"] = [u["member_requisition_ids"] for u in units]
            if "review_cards" in exp and len(units) != exp["review_cards"]:
                rec["mismatches"].append({"field": "review_cards", "expected": exp["review_cards"], "actual": len(units)})
            if "review_cap_slots_consumed" in exp:
                slots = sum(1 for u in plan["review_today"] if set(u["member_requisition_ids"]) & set(uniq))
                if slots != exp["review_cap_slots_consumed"]:
                    rec["mismatches"].append({"field": "review_cap_slots_consumed",
                                              "expected": exp["review_cap_slots_consumed"], "actual": slots})
        elif any(k in exp for k in ("surfaced", "lanes", "overflow", "all_items_lane")):
            rec.update(_run_queue_day(service, run, exp, item_rid, run_date, projection))
        else:
            rid = rids[-1]
            a, n = _state(service, rid, projection)
            rec["actual"], rec["newness"] = a, n
            if len(set(rids)) != 1:
                rec["mismatches"].append({"field": "same_requisition", "expected": True, "actual": sorted(set(rids))})
            res_new = overlay.get(f"{seq['id']}/{run['run_id']}", {}).get("expected_newness")
            rec["mismatches"] += _cmp_state(exp, a, n, res_new)
            rec["undetermined_fields"] = [k for k, v in exp.items() if v == "UNDETERMINED" and not res_new]
        steps.append(rec)
    return {"id": seq["id"], "runs": steps,
            "mismatches": [{**x, "run_id": s["run_id"]} for s in steps for x in s["mismatches"]]}


def _run_queue_day(service, run, exp, item_rid, day, projection):
    key_of = {v: k for k, v in item_rid.items()}
    rec = {"mismatches": []}
    lanes_now = {o["item_key"]: _state(service, item_rid[o["item_key"]], projection)[0] for o in run["observations"]}
    plan = plan_day(service, day)

    def keys(units):
        return [key_of.get(m, m) for u in units for m in u["member_requisition_ids"]]

    surfaced = keys(plan["review_today"])
    carried = keys(plan["review_carried"])
    parked = keys([u for u in plan["lanes"]["PARKED"] if u.get("parked_by") == "overflow"])
    rec.update(surfaced_order=surfaced, carried_order=carried, overflow_parked=parked,
               item_states={k: {"lane": a["lane"], "relevance": a["relevance"], "flags": a["flags"]}
                            for k, a in lanes_now.items()})
    if "all_items_lane" in exp:
        bad = {k: a["lane"] for k, a in lanes_now.items() if a["lane"] != exp["all_items_lane"]}
        if bad:
            rec["mismatches"].append({"field": "all_items_lane", "expected": exp["all_items_lane"], "actual": bad})
    if "surfaced" in exp and sorted(surfaced) != sorted(exp["surfaced"]):
        rec["mismatches"].append({"field": "surfaced", "expected": sorted(exp["surfaced"]), "actual": sorted(surfaced)})
    if "rank_groups_best_first" in exp:
        groups = exp["rank_groups_best_first"]
        gi = {k: i for i, g in enumerate(groups) for k in g}
        order = [k for k in surfaced + carried if k in gi]
        idx = [gi[k] for k in order]
        if idx != sorted(idx) or set(order) != set(gi):
            rec["mismatches"].append({"field": "rank_groups_best_first", "expected": groups, "actual": order})
    for k, desc in (exp.get("overflow") or {}).items():
        if k not in carried:
            where = "surfaced" if k in surfaced else ("overflow-PARKED" if k in parked else "absent")
            rec["mismatches"].append({"field": f"overflow.{k}", "expected": desc, "actual": where})
    for k, lane in (exp.get("lanes") or {}).items():
        where = ("PARKED" if k in parked else "REVIEW" if (k in carried or k in surfaced) else "absent")
        if where != lane:
            rec["mismatches"].append({"field": f"lanes.{k}", "expected": lane, "actual": where})
    for u in plan["review_today"]:
        for m in u["member_requisition_ids"]:
            service.record_review_decision(m, "SKIP", actor="human",
                                           note="R2 harness: surfaced item actioned per fixture queue convention")
    return rec


def run_all(version, projection="p5", *, resolved=False):
    doc = load_doc()
    cases, seqs = [], []
    for c in doc["posting_cases"]:
        try:
            cases.append(run_case(c, version, projection))
        except Exception as e:  # recorded, never hidden
            cases.append({"id": c["id"], "error": f"{type(e).__name__}: {e}", "mismatches": [{"field": "ERROR"}],
                          "mismatches_resolution_adjusted": [{"field": "ERROR"}],
                          "undetermined": c["expected"] == "UNDETERMINED"})
    for s in doc["sequences"]:
        try:
            seqs.append(run_sequence(s, version, projection, resolved=resolved))
        except Exception as e:
            seqs.append({"id": s["id"], "error": f"{type(e).__name__}: {e}", "mismatches": [{"field": "ERROR"}]})
    return cases, seqs
