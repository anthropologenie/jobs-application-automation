#!/usr/bin/env python3
"""
P0-10 per-candidate time instrumentation - deterministic tests

Hermetic fixtures for behaviour, plus READ-ONLY assertions against the live
database, the retained evidence of the first real LinkedIn run, and the live
decision ledger. No test in this file writes to data/jobs-tracker.db, to the
candidate ledger, to data/review/decisions.jsonl or to
data/application/submissions.jsonl; every write a test performs goes to
tmp_path.

What these tests assert:

  * a duration is computed only where BOTH its events were recorded - a missing
    event yields NOT_AVAILABLE, never zero and never a fabricated interval;
  * ACCEPT is not SUBMITTED: a decision to apply creates no submission, implies
    no submission time, and cannot be completed into one;
  * a submission exists only because a human explicitly recorded it, and
    recording one changes no verdict, no evidence, no provenance and no
    decision;
  * elapsed lifecycle time is never presented as active human effort, which
    this architecture cannot observe at all;
  * suppressed definite duplicates do not inflate active throughput, and L3
    probable duplicates remain counted as the real review work they are;
  * legacy NOT_EVALUATED rows stay out of the evaluated funnel and are never
    backfilled or given an invented evaluation timestamp;
  * ZERO, NOT_AVAILABLE, INSUFFICIENT_DATA and NOT_MEASURABLE stay four
    different answers;
  * P0-10 writes nothing that P0-01..P0-08 owns, submits nothing, and opens no
    network connection.

The four existing suites (P0-02, P0-06, P0-07, P0-08) are unchanged by this
work; `test_ad_*` asserts read-only that the live stores they own are untouched
by a full P0-10 report, and the suites themselves are run in full alongside
this file.

Run:
    python3 -m pytest tests/test_p0_10_time_instrumentation.py -v

Author: Karthik Shetty
Created: 2026-09-07
"""

import ast
import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from review.decisions import Decision, DecisionStore, utc_now_iso
from review.ledger import CandidateLedgerStore
from review.queue import ReviewQueue
from review.ruleset import load_review_ruleset

from timing.clock import TimestampError, minutes_between, parse_timestamp
from timing.lifecycle import LifecycleReader
from timing.metrics import TimingReport, distribution, per_day, rate
from timing.ruleset import (
    INCONSISTENT,
    INSUFFICIENT_DATA,
    MEASURED,
    NOT_AVAILABLE,
    NOT_MEASURABLE,
    TimingDriftError,
    load_timing_ruleset,
)
from timing.submissions import (
    SOURCE_HUMAN_STATED,
    SubmissionError,
    SubmissionEvent,
    SubmissionStore,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
LIVE_DB = REPO_ROOT / "data" / "jobs-tracker.db"
LIVE_LEDGER_ROOT = REPO_ROOT / "data" / "ingestion"
LIVE_DECISIONS = REPO_ROOT / "data" / "review" / "decisions.jsonl"
LIVE_SUBMISSIONS = REPO_ROOT / "data" / "application" / "submissions.jsonl"
TIMING_DIR = REPO_ROOT / "timing"
TIMING_ARTIFACT = TIMING_DIR / "jobops-timing-0.1.0.json"

EVALUATED_AT = "2026-09-01T10:00:00+00:00"
DECIDED_AT = "2026-09-01T10:20:00+00:00"
SUBMITTED_AT = "2026-09-01T14:20:00+00:00"


def code_only(path):
    """A module's executable source, docstrings and comments removed."""
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


def timing_code():
    return "\n".join(code_only(p) for p in sorted(TIMING_DIR.glob("*.py")))


def digest(path):
    return (hashlib.sha256(Path(path).read_bytes()).hexdigest()
            if Path(path).exists() else None)


# ==========================================================================
# Fixtures - a hermetic database, ledger, decision store and submission store
# ==========================================================================

@pytest.fixture(scope="module")
def timing_ruleset():
    return load_timing_ruleset()


@pytest.fixture
def temp_db(tmp_path):
    """A database carrying the live DDL for the two tables in play."""
    source = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
    try:
        statements = [row[0] for row in source.execute(
            "SELECT sql FROM sqlite_master WHERE tbl_name IN "
            "('scraped_jobs', 'opportunities') AND sql IS NOT NULL")]
    finally:
        source.close()

    path = tmp_path / "timing-test.db"
    conn = sqlite3.connect(str(path))
    try:
        for statement in statements:
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path


def insert_job(db_path, *, row_id, external_id, source="LinkedIn",
               title="AI Quality Engineer", company="Acme AI", url=None,
               location="Bengaluru, Karnataka, India",
               scraped_at="2026-09-01 09:59:30"):
    url = url or f"https://www.linkedin.com/jobs/view/{external_id.split(':')[-1]}"
    conn = sqlite3.connect(str(db_path))
    try:
        with conn:
            conn.execute(
                "INSERT INTO scraped_jobs (id, external_id, source, job_title, "
                "company, job_url, location, scraped_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (row_id, external_id, source, title, company, url, location,
                 scraped_at))
    finally:
        conn.close()
    return f"scraped_jobs:{row_id}"


def insert_opportunity(db_path, *, row_id, company, role, url=None,
                       source="LinkedIn", status="Lead", scraped_job_id=None,
                       created_at="2026-09-01 11:00:00", applied_date=None):
    conn = sqlite3.connect(str(db_path))
    try:
        with conn:
            conn.execute(
                "INSERT INTO opportunities (id, company, role, job_url, source, "
                "status, scraped_job_id, created_at, applied_date) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (row_id, company, role, url, source, status, scraped_job_id,
                 created_at, applied_date))
    finally:
        conn.close()
    return f"opportunities:{row_id}"


