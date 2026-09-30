#!/usr/bin/env python3
"""
P0-06 LinkedIn ingestion - deterministic tests

FIXTURE TESTS ONLY. Every LinkedIn response in this file is a fixture. Nothing
here contacts LinkedIn, nothing here requires `bun`, and no test in this file
is evidence that live ingestion works. The live bounded validation run is a
separate, explicitly reported activity (P0_IMPLEMENTATION_SPEC.md 7.7, exit
criterion X6) and its evidence lives in data/ingestion/runs/.

What these tests do assert:

  * the ingestion path produces the same verdicts the P0-02 gate produces, for
    the owner-specified vectors, end to end from raw CLI output;
  * work mode survives ingestion, including across the scraped_jobs ->
    opportunities bridge, and ambiguous language never becomes REMOTE;
  * ingestion holds no policy of its own - move the threshold in the artifact
    and the ingested verdict moves with it;
  * data/resume_config.json is not read, statically or at runtime;
  * raw-source provenance is retained and can reconstruct what was received;
  * the volume ceilings are enforced, including across processes;
  * a re-run inserts no duplicate rows under the existing identity contract.

They do NOT cover P0-07. Deduplication beyond L1 (source_portal, external_id)
is not implemented and is not tested here.

Run:
    python3 -m pytest tests/test_p0_06_linkedin_ingestion.py -v

Author: Karthik Shetty
Created: 2026-08-31
"""

import ast
import builtins
import importlib.util
import json
import sqlite3
import subprocess
import sys
import types
from pathlib import Path

import pytest

from ingestion.config import IngestionConfigError, VolumeCaps, load_config
from ingestion.extraction import (
    is_remote_flag,
    locate_work_mode_spans,
    select_work_mode_span,
    work_mode_from_candidate_fields,
)
from ingestion.linkedin_cli import (
    LinkedInSearchCLI,
    RuntimeUnavailable,
    SourceRateLimited,
)
from ingestion.persistence import CandidateStore, PersistenceError
from ingestion.pipeline import LinkedInIngestionPipeline, QuerySpec
from ingestion.rate_limit import CapReached, RateLimiter
from policy import HardEligibilityGate
from policy.ruleset import PolicyRuleset

REPO_ROOT = Path(__file__).resolve().parent.parent
LIVE_DB = REPO_ROOT / "data" / "jobs-tracker.db"
POLICY_ARTIFACT = REPO_ROOT / "policy" / "jobops-policy-0.1.0.json"
INGESTION_DIR = REPO_ROOT / "ingestion"


def code_only(path):
    """
    A module's executable source, with docstrings and comments removed.

    These tests assert that ingestion contains no policy and no P0-07 logic.
    Prose that *names* a thing in order to say it is deliberately absent -
    "data/resume_config.json is never read", "identity_uncertain is P0-07" - is
    documentation, not an implementation, and must not trip the assertion.
    """
    source = path.read_text()
    lines = source.splitlines()
    docstring_lines = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            if ast.get_docstring(node, clean=False) is not None:
                first = node.body[0]
                docstring_lines.update(range(first.lineno, first.end_lineno + 1))
    return "\n".join(
        line for number, line in enumerate(lines, 1)
        if number not in docstring_lines and not line.strip().startswith("#"))


def ingestion_code():
    return "\n".join(code_only(path) for path in sorted(INGESTION_DIR.glob("*.py")))


# ==========================================================================
# Fixtures - LinkedIn CLI output, verbatim in shape with the CLI's contract
# ==========================================================================

def search_payload(*postings):
    """A `search --format json` stdout body: {"meta":{...},"results":[...]}."""
    return json.dumps({
        "meta": {"count": len(postings), "page": 1},
        "results": [{
            "id": p["id"],
            "title": p.get("title", "AI Quality Engineer"),
            "company": p.get("company", "Acme AI"),
            "companyUrl": None,
            "location": p.get("location", "India"),
            "date": p.get("date", "2026-08-28"),
            "url": p.get("url", f"https://www.linkedin.com/jobs/view/{p['id']}"),
        } for p in postings]
    })


def detail_payload(posting):
    """A `detail --format json` stdout body: a JobDetail object."""
    return json.dumps({
        "id": posting["id"],
        "title": posting.get("title", "AI Quality Engineer"),
        "company": posting.get("company", "Acme AI"),
        "companyUrl": None,
        "location": posting.get("location", "India"),
        "date": posting.get("date", "2026-08-28"),
        "url": posting.get("url", f"https://www.linkedin.com/jobs/view/{posting['id']}"),
        "description": posting.get("description", ""),
        "seniority": posting.get("seniority", "Mid-Senior level"),
        "employmentType": posting.get("employmentType", "Full-time"),
        "jobFunction": posting.get("jobFunction", "Quality Assurance"),
        "industries": posting.get("industries", "Software Development"),
    })


class FakeCliRunner:
    """
    Stands in for subprocess.run.

    Records every argv it was handed, so tests can assert on how the CLI was
    invoked as well as on what came back.
    """

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def __call__(self, command, cwd, timeout):
        self.calls.append(list(command))
        if not self.responses:
            raise AssertionError(f"FakeCliRunner ran out of responses for {command}")
        response = self.responses.pop(0)
        return subprocess.CompletedProcess(
            args=command, returncode=response.get("returncode", 0),
            stdout=response.get("stdout", ""), stderr=response.get("stderr", ""))


@pytest.fixture
def temp_db(tmp_path):
    """
    A database carrying the live schema for the two tables in play.

    The DDL is copied from the real database, opened read-only, so a schema
    drift in production shows up here as a test failure rather than as a
    passing test against a schema this file invented.
    """
    source = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
    try:
        statements = [row[0] for row in source.execute(
            "SELECT sql FROM sqlite_master WHERE tbl_name IN "
            "('scraped_jobs', 'opportunities') AND sql IS NOT NULL")]
    finally:
        source.close()

    path = tmp_path / "test-jobs.db"
    conn = sqlite3.connect(str(path))
    try:
        for statement in statements:
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path


@pytest.fixture
def config():
    return load_config()


