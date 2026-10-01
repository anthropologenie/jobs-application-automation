"""
P9 (Phase C-lite) tests: `python3 -m jobops source` / `decisions --import` over synthetic exports.

Fixtures (tests/fixtures/p9/) are independently authored synthetic exports; no Round-3 / Round-4 content.
Every run writes to a pytest tmp_path; the live data/jobs-tracker.db is never opened, and sockets are refused.
"""

import ast
import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import pytest

from evaluation.policy_loader import load_policy_version
from jobops import normalize
from jobops.cli import main
from jobops.sourcing import STATE_DB
from v02_support import fresh_service, no_network  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
FIX = Path(__file__).resolve().parent / "fixtures" / "p9"
DAY1, DAY2, DAY3, DAY4 = FIX / "day1_export.json", FIX / "day2_export.csv", FIX / "day3_export.json", FIX / "day4_export.json"
V26 = "jobops-policy@0.2.6"
SHA26 = "de527c5d1dceb400913ec42e5aa527f19cd809e5054fcef5c61337d7fb890455"
DAYS = ["2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04"]


def run(inp, out, day, *extra):
    return main(["source", "--input", str(inp), "--policy", "0.2.6", "--out", str(out), "--date", day, *extra])


def outputs(out, day):
    d = Path(out) / day
    return {p.relative_to(d).as_posix(): p.read_bytes() for p in sorted(d.rglob("*")) if p.is_file()}


def metrics_of(out, day):
    return json.loads((Path(out) / day / "metrics.json").read_text(encoding="utf-8"))


def digest_of(out, day):
    return (Path(out) / day / "digest.md").read_text(encoding="utf-8")


def section(text, title):
    if f"## {title}" not in text:
        return ""
    return text.split(f"## {title}", 1)[1].split("\n## ", 1)[0]


def ids_in(text):
    return set(re.findall(r"`(req_\d+)`", text))


def write_json(path, records):
    path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
    return path


JD_STRONG = ("Brightmoor builds and sells its own AI product for crop insurance. You will design evaluation harnesses "
             "and golden datasets for our LLM assistants, measure groundedness and faithfulness of RAG answers, and "
             "add guardrails that catch hallucinations before release.")


def rec(i, **over):
    r = {"id": f"t-{i}", "title": "AI Quality Engineer", "company": f"Brightmoor {i}", "location": "Remote, India",
         "work_mode": "Remote", "salary": "₹26 LPA – ₹32 LPA", "employment_type": "Full-time",
         "url": f"https://jobs.example-board.test/view/t-{i}", "description": JD_STRONG, "source": "linkedin"}
    r.update(over)
    return {k: v for k, v in r.items() if v is not None}


# --------------------------------------------------------------- day-1 run

@pytest.fixture(scope="module")
def day1(tmp_path_factory):
    out = tmp_path_factory.mktemp("p9day1")
    assert run(DAY1, out, DAYS[0]) == 0
    return out


def test_outputs_exist_and_header(day1, capsys):
    d = Path(day1) / DAYS[0]
    for name in ("digest.md", "excluded.csv", "decisions.csv", "metrics.json"):
        assert (d / name).is_file(), name
    assert list((d / "jd").glob("req_*.txt"))
    text = digest_of(day1, DAYS[0])
    assert "- Policy: 0.2.6" in text and f"- Policy SHA: {SHA26}" in text
    assert "Gate E: pending" in text and "Gate E: PASS" not in text
    assert hashlib.sha256(DAY1.read_bytes()).hexdigest() in text
    assert (Path(day1) / "state" / STATE_DB).is_file()


def test_stdout_prints_policy_and_gate(tmp_path, capsys):
    assert run(DAY3, tmp_path, DAYS[0]) == 0
    printed = capsys.readouterr().out
    assert f"Policy: 0.2.6\nPolicy SHA: {SHA26}\nGate E: pending" in printed


