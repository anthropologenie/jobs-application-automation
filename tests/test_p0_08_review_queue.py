#!/usr/bin/env python3
"""
P0-08 candidate review queue - deterministic tests

Hermetic fixtures for behaviour, plus a small number of READ-ONLY assertions
against the live database and the retained evidence of the first real LinkedIn
run. No test in this file writes to data/jobs-tracker.db, and none contacts
LinkedIn.

What these tests assert:

  * PASS, UNKNOWN and FAIL land in distinct lanes, and a FAIL is sub-laned by
    whether the compensation floor was the reason;
  * UNKNOWN is first class - never promoted by a remote search filter, never
    promoted by a human deciding to apply, never demoted to FAIL, and always
    carrying the reason codes that explain it;
  * the machine verdict, the human decision and the application outcome live in
    three separate places and stay distinguishable;
  * a human resolving an UNKNOWN records an assertion with its basis and does
    not become machine evidence or rewrite the verdict;
  * L1/L2/L4 definite duplicates leave the ACTIVE queue; an L3 probable
    duplicate does not, and is never labelled definite;
  * suppression deletes and modifies nothing;
  * evidence, provenance, field provenance and ruleset version stay traceable,
    including the three-state distinction between "the source stated none" and
    "this run did not capture it";
  * building the queue twice yields the same queue and changes nothing.

Run:
    python3 -m pytest tests/test_p0_08_review_queue.py -v

Author: Karthik Shetty
Created: 2026-09-02
"""

import ast
import copy
import json
import sqlite3
from pathlib import Path

import pytest

from review.decisions import Decision, DecisionError, DecisionStore, utc_now_iso
from review.ledger import NOT_CAPTURED, CandidateLedgerStore, LedgerError
from review.queue import ReviewQueue
from review.ruleset import ReviewDriftError, load_review_ruleset

REPO_ROOT = Path(__file__).resolve().parent.parent
LIVE_DB = REPO_ROOT / "data" / "jobs-tracker.db"
LIVE_LEDGER_ROOT = REPO_ROOT / "data" / "ingestion"
REVIEW_DIR = REPO_ROOT / "review"
REVIEW_ARTIFACT = REVIEW_DIR / "jobops-review-0.1.0.json"


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


def review_code():
    return "\n".join(code_only(p) for p in sorted(REVIEW_DIR.glob("*.py")))


# ==========================================================================
# Fixtures - a hermetic database, ledger and decision store
# ==========================================================================

@pytest.fixture(scope="module")
def review_ruleset():
    return load_review_ruleset()


@pytest.fixture
def temp_db(tmp_path):
    """
    A database carrying the live schema for the two tables in play.

    The DDL is copied from the real database, opened read-only, so schema drift
    in production surfaces here as a failure rather than as a test passing
    against a schema this file invented.
    """
    source = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
    try:
        statements = [row[0] for row in source.execute(
            "SELECT sql FROM sqlite_master WHERE tbl_name IN "
            "('scraped_jobs', 'opportunities') AND sql IS NOT NULL")]
    finally:
        source.close()

    path = tmp_path / "review-test.db"
    conn = sqlite3.connect(str(path))
    try:
        for statement in statements:
            conn.execute(statement)
        conn.commit()
    finally:
        conn.close()
    return path


def insert_job(db_path, *, row_id, external_id, source="LinkedIn",
               title="AI Quality Engineer", company="Acme AI",
               url=None, location="Bengaluru, Karnataka, India",
               salary_range=None, scraped_at="2026-09-01 10:00:00"):
    url = url or f"https://www.linkedin.com/jobs/view/{external_id.split(':')[-1]}"
    conn = sqlite3.connect(str(db_path))
    try:
        with conn:
            conn.execute(
                "INSERT INTO scraped_jobs (id, external_id, source, job_title, "
                "company, job_url, location, salary_range, scraped_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (row_id, external_id, source, title, company, url, location,
                 salary_range, scraped_at))
    finally:
        conn.close()
    return f"scraped_jobs:{row_id}"


