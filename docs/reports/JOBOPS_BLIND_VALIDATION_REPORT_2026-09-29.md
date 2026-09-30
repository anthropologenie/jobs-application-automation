# JobOps P2 — Independent Blind Validation of jobops-policy@0.2.1 (2026-09-29)

## Executive result

**BLOCKED: the §35 >20% mismatch stop rule was triggered.** Per-mismatch classification was **not performed**. Nothing in the engine, policy or existing tests was changed.

| Measure | Value |
|---|---|
| Blind cases | 144 (72 tricky positives) + 12 sequences |
| Case passes | 109 |
| Case mismatches | **35** (**24.3%**, threshold 20%) |
| UNDETERMINED | 1 case expectation (B052 lane); 2 sequence expectations (S05 step 2 newness; S07 day-4 `parked_ids`). All three were skipped, not asserted |
| Sequence mismatches | 3 of 12 (S01, S09, S10) |

**How the fixture was made independent.** I authored the v0.2.1 engine and its golden tests, so I could not blind-author this fixture myself (the owner decided this). A **fresh subagent with no memory of the implementation session** wrote the cases. It was given only three documents in `/tmp/jobops_blind`:
- `RULINGS_SHEET_2026-09-29.md` (the P2 rulings sheet, §4–§22 of the command);
- `JOBOPS_V2_OWNER_POLICY_SPEC.md`;
- `OWNER_RULINGS_LOG.md`.

It had no repository access and no network. It froze the fixture before I read any of it. I then did Phase 2: the adapter, execution and this report.

**Headline:** most of the mismatches trace to **two engine behaviours in geography extraction**. They appear to be real-world parsing gaps, not rule disagreements:
1. **21 cases:** a technical use of "hybrid" in a JD (e.g. "hybrid BM25 + dense retrieval") is read as a hybrid work arrangement. It conflicts with the posting's "Remote", and geography drops to UNKNOWN.
2. **7 cases:** common Indian office-day wording ("2 days WFO", "2 office days per week", "5 days work from office") is not parsed. Bengaluru hybrid is UNKNOWN instead of PASS/FAIL.

The remaining 7 are single-cause items (see "Suspected causes"). These are the first observed patterns and suspected causes, **not formal classifications**.

## Frozen-fixture integrity

| Check | Result |
|---|---|
| `blind_cases.json` SHA-256 | `44de6af6d8b9bb505044d0b6b871e24cf88a19262bfb90b2b5cf2f6aecdf331a` |
| Hash verified independently (`sha256sum -c`) | Yes, before copying |
| Copied to `tests/fixtures/policy_v02_blind_cases.json` and `.sha256` | Byte-identical (`cmp`) |
| Hash asserted by the test | Yes, `test_frozen_fixture_hash` |
| Fixture frozen before implementation inspection | **YES** (frozen 16:37:01 UTC by the authoring agent; first read by the validating agent afterwards) |
| Fixture modified after engine inspection | **NO** |

## Coverage

A case can count in several categories (from its `tests` field).

| Category | Cases | Pass | Mismatch | UNDETERMINED |
|---|---|---|---|---|
| Geography | 32 | 24 | 8 | 0 |
| Compensation | 23 | 15 | 8 | 0 |
| CTC | 11 | 6 | 4 | 1 |
| Unspecified salary basis | 1 | 0 | 1 | 0 |
| Monthly | 2 | 2 | 0 | 0 |
| Foreign / FX | 7 | 4 | 3 | 0 |
| Indian salary parsing | 5 | 4 | 1 | 0 |
| Employment | 16 | 10 | 6 | 0 |
| Employer | 11 | 8 | 3 | 0 |
| Language | 7 | 6 | 1 | 0 |
| Experience | 7 | 6 | 1 | 0 |
| Relevance | 13 | 10 | 3 | 0 |
| Tier 1 | 8 | 7 | 1 | 0 |
| Lanes | 20 | 18 | 2 | 0 |
| Other | 7 | 6 | 1 | 0 |

Tricky positives mismatched: 21 of 72.

Many mismatches are **collateral**: the case targets one dimension (e.g. B036 targets exact ₹18L), but it fails on geography because its JD template contains the "hybrid BM25" bullet.

## UNDETERMINED cases

