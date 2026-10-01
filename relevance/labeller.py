"""Relevance labeller v1: term spans -> label, title tier, seniority."""

from typing import Any, Dict, List, Optional

from evaluation.textutil import normalize_words


def extract_relevance_spans(sentences: List[str], policy) -> List[Dict[str, Any]]:
    """Every cluster-term and traditional-QA match, with its verbatim sentence."""
    cfg = policy.section("relevance")
    contexts = cfg.get("context_patterns")  # 0.2.3 (Owner Addendum E8); absent before
    spans: List[Dict[str, Any]] = []
    for idx, sentence in enumerate(sentences):
        if contexts is None:
            for cluster, spec in sorted(cfg["clusters"].items()):
                for term in spec["terms"]:
                    m = policy.regex("rel.term", term["pattern"]).search(sentence)
                    if m:
                        spans.append({"cluster": cluster, "term": term["pattern"], "matched": m.group(0),
                                      "specific": term["specific"], "sentence_index": idx,
                                      "quoted_span": sentence})
        else:
            spans += _contextual_spans(sentence, idx, cfg, contexts, policy)
        for pattern in cfg["traditional_qa_terms"]:
            m = policy.regex("rel.qa", pattern).search(sentence)
            if m:
                spans.append({"cluster": "TRADITIONAL_QA", "term": pattern, "matched": m.group(0),
                              "specific": False, "sentence_index": idx, "quoted_span": sentence})
    return spans


def _contextual_spans(sentence: str, idx: int, cfg, contexts, policy) -> List[Dict[str, Any]]:
    """
    0.2.3 span extraction (Owner Addendum E8).

    * A term marked "context" counts only when an AI anchor (relevance.context_patterns) matches
      the same sentence OUTSIDE the term's own text, so a term never anchors itself.
    * Overlapping matches within one cluster are one piece of evidence: the longest match wins
      ("evaluation suites" is one evaluation term, not also "evaluation"), so a single phrase can
      never count as several distinct terms of the same capability. Overlaps across clusters keep
      the pre-0.2.3 behaviour ("LLM evaluation" is application + evaluation evidence).
    """
    found = []
    for cluster, spec in sorted(cfg["clusters"].items()):
        for term in spec["terms"]:
            m = policy.regex("rel.term", term["pattern"]).search(sentence)
            if not m:
                continue
            anchor = None
            ctx = term.get("context")
            if ctx:
                masked = sentence[:m.start()] + " " * (m.end() - m.start()) + sentence[m.end():]
                anchor = next((a.group(0) for a in (policy.regex("rel.ctx", p).search(masked)
                                                    for p in contexts[ctx]) if a), None)
                if anchor is None:
                    continue
            found.append((m.start(), m.end(), cluster, term, m.group(0), anchor))
    kept, taken = [], []
    for start, end, cluster, term, text, anchor in sorted(found, key=lambda f: (-(f[1] - f[0]), f[0], f[2])):
        if any(start < e and s < end and c == cluster for s, e, c in taken):
            continue
        taken.append((start, end, cluster))
        span = {"cluster": cluster, "term": term["pattern"], "matched": text, "specific": term["specific"],
                "sentence_index": idx, "quoted_span": sentence}
        if anchor:
            span["context_anchor"] = anchor
        kept.append((start, span))
    return [span for _, span in sorted(kept, key=lambda k: (k[0], k[1]["cluster"]))]


def label_relevance(spans: Optional[List[Dict[str, Any]]], policy) -> Dict[str, Any]:
    """
    STRONG / MODERATE / WEAK from distinct AI-specific terms; NOT_ASSESSED when
    no JD was captured (spans is None). No numeric score is produced.
    """
    if spans is None:
        return {"relevance_label": "NOT_ASSESSED", "capability_clusters": [],
                "specific_terms": [], "evidence_spans": [], "traditional_qa_terms": [],
                "reason": "No JD text captured; relevance is not guessed from the title."}
    th = policy.section("relevance")["thresholds"]
    specific = sorted({(s["cluster"], s["term"]) for s in spans if s["specific"]})
    clusters = sorted({c for c, _ in specific})
    if len(specific) >= th["strong_min_specific_terms"] and len(clusters) >= th["strong_min_clusters"]:
        label = "STRONG"
    elif len(specific) >= th["moderate_min_specific_terms"]:
        label = "MODERATE"
    else:
        label = "WEAK"
    evidence = []
    seen = set()
    for s in spans:
        key = (s["quoted_span"], s["matched"].lower())
        if key in seen:
            continue
        seen.add(key)
        evidence.append({"cluster": s["cluster"], "matched": s["matched"], "specific": s["specific"],
                         "quoted_span": s["quoted_span"]})
    return {"relevance_label": label, "capability_clusters": clusters,
            "specific_terms": [t for _, t in specific],
            "evidence_spans": evidence,
            "traditional_qa_terms": sorted({s["matched"].lower() for s in spans if s["cluster"] == "TRADITIONAL_QA"}),
            "reason": f"{len(specific)} distinct AI-specific terms across {len(clusters)} clusters"}


def _stripped_title(title: str, policy) -> str:
    words = normalize_words(title).split()
    strip = set(policy.section("lexicon")["title_strip_words"])
    return " " + " ".join(w for w in words if w not in strip) + " "


def title_tier(title: Optional[str], relevance_label: str, policy) -> str:
    """TIER_1 / TIER_2 by title list; TIER_3 when neither but the JD is STRONG/MODERATE; else NONE."""
    if title:
        norm = _stripped_title(title, policy)
        tiers = policy.section("relevance")["title_tiers"]
        for tier in ("TIER_1", "TIER_2"):
            for entry in tiers[tier]:
                for variant in entry["variants"]:
                    if f" {normalize_words(variant)} " in norm:
                        return tier
    return "TIER_3" if relevance_label in ("STRONG", "MODERATE") else "NONE"


def seniority_signal(title: Optional[str], policy) -> str:
    if not title:
        return "NONE"
    for level, patterns in policy.section("lexicon")["seniority"].items():
        for p in patterns:
            if policy.regex("sen", p).search(title):
                return level
    return "NONE"
