"""
Compensation clause parsing (facts only) and summarisation (facts -> comparable
figure). No verdict is decided here; the policy rule table decides.

Fixes relative to v0.1 (audit C3):
  * "up to X" is an upper bound only (never a point figure);
  * the figure marker is token-safe (no "rs " inside "years");
  * a keyword with no figure is a claim only when it is a recognised
    non-numeric or non-base phrase ("compensation paths" is not a salary).

CTC is never converted to base. An INR monthly figure is annualised x12 and
flagged MONTHLY_ASSUMED (Phase B §5). A foreign figure is converted only with an
owner-maintained dated FX snapshot (OR-27); without one it is UNKNOWN.
"""

import re
from datetime import date
from typing import Any, Callable, Dict, List, Optional, Tuple

from .textutil import any_match

_NUMBER = re.compile(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)\s*([kK])?(?![\w])")
_CLAUSE_SPLIT = re.compile(r"[;()\[\]]|\n")
LAKH = 100_000


def _to_number(token: str, k: Optional[str]) -> Optional[float]:
    try:
        value = float(token.replace(",", ""))
    except ValueError:
        return None
    return value * 1000 if k else value


def parse_clauses(sentence: str, policy) -> List[Dict[str, Any]]:
    """Facts for every compensation clause in one sentence. Empty when none."""
    lex = policy.section("lexicon")["compensation"]
    rx = lambda key: policy.regexes("comp." + key, lex[key])  # noqa: E731
    keyword = any_match(rx("keywords"), sentence)
    currency_hit = any(any_match(policy.regexes("comp.cur." + c, pats), sentence)
                       for c, pats in lex["currency"].items())
    if not keyword and not currency_hit:
        return []
    out: List[Dict[str, Any]] = []
    sentence_india = bool(any_match(rx("india_band"), sentence))
    sentence_loc_adj = bool(any_match(rx("location_adjusted"), sentence))
    clauses = [c.strip() for c in _CLAUSE_SPLIT.split(sentence) if c and c.strip()]
    labelled = lex.get("labelled_clause_split")
    if labelled:  # 0.2.2: "Base: ₹25 LPA | CTC: ₹31 LPA" is two clauses, so base can win
        split = policy.regex("comp.labelled_split", labelled)
        clauses = [part.strip() for c in clauses for part in split.split(c) if part and part.strip()]
    for clause in clauses:
        fact = _parse_clause(clause, policy, lex, rx)
        if fact is None:
            continue
        fact["sentence_location_adjusted"] = sentence_loc_adj
        fact["sentence_mentions_india"] = sentence_india
        out.append(fact)
    return out


def _number_regex(policy, lex) -> "re.Pattern[str]":
    """0.2.1 declares its own number token (accepts '₹24L'); 0.2.0 keeps the original one for faithful replay."""
    pattern = lex.get("number_token")
    return policy.regex("comp.number", pattern) if pattern else _NUMBER


def _parse_clause(clause: str, policy, lex, rx) -> Optional[Dict[str, Any]]:
    currency = None
    for code, pats in lex["currency"].items():
        if any_match(policy.regexes("comp.cur." + code, pats), clause):
            currency = code
            break
    numbers: List[Tuple[int, float]] = []
    for m in _number_regex(policy, lex).finditer(clause):
        n = _to_number(m.group(1), m.group(2))
        if n is not None and n > 0:
            numbers.append((m.start(), n))
    loc_adj = bool(any_match(rx("location_adjusted"), clause))
    base = {"quoted_span": clause, "location_adjusted": loc_adj,
            "india_band": bool(any_match(rx("india_band"), clause))}
    if currency and numbers:
        period = None
        for name, pats in lex["period"].items():
            if any_match(policy.regexes("comp.period." + name, pats), clause):
                period = name
                break
        lakh = bool(any_match(rx("lakh_unit"), clause))
        values = [n for _, n in numbers[:2]]
        is_range = False
        if len(numbers) >= 2:
            between = clause[numbers[0][0]:numbers[1][0]]
            is_range = any(sep in between for sep in lex["range_separators"])
        if not is_range:
            values = values[:1]
        if lakh:
            values = [v * LAKH if v < 1000 else v for v in values]
        upper_only = bool(any_match(rx("upper_only"), clause)) and not is_range
        lower_only = bool(any_match(rx("lower_only"), clause)) and not is_range and not upper_only
        basis = "UNSPECIFIED"
        if any_match(rx("ctc"), clause):
            basis = "CTC"
        elif any_match(rx("base"), clause):
            basis = "BASE"
        return {**base, "kind": "FIGURE", "currency": currency, "period": period,
                "lakh_unit": lakh, "min": min(values), "max": max(values),
                "is_range": is_range, "upper_only": upper_only, "lower_only": lower_only,
                "basis": basis}
    if any_match(rx("non_base"), clause):
        return {**base, "kind": "NON_BASE"}
    if any_match(rx("non_numeric"), clause):
        return {**base, "kind": "NON_NUMERIC"}
    if loc_adj:
        return {**base, "kind": "LOCATION_ADJUSTED_NOTE"}
    return None


