"""
Evidence extraction: one observation -> append-only evidence drafts.

Extraction records FACTS (what the posting said, verbatim, and where). It never
decides a verdict; the policy rule tables do that from the stored facts, so a
new policy version can be replayed over stored observations without recrawling.

Posting text is untrusted data. Nothing here follows instructions in it or
fetches a URL found in it.
"""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from geo import PlaceIndex
from relevance.labeller import extract_relevance_spans

from . import compensation
from .textutil import any_match, content_hash, split_sentences

EXTRACTOR_CODE_VERSION = "extract@2.1.0"


@dataclass
class EvidenceDraft:
    dimension: str
    evidence_type: str
    strength: str              # PRIMARY | CONTEXT
    quoted_span: Optional[str]
    value: Dict[str, Any]
    source_field: str


def extractor_version(policy) -> str:
    return f"{policy.version}+{EXTRACTOR_CODE_VERSION}"


def _place_dicts(places) -> List[Dict[str, Any]]:
    return [{"kind": p.kind, "ref": p.ref, "country": p.country, "text": p.text} for p in places]


def _office_days(sentence: str, policy) -> Optional[int]:
    lex = policy.section("lexicon")
    words = lex["number_words"]
    for p in policy.regexes("office_days", lex["office_days"]):
        m = p.search(sentence)
        if m:
            tok = m.group(1).lower()
            return int(tok) if tok.isdigit() else words.get(tok)
    return None


def _words(text: str, policy, cfg) -> List[str]:
    lowered = text.lower()
    for pattern, repl in cfg["normalize"]:
        lowered = policy.regex("geo.hyb.norm", pattern).sub(repl, lowered)
    return policy.regex("geo.hyb.word", cfg["word_pattern"]).findall(lowered)


def _standalone(sentence: str, m: "re.Match[str]") -> bool:
    """'AI Engineer (Hybrid)', 'AI Engineer - Hybrid': the token is set off by punctuation on both sides."""
    before, after = sentence[:m.start()].rstrip(), sentence[m.end():].lstrip()
    return (not before or before[-1] in "(-\u2013\u2014|,:/[") and (not after or after[0] in ")-\u2013\u2014|,/]")


def hybrid_usage(sentence: str, policy, *, office_cue: bool, structured: str) -> List[str]:
    """
    0.2.2 (P3 §9-§11): classify every 'hybrid' token in `sentence` as WORK,
    TECHNICAL or UNCLASSIFIED from its context, using lexicon.hybrid_semantics.
    `structured` is "field" (work-mode / location field or a location line),
    "title", or "" (JD body).
    """
    cfg = policy.section("lexicon")["hybrid_semantics"]
    n = cfg["window_words"]
    work_after, tech_after = set(cfg["work_terms_after"]), set(cfg["technical_terms_after"])
    weak_after = set(cfg["weak_technical_terms_after"])
    work_before, tech_before = set(cfg["work_terms_before"]), set(cfg["technical_terms_before"])
    out = []
    for m in policy.regex("geo.hyb.token", cfg["token"]).finditer(sentence):
        after = _words(sentence[m.end():], policy, cfg)[:n]
        before = list(reversed(_words(sentence[:m.start()], policy, cfg)))[:n]
        right = next(("WORK" if w in work_after else "TECHNICAL" if w in tech_after else "WEAK"
                      for w in after if w in work_after or w in tech_after or w in weak_after), None)
        left = next(("WORK" if w in work_before else "TECHNICAL"
                     for w in before if w in work_before or w in tech_before), None)
        if right in ("WORK", "TECHNICAL"):
            usage = right
        elif right == "WEAK":
            usage = "WORK" if (left == "WORK" or office_cue) else "TECHNICAL"
        elif left:
            usage = left
        elif office_cue:
            usage = "WORK"
        elif structured == "field" or (structured == "title" and _standalone(sentence, m)):
            usage = "WORK"
        else:
            usage = "UNCLASSIFIED"
        out.append(usage)
    return out