def test_day1_metrics(day1):
    m = metrics_of(day1, DAYS[0])
    assert m["jobs_in"] == 57 and m["unique_jobs"] == 53 and m["duplicates"] == 4
    assert m["ambiguous_identity"] == 2 and m["jd_missing"] == 4 and m["jd_truncated"] == 2
    assert m["SHORTLIST"] + m["REVIEW"] + m["PARKED"] + m["EXCLUDED"] + m["SUPPRESSED_DUPLICATE"] == m["unique_jobs"]
    assert m["shortlist_plus_review"] == m["SHORTLIST"] + m["REVIEW"]
    assert m["gap_to_25"] == max(0, 25 - m["shortlist_plus_review"])
    for dim, counts in m["per_dimension"].items():
        assert sum(counts.values()) == m["unique_jobs"], dim
    assert m["bottleneck"]["cause"] and m["policy_sha256"] == SHA26


def test_csv_input_with_other_aliases(day1, tmp_path):
    out = tmp_path / "csv"
    assert run(DAY2, out, DAYS[0]) == 0
    m = metrics_of(out, DAYS[0])
    assert m["jobs_in"] == 14 and m["rejected_records"] == 0


# ----------------------------------------------------------- determinism

def test_rerun_same_input_same_date_is_idempotent(tmp_path):
    assert run(DAY1, tmp_path, DAYS[0]) == 0
    first = outputs(tmp_path, DAYS[0])
    assert run(DAY1, tmp_path, DAYS[0]) == 0
    assert outputs(tmp_path, DAYS[0]) == first
    runs = json.loads((tmp_path / "state" / "runs.json").read_text())["runs"]
    assert len(runs) == 1  # nothing re-ingested


def test_fresh_state_same_input_same_output(tmp_path):
    for name in ("a", "b"):
        assert run(DAY1, tmp_path / name, DAYS[0]) == 0
    assert outputs(tmp_path / "a", DAYS[0]) == outputs(tmp_path / "b", DAYS[0])


def test_runs_must_be_in_date_order(tmp_path):
    assert run(DAY1, tmp_path, DAYS[1]) == 0
    assert run(DAY3, tmp_path, DAYS[0]) == 2


# ---------------------------------------------------------------- newness

@pytest.fixture(scope="module")
def four_days(tmp_path_factory):
    out = tmp_path_factory.mktemp("p9four")
    for day, inp in zip(DAYS, (DAY1, DAY2, DAY3, DAY4)):
        assert run(inp, out, day) == 0
    return out


def _cards(text):
    return {m.group(2): m.group(3) for m in re.finditer(r"### (.+?)  `(req_\d+)`\n(?:.*\n){2}- \*\*Relevance:\*\* \S+ · "
                                                         r"\*\*Newness:\*\* (\w+)", text)}


def test_newness_new_then_seen_before_then_updated(four_days):
    day1 = _cards(digest_of(four_days, DAYS[0]))
    day2 = _cards(digest_of(four_days, DAYS[1]))
    assert set(day1.values()) == {"NEW"}
    assert day2["req_0000006"] == "UPDATED"  # pay figure changed on the same source
    assert day2["req_0000002"] == "UPDATED"  # JD text changed (JD hash)
    assert day2["req_0000001"] == "SEEN_BEFORE"  # unchanged re-sighting
    assert sum(1 for v in day2.values() if v == "NEW") >= 1  # day-2 new jobs


# ------------------------------------------------------ dedupe / identity

def test_duplicate_record_collapses_to_one_canonical_job(tmp_path):
    inp = write_json(tmp_path / "dup.json", [rec(1), rec(1, source="linkedin")])
    assert run(inp, tmp_path / "o", DAYS[0]) == 0
    m = metrics_of(tmp_path / "o", DAYS[0])
    assert m["jobs_in"] == 2 and m["unique_jobs"] == 1 and m["duplicate_records_collapsed"] == 1
    assert digest_of(tmp_path / "o", DAYS[0]).count("`req_0000001`") == 1


def test_bridging_sighting_becomes_suppressed_duplicate(tmp_path):
    a = rec(1)
    b = rec(2, url="https://jobs.example-board.test/view/t-2b")
    bridge = rec(3, url=a["url"], apply_url=b["url"])
    inp = write_json(tmp_path / "bridge.json", [a, b, bridge])
    assert run(inp, tmp_path / "o", DAYS[0]) == 0
    m = metrics_of(tmp_path / "o", DAYS[0])
    assert m["SUPPRESSED_DUPLICATE"] == 1 and m["duplicates"] >= 1
    text = digest_of(tmp_path / "o", DAYS[0])
    shown = ids_in(section(text, "SHORTLIST") + section(text, "REVIEW (shown today)"))
    assert len(shown) == 1  # the suppressed duplicate is never presented as a candidate


