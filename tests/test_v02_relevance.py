"""Relevance labeller v1: deterministic, no LLM, no score, verbatim spans, NOT_ASSESSED without a JD."""

import ast
from pathlib import Path

import pytest

from evaluation.policy_loader import load_policy_v02
from relevance.labeller import extract_relevance_spans, label_relevance, seniority_signal, title_tier
from v02_support import no_network  # noqa: F401

POLICY = load_policy_v02()
REPO = Path(__file__).resolve().parent.parent


def label(text):
    return label_relevance(extract_relevance_spans([text], POLICY), POLICY)


def test_exactly_twenty_tier1_titles():
    assert len(POLICY.section("relevance")["title_tiers"]["TIER_1"]) == 20


@pytest.mark.parametrize("title,expected", [
    ("AI Engineer", "TIER_1"), ("Senior Applied AI Engineer", "TIER_1"), ("Staff AI Engineer", "TIER_1"),
    ("LLMOps Engineer", "TIER_1"), ("AI Operations Engineer", "TIER_1"), ("Developer Productivity Engineer", "TIER_1"),
    ("GenAI Quality Engineer", "TIER_1"), ("AI Governance Engineer", "TIER_1"),
    ("Machine Learning Engineer", "TIER_2"), ("MLOps Engineer", "TIER_2"), ("AI Backend Engineer", "TIER_2"),
    ("AI Solutions Architect", "TIER_2"),
])
def test_title_tiers(title, expected):
    assert title_tier(title, "WEAK", POLICY) == expected


def test_tier3_needs_substantial_jd_and_title_alone_never_decides():
    assert title_tier("Software Engineer - Platform", "STRONG", POLICY) == "TIER_3"
    assert title_tier("Software Engineer - Platform", "WEAK", POLICY) == "NONE"
    # A Tier 1 title with a weak JD stays WEAK: the title is only a prior.
    assert label("Experience with AI tools. Work on exciting AI initiatives.")["relevance_label"] == "WEAK"


def test_labels_and_spans_are_verbatim():
    text = "Build a RAG pipeline with embeddings, BM25 hybrid retrieval and LLM evaluation of groundedness."
    out = label(text)
    assert out["relevance_label"] == "STRONG"
    assert out["capability_clusters"] == ["A", "B", "C"]
    assert all(s["quoted_span"] == text for s in out["evidence_spans"])
    assert all(s["matched"].lower() in text.lower() for s in out["evidence_spans"])


def test_moderate_and_weak():
    assert label("Integrate LLM APIs and write prompt templates.")["relevance_label"] == "MODERATE"
    assert label("Use an LLM occasionally.")["relevance_label"] == "WEAK"


def test_traditional_qa_is_never_strong_ai_evidence():
    out = label("Selenium UI regression testing, manual testing and test cases in TestRail for mobile apps.")
    assert out["relevance_label"] == "WEAK"
    assert out["traditional_qa_terms"]


def test_supporting_terms_alone_do_not_count():
    assert label("Python, FastAPI, Docker, CI/CD and Kubernetes for backend services.")["relevance_label"] == "WEAK"


def test_not_assessed_without_jd():
    out = label_relevance(None, POLICY)
    assert out["relevance_label"] == "NOT_ASSESSED" and out["evidence_spans"] == []


def test_deterministic():
    text = "Build multi-agent systems with LangGraph, tool calling and guardrails."
    assert label(text) == label(text)


def test_seniority_signals():
    assert seniority_signal("Principal AI Engineer", POLICY) == "PRINCIPAL"
    assert seniority_signal("AI Solutions Architect", POLICY) == "ARCHITECT"
    assert seniority_signal("AI Engineer", POLICY) == "NONE"


def test_no_llm_embedding_or_network_imports_in_v2_packages():
    forbidden = {"requests", "httpx", "urllib.request", "http.client", "socket", "openai", "anthropic",
                 "sentence_transformers", "transformers", "torch", "numpy", "sklearn", "faiss", "chromadb",
                 "langchain", "aiohttp"}
    for pkg in ("relevance", "evaluation", "geo", "company", "store", "sources", "digest", "ops", "tools"):
        for path in (REPO / pkg).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for n in names:
                    assert n not in forbidden and n.split(".")[0] not in forbidden, (path, n)
