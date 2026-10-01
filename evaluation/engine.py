"""
The v0.2 evaluator: stored evidence + context -> one immutable evaluation.

Pure function of its inputs. Eligibility, relevance, preference, experience fit,
evidence completeness and lane are computed as separate outputs; the lane is
derived last, from already-computed dimensions, by the policy's lane table.
Newness is not an input and not an output (it belongs to the requisition), so a
changed newness state never forces a new evaluation.
"""

from typing import Any, Callable, Dict, List, Optional

from geo import PlaceIndex
from relevance.labeller import label_relevance, seniority_signal, title_tier

from . import dimensions as D
from . import compensation as C
from .newness import differs as newness_differs
from .selection import conflicts, select
from .textutil import stable_hash

EVALUATOR_VERSION = "evaluator@2.0.0"


def _verdict(policy, dimension: str, facts: Dict[str, Any]) -> Dict[str, Any]:
    rule = policy.first_match(dimension, facts)
    out = {"verdict": rule["verdict"], "rule_id": rule["rule_id"], "flags": list(rule["flags"]),
           "band": rule.get("band"), "facts": facts}
    if "evidence_gap" in rule:  # 0.2.4 (OR-80): missing | known, on UNKNOWN rules only
        out["evidence_gap"] = rule["evidence_gap"]
    return out


def _overall(verdicts: List[str]) -> str:
    for v in ("FAIL", "UNKNOWN", "PASS"):
        if v in verdicts:
            return v
    raise ValueError("no verdicts")


def _lane(policy, facts: Dict[str, Any]) -> Dict[str, Any]:
    for rule in policy.section("lanes")["rules"]:
        ok = True
        for key, expected in rule["when"].items():
            if key == "eligibility_any":
                ok = expected in facts["verdicts"]
            elif key == "review_flag_any":
                ok = bool(facts["review_flags"]) == expected
            else:
                ok = facts.get(key) == expected
            if not ok:
                break
        if ok:
            return {"lane": rule["lane"], "lane_rule": rule["rule_id"]}
    raise RuntimeError("lane table has no catch-all")