def build_pipeline(tmp_path, temp_db, config, responses, *, run_id="test-run",
                   gate=None, caps=None):
    """A pipeline wired to fixtures: no network, no bun, no sleeping."""
    store_root = tmp_path / "store"
    limiter = RateLimiter(caps or config.caps,
                          store_root / "state" / "rate.json",
                          sleeper=lambda seconds: None,
                          clock=lambda: 10_000.0,
                          today="2026-08-31")
    runner = FakeCliRunner(responses)
    cli = LinkedInSearchCLI(config, limiter, runner=runner)
    pipeline = LinkedInIngestionPipeline(
        config=config, gate=gate or HardEligibilityGate(),
        store=CandidateStore(temp_db), cli=cli, rate_limiter=limiter,
        store_root=store_root, run_id=run_id)
    # preflight() would check for `bun`; the fixture path never launches it.
    pipeline._cli_version = {"runtime": "bun", "package_version": "1.0.0",
                             "skill_version": "1.0.0", "source_revision": "fixture"}
    pipeline.preflight = lambda: {"cli_version": pipeline._cli_version,
                                  "row_counts_before": pipeline.store.row_counts()}
    return pipeline, runner


def ingest_one(tmp_path, temp_db, config, posting, **kwargs):
    """Run the whole pipeline over exactly one fixture posting."""
    responses = [{"stdout": search_payload(posting)},
                 {"stdout": detail_payload(posting)}]
    pipeline, runner = build_pipeline(tmp_path, temp_db, config, responses, **kwargs)
    query = QuerySpec(location="India", query="AI Quality Engineer",
                      jobage=7, remote="remote", page=1, limit=1)
    summary = pipeline.run([query])
    ledger = [json.loads(line) for line in
              Path(summary["evidence_paths"]["candidates"]).read_text().splitlines()]
    return summary, ledger, pipeline, runner


# ==========================================================================
# 1-7  The owner-specified verdict vectors, end to end through ingestion
# ==========================================================================

REMOTE_BODY = "This is a fully remote role."
HYBRID_BODY = "Hybrid working model, 3 days in office."
ONSITE_BODY = "This is an On-site role based at our office."

VERDICT_VECTORS = [
    ("1  Remote + Rs22 LPA",
     {"id": "4400000001", "location": "India",
      "description": f"{REMOTE_BODY} Salary: ₹22 LPA."},
     "PASS", "REMOTE", ["WM-PASS-REMOTE", "COMP-PASS-AT-OR-ABOVE-FLOOR"]),

    ("2  Remote + Rs19 LPA",
     {"id": "4400000002", "location": "India",
      "description": f"{REMOTE_BODY} Salary: ₹19 LPA."},
     "FAIL", "REMOTE", ["COMP-FAIL-BELOW-FLOOR"]),

    ("3  Remote + no salary",
     {"id": "4400000003", "location": "India",
      "description": f"{REMOTE_BODY} Join a growing quality engineering team."},
     "UNKNOWN", "REMOTE", ["COMP-UNKNOWN-ABSENT"]),

    ("4  Hybrid + Rs30 LPA",
     {"id": "4400000004", "location": "Bengaluru, Karnataka, India",
      "description": f"{HYBRID_BODY} Compensation: ₹30 LPA."},
     "FAIL", "HYBRID", ["WM-FAIL-HYBRID"]),

    ("5  On-site + Rs30 LPA",
     {"id": "4400000005", "location": "Bengaluru, Karnataka, India",
      "description": f"{ONSITE_BODY} Compensation: ₹30 LPA."},
     "FAIL", "ONSITE", ["WM-FAIL-ONSITE"]),

    ("6  Remote + Rs18-24 LPA straddling range",
     {"id": "4400000006", "location": "India",
      "description": f"{REMOTE_BODY} Salary: ₹18–24 LPA."},
     "UNKNOWN", "REMOTE", ["COMP-UNKNOWN-RANGE-STRADDLES"]),

    ("7  Remote + non-INR compensation",
     {"id": "4400000007", "location": "India",
      "description": f"{REMOTE_BODY} Salary: $150,000 per year."},
     "UNKNOWN", "REMOTE", ["COMP-UNKNOWN-NO-INR-BASIS"]),
]


@pytest.mark.parametrize("label,posting,expected_verdict,expected_mode,expected_codes",
                         VERDICT_VECTORS, ids=[v[0] for v in VERDICT_VECTORS])
def test_ingested_posting_receives_the_expected_gate_verdict(
        tmp_path, temp_db, config, label, posting, expected_verdict,
        expected_mode, expected_codes):
    summary, ledger, _, _ = ingest_one(tmp_path, temp_db, config, posting)
    assert len(ledger) == 1
    record = ledger[0]
    verdict = record["gate_verdict"]

    assert verdict["verdict"] == expected_verdict
    assert verdict["normalized_work_mode"] == expected_mode
    assert set(expected_codes) <= set(verdict["reason_codes"])
    assert summary["counts"][f"gate_{expected_verdict.lower()}"] == 1


@pytest.mark.parametrize("label,posting,expected_verdict,expected_mode,expected_codes",
                         VERDICT_VECTORS, ids=[v[0] for v in VERDICT_VECTORS])
def test_ingestion_verdict_equals_the_gate_called_directly(
        tmp_path, temp_db, config, label, posting, expected_verdict,
        expected_mode, expected_codes):
    """
    Ingestion adds no verdict of its own.

    The record the pipeline writes must carry exactly what the gate returns for
    the same located evidence - same verdict, same codes, same rules fired.
    """
    _, ledger, pipeline, _ = ingest_one(tmp_path, temp_db, config, posting)
    record = ledger[0]

    located = record["located_evidence"]
    raw = {"candidate_id": record["candidate_id"]}
    if located["work_mode_selected"]:
        raw["work_mode_text"] = located["work_mode_selected"]["verbatim_text"]
    if located["work_mode_portal_claim"]:
        raw["portal_work_mode_field"] = located["work_mode_portal_claim"]
    if located["compensation_selected"]:
        raw["compensation_text"] = located["compensation_selected"]["verbatim_text"]

    direct = HardEligibilityGate().evaluate_posting(raw)
    assert direct.verdict == record["gate_verdict"]["verdict"]
    assert direct.reason_codes == record["gate_verdict"]["reason_codes"]
    assert direct.rules_fired == record["gate_verdict"]["rules_fired"]


