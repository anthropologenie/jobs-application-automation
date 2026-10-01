"""
Office-day normalisation (jobops-policy@0.2.3, Owner Addendum E6).

Turns natural-language office-attendance statements into one number of office
days per week, with the method and the verbatim span that produced it:

    "3 days per week", "three days in a week", "twice a week"      -> weekly count
    "8 days a month"                                               -> monthly / monthly_weeks
    "Mon/Wed/Thu", "Tuesdays and Thursdays", "Monday through Thursday"
                                                                   -> weekday list (office cue)
    "Friday is our WFH day", "Tue/Fri from home", "3 WFH days"     -> standard week - WFH days
    "alternate days", "every other day"                            -> alternate_days_per_week
    "one fixed anchor day per week"                                -> weekly count

Everything is read from lexicon.office_day_normalization and the policy
parameters (standard_work_week_days, monthly_weeks); nothing is hardcoded here.
This module extracts facts only; the geography rule table decides the verdict.
Older policies do not have the lexicon section and never call this module.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri")


def _num_alt(cfg) -> str:
    return "|".join(sorted(cfg["number_words"], key=len, reverse=True))


def _rx(policy, key: str, pattern: str, cfg) -> "re.Pattern[str]":
    pattern = pattern.replace("{num}", _num_alt(cfg)).replace("{freq}", "|".join(cfg["frequency_words"]))
    return policy.regex("od." + key, pattern)


def _value(token: str, cfg) -> Optional[float]:
    tok = token.lower()
    if tok.isdigit():
        return float(tok)
    if tok in cfg["number_words"]:
        return float(cfg["number_words"][tok])
    if tok in cfg["frequency_words"]:
        return float(cfg["frequency_words"][tok])
    return None


def _first(policy, key: str, patterns: List[str], text: str, cfg) -> Optional["re.Match[str]"]:
    best = None
    for p in patterns:
        m = _rx(policy, key, p, cfg).search(text)
        if m and (best is None or m.start() < best.start()):
            best = m
    return best


def _not_attendance(policy, text: str, m: "re.Match[str]", cfg) -> bool:
    """
    0.2.5 (P8 Task 3): a day count next to a non-attendance context ("five working days to respond",
    "a five-day onboarding", "three days of training", "five-day on-call rotation") is not an office-day
    statement. The context is looked for among the `window_words` words on each side of the count.
    """
    ctx = cfg["count_context_exclusions"]
    n = ctx["window_words"]
    before = " ".join(re.findall(r"\S+", text[:m.start()])[-n:])
    after = " ".join(re.findall(r"\S+", text[m.end():])[:n])
    window = f"{before} {m.group(0)} {after}"
    return any(_rx(policy, "ctx_excl", p, cfg).search(window) for p in ctx["patterns"])


def _count(policy, key: str, patterns: List[str], text: str, cfg) -> Optional["re.Match[str]"]:
    """First count match; under 0.2.5 a count in a non-attendance context is skipped."""
    if "count_context_exclusions" not in cfg:
        return _first(policy, key, patterns, text, cfg)
    best = None
    for p in patterns:
        for m in _rx(policy, key, p, cfg).finditer(text):
            if _not_attendance(policy, text, m, cfg):
                continue
            if best is None or m.start() < best.start():
                best = m
            break
    return best


def _positions(policy, key: str, patterns: List[str], text: str, cfg) -> List[int]:
    out = []
    for p in patterns:
        out += [m.start() for m in _rx(policy, key, p, cfg).finditer(text)]
    return out


def _weekday_sets(sentence: str, policy, cfg, structured: bool) -> Tuple[set, set, Optional[str]]:
    """(office weekdays, WFH weekdays, span) from weekday tokens and ranges, each assigned to its nearest cue."""
    tok_rx = _rx(policy, "weekday", cfg["weekday_token"], cfg)
    tokens = []
    for m in tok_rx.finditer(sentence):
        day = next(k for k in _WEEKDAYS if m.group(k))
        tokens.append((m.start(), m.end(), day))
    if not tokens:
        return set(), set(), None
    joiner = _rx(policy, "joiner", "^" + cfg["range_joiner"] + "$", cfg)
    groups: List[Tuple[int, int, List[str]]] = []
    i = 0
    while i < len(tokens):
        s, e, d = tokens[i]
        if i + 1 < len(tokens) and joiner.match(sentence[e:tokens[i + 1][0]]):
            a, b = _WEEKDAYS.index(d), _WEEKDAYS.index(tokens[i + 1][2])
            if a < b:
                groups.append((s, tokens[i + 1][1], list(_WEEKDAYS[a:b + 1])))
                i += 2
                continue
        groups.append((s, e, [d]))
        i += 1
    office_pos = _positions(policy, "office_cue", cfg["office_cues"], sentence, cfg)
    wfh_pos = _positions(policy, "wfh_cue", cfg["wfh_cues"], sentence, cfg)
    if not office_pos and not wfh_pos and not structured:
        return set(), set(), None
    office, wfh = set(), set()
    for s, e, days in groups:
        d_office = min((abs(p - s) for p in office_pos), default=None)
        d_wfh = min((abs(p - s) for p in wfh_pos), default=None)
        if d_wfh is not None and (d_office is None or d_wfh < d_office):
            wfh.update(days)
        else:
            office.update(days)
    span = sentence[groups[0][0]:groups[-1][1]]
    return office, wfh, span


def normalize(sentence: str, policy, *, structured: bool) -> Optional[Dict[str, Any]]:
    """
    {days, method, span, office_cue, wfh_derived} for one sentence / field, or None.
    `structured` is True for the work-mode field, the location field and the title.
    """
    cfg = policy.section("lexicon")["office_day_normalization"]
    week = float(policy.param("standard_work_week_days"))
    office_cue = bool(_first(policy, "office_cue", cfg["office_cues"], sentence, cfg))

    def out(days, method, span, wfh_derived=False):
        days = round(max(0.0, min(days, week)), 2)
        return {"days": int(days) if days == int(days) else days, "method": method, "span": span,
                "office_cue": office_cue, "wfh_derived": wfh_derived}

    m = _count(policy, "alternate", cfg["alternate"], sentence, cfg)
    if m:
        return out(float(cfg["alternate_days_per_week"]), "ALTERNATE_DAYS", m.group(0))
    m = _count(policy, "wfh_count", cfg["wfh_count"], sentence, cfg)
    if m and _value(m.group("n"), cfg) is not None:
        return out(week - _value(m.group("n"), cfg), "WFH_DAYS_PER_WEEK", m.group(0), wfh_derived=True)
    m = _count(policy, "weekly", cfg["weekly_count"], sentence, cfg)
    if m and _value(m.group("n"), cfg) is not None:
        return out(_value(m.group("n"), cfg), "DAYS_PER_WEEK", m.group(0))
    m = _count(policy, "monthly", cfg["monthly_count"], sentence, cfg)
    if m and _value(m.group("n"), cfg) is not None:
        per_month = _value(m.group("n"), cfg)
        return out(per_month / float(policy.param("monthly_weeks")), "DAYS_PER_MONTH", m.group(0))
    office, wfh, span = _weekday_sets(sentence, policy, cfg, structured)
    extra = 0.0
    em = _count(policy, "extra", cfg["extra_days"], sentence, cfg)
    if em and _value(em.group("n"), cfg) is not None:
        extra = _value(em.group("n"), cfg)
    if office:
        return out(len(office) + extra, "WEEKDAY_LIST", span + (f" … {em.group(0)}" if extra else ""))
    if wfh:
        return out(week - len(wfh), "WFH_WEEKDAYS", span, wfh_derived=True)
    m = _count(policy, "all_weekdays", cfg["all_weekdays"], sentence, cfg)
    if m:
        return out(week, "ALL_WEEKDAYS", m.group(0))
    return None