def ledger_record(external_id, *, verdict="UNKNOWN",
                  reason_codes=("WM-UNKNOWN-ABSENT",), work_mode="ABSENT",
                  evaluated_at=EVALUATED_AT, source_fetched_at="2026-09-01T09:59:00+00:00",
                  ruleset_version="jobops-policy@0.1.0", evidence=None):
    """One candidate ledger record, shaped exactly like the real ones."""
    return {
        "candidate_id": external_id,
        "external_id": external_id,
        "source_portal": "linkedin-search",
        "provenance": {
            "source_portal": "linkedin-search",
            "source_mechanism": "cli",
            "source_query": {"query": "AI Quality Engineer", "remote": "remote"},
            "source_fetched_at": source_fetched_at,
            "raw_payload_ref": f"raw/linkedin-search/run/search-{external_id}.json",
            "source_url": f"https://www.linkedin.com/jobs/view/{external_id.split(':')[-1]}",
            "detail_fetched_at": "2026-09-01T09:59:40+00:00",
        },
        "extractor_version": "linkedin-ingestion@0.1.0",
        "normalizer_version": ruleset_version,
        "located_evidence": {"work_mode": [], "compensation": []},
        "normalized_candidate_row": {},
        "normalized_work_mode": work_mode,
        "gate_verdict": {
            "candidate_id": external_id,
            "verdict": verdict,
            "ruleset_version": ruleset_version,
            "evaluated_at": evaluated_at,
            "reason_codes": list(reason_codes),
            "dimension_verdicts": {"work_mode": "UNKNOWN" if work_mode == "ABSENT"
                                   else "PASS",
                                   "compensation": "UNKNOWN"},
            "rules_fired": ["WM-R5"],
            "normalized_work_mode": work_mode,
            "normalized_compensation": {"state": "ABSENT"},
            "work_mode_provenance": None,
            "compensation_provenance": None,
            "requires_human_review": verdict == "UNKNOWN",
            "evidence": evidence if evidence is not None else [],
            "unresolved_evidence": [],
            "company_type_signal": None,
            "eligible_for_scoring": verdict == "PASS",
        },
        "persistence": {"table": "scraped_jobs", "outcome": "inserted"},
    }


@pytest.fixture
def instrumented(tmp_path, timing_ruleset):
    """
    A LifecycleReader over a hermetic queue, decision store and submission store.

    Returns a helper carrying the reader plus the two write surfaces, so a test
    can record a decision (P0-08's store) and a submission (P0-10's) and see
    what the instrumentation makes of them - without either store being the
    live one.
    """
    class Harness:
        def __init__(self, db_path, records=None, run_id="run-0001"):
            ledger_root = tmp_path / "ingestion"
            (ledger_root / "candidates").mkdir(parents=True, exist_ok=True)
            if records:
                with open(ledger_root / "candidates" / f"{run_id}.jsonl", "w",
                          encoding="utf-8") as handle:
                    for record in records:
                        handle.write(json.dumps(record) + "\n")
            self.decision_root = tmp_path / "review"
            self.submission_root = tmp_path / "application"
            self.decisions = DecisionStore(self.decision_root,
                                           ruleset=load_review_ruleset())
            self.submissions = SubmissionStore(self.submission_root,
                                               ruleset=timing_ruleset)
            self.ledger_path = ledger_root / "candidates" / f"{run_id}.jsonl"
            self.queue = ReviewQueue(db_path=db_path,
                                     ledger=CandidateLedgerStore(ledger_root),
                                     decisions=self.decisions)
            self.reader = LifecycleReader(queue=self.queue,
                                          submissions=self.submissions,
                                          ruleset=timing_ruleset)

        def timeline(self, candidate_ref):
            return {t.candidate_ref: t
                    for t in self.reader.timelines()}[candidate_ref]

        def report(self):
            return TimingReport(reader=self.reader,
                                ruleset=timing_ruleset).build()

        def decide(self, candidate_ref, kind="ACCEPT", decided_at=DECIDED_AT,
                   **kwargs):
            return self.decisions.record(Decision(
                candidate_ref=candidate_ref, kind=kind, decided_at=decided_at,
                machine_context=self.queue.machine_context_for(candidate_ref),
                **kwargs))

        def submit(self, candidate_ref, submitted_at=SUBMITTED_AT, **kwargs):
            standing = self.reader.human_block(
                self.queue.build().entry(candidate_ref).payload["human"]
            )["standing_accept"]
            return self.submissions.record(SubmissionEvent(
                candidate_ref=candidate_ref, submitted_at=submitted_at,
                decision_ref=standing["decision_id"] if standing else None,
                **kwargs))

    return Harness


@pytest.fixture
def one_unknown(temp_db, instrumented):
    """One evaluated UNKNOWN candidate, no human action yet."""
    ref = insert_job(temp_db, row_id=1, external_id="linkedin:1001")
    return ref, instrumented(temp_db, [ledger_record("linkedin:1001")])


# ==========================================================================
# A / B / C - the decision timestamp, and what it does and does not mean
# ==========================================================================

def test_a_an_existing_human_decision_timestamp_is_read_exactly_as_written(one_unknown):
    """P0-10 reads P0-08's ledger. It does not round, re-stamp or rewrite it."""
    ref, harness = one_unknown
    recorded = harness.decide(ref, decided_at=DECIDED_AT)
    before = digest(harness.decisions.path)

    timeline = harness.timeline(ref)
    assert timeline.events["HUMAN_DECISION"]["at"] == DECIDED_AT
    assert timeline.human["standing_decided_at"] == DECIDED_AT
    assert timeline.human["standing_decision_id"] == recorded["decision_id"]
    # Building the report reads the ledger and changes nothing in it.
    harness.report()
    assert digest(harness.decisions.path) == before


