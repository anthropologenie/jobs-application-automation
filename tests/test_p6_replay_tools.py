"""
P6 offline real-JD replay and owner-label scorer (tools/replay_real_jds.py, tools/score_owner_labels.py).
Five synthetic JDs; no real data, no network, no live DB.
"""

import csv
import json
import subprocess
from pathlib import Path

import pytest

import store.db
from v02_support import no_network  # noqa: F401  (autouse: any socket connect fails the test)

ROOT = Path(__file__).resolve().parent.parent
import sys  # noqa: E402

sys.path.insert(0, str(ROOT / "tools"))
import replay_real_jds as replay  # noqa: E402
import score_owner_labels as scorer  # noqa: E402

JDS = {
    "p1-remote-strong": ("AI Evaluation Engineer",
                         "Location: Remote - India.\nSalary: ₹30 LPA base.\nEmployment type: Full-time, permanent.\n"
                         "Build RAG pipelines, calibrate LLM-as-judge graders and run hallucination evals on golden "
                         "datasets. Experience: 2-4 years."),
    "p2-canada-lock": ("Applied AI Engineer",
                       "Location: Remote — Canada.\nSalary: ₹32 LPA base.\nEmployment type: Permanent.\n"
                       "Build LLM agents and RAG retrieval with evals."),
    "p3-usd-no-fx": ("GenAI Engineer",
                     "Location: Remote - India.\nSalary: USD 90,000 per year base.\nEmployment type: Full-time.\n"
                     "Ship LLM features with RAG and guardrails."),
    "p4-contract": ("RAG Engineer",
                    "Location: Remote - India.\nSalary: ₹30 LPA base.\nThis is a 12-month contract role.\n"
                    "Build retrieval-augmented generation with embeddings and rerankers."),
    "p5-bi": ("Data Analyst", "Location: Remote - India.\nSalary: ₹26 LPA base.\nEmployment type: Permanent.\n"
                              "Build Power BI dashboards and SQL reports for sales."),
}


@pytest.fixture
def jd_folder(tmp_path):
    folder = tmp_path / "jds"
    folder.mkdir()
    for pid, (title, body) in JDS.items():
        (folder / f"{pid}.txt").write_text(f"{title}\n{body}\n", encoding="utf-8")
    return folder


@pytest.fixture
def db_guard(monkeypatch):
    opened = []
    real = store.db.connect

    def guarded(path, *a, **k):
        opened.append(str(path))
        assert str(path) == ":memory:", f"replay opened a real database: {path}"
        return real(path, *a, **k)

    monkeypatch.setattr(replay, "connect", guarded)
    return opened


def _run(jd_folder, tmp_path, *extra):
    out = tmp_path / "out"
    replay.main([str(jd_folder), "--as-of", "2026-09-30", "--policy", "jobops-policy@0.2.4", "--out", str(out), *extra])
    results = json.loads((out / "results.json").read_text(encoding="utf-8"))
    return out, {r["posting_id"]: r for r in results["results"]}, results


def test_replay_runs_offline_and_only_in_memory(jd_folder, tmp_path, db_guard):
    _, res, _ = _run(jd_folder, tmp_path)
    assert db_guard and set(db_guard) == {":memory:"}
    assert len(res) == 5


def test_expected_columns_and_empty_owner_labels(jd_folder, tmp_path, db_guard):
    out, _, _ = _run(jd_folder, tmp_path)
    with open(out / "owner_labels.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    for col in ("posting_id", "title", "company", "location", "engine_relevance", "engine_eligibility", "engine_lane",
                "engine_excluded", "engine_flags", "owner_relevance", "owner_eligibility", "owner_lane"):
        assert col in reader.fieldnames
    assert all(r["owner_relevance"] == r["owner_eligibility"] == r["owner_lane"] == "" for r in rows)


def test_excluded_audit_lists_dimension_evidence_and_rule(jd_folder, tmp_path, db_guard):
    out, res, _ = _run(jd_folder, tmp_path)
    digest = (out / "digest.md").read_text(encoding="utf-8")
    assert "## EXCLUDED AUDIT" in digest
    audit = digest.split("## EXCLUDED AUDIT", 1)[1]
    assert res["p2-canada-lock"]["lane"] == "EXCLUDED" and res["p4-contract"]["lane"] == "EXCLUDED"
    assert "p2-canada-lock" in audit and "GEO-R03" in audit and "Canada" in audit
    assert "p4-contract" in audit and "EMP-R03" in audit and "12-month contract role" in audit
    assert "p1-remote-strong" not in audit


def test_missing_fx_is_unknown_fx_rate_unavailable(jd_folder, tmp_path, db_guard):
    _, res, _ = _run(jd_folder, tmp_path)
    r = res["p3-usd-no-fx"]
    assert r["dimensions"]["compensation"] == {"verdict": "UNKNOWN", "rule_id": "COMP-R14"}
    assert "FX_RATE_UNAVAILABLE" in r["flags"]


def test_fx_file_is_used_and_as_of_drives_staleness(jd_folder, tmp_path, db_guard):
    fx = tmp_path / "fx.csv"
    fx.write_text("# test rates, not real\ncurrency,rate_to_inr,snapshot_date,source\nUSD,80,2026-09-25,test\n",
                  encoding="utf-8")
    _, res, _ = _run(jd_folder, tmp_path, "--fx", str(fx))
    assert res["p3-usd-no-fx"]["dimensions"]["compensation"]["verdict"] == "PASS"
    out2 = tmp_path / "late"
    replay.main([str(jd_folder), "--as-of", "2026-10-20", "--policy", "jobops-policy@0.2.4", "--fx", str(fx),
                 "--out", str(out2)])
    late = {r["posting_id"]: r for r in json.loads((out2 / "results.json").read_text())["results"]}
    assert late["p3-usd-no-fx"]["dimensions"]["compensation"] == {"verdict": "UNKNOWN", "rule_id": "COMP-R19"}