def test_ambiguous_identity_is_review_not_excluded(day1):
    text = digest_of(day1, DAYS[0])
    review = section(text, "REVIEW (shown today)")
    assert review.count("IDENTITY_UNCERTAIN: may be the same job") == 2
    excluded = {r["job_id"] for r in csv.DictReader(open(Path(day1) / DAYS[0] / "excluded.csv"))}
    assert not (ids_in(review) & excluded)


# ------------------------------------------------------- missing JD paths

def test_missing_jd_never_excluded_for_the_missing_jd(tmp_path):
    inp = write_json(tmp_path / "nojd.json", [rec(1, description=None), rec(2, description="", title="Data Analyst"),
                                              rec(3, description=None, location="Mumbai, Maharashtra",
                                                  work_mode="On-site")])
    assert run(inp, tmp_path / "o", DAYS[0]) == 0
    rows = list(csv.DictReader(open(tmp_path / "o" / DAYS[0] / "excluded.csv")))
    # Only the posting whose structured location fails is excluded, and on geography (not on the JD).
    assert [(r["job_id"], r["failing_dimension"]) for r in rows] == [("req_0000003", "geography")]
    m = metrics_of(tmp_path / "o", DAYS[0])
    assert m["jd_missing"] == 3 and m["EXCLUDED"] == 1
    # Language depends on the JD: it is never PASS without one.
    assert m["per_dimension"]["language"]["PASS"] == 0
    jd = (tmp_path / "o" / DAYS[0] / "jd" / "req_0000001.txt").read_text()
    assert "JD_MISSING" in jd


def test_truncated_jd_is_never_shortlisted(day1):
    text = digest_of(day1, DAYS[0])
    held = section(text, "REVIEW — held from SHORTLIST (incomplete JD; outside the daily cap)")
    assert held.count("JD_TRUNCATED") == 2
    assert not (ids_in(held) & ids_in(section(text, "SHORTLIST")))
    decisions = {r["job_id"] for r in csv.DictReader(open(Path(day1) / DAYS[0] / "decisions.csv"))}
    assert ids_in(held) <= decisions
    for jid in ids_in(held):
        assert "JD_TRUNCATED" in (Path(day1) / DAYS[0] / "jd" / f"{jid}.txt").read_text()


# ------------------------------------------------------------- review cap

def _units(m):
    return m["queue_today"]["review_shown"], m["queue_today"]["review_overflow"]


@pytest.mark.parametrize("cap,expect_overflow", [(40, 0), (5, None)])
def test_review_cap_below_and_above(tmp_path, cap, expect_overflow):
    assert run(DAY1, tmp_path, DAYS[0], "--review-cap", str(cap)) == 0
    m = metrics_of(tmp_path, DAYS[0])
    shown, overflow = _units(m)
    assert m["queue_today"]["review_cap"] == cap
    if expect_overflow == 0:
        assert overflow == 0
    else:
        assert overflow > 0 and shown <= cap + 1  # one grouped card holds two members in one cap slot


def test_review_cap_exactly_at_cap(tmp_path):
    assert run(DAY1, tmp_path / "probe", DAYS[0], "--review-cap", "40") == 0
    m = metrics_of(tmp_path / "probe", DAYS[0])
    n_units = m["queue_today"]["review_shown"] - 1  # the identity-uncertain pair is one unit
    assert run(DAY1, tmp_path / "at", DAYS[0], "--review-cap", str(n_units)) == 0
    m2 = metrics_of(tmp_path / "at", DAYS[0])
    assert m2["queue_today"]["review_overflow"] == 0 and m2["queue_today"]["review_shown"] == n_units + 1