def test_b_time_to_decision_is_computed_from_the_two_recorded_events(one_unknown):
    ref, harness = one_unknown
    harness.decide(ref)
    interval = harness.timeline(ref).intervals["time_from_evaluation_to_decision"]

    assert interval["state"] == MEASURED
    assert interval["minutes"] == 20.0
    assert interval["start_event"] == "CANDIDATE_EVALUATED"
    assert interval["end_event"] == "HUMAN_DECISION"
    assert interval["start_at"] == EVALUATED_AT
    assert interval["end_at"] == DECIDED_AT

    report = harness.report()["durations"]["time_from_evaluation_to_decision"]
    assert report["state"] == MEASURED
    assert report["median"] == 20.0 and report["n"] == 1


def test_c_time_to_decision_is_never_presented_as_active_human_effort(one_unknown,
                                                                     timing_ruleset):
    """
    20 minutes of elapsed time is not 20 minutes of human attention, and nothing
    in this package is allowed to name it as though it were.
    """
    ref, harness = one_unknown
    harness.decide(ref)
    interval = harness.timeline(ref).intervals["time_from_evaluation_to_decision"]
    assert interval["is_active_human_effort"] is False
    assert interval["measures"] == "elapsed_lifecycle"

    metric = harness.report()["durations"]["time_from_evaluation_to_decision"]
    assert metric["is_active_human_effort"] is False

    assert timing_ruleset.measures_active_human_effort(
        "time_from_evaluation_to_decision") is False
    for forbidden in ("review_time", "active_human_time", "human_review_minutes",
                      "effort_minutes"):
        assert forbidden not in timing_code()
        assert forbidden not in TIMING_ARTIFACT.read_text().replace(
            "active_human_time", "")  # the artifact may only NAME the ban


def test_c2_active_human_effort_is_declared_not_measurable(timing_ruleset):
    review_ended = timing_ruleset.unobserved_event("REVIEW_ENDED")
    assert "ACTIVE HUMAN EFFORT IS NOT DIRECTLY MEASURABLE" in \
        review_ended["consequence"]
    assert timing_ruleset.state_override(
        "applications_per_unit_of_human_effort") == NOT_MEASURABLE


def test_c3_queue_availability_is_a_bound_and_never_an_interval_endpoint(one_unknown):
    """
    Nothing observes the moment a human was shown a candidate. The run-close
    bound is on the timeline, named as derived, and no metric consumes it.
    """
    ref, harness = one_unknown
    harness.decide(ref)
    timeline = harness.timeline(ref)
    interval = timeline.intervals["time_from_queue_availability_to_decision"]

    assert interval["state"] == NOT_MEASURABLE
    assert interval["minutes"] is None
    assert "Derived, not observed" in \
        timeline.derived["queue_availability_lower_bound_note"]
    assert harness.report()["durations"][
        "time_from_queue_availability_to_decision"]["state"] == NOT_MEASURABLE


# ==========================================================================
# D / N / O - UNKNOWN resolution, timed separately and kept separate
# ==========================================================================

def test_d_unknown_resolution_is_timed_separately_from_any_other_decision(one_unknown):
    ref, harness = one_unknown
    harness.decide(ref, kind="RESOLVE_UNKNOWN",
                   decided_at="2026-09-01T10:45:00+00:00",
                   dimension="work_mode", human_assertion="REMOTE",
                   human_basis="recruiter email 2026-09-01")
    timeline = harness.timeline(ref)

    resolution = timeline.intervals["time_from_unknown_to_human_resolution"]
    assert resolution["state"] == MEASURED
    assert resolution["minutes"] == 45.0
    assert resolution["end_event"] == "HUMAN_DECISION:RESOLVE_UNKNOWN"


def test_d2_a_non_unknown_candidate_has_no_unknown_resolution_interval(temp_db,
                                                                      instrumented):
    ref = insert_job(temp_db, row_id=2, external_id="linkedin:1002")
    harness = instrumented(temp_db, [ledger_record(
        "linkedin:1002", verdict="PASS",
        reason_codes=["WM-PASS-REMOTE", "COMP-PASS-AT-OR-ABOVE-FLOOR"],
        work_mode="REMOTE")])
    assert "time_from_unknown_to_human_resolution" not in \
        harness.timeline(ref).intervals


def test_n_a_human_resolution_does_not_change_the_machine_verdict(one_unknown):
    ref, harness = one_unknown
    ledger_before = digest(harness.ledger_path)
    harness.decide(ref, kind="RESOLVE_UNKNOWN", dimension="work_mode",
                   human_assertion="REMOTE", human_basis="recruiter email")
    timeline = harness.timeline(ref)

    assert timeline.verdict == "UNKNOWN"
    assert timeline.reason_codes == ["WM-UNKNOWN-ABSENT"]
    assert digest(harness.ledger_path) == ledger_before


def test_o_the_machine_context_at_the_decision_stays_recoverable(one_unknown):
    ref, harness = one_unknown
    recorded = harness.decide(ref)
    assert recorded["machine_context"]["verdict"] == "UNKNOWN"
    assert recorded["machine_context"]["ruleset_version"] == "jobops-policy@0.1.0"

    history = harness.timeline(ref).human
    assert history["decision_count"] == 1
    stored = harness.decisions.history_for(ref)[0]
    assert stored["machine_context"] == recorded["machine_context"]


# ==========================================================================
# E / F / G / H - ACCEPT is not SUBMITTED
# ==========================================================================

