"""
Fact summarisers: stored evidence rows -> the fact dictionaries that the
policy rule tables match. Summaries are deterministic functions of evidence
(plus registry classification and dated FX), which is what makes evaluation
replayable. No verdict is decided here.
"""

from typing import Any, Callable, Dict, List, Optional, Tuple

from company.registry import resolve_classification
from geo.places import INDIA, PlaceIndex, PlaceRef

from . import compensation
from .textutil import normalize_words


def _refs(items: List[Dict[str, Any]]) -> List[PlaceRef]:
    return [PlaceRef(p["kind"], p["ref"], p["country"], p["text"]) for p in items]


# ------------------------------------------------------------------ geography

def _remote_scope(places: List[PlaceRef], listing: List[PlaceRef], index: PlaceIndex) -> str:
    def scope_of(ps: List[PlaceRef]) -> Optional[str]:
        if not ps:
            return None
        if any(p.kind == "WORLDWIDE" for p in ps):
            return "WORLDWIDE"
        if any(p.kind == "CITY" and p.country == INDIA and not p.is_bengaluru for p in ps):
            return "CITY_HUB_OTHER_INDIA"
        india_country = any(p.kind in ("COUNTRY", "STATE") and p.country == INDIA for p in ps)
        if india_country:
            return "INDIA_EXPLICIT"
        if any(p.is_bengaluru for p in ps):
            return "BENGALURU"
        if any(p.kind == "REGION" and index.region_contains(p.ref, INDIA) for p in ps):
            return "REGION_INCLUDES_INDIA_IMPLICIT"
        return "REGION_EXCLUDES_INDIA"

    direct = scope_of(places)
    if direct:
        return direct
    listed = scope_of(listing)
    if listed in ("INDIA_EXPLICIT", "BENGALURU"):
        return "UNQUALIFIED_INDIA_LISTING"
    if listed == "CITY_HUB_OTHER_INDIA":
        return "CITY_HUB_OTHER_INDIA"
    if listed in ("REGION_EXCLUDES_INDIA", "REGION_INCLUDES_INDIA_IMPLICIT"):
        return "UNQUALIFIED_FOREIGN_LISTING"
    if listed == "WORLDWIDE":
        return "WORLDWIDE"
    return "UNQUALIFIED_NO_LISTING"


def _residence_class(places: List[PlaceRef], index: PlaceIndex) -> Optional[str]:
    if not places:
        return None
    if any(p.kind == "CITY" and p.country == INDIA and not p.is_bengaluru for p in places):
        return "OTHER_INDIA"
    if any(p.kind in ("CITY", "COUNTRY") and p.country and p.country != INDIA for p in places):
        return "ABROAD"
    if any(p.kind == "REGION" and not index.region_contains(p.ref, INDIA) for p in places):
        return "ABROAD"
    if any(p.is_bengaluru for p in places):
        return "BENGALURU"
    return "INDIA"


def _resolve_mode(statements: List[Dict[str, Any]]) -> str:
    """
    One work mode for the posting.

    0.2.0 / 0.2.1 statements carry no source_rank: any two distinct modes are
    CONFLICTING. 0.2.2 statements carry source_rank (1 = structured work-mode
    field, 2 = location, 3 = title, 4 = JD body; P3 §8): the highest-precedence
    source that states a mode decides; two modes inside that source are
    CONFLICTING (as before); a lower-precedence source stating a different mode
    is a genuine cross-source contradiction, CONFLICTING_SOURCES (GEO-R25), never
    a silent override. Technical 'hybrid' never yields a mode, so it cannot
    create either conflict.
    """
    stated = [s for s in statements if s["mode"]]
    if not stated:
        return "NONE"
    if not any("source_rank" in s for s in stated):
        modes = sorted({s["mode"] for s in stated})
        return modes[0] if len(modes) == 1 else "CONFLICTING"
    top = min(s["source_rank"] for s in stated)
    top_modes = {s["mode"] for s in stated if s["source_rank"] == top}
    if len(top_modes) > 1:
        return "CONFLICTING"
    accepted = next(iter(top_modes))
    if any(s["mode"] != accepted for s in stated if s["source_rank"] > top):
        return "CONFLICTING_SOURCES"
    return accepted


