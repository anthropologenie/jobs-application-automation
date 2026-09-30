#!/usr/bin/env python3
"""
P0-07 cross-source identity / deduplication - deterministic tests

FIXTURE TESTS, plus a small number of READ-ONLY assertions against the live
database. Nothing here contacts LinkedIn, nothing here requires `bun`, and no
test in this file writes, deletes, merges or repairs a single row. The three
real LinkedIn records produced by the first live P0-06 run (scraped_jobs 78, 79
and 80) and the existing opportunities rows are used as read-only evidence
where a fixture would be weaker evidence than the real thing.

What these tests assert:

  * L1 (source_portal, external_id) is idempotent and namespaced, so the same
    numeric id from two portals is two jobs;
  * L2 canonicalization resolves real URL variance - the slug form the search
    result returned and the bare form the detail response returned are one
    identity - while REJECTING listing, root and fragment-only URLs, and while
    never destroying the original URL;
  * L3 is conservative: an exact company+title+location match is a PROBABLE
    duplicate for a human, never a definite one; a differing location is
    counter-evidence; a missing location fabricates nothing;
  * L4 requisition ids are namespaced by ATS system and tenant, so the same
    number on two systems is two jobs;
  * matching spans scraped_jobs AND opportunities, so something already applied
    to is recognized;
  * identity uncertainty stays uncertainty and is never collapsed;
  * deduplication changes no application status, no gate verdict and no
    UNKNOWN;
  * D1: a detail response that states nothing cannot erase evidence the search
    result supplied.

Run:
    python3 -m pytest tests/test_p0_07_identity_dedup.py -v

Author: Karthik Shetty
Created: 2026-09-02
"""

import ast
import copy
import json
import re
import sqlite3
from pathlib import Path

import pytest

from identity import (
    AtsRequisition,
    IdentityDriftError,
    IdentityIndex,
    IdentityRecord,
    IdentityResolver,
    IdentityStore,
    canonicalize_url,
    load_identity_ruleset,
    normalize_company,
    normalize_location,
    normalize_title,
    record_from_candidate,
    record_from_opportunity,
    record_from_scraped_job,
    requisition_from_url,
)
from ingestion.merge import (
    ENRICH,
    FIRST_OBSERVATION,
    MergedRecord,
    SourceRecord,
    merge_source_records,
)
from policy import HardEligibilityGate

REPO_ROOT = Path(__file__).resolve().parent.parent
LIVE_DB = REPO_ROOT / "data" / "jobs-tracker.db"
IDENTITY_DIR = REPO_ROOT / "identity"
IDENTITY_ARTIFACT = IDENTITY_DIR / "jobops-identity-0.1.0.json"

# The URL variance the first real run actually produced.
LIVE_SEARCH_URL = ("https://in.linkedin.com/jobs/view/"
                   "ai-qa-and-evaluation-engineer-at-elastic-4459864135")
LIVE_DETAIL_URL = "https://www.linkedin.com/jobs/view/4459864135"