def test_e_accept_does_not_imply_submission(one_unknown):
    """The single most important assertion in this file."""
    ref, harness = one_unknown
    harness.decide(ref, kind="ACCEPT")
    timeline = harness.timeline(ref)

    assert timeline.submission is None
    assert timeline.events["APPLICATION_SUBMITTED"]["observed"] is False
    assert timeline.intervals["time_from_decision_to_submission"]["state"] == \
        NOT_AVAILABLE
    assert timeline.intervals["time_from_decision_to_submission"]["minutes"] is None

    report = harness.report()
    assert report["funnel"]["actual_submissions"]["value"] == 0
    assert report["funnel"]["accepted_without_submission_record"]["value"] == 1
    # Recording a decision creates no submission file at all.
    assert not harness.submissions.path.exists()


def test_f_a_submission_exists_only_because_a_human_recorded_one(one_unknown):
    ref, harness = one_unknown
    harness.decide(ref, kind="ACCEPT")
    assert harness.timeline(ref).submission is None

    record = harness.submit(ref)
    assert record["event"] == "APPLICATION_SUBMITTED"
    assert record["recorded_by"] == "human"
    assert record["submitted_by_jobops"] is False
    assert record["external_request_made"] is False
    assert harness.timeline(ref).submission["submitted_at"] == SUBMITTED_AT


def test_f2_a_submission_without_a_time_is_refused(one_unknown):
    ref, harness = one_unknown
    with pytest.raises(SubmissionError, match="no default"):
        harness.submissions.record(SubmissionEvent(candidate_ref=ref,
                                                   submitted_at=None))


def test_f3_a_submission_in_the_future_is_refused(one_unknown):
    """An unsubmitted application is an intention, and intentions are ACCEPTs."""
    ref, harness = one_unknown
    with pytest.raises(SubmissionError, match="in the future"):
        harness.submissions.record(SubmissionEvent(
            candidate_ref=ref, submitted_at="2099-01-01T00:00:00+00:00"))


def test_g_time_to_submit_is_computed_only_when_both_timestamps_exist(one_unknown):
    ref, harness = one_unknown
    harness.decide(ref, kind="ACCEPT", decided_at=DECIDED_AT)
    harness.submit(ref, submitted_at=SUBMITTED_AT)
    intervals = harness.timeline(ref).intervals

    assert intervals["time_from_decision_to_submission"]["state"] == MEASURED
    assert intervals["time_from_decision_to_submission"]["minutes"] == 240.0
    assert intervals["time_from_evaluation_to_submission"]["state"] == MEASURED
    assert intervals["time_from_evaluation_to_submission"]["minutes"] == 260.0


def test_g2_a_submission_without_a_standing_accept_produces_no_interval(one_unknown):
    """
    The submission is recorded as it happened. No decision timestamp is invented
    to complete the interval.
    """
    ref, harness = one_unknown
    harness.submit(ref)
    intervals = harness.timeline(ref).intervals

    assert harness.timeline(ref).submission is not None
    assert intervals["time_from_decision_to_submission"]["state"] == NOT_AVAILABLE
    assert "HUMAN_DECISION:ACCEPT" in \
        intervals["time_from_decision_to_submission"]["missing"]
    assert intervals["time_from_evaluation_to_submission"]["state"] == MEASURED


def test_h_a_missing_submission_never_becomes_a_duration(one_unknown):
    ref, harness = one_unknown
    harness.decide(ref, kind="ACCEPT")
    metric = harness.report()["durations"]["time_from_decision_to_submission"]

    assert metric["state"] == NOT_AVAILABLE
    assert metric["median"] is None and metric["p90"] is None
    assert metric["n"] == 0
    assert "not zero minutes" in metric["why"]


# ==========================================================================
# I / J / K / L / M - a submission changes nothing else
# ==========================================================================

def test_i_j_k_a_submission_changes_no_machine_verdict_evidence_or_provenance(
        one_unknown):
    ref, harness = one_unknown
    before_ledger = digest(harness.ledger_path)
    machine_before = harness.queue.build().entry(ref).payload["machine"]

    harness.decide(ref, kind="ACCEPT")
    harness.submit(ref)

    machine_after = harness.queue.build().entry(ref).payload["machine"]
    assert digest(harness.ledger_path) == before_ledger
    assert machine_after["verdict"] == machine_before["verdict"]
    assert machine_after["evidence"] == machine_before["evidence"]
    assert machine_after["provenance"] == machine_before["provenance"]
    assert machine_after["evaluated_at"] == machine_before["evaluated_at"]
    assert machine_after["reason_codes"] == machine_before["reason_codes"]


def test_l_a_submission_does_not_convert_unknown_to_pass(one_unknown):
    ref, harness = one_unknown
    harness.decide(ref, kind="ACCEPT")
    harness.submit(ref)
    timeline = harness.timeline(ref)

    assert timeline.verdict == "UNKNOWN"
    assert timeline.lane == "REVIEW"
    assert harness.queue.build().entry(ref).payload["machine"][
        "eligible_for_scoring"] is False
    assert harness.timeline(ref).submission["changes_machine_verdict"] is False


def test_m_the_decision_and_the_submission_are_separate_records_in_separate_files(
        one_unknown):
    ref, harness = one_unknown
    decision = harness.decide(ref, kind="ACCEPT")
    decisions_before = digest(harness.decisions.path)
    submission = harness.submit(ref)

    assert harness.decisions.path != harness.submissions.path
    assert harness.decisions.path.parent != harness.submissions.path.parent
    assert digest(harness.decisions.path) == decisions_before
    assert submission["decision_ref"] == decision["decision_id"]
    assert "kind" not in submission and "decision_id" not in submission
    # The reference is an id, not a copy of the decision or of the verdict.
    assert "machine_context" not in submission