def evaluate(observations: List[Dict[str, Any]], evidence: List[Dict[str, Any]],
             context: Dict[str, Any], policy, places: PlaceIndex) -> Dict[str, Any]:
    fx_lookup: Callable = context.get("fx_lookup") or (lambda cur, as_of: None)
    used: Dict[str, Any] = {}
    content: Dict[str, Any] = {}

    def pick(dim, **kw):
        sel = select(observations, evidence, dim, **kw)
        used[dim] = {"observation_id": sel["observation"]["observation_id"] if sel else None,
                     "evidence_ids": [r["evidence_id"] for r in sel["rows"]] if sel else []}
        # The evaluation key hashes evidence CONTENT, so an identical re-sighting
        # (new ids, same facts) maps to the existing evaluation instead of a new one.
        content[dim] = [(r["evidence_type"], r["strength"], r["quoted_span"], r["value"])
                        for r in sel["rows"]] if sel else []
        return sel

    # ------------------------------------------------------------ geography
    geo_sel = pick("geography")
    geo_rows = geo_sel["rows"] if geo_sel else []
    listing_rows: List[Dict[str, Any]] = []
    if geo_sel and not any(r["value"]["is_listing"] for r in geo_rows):
        for obs, rows in geo_sel["candidates"][1:]:
            ctx = [r for r in rows if r["value"]["is_listing"]]
            if ctx:
                listing_rows = ctx
                used["geography"]["listing_evidence_ids"] = [r["evidence_id"] for r in ctx]
                content["geography_listing"] = [(r["quoted_span"], r["value"]) for r in ctx]
                break
    geo_facts = D.summarize_geography(geo_rows, listing_rows, places,
                                      bool(policy.params.get("work_authorization_fallback_to_listing")))
    geo = _verdict(policy, "geography", geo_facts)

    # ---------------------------------------------------------- compensation
    comp_sel = pick("compensation")
    as_of = (comp_sel["observation"]["observed_at"][:10] if comp_sel else None) or ""
    evaluation_date = context.get("evaluation_date")
    comp_facts, comp_norm_flags, fx_used = D.summarize_compensation(
        comp_sel["rows"] if comp_sel else [], policy, fx_lookup, as_of, evaluation_date)
    if fx_used:
        used["fx"] = fx_used
        # Hash the snapshot identity and its usable/stale state, not the day-by-day
        # age, so a requisition is re-evaluated only when the FX outcome changes.
        content["fx"] = {k: v for k, v in fx_used.items() if k not in ("fx_age_days", "fx_reference_date")}
        content["fx_stale"] = comp_facts.get("state") == "FX_STALE"
    comp = _verdict(policy, "compensation", comp_facts)

    # ------------------------------------------------------- employment type
    emp_sel = pick("employment_type")
    emp_facts = D.summarize_employment(emp_sel["rows"] if emp_sel else [], policy)
    emp = _verdict(policy, "employment_type", emp_facts)

    # ------------------------------------------------- employer / relationship
    empr_sel = pick("employer_type")
    empr_resolved = D.summarize_employer(context.get("classification_records", []),
                                         empr_sel["rows"] if empr_sel else [])
    used["employer_classification"] = {k: empr_resolved[k] for k in ("classification", "basis", "classification_id")}
    content["employer_classification"] = used["employer_classification"]
    rel_sel = pick("employment_relationship")
    rel_facts = D.summarize_relationship(rel_sel["rows"] if rel_sel else [], empr_resolved["classification"])
    rel = _verdict(policy, "employment_relationship", rel_facts)
    empr_facts = {"classification": empr_resolved["classification"]}
    if policy.params.get("employer_fail_on_third_party_relationship"):
        # 0.2.3 (Owner Addendum E5): third-party payroll / client placement is an EMPLOYER-type
        # failure in its own right, not merely an employment-type one.
        empr_facts["third_party_relationship"] = bool(rel_facts["placement"] or rel_facts["third_party_payroll"])
    empr = _verdict(policy, "employer_type", empr_facts)

    # ------------------------------------------------------------- language
    lang_sel = pick("language")
    lang_facts = D.summarize_language(lang_sel["rows"] if lang_sel else [])
    lang = _verdict(policy, "language", lang_facts)

    # ------------------------------------------- fit signals (never verdicts)
    exp_sel = pick("experience")
    exp = D.experience_fit(exp_sel["rows"] if exp_sel else [], policy)
    tz_sel = pick("timezone")
    tz = D.timezone_info(tz_sel["rows"] if tz_sel else [])
    title_sel = pick("title")
    title = title_sel["rows"][0]["value"]["title"] if title_sel else None
    rel_jd = pick("relevance")
    spans = rel_jd["rows"][0]["value"]["spans"] if rel_jd else None
    relevance = label_relevance(spans, policy)
    tier = title_tier(title, relevance["relevance_label"], policy)
    seniority = seniority_signal(title, policy)
    # 0.2.3 (Owner Addendum E7): a Tier 1 title is a prior, not proof. WEAK JD evidence that still
    # contains at least one AI-specific term goes to REVIEW with RELEVANCE_TITLE_PRIOR; a Tier 1 JD
    # with no AI-specific term stays WEAK (PARKED). The relevance label itself is not changed.
    title_prior = ("RELEVANCE_TITLE_PRIOR" in policy.review_flags and tier == "TIER_1"
                   and relevance["relevance_label"] == "WEAK" and bool(relevance["specific_terms"]))

    # -------------------------------------------------------------- conflicts
    source_conflicts = []
    tolerant = None
    if policy.section("source_authority").get("absent_detail_is_not_conflict"):  # 0.2.3
        tolerant = lambda a, b: newness_differs(a, b, True)  # noqa: E731
    source_conflicts += conflicts(title_sel, "title", D.title_comparable)
    source_conflicts += conflicts(geo_sel, "geography",
                                  lambda rows: D.geography_comparable(D.summarize_geography(rows, [], places)),
                                  tolerant)
    source_conflicts += conflicts(comp_sel, "compensation",
                                  lambda rows: C.comparable(D.summarize_compensation(rows, policy, fx_lookup, as_of,
                                                                                     evaluation_date)[0]))
    source_conflicts += conflicts(emp_sel, "employment_type",
                                  lambda rows: D.employment_comparable(D.summarize_employment(rows, policy)))

    # ---------------------------------------------------------- flags / lane
    dims = {"geography": geo, "language": lang, "compensation": comp, "employment_type": emp,
            "employment_relationship": rel, "employer_type": empr}
    flags = set()
    for d in dims.values():
        flags.update(d["flags"])
    flags.update(comp_norm_flags)
    flags.update(tz["flags"])
    flags.update(exp["flags"])
    if seniority != "NONE":
        flags.add(f"SENIORITY_{seniority}")
    flags.update(context.get("identity_flags", []))
    if title_prior:
        flags.add("RELEVANCE_TITLE_PRIOR")
    if source_conflicts:
        flags.add("SOURCE_CONFLICT")
    for f in flags:
        policy.assert_flag(f, "evaluation")
    review_flags = sorted(f for f in flags if f in policy.review_flags)
    verdicts = [d["verdict"] for d in dims.values()]
    parking_signal = exp["substantial_mismatch"] or seniority in policy.param("parking_seniority")
    lane = _lane(policy, {"duplicate": bool(context.get("duplicate")), "verdicts": verdicts,
                          "relevance": relevance["relevance_label"], "title_tier": tier,
                          "parking_signal": parking_signal, "review_flags": review_flags,
                          "relevance_title_prior": title_prior})

    unknown_dims = sorted(k for k, d in dims.items() if d["verdict"] == "UNKNOWN")
    completeness = {"unknown_dimension_count": len(unknown_dims), "unknown_dimensions": unknown_dims}
    if policy.params.get("completeness_counts_missing_only"):
        # 0.2.4 (OR-80, F3): only UNKNOWNs caused by missing information count as incomplete evidence.
        missing = sorted(k for k in unknown_dims if dims[k].get("evidence_gap") == "missing")
        completeness.update({"missing_evidence_count": len(missing), "missing_dimensions": missing,
                             "known_dimensions": sorted(k for k in unknown_dims if k not in missing)})
    preference = {
        "compensation_band": comp["band"],
        "employer_preference": policy.section("employer_preference").get(empr_resolved["classification"], "UNKNOWN"),
        "work_arrangement": D.work_arrangement(geo_facts),
    }
    conflict_content = [{k: v for k, v in c.items() if not k.endswith("_observation")} for c in source_conflicts]
    hash_inputs = {"policy_version": policy.version, "evaluator": EVALUATOR_VERSION, "evidence": content,
                   "identity_flags": sorted(context.get("identity_flags", [])),
                   "duplicate": bool(context.get("duplicate")),
                   "conflicts": conflict_content}
    return {
        "policy_version": policy.version,
        "evaluator_version": EVALUATOR_VERSION,
        "evidence_hash": stable_hash(hash_inputs),
        "eligibility_dimensions": {k: {"verdict": d["verdict"], "rule_id": d["rule_id"], "flags": d["flags"],
                                       "facts": d["facts"],
                                       **({"evidence_gap": d["evidence_gap"]} if "evidence_gap" in d else {})}
                                   for k, d in dims.items()},
        "eligibility_overall": _overall(verdicts),
        "relevance": {**relevance, "title_signal": tier,
                      **({"title_prior": title_prior} if "RELEVANCE_TITLE_PRIOR" in policy.review_flags else {}),
                      "experience_signal": exp["experience_fit"],
                      "experience_rule": exp["rule_id"], "seniority_signal": seniority,
                      "parking_signal": parking_signal},
        "preference_attributes": preference,
        "timezone": tz,
        "flags": sorted(flags),
        "review_flags": review_flags,
        "evidence_completeness": completeness,
        "source_conflicts": source_conflicts,
        "lane": lane["lane"],
        "lane_rule": lane["lane_rule"],
        "selected_evidence": used,
        "compensation_normalized": comp_facts,
        "fx_freshness": _fx_freshness(policy, fx_used),
    }


def _fx_freshness(policy, fx_used: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """FX age information for the digest (OI-040). None when no FX was involved."""
    if not fx_used or fx_used.get("fx_age_days") is None:
        return None
    age = fx_used["fx_age_days"]
    warn = policy.params.get("fx_digest_warning_age_days")
    limit = policy.params.get("fx_max_age_days")
    return {"fx_age_days": age, "fx_snapshot_date": fx_used["fx_snapshot_date"],
            "stale": limit is not None and age > limit,
            "digest_warning": warn is not None and age > warn and (limit is None or age <= limit)}
