"""
P10 REVIEW presentation tiers. Presentation metadata only.

A tier is computed from the stored evaluation of a job that is already REVIEW (the engine's REVIEW lane, or a
SHORTLIST job held in REVIEW for an incomplete JD). It never changes a verdict, flag, relevance label,
experience label, lane or queue state, and the engine never reads it.

First match wins:

  T1 Nearly Ready                  every dimension PASS, except possibly employer UNKNOWN with exactly
                                   EMPLOYER_UNCLASSIFIED and/or compensation UNKNOWN with exactly COMP_UNDISCLOSED;
                                   no other review-routing flag (so no identity / source / work-mode conflict,
                                   no BELOW_TARGET ...); complete JD; experience not STRETCH.
  T2 Stretch Experience Only       as T1, but experience is STRETCH.
  T3 Location / Work Mode Unclear  geography UNKNOWN, or a WORK_MODE_CONFLICT flag.
  T4 Other                         everything else.

Within a tier: STRONG > MODERATE > other relevance, NEW > UPDATED > SEEN_BEFORE, then stated pay
IN_TARGET / ABOVE_TARGET before any other pay state (not stated, below target, unclear), then job id.
"""

from collections import Counter
from typing import Any, Dict, List, Optional

from .sourcing import ALL_DIMS

TIERS = ("T1", "T2", "T3", "T4")
TIER_LABEL = {"T1": "T1 — Nearly Ready", "T2": "T2 — Stretch Experience Only",
              "T3": "T3 — Location / Work Mode Unclear", "T4": "T4 — Other"}

# The only UNKNOWNs T1 / T2 tolerate: dimension -> the single flag that must explain it.
NARROW_UNKNOWN = {"employer_type": "EMPLOYER_UNCLASSIFIED", "compensation": "COMP_UNDISCLOSED"}
STRETCH_FLAG = "EXPERIENCE_STRETCH"
NARROW_REVIEW_FLAGS = set(NARROW_UNKNOWN.values()) | {STRETCH_FLAG}
WORK_MODE_CONFLICT = "WORK_MODE_CONFLICT"
TARGET_PAY = {"IN_TARGET", "ABOVE_TARGET"}
NOT_TARGET_PAY = {"BELOW_TARGET", "COMPENSATION_REVIEW"}

_REL = ["STRONG", "MODERATE"]
_NEW = ["NEW", "UPDATED", "SEEN_BEFORE"]


def _all_flags(j: Dict[str, Any]) -> set:
    return set(j["review_flags"]) | {f for d in ALL_DIMS for f in j["dims"][d]["flags"]}


def is_stretch(j: Dict[str, Any]) -> bool:
    return j.get("experience") == "STRETCH" or STRETCH_FLAG in j["review_flags"]


def _narrow(j: Dict[str, Any]) -> bool:
    """Only employer-unclassified / pay-not-stated uncertainty remains (T1 / T2 eligibility)."""
    if j["jd_status"] != "JD_COMPLETE" or j["identity_uncertain"]:
        return False
    for d in ALL_DIMS:
        v = j["dims"][d]
        if v["verdict"] == "PASS":
            continue
        if v["verdict"] == "UNKNOWN" and d in NARROW_UNKNOWN and set(v["flags"]) == {NARROW_UNKNOWN[d]}:
            continue
        return False
    return not (set(j["review_flags"]) - NARROW_REVIEW_FLAGS)


def tier_of(j: Dict[str, Any]) -> str:
    if _narrow(j):
        return "T2" if is_stretch(j) else "T1"
    if j["dims"]["geography"]["verdict"] == "UNKNOWN" or WORK_MODE_CONFLICT in _all_flags(j):
        return "T3"
    return "T4"


def pay_rank(j: Dict[str, Any]) -> int:
    """0: stated pay IN_TARGET / ABOVE_TARGET. 1: anything else (not stated, below target, unclear)."""
    c = j["dims"]["compensation"]
    flags = set(c["flags"])
    return 0 if c["verdict"] == "PASS" and flags & TARGET_PAY and not flags & NOT_TARGET_PAY else 1


def order_key(j: Dict[str, Any]) -> tuple:
    return (TIERS.index(j["tier"]),
            _REL.index(j["relevance"]) if j["relevance"] in _REL else len(_REL),
            _NEW.index(j["newness"]) if j["newness"] in _NEW else len(_NEW),
            pay_rank(j), j["job_id"])


# ---------------------------------------------------------------- blockers