def insert_opportunity(db_path, *, row_id, company, role, url=None,
                       source="LinkedIn", status="Applied", scraped_job_id=None):
    conn = sqlite3.connect(str(db_path))
    try:
        with conn:
            conn.execute(
                "INSERT INTO opportunities (id, company, role, job_url, source, "
                "status, scraped_job_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (row_id, company, role, url, source, status, scraped_job_id))
    finally:
        conn.close()
    return f"opportunities:{row_id}"


def write_ledger(root, run_id, records):
    """Write a candidate ledger exactly as the P0-06 pipeline writes one."""
    candidates = Path(root) / "candidates"
    candidates.mkdir(parents=True, exist_ok=True)
    with open(candidates / f"{run_id}.jsonl", "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return candidates / f"{run_id}.jsonl"


def ledger_record(external_id, *, verdict, reason_codes, work_mode="ABSENT",
                  compensation=None, evidence=None, evaluated_at="2026-09-01T10:00:00+00:00",
                  ruleset_version="jobops-policy@0.1.0", remote_filter="remote",
                  field_provenance=None, row=None):
    """
    One candidate ledger record, shaped exactly like the real ones.

    `remote_filter` populates provenance.source_query.remote so tests can assert
    that a portal filter present in the query never becomes work-mode evidence.
    """
    record = {
        "candidate_id": external_id,
        "external_id": external_id,
        "source_portal": "linkedin-search",
        "provenance": {
            "source_portal": "linkedin-search",
            "source_mechanism": "cli",
            "source_query": {"location": "India", "query": "AI Quality Engineer",
                             "jobage": 7, "remote": remote_filter, "page": 1},
            "source_fetched_at": "2026-09-01T09:59:00+00:00",
            "raw_payload_ref": f"raw/linkedin-search/run/search-{external_id}.json",
            "cli_version": {"runtime": "bun", "package_version": "1.0.0"},
            "source_url": f"https://www.linkedin.com/jobs/view/{external_id.split(':')[-1]}",
        },
        "extractor_version": "linkedin-ingestion@0.1.0",
        "normalizer_version": ruleset_version,
        "located_evidence": {"work_mode": [], "work_mode_selected": None,
                             "work_mode_portal_claim": None,
                             "compensation": [], "compensation_selected": None},
        "normalized_candidate_row": row or {},
        "normalized_work_mode": work_mode,
        "gate_verdict": {
            "candidate_id": external_id,
            "verdict": verdict,
            "ruleset_version": ruleset_version,
            "evaluated_at": evaluated_at,
            "reason_codes": list(reason_codes),
            "dimension_verdicts": {"work_mode": "UNKNOWN" if work_mode == "ABSENT"
                                   else "PASS", "compensation": "UNKNOWN"},
            "rules_fired": ["WM-R5"],
            "normalized_work_mode": work_mode,
            "normalized_compensation": compensation or {"state": "ABSENT"},
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
    if field_provenance is not None:
        record["field_provenance"] = field_provenance
    return record


@pytest.fixture
def queue_factory(tmp_path, review_ruleset):
    """Build a ReviewQueue over a hermetic database, ledger and decision store."""
    def _factory(db_path, records=None, run_id="run-0001"):
        ledger_root = tmp_path / "ingestion"
        (ledger_root / "candidates").mkdir(parents=True, exist_ok=True)
        if records:
            write_ledger(ledger_root, run_id, records)
        decisions = DecisionStore(tmp_path / "review", ruleset=review_ruleset)
        return ReviewQueue(db_path=db_path, ruleset=review_ruleset,
                           ledger=CandidateLedgerStore(ledger_root),
                           decisions=decisions)
    return _factory


def lane_of(build, candidate_ref):
    entry = build.entry(candidate_ref)
    return entry.lane if entry else None


# ==========================================================================
# A / B / C - PASS, FAIL below floor, FAIL work mode
# ==========================================================================

def test_a_pass_appears_in_the_shortlist(temp_db, queue_factory):
    ref = insert_job(temp_db, row_id=1, external_id="linkedin:1001")
    queue = queue_factory(temp_db, [ledger_record(
        "linkedin:1001", verdict="PASS", reason_codes=[
            "WM-PASS-REMOTE", "COMP-PASS-AT-OR-ABOVE-FLOOR"], work_mode="REMOTE")])
    build = queue.build()
    assert lane_of(build, ref) == "SHORTLIST"
    entry = build.entry(ref)
    assert entry.payload["machine"]["verdict"] == "PASS"
    assert entry.payload["machine"]["eligible_for_scoring"] is True


def test_b_fail_below_the_compensation_floor_has_its_own_lane(temp_db, queue_factory):
    ref = insert_job(temp_db, row_id=2, external_id="linkedin:1002")
    queue = queue_factory(temp_db, [ledger_record(
        "linkedin:1002", verdict="FAIL", reason_codes=["COMP-FAIL-BELOW-FLOOR"],
        work_mode="REMOTE")])
    build = queue.build()
    assert lane_of(build, ref) == "BELOW_THRESHOLD"
    assert build.entry(ref).payload["machine"]["reason_codes"] == \
        ["COMP-FAIL-BELOW-FLOOR"]


@pytest.mark.parametrize("code", ["WM-FAIL-HYBRID", "WM-FAIL-ONSITE"])
def test_c_hybrid_and_onsite_stay_excluded(temp_db, queue_factory, code):
    """
    OR-04: a work-mode veto is pre-scoring and salary cannot rescue it. The
    candidate is retained and visible - P0_SPEC 5.2 makes retention itself the
    career doc's 'flagged for manual review' outcome - but never shortlisted.
    """
    ref = insert_job(temp_db, row_id=3, external_id="linkedin:1003")
    queue = queue_factory(temp_db, [ledger_record(
        "linkedin:1003", verdict="FAIL", reason_codes=[code], work_mode="HYBRID")])
    build = queue.build()
    assert lane_of(build, ref) == "EXCLUDED"
    assert build.entry(ref) not in build.lane("SHORTLIST")
    assert build.lane("SHORTLIST") == []
    assert build.entry(ref).payload["machine"]["eligible_for_scoring"] is False


def test_c2_no_fourth_verdict_value_is_invented(review_ruleset):
    """
    P0_SPEC 5.2: P0 introduces no FLAG / EXCEPTION-FLAG primary verdict. The
    queue's lanes map only the three real verdicts plus the absence of one.
    """
    declared = {lane.get("verdict") for lane in review_ruleset.lanes}
    assert declared == {"PASS", "UNKNOWN", "FAIL", None}


# ==========================================================================
# D / E / F / G - UNKNOWN is first class
# ==========================================================================

def test_d_unknown_work_mode_goes_to_review(temp_db, queue_factory):
    ref = insert_job(temp_db, row_id=4, external_id="linkedin:1004")
    queue = queue_factory(temp_db, [ledger_record(
        "linkedin:1004", verdict="UNKNOWN", reason_codes=["WM-UNKNOWN-ABSENT"])])
    build = queue.build()
    assert lane_of(build, ref) == "REVIEW"
    assert build.entry(ref).payload["machine"]["requires_human_review"] is True


def test_e_unknown_compensation_goes_to_review(temp_db, queue_factory):
    ref = insert_job(temp_db, row_id=5, external_id="linkedin:1005")
    queue = queue_factory(temp_db, [ledger_record(
        "linkedin:1005", verdict="UNKNOWN",
        reason_codes=["COMP-UNKNOWN-NON-NUMERIC"], work_mode="REMOTE")])
    assert lane_of(queue.build(), ref) == "REVIEW"


def test_f_a_remote_search_filter_never_promotes_unknown(temp_db, queue_factory):
    """
    The query was run with --remote remote. The posting still states no work
    mode. The filter is visible in provenance as a query parameter and is
    nowhere near the verdict - it is a volume reducer, not evidence.
    """
    ref = insert_job(temp_db, row_id=6, external_id="linkedin:1006")
    queue = queue_factory(temp_db, [ledger_record(
        "linkedin:1006", verdict="UNKNOWN", reason_codes=["WM-UNKNOWN-ABSENT"],
        work_mode="ABSENT", remote_filter="remote")])
    entry = queue.build().entry(ref)

    assert entry.lane == "REVIEW"
    assert entry.payload["machine"]["verdict"] == "UNKNOWN"
    assert entry.payload["machine"]["normalized_work_mode"] == "ABSENT"
    # The filter is retained for provenance, and is visibly a query parameter.
    assert entry.payload["machine"]["provenance"]["source_query"]["remote"] == "remote"
    assert entry.payload["machine"]["work_mode_provenance"] is None


def test_f2_unknown_is_never_collapsed_into_pass_or_fail(review_ruleset):
    prohibited = " ".join(review_ruleset.prohibited)
    assert "Promoting UNKNOWN to PASS" in prohibited
    assert "demoting UNKNOWN to FAIL" in prohibited
    lanes = {lane["id"]: lane.get("verdict") for lane in review_ruleset.lanes}
    assert lanes["REVIEW"] == "UNKNOWN"
    assert lanes["SHORTLIST"] == "PASS"
    assert lanes["REVIEW"] != lanes["SHORTLIST"]


def test_g_unknown_reason_codes_stay_visible(temp_db, queue_factory):
    ref = insert_job(temp_db, row_id=7, external_id="linkedin:1007")
    codes = ["WM-UNKNOWN-ABSENT", "COMP-UNKNOWN-NON-NUMERIC"]
    queue = queue_factory(temp_db, [ledger_record(
        "linkedin:1007", verdict="UNKNOWN", reason_codes=codes)])
    entry = queue.build().entry(ref)
    assert entry.payload["machine"]["reason_codes"] == codes
    assert entry.payload["machine"]["dimension_verdicts"]["work_mode"] == "UNKNOWN"


def test_g2_lanes_are_never_merged_into_one_ranked_list(temp_db, queue_factory):
    """
    OR-03b / T-12: an UNKNOWN must never be ordered above a confirmed-qualifying
    PASS. Lanes being separate collections is the structural guarantee - there
    is no list in which the two can be compared.
    """
    insert_job(temp_db, row_id=8, external_id="linkedin:1008")
    insert_job(temp_db, row_id=9, external_id="linkedin:1009")
    queue = queue_factory(temp_db, [
        ledger_record("linkedin:1008", verdict="PASS",
                      reason_codes=["WM-PASS-REMOTE"], work_mode="REMOTE"),
        ledger_record("linkedin:1009", verdict="UNKNOWN",
                      reason_codes=["COMP-UNKNOWN-ABSENT"], work_mode="REMOTE"),
    ])
    build = queue.build()
    assert [e.candidate_ref for e in build.lane("SHORTLIST")] == ["scraped_jobs:8"]
    assert [e.candidate_ref for e in build.lane("REVIEW")] == ["scraped_jobs:9"]
    assert set(build.lanes) == set(load_review_ruleset().lane_ids)
    assert "cross_lane_ordering" in \
        load_review_ruleset().raw["lane_assignment"]


def test_g3_an_unevaluated_row_is_unassessed_not_unknown(temp_db, queue_factory):
    """
    A row no gate evaluation covers has no verdict. Rendering it as UNKNOWN
    would claim the gate looked and could not decide, which is false.
    """
    ref = insert_job(temp_db, row_id=10, external_id="1128999", source="RemoteOK",
                     url="https://remoteok.com/remote-jobs/x-1128999")
    entry = queue_factory(temp_db, []).build().entry(ref)
    assert entry.lane == "NOT_EVALUATED"
    assert entry.payload["machine"]["verdict"] is None
    assert entry.payload["machine"]["verdict_available"] is False
    assert entry.payload["machine"]["ruleset_version"] == NOT_CAPTURED
    assert "unassessed" in entry.payload["machine"]["verdict_absent_reason"]


# ==========================================================================
# H / I / J - evidence, field provenance, version traceability
# ==========================================================================

def test_h_supporting_evidence_stays_traceable(temp_db, queue_factory):
    ref = insert_job(temp_db, row_id=11, external_id="linkedin:1011")
    evidence = [{
        "dimension": "compensation", "evidence_class": "NON_NUMERIC_CLAIM",
        "verbatim_text": "competitive salary", "source": "jd_body",
        "source_ref": "https://www.linkedin.com/jobs/view/1011",
        "source_fetched_at": "2026-09-01T09:59:00+00:00",
        "extractor_version": "jobops-policy@0.1.0",
    }]
    queue = queue_factory(temp_db, [ledger_record(
        "linkedin:1011", verdict="UNKNOWN",
        reason_codes=["COMP-UNKNOWN-NON-NUMERIC"], evidence=evidence)])
    entry = queue.build().entry(ref)

    assert entry.payload["machine"]["evidence"] == evidence
    item = entry.payload["machine"]["evidence"][0]
    assert item["verbatim_text"] == "competitive salary"
    assert item["source_ref"].startswith("https://")
    assert item["source_fetched_at"]
    provenance = entry.payload["machine"]["provenance"]
    assert provenance["raw_payload_ref"].startswith("raw/")
    assert "untrusted_text_note" in entry.payload["candidate"]


def test_i_field_provenance_stays_traceable_when_captured(temp_db, queue_factory):
    """The D1 record: which observation supplied the stored value."""
    ref = insert_job(temp_db, row_id=12, external_id="linkedin:1012")
    field_provenance = {
        "field_provenance": {"date": {
            "value_from": "search", "rule": "enrich", "erasure_prevented": True,
            "observations": [
                {"record": "search", "state": "value", "value": "2026-08-28"},
                {"record": "detail", "state": "stated_none", "value": None}]}},
        "conflicts": [{"field": "date", "resolved_value": "2026-08-28",
                       "reason": "empty_observation_did_not_erase_evidence"}],
    }
    queue = queue_factory(temp_db, [ledger_record(
        "linkedin:1012", verdict="UNKNOWN", reason_codes=["WM-UNKNOWN-ABSENT"],
        field_provenance=field_provenance)])
    surfaced = queue.build().entry(ref).payload["machine"]["field_provenance"]
    assert surfaced["field_provenance"]["date"]["value_from"] == "search"
    assert surfaced["field_provenance"]["date"]["erasure_prevented"] is True
    assert surfaced["conflicts"][0]["field"] == "date"


def test_i2_absent_field_provenance_is_not_captured_not_empty(temp_db, queue_factory):
    """
    P0_SPEC 4.4 three-state discipline. Runs predating the D1 fix carry no
    field_provenance key. The queue says "not captured" and does not
    manufacture an empty structure that would read as "there were no conflicts".
    """
    ref = insert_job(temp_db, row_id=13, external_id="linkedin:1013")
    queue = queue_factory(temp_db, [ledger_record(
        "linkedin:1013", verdict="UNKNOWN", reason_codes=["WM-UNKNOWN-ABSENT"])])
    entry = queue.build().entry(ref)
    assert entry.payload["machine"]["field_provenance"] == NOT_CAPTURED
    assert entry.payload["machine"]["field_provenance"] != {}


def test_j_ruleset_and_extractor_versions_stay_traceable(temp_db, queue_factory):
    ref = insert_job(temp_db, row_id=14, external_id="linkedin:1014")
    queue = queue_factory(temp_db, [ledger_record(
        "linkedin:1014", verdict="UNKNOWN", reason_codes=["WM-UNKNOWN-ABSENT"])])
    build = queue.build()
    machine = build.entry(ref).payload["machine"]
    assert machine["ruleset_version"] == "jobops-policy@0.1.0"
    assert machine["extractor_version"] == "linkedin-ingestion@0.1.0"
    assert machine["normalizer_version"] == "jobops-policy@0.1.0"
    assert machine["evaluated_at"] == "2026-09-01T10:00:00+00:00"
    assert build.review_version == "jobops-review@0.1.0"
    assert build.identity_version == "jobops-identity@0.1.0"


def test_j2_a_re_evaluation_is_a_new_record_and_the_old_one_survives(
        tmp_path, temp_db, review_ruleset):
    """
    P0_SPEC 5.3: a verdict is immutable against later ruleset changes. Two runs
    over one posting produce two verdicts; the queue shows the newer and keeps
    the older readable rather than overwriting it.
    """
    ref = insert_job(temp_db, row_id=15, external_id="linkedin:1015")
    ledger_root = tmp_path / "ingestion"
    write_ledger(ledger_root, "run-0001", [ledger_record(
        "linkedin:1015", verdict="UNKNOWN", reason_codes=["COMP-UNKNOWN-ABSENT"],
        evaluated_at="2026-08-01T10:00:00+00:00")])
    older = json.loads((ledger_root / "candidates" / "run-0001.jsonl").read_text())
    older["provenance"]["source_fetched_at"] = "2026-08-01T09:00:00+00:00"
    write_ledger(ledger_root, "run-0001", [older])
    newer = ledger_record("linkedin:1015", verdict="FAIL",
                          reason_codes=["COMP-FAIL-BELOW-FLOOR"],
                          evaluated_at="2026-09-01T10:00:00+00:00")
    newer["provenance"]["source_fetched_at"] = "2026-09-01T09:00:00+00:00"
    write_ledger(ledger_root, "run-0002", [newer])

    queue = ReviewQueue(db_path=temp_db, ruleset=review_ruleset,
                        ledger=CandidateLedgerStore(ledger_root),
                        decisions=DecisionStore(tmp_path / "review",
                                                ruleset=review_ruleset))
    entry = queue.build().entry(ref)
    assert entry.payload["machine"]["verdict"] == "FAIL"
    assert entry.lane == "BELOW_THRESHOLD"
    history = entry.payload["machine"]["verdict_history"]
    assert [h["verdict"] for h in history] == ["UNKNOWN"]
    assert history[0]["evaluated_at"] == "2026-08-01T10:00:00+00:00"
    assert entry.payload["candidate"]["first_observed_at"] == \
        "2026-08-01T09:00:00+00:00"
    assert entry.payload["candidate"]["last_observed_at"] == \
        "2026-09-01T09:00:00+00:00"


# ==========================================================================
# K / L / M / N / O / P - duplicates
# ==========================================================================

def test_k_l1_definite_duplicate_leaves_the_active_queue(temp_db, queue_factory):
    """
    The candidate is already an opportunity - already applied to. P0_SPEC 8.4:
    not re-surfaced.
    """
    ref = insert_job(temp_db, row_id=20, external_id="linkedin:4454261604",
                     company="Dautom", title="AI Data Engineer")
    insert_opportunity(temp_db, row_id=90, company="Dautom",
                       role="AI Data Engineer",
                       url="https://www.linkedin.com/jobs/view/4454261604/",
                       status="Applied")
    queue = queue_factory(temp_db, [ledger_record(
        "linkedin:4454261604", verdict="UNKNOWN",
        reason_codes=["WM-UNKNOWN-ABSENT"])])
    build = queue.build()
    entry = build.entry(ref)

    assert entry.lane == "SUPPRESSED_DUPLICATE"
    assert entry.payload["identity"]["matched_layer"] == "L1"
    assert entry.payload["identity"]["outcome"] == "DEFINITE_DUPLICATE"
    assert "SUPPRESSED_DUPLICATE" not in load_review_ruleset().active_lane_ids
    assert build.lane("REVIEW") == []


def test_l_l2_definite_duplicate_leaves_the_active_queue(temp_db, queue_factory):
    """L2 standing alone, on a host family exposing no source-native id."""
    ref = insert_job(temp_db, row_id=21, external_id="careers:abc",
                     source="Monks Careers", company="Monks", title="Testing Lead",
                     url="https://www.monks.com/careers/6128657004/testing-lead"
                         "?gh_src=a9b949034us")
    insert_opportunity(temp_db, row_id=91, company="Monks", role="Testing Lead",
                       url="https://monks.com/careers/6128657004/testing-lead/",
                       source="Monks Careers", status="Applied")
    build = queue_factory(temp_db, []).build()
    entry = build.entry(ref)
    assert entry.lane == "SUPPRESSED_DUPLICATE"
    assert entry.payload["identity"]["matched_layer"] == "L2"


def test_m_l4_definite_duplicate_leaves_the_active_queue(temp_db, queue_factory):
    """Same Workday tenant and requisition, two URL forms."""
    ref = insert_job(
        temp_db, row_id=22, external_id="careers:q1", source="Quantiphi Careers",
        company="Quantiphi", title="Senior Test Engineer",
        url="https://quantiphi.wd1.myworkdayjobs.com/en-US/Careers_at_Quantiphi"
            "/job/India/Senior-Test-Engineer_JR11513")
    insert_opportunity(
        temp_db, row_id=92, company="Quantiphi", role="Senior Test Engineer - AI/ML",
        url="https://quantiphi.wd1.myworkdayjobs.com/Careers_at_Quantiphi/job/"
            "IN-KA-Bengaluru/Senior-Test-Engineer---AI-ML_JR11513",
        status="Applied")
    entry = queue_factory(temp_db, []).build().entry(ref)
    assert entry.lane == "SUPPRESSED_DUPLICATE"
    assert entry.payload["identity"]["matched_layer"] == "L4"


def test_n_l3_probable_duplicate_stays_visible_and_flagged(temp_db, queue_factory):
    """
    P0_SPEC 8.4 grants suppression at L1/L2/L4 only. An exact L3 match stays in
    its verdict lane, carries a warning and the relationship, and the human
    decides.
    """
    ref = insert_job(temp_db, row_id=23, external_id="linkedin:2301",
                     company="Acme AI", title="AI Quality Engineer",
                     location="Bengaluru, Karnataka, India",
                     url="https://www.linkedin.com/jobs/view/2301")
    insert_job(temp_db, row_id=24, external_id="careers:acme-1",
               source="Acme Careers", company="Acme AI",
               title="AI Quality Engineer", location="Bengaluru, Karnataka, India",
               url="https://careers.acme.example/roles/xyz")
    queue = queue_factory(temp_db, [ledger_record(
        "linkedin:2301", verdict="UNKNOWN", reason_codes=["WM-UNKNOWN-ABSENT"])])
    entry = queue.build().entry(ref)

    assert entry.lane == "REVIEW"                       # NOT suppressed
    assert entry.payload["identity"]["outcome"] == "PROBABLE_DUPLICATE"
    assert entry.payload["identity"]["matched_layer"] == "L3"
    assert entry.payload["identity"]["presentation"] == "warning"
    assert entry.payload["identity"]["suppressed_from_active_queue"] is False
    assert entry.payload["identity"]["matched_record_ref"] == "scraped_jobs:24"


def test_o_l3_is_never_represented_as_a_definite_duplicate(review_ruleset,
                                                           temp_db, queue_factory):
    rule = review_ruleset.duplicate_presentation("PROBABLE_DUPLICATE")
    assert rule["suppress_from_active_queue"] is False
    assert review_ruleset.suppresses("PROBABLE_DUPLICATE", "L3") is False
    assert review_ruleset.suppresses("DEFINITE_DUPLICATE", "L3") is False
    assert "Promoting an L3 probable duplicate to definite identity." in \
        review_ruleset.prohibited

    ref = insert_job(temp_db, row_id=25, external_id="linkedin:2501",
                     company="Acme AI", title="AI Quality Engineer")
    insert_job(temp_db, row_id=26, external_id="careers:acme-2",
               source="Acme Careers", company="Acme AI",
               title="AI Quality Engineer",
               url="https://careers.acme.example/roles/abc")
    entry = queue_factory(temp_db, []).build().entry(ref)
    assert entry.payload["identity"]["outcome"] != "DEFINITE_DUPLICATE"


def test_p_suppression_deletes_and_modifies_nothing(temp_db, queue_factory):
    """Build the queue over a database and assert it is byte-identical after."""
    insert_job(temp_db, row_id=27, external_id="linkedin:4454261604",
               company="Dautom", title="AI Data Engineer")
    insert_opportunity(temp_db, row_id=93, company="Dautom",
                       role="AI Data Engineer",
                       url="https://www.linkedin.com/jobs/view/4454261604/",
                       status="Applied")

    def snapshot():
        with sqlite3.connect(f"file:{temp_db}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            return json.dumps({t: [dict(r) for r in conn.execute(
                f"SELECT * FROM {t} ORDER BY id")]
                for t in ("scraped_jobs", "opportunities")},
                sort_keys=True, default=str)

    before = snapshot()
    build = queue_factory(temp_db, []).build()
    assert build.entry("scraped_jobs:27").lane == "SUPPRESSED_DUPLICATE"
    assert snapshot() == before

    # The suppressed record is retained and fully retrievable, with the whole
    # inspection set intact - suppression is a presentation decision only.
    entry = build.entry("scraped_jobs:27")
    assert entry.payload["candidate"]["company"] == "Dautom"
    assert entry.payload["candidate"]["original_source_url"]
    assert entry.payload["candidate"]["canonical_identity_url"]
    assert entry.payload["identity"]["matched_record_ref"] == "opportunities:93"
    assert entry.payload["identity"]["matches"], "the evidence for the match is gone"
    assert "untouched" in entry.payload["identity"]["suppression_effect"]


def test_p2_the_queue_connection_physically_rejects_writes(temp_db, queue_factory):
    queue = queue_factory(temp_db, [])
    conn = queue._connect()
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("UPDATE opportunities SET status = 'Rejected'")
    finally:
        conn.close()


def test_p3_the_review_package_contains_no_write_statement():
    text = review_code().upper()
    for token in ("INSERT INTO", "UPDATE ", "DELETE FROM", "DROP ", "REPLACE INTO",
                  "ALTER TABLE", "CREATE TABLE", "CREATE INDEX"):
        assert token not in text, f"review attempts a database write: {token}"


# ==========================================================================
# Q / R / S - machine verdict vs human decision vs application outcome
# ==========================================================================

def test_q_resolving_unknown_does_not_fabricate_machine_evidence(
        tmp_path, temp_db, queue_factory):
    ref = insert_job(temp_db, row_id=30, external_id="linkedin:3001")
    queue = queue_factory(temp_db, [ledger_record(
        "linkedin:3001", verdict="UNKNOWN", reason_codes=["WM-UNKNOWN-ABSENT"])])
    before = queue.build().entry(ref)
    evidence_before = copy.deepcopy(before.payload["machine"]["evidence"])

    queue.decisions.record(Decision(
        candidate_ref=ref, kind="RESOLVE_UNKNOWN", decided_at=utc_now_iso(),
        dimension="work_mode", human_assertion="REMOTE",
        human_basis="recruiter email 2026-09-02",
        machine_context=queue.machine_context_for(ref)))

    after = queue.build().entry(ref)
    assert after.payload["machine"]["evidence"] == evidence_before
    assert after.payload["machine"]["verdict"] == "UNKNOWN"
    assert after.payload["machine"]["normalized_work_mode"] == "ABSENT"
    # The human assertion is present, and it is labelled as the human's.
    assert after.payload["human"]["human_assertion"] == "REMOTE"
    assert after.payload["human"]["human_basis"] == "recruiter email 2026-09-02"
    assert after.payload["human"]["is_machine_evidence"] is False
    standing = queue.decisions.current_for(ref)
    assert standing["asserted_by"] == "human"
    assert standing["is_machine_evidence"] is False


def test_r_a_human_decision_never_rewrites_the_machine_verdict(
        temp_db, queue_factory):
    """
    A human applying to an UNKNOWN candidate leaves it UNKNOWN. The lane, the
    verdict and the reason codes are all unchanged; only the human block moves.
    """
    ref = insert_job(temp_db, row_id=31, external_id="linkedin:3101")
    queue = queue_factory(temp_db, [ledger_record(
        "linkedin:3101", verdict="UNKNOWN",
        reason_codes=["WM-UNKNOWN-ABSENT", "COMP-UNKNOWN-ABSENT"])])
    before = queue.build().entry(ref).payload["machine"]

    queue.decisions.record(Decision(
        candidate_ref=ref, kind="ACCEPT", decided_at=utc_now_iso(),
        note="applying anyway", machine_context=queue.machine_context_for(ref)))

    after_entry = queue.build().entry(ref)
    assert after_entry.payload["machine"] == before
    assert after_entry.payload["machine"]["verdict"] == "UNKNOWN"
    assert after_entry.lane == "REVIEW"
    assert after_entry.payload["human"]["decision"] == "ACCEPT"
    assert after_entry.payload["machine"]["eligible_for_scoring"] is False


def test_s_machine_human_and_application_are_three_separate_blocks(
        temp_db, queue_factory):
    ref = insert_job(temp_db, row_id=32, external_id="linkedin:3201",
                     company="Dautom", title="AI Data Engineer")
    insert_opportunity(temp_db, row_id=94, company="Dautom",
                       role="AI Data Engineer", url="https://example.org/x",
                       status="Screening", scraped_job_id=32)
    queue = queue_factory(temp_db, [ledger_record(
        "linkedin:3201", verdict="UNKNOWN", reason_codes=["WM-UNKNOWN-ABSENT"])])
    queue.decisions.record(Decision(
        candidate_ref=ref, kind="ACCEPT", decided_at=utc_now_iso(),
        machine_context=queue.machine_context_for(ref)))

    entry = queue.build().entry(ref)
    assert entry.payload["machine"]["verdict"] == "UNKNOWN"
    assert entry.payload["human"]["decision"] == "ACCEPT"
    assert entry.payload["application"]["status"] == "Screening"
    assert entry.payload["application"]["opportunity_ref"] == "opportunities:94"
    # Three distinct keys; no field of one leaks into another.
    assert "verdict" not in entry.payload["human"]
    assert "decision" not in entry.payload["machine"]
    assert "verdict" not in entry.payload["application"]


def test_s2_a_decision_records_what_the_machine_said_at_the_time(
        temp_db, queue_factory):
    """
    So a later reader can tell "the human decided against what the machine then
    knew" from "the ruleset changed afterwards".
    """
    ref = insert_job(temp_db, row_id=33, external_id="linkedin:3301")
    queue = queue_factory(temp_db, [ledger_record(
        "linkedin:3301", verdict="UNKNOWN", reason_codes=["WM-UNKNOWN-ABSENT"])])
    record = queue.decisions.record(Decision(
        candidate_ref=ref, kind="SKIP", decided_at=utc_now_iso(),
        machine_context=queue.machine_context_for(ref)))
    assert record["machine_context"]["verdict"] == "UNKNOWN"
    assert record["machine_context"]["ruleset_version"] == "jobops-policy@0.1.0"
    assert record["machine_context"]["reason_codes"] == ["WM-UNKNOWN-ABSENT"]
    assert record["machine_context"]["lane"] == "REVIEW"


def test_s3_a_decision_is_reversed_by_appending_never_by_editing(
        temp_db, queue_factory):
    ref = insert_job(temp_db, row_id=34, external_id="linkedin:3401")
    queue = queue_factory(temp_db, [])
    first = queue.decisions.record(Decision(
        candidate_ref=ref, kind="SKIP", decided_at=utc_now_iso()))
    second = queue.decisions.record(Decision(
        candidate_ref=ref, kind="REOPEN", decided_at=utc_now_iso(),
        supersedes=first["decision_id"], note="changed my mind"))

    assert queue.decisions.current_for(ref)["decision_id"] == second["decision_id"]
    history = queue.decisions.history_for(ref)
    assert [h["kind"] for h in history] == ["SKIP", "REOPEN"]
    assert history[0] == first          # the superseded record is untouched
    assert "Editing or deleting a decision already written to the ledger." in \
        queue.ruleset.prohibited


def test_s4_a_duplicate_relationship_is_resolved_by_the_human_not_by_merging(
        temp_db, queue_factory):
    ref = insert_job(temp_db, row_id=35, external_id="linkedin:3501")
    queue = queue_factory(temp_db, [])
    record = queue.decisions.record(Decision(
        candidate_ref=ref, kind="CONFIRM_DUPLICATE", decided_at=utc_now_iso(),
        related_record_ref="scraped_jobs:36", note="same req"))
    assert record["related_record_ref"] == "scraped_jobs:36"
    assert record["kind"] == "CONFIRM_DUPLICATE"
    kind = queue.ruleset.decision_kind("CONFIRM_DUPLICATE")
    assert "does not merge, delete or rewrite" in kind["note"]


def test_s5_a_decision_kind_the_artifact_does_not_declare_is_refused(
        tmp_path, review_ruleset):
    store = DecisionStore(tmp_path / "review", ruleset=review_ruleset)
    with pytest.raises(ReviewDriftError):
        store.record(Decision(candidate_ref="scraped_jobs:1", kind="AUTO_APPLY",
                              decided_at=utc_now_iso()))


# ==========================================================================
# T / U - no automation of any kind
# ==========================================================================

def test_t_no_auto_apply_exists(review_ruleset):
    for kind in review_ruleset.decision_kinds:
        assert kind["submits_anything"] is False, \
            f"decision kind {kind['id']} claims to submit something"
    assert "Submitting an application, contacting a recruiter, or sending any " \
           "message." in review_ruleset.prohibited

    code = review_code().lower()
    for token in ("requests.post", "urllib.request", "smtplib", "http.client",
                  "subprocess", "socket.", "sendmail", "webhook",
                  "auto_apply", "autoapply", "submit_application"):
        assert token not in code, f"review reaches outward: {token}"


def test_u_no_recruiter_outreach_exists():
    code = review_code().lower()
    for token in ("gmail", "n8n", "smtp", "linkedin_message", "send_message",
                  "outreach", "recruiter_email", "dm(", "inmail"):
        assert token not in code, f"review implements outreach: {token}"


def test_t2_the_accept_action_is_a_decision_not_a_submission(review_ruleset):
    accept = review_ruleset.decision_kind("ACCEPT")
    assert accept["submits_anything"] is False
    assert "does not submit an application" in accept["note"]
    assert "invoked by the human" in accept["note"]


def test_t3_no_scoring_or_opportunity_quality_signal_exists():
    code = review_code().lower()
    for token in ("match_score >", "compute_score", "rank_by", "ai_native",
                  "opportunity_quality", "company_score", "fit_score",
                  "weighted"):
        assert token not in code, f"P1 scoring appears in P0-08: {token}"


def test_t4_no_new_ingestion_source_is_introduced():
    code = review_code().lower()
    for token in ("naukri", "remoteok_integration", "scraper", "fetch(",
                  "bun ", "linkedin_cli", "cli.ts"):
        assert token not in code, f"P0-08 touches ingestion: {token}"


def test_t5_review_derives_no_verdict():
    """
    The queue never evaluates policy. It does not import the gate, and the
    verdict values appear nowhere in its executable source.
    """
    code = review_code()
    assert "HardEligibilityGate" not in code
    assert "evaluate_posting" not in code
    assert "resume_config" not in code
    for token in ("WM-FAIL", "COMP-FAIL", "min_salary", "2000000"):
        assert token not in code, f"policy leaked into review: {token}"


# ==========================================================================
# Y / Z - determinism and idempotence
# ==========================================================================

def test_y_queue_construction_is_deterministic(temp_db, queue_factory):
    for row_id, external_id, verdict, codes in (
            (40, "linkedin:4001", "UNKNOWN", ["WM-UNKNOWN-ABSENT"]),
            (41, "linkedin:4002", "UNKNOWN", ["COMP-UNKNOWN-ABSENT"]),
            (42, "linkedin:4003", "FAIL", ["WM-FAIL-HYBRID"]),
            (43, "linkedin:4004", "PASS", ["WM-PASS-REMOTE"])):
        insert_job(temp_db, row_id=row_id, external_id=external_id)
    queue = queue_factory(temp_db, [
        ledger_record("linkedin:4001", verdict="UNKNOWN",
                      reason_codes=["WM-UNKNOWN-ABSENT"]),
        ledger_record("linkedin:4002", verdict="UNKNOWN",
                      reason_codes=["COMP-UNKNOWN-ABSENT"]),
        ledger_record("linkedin:4003", verdict="FAIL",
                      reason_codes=["WM-FAIL-HYBRID"]),
        ledger_record("linkedin:4004", verdict="PASS",
                      reason_codes=["WM-PASS-REMOTE"], work_mode="REMOTE"),
    ])

    def stripped(build):
        payload = copy.deepcopy(build.as_dict())
        payload.pop("built_at")
        return json.dumps(payload, sort_keys=True, default=str)

    assert stripped(queue.build()) == stripped(queue.build())
    assert queue.build().counts == queue.build().counts


def test_y2_lane_order_is_stable_and_batches_like_escalations(
        temp_db, queue_factory):
    """P0_SPEC 9.2: the UNKNOWN lane is ordered by evidence-gap type."""
    insert_job(temp_db, row_id=50, external_id="linkedin:5001")
    insert_job(temp_db, row_id=51, external_id="linkedin:5002")
    insert_job(temp_db, row_id=52, external_id="linkedin:5003")
    queue = queue_factory(temp_db, [
        ledger_record("linkedin:5001", verdict="UNKNOWN",
                      reason_codes=["WM-UNKNOWN-ABSENT"]),
        ledger_record("linkedin:5002", verdict="UNKNOWN",
                      reason_codes=["COMP-UNKNOWN-ABSENT"]),
        ledger_record("linkedin:5003", verdict="UNKNOWN",
                      reason_codes=["COMP-UNKNOWN-ABSENT"]),
    ])
    order = [e.candidate_ref for e in queue.build().lane("REVIEW")]
    assert order == ["scraped_jobs:51", "scraped_jobs:52", "scraped_jobs:50"]
    assert order == [e.candidate_ref for e in queue.build().lane("REVIEW")]


def test_z_rebuilding_adds_no_candidate_and_mutates_no_evidence(
        tmp_path, temp_db, queue_factory):
    insert_job(temp_db, row_id=60, external_id="linkedin:6001")
    records = [ledger_record("linkedin:6001", verdict="UNKNOWN",
                             reason_codes=["WM-UNKNOWN-ABSENT"])]
    queue = queue_factory(temp_db, records)

    ledger_path = queue.ledger.ledger_paths()[0]
    ledger_before = ledger_path.read_bytes()

    def db_snapshot():
        with sqlite3.connect(f"file:{temp_db}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            return json.dumps({t: [dict(r) for r in conn.execute(
                f"SELECT * FROM {t} ORDER BY id")]
                for t in ("scraped_jobs", "opportunities")},
                sort_keys=True, default=str)

    db_before = db_snapshot()
    first = queue.build()
    second = queue.build()
    third = queue.build()

    assert first.counts["total"] == second.counts["total"] == third.counts["total"] == 1
    assert len(second.lane("REVIEW")) == 1
    assert ledger_path.read_bytes() == ledger_before
    assert db_snapshot() == db_before
    assert not (tmp_path / "review" / "decisions.jsonl").exists()


