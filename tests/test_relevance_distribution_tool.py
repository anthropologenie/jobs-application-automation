"""Offline relevance distribution tool: three synthetic JDs, deterministic, thresholds untouched."""

import hashlib
import json
import sys
from pathlib import Path

from evaluation.policy_loader import POLICY_PATHS, load_policy_v02
from v02_support import no_network  # noqa: F401

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "tools"))
import relevance_distribution as tool  # noqa: E402


def _write(folder: Path):
    (folder / "a_strong.txt").write_text(
        "AI Engineer\nBuild a RAG pipeline with embeddings, BM25 hybrid retrieval and LLM evaluation of groundedness.\n",
        encoding="utf-8")
    (folder / "b_moderate.txt").write_text(
        "Machine Learning Engineer\nIntegrate LLM APIs and write prompt templates for summarization.\n", encoding="utf-8")
    (folder / "c_weak.txt").write_text(
        "QA Engineer\nManual regression test execution with Selenium for our web app.\n", encoding="utf-8")
    (folder / "d_nojd.txt").write_text("Applied AI Engineer\n", encoding="utf-8")


def test_distribution_counts_and_evidence(tmp_path):
    _write(tmp_path)
    report = tool.distribution(tmp_path, load_policy_v02())
    assert report["counts"] == {"STRONG": 1, "MODERATE": 1, "WEAK": 1, "NOT_ASSESSED": 1}
    by = {r["file"]: r for r in report["files"]}
    strong = by["a_strong.txt"]
    assert strong["label"] == "STRONG" and strong["capability_clusters"] == ["A", "B", "C"]
    assert strong["title_tier"] == "TIER_1"
    body = (tmp_path / "a_strong.txt").read_text(encoding="utf-8")
    assert all(s["quoted_span"] in body for s in strong["evidence_spans"])
    assert by["b_moderate.txt"]["title_tier"] == "TIER_2"
    assert by["c_weak.txt"]["matched_terms"] == []
    assert by["d_nojd.txt"]["label"] == "NOT_ASSESSED" and by["d_nojd.txt"]["evidence_spans"] == []


def test_deterministic_and_does_not_modify_policy(tmp_path, capsys):
    _write(tmp_path)
    before = {v: hashlib.sha256(p.read_bytes()).hexdigest() for v, p in POLICY_PATHS.items()}
    tool.main([str(tmp_path), "--json"])
    first = capsys.readouterr().out
    tool.main([str(tmp_path), "--json"])
    assert capsys.readouterr().out == first
    assert json.loads(first)["thresholds"] == {"strong_min_specific_terms": 3, "strong_min_clusters": 2,
                                               "moderate_min_specific_terms": 2}
    assert {v: hashlib.sha256(p.read_bytes()).hexdigest() for v, p in POLICY_PATHS.items()} == before
    tool.main([str(tmp_path)])
    assert "STRONG" in capsys.readouterr().out