def _geography(sentences: List[str], listing: Optional[str], policy, places: PlaceIndex,
               work_mode: Optional[str] = None, title: Optional[str] = None) -> List[EvidenceDraft]:
    lex = policy.section("lexicon")
    rx = lambda k: policy.regexes("geo." + k, lex[k])  # noqa: E731
    out: List[EvidenceDraft] = []
    # 0.2.2: work-mode source precedence and contextual 'hybrid'. Older policies
    # lack these sections and keep their original behaviour byte-for-byte.
    sources = lex.get("work_mode_sources")
    rank_of = {f: i + 1 for i, f in enumerate(sources["order"])} if sources else {}
    semantic = "hybrid_semantics" in lex

    def analyse(sentence: str, field: str, forced_listing: bool) -> Optional[EvidenceDraft]:
        remote = bool(any_match(rx("remote"), sentence))
        onsite = bool(any_match(rx("onsite"), sentence))
        days = _office_days(sentence, policy)
        hybrid_usages = None
        if semantic:
            structured = ("field" if field in ("raw_work_mode", "raw_location") or any_match(rx("location_line"), sentence)
                          else "title" if field == "raw_title" else "")
            hybrid_usages = hybrid_usage(sentence, policy, office_cue=days is not None or onsite,
                                         structured=structured)
            hybrid = "WORK" in hybrid_usages
        else:
            hybrid = bool(any_match(rx("hybrid"), sentence))
        relocation = bool(any_match(rx("relocation"), sentence)) and not any_match(rx("relocation_negation"), sentence)
        visa = bool(any_match(rx("visa"), sentence)) and not any_match(rx("visa_negation"), sentence)
        auth_m = any_match(rx("work_authorization"), sentence)
        res_m = any_match(rx("residence_requirement"), sentence)
        is_location_line = forced_listing or bool(any_match(rx("location_line"), sentence))
        if hybrid:
            mode = "HYBRID"
        elif onsite and days is not None and days < 5:
            mode = "HYBRID"
        elif onsite and remote:
            mode = "CONFLICTING"
        elif onsite:
            mode = "ONSITE"
        elif remote:
            mode = "REMOTE"
        else:
            mode = None
        if not (mode or relocation or visa or auth_m or res_m or is_location_line):
            return None
        found = places.find(sentence)
        value = {
            "mode": mode, "places": _place_dicts(found), "office_days": days,
            "flexible": bool(any_match(rx("flexible_hybrid"), sentence)),
            "relocation": relocation, "visa": visa,
            "work_authorization": bool(auth_m),
            "work_authorization_places": _place_dicts(places.find(sentence[auth_m.end():])) if auth_m else [],
            "residence_places": _place_dicts(places.find(sentence[res_m.end():])) if res_m else [],
            "is_listing": mode is None and not (relocation or visa or auth_m or res_m),
        }
        if rank_of:
            value["source_rank"] = rank_of[field]
            if hybrid_usages:
                value["hybrid_usage"] = hybrid_usages
        strength = "CONTEXT" if value["is_listing"] else "PRIMARY"
        return EvidenceDraft("geography", "geography.statement", strength, sentence, value, field)

    for s in sentences:
        d = analyse(s, "raw_text", False)
        if d:
            out.append(d)
    if listing:
        d = analyse(listing, "raw_location", True)
        if d:
            out.append(d)
    if rank_of and work_mode and "raw_work_mode" in rank_of:
        d = analyse(work_mode, "raw_work_mode", False)
        if d:
            out.append(d)
    if rank_of and title and "raw_title" in rank_of:
        d = analyse(title, "raw_title", False)
        # A title contributes a stated work mode only, never a listing or a residence rule.
        if d and d.value["mode"]:
            out.append(d)
    return out