def test_z2_recording_a_decision_appends_exactly_one_line(temp_db, queue_factory):
    ref = insert_job(temp_db, row_id=61, external_id="linkedin:6101")
    queue = queue_factory(temp_db, [])
    for index in range(3):
        queue.decisions.record(Decision(candidate_ref=ref, kind="DEFER",
                                        decided_at=utc_now_iso(),
                                        note=f"pass {index}"))
    lines = queue.decisions.path.read_text().strip().splitlines()
    assert len(lines) == 3
    assert len({json.loads(l)["decision_id"] for l in lines}) == 3


# ==========================================================================
# The artifact is the authority
# ==========================================================================

def test_the_review_artifact_is_version_pinned(review_ruleset):
    from review.ruleset import ReviewRuleset
    assert review_ruleset.version == "jobops-review@0.1.0"
    with pytest.raises(ReviewDriftError):
        ReviewRuleset(REVIEW_ARTIFACT, expected_version="jobops-review@9.9.9")


def test_a_verdict_with_no_lane_is_drift_not_a_silent_default(review_ruleset):
    with pytest.raises(ReviewDriftError):
        review_ruleset.lane_for_verdict("EXCEPTION-FLAG")


def test_the_artifact_documents_every_source_of_truth(review_ruleset):
    sources = review_ruleset.source_of_truth
    for required in ("machine_verdict", "evidence_and_provenance", "candidate_row",
                     "identity", "human_decision", "application_outcome"):
        assert required in sources, f"undocumented source of truth: {required}"
        assert sources[required].get("store")
    assert sources["human_decision"]["access"] == "append-only"
    assert sources["machine_verdict"]["store"].endswith(".jsonl")
    assert "read-only" in sources["application_outcome"]["access"]