def code_only(path):
    """
    A module's executable source, with docstrings and comments removed.

    Several tests below assert that the identity package holds no policy, no
    verdict vocabulary, no similarity scoring and no write statement. Prose
    that NAMES one of those in order to say it is deliberately absent - "never
    turns an UNKNOWN into a PASS", "computes no similarity" - is documentation,
    not an implementation, and must not trip the assertion.
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


def identity_code():
    return "\n".join(code_only(path) for path in sorted(IDENTITY_DIR.glob("*.py")))


@pytest.fixture(scope="module")
def ruleset():
    return load_identity_ruleset()


@pytest.fixture
def make(ruleset):
    """Build a candidate record with as little ceremony as the test allows."""
    def _make(ref, **kwargs):
        return record_from_candidate(ruleset, record_ref=ref, **kwargs)
    return _make


def resolve(ruleset, candidate, *records):
    return IdentityResolver(IdentityIndex(records), ruleset).resolve(candidate)


def names(ruleset):
    return {key: ruleset.outcome_name(key) for key in
            ("definite_duplicate", "probable_duplicate", "identity_uncertain",
             "distinct")}


# ==========================================================================
# TEST 1 - L1: same source, same external id
# ==========================================================================

def test_1_same_source_and_external_id_is_a_definite_duplicate(ruleset, make):
    held = make("scraped_jobs:78", source="LinkedIn",
                external_id="linkedin:4459864135", url=LIVE_DETAIL_URL,
                company="Elastic", title="AI QA and Evaluation Engineer",
                location="Bengaluru, Karnataka, India")
    again = make("candidate:rerun", source="LinkedIn",
                 external_id="linkedin:4459864135", url=LIVE_SEARCH_URL,
                 company="Elastic", title="AI QA and Evaluation Engineer",
                 location="Bengaluru, Karnataka, India")

    result = resolve(ruleset, again, held)
    assert result.outcome == names(ruleset)["definite_duplicate"]
    assert result.matched_layer == "L1"
    assert result.matched_record_ref == "scraped_jobs:78"
    assert "ID-L1-MATCH" in result.reason_codes


def test_1b_l1_is_idempotent_within_one_run(ruleset, make):
    """
    The second occurrence inside a single run resolves against the first.

    This is the behaviour re-running ingestion depends on: two consecutive runs
    add zero duplicate representations (P0_SPEC 13, X7).
    """
    batch = [make(f"candidate:{i}", source="LinkedIn",
                  external_id="linkedin:4459864135", url=LIVE_DETAIL_URL,
                  company="Elastic", title="AI QA and Evaluation Engineer",
                  location="Bengaluru, Karnataka, India") for i in range(3)]
    resolver = IdentityResolver(IdentityIndex(), ruleset)
    outcomes = [r.outcome for r in resolver.resolve_batch(batch)]
    assert outcomes[0] == names(ruleset)["distinct"]
    assert outcomes[1:] == [names(ruleset)["definite_duplicate"]] * 2


def test_1c_two_consecutive_runs_add_zero_new_identities(ruleset, make):
    run = [make("candidate:a", source="LinkedIn", external_id="linkedin:4459864135",
                url=LIVE_SEARCH_URL, company="Elastic",
                title="AI QA and Evaluation Engineer", location="Bengaluru"),
           make("candidate:b", source="LinkedIn", external_id="linkedin:4460144522",
                url="https://www.linkedin.com/jobs/view/4460144522",
                company="Qentelli", title="AI QA Engineer", location="Hyderabad")]
    resolver = IdentityResolver(IdentityIndex(), ruleset)
    first = resolver.resolve_batch(run)
    assert all(r.outcome == names(ruleset)["distinct"] for r in first)

    # Second run: the same postings, now held.
    index = IdentityIndex(run)
    second = IdentityResolver(index, ruleset).resolve_batch(
        [make(f"candidate:rerun-{i}", source=r.source, external_id=r.external_id,
              url=r.original_source_url, company=r.company, title=r.title,
              location=r.location) for i, r in enumerate(run)])
    assert [r.outcome for r in second] == [names(ruleset)["definite_duplicate"]] * 2
    assert all(r.suppress_from_review for r in second)


def test_1d_the_same_numeric_id_on_two_portals_is_two_jobs(ruleset, make):
    """
    scraped_jobs.external_id is UNIQUE table-wide and older RemoteOK rows hold a
    bare number, so the L1 key is namespaced by portal. 1128942 on RemoteOK and
    1128942 on LinkedIn must not collapse.
    """
    remoteok = make("scraped_jobs:3", source="RemoteOK", external_id="1128942",
                    url="https://remoteOK.com/remote-jobs/remote-contract-"
                        "senior-software-engineer-yld-1128942",
                    company="YLD", title="Contract Senior Software Engineer",
                    location="Remote")
    linkedin = make("candidate:collision", source="LinkedIn",
                    external_id="linkedin:1128942",
                    url="https://www.linkedin.com/jobs/view/1128942",
                    company="Some Other Company", title="Data Engineer",
                    location="India")
    result = resolve(ruleset, linkedin, remoteok)
    assert result.outcome == names(ruleset)["distinct"]
    assert result.matched_record_ref is None


# ==========================================================================
# TEST 2 / 3 - L2: canonical URL identity, and the original URL survives it
# ==========================================================================

def test_2_linkedin_slug_url_and_bare_detail_url_are_one_identity(ruleset):
    """The exact variance the first real LinkedIn run produced."""
    search = canonicalize_url(LIVE_SEARCH_URL, ruleset)
    detail = canonicalize_url(LIVE_DETAIL_URL, ruleset)
    assert search.identity_url == detail.identity_url
    assert search.external_id == detail.external_id == "4459864135"
    assert search.identity_url == "https://linkedin.com/jobs/view/4459864135"


@pytest.mark.parametrize("variant", [
    "https://www.linkedin.com/jobs/view/4459864135",
    "https://www.linkedin.com/jobs/view/4459864135/",
    "http://in.linkedin.com/jobs/view/ai-qa-at-elastic-4459864135",
    "https://linkedin.com/jobs/view/4459864135?trk=public_jobs&refId=abc",
    "https://uk.linkedin.com/jobs/view/some-other-slug-4459864135#applyBox",
    "in.linkedin.com/jobs/view/ai-qa-and-evaluation-engineer-at-elastic-4459864135",
])
def test_2b_url_variants_reduce_to_one_identity(ruleset, variant):
    assert canonicalize_url(variant, ruleset).identity_url == \
        "https://linkedin.com/jobs/view/4459864135"


def test_2c_l2_matches_without_any_l1_evidence(ruleset, make):
    """
    L2 standing on its own, proven on a host family that exposes no
    source-native id: tracking parameters, host case, www and a trailing slash
    all fall away, and the two records are one identity at L2.
    """
    held = make("opportunities:26", source="Monks Careers",
                url="https://www.monks.com/careers/6128657004/testing-lead"
                    "?gh_src=a9b949034us",
                company="Monks", title="Testing Lead")
    candidate = make("candidate:monks", source="Some Aggregator",
                     url="https://monks.com/careers/6128657004/testing-lead/"
                         "?utm_campaign=weekly",
                     company="Media Monks", title="QA Testing Lead")
    assert held.l1_key is None and candidate.l1_key is None
    result = resolve(ruleset, candidate, held)
    assert result.outcome == names(ruleset)["definite_duplicate"]
    assert result.matched_layer == "L2"
    assert "ID-L2-MATCH" in result.reason_codes


def test_3_the_original_url_is_retained_after_canonicalization(ruleset, make):
    record = make("candidate:provenance", source="LinkedIn",
                  external_id="linkedin:4459864135", url=LIVE_SEARCH_URL,
                  company="Elastic", title="AI QA and Evaluation Engineer",
                  location="Bengaluru")
    assert record.original_source_url == LIVE_SEARCH_URL
    assert record.canonical_identity_url == "https://linkedin.com/jobs/view/4459864135"
    assert record.original_source_url != record.canonical_identity_url

    payload = record.as_dict()
    assert payload["url"]["original_source_url"] == LIVE_SEARCH_URL
    assert payload["url"]["canonical_identity_url"] == \
        "https://linkedin.com/jobs/view/4459864135"


def test_3b_a_rejected_url_still_carries_its_original_and_its_reason(ruleset):
    rejected = canonicalize_url("https://jobs.lever.co/Sprinto", ruleset)
    assert rejected.identity_url is None
    assert rejected.original == "https://jobs.lever.co/Sprinto"
    assert rejected.reason_codes


@pytest.mark.parametrize("url,code", [
    ("https://jobs.lever.co/Sprinto", "ID-URL-NOT-A-POSTING-PATH"),
    ("https://recruiting.ultipro.com/", "ID-URL-ROOT-ONLY"),
    ("https://careers.example.com/#job-4321", "ID-URL-FRAGMENT-ONLY"),
    ("https://careers.example.com/jobs", "ID-URL-LISTING-PAGE"),
    ("https://www.linkedin.com/jobs/search?keywords=qa", "ID-URL-NOT-A-POSTING-PATH"),
    ("mailto:recruiter@example.com", "ID-URL-UNSUPPORTED-SCHEME"),
    (None, "ID-URL-ABSENT"),
])
def test_3c_listing_root_and_fragment_urls_are_refused_as_identities(ruleset, url, code):
    """
    P0_SPEC 8.2 requires these be rejected rather than stored as identities.
    A company board URL used as an identity merges every posting that employer
    has.
    """
    result = canonicalize_url(url, ruleset)
    assert result.identity_url is None
    assert code in result.reason_codes


def test_3d_two_records_sharing_a_listing_url_do_not_become_one_job(ruleset, make):
    a = make("opportunities:22", source="Sprinto Careers",
             url="https://jobs.lever.co/Sprinto", company="Sprinto",
             title="Lead SDET")
    b = make("candidate:sprinto-2", source="Sprinto Careers",
             url="https://jobs.lever.co/Sprinto", company="Sprinto",
             title="Senior Backend Engineer")
    result = resolve(ruleset, b, a)
    assert result.outcome == names(ruleset)["distinct"]


def test_3e_an_unrecognized_query_parameter_is_identity_bearing(ruleset):
    """Dropping unknown parameters would merge every posting on that host."""
    one = canonicalize_url("https://www.rapidbrains.com/job?id=NIM2919", ruleset)
    two = canonicalize_url("https://www.rapidbrains.com/job?id=NIM3000", ruleset)
    assert one.identity_url and two.identity_url
    assert one.identity_url != two.identity_url


# ==========================================================================
# TEST 4-7 - L3: conservative company / title / location
# ==========================================================================

def test_4_same_company_title_and_location_is_probable_not_definite(ruleset, make):
    """
    P0_SPEC 8.4 grants suppression confidence at L1/L2/L4 only. An exact L3
    match is medium confidence, so it is surfaced for a human rather than
    asserted.
    """
    held = make("scraped_jobs:900", source="LinkedIn",
                url="https://careers.acme.example/postings/aaa",
                company="Acme AI", title="AI Quality Engineer",
                location="Bengaluru, Karnataka, India")
    candidate = make("candidate:l3", source="Careers Site",
                     url="https://acme.example.org/roles/bbb",
                     company="Acme AI", title="AI Quality Engineer",
                     location="Bengaluru, Karnataka, India")
    result = resolve(ruleset, candidate, held)
    assert result.outcome == names(ruleset)["probable_duplicate"]
    assert result.matched_layer == "L3"
    assert "ID-L3-MATCH" in result.reason_codes
    assert result.identity_uncertain is True
    assert result.requires_human_review is True
    assert result.suppress_from_review is False


def test_4b_l3_normalization_is_conservative(ruleset):
    assert normalize_company("Qentelli Pvt. Ltd.", ruleset) == "qentelli"
    assert normalize_company("Elastic Co.", ruleset) == "elastic"
    # A division or country qualifier is NOT stripped: merging a subsidiary
    # into its parent would assert an identity nobody established.
    assert normalize_company("SymphonyAI Group - India", ruleset) == \
        "symphonyai group india"
    assert normalize_company("SymphonyAI", ruleset) != \
        normalize_company("SymphonyAI Group - India", ruleset)
    # No seniority stripping, no synonym expansion.
    assert normalize_title("AI QA Engineer", ruleset) != \
        normalize_title("AI Quality Assurance Engineer", ruleset)
    assert normalize_title("Senior AI QA Engineer", ruleset) != \
        normalize_title("AI QA Engineer", ruleset)
    # No geographic inference.
    assert normalize_location("Bengaluru", ruleset) != \
        normalize_location("Bengaluru, Karnataka, India", ruleset)


def test_5_identical_title_at_a_different_company_is_distinct(ruleset, make):
    held = make("scraped_jobs:901", source="LinkedIn",
                url="https://careers.acme.example/postings/aaa",
                company="Acme AI", title="AI Quality Engineer",
                location="Bengaluru")
    candidate = make("candidate:other-co", source="LinkedIn",
                     url="https://careers.globex.example/postings/zzz",
                     company="Globex", title="AI Quality Engineer",
                     location="Bengaluru")
    result = resolve(ruleset, candidate, held)
    assert result.outcome == names(ruleset)["distinct"]
    assert result.matches == []


def test_6_same_company_and_title_in_a_different_location_is_distinct(ruleset, make):
    """
    Two requisitions for one title at one employer in two cities are two
    requisitions. A differing evaluable location is counter-evidence, and it is
    reported as such rather than silently dropped.
    """
    held = make("scraped_jobs:902", source="LinkedIn",
                url="https://careers.acme.example/postings/blr",
                company="Acme AI", title="AI Quality Engineer",
                location="Bengaluru, Karnataka, India")
    candidate = make("candidate:hyd", source="LinkedIn",
                     url="https://careers.acme.example/postings/hyd",
                     company="Acme AI", title="AI Quality Engineer",
                     location="Hyderabad, Telangana, India")
    result = resolve(ruleset, candidate, held)
    assert result.outcome == names(ruleset)["distinct"]
    assert result.matches == []
    assert [c["reason_codes"] for c in result.considered] == \
        [["ID-L3-LOCATION-DIFFERS"]]


@pytest.mark.parametrize("candidate_location,held_location", [
    (None, "Bengaluru, Karnataka, India"),
    ("Bengaluru, Karnataka, India", None),
    ("Unknown", "Bengaluru, Karnataka, India"),
    ("", "Bengaluru, Karnataka, India"),
    (None, None),
])
def test_7_a_missing_or_unknown_location_fabricates_no_identity(
        ruleset, make, candidate_location, held_location):
    """
    An absent location is not evidence of sameness and not evidence of
    difference. The pair is a near-match: retained, linked, surfaced - never
    asserted as a duplicate (P0_SPEC 8.3).
    """
    held = make("scraped_jobs:903", source="LinkedIn",
                url="https://careers.acme.example/postings/aaa",
                company="Acme AI", title="AI Quality Engineer",
                location=held_location)
    candidate = make("candidate:noloc", source="Careers Site",
                     url="https://acme.example.org/roles/bbb",
                     company="Acme AI", title="AI Quality Engineer",
                     location=candidate_location)
    result = resolve(ruleset, candidate, held)
    assert result.outcome == names(ruleset)["identity_uncertain"]
    assert result.identity_uncertain is True
    assert result.suppress_from_review is False
    assert "ID-L3-PARTIAL" in result.reason_codes
    assert result.matched_record_ref == "scraped_jobs:903"


def test_7b_an_unknown_location_never_matches_another_unknown_location(ruleset):
    assert normalize_location("Unknown", ruleset) is None
    assert normalize_location("N/A", ruleset) is None
    assert normalize_location("   ", ruleset) is None


def test_7c_l3_requires_all_three_components(ruleset, make):
    record = make("candidate:partial", company="Acme AI",
                  title="AI Quality Engineer", location=None)
    assert record.l3_key is None
    assert "ID-L3-NOT-EVALUABLE" in \
        resolve(ruleset, record).reason_codes


# ==========================================================================
# TEST 8 / 9 - L4: ATS requisition identity, namespaced
# ==========================================================================

def test_8_same_ats_tenant_and_requisition_is_a_duplicate(ruleset, make):
    """Two URL forms of one Workday requisition - locale prefix and title slug
    differ, the requisition does not."""
    held = make("opportunities:25", source="LinkedIn",
                url="https://quantiphi.wd1.myworkdayjobs.com/Careers_at_Quantiphi"
                    "/job/IN-KA-Bengaluru/Senior-Test-Engineer---AI-ML_JR11513",
                company="Quantiphi", title="Senior Test Engineer - AI/ML")
    candidate = make("candidate:workday", source="Quantiphi Careers",
                     url="https://quantiphi.wd1.myworkdayjobs.com/en-US/"
                         "Careers_at_Quantiphi/job/India/Senior-Test-Engineer_JR11513",
                     company="Quantiphi", title="Senior Test Engineer")
    assert candidate.l4_key == ("workday", "quantiphi", "JR11513")
    result = resolve(ruleset, candidate, held)
    assert result.outcome == names(ruleset)["definite_duplicate"]
    assert result.matched_layer == "L4"
    assert "ID-L4-MATCH" in result.reason_codes


def test_9_the_same_requisition_number_on_two_ats_systems_is_two_jobs(ruleset):
    greenhouse = IdentityRecord(
        record_kind="opportunity", record_ref="opportunities:990",
        company="Acme AI", title="AI Quality Engineer",
        normalized_company="acme ai", normalized_title="ai quality engineer",
        ats=AtsRequisition(system="greenhouse", tenant="acme",
                           requisition_id="12345"))
    workday = IdentityRecord(
        record_kind="candidate", record_ref="candidate:990",
        company="Globex", title="Test Engineer",
        normalized_company="globex", normalized_title="test engineer",
        ats=AtsRequisition(system="workday", tenant="globex",
                           requisition_id="12345"))
    assert greenhouse.l4_key != workday.l4_key
    result = resolve(ruleset, workday, greenhouse)
    assert result.outcome == names(ruleset)["distinct"]


def test_9b_the_same_requisition_number_on_two_tenants_is_two_jobs(ruleset, make):
    acme = make("opportunities:991", url="https://boards.greenhouse.io/acme/jobs/12345",
                company="Acme AI", title="AI Quality Engineer")
    globex = make("candidate:991", url="https://boards.greenhouse.io/globex/jobs/12345",
                  company="Globex", title="AI Quality Engineer")
    assert acme.l4_key == ("greenhouse", "acme", "12345")
    assert globex.l4_key == ("greenhouse", "globex", "12345")
    assert resolve(ruleset, globex, acme).outcome == names(ruleset)["distinct"]


def test_9c_a_bare_requisition_id_is_never_a_key(ruleset):
    assert AtsRequisition(requisition_id="12345").key is None
    assert AtsRequisition(system="greenhouse").key is None
    # A known ATS host whose path carries no requisition yields no key either -
    # (system, tenant, None) would match every other id-less posting there.
    assert requisition_from_url("https://boards.greenhouse.io/acme", ruleset).key is None


# ==========================================================================
# TEST 10 - cross-source: matching an existing opportunity
# ==========================================================================

def test_10_a_linkedin_candidate_matches_an_existing_opportunity(ruleset, make):
    """
    opportunities has no external_id column. The L1 key is derived from the
    posting id the job_url demonstrably carries - reading an id that is present,
    not inferring one that is not.
    """
    opportunity = record_from_opportunity(
        {"id": 20, "company": "Dautom",
         "role": "AI Data Engineer - Vector Database & RAG",
         "job_url": "https://www.linkedin.com/jobs/view/4454261604/",
         "source": "LinkedIn", "discovered_date": "2026-08-19"}, ruleset)
    assert opportunity.l1_key == ("linkedin", "4454261604")

    candidate = make("candidate:4454261604", source="LinkedIn",
                     external_id="linkedin:4454261604",
                     url="https://in.linkedin.com/jobs/view/"
                         "ai-data-engineer-at-dautom-4454261604",
                     company="Dautom",
                     title="AI Data Engineer - Vector Database & RAG",
                     location="India")
    result = resolve(ruleset, candidate, opportunity)
    assert result.outcome == names(ruleset)["definite_duplicate"]
    assert result.matched_record_kind == "opportunity"
    assert result.matched_record_ref == "opportunities:20"
    assert result.suppress_from_review is True


def test_10b_matching_spans_both_tables(ruleset):
    assert set(ruleset.match_scope_tables) == {"scraped_jobs", "opportunities"}
    index = IdentityStore(LIVE_DB, ruleset).build_index()
    counts = index.counts()
    assert counts["scraped_job"] > 0
    assert counts["opportunity"] > 0


def test_10c_a_synthetic_second_source_needs_no_redesign(ruleset, make):
    """
    X7 requires the scheme be demonstrated against a second source even though
    only one real source ships. A second portal is a builder call, not a change
    to any identity layer.
    """
    linkedin = make("scraped_jobs:78", source="LinkedIn",
                    external_id="linkedin:4459864135", url=LIVE_DETAIL_URL,
                    company="Elastic", title="AI QA and Evaluation Engineer",
                    location="Bengaluru, Karnataka, India")
    careers_site = make("candidate:careers-elastic", source="Elastic Careers",
                        external_id="elastic-careers:REQ-9981",
                        url="https://boards.greenhouse.io/elastic/jobs/7788",
                        company="Elastic", title="AI QA and Evaluation Engineer",
                        location="Bengaluru, Karnataka, India")
    result = resolve(ruleset, careers_site, linkedin)
    # Different portal, different URL family, no shared requisition: the only
    # evidence is L3, so the answer is "probably, ask a human" - not a merge.
    assert result.outcome == names(ruleset)["probable_duplicate"]
    assert result.matched_layer == "L3"
    assert result.requires_human_review is True


def test_10d_an_applied_opportunity_is_in_scope_and_its_status_is_not_read(ruleset, make):
    """
    P0_SPEC 8.4 puts applied, rejected and archived rows in identity scope -
    that is the whole point. Status is not an input: an opportunity record
    carries no status field at all, so no match can depend on one.
    """
    opportunity = record_from_opportunity(
        {"id": 19, "company": "Welldoc", "role": "AI Model Quality Engineer",
         "job_url": "https://www.linkedin.com/jobs/view/4435124351/",
         "source": "LinkedIn", "discovered_date": "2026-08-14"}, ruleset)
    assert "status" not in opportunity.as_dict()
    candidate = make("candidate:welldoc", source="LinkedIn",
                     external_id="linkedin:4435124351",
                     url="https://in.linkedin.com/jobs/view/ai-model-qe-4435124351",
                     company="Welldoc", title="AI Model Quality Engineer")
    assert resolve(ruleset, candidate, opportunity).outcome == \
        names(ruleset)["definite_duplicate"]


# ==========================================================================
# TEST 11-13 - identity is not application outcome
# ==========================================================================

def test_11_deduplication_changes_no_application_status(ruleset, tmp_path):
    """
    Run a full resolution over every record the live database holds, against a
    copy, and assert the copy is byte-identical afterwards. Nothing is deleted,
    merged, re-statused or "cleaned up".
    """
    copy_path = tmp_path / "identity-readonly-check.db"
    source = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
    try:
        destination = sqlite3.connect(str(copy_path))
        try:
            source.backup(destination)
        finally:
            destination.close()
    finally:
        source.close()

    def snapshot():
        with sqlite3.connect(f"file:{copy_path}?mode=ro", uri=True) as conn:
            conn.row_factory = sqlite3.Row
            return json.dumps(
                {table: [dict(r) for r in conn.execute(
                    f"SELECT * FROM {table} ORDER BY id")]
                 for table in ("scraped_jobs", "opportunities")},
                sort_keys=True, default=str)

    before = snapshot()
    store = IdentityStore(copy_path, ruleset)
    index = store.build_index()
    resolver = IdentityResolver(index, ruleset)
    resolutions = [resolver.resolve(record) for record in index.records]
    assert len(resolutions) == len(index.records)
    assert snapshot() == before


def test_11b_the_identity_store_connection_physically_rejects_writes(ruleset):
    """
    Read-only is enforced by SQLite, not by convention. A later edit cannot
    quietly turn this package into something that repairs history.
    """
    store = IdentityStore(LIVE_DB, ruleset)
    conn = store._connect()
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("UPDATE opportunities SET status = 'Rejected' WHERE id = 1")
    finally:
        conn.close()


def test_11c_the_identity_package_contains_no_write_statement():
    text = identity_code().upper()
    for token in ("INSERT INTO", "UPDATE ", "DELETE FROM", "DROP ", "REPLACE INTO",
                  "ALTER TABLE", "CREATE TABLE", "CREATE INDEX", "PRAGMA USER_VERSION"):
        assert token not in text, f"identity attempts a write or schema change: {token}"


def test_12_deduplication_changes_no_policy_verdict(ruleset, make):
    """
    A resolution carries no verdict field, so there is no field through which a
    verdict could travel - and the gate result object is not an input to
    anything here.
    """
    gate = HardEligibilityGate()
    verdict = gate.evaluate_posting({
        "candidate_id": "linkedin:4459864135",
        "source_ref": LIVE_DETAIL_URL,
        "source_fetched_at": "2026-08-31T07:36:39+00:00",
        "work_mode_text": "Remote-friendly",
    })
    before = json.dumps(verdict.as_dict(), sort_keys=True, default=str)

    candidate = make("candidate:verdict", source="LinkedIn",
                     external_id="linkedin:4459864135", url=LIVE_SEARCH_URL,
                     company="Elastic", title="AI QA and Evaluation Engineer",
                     location="Bengaluru")
    resolution = resolve(ruleset, candidate,
                         make("scraped_jobs:78", source="LinkedIn",
                              external_id="linkedin:4459864135",
                              url=LIVE_DETAIL_URL, company="Elastic",
                              title="AI QA and Evaluation Engineer",
                              location="Bengaluru"))
    assert resolution.outcome == names(ruleset)["definite_duplicate"]
    assert json.dumps(verdict.as_dict(), sort_keys=True, default=str) == before

    payload = json.dumps(resolution.as_dict(), default=str)
    for forbidden in ('"verdict"', '"match_score"', '"status"', '"recommendation"',
                      '"classification"', '"requires_human_review": "PASS"'):
        assert forbidden not in payload, \
            f"identity resolution carries policy or application state: {forbidden}"


def test_13_deduplication_never_turns_unknown_into_pass(ruleset, make):
    """
    The three live records were all UNKNOWN. Identity resolution has no verdict
    vocabulary at all - PASS, FAIL and UNKNOWN appear nowhere in the package -
    so there is no code path by which it could promote one.
    """
    code = identity_code()
    for token in ("PASS", "FAIL", "UNKNOWN"):
        assert re.search(rf"\b{token}\b", code) is None, \
            f"identity handles a gate verdict value: {token}"
    assert "resume_config" not in code
    assert "jobops-policy" not in code
    # The artifact may NAME the policy artifact in order to disclaim it; it
    # must not be loadable from here. No code reads it.
    assert "jobops-policy" in IDENTITY_ARTIFACT.read_text()
    assert "not_authority_for" in IDENTITY_ARTIFACT.read_text()


def test_13b_identity_holds_no_policy(ruleset):
    code = identity_code()
    for token in ("2000000", "20 LPA", "min_salary", "REMOTE", "HYBRID", "ONSITE",
                  "match_score", "company_type", "annual_min", "reason_code_verdict"):
        assert token not in code, f"policy leaked into identity: {token}"


# ==========================================================================
# TEST 14-16 - D1: an empty detail response cannot erase search evidence
# ==========================================================================

def test_14_a_null_detail_date_does_not_erase_the_search_date():
    """
    CASE A, and the exact loss the first real run suffered: the search results
    stated 2026-08-27 / 2026-08-28 / 2026-08-28 and the detail endpoint stated
    null, so three rows were persisted with posted_date NULL.
    """
    merged = merge_source_records([
        SourceRecord("search", {"date": "2026-08-28"}, "2026-08-31T07:36:39+00:00"),
        SourceRecord("detail", {"date": None}, "2026-08-31T07:36:50+00:00"),
    ])
    assert merged.values["date"] == "2026-08-28"
    assert merged.field_provenance["date"]["value_from"] == "search"
    assert merged.field_provenance["date"]["erasure_prevented"] is True
    assert [c["field"] for c in merged.conflicts] == ["date"]


def test_14b_the_real_live_payloads_would_now_retain_their_dates():
    """Replayed from the retained raw payloads of the first live run."""
    for posting_id, date in (("4459864135", "2026-08-27"),
                             ("4460144522", "2026-08-28"),
                             ("4458935431", "2026-08-28")):
        merged = merge_source_records([
            SourceRecord("search", {"id": posting_id, "date": date,
                                    "url": f"https://in.linkedin.com/jobs/view/"
                                           f"slug-{posting_id}"}),
            SourceRecord("detail", {"id": posting_id, "date": None,
                                    "url": f"https://www.linkedin.com/jobs/view/"
                                           f"{posting_id}",
                                    "description": "..."}),
        ])
        assert merged.values["date"] == date


def test_15_a_detail_date_fills_in_where_the_search_stated_none():
    """CASE B: enrichment is exactly what the detail call is for."""
    merged = merge_source_records([
        SourceRecord("search", {"date": None}),
        SourceRecord("detail", {"date": "2026-08-28"}),
    ])
    assert merged.values["date"] == "2026-08-28"
    assert merged.field_provenance["date"]["value_from"] == "detail"


def test_16_field_level_precedence_is_not_a_blanket_never_overwrite():
    """
    CASE C. Under the default rule a detail response that supplies a better
    value replaces the search value; under the url rule it does not, because
    both URLs are legitimate and arrival order is not authority.
    """
    merged = merge_source_records([
        SourceRecord("search", {"description": "AI Quality Engineer at Acme",
                                "url": "https://in.linkedin.com/jobs/view/slug-1"}),
        SourceRecord("detail", {"description": "Full job description, 4000 chars",
                                "url": "https://www.linkedin.com/jobs/view/1"}),
    ])
    assert merged.values["description"] == "Full job description, 4000 chars"
    assert merged.field_provenance["description"]["rule"] == ENRICH
    assert merged.values["url"] == "https://in.linkedin.com/jobs/view/slug-1"
    assert merged.field_provenance["url"]["rule"] == FIRST_OBSERVATION
    # The displaced URL is retained, not discarded.
    observed = [o["value"] for o in merged.field_provenance["url"]["observations"]]
    assert "https://www.linkedin.com/jobs/view/1" in observed


def test_16b_a_blank_string_is_not_a_value_and_erases_nothing():
    merged = merge_source_records([
        SourceRecord("search", {"location": "Bengaluru, Karnataka, India"}),
        SourceRecord("detail", {"location": "   "}),
    ])
    assert merged.values["location"] == "Bengaluru, Karnataka, India"


def test_16c_the_three_state_discipline_survives_the_merge():
    """
    P0_SPEC 4.4: an absent key means "this run did not capture it"; a null
    means "the source stated none". The merge must not conflate them.
    """
    merged = merge_source_records([
        SourceRecord("search", {"date": None}),
        SourceRecord("detail", {"description": "body"}),
    ])
    assert "date" in merged.values and merged.values["date"] is None
    assert "seniority" not in merged.values
    assert merged.field_provenance["date"]["value_from"] is None


def test_16d_a_missing_detail_record_leaves_the_search_record_intact():
    merged = merge_source_records([
        SourceRecord("search", {"date": "2026-08-28", "url": "https://x/1"})])
    assert merged.values == {"date": "2026-08-28", "url": "https://x/1"}
    assert merged.conflicts == []


def test_16e_the_pipeline_uses_the_evidence_preserving_merge():
    """The defective spread is gone from the pipeline, not merely shadowed."""
    source = (REPO_ROOT / "ingestion" / "pipeline.py").read_text()
    assert "{**posting, **(detail or {})}" not in source
    assert "merge_source_records" in source


# ==========================================================================
# TEST 17 / 18 - uncertainty stays uncertainty; resolution is deterministic
# ==========================================================================

def test_17_identity_uncertainty_is_never_collapsed(ruleset, make):
    uncertain = ruleset.outcome("identity_uncertain")
    probable = ruleset.outcome("probable_duplicate")
    for spec in (uncertain, probable):
        assert spec["identity_asserted"] is False
        assert spec["identity_uncertain"] is True
        assert spec["requires_human_review"] is True
        assert spec["suppress_from_review"] is False

    held = make("scraped_jobs:904", source="LinkedIn",
                url="https://careers.acme.example/postings/aaa",
                company="Acme AI", title="AI Quality Engineer", location=None)
    candidate = make("candidate:uncertain", source="Careers Site",
                     url="https://acme.example.org/roles/bbb",
                     company="Acme AI", title="AI Quality Engineer",
                     location="Bengaluru")
    result = resolve(ruleset, candidate, held)
    assert result.outcome == names(ruleset)["identity_uncertain"]
    assert result.matched_record_ref == "scraped_jobs:904"   # linked, not merged
    assert result.requires_human_review is True


def test_17b_conflicting_high_confidence_evidence_downgrades_to_uncertain(ruleset, make):
    """
    Conflicting identity evidence must not silently merge. Same Workday tenant,
    same posting, two different requisition ids: the system says it does not
    know rather than asserting the L2 match.
    """
    held = make("opportunities:992", source="Acme Careers",
                url="https://acme.wd1.myworkdayjobs.com/Careers/job/India/"
                    "AI-Quality-Engineer_JR11111",
                company="Acme AI", title="AI Quality Engineer")
    candidate = make("candidate:992", source="Acme Careers",
                     url="https://acme.wd1.myworkdayjobs.com/Careers/job/India/"
                         "AI-Quality-Engineer_JR11111",
                     company="Acme AI", title="AI Quality Engineer")
    # Same URL, so L2 matches; now give the candidate a contradicting L4.
    candidate = IdentityRecord(
        **{**{f.name: getattr(candidate, f.name)
              for f in candidate.__dataclass_fields__.values()},
           "ats": AtsRequisition(system="workday", tenant="acme",
                                 requisition_id="JR99999")})
    result = resolve(ruleset, candidate, held)
    assert result.outcome == names(ruleset)["identity_uncertain"]
    assert "ID-CONFLICT-L4" in result.reason_codes
    assert result.suppress_from_review is False


def test_17c_a_conflict_never_upgrades_an_outcome(ruleset):
    for rule in ruleset.conflict_rules:
        assert rule["reason_code"] in ruleset.reason_code_registry
    assert "Collapsing IDENTITY_UNCERTAIN into a duplicate outcome." in \
        ruleset.raw["prohibited"]


def test_17d_a_stronger_match_is_not_masked_by_a_weaker_uncertain_one(ruleset, make):
    """
    A clean L1 match against one record stays definite even when a different
    record produces a near-match. The near-match is retained and reported, not
    discarded and not allowed to mask established evidence.
    """
    exact = make("scraped_jobs:905", source="LinkedIn",
                 external_id="linkedin:4459864135", url=LIVE_DETAIL_URL,
                 company="Elastic", title="AI QA and Evaluation Engineer",
                 location="Bengaluru")
    near = make("opportunities:906", source="Elastic Careers",
                url="https://boards.greenhouse.io/elastic/jobs/7788",
                company="Elastic", title="AI QA and Evaluation Engineer")
    candidate = make("candidate:both", source="LinkedIn",
                     external_id="linkedin:4459864135", url=LIVE_SEARCH_URL,
                     company="Elastic", title="AI QA and Evaluation Engineer",
                     location="Bengaluru")
    result = resolve(ruleset, candidate, exact, near)
    assert result.outcome == names(ruleset)["definite_duplicate"]
    assert result.matched_record_ref == "scraped_jobs:905"
    assert result.has_uncertain_match is True
    assert {m.record_ref for m in result.matches} == \
        {"scraped_jobs:905", "opportunities:906"}


def test_18_resolution_is_deterministic_across_repeated_runs(ruleset, make):
    held = [
        make("scraped_jobs:78", source="LinkedIn", external_id="linkedin:4459864135",
             url=LIVE_DETAIL_URL, company="Elastic",
             title="AI QA and Evaluation Engineer", location="Bengaluru"),
        make("opportunities:26", source="Monks Careers",
             url="https://www.monks.com/careers/6128657004/testing-lead",
             company="Monks", title="Testing Lead"),
        make("scraped_jobs:900", source="LinkedIn",
             url="https://careers.acme.example/postings/aaa", company="Acme AI",
             title="AI Quality Engineer", location="Bengaluru"),
    ]
    candidate = make("candidate:determinism", source="LinkedIn",
                     external_id="linkedin:4459864135", url=LIVE_SEARCH_URL,
                     company="Acme AI", title="AI Quality Engineer",
                     location="Bengaluru")

    def stripped(resolution):
        payload = copy.deepcopy(resolution.as_dict())
        payload.pop("resolved_at")
        return json.dumps(payload, sort_keys=True, default=str)

    first = stripped(resolve(ruleset, candidate, *held))
    second = stripped(resolve(ruleset, candidate, *held))
    reversed_index = stripped(resolve(ruleset, candidate, *reversed(held)))
    assert first == second == reversed_index


def test_18b_batch_resolution_is_deterministic(ruleset, make):
    batch = [make(f"candidate:{i}", source="LinkedIn",
                  external_id=f"linkedin:44598641{i:02d}",
                  url=f"https://www.linkedin.com/jobs/view/44598641{i:02d}",
                  company="Acme AI", title="AI Quality Engineer",
                  location="Bengaluru") for i in range(4)]
    resolver = IdentityResolver(IdentityIndex(), ruleset)
    first = [(r.outcome, r.matched_layer, r.matched_record_ref)
             for r in resolver.resolve_batch(batch)]
    second = [(r.outcome, r.matched_layer, r.matched_record_ref)
              for r in resolver.resolve_batch(batch)]
    assert first == second


def test_18c_resolve_batch_does_not_modify_the_base_index(ruleset, make):
    index = IdentityIndex()
    resolver = IdentityResolver(index, ruleset)
    resolver.resolve_batch([make("candidate:x", source="LinkedIn",
                                 external_id="linkedin:1", url="https://x/1",
                                 company="A", title="B", location="C")])
    assert len(index) == 0


# ==========================================================================
# Provenance - every decision is explainable
# ==========================================================================

def test_every_resolution_carries_at_least_one_registered_reason_code(ruleset, make):
    registry = ruleset.reason_code_registry
    cases = [
        make("candidate:p1", source="LinkedIn", external_id="linkedin:1",
             url="https://www.linkedin.com/jobs/view/1", company="A",
             title="B", location="C"),
        make("candidate:p2", url="https://jobs.lever.co/Sprinto", company="A",
             title="B"),
        make("candidate:p3", company="A", title="B", location=None),
        make("candidate:p4"),
    ]
    held = make("scraped_jobs:1", source="LinkedIn", external_id="linkedin:1",
                url="https://www.linkedin.com/jobs/view/1", company="A",
                title="B", location="C")
    for candidate in cases:
        result = resolve(ruleset, candidate, held)
        assert result.reason_codes, f"{candidate.record_ref} has no reason code"
        for code in result.reason_codes:
            assert code in registry, f"unregistered reason code {code}"


def test_a_resolution_answers_why_two_postings_were_considered_the_same(ruleset, make):
    held = record_from_opportunity(
        {"id": 20, "company": "Dautom", "role": "AI Data Engineer",
         "job_url": "https://www.linkedin.com/jobs/view/4454261604/",
         "source": "LinkedIn", "discovered_date": "2026-08-19"}, ruleset)
    candidate = make("candidate:why", source="LinkedIn",
                     external_id="linkedin:4454261604",
                     url="https://in.linkedin.com/jobs/view/slug-4454261604",
                     company="Dautom", title="AI Data Engineer",
                     location="India", source_observed_at="2026-09-02T00:00:00+00:00")
    payload = resolve(ruleset, candidate, held).as_dict()

    assert payload["identity_version"] == "jobops-identity@0.1.0"
    assert payload["resolved_at"]
    assert payload["matched_layer"] == "L1"
    assert payload["matched_record_ref"] == "opportunities:20"
    assert payload["matched_record_kind"] == "opportunity"
    assert payload["candidate"]["source"] == "LinkedIn"
    assert payload["candidate"]["source_portal"] == "linkedin"
    assert payload["candidate"]["external_id"] == "4454261604"
    assert payload["candidate"]["source_observed_at"]
    assert payload["candidate"]["url"]["original_source_url"] == \
        "https://in.linkedin.com/jobs/view/slug-4454261604"
    assert payload["candidate"]["url"]["canonical_identity_url"] == \
        "https://linkedin.com/jobs/view/4454261604"

    match = payload["matches"][0]
    assert match["layer"] == "L1"
    assert match["evidence"]["candidate_value"] == ["linkedin", "4454261604"]
    assert match["evidence"]["matched_value"] == ["linkedin", "4454261604"]
    assert match["evidence"]["matched_original_source_url"] == \
        "https://www.linkedin.com/jobs/view/4454261604/"


def test_the_duplicate_flag_is_never_a_bare_boolean(ruleset, make):
    payload = resolve(ruleset, make("candidate:bare")).as_dict()
    assert "duplicate" not in payload
    assert payload["outcome"] == names(ruleset)["distinct"]
    assert payload["reason_codes"] == ["ID-NO-MATCH", "ID-L1-ABSENT",
                                       "ID-URL-ABSENT", "ID-L4-ABSENT",
                                       "ID-L3-NOT-EVALUABLE"]


# ==========================================================================
# The artifact is the authority
# ==========================================================================

def test_the_identity_artifact_is_version_pinned(ruleset):
    from identity.ruleset import IdentityRuleset
    assert ruleset.version == "jobops-identity@0.1.0"
    with pytest.raises(IdentityDriftError):
        IdentityRuleset(IDENTITY_ARTIFACT, expected_version="jobops-identity@9.9.9")


def test_l3_is_not_a_suppression_grade_layer(ruleset):
    """P0_SPEC 8.4 grants suppression at L1/L2/L4 confidence. Not L3."""
    assert ruleset.suppression_grade_layers() == ["L1", "L2", "L4"]
    assert ruleset.layer("L3")["suppression_grade"] is False


def test_an_unregistered_reason_code_is_drift_not_a_new_code(ruleset):
    with pytest.raises(IdentityDriftError):
        ruleset.assert_reason_code("ID-MADE-UP")


def test_the_artifact_declares_every_layer_the_resolver_implements(ruleset):
    assert {layer["id"] for layer in ruleset.layers} == {"L1", "L2", "L3", "L4"}
    for layer in ruleset.layers:
        assert layer["reason_code"] in ruleset.reason_code_registry


def test_no_similarity_scoring_exists_anywhere_in_the_package():
    """
    P0 does not auto-merge on fuzzy evidence (P0_SPEC 8.3), and the way to
    guarantee that is to compute no similarity at all.
    """
    code = identity_code().lower()
    for token in ("difflib", "sequencematcher", "levenshtein", "jaro",
                  "fuzzywuzzy", "rapidfuzz", "ratio(", "similarity", "distance("):
        assert token not in code, f"identity computes a similarity score: {token}"


# ==========================================================================
# Read-only evidence from the first real LinkedIn run
# ==========================================================================

@pytest.mark.parametrize("row_id,external_id", [
    (78, "linkedin:4459864135"),
    (79, "linkedin:4460144522"),
    (80, "linkedin:4458935431"),
])
def test_the_three_live_records_resolve_against_themselves(ruleset, row_id,
                                                           external_id):
    """
    Read-only. Each live row, offered again as a candidate, is recognized as
    the row it already is. Nothing is written, and rows 78-80 are not repaired.
    """
    with sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        row = dict(conn.execute(
            "SELECT * FROM scraped_jobs WHERE id = ?", (row_id,)).fetchone())
    assert row["external_id"] == external_id

    held = record_from_scraped_job(row, ruleset)
    candidate = record_from_candidate(
        ruleset, record_ref=f"candidate:{row_id}", source=row["source"],
        external_id=row["external_id"], url=row["job_url"],
        company=row["company"], title=row["job_title"], location=row["location"])
    result = resolve(ruleset, candidate, held)
    assert result.outcome == names(ruleset)["definite_duplicate"]
    assert result.matched_layer == "L1"


def test_the_live_index_reports_historical_duplicates_without_repairing_them(ruleset):
    """
    Detect, classify, report. Historical repair is a separate, separately
    authorized concern - so this test asserts only that the report can be
    produced, never that the database was changed.
    """
    index = IdentityStore(LIVE_DB, ruleset).build_index()
    resolver = IdentityResolver(index, ruleset)
    outcomes = {}
    for record in index.records:
        outcome = resolver.resolve(record).outcome
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    assert sum(outcomes.values()) == len(index.records)
    assert set(outcomes) <= set(names(ruleset).values())


# ==========================================================================
# D1 end to end - the row the pipeline would now build for the live postings
# ==========================================================================

def test_d1_the_pipeline_builds_a_row_that_keeps_the_search_date():
    """
    Not a unit test of the merge helper: this drives the ingestion pipeline's
    own normalization and row-building path with the exact search/detail pair
    the first live run received, and asserts the CandidateRow it produces
    carries the date the source actually stated.

    No store, no CLI, no network - the pipeline is constructed with store=None
    and dry_run, so nothing is written anywhere.
    """
    from ingestion.pipeline import LinkedInIngestionPipeline, QuerySpec

    pipeline = LinkedInIngestionPipeline(
        store=None, dry_run=True,
        store_root=Path(__file__).resolve().parent.parent / "data" / "ingestion")

    posting = {
        "id": "4459864135",
        "title": "AI QA and Evaluation Engineer",
        "company": "Elastic",
        "location": "Bengaluru, Karnataka, India",
        "date": "2026-08-27",
        "url": LIVE_SEARCH_URL,
    }
    detail = {
        "id": "4459864135",
        "title": "AI QA and Evaluation Engineer",
        "company": "Elastic",
        "location": "Bengaluru, Karnataka, India",
        "date": None,                       # the defect's trigger
        "url": LIVE_DETAIL_URL,
        "description": "Fully remote role. Salary: ₹25 LPA.",
        "seniority": "Not Applicable",
        "employmentType": "Full-time",
    }

    built = pipeline._gate_and_build([{
        "posting": posting,
        "detail": detail,
        "external_id": "linkedin:4459864135",
        "query": QuerySpec(location="India", query="AI Quality Engineer"),
        "search_raw_ref": "raw/search-p1-001.json",
        "search_fetched_at": "2026-08-31T07:36:39+00:00",
        "detail_raw_ref": "raw/detail-4459864135.json",
        "detail_fetched_at": "2026-08-31T07:36:50+00:00",
    }])
    row = built[0]["row"]

    assert row.posted_date == "2026-08-27", \
        "a null detail date erased the search date again"
    assert row.job_url == LIVE_SEARCH_URL
    assert row.description == "Fully remote role. Salary: ₹25 LPA."

    # Both observations survive in provenance, so the detail URL and the empty
    # detail date are still auditable rather than silently gone.
    provenance = built[0]["prepared"]["merge_record"].as_dict()
    date_observations = provenance["field_provenance"]["date"]["observations"]
    assert [o["state"] for o in date_observations] == ["value", "stated_none"]
    url_values = [o["value"]
                  for o in provenance["field_provenance"]["url"]["observations"]]
    assert url_values == [LIVE_SEARCH_URL, LIVE_DETAIL_URL]
    assert {c["field"] for c in provenance["conflicts"]} == {"date", "url"}


def test_d1_the_candidate_ledger_record_carries_field_provenance():
    """A future reviewer can see which observation supplied every stored value."""
    source = (REPO_ROOT / "ingestion" / "pipeline.py").read_text()
    assert '"field_provenance": b["prepared"]["merge_record"].as_dict(),' in source