def _timezone(sentences: List[str], policy) -> List[EvidenceDraft]:
    lex = policy.section("lexicon")
    tz_tokens = policy.section("geo")["timezone_tokens"]
    out = []
    for s in sentences:
        if not any_match(policy.regexes("tz", lex["timezone"]), s):
            continue
        regions = []
        for region, tokens in tz_tokens.items():
            for tok in tokens:
                flags = 0 if tok.isupper() else re.I
                if re.search(rf"(?<!\w){re.escape(tok)}(?!\w)", s, flags):
                    regions.append(region)
                    break
        if regions:
            out.append(EvidenceDraft("timezone", "timezone.requirement", "PRIMARY", s,
                                     {"regions": sorted(set(regions))}, "raw_text"))
    return out


def _employment(sentences: List[str], policy) -> List[EvidenceDraft]:
    lex = policy.section("lexicon")
    excl = policy.regexes("emp.excl", lex["employment_cue_exclusions"])
    out = []
    for s in sentences:
        cleaned = s
        for p in excl:
            cleaned = p.sub(" ", cleaned)
        kinds = [k for k, pats in lex["employment"].items()
                 if any_match(policy.regexes("emp." + k, pats), cleaned)]
        if not kinds:
            continue
        months = None
        for p in policy.regexes("emp.duration", lex["contract_duration"]):
            m = p.search(cleaned)
            if m:
                n = int(m.group(1))
                months = n * 12 if "year" in m.group(0).lower() else n
                break
        direct = bool(any_match(policy.regexes("emp.direct", lex["direct_contract"]), cleaned))
        out.append(EvidenceDraft("employment_type", "employment.statement", "PRIMARY", s,
                                 {"kinds": kinds, "contract_months": months, "direct": direct}, "raw_text"))
    return out


def _relationship(sentences: List[str], policy, employment_sentences: Optional[List[str]] = None) -> List[EvidenceDraft]:
    """Relationship signals from the JD body, and (0.2.2, lexicon.relationship_fields) the employment field."""
    lex = policy.section("lexicon")["relationship"]
    out = []
    tagged = [(s, "raw_text") for s in sentences] + [(s, "raw_employment_type") for s in employment_sentences or []]
    for s, field in tagged:
        signals = [k for k, pats in lex.items() if any_match(policy.regexes("rel." + k, pats), s)]
        if signals:
            out.append(EvidenceDraft("employment_relationship", "relationship.signal", "PRIMARY", s,
                                     {"signals": signals}, field))
    return out


def _employer(sentences: List[str], policy) -> List[EvidenceDraft]:
    lex = policy.section("lexicon")["employer_signals"]
    out = []
    for s in sentences:
        signals = [k for k, pats in lex.items() if any_match(policy.regexes("empr." + k, pats), s)]
        if signals:
            out.append(EvidenceDraft("employer_type", "employer.signal", "PRIMARY", s,
                                     {"signals": signals}, "raw_text"))
    return out


def _language(sentences: List[str], text: Optional[str], detection: Optional[Dict[str, Any]], policy) -> List[EvidenceDraft]:
    lex = policy.section("lexicon")["language"]
    out = []
    for s in sentences:
        for key, conf_key in (("required", "required_confidence"), ("weak_requirement", "weak_requirement_confidence")):
            for p in policy.regexes("lang." + key, lex[key]):
                m = p.search(s)
                if m and m.group("lang"):
                    out.append(EvidenceDraft("language", "language.requirement", "PRIMARY", s,
                                             {"language": m.group("lang").lower(), "confidence": lex[conf_key],
                                              "pattern_class": key}, "raw_text"))
                    break
        for p in policy.regexes("lang.preferred", lex["preferred"]):
            m = p.search(s)
            if m and m.group("lang"):
                out.append(EvidenceDraft("language", "language.preference", "PRIMARY", s,
                                         {"language": m.group("lang").lower()}, "raw_text"))
                break
    if detection:
        out.append(EvidenceDraft("language", "language.detection", "PRIMARY", None,
                                 {"detected_language": detection.get("detected_language"),
                                  "confidence": detection.get("confidence"),
                                  "detector": detection.get("detector", "supplied_with_observation")},
                                 "language_detection"))
    elif text:
        words = [w.strip(".,:;()").lower() for w in text.split()]
        words = [w for w in words if w]
        if len(words) >= 20:
            stop = set(lex["english_stopwords"])
            ratio = sum(1 for w in words if w in stop) / len(words)
            if ratio >= lex["heuristic_english_ratio"]:
                detected, conf = "en", round(min(ratio * 4, 0.99), 3)
            else:
                detected, conf = "und", min(policy.param("heuristic_language_max_confidence"), 0.9)
            out.append(EvidenceDraft("language", "language.detection", "PRIMARY", None,
                                     {"detected_language": detected, "confidence": conf,
                                      "detector": "stopword_heuristic", "english_ratio": round(ratio, 4)},
                                     "raw_text"))
    return out