def test_p_a_submission_is_corrected_by_appending_never_by_editing(one_unknown):
    ref, harness = one_unknown
    first = harness.submit(ref, submitted_at="2026-09-01T14:00:00+00:00")
    corrected = harness.submit(ref, submitted_at="2026-09-01T10:30:00+00:00",
                               supersedes=first["submission_id"])

    history = harness.submissions.history_for(ref)
    assert len(history) == 2
    assert history[0]["submitted_at"] == "2026-09-01T14:00:00+00:00"
    assert harness.submissions.current_for(ref)["submission_id"] == \
        corrected["submission_id"]
    assert harness.submissions.counts() == {"records": 2, "standing": 1,
                                            "corrections": 1}


def test_p2_superseding_an_unknown_submission_is_refused(one_unknown):
    ref, harness = one_unknown
    with pytest.raises(SubmissionError, match="supersede unknown"):
        harness.submit(ref, supersedes="sub-000999-deadbeefcafe")


# ==========================================================================
# Q / R - duplicates must not distort throughput
# ==========================================================================

def test_q_a_suppressed_definite_duplicate_does_not_inflate_active_metrics(
        temp_db, instrumented):
    ref = insert_job(temp_db, row_id=20, external_id="linkedin:4454261604",
                     company="Dautom", title="AI Data Engineer")
    insert_opportunity(temp_db, row_id=90, company="Dautom",
                       role="AI Data Engineer", status="Applied",
                       url="https://www.linkedin.com/jobs/view/4454261604/")
    harness = instrumented(temp_db, [ledger_record("linkedin:4454261604")])
    timeline = harness.timeline(ref)
    report = harness.report()

    assert timeline.suppressed is True
    assert timeline.in_active_funnel is False
    assert report["funnel"]["candidates_evaluated"]["value"] == 1
    assert report["funnel"]["distinct_review_candidates"]["value"] == 0
    assert report["funnel"]["definite_duplicates_suppressed"]["value"] == 1
    assert report["rates"]["unknown_rate"]["state"] == INSUFFICIENT_DATA


def test_r_an_l3_probable_duplicate_stays_a_real_review_opportunity(temp_db,
                                                                   instrumented):
    ref = insert_job(temp_db, row_id=23, external_id="linkedin:2301",
                     company="Acme AI", title="AI Quality Engineer")
    insert_job(temp_db, row_id=24, external_id="careers:acme-1",
               source="Acme Careers", company="Acme AI",
               title="AI Quality Engineer",
               url="https://careers.acme.example/roles/xyz")
    harness = instrumented(temp_db, [ledger_record("linkedin:2301")])
    timeline = harness.timeline(ref)
    report = harness.report()

    assert timeline.identity_outcome == "PROBABLE_DUPLICATE"
    assert timeline.suppressed is False
    assert timeline.in_active_funnel is True
    assert timeline.probable_duplicate is True
    assert report["funnel"]["distinct_review_candidates"]["value"] == 1
    assert report["funnel"][
        "probable_duplicates_needing_human_judgement"]["value"] == 1
    assert report["funnel"]["definite_duplicates_suppressed"]["value"] == 0


# ==========================================================================
# S / T / U / V / W - populations stay distinguishable
# ==========================================================================

def test_s_not_evaluated_rows_are_excluded_from_the_evaluated_funnel(temp_db,
                                                                    instrumented):
    insert_job(temp_db, row_id=30, external_id="remoteok:1")
    insert_job(temp_db, row_id=31, external_id="remoteok:2")
    ref = insert_job(temp_db, row_id=32, external_id="linkedin:3001")
    harness = instrumented(temp_db, [ledger_record("linkedin:3001")])
    report = harness.report()

    assert report["funnel"]["candidates_evaluated"]["value"] == 1
    assert report["funnel"]["legacy_not_evaluated_count"]["value"] == 2
    assert report["rates"]["unknown_rate"]["denominator"] == 1
    assert harness.timeline(ref).is_legacy_not_evaluated is False


def test_t_not_evaluated_rows_are_not_silently_backfilled(temp_db, instrumented):
    ref = insert_job(temp_db, row_id=33, external_id="remoteok:3")
    harness = instrumented(temp_db, [])
    timeline = harness.timeline(ref)

    assert timeline.verdict is None
    assert timeline.verdict_available is False
    assert timeline.is_legacy_not_evaluated is True
    assert timeline.events["CANDIDATE_EVALUATED"]["observed"] is False
    assert timeline.events["CANDIDATE_EVALUATED"]["at"] is None
    # Its row-creation time exists and is NOT promoted into an evaluation time.
    assert timeline.events["CANDIDATE_INGESTED"]["observed"] is True
    assert timeline.intervals["time_from_evaluation_to_decision"]["state"] == \
        NOT_AVAILABLE


def test_u_discovered_records_are_distinguishable_from_evaluated_candidates(
        temp_db, instrumented):
    ref = insert_job(temp_db, row_id=34, external_id="linkedin:3401")
    harness = instrumented(temp_db, [ledger_record("linkedin:3401")])
    funnel = harness.report()["funnel"]

    assert funnel["candidates_discovered"]["state"] == NOT_AVAILABLE
    assert funnel["candidates_evaluated"]["value"] == 1
    assert funnel["candidates_ingested"]["value"] == 1
    assert harness.timeline(ref).events["CANDIDATE_OBSERVED"]["at"] != \
        harness.timeline(ref).events["CANDIDATE_EVALUATED"]["at"]