def test_policy_override_is_honoured(jd_folder, tmp_path, db_guard):
    out = tmp_path / "v22"
    replay.main([str(jd_folder), "--as-of", "2026-09-30", "--policy", "jobops-policy@0.2.2", "--out", str(out)])
    data = json.loads((out / "results.json").read_text())
    assert data["policy_version"] == "jobops-policy@0.2.2"
    assert "jobops-policy@0.2.2" in (out / "digest.md").read_text()


def test_mapped_json_and_csv_inputs(tmp_path, db_guard):
    mapping = json.loads((ROOT / "tools" / "replay_mapping.example.json").read_text())
    items = [{"id": f"x{i}", "title": t, "companyName": "Co", "location": "Remote - India", "description": b}
             for i, (t, b) in enumerate(JDS.values())]
    src = tmp_path / "export.json"
    src.write_text(json.dumps({"items": items}), encoding="utf-8")
    mp = tmp_path / "m.json"
    mp.write_text(json.dumps(mapping), encoding="utf-8")
    out = replay.main([str(src), "--mapping", str(mp), "--as-of", "2026-09-30", "--out", str(tmp_path / "j")])
    assert len(json.loads((out / "results.json").read_text())["results"]) == 5
    csv_src = tmp_path / "export.csv"
    with open(csv_src, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(items[0]))
        w.writeheader()
        w.writerows(items)
    out = replay.main([str(csv_src), "--mapping", str(mp), "--as-of", "2026-09-30", "--out", str(tmp_path / "c")])
    assert len(json.loads((out / "results.json").read_text())["results"]) == 5


def test_scorer_known_confusion_matrix_and_safety_rows(tmp_path):
    rows = [
        # posting, engine rel, engine lane, engine elig, owner rel, owner elig, words
        ("a", "STRONG", "SHORTLIST", "PASS", "STRONG", "PASS", 120),
        ("b", "STRONG", "SHORTLIST", "PASS", "MODERATE", "FAIL", 40),
        ("c", "MODERATE", "REVIEW", "UNKNOWN", "STRONG", "UNKNOWN", 300),
        ("d", "WEAK", "PARKED", "PASS", "WEAK", "PASS", 80),
        ("e", "STRONG", "EXCLUDED", "FAIL", "STRONG", "PASS", 200),
        ("f", "WEAK", "PARKED", "PASS", "", "", 10),
    ]
    path = tmp_path / "labels.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(replay.LABEL_COLUMNS))
        w.writeheader()
        for pid, er, el, ee, orl, oe, n in rows:
            w.writerow({**{c: "" for c in replay.LABEL_COLUMNS}, "posting_id": pid, "title": pid.upper(),
                        "engine_relevance": er, "engine_lane": el, "engine_eligibility": ee, "owner_relevance": orl,
                        "owner_eligibility": oe, "jd_word_count": n})
    s = scorer.main([str(path), "--json"])
    cm = s["relevance_confusion"]
    assert cm["STRONG"] == {"STRONG": 2, "MODERATE": 1, "WEAK": 0}
    assert cm["MODERATE"] == {"STRONG": 1, "MODERATE": 0, "WEAK": 0}
    assert cm["WEAK"] == {"STRONG": 0, "MODERATE": 0, "WEAK": 1}
    assert s["strong_precision"] == round(2 / 3, 4) and s["strong_recall"] == round(2 / 3, 4)
    assert s["relevance_labelled"] == 5 and s["eligibility_agreement"] == "3/5"
    assert [r["posting_id"] for r in s["safety_engine_excluded_owner_eligible"]] == ["e"]
    assert [r["posting_id"] for r in s["safety_engine_shortlist_owner_ineligible"]] == ["b"]
    assert s["jd_length"]["min"] == 10 and s["jd_length"]["max"] == 300
    assert "composite" not in json.dumps(s).lower() or "no composite" in scorer.to_markdown(s).lower()


def test_fx_template_has_no_rates():
    lines = (ROOT / "data" / "fx" / "fx_rates.template.csv").read_text(encoding="utf-8").splitlines()
    data = [ln for ln in lines if ln.strip() and not ln.startswith("#")]
    assert data == ["currency,rate_to_inr,snapshot_date,source"]
    assert 2 <= sum(ln.startswith("#") for ln in lines) <= 3


@pytest.mark.parametrize("path,ignored", [
    ("data/replay/run-2026-10-01/owner_labels.csv", True),
    ("data/replay/run-2026-10-01/digest.md", True),
    ("data/real_jds/batch1/posting.txt", True),
    ("reports/owner_labels_filled.csv", True),
    ("data/fx/fx_rates.template.csv", False),
    ("tools/replay_real_jds.py", False),
])
def test_real_jd_paths_are_git_ignored(path, ignored):
    try:
        rc = subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT).returncode
    except OSError:
        pytest.skip("git not available")
    if rc == 128:
        pytest.skip("not a git work tree (scratch copy)")
    assert (rc == 0) == ignored