def test_unknown_is_never_recorded_as_pass(tmp_path, temp_db, config):
    """Every UNKNOWN keeps its own verdict, is not scoring-eligible, and escalates."""
    for label, posting, expected, _mode, _codes in VERDICT_VECTORS:
        if expected != "UNKNOWN":
            continue
        _, ledger, _, _ = ingest_one(tmp_path, temp_db, config, posting,
                                     run_id=f"unknown-{posting['id']}")
        verdict = ledger[0]["gate_verdict"]
        assert verdict["verdict"] == "UNKNOWN"
        assert verdict["eligible_for_scoring"] is False
        assert verdict["requires_human_review"] is True
        assert verdict["reason_codes"], "an UNKNOWN with no reason code is unexplained"


def test_fail_candidates_are_retained_not_discarded(tmp_path, temp_db, config):
    """
    A FAIL is kept with its reason codes.

    P0_SPEC 5.2 achieves the career doc's "flagged for manual review" outcome by
    retention and visibility, not by a fourth verdict value - so a FAIL must
    reach the candidate table, not be dropped by the ingestion layer.
    """
    posting = VERDICT_VECTORS[3][1]  # Hybrid + Rs30 LPA
    summary, ledger, _, _ = ingest_one(tmp_path, temp_db, config, posting)
    assert ledger[0]["gate_verdict"]["verdict"] == "FAIL"
    assert ledger[0]["persistence"]["outcome"] == "inserted"
    assert summary["counts"]["persisted"] == 1


# ==========================================================================
# 8-9  Work mode: is_remote mapping, and ambiguity that must not become remote
# ==========================================================================

WORK_MODE_MAPPING = [
    ("Remote",                       "This role is fully remote.",          "REMOTE",    1),
    ("India (Remote)",               "Join our quality team.",              "REMOTE",    1),
    ("Bengaluru, Karnataka, India",  "Hybrid working model, 3 days in office.", "HYBRID",  0),
    ("Bengaluru, Karnataka, India",  "This is an On-site role.",            "ONSITE",    0),
    ("India",                        "We are remote-friendly.",             "AMBIGUOUS", 0),
    ("India",                        "Remote depending on location.",       "AMBIGUOUS", 0),
    ("India",                        "Remote with occasional travel to office.", "AMBIGUOUS", 0),
    ("India",                        "Location-dependent arrangement.",     "AMBIGUOUS", 0),
    ("Pune, Maharashtra, India",     "A great team and a strong roadmap.",  "ABSENT",    0),
]


@pytest.mark.parametrize("location,description,expected_mode,expected_flag",
                         WORK_MODE_MAPPING)
def test_work_mode_maps_to_is_remote_without_favouring_remote(
        location, description, expected_mode, expected_flag):
    normalizer = HardEligibilityGate().normalizer
    mode, _spans = work_mode_from_candidate_fields(
        normalizer, location=location, description=description)
    assert mode == expected_mode
    assert is_remote_flag(mode) == expected_flag


def test_is_remote_is_set_only_by_a_confirmed_remote():
    """The one direction the boolean is allowed to assert anything in."""
    assert is_remote_flag("REMOTE") == 1
    for mode in ("HYBRID", "ONSITE", "AMBIGUOUS", "ABSENT", None, "", "remote"):
        assert is_remote_flag(mode) == 0


def test_remote_elsewhere_in_the_body_does_not_override_a_stated_hybrid():
    """
    Selection precedence across spans, the multi-sentence case.

    A posting that advertises a remote-first culture and then states three days
    in office is not a remote posting. Reading the flattering sentence would
    turn a FAIL into a PASS.
    """
    normalizer = HardEligibilityGate().normalizer
    description = ("We are a fully remote company at heart. "
                   "This role is Hybrid: 3 days in office each week.")
    mode, _ = work_mode_from_candidate_fields(normalizer, location="India",
                                              description=description)
    assert mode in ("HYBRID", "AMBIGUOUS")
    assert mode != "REMOTE"
    assert is_remote_flag(mode) == 0


def test_portal_remote_filter_does_not_override_a_hybrid_body(tmp_path, temp_db, config):
    """
    WM-N1 survives ingestion.

    --remote remote is a server-side volume reducer, never evidence. A posting
    the filter returned whose body says hybrid resolves to AMBIGUOUS, escalated
    - the filter does not decide the work mode in either direction.
    """
    posting = {"id": "4400000010", "location": "India (Remote)",
               "description": "Hybrid working model, 3 days in office."}
    _, ledger, _, _ = ingest_one(tmp_path, temp_db, config, posting)
    verdict = ledger[0]["gate_verdict"]
    assert verdict["normalized_work_mode"] == "AMBIGUOUS"
    assert verdict["verdict"] == "UNKNOWN"
    assert verdict["unresolved_evidence"], "the conflict must be surfaced, not resolved"
    assert verdict["requires_human_review"] is True


def test_ambiguous_language_never_reaches_the_database_as_remote(
        tmp_path, temp_db, config):
    posting = {"id": "4400000011", "location": "India",
               "description": "We are remote-friendly. Salary: ₹30 LPA."}
    _, ledger, _, _ = ingest_one(tmp_path, temp_db, config, posting)
    assert ledger[0]["normalized_work_mode"] == "AMBIGUOUS"
    assert ledger[0]["is_remote_flag"] == 0


# --------------------------------------------------------------------------
# The bridge defect: scraped_jobs.location = "Remote" -> opportunities.is_remote
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def api_server_module():
    """Load api-server.py as a module. Its server start is under a main guard."""
    spec = importlib.util.spec_from_file_location(
        "api_server_under_test", REPO_ROOT / "api-server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BRIDGE_CASES = [
    ("Remote",                      "Fully remote role.",                       "REMOTE",    1),
    ("Bengaluru, Karnataka, India", "Hybrid working model, 3 days in office.",  "HYBRID",    0),
    ("Bengaluru, Karnataka, India", "This is an On-site role.",                 "ONSITE",    0),
    ("India",                       "We are remote-friendly.",                  "AMBIGUOUS", 0),
    ("India",                       "A strong engineering culture.",            "ABSENT",    0),
]