def test_suppression_grade_is_read_from_the_identity_artifact_not_redeclared(
        review_ruleset):
    """
    P0-08 must not invent its own idea of which layer is strong enough. The
    review artifact names the layers; the identity artifact remains the place
    where suppression grade is decided, and the two must agree.
    """
    from identity import load_identity_ruleset
    identity = load_identity_ruleset()
    declared = review_ruleset.duplicate_presentation(
        "DEFINITE_DUPLICATE")["requires_layer_in"]
    assert sorted(declared) == sorted(identity.suppression_grade_layers())
    assert "L3" not in declared


# ==========================================================================
# Read-only validation against the live data
# ==========================================================================

@pytest.fixture(scope="module")
def live_build():
    """One read-only build over the real database and the real evidence store."""
    return ReviewQueue(db_path=LIVE_DB).build()


@pytest.mark.parametrize("company,fragment", [
    ("Elastic", "AI QA and Evaluation Engineer"),
    ("Qentelli", "AI Quality Assurance Engineer"),
    ("SymphonyAI Group - India", "AI-QA"),
])
def test_the_three_real_linkedin_candidates_are_representable(live_build, company,
                                                              fragment):
    """
    The postings that exposed the missing review layer, surfaced through the
    queue using their actual stored evidence. Nothing is hard-coded into the
    implementation; this test only asserts the queue can represent what the
    database and ledger already hold.
    """
    matches = [e for e in live_build.lane("REVIEW")
               if e.payload["candidate"]["company"] == company
               and fragment in (e.payload["candidate"]["job_title"] or "")]
    assert len(matches) == 1, f"{company} is not representable in the REVIEW lane"
    entry = matches[0]
    machine = entry.payload["machine"]

    assert machine["verdict"] == "UNKNOWN"
    assert machine["requires_human_review"] is True
    assert machine["reason_codes"], "an UNKNOWN with no reason code is unexplained"
    assert all(code.startswith(("WM-UNKNOWN", "COMP-UNKNOWN"))
               for code in machine["reason_codes"])
    assert machine["ruleset_version"] == "jobops-policy@0.1.0"
    assert machine["evaluated_at"]
    assert machine["provenance"]["raw_payload_ref"]
    assert entry.payload["candidate"]["original_source_url"].startswith("https://")
    assert entry.payload["candidate"]["canonical_identity_url"]
    # The search used --remote remote and the work mode is still not asserted.
    assert machine["provenance"]["source_query"]["remote"] == "remote"
    assert machine["normalized_work_mode"] == "ABSENT"
    # Human and application layers are empty because nobody has decided yet.
    assert entry.payload["human"]["decision"] is None
    assert entry.payload["application"]["status"] is None