def test_v_evaluated_candidates_are_distinguishable_from_reviewed_ones(temp_db,
                                                                      instrumented):
    ref_a = insert_job(temp_db, row_id=35, external_id="linkedin:3501")
    insert_job(temp_db, row_id=36, external_id="linkedin:3502")
    harness = instrumented(temp_db, [ledger_record("linkedin:3501"),
                                     ledger_record("linkedin:3502")])
    harness.decide(ref_a, kind="SKIP")
    funnel = harness.report()["funnel"]

    assert funnel["candidates_evaluated"]["value"] == 2
    assert funnel["candidates_human_reviewed"]["value"] == 1
    assert funnel["human_decisions"]["value"] == 1


def test_w_human_decisions_are_distinguishable_from_actual_submissions(temp_db,
                                                                      instrumented):
    ref_a = insert_job(temp_db, row_id=37, external_id="linkedin:3701")
    ref_b = insert_job(temp_db, row_id=38, external_id="linkedin:3702")
    harness = instrumented(temp_db, [ledger_record("linkedin:3701"),
                                     ledger_record("linkedin:3702")])
    harness.decide(ref_a, kind="ACCEPT")
    harness.decide(ref_b, kind="ACCEPT")
    harness.submit(ref_a)
    funnel = harness.report()["funnel"]

    assert funnel["human_decisions"]["value"] == 2
    assert funnel["actual_submissions"]["value"] == 1
    assert funnel["accepted_without_submission_record"]["value"] == 1


def test_w2_promotion_into_opportunities_is_not_a_submission(temp_db, instrumented):
    """
    The bridge creates an application-workflow row. That is entry into the
    workflow, and the instrumentation says so in a different field from the one
    a submission would occupy.
    """
    ref = insert_job(temp_db, row_id=39, external_id="linkedin:3901")
    insert_opportunity(temp_db, row_id=95, company="Acme AI",
                       role="AI Quality Engineer", scraped_job_id=39,
                       status="Applied", created_at="2026-09-01 11:00:00",
                       applied_date="2026-09-01")
    harness = instrumented(temp_db, [ledger_record("linkedin:3901")])
    harness.decide(ref, kind="ACCEPT")
    timeline = harness.timeline(ref)

    assert timeline.events["APPLICATION_PROMOTED"]["observed"] is True
    assert timeline.events["APPLICATION_SUBMITTED"]["observed"] is False
    assert timeline.intervals["time_from_decision_to_promotion"]["state"] == MEASURED
    assert timeline.intervals["time_from_decision_to_submission"]["state"] == \
        NOT_AVAILABLE
    assert timeline.application["status"] == "Applied"
    assert "never used as a submission timestamp" in \
        timeline.application["status_is_not_a_submission_event"]
    assert harness.report()["funnel"]["actual_submissions"]["value"] == 0


def test_w3_applied_date_is_kept_at_day_precision_and_used_in_no_interval(
        temp_db, instrumented):
    ref = insert_job(temp_db, row_id=40, external_id="linkedin:4001")
    insert_opportunity(temp_db, row_id=96, company="Acme AI",
                       role="AI Quality Engineer", scraped_job_id=40,
                       status="Applied", applied_date="2026-09-01")
    harness = instrumented(temp_db, [ledger_record("linkedin:4001")])
    timeline = harness.timeline(ref)

    assert timeline.application["applied_date_day_precision"] == "2026-09-01"
    for interval in timeline.intervals.values():
        assert interval["end_at"] != "2026-09-01"
        assert interval["start_at"] != "2026-09-01"


# ==========================================================================
# X / Y / Z - zero, missing, insufficient and inconsistent stay four answers
# ==========================================================================

def test_x_zero_and_missing_are_not_conflated(temp_db, instrumented):
    ref = insert_job(temp_db, row_id=41, external_id="linkedin:4101")
    harness = instrumented(temp_db, [ledger_record("linkedin:4101")])
    report = harness.report()

    # A counted zero is MEASURED and really is zero.
    assert report["funnel"]["actual_submissions"] == {
        "state": MEASURED, "value": 0, "unit": "candidates",
        "counts": report["funnel"]["actual_submissions"]["counts"],
        "note": report["funnel"]["actual_submissions"]["note"]}
    # A duration with no data is NOT_AVAILABLE with a null value.
    assert report["durations"]["time_from_evaluation_to_decision"]["state"] == \
        NOT_AVAILABLE
    assert report["durations"]["time_from_evaluation_to_decision"]["median"] is None
    # An empty denominator is INSUFFICIENT_DATA, not a rate of zero.
    assert report["rates"]["pass_to_apply_rate"]["state"] == INSUFFICIENT_DATA
    assert report["rates"]["pass_to_apply_rate"]["value"] is None
    # A real zero numerator over a real denominator IS a rate of zero.
    assert report["rates"]["unknown_to_apply_rate"]["state"] == MEASURED
    assert report["rates"]["unknown_to_apply_rate"]["value"] == 0.0
    # A quantity nothing can observe is NOT_MEASURABLE.
    assert report["throughput"][
        "applications_per_unit_of_human_effort"]["state"] == NOT_MEASURABLE


def test_y_out_of_order_events_are_withheld_not_turned_into_a_duration(temp_db,
                                                                      instrumented):
    """A decision recorded before the evaluation is a data fact, not a -20 min."""
    ref = insert_job(temp_db, row_id=42, external_id="linkedin:4201")
    harness = instrumented(temp_db, [ledger_record("linkedin:4201")])
    harness.decide(ref, decided_at="2026-09-01T09:00:00+00:00")
    interval = harness.timeline(ref).intervals["time_from_evaluation_to_decision"]

    assert interval["state"] == INCONSISTENT
    assert interval["minutes"] is None

    metric = harness.report()["durations"]["time_from_evaluation_to_decision"]
    assert metric["n"] == 0
    assert metric["candidates_with_inconsistent_events"] == 1
    assert metric["inconsistent_candidates"] == [ref]
    assert metric["state"] == NOT_AVAILABLE
    assert minutes_between(parse_timestamp(EVALUATED_AT),
                           parse_timestamp("2026-09-01T09:00:00+00:00")) is None