@pytest.mark.parametrize("location,description,expected_mode,expected_flag", BRIDGE_CASES)
def test_import_bridge_carries_work_mode_into_opportunities(
        api_server_module, temp_db, monkeypatch, location, description,
        expected_mode, expected_flag):
    """
    Regression for the bridge defect found during verification:
    scraped_jobs.location = "Remote" produced opportunities.is_remote = 0,
    because the INSERT omitted the column and took its default.

    This exercises the real handler, not a reimplementation of it.
    """
    conn = sqlite3.connect(str(temp_db))
    conn.row_factory = sqlite3.Row
    conn.execute(
        "INSERT INTO scraped_jobs (external_id, source, job_title, company, "
        "job_url, location, description) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (f"linkedin:test-{expected_mode}", "LinkedIn", "AI Quality Engineer",
         "Acme AI", "https://example.invalid/job/1", location, description))
    conn.commit()
    scraped_job_id = conn.execute(
        "SELECT id FROM scraped_jobs ORDER BY id DESC LIMIT 1").fetchone()["id"]

    monkeypatch.setattr(api_server_module, "get_db", lambda: conn)
    captured = {}
    handler = types.SimpleNamespace(
        _send_json_response=lambda data, status=200: captured.update(
            {"data": data, "status": status}))

    api_server_module.APIHandler._handle_import_scraped_job(handler, scraped_job_id)

    assert captured["data"].get("status") == "imported", captured
    assert captured["data"]["normalized_work_mode"] == expected_mode
    row = conn.execute("SELECT is_remote FROM opportunities WHERE scraped_job_id = ?",
                       (scraped_job_id,)).fetchone()
    assert row["is_remote"] == expected_flag
    conn.close()


def test_import_bridge_writes_is_remote_explicitly():
    """
    Guards the shape of the fix, not only its effect.

    The defect was an omitted column silently taking a default. A future edit
    that drops is_remote from the INSERT again would still satisfy a
    value-only assertion on a hybrid posting, since both produce 0.
    """
    source = (REPO_ROOT / "api-server.py").read_text()
    start = source.index("def _handle_import_scraped_job")
    end = source.index("def _send_json_response", start)
    handler_source = source[start:end]
    assert "INSERT INTO opportunities" in handler_source
    assert "is_remote" in handler_source
    assert "work_mode_from_candidate_fields" in handler_source


# ==========================================================================
# 10  The existing gate remains the only policy authority
# ==========================================================================

def test_moving_the_threshold_in_the_artifact_moves_the_ingested_verdict(
        tmp_path, temp_db, config):
    """
    Behavioural proof that ingestion holds no threshold of its own.

    A posting that passes at ₹20 LPA must FAIL when the artifact's threshold is
    ₹35 LPA, with nothing in ingestion changed. If ingestion carried a copy of
    the rule, this test would not move.
    """
    doc = json.loads(POLICY_ARTIFACT.read_text())
    doc["dimensions"]["compensation"]["threshold"]["value"] = 3_500_000
    altered = tmp_path / "altered-policy.json"
    altered.write_text(json.dumps(doc))

    description = f"{REMOTE_BODY} Salary: ₹22 LPA."
    # Distinct ids: an already-held posting is skipped by the detail pre-filter,
    # which would starve the second run of the very evidence under test.
    baseline_posting = {"id": "4400000020", "location": "India",
                        "description": description}
    moved_posting = {"id": "4400000021", "location": "India",
                     "description": description}

    _, baseline, _, _ = ingest_one(tmp_path, temp_db, config, baseline_posting,
                                   run_id="threshold-baseline")
    assert baseline[0]["gate_verdict"]["verdict"] == "PASS"

    altered_gate = HardEligibilityGate(ruleset=PolicyRuleset(altered))
    _, moved, _, _ = ingest_one(tmp_path, temp_db, config, moved_posting,
                                run_id="threshold-moved", gate=altered_gate)
    assert moved[0]["gate_verdict"]["verdict"] == "FAIL"
    assert "COMP-FAIL-BELOW-FLOOR" in moved[0]["gate_verdict"]["reason_codes"]


def test_ingestion_hardcodes_no_policy_constant():
    """
    No threshold figure, reason code, or verdict decision lives in ingestion.

    The verdict strings do appear - the pipeline counts PASS/UNKNOWN/FAIL and
    the runner documents them - so what is asserted here is the absence of
    policy VALUES and of any rule that produces a verdict.
    """
    banned_values = ("2000000", "2_000_000", "1800000", "1_800_000", "20 LPA",
                     "min_salary_inr")
    banned_codes = ("COMP-PASS", "COMP-FAIL", "WM-PASS", "WM-FAIL",
                    "COMP-UNKNOWN", "WM-UNKNOWN")
    for path in sorted(INGESTION_DIR.glob("*.py")):
        text = path.read_text()
        for value in banned_values:
            assert value not in text, f"{path.name} hardcodes policy value {value!r}"
        for code in banned_codes:
            assert code not in text, f"{path.name} hardcodes reason code {code!r}"


def test_ingestion_never_decides_a_verdict_itself():
    """
    The only source of a verdict in the pipeline is the gate.

    Asserted structurally: the pipeline assigns `result` from
    gate.evaluate_posting and from nowhere else.
    """
    text = (INGESTION_DIR / "pipeline.py").read_text()
    assert "self.gate.evaluate_posting(" in text
    for forbidden in ("verdict = \"PASS\"", "verdict = \"FAIL\"",
                      "verdict = \"UNKNOWN\"", "if annual_min", "if salary"):
        assert forbidden not in text, f"pipeline.py appears to decide policy: {forbidden}"


# ==========================================================================
# 11  data/resume_config.json is not read
# ==========================================================================

def test_ingestion_source_never_mentions_resume_config():
    for path in sorted(INGESTION_DIR.glob("*.py")):
        assert "resume_config" not in code_only(path), \
            f"{path.name} references data/resume_config.json in executable code"