def test_review_cap_changes_presentation_only(tmp_path):
    for cap in ("5", "40"):
        assert run(DAY1, tmp_path / cap, DAYS[0], "--review-cap", cap) == 0
    a, b = metrics_of(tmp_path / "5", DAYS[0]), metrics_of(tmp_path / "40", DAYS[0])
    for k in ("SHORTLIST", "REVIEW", "PARKED", "EXCLUDED", "per_dimension"):
        assert a[k] == b[k], k
    assert load_policy_version(V26).doc["parameters"]["review_daily_cap"] == 10


# ------------------------------------------------------------------ OR-88

@pytest.mark.parametrize("d4_cap", ["50", "AT", "3"], ids=["below_cap", "at_cap", "over_cap"])
def test_or88_d3_non_strong_parked_whatever_the_queue(tmp_path, d4_cap):
    for day, inp in zip(DAYS[:3], (DAY1, DAY2, DAY3)):
        assert run(inp, tmp_path, day, "--review-cap", "5") == 0
    m3 = metrics_of(tmp_path, DAYS[2])
    pending = m3["queue_today"]["review_shown"] + m3["queue_today"]["review_overflow"] - 1  # units
    cap = str(pending - 2) if d4_cap == "AT" else d4_cap  # the two non-STRONG units leave the pool on D+3
    assert run(DAY4, tmp_path, DAYS[3], "--review-cap", cap) == 0
    text = digest_of(tmp_path, DAYS[3])
    parked = section(text, "PARKED (1 from this export, 2 by overflow today)")
    assert parked, text.split("## PARKED", 1)[1][:300]
    assert {"req_0000027", "req_0000028"} <= ids_in(parked)  # NOT_ASSESSED items carried D, D+1, D+2
    shown = ids_in(section(text, "REVIEW (shown today)") + section(text, "REVIEW overflow (carried to tomorrow)"))
    assert not ({"req_0000027", "req_0000028"} & shown)


def test_or88_default_cap_four_days(four_days):
    m = metrics_of(four_days, DAYS[3])
    assert m["queue_today"]["overflow_parked_today"] == 2
    assert all(metrics_of(four_days, d)["queue_today"]["overflow_parked_today"] == 0 for d in DAYS[:3])


# ------------------------------------------------------------ digest safety

@pytest.mark.parametrize("day", DAYS)
def test_excluded_never_shortlist_or_review(four_days, day):
    excluded = {r["job_id"] for r in csv.DictReader(open(Path(four_days) / day / "excluded.csv"))}
    text = digest_of(four_days, day)
    candidates = ids_in(section(text, "SHORTLIST") + section(text, "REVIEW (shown today)")
                        + section(text, "REVIEW — held from SHORTLIST (incomplete JD; outside the daily cap)")
                        + section(text, "REVIEW overflow (carried to tomorrow)"))
    assert not (excluded & candidates)
    decisions = {r["job_id"] for r in csv.DictReader(open(Path(four_days) / day / "decisions.csv"))}
    assert not (excluded & decisions) and candidates <= decisions


def test_decisions_csv_has_exactly_core_columns(day1):
    with open(Path(day1) / DAYS[0] / "decisions.csv") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    assert reader.fieldnames == ["job_id", "applied", "skipped", "skip_reason", "notes"]
    assert rows and all(not any(r[k] for k in ("applied", "skipped", "skip_reason", "notes")) for r in rows)


def test_quotes_are_verbatim_from_the_export(day1):
    raw = json.loads(DAY1.read_text(encoding="utf-8"))
    corpus = "\n".join(str(v) for r in raw for v in r.values())
    for line in digest_of(day1, DAYS[0]).splitlines():
        if line.startswith("  > "):
            quote = line[4:]
            assert (quote.rstrip("…") if quote.endswith("…") else quote) in corpus, quote


# --------------------------------------------------------------- URL safety

def test_urls_preserved_and_never_fabricated(day1):
    raw = json.loads(DAY1.read_text(encoding="utf-8"))
    supplied = {r[k] for r in raw for k in ("link",) if r.get(k)}
    text = digest_of(day1, DAYS[0])
    for url in re.findall(r"\*\*Apply:\*\* (\S+)", text):
        assert url == "apply_url_missing" or url in supplied, url
    assert "/jobs/search" not in text  # a search-results URL is never presented as an application URL
    m = metrics_of(day1, DAYS[0])
    assert m["apply_url_missing"] == 5