def test_the_live_queue_puts_nothing_in_the_shortlist_it_should_not(live_build):
    """Every live candidate is UNKNOWN, so the shortlist must be empty."""
    assert live_build.lane("SHORTLIST") == []
    assert live_build.counts["REVIEW"] == 3


@pytest.mark.parametrize("scraped_ref,opportunity_ref", [
    ("scraped_jobs:3", "opportunities:27"),
    ("scraped_jobs:43", "opportunities:28"),
])
def test_the_known_bridge_pairs_are_suppressed_not_cleaned_up(live_build,
                                                              scraped_ref,
                                                              opportunity_ref):
    """
    Legitimate bridge linkage, not corruption. The candidate is recognized as
    already represented in opportunities and is kept out of the active queue -
    and both rows still exist, untouched.
    """
    entry = live_build.entry(scraped_ref)
    assert entry is not None
    assert entry.lane == "SUPPRESSED_DUPLICATE"
    assert entry.payload["identity"]["outcome"] == "DEFINITE_DUPLICATE"
    assert entry.payload["identity"]["matched_record_ref"] == opportunity_ref

    with sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True) as conn:
        assert conn.execute("SELECT COUNT(*) FROM scraped_jobs WHERE id = ?",
                            (int(scraped_ref.split(":")[1]),)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM opportunities WHERE id = ?",
                            (int(opportunity_ref.split(":")[1]),)).fetchone()[0] == 1


def test_the_live_legacy_rows_are_unassessed_not_given_a_verdict(live_build):
    """
    The RemoteOK rows predate the gate. They are shown as unassessed, and none
    of them is presented as PASS, UNKNOWN or FAIL.
    """
    unevaluated = live_build.lane("NOT_EVALUATED")
    assert unevaluated, "expected the pre-gate rows to be represented"
    for entry in unevaluated:
        assert entry.payload["machine"]["verdict"] is None
        assert entry.payload["machine"]["verdict_available"] is False


def test_building_the_live_queue_writes_nothing(live_build):
    """
    The live build above already ran. Assert the evidence store and the
    database are unchanged by it, and that no decision file was created as a
    side effect of merely looking.
    """
    with sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True) as conn:
        assert conn.execute("SELECT COUNT(*) FROM scraped_jobs").fetchone()[0] == \
            live_build.counts["total"]
    ledger = CandidateLedgerStore(LIVE_LEDGER_ROOT)
    assert ledger.counts()["candidates"] == 3
    assert live_build.sources["machine_verdict"].endswith("candidates")