def test_a_full_ingestion_run_opens_no_resume_config(tmp_path, temp_db, config,
                                                     monkeypatch):
    """Runtime proof, not only a source scan: any open() of it raises."""
    real_open = builtins.open
    touched = []

    def guarded_open(file, *args, **kwargs):
        if "resume_config" in str(file):
            touched.append(str(file))
            raise AssertionError(f"ingestion opened {file}")
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)
    posting = {"id": "4400000030", "location": "India",
               "description": f"{REMOTE_BODY} Salary: ₹22 LPA."}
    summary, ledger, _, _ = ingest_one(tmp_path, temp_db, config, posting,
                                       run_id="no-resume-config")
    assert not touched
    assert ledger[0]["gate_verdict"]["verdict"] == "PASS"
    assert summary["counts"]["persisted"] == 1


# ==========================================================================
# 12  Raw-source provenance is retained
# ==========================================================================

def test_raw_payload_is_retained_verbatim_and_reconstructs_what_was_received(
        tmp_path, temp_db, config):
    posting = {"id": "4400000040", "location": "India",
               "description": f"{REMOTE_BODY} Salary: ₹22 LPA."}
    expected_search_stdout = search_payload(posting)
    expected_detail_stdout = detail_payload(posting)

    _, ledger, pipeline, _ = ingest_one(tmp_path, temp_db, config, posting)
    provenance = ledger[0]["provenance"]

    search_raw = pipeline.raw_store.read(provenance["raw_payload_ref"])
    detail_raw = pipeline.raw_store.read(provenance["detail_raw_payload_ref"])
    assert search_raw["stdout"] == expected_search_stdout
    assert detail_raw["stdout"] == expected_detail_stdout
    assert search_raw["exit_code"] == 0
    assert search_raw["command"][0] == "bun"


def test_provenance_answers_every_question_section_7_5_requires(
        tmp_path, temp_db, config):
    posting = {"id": "4400000041", "location": "India",
               "description": f"{REMOTE_BODY} Salary: ₹22 LPA."}
    _, ledger, _, _ = ingest_one(tmp_path, temp_db, config, posting)
    record = ledger[0]
    provenance = record["provenance"]

    assert provenance["source_portal"] == "linkedin-search"      # which source
    assert provenance["source_mechanism"] == "cli"
    assert provenance["source_url"].endswith(posting["id"])       # what URL
    assert provenance["source_fetched_at"]                        # when observed
    assert provenance["raw_payload_ref"]                          # what payload
    assert provenance["cli_version"]["package_version"]           # which CLI
    assert record["extractor_version"] == config.version          # which extractor
    assert record["normalizer_version"] == "jobops-policy@0.1.0"
    assert record["derived_fields"]["job_title"] == "results[].title"
    assert record["gate_verdict"]["verdict"] == "PASS"            # which verdict
    assert provenance["source_query"]["query"] == "AI Quality Engineer"
    assert provenance["source_query"]["remote"] == "remote"


def test_evidence_spans_are_verbatim_never_paraphrased(tmp_path, temp_db, config):
    posting = {"id": "4400000042", "location": "India",
               "description": "This is a fully remote role. Salary: ₹22 LPA."}
    _, ledger, _, _ = ingest_one(tmp_path, temp_db, config, posting)
    located = ledger[0]["located_evidence"]
    for span in located["work_mode"] + located["compensation"]:
        assert span["verbatim_text"] in posting["description"]
    for item in ledger[0]["gate_verdict"]["evidence"]:
        if item["verbatim_text"]:
            assert item["verbatim_text"] in posting["description"]


def test_a_second_run_never_overwrites_the_first_runs_raw_evidence(
        tmp_path, temp_db, config):
    posting = {"id": "4400000043", "location": "India",
               "description": f"{REMOTE_BODY} Salary: ₹22 LPA."}
    _, first, pipeline_one, _ = ingest_one(tmp_path, temp_db, config, posting,
                                           run_id="run-one")
    first_ref = first[0]["provenance"]["raw_payload_ref"]
    first_body = pipeline_one.raw_store.read(first_ref)

    _, second, pipeline_two, _ = ingest_one(tmp_path, temp_db, config, posting,
                                            run_id="run-two")
    assert second[0]["provenance"]["raw_payload_ref"] != first_ref
    assert pipeline_one.raw_store.read(first_ref) == first_body


def test_run_manifest_carries_the_run_level_counts(tmp_path, temp_db, config):
    posting = {"id": "4400000044", "location": "India",
               "description": f"{REMOTE_BODY} Salary: ₹22 LPA."}
    summary, _, _, _ = ingest_one(tmp_path, temp_db, config, posting)
    manifest = json.loads(Path(summary["evidence_paths"]["manifest"]).read_text())

    for key in ("run_id", "started_at", "finished_at", "queries", "counts",
                "terminating_condition", "errors", "rate_limiting",
                "row_counts_before", "row_counts_after", "policy_ruleset_version"):
        assert key in manifest, f"run manifest is missing {key}"
    for key in ("returned_by_linkedin", "normalized", "rejected_unparseable",
                "gate_pass", "gate_unknown", "gate_fail", "persisted",
                "skipped_existing", "detail_fetched"):
        assert key in manifest["counts"], f"counts is missing {key}"
    assert manifest["queries"][0]["command"].startswith("bun run")


# ==========================================================================
# 13  Re-running the same bounded ingestion does not multiply records
# ==========================================================================

def test_rerunning_the_same_query_inserts_no_duplicate_rows(tmp_path, temp_db,
                                                            config):
    """
    The existing identity contract, and only that.

    scraped_jobs.external_id is UNIQUE and LinkedIn ids are namespaced into it,
    so INSERT OR IGNORE makes the second run a no-op at the row level. This is
    L1 single-source identity - not P0-07.
    """
    posting = {"id": "4400000050", "location": "India",
               "description": f"{REMOTE_BODY} Salary: ₹22 LPA."}
    first, ledger_one, _, _ = ingest_one(tmp_path, temp_db, config, posting,
                                         run_id="dup-one")
    assert first["counts"]["persisted"] == 1
    assert first["row_counts_after"]["scraped_jobs"] == 1

    second, ledger_two, _, runner_two = ingest_one(tmp_path, temp_db, config,
                                                   posting, run_id="dup-two")
    assert second["counts"]["persisted"] == 0
    assert second["counts"]["skipped_existing"] == 1
    assert second["row_counts_after"]["scraped_jobs"] == 1
    assert ledger_two[0]["persistence"]["outcome"] == "skipped_existing"

    with sqlite3.connect(str(temp_db)) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM scraped_jobs WHERE external_id = ?",
            ("linkedin:4400000050",)).fetchone()[0]
    assert count == 1


