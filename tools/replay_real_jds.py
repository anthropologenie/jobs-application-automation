#!/usr/bin/env python3
"""
Offline real-JD replay (P6).

    python3 tools/replay_real_jds.py INPUT [--mapping mapping.json] [--policy jobops-policy@0.2.4]
                                     [--as-of 2026-09-30] [--fx data/fx/fx_rates.csv] [--out data/replay/run1]

INPUT is a folder of *.txt files (first line = title, remaining lines = JD), or a .json / .csv export whose
fields are mapped with --mapping (see tools/replay_mapping.example.json). Writes to --out:

    digest.md          per-posting verdicts with verbatim evidence spans, and the mandatory EXCLUDED AUDIT
    owner_labels.csv   one row per posting; owner_* columns are left EMPTY for the owner to fill
    results.json       machine-readable results (for tools/score_owner_labels.py and audits)

Offline and read-only by construction: an in-memory SQLite database built by the migration runner (the live
DB and data/jobs-tracker.db are never opened), no network, no LLM, no submission of anything. FX rates come
only from the owner's --fx file; without it a foreign-currency figure stays UNKNOWN (FX_RATE_UNAVAILABLE).
"""

import argparse
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from evaluation import policy_loader  # noqa: E402
from evaluation.service import EvaluationService  # noqa: E402
from sources.base import ObservationInput  # noqa: E402
from store.db import connect  # noqa: E402
from store.migrate import MigrationRunner  # noqa: E402

FIELDS = ("title", "company", "location", "work_mode", "employment_type", "salary", "description", "url", "source",
          "posted_date", "company_type")
REQUIRED = ("title",)
DIMENSIONS = ("geography", "compensation", "employment_type", "employment_relationship", "employer_type", "language")
COMPANY_TYPES = {"product": "PRODUCT", "ai_native": "AI_NATIVE", "gcc": "GCC", "enterprise": "ENTERPRISE_DIRECT",
                 "staffing": "STAFFING", "consultancy": "CONSULTANCY", "it_services": "IT_SERVICES",
                 "engineering_led": "ENGINEERING_LED", "third_party_payroll": "THIRD_PARTY_PAYROLL"}
LABEL_COLUMNS = ("posting_id", "title", "company", "location", "engine_relevance", "engine_eligibility",
                 "engine_lane", "engine_excluded", "engine_flags", "owner_relevance", "owner_eligibility",
                 "owner_lane", "engine_geography", "engine_compensation", "engine_employment_type",
                 "engine_employer_type", "engine_language", "jd_word_count")
SPAN_MAX = 180


# ---------------------------------------------------------------- input

