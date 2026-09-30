"""
Deterministic, rules-based relevance labeller v1 (Phase B).

No LLM, no embeddings, no network, no score. Output is exactly one of STRONG,
MODERATE, WEAK or NOT_ASSESSED, with the verbatim JD spans that support it.
All term lists and thresholds are read from the policy artifact's `relevance`
section. Relevance never produces an eligibility verdict.
"""

from .labeller import (  # noqa: F401
    extract_relevance_spans,
    label_relevance,
    seniority_signal,
    title_tier,
)