def test_y2_a_partial_history_produces_no_interval_for_the_missing_leg(temp_db,
                                                                      instrumented):
    ref = insert_job(temp_db, row_id=43, external_id="linkedin:4301")
    harness = instrumented(temp_db, [ledger_record("linkedin:4301")])
    harness.decide(ref, kind="ACCEPT")
    intervals = harness.timeline(ref).intervals

    assert intervals["time_from_evaluation_to_decision"]["state"] == MEASURED
    for missing in ("time_from_decision_to_submission",
                    "time_from_evaluation_to_submission",
                    "time_from_decision_to_promotion"):
        assert intervals[missing]["state"] == NOT_AVAILABLE
        assert intervals[missing]["minutes"] is None


def test_z_an_empty_dataset_produces_explicit_safe_results(temp_db, instrumented):
    harness = instrumented(temp_db, [])
    report = harness.report()

    assert report["funnel"]["candidates_evaluated"]["value"] == 0
    assert report["funnel"]["legacy_not_evaluated_count"]["value"] == 0
    assert report["durations"]["time_from_evaluation_to_decision"]["state"] == \
        NOT_AVAILABLE
    assert report["rates"]["unknown_rate"]["state"] == INSUFFICIENT_DATA
    assert report["throughput"]["decisions_per_period"]["state"] == NOT_AVAILABLE
    assert report["window"]["meets_exit_criterion_window"] is False
    assert report["reporting_discipline"][
        "veto_rate_per_reason_code"]["state"] == NOT_AVAILABLE


def test_z2_per_day_reports_a_span_and_never_invents_quiet_days():
    series = per_day(["2026-09-01", "2026-09-01", "2026-09-04"])
    assert series["state"] == MEASURED
    assert series["by_day"] == {"2026-09-01": 2, "2026-09-04": 1}
    assert series["days_with_activity"] == 2
    assert series["span_days"] == 4
    assert "2026-09-02" not in series["by_day"]
    assert per_day([])["state"] == NOT_AVAILABLE


def test_z3_an_unreadable_timestamp_is_an_error_not_a_guess():
    with pytest.raises(TimestampError):
        parse_timestamp("last Tuesday", field="submitted_at")
    assert parse_timestamp(None) is None


# ==========================================================================
# AE / AF / AG - no submission path, no network, nothing else touched
# ==========================================================================

def test_ae_no_automatic_submission_path_exists():
    """
    A submission record is written in exactly one place, reached only from the
    explicit --record-submission command. Nothing else in the package can
    create one.
    """
    code = timing_code()
    for forbidden in ("apply(", "auto_apply", "submit_application",
                      "easy_apply", "send_message", "recruiter"):
        assert forbidden not in code

    constructions = [path.name for path in sorted(TIMING_DIR.glob("*.py"))
                     if "SubmissionEvent(" in code_only(path)]
    assert constructions == ["run_timing_report.py"]

    source = (TIMING_DIR / "run_timing_report.py").read_text()
    assert "record_submission" in source
    tree = ast.parse(code_only(TIMING_DIR / "run_timing_report.py"))
    callers = {node.name for node in ast.walk(tree)
               if isinstance(node, ast.FunctionDef)
               and "SubmissionEvent(" in ast.unparse(node)}
    assert callers == {"record_submission"}


def test_af_no_network_or_external_process_capability_is_introduced():
    code = timing_code()
    for forbidden in ("import requests", "import socket", "import http",
                      "import urllib", "urlopen", "import subprocess",
                      "os.system", "httpx", "aiohttp"):
        assert forbidden not in code


def test_ag_p0_10_writes_nothing_that_an_earlier_task_owns():
    """
    The only write in the package is the append to submissions.jsonl. There is
    no INSERT, UPDATE, DELETE or database connection that is not read-only.
    """
    code = timing_code()
    for forbidden in ("INSERT INTO", "UPDATE ", "DELETE FROM", "DROP ",
                      "ALTER TABLE", "PRAGMA journal", "commit()"):
        assert forbidden not in code
    assert code.count("sqlite3.connect") == 1
    assert "mode=ro" in code

    writes = [path.name for path in sorted(TIMING_DIR.glob("*.py"))
              if 'open(' in code_only(path) and '"a"' in code_only(path)]
    assert writes == ["submissions.py"]

    # Nothing earlier depends on this package, so no existing surface changes.
    for module in ("policy", "identity", "ingestion", "review"):
        for path in (REPO_ROOT / module).glob("*.py"):
            assert "timing" not in code_only(path).replace("timing_", "")
    assert "timing" not in (REPO_ROOT / "api-server.py").read_text()


# ==========================================================================
# The artifact - every event and metric has a written meaning
# ==========================================================================

def test_the_timing_artifact_is_version_pinned(timing_ruleset):
    assert timing_ruleset.version == "jobops-timing@0.1.0"
    with pytest.raises(TimingDriftError):
        load_timing_ruleset.__globals__["TimingRuleset"](
            TIMING_ARTIFACT, expected_version="jobops-timing@9.9.9")


def test_an_event_the_artifact_does_not_declare_cannot_be_used(timing_ruleset):
    with pytest.raises(TimingDriftError):
        timing_ruleset.event("REVIEW_STARTED")        # declared UNOBSERVED
    with pytest.raises(TimingDriftError):
        timing_ruleset.metric("time_spent_reading")
    assert "REVIEW_STARTED" in timing_ruleset.unobserved_event_ids


