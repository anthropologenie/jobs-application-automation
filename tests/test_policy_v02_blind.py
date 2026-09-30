"""
Independent blind validation (P2, re-run in P3 against jobops-policy@0.2.2).

The fixture tests/fixtures/policy_v02_blind_cases.json was authored by a separate,
context-free agent from the rulings sheet, the owner policy spec and the rulings
log only, and frozen (SHA-256 in policy_v02_blind_cases.sha256) BEFORE the
implementation was inspected. This module:

  * verifies the frozen SHA-256 (fails if the fixture changed);
  * maps each raw posting onto the engine's public input (ObservationInput plus
    registry / FX table / evaluation-date clock); the mapping is fixed and
    documented below and contains NO expected values;
  * evaluates with the policy pinned in TARGET (jobops-policy@0.2.2 since P3) and
    asserts every expectation in the fixture that is not "UNDETERMINED";
  * marks known, classified mismatches as strict xfails (reason "<CLASS>:<id>").

Adapter mapping (decided before execution):
  source linkedin/naukri/other -> JOB_BOARD, ats -> EMPLOYER_ATS
  jd_text present -> FULL_JD, raw_text = jd_text;  absent -> SEARCH_ONLY, raw_text None
  raw_location = location_text; raw_work_mode = work_mode_text (separate fields; P3 §15.
                 P2 joined them into raw_location because the engine had no work-mode input,
                 which turned "Berlin, Germany — Remote" into a stated remote region: B009)
  raw_salary = compensation_text; raw_employment_type = employment_text
  employer_type_hint / employer_type_detail -> company registry classification
  jd_language(+confidence) -> language_detection; otherwise the engine's own detection
  fx_* -> owner FX table row; evaluation_date -> injected clock
  blind.employment_type = FAIL>UNKNOWN>PASS over engine employment_type and
                          employment_relationship (EOR / contractor / payroll live there)
  blind.employer_type   = engine employer_type, plus employment_relationship only
                          when it FAILs on placement / third-party payroll (REL-R06/R07)
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path

import pytest

from evaluation.policy_loader import load_policy_version
from evaluation.queue import plan_day
from store import repository as repo
from v02_support import fresh_service, no_network, observation  # noqa: F401

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FIXTURE = FIXTURES / "policy_v02_blind_cases.json"
SHA_FILE = FIXTURES / "policy_v02_blind_cases.sha256"
DOC = json.loads(FIXTURE.read_text(encoding="utf-8"))
DEFAULT_DATE = DOC["fixture"]["default_evaluation_date"]
TARGET = "jobops-policy@0.2.2"

# Classified mismatches (see docs/reports/JOBOPS_BLIND_VALIDATION_REPORT_2026-09-29.md).
# Keys are case / sequence ids; values are "<CLASS>:<id>". Strict: an xfail that
# starts passing turns the suite red.
KNOWN_MISMATCHES = {}

_SOURCE_KIND = {"linkedin": "JOB_BOARD", "naukri": "JOB_BOARD", "other": "JOB_BOARD", "ats": "EMPLOYER_ATS"}
_CLASSIFICATION = {"product": "PRODUCT", "ai_native": "AI_NATIVE", "gcc": "GCC", "enterprise": "ENTERPRISE_DIRECT",
                   "staffing": "STAFFING", "consultancy": "CONSULTANCY", "engineering_led": "ENGINEERING_LED",
                   "it_services": "IT_SERVICES"}
_ORDER = ("FAIL", "UNKNOWN", "PASS")


def _worst(*verdicts):
    for v in _ORDER:
        if v in verdicts:
            return v
    raise ValueError(verdicts)


# --------------------------------------------------------------- integrity

def test_frozen_fixture_hash():
    recorded = SHA_FILE.read_text(encoding="utf-8").split()[0]
    assert hashlib.sha256(FIXTURE.read_bytes()).hexdigest() == recorded, "blind fixture changed after freezing"


def test_target_policy_is_022():
    assert load_policy_version(TARGET).version == TARGET


# ----------------------------------------------------------------- adapter

def _obs_fields(p, *, idx):
    jd = p.get("jd_text")
    completeness = p.get("completeness")
    if completeness:
        completeness = {"full_jd": "FULL_JD", "search_only": "SEARCH_ONLY"}[completeness]
    else:
        completeness = "FULL_JD" if jd else "SEARCH_ONLY"
    kind = _SOURCE_KIND[p["source"]]
    url = p.get("requisition_url")
    fields = dict(source=p["source"], source_kind=kind, completeness=completeness,
                  raw_title=p.get("title"), raw_company=p.get("company"),
                  raw_location=p.get("location_text") or None, raw_work_mode=p.get("work_mode_text") or None,
                  raw_salary=p.get("compensation_text") or None, raw_employment_type=p.get("employment_text") or None,
                  raw_text=jd if completeness != "SEARCH_ONLY" else None,
                  source_posted_date=p.get("posted_date"),
                  observed_at=p.get("observed_at") or f"{p.get('posted_date') or DEFAULT_DATE}T06:00:00+00:00",
                  run_id=p.get("run_id") or f"blind-{idx}",
                  source_url=url, apply_url=p.get("apply_url"),
                  source_external_id=p.get("source_job_id") or (None if url else f"blind-{idx}"))
    if p.get("jd_language"):
        fields["language_detection"] = {"detected_language": p["jd_language"],
                                        "confidence": p.get("jd_language_confidence")}
    return fields


def _prepare(service, p, seen_companies, seen_fx):
    cls = _CLASSIFICATION.get(p.get("employer_type_detail") or p.get("employer_type_hint"))
    company = p.get("company")
    if cls and company and company not in seen_companies:
        service.classify_company(company, cls, "INFERRED_FROM_EVIDENCE", "blind:fixture-hint")
        seen_companies.add(company)
    if p.get("fx_currency"):
        key = (p["fx_currency"], p["fx_snapshot_date"])
        if key not in seen_fx:
            service.add_fx_rate(p["fx_currency"], p["fx_rate_to_inr"], p["fx_snapshot_date"], "blind-fixture")
            seen_fx.add(key)


def _project(result):
    dims = {k: v["verdict"] for k, v in result["eligibility_dimensions"].items()}
    rel_dim = result["eligibility_dimensions"]["employment_relationship"]
    employer = dims["employer_type"]
    if rel_dim["verdict"] == "FAIL" and rel_dim["rule_id"] in ("REL-R06", "REL-R07"):
        employer = _worst(employer, "FAIL")
    return {"geography": dims["geography"], "compensation": dims["compensation"], "language": dims["language"],
            "employment_type": _worst(dims["employment_type"], dims["employment_relationship"]),
            "employer_type": employer,
            "relevance": result["relevance"]["relevance_label"],
            # the blind schema writes "no experience requirement stated" as null
            "experience_label": (None if result["relevance"]["experience_signal"] == "UNKNOWN_FIT"
                                 else result["relevance"]["experience_signal"]),
            "lane": result["lane"], "flags": set(result["flags"])}


def _compare(expected, actual, requisition=None):
    """Return a list of (field, expected, actual) mismatches; UNDETERMINED is skipped."""
    out = []
    for field, exp in expected.items():
        if exp == "UNDETERMINED" or field in ("undetermined_question", "applies_to_steps"):
            continue
        if field == "must_have_flags":
            missing = [f for f in exp if f not in actual["flags"]]
            if missing:
                out.append((field, exp, sorted(actual["flags"])))
        elif field == "must_not_have_flags":
            present = [f for f in exp if f in actual["flags"]]
            if present:
                out.append((field, exp, sorted(actual["flags"])))
        elif field == "newness":
            if requisition["newness_state"] != exp:
                out.append((field, exp, requisition["newness_state"]))
        elif field == "first_seen_at":
            if datetime.fromisoformat(requisition["first_seen_at"]) != datetime.fromisoformat(exp):
                out.append((field, exp, requisition["first_seen_at"]))
        elif field in actual:
            if actual[field] != exp:
                out.append((field, exp, actual[field]))
    return out


def evaluate_case(case):
    p = case["posting"]
    service = fresh_service(load_policy_version(TARGET))
    service.clock = lambda: p.get("evaluation_date") or DEFAULT_DATE
    _prepare(service, p, set(), set())
    result = service.ingest(observation(**_obs_fields(p, idx=case["id"])))
    return _compare(case["expected"], _project(result["evaluation"]["result"]), result["requisition"])


def run_sequence(seq):
    """Execute a sequence; return a list of (step, field, expected, actual) mismatches."""
    service = fresh_service(load_policy_version(TARGET))
    companies, fxs = set(), set()
    req_of_step, req_of_item = {}, {}
    mismatches = []
    for st in seq["steps"]:
        date = st.get("evaluation_date") or DEFAULT_DATE
        service.clock = lambda d=date: d
        exp = dict(st.get("expected") or {})
        if st.get("observation"):
            p = st["observation"]
            _prepare(service, p, companies, fxs)
            res = service.ingest(observation(**_obs_fields(p, idx=f"{seq['id']}-{st['step']}")))
            rid = res["requisition_id"]
            req_of_step[st["step"]] = rid
            if p.get("queue_item_id"):
                req_of_item[p["queue_item_id"]] = rid
            steps = exp.pop("applies_to_steps", [st["step"]])
            if "same_requisition_as_step" in exp:
                other = exp.pop("same_requisition_as_step")
                if req_of_step[other] != rid:
                    mismatches.append((st["step"], "same_requisition_as_step", other, "different requisition"))
            if exp.pop("separate_requisitions", False):
                ids = [req_of_step[s] for s in steps]
                if len(set(ids)) != len(ids):
                    mismatches.append((st["step"], "separate_requisitions", True, ids))
            fx_warn = exp.pop("digest_fx_freshness_warning", None)
            for s in steps:
                r = req_of_step[s]
                ev = service.current_evaluation(r)["result"]
                for m in _compare(exp, _project(ev), repo.get_requisition(service.conn, r)):
                    mismatches.append((s,) + m)
            if fx_warn is not None:
                warned = rid in {w["requisition_id"] for w in plan_day(service, date)["fx_warnings"]}
                if warned != fx_warn:
                    mismatches.append((st["step"], "digest_fx_freshness_warning", fx_warn, warned))
        elif st.get("action") == "run_daily_review_queue":
            plan = plan_day(service, date)
            item_of_req = {v: k for k, v in req_of_item.items()}
            today = plan["review_today"]

            def ids(units):
                out = []
                for u in units:
                    members = u.get("member_requisition_ids") or [u["requisition_id"]]
                    out.append("+".join(sorted(item_of_req.get(m, m) for m in members)))
                return out

            actual = {"surfaced_today_count": len(today), "review_cap_slots_used": len(today),
                      "grouped_review_cards": sum(1 for u in today + plan["review_carried"] if u.get("group_id")),
                      "surfaced_order": ids(today), "surfaced_ids": sorted(ids(today)),
                      "carried_ids": sorted(ids(plan["review_carried"])),
                      "parked_ids": sorted(ids([u for u in plan["lanes"]["PARKED"] if u.get("parked_by") == "overflow"]))}
            for field, e in exp.items():
                if e == "UNDETERMINED" or field == "undetermined_question":
                    continue
                if field == "must_not_park":
                    parked = set(actual["parked_ids"])
                    if parked & set(e):
                        mismatches.append((st["step"], field, e, sorted(parked)))
                    continue
                a = actual[field]
                e_cmp = sorted(e) if field in ("surfaced_ids", "carried_ids", "parked_ids") else e
                if a != e_cmp:
                    mismatches.append((st["step"], field, e, a))
            # Fixture queue assumption: items surfaced on a day are handled that day.
            for u in today:
                for m in u.get("member_requisition_ids") or [u["requisition_id"]]:
                    service.record_review_decision(m, "SKIP", actor="human",
                                                   note="blind adapter: surfaced item handled per fixture queue assumption")
    return mismatches


# ------------------------------------------------------------------- tests

def _param(item):
    reason = KNOWN_MISMATCHES.get(item["id"])
    marks = [pytest.mark.xfail(strict=True, reason=reason)] if reason else []
    return pytest.param(item, id=item["id"], marks=marks)


@pytest.mark.parametrize("case", [_param(c) for c in DOC["cases"]])
def test_blind_case(case):
    mismatches = evaluate_case(case)
    assert not mismatches, (case["id"], mismatches)


@pytest.mark.parametrize("seq", [_param(s) for s in DOC["sequences"]])
def test_blind_sequence(seq):
    mismatches = run_sequence(seq)
    assert not mismatches, (seq["id"], mismatches)
