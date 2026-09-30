#!/usr/bin/env python3
"""
Offline relevance distribution (P1a calibration instrument).

    python3 tools/relevance_distribution.py path/to/jd_folder [--policy jobops-policy@0.2.1] [--json]

Each *.txt file: first line = title, remaining lines = JD body. An empty body
is NOT_ASSESSED. Output: label counts, then per file the title, label, title
tier, matched AI-specific terms, capability clusters and verbatim evidence spans.

Deterministic, offline, read-only: no network, no LLM, no randomness, no DB,
and it never modifies policy. Thresholds are read from the policy artifact
unchanged.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation.policy_loader import load_policy_v02, load_policy_version  # noqa: E402
from evaluation.textutil import split_sentences  # noqa: E402
from relevance.labeller import extract_relevance_spans, label_relevance, title_tier  # noqa: E402

LABELS = ("STRONG", "MODERATE", "WEAK", "NOT_ASSESSED")


def analyse_file(path: Path, policy) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    title = lines[0].strip() if lines else ""
    body = "\n".join(lines[1:]).strip()
    if body:
        split = policy.regex("sentence_split", policy.section("lexicon")["sentence_split"])
        spans = extract_relevance_spans(split_sentences(body, split), policy)
    else:
        spans = None
    out = label_relevance(spans, policy)
    return {"file": path.name, "title": title, "label": out["relevance_label"],
            "title_tier": title_tier(title, out["relevance_label"], policy),
            "matched_terms": sorted({s["matched"] for s in out["evidence_spans"] if s["specific"]}, key=str.lower),
            "capability_clusters": out["capability_clusters"],
            "evidence_spans": [{"cluster": s["cluster"], "matched": s["matched"], "specific": s["specific"],
                                "quoted_span": s["quoted_span"]} for s in out["evidence_spans"]]}


def distribution(folder: Path, policy) -> Dict[str, Any]:
    files = sorted(p for p in Path(folder).glob("*.txt") if p.is_file())
    results: List[Dict[str, Any]] = [analyse_file(p, policy) for p in files]
    counts = {label: sum(1 for r in results if r["label"] == label) for label in LABELS}
    return {"policy_version": policy.version,
            "thresholds": policy.section("relevance")["thresholds"],
            "counts": counts, "total": len(results), "files": results}


def render_text(report: Dict[str, Any]) -> str:
    out = [f"policy {report['policy_version']} · thresholds {report['thresholds']}", ""]
    out += [f"{label:<13}{report['counts'][label]}" for label in LABELS] + [f"{'TOTAL':<13}{report['total']}", ""]
    for r in report["files"]:
        out.append(f"== {r['file']} · {r['title']} · {r['label']} · {r['title_tier']}")
        out.append(f"   clusters: {', '.join(r['capability_clusters']) or '-'}")
        out.append(f"   matched:  {', '.join(r['matched_terms']) or '-'}")
        for s in r["evidence_spans"]:
            kind = "AI" if s["specific"] else ("QA" if s["cluster"] == "TRADITIONAL_QA" else "support")
            out.append(f"   [{s['cluster']}/{kind}] {s['matched']!r}: {s['quoted_span']}")
        out.append("")
    return "\n".join(out)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Offline relevance label distribution over plain-text JDs.")
    parser.add_argument("folder")
    parser.add_argument("--policy", help="Policy version, e.g. jobops-policy@0.2.0 (default: the active default).")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    policy = load_policy_version(args.policy) if args.policy else load_policy_v02()
    report = distribution(Path(args.folder), policy)
    print(json.dumps(report, indent=2, ensure_ascii=False) if args.json else render_text(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