def test_every_metric_the_report_emits_is_declared_in_the_artifact(temp_db,
                                                                  instrumented,
                                                                  timing_ruleset):
    report = instrumented(temp_db, []).report()
    declared = set(timing_ruleset.metric_ids)
    for metric_id in report["durations"]:
        assert metric_id in declared
    for metric_id in report["rates"]:
        assert metric_id in declared
    for metric_id in ("candidates_evaluated", "actual_submissions",
                      "human_decisions", "distinct_review_candidates",
                      "candidates_human_reviewed"):
        assert metric_id in declared


def test_the_artifact_forbids_equating_accept_with_submitted(timing_ruleset):
    prohibited = " ".join(timing_ruleset.prohibited)
    assert "Defining ACCEPT as SUBMITTED" in prohibited
    assert "Emitting 0 for a measurement that is missing" in prohibited
    accept = next(item for item in timing_ruleset.non_events
                  if item["id"] == "ACCEPT")
    assert "can never be its end" in accept["treatment"]


def test_the_artifact_names_a_source_of_truth_for_every_observed_event(
        timing_ruleset):
    for event in timing_ruleset.events:
        assert event["store"] and event["meaning"] and event["precision"]
        assert event["origin"] in ("machine", "human",
                                   "machine record of a human-invoked action")
        assert event["measures"] == "elapsed_lifecycle"


# ==========================================================================
# Read-only validation against the live data
# ==========================================================================

@pytest.fixture(scope="module")
def live_report():
    """One read-only report over the real database and the real evidence."""
    return TimingReport(db_path=LIVE_DB).build()


@pytest.mark.parametrize("candidate_ref,company", [
    ("scraped_jobs:78", "Elastic"),
    ("scraped_jobs:79", "Qentelli"),
    ("scraped_jobs:80", "SymphonyAI Group - India"),
])
def test_the_three_real_linkedin_candidates_keep_their_history(candidate_ref,
                                                               company):
    """
    The real P0-06 candidates: machine evaluation preserved, UNKNOWN preserved,
    reason codes preserved, and no human event invented for any of them.
    """
    timelines = {t.candidate_ref: t
                 for t in LifecycleReader(db_path=LIVE_DB).timelines()}
    timeline = timelines[candidate_ref]

    assert timeline.verdict == "UNKNOWN"
    assert timeline.reason_codes  # the gate's codes, unchanged
    assert timeline.events["CANDIDATE_EVALUATED"]["at"].startswith("2026-08-31T07:36:5")
    assert timeline.events["CANDIDATE_OBSERVED"]["observed"] is True
    # Nothing human has happened to these records, and nothing pretends it has.
    assert timeline.events["HUMAN_DECISION"]["observed"] is False
    assert timeline.events["APPLICATION_SUBMITTED"]["observed"] is False
    assert timeline.submission is None
    assert timeline.human["decision_count"] == 0
    assert timeline.intervals["time_from_evaluation_to_decision"]["state"] == \
        NOT_AVAILABLE


def test_the_live_funnel_separates_the_evaluated_from_the_legacy(live_report):
    funnel = live_report["funnel"]
    assert funnel["candidates_evaluated"]["value"] == 3
    assert funnel["distinct_review_candidates"]["value"] == 3
    assert funnel["legacy_not_evaluated_count"]["value"] == 75
    assert funnel["definite_duplicates_suppressed"]["value"] == 2


def test_the_live_known_bridge_pairs_are_still_suppressed_and_untouched():
    """scraped_jobs:3 <-> opportunities:27 and scraped_jobs:43 <-> 28."""
    timelines = {t.candidate_ref: t
                 for t in LifecycleReader(db_path=LIVE_DB).timelines()}
    for ref in ("scraped_jobs:3", "scraped_jobs:43"):
        timeline = timelines[ref]
        assert timeline.suppressed is True
        assert timeline.in_active_funnel is False
        assert timeline.verdict is None          # never evaluated, not backfilled


def test_the_live_report_claims_no_submission_and_no_effort(live_report):
    assert live_report["funnel"]["actual_submissions"]["value"] == 0
    assert live_report["durations"][
        "time_from_decision_to_submission"]["state"] == NOT_AVAILABLE
    assert live_report["throughput"][
        "applications_per_unit_of_human_effort"]["state"] == NOT_MEASURABLE
    assert live_report["window"]["meets_exit_criterion_window"] is False
    assert any("ACTIVE HUMAN EFFORT IS NOT DIRECTLY MEASURABLE" in limitation
               for limitation in live_report["limitations"])


def test_ad_building_the_live_report_writes_nothing_any_task_owns():
    """
    P0-02, P0-06, P0-07 and P0-08 own the ledger, the database and the decision
    ledger. A full P0-10 report reads all three and leaves every byte alone.
    """
    before = {path: digest(path) for path in
              [LIVE_DB, LIVE_DECISIONS, LIVE_SUBMISSIONS,
               *sorted((LIVE_LEDGER_ROOT / "candidates").glob("*.jsonl")),
               *sorted((LIVE_LEDGER_ROOT / "runs").glob("*.json"))]}
    TimingReport(db_path=LIVE_DB).build()
    assert {path: digest(path) for path in before} == before


def test_the_live_database_connection_physically_rejects_writes():
    reader = LifecycleReader(db_path=LIVE_DB)
    with reader._connect() as conn:
        with pytest.raises(sqlite3.OperationalError,
                           match="readonly|attempt to write"):
            conn.execute("UPDATE scraped_jobs SET job_title = 'x' WHERE id = 78")