def test_search_url_is_not_an_application_url():
    r = normalize.canonicalise({"title": "AI QA", "company": "X", "url": "https://board.test/jobs/search?keywords=ai"}, 0)
    assert r["application_url"] is None and r["search_url_only"]
    r = normalize.canonicalise({"title": "AI QA", "company": "X", "url": "https://board.test/view/123?ref=abc"}, 0)
    assert r["application_url"] == "https://board.test/view/123?ref=abc"


# ------------------------------------------------------------ schema errors

def test_unmappable_schema_fails_clearly(tmp_path, capsys):
    inp = write_json(tmp_path / "bad.json", [{"foo": "bar", "baz": 1}])
    assert run(inp, tmp_path / "o", DAYS[0]) == 2
    assert "no record has a recognised title field" in capsys.readouterr().err
    assert not (tmp_path / "o" / DAYS[0]).exists()


def test_record_without_identity_fields_is_rejected_not_invented(tmp_path):
    inp = write_json(tmp_path / "partial.json", [rec(1), {"title": "AI QA Engineer"}])
    assert run(inp, tmp_path / "o", DAYS[0]) == 0
    m = metrics_of(tmp_path / "o", DAYS[0])
    assert m["rejected_records"] == 1 and m["unique_jobs"] == 1


def test_aliases_and_container_keys(tmp_path):
    inp = tmp_path / "wrapped.json"
    inp.write_text(json.dumps({"items": [{"jobTitle": "AI QA", "companyName": "Y", "jobUrl": "https://b.test/v/1",
                                          "jobDescription": "Text", "workplaceType": "Remote"}]}))
    recs = normalize.map_schema(normalize.read_export(inp), inp.name)
    assert recs[0]["title"] == "AI QA" and recs[0]["company"] == "Y" and recs[0]["job_url"] == "https://b.test/v/1"
    assert recs[0]["work_mode"] == "Remote" and recs[0]["description"] == "Text"


# ---------------------------------------------------------- decision import

def test_decisions_import_updates_local_state_only(tmp_path):
    assert run(DAY1, tmp_path, DAYS[0]) == 0
    sheet = Path(tmp_path) / DAYS[0] / "decisions.csv"
    rows = list(csv.DictReader(open(sheet)))
    rows[0]["applied"] = "yes"
    rows[1]["skipped"] = "yes"
    rows[1]["skip_reason"] = "stack mismatch"
    with open(sheet, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["job_id", "applied", "skipped", "skip_reason", "notes"])
        w.writeheader()
        w.writerows(rows)
    args = ["decisions", "--import", str(sheet), "--out", str(tmp_path), "--date", DAYS[0]]
    assert main(args) == 0
    assert main(args) == 0  # re-import is a no-op
    ledger = json.loads((tmp_path / "state" / "decisions_imported.json").read_text())
    assert len(ledger) == 2
    assert run(DAY1, tmp_path, DAYS[0]) == 0  # a rerun of day 1 never overwrites the filled-in sheet
    assert "yes" in sheet.read_text() and (Path(tmp_path) / DAYS[0] / "decisions.pending.csv").exists()
    # The decided jobs leave the next day's candidate lists.
    assert run(DAY3, tmp_path, DAYS[1]) == 0
    nxt = digest_of(tmp_path, DAYS[1])
    assert rows[0]["job_id"] not in nxt and rows[1]["job_id"] not in nxt


def test_decisions_import_rejects_unknown_and_contradictory_rows(tmp_path):
    assert run(DAY3, tmp_path, DAYS[0]) == 0
    sheet = tmp_path / "d.csv"
    sheet.write_text("job_id,applied,skipped,skip_reason,notes\nreq_9999999,yes,,,\nreq_0000001,yes,yes,,\n")
    assert main(["decisions", "--import", str(sheet), "--out", str(tmp_path)]) == 1


# ------------------------------------------------------------ verdict parity

