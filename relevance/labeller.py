"""Relevance labeller v1: term spans -> label, title tier, seniority."""

from typing import Any, Dict, List, Optional

from evaluation.textutil import normalize_words


def extract_relevance_spans(sentences: List[str], policy) -> List[Dict[str, Any]]:
    """Every cluster-term and traditional-QA match, with its verbatim sentence."""
    cfg = policy.section("relevance")
    spans: List[Dict[str, Any]] = []
    for idx, sentence in enumerate(sentences):
        for cluster, spec in sorted(cfg["clusters"].items()):
            for term in spec["terms"]:
                m = policy.regex("rel.term", term["pattern"]).search(sentence)
                if m:
                    spans.append({"cluster": cluster, "term": term["pattern"], "matched": m.group(0),
                                  "specific": term["specific"], "sentence_index": idx,
                                  "quoted_span": sentence})
        for pattern in cfg["traditional_qa_terms"]:
            m = policy.regex("rel.qa", pattern).search(sentence)
            if m:
                spans.append({"cluster": "TRADITIONAL_QA", "term": pattern, "matched": m.group(0),
                              "specific": False, "sentence_index": idx, "quoted_span": sentence})
    return spans


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