def _slug(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")[:60] or "posting"


def load_txt_folder(folder: Path) -> List[Dict[str, Any]]:
    out = []
    for path in sorted(folder.glob("*.txt")):
        lines = path.read_text(encoding="utf-8").splitlines()
        title = lines[0].strip() if lines else ""
        out.append({"posting_id": path.stem, "title": title, "description": "\n".join(lines[1:]).strip()})
    return out


def load_mapped(path: Path, mapping: Dict[str, Any]) -> List[Dict[str, Any]]:
    fields = mapping.get("fields", mapping)
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data if isinstance(data, list) else data.get(mapping.get("records_key", "items"), [])
    elif path.suffix.lower() == ".csv":
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    else:
        raise SystemExit(f"unsupported input {path} (use a folder of .txt, a .json or a .csv)")
    out = []
    for i, row in enumerate(rows, 1):
        rec = {}
        for target in FIELDS:
            src = fields.get(target)
            if not src:
                continue
            value = row
            for part in str(src).split("."):  # dotted paths for nested JSON
                value = value.get(part) if isinstance(value, dict) else None
            rec[target] = str(value).strip() if value not in (None, "") else None
        id_field = mapping.get("id")
        rec["posting_id"] = _slug(str(row.get(id_field))) if id_field and row.get(id_field) else f"row-{i:04d}"
        out.append(rec)
    return out


def load_input(path: Path, mapping_path: Optional[Path]) -> List[Dict[str, Any]]:
    if path.is_dir():
        records = load_txt_folder(path)
    else:
        if not mapping_path:
            raise SystemExit("--mapping is required for .json / .csv input")
        records = load_mapped(path, json.loads(mapping_path.read_text(encoding="utf-8")))
    for r in records:
        missing = [f for f in REQUIRED if not r.get(f)]
        if missing:
            raise SystemExit(f"{r['posting_id']}: missing required field(s) {missing}")
    return records


def load_fx(path: Optional[Path]) -> List[Dict[str, Any]]:
    """Owner FX table: currency, rate_to_inr, snapshot_date, source. Lines starting with '#' are comments."""
    if not path:
        return []
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        lines = [ln for ln in f if ln.strip() and not ln.lstrip().startswith("#")]
    for row in csv.DictReader(lines):
        rows.append({"currency": row["currency"].strip().upper(), "rate": float(row["rate_to_inr"]),
                     "snapshot_date": row["snapshot_date"].strip(), "source": (row.get("source") or "owner").strip()})
    return rows


# --------------------------------------------------------------- replay

def _service(version: str, as_of: str) -> EvaluationService:
    conn = connect(":memory:")  # never the live DB
    MigrationRunner(conn).apply_pending()
    service = EvaluationService(conn, policy_loader.load_policy_version(version))
    service.clock = lambda: as_of
    return service


def _span(text: Optional[str]) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if len(text) <= SPAN_MAX else text[:SPAN_MAX - 1] + "…"


def _dimension_evidence(service, rid: str, result: Dict[str, Any]) -> Dict[str, List[str]]:
    _, _, evidence, _ = service._bundle(rid, service.policy)
    by_id = {e["evidence_id"]: e for e in evidence}
    out = {}
    for dim, sel in result["selected_evidence"].items():
        if not isinstance(sel, dict) or "evidence_ids" not in sel:
            continue
        spans = []
        for eid in sel["evidence_ids"] + sel.get("listing_evidence_ids", []):
            e = by_id.get(eid)
            if e and e.get("quoted_span") and _span(e["quoted_span"]) not in spans:
                spans.append(_span(e["quoted_span"]))
        out[dim] = spans[:3]
    return out


def replay(records: List[Dict[str, Any]], version: str, as_of: str, fx_rows: List[Dict[str, Any]]):
    service = _service(version, as_of)
    for fx in fx_rows:
        service.add_fx_rate(fx["currency"], fx["rate"], fx["snapshot_date"], fx["source"])
    results = []
    for r in records:
        cls = COMPANY_TYPES.get((r.get("company_type") or "").strip().lower())
        if cls and r.get("company"):
            service.classify_company(r["company"], cls, "INFERRED_FROM_EVIDENCE", "replay:input")
        desc = r.get("description") or None
        obs = ObservationInput(
            source=r.get("source") or "replay", source_kind="JOB_BOARD",
            observed_at=f"{as_of}T06:00:00+00:00", run_id=f"replay-{as_of}",
            completeness="FULL_JD" if desc else "SEARCH_ONLY", source_external_id=r["posting_id"],
            source_url=r.get("url"), raw_title=r.get("title"), raw_company=r.get("company"),
            raw_location=r.get("location"), raw_work_mode=r.get("work_mode"), raw_salary=r.get("salary"),
            raw_employment_type=r.get("employment_type"), raw_text=desc, source_posted_date=r.get("posted_date"))
        res = service.ingest(obs)
        rid = res["requisition_id"]
        ev = service.current_evaluation(rid)["result"]
        dims = ev["eligibility_dimensions"]
        rel = ev["relevance"]
        results.append({
            "posting_id": r["posting_id"], "requisition_id": rid, "title": r.get("title"), "company": r.get("company"),
            "location": r.get("location"), "lane": ev["lane"], "lane_rule": ev["lane_rule"],
            "eligibility": ev["eligibility_overall"],
            "dimensions": {d: {"verdict": dims[d]["verdict"], "rule_id": dims[d]["rule_id"]} for d in DIMENSIONS},
            "evidence": _dimension_evidence(service, rid, ev),
            "relevance": rel["relevance_label"], "relevance_reason": rel.get("reason"),
            "relevance_spans": [f"{s['matched']} — “{_span(s['quoted_span'])}”" for s in rel.get("evidence_spans", [])
                                if s.get("specific")][:6],
            "experience": rel.get("experience_signal"), "flags": ev["flags"], "review_flags": ev["review_flags"],
            "jd_word_count": len((desc or "").split()),
        })
    return results


# --------------------------------------------------------------- output

def _employment_verdict(res):
    order = ("FAIL", "UNKNOWN", "PASS")
    v = [res["dimensions"]["employment_type"]["verdict"], res["dimensions"]["employment_relationship"]["verdict"]]
    return next(x for x in order if x in v)


def write_digest(results, path: Path, version: str, as_of: str, fx_loaded: bool):
    lanes = ("SHORTLIST", "REVIEW", "PARKED", "EXCLUDED", "SUPPRESSED_DUPLICATE")
    lines = [f"# JobOps real-JD replay digest", "",
             f"Policy `{version}` · as of {as_of} · {len(results)} postings · FX table "
             f"{'loaded' if fx_loaded else 'NOT supplied (foreign currency stays UNKNOWN / FX_RATE_UNAVAILABLE)'}",
             "", "Offline replay. Nothing was submitted; application submission is human-only.", "",
             "| Lane | Count |", "|---|---|"]
    lines += [f"| {ln} | {sum(r['lane'] == ln for r in results)} |" for ln in lanes]
    for lane in lanes:
        group = [r for r in results if r["lane"] == lane]
        if not group:
            continue
        lines += ["", f"## {lane}", ""]
        for r in group:
            d = r["dimensions"]
            ev = r["evidence"]
            lines += [f"### {r['posting_id']} — {r['title']} · {r.get('company') or '—'}", "",
                      f"- **Lane:** {r['lane']} (reason: `{r['lane_rule']}`"
                      f"{'; review flags: ' + ', '.join(r['review_flags']) if r['review_flags'] else ''})",
                      f"- **Relevance:** {r['relevance']} — {r['relevance_reason']}"]
            lines += [f"  - {s}" for s in r["relevance_spans"]]
            for dim, label in (("geography", "Geography"), ("compensation", "Compensation"),
                               ("employment_type", "Employment"), ("employer_type", "Employer type"),
                               ("language", "Language")):
                verdict = _employment_verdict(r) if dim == "employment_type" else d[dim]["verdict"]
                rule = d[dim]["rule_id"] if dim != "employment_type" else \
                    f"{d['employment_type']['rule_id']} / {d['employment_relationship']['rule_id']}"
                spans = ev.get(dim, []) + (ev.get("employment_relationship", []) if dim == "employment_type" else [])
                lines.append(f"- **{label}:** {verdict} (`{rule}`)" +
                             (" — " + "; ".join(f"“{s}”" for s in spans) if spans else " — no evidence captured"))
            lines += [f"- **Experience:** {r['experience']}",
                      f"- **Flags:** {', '.join(r['flags']) or '—'}", ""]
    lines += ["", "## EXCLUDED AUDIT", "",
              "Every posting JobOps excluded, the dimension that failed, the exact evidence and the rule. "
              "Check these first: an exclusion is never shown in SHORTLIST or REVIEW.", ""]
    excluded = [r for r in results if r["lane"] == "EXCLUDED"]
    if not excluded:
        lines.append("_No posting was excluded._")
    else:
        lines += ["| Posting | Title | Company | Dimension | Verdict | Evidence | Rule |", "|---|---|---|---|---|---|---|"]
        for r in excluded:
            for dim in DIMENSIONS:
                if r["dimensions"][dim]["verdict"] != "FAIL":
                    continue
                spans = r["evidence"].get(dim) or ["(no evidence span captured)"]
                ev = "; ".join(s.replace("|", "\\|") for s in spans)
                lines.append(f"| {r['posting_id']} | {r['title']} | {r.get('company') or '—'} | {dim} | FAIL | "
                             f"“{ev}” | `{r['dimensions'][dim]['rule_id']}` |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_labels(results, path: Path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LABEL_COLUMNS)
        w.writeheader()
        for r in results:
            d = r["dimensions"]
            w.writerow({"posting_id": r["posting_id"], "title": r["title"], "company": r.get("company") or "",
                        "location": r.get("location") or "", "engine_relevance": r["relevance"],
                        "engine_eligibility": r["eligibility"], "engine_lane": r["lane"],
                        "engine_excluded": "YES" if r["lane"] == "EXCLUDED" else "NO",
                        "engine_flags": ";".join(r["flags"]),
                        "owner_relevance": "", "owner_eligibility": "", "owner_lane": "",
                        "engine_geography": d["geography"]["verdict"], "engine_compensation": d["compensation"]["verdict"],
                        "engine_employment_type": _employment_verdict(r),
                        "engine_employer_type": d["employer_type"]["verdict"], "engine_language": d["language"]["verdict"],
                        "jd_word_count": r["jd_word_count"]})


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", type=Path)
    ap.add_argument("--mapping", type=Path)
    ap.add_argument("--policy", default=policy_loader.DEFAULT_VERSION)
    ap.add_argument("--as-of", default=date.today().isoformat())
    ap.add_argument("--fx", type=Path)
    ap.add_argument("--out", type=Path)
    a = ap.parse_args(argv)
    date.fromisoformat(a.as_of)
    out = a.out or (REPO_ROOT / "data" / "replay" / f"run-{a.as_of}")
    out.mkdir(parents=True, exist_ok=True)
    records = load_input(a.input, a.mapping)
    fx_rows = load_fx(a.fx)
    results = replay(records, a.policy, a.as_of, fx_rows)
    write_digest(results, out / "digest.md", a.policy, a.as_of, bool(fx_rows))
    write_labels(results, out / "owner_labels.csv")
    (out / "results.json").write_text(json.dumps({"policy_version": a.policy, "as_of": a.as_of,
                                                  "fx_rows": len(fx_rows), "results": results},
                                                 indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(results)} postings -> {out}/digest.md, owner_labels.csv, results.json "
          f"(EXCLUDED: {sum(r['lane'] == 'EXCLUDED' for r in results)})")
    return out


if __name__ == "__main__":
    main()