| ID | Missing determination | Smallest yes/no question |
|---|---|---|
| B052 (CTC ₹24 LPA) | lane | Does CTC_BASIS_UNVERIFIED on its own (no UNKNOWN dimension, no other review flag, STRONG relevance) route a posting to REVIEW instead of SHORTLIST? |
| S05 step 2 | newness | When a higher-precedence ATS observation contradicts an earlier board observation on employment type, is newness UPDATED rather than SEEN_BEFORE? |
| S07 step 46 | parked_ids on 2026-10-02 | Is the day an item first overflows (2026-09-29) counted as the first of its 3 carry days, so that a non-STRONG item is parked on 2026-10-02 rather than 2026-10-03? |

## Mismatch table

Facts only. Classification was not performed (§35). "Suspected pattern" is an observation from reading the evidence, not a classification.

| Case | Expected → actual | Suspected pattern |
|---|---|---|
| B004 | geography FAIL → UNKNOWN; lane EXCLUDED → REVIEW | A: JD "hybrid BM25" conflicts with "Remote (US only)" |
| B020 | geography FAIL → UNKNOWN; lane EXCLUDED → REVIEW | A: JD "hybrid BM25" conflicts with "Work from office" (Pune) |
| B036, B040, B044, B048, B056, B060, B064, B068, B072, B076, B080, B088, B092, B096, B100, B106, B117, B118, B131 | geography PASS → UNKNOWN (rule GEO-R19, mode CONFLICTING); lane SHORTLIST/REVIEW → REVIEW where asserted | A: shared JD bullet "…vector database (Milvus) and hybrid BM25 + dense retrieval" |
| B012, B027, B028, B095 | geography PASS → UNKNOWN (GEO-R08, days unspecified) | B: "Hybrid (2 days WFO)", "Hybrid: 2 days WFO" |
| B030 | geography PASS → UNKNOWN (GEO-R08) | B: "Hybrid (2 office days per week)" |
| B144 | geography PASS → UNKNOWN (GEO-R08) | B: "Hybrid (3 days WFO)" |
| B015 | geography FAIL → UNKNOWN (GEO-R08); lane EXCLUDED → REVIEW | B: "Hybrid – 5 days work from office" |
| B009 | geography UNKNOWN → FAIL; lane REVIEW → EXCLUDED | C1: the adapter joins listing and work mode ("Berlin, Germany — Remote") into one statement, so the foreign listing becomes a stated remote region |
| B054 | missing CTC_BASIS_UNVERIFIED (has COMPENSATION_REVIEW) | C2: OI-049 (resolved YES in the P2 sheet) is not implemented in 0.2.1 (COMP-C03 unchanged) |
| B055 | missing CTC_BASIS_UNVERIFIED | C2: same as B054 |
| B058 | IN_TARGET expected, CTC_BASIS_UNVERIFIED present; lane SHORTLIST → REVIEW | C3: "Base: ₹25 LPA \| CTC: ₹31 LPA": pipe-separated base and CTC on one line are parsed as one CTC clause, so base does not win |
| B082 | employment UNKNOWN → FAIL; missing LONG_TERM_DIRECT_CONTRACT | C4: "12-month fixed-term contract, employed directly by …" does not match the direct-contract lexicon |
| B085 | employment UNKNOWN → PASS; missing EOR | C5: EOR wording sits in the employment field; relationship signals are read only from the JD body |
| B086 | employment FAIL → UNKNOWN (EMPLOYMENT_UNSTATED); lane EXCLUDED → REVIEW | C5: "Independent contractor" in the employment field is not read as a relationship signal |

| Sequence | Mismatches | Suspected pattern |
|---|---|---|
| S01 | steps 1–2 geography PASS → UNKNOWN, lane SHORTLIST → REVIEW; step 2 newness SEEN_BEFORE → UPDATED; step 3 newness UPDATED → SEEN_BEFORE | A for geography. Newness: step 2 (search-only re-sighting) flagged a material change, probably from differing listing strings; step 3 (ATS contradicting the board) is cross-source, which the engine treats as a conflict, not an update. Relates to the S05 UNDETERMINED question |
| S09 | steps 1–2 lane SHORTLIST → REVIEW | Not yet diagnosed (stop rule) |
| S10 | step 2 newness SEEN_BEFORE → UPDATED | Search-only re-sighting marked UPDATED. Probably a changed listing string (location with work mode) between the two sightings; possibly the adapter's location/work-mode join |

The F4 property itself held in S01 and S10. Compensation and relevance did not weaken after the search-only re-sighting.