def test_a_posting_already_held_costs_no_detail_call(tmp_path, temp_db, config):
    """
    The detail pre-filter is an identity filter, and it is real.

    P0_SPEC 7.3 requires detail to be fetched only for pre-filtered candidates.
    A second run over an already-held posting must issue the search call and no
    detail call at all.
    """
    posting = {"id": "4400000051", "location": "India",
               "description": f"{REMOTE_BODY} Salary: ₹22 LPA."}
    ingest_one(tmp_path, temp_db, config, posting, run_id="prefilter-one")

    responses = [{"stdout": search_payload(posting)}]  # no detail response supplied
    pipeline, runner = build_pipeline(tmp_path, temp_db, config, responses,
                                      run_id="prefilter-two")
    summary = pipeline.run([QuerySpec(location="India", query="AI Quality Engineer",
                                      jobage=7, remote="remote", page=1, limit=1)])
    assert summary["counts"]["detail_fetched"] == 0
    assert summary["rate_limiting"]["run_detail_calls"] == 0
    assert len(runner.calls) == 1
    assert runner.calls[0][3] == "search"


def test_external_ids_are_namespaced_by_portal(config):
    """
    scraped_jobs.external_id is UNIQUE table-wide, not per source, so a bare
    numeric LinkedIn id could collide with a bare numeric id from another
    portal and silently suppress a real posting.
    """
    assert config.external_id_for("4426311357") == "linkedin:4426311357"


def test_persisted_row_preserves_source_identity_and_url(tmp_path, temp_db, config):
    posting = {"id": "4400000052", "location": "India (Remote)",
               "company": "Acme AI", "title": "AI Quality Engineer",
               "description": f"{REMOTE_BODY} Salary: ₹22 LPA."}
    ingest_one(tmp_path, temp_db, config, posting)
    with sqlite3.connect(str(temp_db)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM scraped_jobs WHERE external_id = ?",
                           ("linkedin:4400000052",)).fetchone()
    assert row["source"] == "LinkedIn"
    assert row["job_url"] == f"https://www.linkedin.com/jobs/view/{posting['id']}"
    assert row["location"] == "India (Remote)"
    assert row["posted_date"] == "2026-08-28"
    assert row["salary_range"] == "Salary: ₹22 LPA."


def test_p0_06_writes_no_scoring_columns(tmp_path, temp_db, config):
    """P0-06 does not score. A scoring column filled with a placeholder would
    make an unscored candidate indistinguishable from a scored one."""
    posting = {"id": "4400000053", "location": "India",
               "description": f"{REMOTE_BODY} Salary: ₹22 LPA."}
    ingest_one(tmp_path, temp_db, config, posting)
    with sqlite3.connect(str(temp_db)) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM scraped_jobs WHERE external_id = ?",
                           ("linkedin:4400000053",)).fetchone()
    for column in ("match_score", "classification", "matched_skills",
                   "matched_domains", "red_flags", "recommendation"):
        assert row[column] is None, f"{column} was written by P0-06"
    assert row["imported_to_opportunities"] == 0


def test_ingestion_touches_no_table_but_scraped_jobs(tmp_path, temp_db, config):
    posting = {"id": "4400000054", "location": "India",
               "description": f"{REMOTE_BODY} Salary: ₹22 LPA."}
    summary, _, _, _ = ingest_one(tmp_path, temp_db, config, posting)
    assert summary["row_counts_before"]["opportunities"] == \
        summary["row_counts_after"]["opportunities"]


# ==========================================================================
# Volume and rate control
# ==========================================================================

def test_configured_concurrency_must_be_one():
    with pytest.raises(IngestionConfigError):
        VolumeCaps(1, 1, 1, 1, 1, 1, 1.0, concurrency=4)


def test_shipped_caps_are_conservative(config):
    caps = config.caps
    assert caps.concurrency == 1
    assert caps.min_interval_seconds >= 1.0
    assert caps.max_search_calls_per_run <= caps.daily_max_search_calls
    assert caps.max_detail_calls_per_run <= caps.daily_max_detail_calls
    assert caps.max_pages_per_query == 1
    assert caps.max_results_per_run <= config.results_per_page


def test_per_run_search_cap_stops_the_run(tmp_path, config):
    caps = config.caps
    limiter = RateLimiter(
        VolumeCaps(1, 5, 1, 10, 100, 100, 0.0, 1),
        tmp_path / "rate.json", sleeper=lambda s: None, clock=lambda: 0.0)
    limiter.acquire_search()
    with pytest.raises(CapReached) as excinfo:
        limiter.acquire_search()
    assert excinfo.value.cap_name == "max_search_calls_per_run"
    assert excinfo.value.scope == "run"


def test_daily_cap_survives_a_new_process(tmp_path, config):
    """
    The daily cap is enforced from a persisted counter, not per-invocation.

    A second RateLimiter reading the same state file must see the first one's
    consumption - otherwise re-running the script resets the day's budget.
    """
    state = tmp_path / "rate.json"
    caps = VolumeCaps(10, 10, 1, 10, 2, 10, 0.0, 1)
    first = RateLimiter(caps, state, sleeper=lambda s: None, clock=lambda: 0.0,
                        today="2026-08-31")
    first.acquire_search()
    first.acquire_search()

    second = RateLimiter(caps, state, sleeper=lambda s: None, clock=lambda: 0.0,
                         today="2026-08-31")
    with pytest.raises(CapReached) as excinfo:
        second.acquire_search()
    assert excinfo.value.scope == "daily"

    tomorrow = RateLimiter(caps, state, sleeper=lambda s: None, clock=lambda: 0.0,
                           today="2026-09-01")
    tomorrow.acquire_search()  # a new UTC day starts over, and does not carry forward
    assert tomorrow.daily.search_calls == 1