def summarize_geography(rows: List[Dict[str, Any]], listing_rows: List[Dict[str, Any]],
                        index: PlaceIndex, auth_fallback_to_listing: bool = False) -> Dict[str, Any]:
    statements = [r["value"] for r in rows]
    listing = [p for r in listing_rows for p in _refs(r["value"]["places"])]
    listing += [p for s in statements if s["is_listing"] for p in _refs(s["places"])]
    mode = _resolve_mode(statements)
    all_places = [p for s in statements for p in _refs(s["places"])] + listing
    residence = [p for s in statements for p in _refs(s["residence_places"])]
    auth = [p for s in statements for p in _refs(s["work_authorization_places"])]
    relocation = any(s["relocation"] for s in statements)
    visa = any(s["visa"] for s in statements)
    obs_city = PlaceIndex.city_class(all_places)
    foreign_auth = (any(p.country != INDIA for p in auth if p.country)
                    or any(p.kind == "REGION" and not index.region_contains(p.ref, INDIA) for p in auth))
    # "Authorized to work in the country of this posting" names no country:
    # when the policy enables it, the posting's own places decide (0.2.1).
    unnamed_auth = any(s.get("work_authorization") and not s["work_authorization_places"] for s in statements)
    if auth_fallback_to_listing and unnamed_auth and not auth:
        foreign_auth = foreign_auth or obs_city == "ABROAD"
    facts: Dict[str, Any] = {
        "mode": mode,
        "relocation_abroad": relocation and obs_city == "ABROAD",
        "visa_sponsorship": visa,
        "foreign_work_authorization": foreign_auth,
        "residence_requirement": _residence_class(residence, index),
        "remote_scope": None, "city_class": None, "office_days": None, "flexible": False,
    }
    if mode == "REMOTE":
        remote_places = [p for s in statements if s["mode"] == "REMOTE" for p in _refs(s["places"])]
        facts["remote_scope"] = _remote_scope(remote_places, listing, index)
        explicit = sorted({s["explicit_eligibility"] for s in statements if s.get("explicit_eligibility")})
        if explicit:
            # 0.2.4 (OR-79, F2): an explicit "candidates in India / worldwide are eligible" statement lifts a
            # single-country lock and qualifies an unqualified or implicit remote scope (PASS). Against a
            # multi-country region lock it is a contradiction -> UNKNOWN (OI-052, recall-safe reading).
            facts["explicit_eligibility"] = explicit
            scope = facts["remote_scope"]
            if scope == "REGION_EXCLUDES_INDIA":
                foreign = [p for p in remote_places if p.country != INDIA or p.kind == "REGION"]
                single_country = bool(foreign) and all(p.kind == "COUNTRY" for p in foreign)
                facts["remote_scope"] = "EXPLICIT_ELIGIBILITY" if single_country else "REGION_LOCK_CONTRADICTED"
            elif scope in ("UNQUALIFIED_NO_LISTING", "UNQUALIFIED_FOREIGN_LISTING", "REGION_INCLUDES_INDIA_IMPLICIT"):
                facts["remote_scope"] = "EXPLICIT_ELIGIBILITY"
    if mode in ("HYBRID", "ONSITE"):
        mode_places = [p for s in statements if s["mode"] == mode for p in _refs(s["places"])]
        facts["city_class"] = PlaceIndex.city_class(mode_places) or PlaceIndex.city_class(listing)
        days = [s["office_days"] for s in statements if s["mode"] == mode and s["office_days"] is not None]
        facts["office_days"] = max(days) if days else None
        facts["flexible"] = any(s["flexible"] for s in statements if s["mode"] == mode)
    return facts


def geography_comparable(facts: Dict[str, Any]) -> Optional[Tuple]:
    if facts["mode"] in ("NONE",):
        return None
    return (facts["mode"], facts["remote_scope"], facts["city_class"], facts["office_days"])


def work_arrangement(facts: Dict[str, Any]) -> str:
    if facts["mode"] == "REMOTE":
        return "REMOTE"
    if facts["mode"] == "HYBRID" and facts["city_class"] == "BENGALURU":
        return "BENGALURU_HYBRID"
    if facts["mode"] in ("HYBRID", "ONSITE"):
        return "OTHER"
    return "UNKNOWN"


# --------------------------------------------------------------- compensation

def summarize_compensation(rows: List[Dict[str, Any]], policy, fx_lookup, as_of: str,
                           evaluation_date: Optional[str] = None):
    clauses = [r["value"] for r in rows]
    return compensation.summarize(clauses, policy, fx_lookup, as_of, evaluation_date)


# ------------------------------------------------------------- employment etc.