## Classification counts

**Not performed.** §35 stops classification above 20%.

| Class | Count |
|---|---|
| ENGINE_BUG | not classified |
| CASE_ERROR | not classified |
| SPEC_AMBIGUITY | not classified |
| ADAPTER_LIMIT | not classified |

## Suspected common causes

1. **Pattern A (21 cases, plus S01/S09 lanes):** the work-arrangement lexicon matches any "hybrid" not immediately followed by a small list of technical nouns. "hybrid BM25", "hybrid dense/sparse" and similar technical phrases in a JD are read as a hybrid arrangement. That conflicts with the listing's REMOTE, so geography becomes UNKNOWN (never FAIL, so recall is preserved, but clean SHORTLIST candidates are sent to REVIEW).
   - Posting type affected: any strong RAG/retrieval JD that says "hybrid" in a technical sense.
   - Suspected area: policy lexicon `lexicon.hybrid` and the statement-level mode resolution.
2. **Pattern B (7 cases):** the office-day patterns require "N days per/a week" or "N days in/at/from office". Real Indian postings write "2 days WFO", "2 office days per week" and "5 days work from office".
   - Effect: Bengaluru hybrid becomes UNKNOWN, including 4–5-day roles that should FAIL.
   - Suspected area: `lexicon.office_days`.
3. **C1 (1 case):** likely an adapter mapping artefact, where listing and work mode were joined into one location string. This would need confirmation during classification.
4. **C2 (2 cases):** OI-049 postdates 0.2.1.
5. **C3–C5 (4 cases):** individual parsing gaps:
   - base/CTC on one pipe-separated line;
   - "employed directly" not recognised as a direct contract;
   - relationship signals (EOR, contractor) read only from the JD body and not from the employment field.

## Owner questions

No SPEC_AMBIGUITY classification was performed. The only open questions are the three UNDETERMINED items above, as written by the blind author.

## Test and suite results (scratch copies, network blocked process-wide)

| Suite | Total | Passed | Failed | xfail | Skipped |
|---|---|---|---|---|---|
| Blind (`tests/test_policy_v02_blind.py`: 2 integrity + 144 cases + 12 sequences) | 158 | 120 | **38** | 0 | 0 |
| Existing suite (everything except the blind module) | 889 | 889 | 0 | 0 | 0 |
| Full suite (both) | 1047 | 1009 | 38 | 0 | 0 |

**No strict xfails were created.** §36 allows them only when mismatches are ≤ 20%, and without classification an xfail reason cannot be written. The blind module is therefore **red by design** until a fix or classification pass. It asserts only fixture values; `KNOWN_MISMATCHES` is empty.

- The blind-only run used a scratch copy **without** any DB file.
- The full-suite run used a scratch copy with a byte copy of the DB file, because the pre-existing P0 tests genuinely require it. The live file was never opened.

## Adapter (fixed before execution; documented in the test module)

The mapping is listed in the module docstring of `tests/test_policy_v02_blind.py`. Two choices matter for interpreting the results:
- **Work mode and listing are joined into `raw_location`.** The engine has no separate work-mode field. This is the suspected cause of B009, and may contribute to the S01/S10 newness results.
- **Blind `employment_type` and `employer_type` are projections of the engine's three dimensions.** `employment_relationship` is folded into `employment_type`, and into `employer_type` only when it FAILs on placement or payroll.

## Safety check

| Check | Result |
|---|---|
| Network used | NO (sockets blocked; no HTTP/DNS) |
| Live DB opened | NO (mtime `1788161814` unchanged) |
| `data/n8n` opened | NO |
| `.env` opened | NO |
| Secrets accessed | NO |
| Engine modified | NO |
| Policy modified | NO (`0.2.0` `65f74aec…`, `0.2.1` `af19a3fd…` unchanged) |
| Existing tests modified | NO |
| Git index modified | NO (still only `D data/jobs-tracker.db`) |
| Commits created | NO |
| C1 started | NO |
| LinkedIn ingestion rewired | NO |
| Scheduler started | NO |
| ATS adapters created | NO |

**Files created (4):** `tests/fixtures/policy_v02_blind_cases.json`, `tests/fixtures/policy_v02_blind_cases.sha256`, `tests/test_policy_v02_blind.py`, and this report. Scratch artefacts are under `/tmp/jobops_blind/`.
