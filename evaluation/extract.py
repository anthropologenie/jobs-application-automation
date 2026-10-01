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

from . import compensation, officedays
from .textutil import any_match, content_hash, split_sentences

EXTRACTOR_CODE_VERSION = "extract@2.3.0"


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
    negation = set(cfg.get("negation_terms_before", []))  # 0.2.3 (Addendum E6); absent before
    out = []
    for m in policy.regex("geo.hyb.token", cfg["token"]).finditer(sentence):
        after = _words(sentence[m.end():], policy, cfg)[:n]
        before = list(reversed(_words(sentence[:m.start()], policy, cfg)))[:n]
        if negation and any(w in negation for w in before):
            out.append("NEGATED")  # "not a hybrid role": never a work arrangement
            continue
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

    normalised = "office_day_normalization" in lex  # 0.2.3 (Addendum E6)

    def analyse(sentence: str, field: str, forced_listing: bool) -> Optional[EvidenceDraft]:
        remote = bool(any_match(rx("remote"), sentence))
        onsite = bool(any_match(rx("onsite"), sentence))
        days_info = None
        if normalised:
            days_info = officedays.normalize(sentence, policy, structured=field != "raw_text")
            days = days_info["days"] if days_info else None
        else:
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
        # 0.2.3: a normalised office-day count with an attendance cue states a work mode by itself
        # ("office on Tuesdays and Thursdays", "Friday is our WFH day", "five days a week at our
        # Chennai centre"); a WFH-derived count is never read as a remote statement.
        days_mode = None
        if days_info and not hybrid and (onsite or days_info["office_cue"] or days_info["wfh_derived"]
                                         or field != "raw_text"):
            days_mode = "HYBRID" if days < policy.param("standard_work_week_days") else "ONSITE"
        relocation = bool(any_match(rx("relocation"), sentence)) and not any_match(rx("relocation_negation"), sentence)
        visa = bool(any_match(rx("visa"), sentence)) and not any_match(rx("visa_negation"), sentence)
        auth_m = any_match(rx("work_authorization"), sentence)
        res_m = any_match(rx("residence_requirement"), sentence)
        explicit = None  # 0.2.4 (OR-79): explicit India / worldwide eligibility statement
        for scope_name, pats in (lex.get("explicit_eligibility") or {}).items():
            if any_match(policy.regexes("geo.explicit." + scope_name, pats), sentence):
                explicit = scope_name
                break
        is_location_line = forced_listing or bool(any_match(rx("location_line"), sentence)) \
            or bool(lex.get("eligibility_line") and any_match(rx("eligibility_line"), sentence)) or bool(explicit)
        if hybrid:
            mode = "HYBRID"
        elif days_mode:
            mode = days_mode
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
        if explicit:
            value["explicit_eligibility"] = explicit
        if days_info:
            value["office_days_method"] = days_info["method"]
            value["office_days_span"] = days_info["span"]
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


def _employment_by_field(tagged: List[tuple], policy) -> List[EvidenceDraft]:
    """
    0.2.3 (Owner Addendum E1): employment evidence with its source field.

    The structured employment field keeps the single-word vocabulary (lexicon.employment:
    "Contract", "Permanent", "Internship" are unambiguous there). The JD body and the salary
    line use lexicon.employment_jd, which only recognises explicit multi-word employment
    statements ("contract role", "12-month contract", "temporary position"), so words such
    as "contract testing", "smart contract" or "contract-review assistant" never produce a
    kind. Direct-employment evidence ("employed directly by", "on our payroll") is a
    posting-level fact: it is recorded from any sentence, as CONTEXT evidence.
    """
    lex = policy.section("lexicon")
    excl = policy.regexes("emp.excl", lex["employment_cue_exclusions"])
    out = []
    for s, field in tagged:
        cleaned = s
        for p in excl:
            cleaned = p.sub(" ", cleaned)
        labelled = field != "raw_employment_type" and any_match(
            policy.regexes("emp.label_line", lex.get("employment_label_line", [])), s)
        vocab = lex["employment"] if (field == "raw_employment_type" or labelled) else lex["employment_jd"]
        kinds = [k for k, pats in vocab.items() if any_match(policy.regexes(f"emp.{field}." + k, pats), cleaned)]
        direct_m = any_match(policy.regexes("emp.direct", lex["direct_contract"]), cleaned)
        if not kinds and not direct_m:
            continue
        months = None
        if kinds:
            for p in policy.regexes("emp.duration", lex["contract_duration"]):
                m = p.search(cleaned)
                if m:
                    n = int(m.group(1))
                    months = n * 12 if "year" in m.group(0).lower() else n
                    break
        out.append(EvidenceDraft("employment_type", "employment.statement" if kinds else "employment.direct",
                                 "PRIMARY" if kinds else "CONTEXT", s,
                                 {"kinds": kinds, "contract_months": months, "direct": bool(direct_m),
                                  "source_field": field,
                                  "direct_span": direct_m.group(0) if direct_m else None}, field))
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
    elif text and lex.get("detector"):
        out.append(_detect_language(text, lex["detector"], policy))
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