def test_unreadable_counter_file_does_not_grant_a_fresh_budget(tmp_path, config):
    state = tmp_path / "rate.json"
    state.write_text("{not json")
    with pytest.raises(RuntimeError, match="unreadable"):
        RateLimiter(config.caps, state, sleeper=lambda s: None, clock=lambda: 0.0)


def test_minimum_interval_is_actually_waited(tmp_path):
    slept = []
    ticks = iter([0.0, 1.0, 1.0])
    limiter = RateLimiter(VolumeCaps(5, 5, 1, 10, 100, 100, 5.0, 1),
                          tmp_path / "rate.json", sleeper=slept.append,
                          clock=lambda: next(ticks))
    limiter.acquire_search()
    limiter.acquire_search()
    assert slept == [4.0], "the second request must wait out the remaining interval"


def test_pagination_beyond_the_page_cap_is_refused(tmp_path, config):
    limiter = RateLimiter(config.caps, tmp_path / "rate.json",
                          sleeper=lambda s: None, clock=lambda: 0.0)
    limiter.check_page(1)
    with pytest.raises(CapReached) as excinfo:
        limiter.check_page(2)
    assert excinfo.value.cap_name == "max_pages_per_query"


def test_detail_cap_terminates_the_run_normally(tmp_path, temp_db, config):
    """Reaching a cap is a terminating condition in the summary, not an error."""
    postings = [{"id": f"44000001{n:02d}", "location": "India",
                 "description": f"{REMOTE_BODY} Salary: ₹22 LPA."} for n in range(4)]
    responses = [{"stdout": search_payload(*postings)}]
    responses += [{"stdout": detail_payload(p)} for p in postings]
    caps = VolumeCaps(2, 2, 1, 10, 100, 100, 0.0, 1)  # detail cap of 2
    pipeline, runner = build_pipeline(tmp_path, temp_db, config, responses,
                                      run_id="detail-cap", caps=caps)
    summary = pipeline.run([QuerySpec(location="India", query="AI Quality Engineer",
                                      page=1, limit=4)])
    assert summary["counts"]["detail_fetched"] == 2
    assert "max_detail_calls_per_run" in summary["terminating_condition"]
    assert summary["rate_limiting"]["run_detail_calls"] == 2
    # Postings past the cap are still normalized and gated from search evidence;
    # none is silently dropped.
    assert summary["counts"]["normalized"] == 4


def test_the_cli_is_invoked_with_the_bounded_flags(tmp_path, temp_db, config):
    posting = {"id": "4400000060", "location": "India",
               "description": f"{REMOTE_BODY} Salary: ₹22 LPA."}
    _, _, _, runner = ingest_one(tmp_path, temp_db, config, posting)
    argv = runner.calls[0]
    assert argv[:3] == ["bun", "run", "cli/src/cli.ts"]
    assert argv[3] == "search"
    assert "--location" in argv and "--limit" in argv and "--page" in argv
    assert argv[argv.index("--page") + 1] == "1"
    assert argv[argv.index("--format") + 1] == "json"
    assert "--jobage-minutes" not in argv, "--jobage and --jobage-minutes conflict"


def test_the_pipeline_has_no_parallel_code_path():
    """No concurrency against this source, asserted structurally (P0_SPEC 7.3)."""
    for path in sorted(INGESTION_DIR.glob("*.py")):
        text = path.read_text()
        for token in ("ThreadPool", "ProcessPool", "concurrent.futures",
                      "asyncio", "threading.Thread", "multiprocessing"):
            assert token not in text, f"{path.name} introduces concurrency: {token}"


# ==========================================================================
# Failure handling
# ==========================================================================

def test_missing_runtime_fails_explicitly_and_offers_no_substitute(config,
                                                                   tmp_path,
                                                                   monkeypatch):
    limiter = RateLimiter(config.caps, tmp_path / "rate.json",
                          sleeper=lambda s: None, clock=lambda: 0.0)
    cli = LinkedInSearchCLI(config, limiter, runner=FakeCliRunner([]))
    monkeypatch.setattr("ingestion.linkedin_cli.shutil.which", lambda name: None)
    with pytest.raises(RuntimeUnavailable) as excinfo:
        cli.preflight()
    message = str(excinfo.value)
    assert "bun" in message
    assert "not on PATH" in message
    for substitute in ("RemoteOK", "Naukri", "Indeed", "fallback to"):
        assert substitute.lower() not in message.lower().replace(
            "fallback to another source", "")


def test_cli_error_is_recorded_verbatim_and_does_not_abort_the_run(
        tmp_path, temp_db, config):
    """P0_SPEC 7.4: record the error with its code, continue the run."""
    posting = {"id": "4400000070", "location": "India",
               "description": f"{REMOTE_BODY} Salary: ₹22 LPA."}
    responses = [
        {"stdout": search_payload(posting)},
        {"returncode": 1, "stderr": json.dumps({"error": "Job not found",
                                                "code": "NOT_FOUND"})},
    ]
    pipeline, _ = build_pipeline(tmp_path, temp_db, config, responses,
                                 run_id="cli-error")
    summary = pipeline.run([QuerySpec(location="India", page=1, limit=1)])
    manifest = json.loads(Path(summary["evidence_paths"]["manifest"]).read_text())
    detail_errors = [e for e in manifest["errors"] if e["stage"] == "detail"]
    assert detail_errors[0]["error"] == {"error": "Job not found", "code": "NOT_FOUND"}
    # The posting is still normalized and gated from the search evidence.
    assert summary["counts"]["normalized"] == 1
    assert summary["counts"]["persisted"] == 1