FxLookup = Callable[[str, str], Optional[Dict[str, Any]]]


def _age_days(reference: str, snapshot_date: str) -> int:
    return (date.fromisoformat(reference[:10]) - date.fromisoformat(snapshot_date[:10])).days


def summarize(clauses: List[Dict[str, Any]], policy, fx_lookup: FxLookup,
              as_of: str, evaluation_date: Optional[str] = None
              ) -> Tuple[Dict[str, Any], List[str], Optional[Dict[str, Any]]]:
    """
    Reduce one observation's clauses to the facts the rule table reads.

    Returns (facts, normalisation_flags, fx_used). Selection among clauses:
    India-tagged figure first, then BASE, then UNSPECIFIED salary, then CTC.

    FX (OR-27 / OI-040): the snapshot is looked up as of the observation date
    (0.2.0) or the evaluation date (0.2.1, `fx_reference_date: evaluation`).
    When `fx_max_age_days` is set, a snapshot older than that relative to the
    reference date is stale -> state FX_STALE (UNKNOWN, never FAIL).
    """
    figures = [c for c in clauses if c["kind"] == "FIGURE"]
    flags: List[str] = []
    if not figures:
        if any(c["kind"] == "NON_BASE" for c in clauses):
            return {"state": "NON_BASE_ONLY"}, flags, None
        if any(c["kind"] == "NON_NUMERIC" for c in clauses):
            return {"state": "NON_NUMERIC"}, flags, None
        return {"state": "ABSENT"}, flags, None

    india = [c for c in figures if c["india_band"]]
    pool = india or figures
    order = {"BASE": 0, "UNSPECIFIED": 1, "CTC": 2}
    chosen = sorted(enumerate(pool), key=lambda ic: (order[ic[1]["basis"]], ic[0]))[0][1]
    location_adjusted = any(c["location_adjusted"] or c["sentence_location_adjusted"] for c in clauses)

    facts: Dict[str, Any] = {"basis": "CTC" if chosen["basis"] == "CTC" else "SALARY",
                             "compensation_type": chosen["basis"],
                             "original_currency": chosen["currency"],
                             "original_min": chosen["min"], "original_max": chosen["max"],
                             "original_period": chosen["period"],
                             "quoted_span": chosen["quoted_span"],
                             "india_band_used": bool(india)}
    if chosen["upper_only"]:
        return {**facts, "state": "UPPER_BOUND_ONLY"}, flags, None
    if chosen["currency"] != "INR" and location_adjusted and not india:
        return {**facts, "state": "LOCATION_ADJUSTED_NO_INDIA_BAND"}, flags, None

    period = chosen["period"] or ("annual" if chosen["lakh_unit"] else None)
    lo, hi = chosen["min"], chosen["max"]
    if period is None:
        return {**facts, "state": "PERIOD_UNSTATED"}, flags, None
    if period == "monthly" and chosen["currency"] == "INR":
        mult = policy.param("monthly_multiplier")
        lo, hi = lo * mult, hi * mult
        flags.append("MONTHLY_ASSUMED")
    elif period != "annual":
        return {**facts, "state": "NOT_ANNUALIZABLE"}, flags, None

    fx_used = None
    if chosen["currency"] != "INR":
        use_eval_date = policy.params.get("fx_reference_date") == "evaluation"
        reference = (evaluation_date if use_eval_date and evaluation_date else as_of)
        fx_used = fx_lookup(chosen["currency"], reference)
        if fx_used is None:
            return {**facts, "state": "FX_RATE_UNAVAILABLE"}, flags, None
        max_age = policy.params.get("fx_max_age_days")
        if max_age is not None:
            age = _age_days(reference, fx_used["fx_snapshot_date"])
            fx_used = {**fx_used, "fx_age_days": age, "fx_reference_date": reference[:10]}
            if age > max_age:
                return {**facts, "state": "FX_STALE", "fx": fx_used}, flags, fx_used
        lo, hi = lo * fx_used["rate"], hi * fx_used["rate"]
    if chosen["basis"] == "UNSPECIFIED" and chosen["currency"] == "INR":
        flags.append("COMP_BASIS_UNSTATED")

    shape = "POINT" if (not chosen["is_range"] and not chosen["lower_only"]) else "RANGE"
    max_inr = None if chosen["lower_only"] else int(round(hi))
    facts.update({"state": "FIGURE", "shape": shape, "min_inr": int(round(lo)),
                  "max_inr": max_inr, "normalized_inr_annual_base_min": int(round(lo)),
                  "normalized_inr_annual_base_max": max_inr,
                  "fx": fx_used})
    return facts, flags, fx_used


def comparable(facts: Dict[str, Any]) -> Optional[Tuple]:
    if facts.get("state") != "FIGURE":
        return None
    return (facts["basis"], facts["min_inr"], facts["max_inr"])