_WORD = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)?", re.UNICODE)
_LATIN_DIACRITIC = re.compile(r"[àáâãäåæçèéêëìíîïñòóôõöøùúûüýÿßœ]", re.I)


def _non_latin(word: str) -> bool:
    return any(ord(ch) > 0x024F for ch in word)


def _detect_language(text: str, cfg: Dict[str, Any], policy) -> EvidenceDraft:
    """
    0.2.3 built-in document-language detector (Owner Addendum E4). Deterministic and local.

    Evidence for English is the count of English function words; evidence for another
    language is the count of that language's function words, plus words written with Latin
    diacritics, plus words in a non-Latin script. Product names, tool names and technical
    vocabulary are neither, so they never lower English confidence. With no function-word
    evidence at all, all-ASCII text is read as English (there is no non-English evidence).

        foreign share <= english_max_foreign_share        -> en,  confidence 1 - share (>= .95)
        foreign share >= non_english_min_foreign_share    -> xx,  confidence = share
        otherwise (mixed)                                  -> und, confidence = 1 - share
    """
    text = policy.regex("lang.strip", cfg["strip_pattern"]).sub(" ", text)  # URLs, e-mails, domains
    words = [w.lower() for w in _WORD.findall(text)]
    english = set(cfg["english_function_words"])
    foreign = {lang: set(ws) for lang, ws in cfg["foreign_function_words"].items()}
    en_hits = sum(1 for w in words if w in english)
    per_lang = {lang: sum(1 for w in words if w in ws) for lang, ws in foreign.items()}
    counted = {w for ws in foreign.values() for w in ws}
    raw_tokens = _WORD.findall(text)
    proper = {t.lower() for t in raw_tokens if t[:1].isupper() and _LATIN_DIACRITIC.search(t)}
    diacritic = [w for w in words if w not in counted and w not in proper and not _non_latin(w)
                 and _LATIN_DIACRITIC.search(w)]
    script = [w for w in words if _non_latin(w)]
    # Scripts written without spaces (Japanese, Chinese, Thai) put a whole clause in one token, so
    # non-Latin evidence is measured in characters (about three per word) rather than in tokens.
    script_units = sum(max(1, sum(1 for ch in w if ord(ch) > 0x024F) // 3) for w in script)
    fo_raw = sum(per_lang.values()) + len(diacritic) + script_units
    # An isolated stray token is noise, not evidence of another language.
    fo_hits = fo_raw if fo_raw >= cfg["min_foreign_evidence"] or not en_hits else 0
    total = en_hits + fo_hits
    value: Dict[str, Any] = {"detector": "function_words_v2", "word_count": len(words), "foreign_raw": fo_raw,
                             "english_function_words": en_hits, "foreign_function_words": per_lang,
                             "diacritic_words": len(diacritic), "non_latin_script_words": len(script),
                             "non_latin_script_units": script_units,
                             "foreign_examples": sorted({w for w in words if w in counted} | set(diacritic) | set(script))[:8]}
    if total == 0:
        if words and not script:
            share, detected, conf = 0.0, "en", float(cfg["no_evidence_ascii_confidence"])
        else:
            share, detected, conf = None, "und", 0.0
    else:
        share = fo_hits / total
        if total < cfg["min_evidence_words"] and fo_hits:
            detected, conf = "und", round(1 - share, 3)
        elif share <= cfg["english_max_foreign_share"]:
            detected, conf = "en", round(1 - share, 3)
        elif share >= cfg["non_english_min_foreign_share"]:
            if script and script_units >= sum(per_lang.values()):
                detected = "non_latin"
            else:
                detected = max(per_lang, key=lambda k: (per_lang[k], k)) if any(per_lang.values()) else "xx"
            conf = round(share, 3)
        else:
            detected, conf = "und", round(1 - share, 3)
    value.update({"detected_language": detected, "confidence": conf,
                  "foreign_share": None if share is None else round(share, 4)})
    return EvidenceDraft("language", "language.detection", "PRIMARY", None, value, "raw_text")


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
    if "employment_jd" in policy.section("lexicon"):
        tagged = ([(s, "raw_text") for s in sentences]
                  + [(s, "raw_salary") for s in split_sentences(obs.get("raw_salary"), split)]
                  + [(s, "raw_employment_type") for s in split_sentences(obs.get("raw_employment_type"), split)])
        drafts += _employment_by_field(tagged, policy)
    else:
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