def summarize_employment(rows: List[Dict[str, Any]], policy) -> Dict[str, Any]:
    lex = policy.section("lexicon")
    order = list(lex["employment"].keys())
    kinds = {k for r in rows for k in r["value"]["kinds"]}
    kind = next((k for k in order if k in kinds), None)
    months = next((r["value"]["contract_months"] for r in rows if r["value"]["contract_months"] is not None), None)
    direct = any(r["value"]["direct"] for r in rows)
    conflict_cfg = lex.get("employment_source_conflicts")
    if conflict_cfg is None:
        return {"kind": kind, "contract_months": months, "direct": direct}
    # 0.2.3 (Owner Addendum E1): structured field evidence outranks free text; a genuine
    # contradiction between them is CONFLICTING (UNKNOWN + EMPLOYMENT_SOURCE_CONFLICT), never FAIL.
    structured = {k for r in rows if r["value"].get("source_field") == "raw_employment_type" for k in r["value"]["kinds"]}
    free = {k for r in rows if r["value"].get("source_field") != "raw_employment_type" for k in r["value"]["kinds"]}
    conflicting = sorted({f"{s}~{f}" for s in structured for f in free if f in conflict_cfg.get(s, [])})
    if conflicting:
        kind = "CONFLICTING"
    source = None
    if kind and kind != "CONFLICTING":
        source = "STRUCTURED_FIELD" if kind in structured else "JD_FREE_TEXT"
    return {"kind": kind, "contract_months": months, "direct": direct, "kind_source": source,
            "source_conflicts": conflicting}


def employment_comparable(facts: Dict[str, Any]) -> Optional[Tuple]:
    return None if facts["kind"] is None else (facts["kind"], facts["contract_months"])


def summarize_relationship(rows: List[Dict[str, Any]], employer_classification: str) -> Dict[str, Any]:
    signals = {s for r in rows for s in r["value"]["signals"]}
    facts = {k: (k in signals) for k in ("placement", "third_party_payroll", "independent_contractor",
                                         "b2b", "invoice", "hourly_contractor", "eor")}
    facts["employer_classification"] = employer_classification
    return facts


def summarize_employer(registry_records: List[Dict[str, Any]], rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    signals = sorted({s for r in rows for s in r["value"]["signals"]})
    resolved = resolve_classification(registry_records, signals)
    return {**resolved, "text_signals": signals}


def summarize_language(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    req = [r["value"] for r in rows if r["evidence_type"] == "language.requirement"
           and r["value"]["language"] != "english"]
    pref = [r["value"] for r in rows if r["evidence_type"] == "language.preference"
            and r["value"]["language"] != "english"]
    det = next((r["value"] for r in rows if r["evidence_type"] == "language.detection"), None)
    if det is None:
        doc_lang, doc_conf = "UNDETERMINED", None
    else:
        code = (det.get("detected_language") or "und").lower()
        doc_lang = "ENGLISH" if code == "en" else ("UNDETERMINED" if code in ("und", "") else "NON_ENGLISH")
        doc_conf = det.get("confidence")
    return {"required_non_english": bool(req),
            "required_confidence": max((v["confidence"] for v in req), default=None),
            "required_languages": sorted({v["language"] for v in req}),
            "preferred_non_english": bool(pref),
            "preferred_languages": sorted({v["language"] for v in pref}),
            "document_language": doc_lang, "document_confidence": doc_conf}


def experience_fit(rows: List[Dict[str, Any]], policy) -> Dict[str, Any]:
    cfg = policy.section("experience_fit")
    req = rows[0]["value"] if rows else {"shape": "NONE"}
    for rule in cfg["rules"]:
        if rule["shape"] != req["shape"]:
            continue
        if policy.matches(rule["when"], req):
            flags = [cfg["stretch_flag"]] if rule["label"] == "STRETCH" else []
            min_years = req.get("min")
            substantial = min_years is not None and min_years >= policy.param("parking_min_years")
            if substantial:
                flags.append("EXPERIENCE_SUBSTANTIAL_MISMATCH")
            return {"experience_fit": rule["label"], "rule_id": rule["rule_id"], "requirement": req,
                    "flags": flags, "substantial_mismatch": substantial,
                    "quoted_span": rows[0]["quoted_span"] if rows else None}
    raise RuntimeError("experience_fit rules have no catch-all for shape " + req["shape"])


def timezone_info(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    regions = sorted({g for r in rows for g in r["value"]["regions"]})
    return {"timezone_requirement": regions or None, "timezone_overlap_flag": bool(regions),
            "detected_timezone": regions, "evidence": [r["quoted_span"] for r in rows],
            "flags": [f"TIMEZONE_OVERLAP_{g}" for g in regions]}


def title_comparable(rows: List[Dict[str, Any]]) -> Optional[str]:
    return normalize_words(rows[0]["value"]["title"]) if rows else None