_FLAG_TEXT = {
    "EMPLOYER_UNCLASSIFIED": "employer unclassified", "STAFFING": "employer is staffing",
    "CONSULTANCY": "employer is a consultancy", "IT_SERVICES": "employer is IT services",
    "EMPLOYER_TYPE_REVIEW": "staffing relationship", "EOR": "employer of record",
    "COMP_UNDISCLOSED": "pay not stated", "COMP_NON_NUMERIC": "pay not numeric",
    "COMP_NON_BASE_ONLY": "only non-base pay stated", "COMP_UPPER_BOUND_ONLY": "pay upper bound only",
    "COMP_LOCATION_ADJUSTED_NO_INDIA_BAND": "no India pay band", "COMP_NOT_ANNUALIZABLE": "pay not annualizable",
    "COMP_PERIOD_UNSTATED": "pay period not stated", "FX_RATE_UNAVAILABLE": "FX rate unavailable",
    "FX_STALE": "FX rate stale", "COMP_UNCLASSIFIED": "pay unclassified",
    "SALARY_RANGE_STRADDLES_FLOOR": "pay range straddles floor", "CTC_RANGE_STRADDLES_FLOOR": "CTC range straddles floor",
    "BELOW_TARGET": "pay below target", "COMPENSATION_REVIEW": "pay range starts below target",
    "WORK_MODE_CONFLICT": "work mode conflict",
    "EMPLOYMENT_UNSTATED": "employment type not stated", "EMPLOYMENT_MIXED": "employment type mixed",
    "EMPLOYMENT_SOURCE_CONFLICT": "employment type conflict", "LONG_TERM_DIRECT_CONTRACT": "long-term direct contract",
    "CONTRACT_DURATION_UNSTATED": "contract duration not stated",
    "LANGUAGE_UNCERTAIN": "language unknown",
    "EXPERIENCE_STRETCH": "experience stretch", "IDENTITY_UNCERTAIN": "identity uncertain",
    "SOURCE_CONFLICT": "source conflict", "RELEVANCE_TITLE_PRIOR": "relevance from title only",
}
_DIM_UNKNOWN = {"geography": "geography unclear", "compensation": "pay unclear", "employment_type": "employment unknown",
                "employer_type": "employer unknown", "language": "language unknown",
                "employment_relationship": "relationship unknown"}


def _flag_text(flag: str) -> str:
    return _FLAG_TEXT.get(flag, flag.lower().replace("_", " "))


def blockers(j: Dict[str, Any]) -> List[str]:
    """Why this job is in REVIEW, derived only from its stored verdicts, flags and JD status."""
    out: List[str] = []

    def add(text):
        if text not in out:
            out.append(text)

    review = set(j["review_flags"])
    for d in ALL_DIMS:
        v = j["dims"][d]
        if v["verdict"] == "UNKNOWN":
            if d == "geography":
                # "work mode conflict", else "geography unclear (<its flag>)".
                if WORK_MODE_CONFLICT in v["flags"]:
                    add(_flag_text(WORK_MODE_CONFLICT))
                else:
                    detail = ", ".join(f.lower().replace("_", " ") for f in v["flags"])
                    add(f"{_DIM_UNKNOWN[d]} ({detail})" if detail else _DIM_UNKNOWN[d])
                continue
            named = [f for f in v["flags"] if f in review or f in _FLAG_TEXT]
            for f in named:
                add(_flag_text(f))
            if not named:
                add(_DIM_UNKNOWN[d])
        elif v["verdict"] == "PASS":
            for f in v["flags"]:
                if f in review:
                    add(_flag_text(f))
    covered = {f for d in ALL_DIMS for f in j["dims"][d]["flags"]}
    for f in j["review_flags"]:
        if f not in covered:
            add(_flag_text(f))
    if j["relevance"] == "NOT_ASSESSED":
        add("relevance not assessed")
    if j["jd_status"] == "JD_MISSING":
        add("JD missing")
    elif j["jd_status"] == "JD_TRUNCATED":
        add("JD truncated")
    return out


# ---------------------------------------------------------------- annotate / order

def annotate(j: Dict[str, Any]) -> Dict[str, Any]:
    j["tier"] = tier_of(j)
    j["blockers"] = blockers(j)
    return j


def order_units(units: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """A unit (single job or identity-uncertain group) ranks by its best-ranked member."""
    for u in units:
        u["members"] = sorted(u["members"], key=order_key)
        u["tier"] = u["members"][0]["tier"]
        u["key"] = order_key(u["members"][0])
    return sorted(units, key=lambda u: u["key"])


def count_by_tier(jobs: List[Dict[str, Any]]) -> Dict[str, int]:
    c = Counter(j["tier"] for j in jobs)
    return {t: c[t] for t in TIERS}


def largest_blocker(jobs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    c = Counter(b for j in jobs for b in j["blockers"])
    if not c:
        return None
    top = sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))
    return {"blocker": top[0][0], "count": top[0][1], "top": [{"blocker": b, "count": n} for b, n in top[:5]]}