def _experience(sentences: List[str], policy) -> List[EvidenceDraft]:
    lex = policy.section("lexicon")
    ctx = policy.regexes("exp.ctx", lex["experience_context"])
    pats = lex["experience"]
    for s in sentences:
        if not any_match(ctx, s):
            continue
        m = policy.regex("exp.range", pats["range"]).search(s)
        if m:
            return [EvidenceDraft("experience", "experience.requirement", "PRIMARY", s,
                                  {"shape": "RANGE", "min": int(m.group(1)), "max": int(m.group(2))}, "raw_text")]
        m = policy.regex("exp.plus", pats["plus"]).search(s)
        if m:
            n = int(next(g for g in m.groups() if g))
            return [EvidenceDraft("experience", "experience.requirement", "PRIMARY", s,
                                  {"shape": "PLUS", "min": n, "max": None}, "raw_text")]
        m = policy.regex("exp.point", pats["point"]).search(s)
        if m:
            n = int(m.group(1))
            return [EvidenceDraft("experience", "experience.requirement", "PRIMARY", s,
                                  {"shape": "POINT", "value": n, "min": n, "max": n}, "raw_text")]
    return []


def extract(obs: Dict[str, Any], policy, places: PlaceIndex) -> List[EvidenceDraft]:
    """All evidence for one stored observation row (dict with raw_* fields)."""
    split = policy.regex("sentence_split", policy.section("lexicon")["sentence_split"])
    text = obs.get("raw_text")
    sentences = split_sentences(text, split)
    extra = [v for v in (obs.get("raw_salary"), obs.get("raw_employment_type")) if v]
    all_sentences = sentences + [s for v in extra for s in split_sentences(v, split)]
    drafts: List[EvidenceDraft] = []

    if obs.get("raw_title"):
        drafts.append(EvidenceDraft("title", "title", "PRIMARY", obs["raw_title"],
                                    {"title": obs["raw_title"]}, "raw_title"))
    drafts += _geography(sentences, obs.get("raw_location"), policy, places,
                         obs.get("raw_work_mode"), obs.get("raw_title"))
    drafts += _timezone(sentences, policy)
    for s in all_sentences:
        for clause in compensation.parse_clauses(s, policy):
            strength = "PRIMARY" if clause["kind"] == "FIGURE" else "CONTEXT"
            drafts.append(EvidenceDraft("compensation", "compensation.clause", strength,
                                        clause["quoted_span"], clause, "raw_text"))
    drafts += _employment(all_sentences, policy)
    rel_fields = policy.section("lexicon").get("relationship_fields", {}).get("fields", ["raw_text"])
    emp_sentences = (split_sentences(obs.get("raw_employment_type"), split)
                     if "raw_employment_type" in rel_fields else None)
    drafts += _relationship(sentences, policy, emp_sentences)
    drafts += _employer(sentences, policy)
    drafts += _language(sentences, text, obs.get("language_detection"), policy)
    drafts += _experience(sentences, policy)
    if text:
        drafts.append(EvidenceDraft("relevance", "relevance.jd", "PRIMARY", None,
                                    {"jd_hash": content_hash(text),
                                     "spans": extract_relevance_spans(sentences, policy)}, "raw_text"))
    return drafts