def test_rate_limit_stops_the_source_and_is_never_recorded_as_broken(
        tmp_path, temp_db, config):
    responses = [{"returncode": 1,
                  "stderr": json.dumps({"error": "HTTP 429 Too Many Requests",
                                        "code": "SEARCH_FAILED"})}]
    pipeline, _ = build_pipeline(tmp_path, temp_db, config, responses,
                                 run_id="rate-limited")
    summary = pipeline.run([QuerySpec(location="India", page=1, limit=1)])
    manifest = json.loads(Path(summary["evidence_paths"]["manifest"]).read_text())
    assert manifest["queries"][0]["outcome"] == "rate_limited"
    assert "broken" not in json.dumps(manifest).lower()
    assert pipeline.cli._rate_limited is True
    with pytest.raises(SourceRateLimited):
        pipeline.cli.search(location="India")


def test_malformed_json_is_retained_and_excluded_not_guessed(tmp_path, temp_db,
                                                             config):
    responses = [{"stdout": '{"meta": {"count": 1}, "results": [ truncated'}]
    pipeline, _ = build_pipeline(tmp_path, temp_db, config, responses,
                                 run_id="unparseable")
    summary = pipeline.run([QuerySpec(location="India", page=1, limit=1)])
    manifest = json.loads(Path(summary["evidence_paths"]["manifest"]).read_text())
    assert manifest["counts"]["rejected_unparseable"] == 1
    assert manifest["counts"]["normalized"] == 0
    assert manifest["counts"]["persisted"] == 0
    raw = pipeline.raw_store.read(manifest["queries"][0]["raw_payload_ref"])
    assert raw["stdout"] == responses[0]["stdout"] if responses else True


def test_zero_results_is_recorded_as_suspect_not_as_no_jobs(tmp_path, temp_db,
                                                            config):
    responses = [{"stdout": search_payload()}]
    pipeline, _ = build_pipeline(tmp_path, temp_db, config, responses,
                                 run_id="zero-results")
    summary = pipeline.run([QuerySpec(location="India", page=1, limit=1)])
    manifest = json.loads(Path(summary["evidence_paths"]["manifest"]).read_text())
    assert any(e.get("outcome") == "suspect_zero_results" for e in manifest["errors"])
    assert summary["counts"]["returned_by_linkedin"] == 0


def test_schema_verification_reports_rather_than_migrates(temp_db):
    store = CandidateStore(temp_db)
    store.verify_schema()
    with sqlite3.connect(str(temp_db)) as conn:
        conn.execute("ALTER TABLE scraped_jobs RENAME TO scraped_jobs_old")
    with pytest.raises(PersistenceError, match="does not exist"):
        store.verify_schema()


# ==========================================================================
# Scope boundaries this task must not cross
# ==========================================================================

def test_p0_06_implements_no_gmail_n8n_or_submission_path():
    for path in sorted(INGESTION_DIR.glob("*.py")):
        text = path.read_text().lower()
        for token in ("smtp", "gmail", "n8n", "sendmail", "apply_to_job",
                      "submit_application"):
            assert token not in text, f"{path.name} reaches beyond P0-06: {token}"


def test_p0_06_does_not_import_the_scorer():
    for path in sorted(INGESTION_DIR.glob("*.py")):
        text = path.read_text()
        assert "simple_scorer" not in text
        assert "SimpleJobScorer" not in text


def test_p0_06_imports_nothing_from_ai_job_search():
    """
    JS-R3: the CLI is a subprocess with a stdout contract, not a library.

    `ai-job-search` may be named as a path - it is where the CLI lives - but
    nothing from it may be imported.
    """
    for path in sorted(INGESTION_DIR.glob("*.py")):
        for line in path.read_text().splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                assert "ai_job_search" not in stripped
                assert "ai-job-search" not in stripped


def test_p0_07_deduplication_is_not_implemented_here():
    """
    Guards the boundary in both directions.

    P0-06 claims exactly one identity layer: L1, (source_portal, external_id),
    provided by the existing INSERT OR IGNORE contract. If a later session adds
    URL canonicalization, fuzzy matching, or opportunities matching to this
    package, that is P0-07 work and this test should fail until the boundary is
    restated deliberately.
    """
    code = ingestion_code()
    for token in ("canonicalize_url", "canonical_url", "fuzzy", "levenshtein",
                  "SequenceMatcher", "difflib", "auto_merge", "probable_match"):
        assert token not in code, f"P0-07 dedup logic appears in P0-06: {token}"


def test_the_only_identity_query_is_the_l1_external_id_check():
    """
    The one identity question P0-06 asks the database is "do we already hold
    this external_id?". Matching a candidate against `opportunities` - so that
    something already applied to is not re-surfaced - is P0-07 and is not asked
    here.
    """
    code = ingestion_code()
    statements = [line.strip() for line in code.splitlines()
                  if any(clause in line for clause in
                         ("FROM opportunities", "INTO opportunities",
                          "UPDATE opportunities", "JOIN opportunities"))]
    assert statements == ['"SELECT COUNT(*) FROM opportunities").fetchone()[0],'], \
        f"ingestion queries opportunities beyond the row count: {statements}"
    assert "WHERE external_id IN" in code


def test_the_dedup_boundary_is_declared_in_the_config_artifact():
    """The boundary is documented where an auditor will look for it."""
    boundary = load_config().raw["persistence"]["dedup_boundary"]
    for expected in ("L2", "L3", "L4", "P0-07", "opportunities",
                     "identity_uncertain"):
        assert expected in boundary


def test_p0_06_applies_no_migration():
    text = "\n".join(p.read_text() for p in sorted(INGESTION_DIR.glob("*.py")))
    for token in ("ALTER TABLE", "CREATE TABLE", "DROP TABLE", "CREATE INDEX",
                  "PRAGMA user_version"):
        assert token not in text, f"ingestion attempts a schema change: {token}"


def test_ai_native_signal_is_not_a_gate_dimension():
    """
    FS-01 is P1 Opportunity Quality. Source evidence that could later support
    it is preserved in the retained raw payload and the persisted description;
    nothing scores or ranks on it, and it is not a gate dimension.
    """
    text = "\n".join(p.read_text() for p in sorted(INGESTION_DIR.glob("*.py")))
    for token in ("ai_native", "ai_maturity", "opportunity_quality",
                  "company_score"):
        assert token not in text.lower(), f"P1 scoring signal appears in P0-06: {token}"