def test_p9_verdicts_equal_direct_engine_verdicts(day1):
    """P9 adds no verdict: each job's dimensions equal a direct, single-record engine evaluation."""
    import sqlite3
    raws = normalize.read_export(DAY1)
    records = normalize.map_schema(raws, DAY1.name)
    ledger = json.loads((Path(day1) / "state" / "runs.json").read_text())
    mapping = ledger["runs"][0]["records"]
    counts = {}
    for m in mapping:
        counts[m["requisition_id"]] = counts.get(m["requisition_id"], 0) + 1
    conn = sqlite3.connect(Path(day1) / "state" / STATE_DB)
    conn.row_factory = sqlite3.Row
    checked = 0
    for m in mapping:
        rid = m["requisition_id"]
        if rid is None or counts[rid] > 1:
            continue
        row = conn.execute("SELECT result_json FROM evaluation WHERE requisition_id=? ORDER BY seq DESC LIMIT 1",
                           (rid,)).fetchone()
        p9 = json.loads(row["result_json"])
        if "IDENTITY_UNCERTAIN" in p9["flags"]:
            continue
        s = fresh_service(load_policy_version(V26))
        s.clock = lambda: DAYS[0]
        direct = s.ingest(normalize.to_observation(records[m["index"]], run_id="direct", day=DAYS[0]))["evaluation"]["result"]
        assert {k: v["verdict"] for k, v in p9["eligibility_dimensions"].items()} == \
               {k: v["verdict"] for k, v in direct["eligibility_dimensions"].items()}, rid
        assert p9["lane"] == direct["lane"] and p9["relevance"]["relevance_label"] == direct["relevance"]["relevance_label"]
        checked += 1
    conn.close()
    assert checked >= 45


# ------------------------------------------------------------- offline safety

FORBIDDEN = {"socket", "ssl", "http", "urllib", "requests", "httpx", "aiohttp", "websocket", "websockets",
             "ftplib", "smtplib", "telnetlib", "subprocess", "openai", "anthropic", "google", "cohere", "mistralai"}


def test_jobops_imports_no_network_or_llm_module_statically():
    for path in sorted((ROOT / "jobops").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                names = [node.module or ""]
            for n in names:
                assert n.split(".")[0] not in FORBIDDEN, (path.name, n)


def test_running_the_command_loads_no_network_module(tmp_path):
    before = set(sys.modules)
    assert run(DAY3, tmp_path, DAYS[0]) == 0
    loaded = {m.split(".")[0] for m in set(sys.modules) - before}
    assert not (loaded & FORBIDDEN), loaded & FORBIDDEN


def test_state_never_touches_the_live_db(day1):
    assert (Path(day1) / "state" / STATE_DB).exists()
    from store.db import connect
    from store.paths import LEGACY_DB_PATH, LegacyDatabaseRefused
    with pytest.raises(LegacyDatabaseRefused):
        connect(LEGACY_DB_PATH)


# ------------------------------------------------------------------ integrity

HASHES = {"0.2.0": "65f74aec883d475989ea0594fac070f547c96a697bc1f7f4b46cf8e0d5dd567a",
          "0.2.1": "af19a3fd998e945cba19ce68f0e36f2eba4156e8bfd5255ac4ea7dacf7f5ea7d",
          "0.2.2": "3743bbaebce2b5f3143ec0a211d6c63aa35b8113dce03b1622876ef43eeed734",
          "0.2.3": "918bf66e7d83d06d7ff7b10c6d8b1309cbabd033331315510851110856659d77",
          "0.2.4": "735934bf33533a31d207349cf689a3df6dafcdacc9c6a11b889b92e5af8c8136",
          "0.2.5": "27fe5d1accff78ce9db8ccc5f42a7d905b3e709a474d93d446e19a795ad53c93",
          "0.2.6": SHA26}


@pytest.mark.parametrize("version,sha", sorted(HASHES.items()))
def test_policies_byte_identical(version, sha):
    assert hashlib.sha256((ROOT / "policy" / f"jobops-policy-{version}.json").read_bytes()).hexdigest() == sha


def test_p9_fixtures_are_independent_of_round3():
    text = "\n".join(p.read_text(encoding="utf-8") for p in FIX.iterdir())
    assert not re.search(r"\bR3-\d{3}\b|\bS-0\d\b", text)
    import test_p8_policy_025 as p8
    assert [s for s in p8._round3_gap_sentences() if s in text.lower()] == []
