# JobOps — Phase B Follow-up (P1a) Report — 2026-09-29

**Result: PASS.** Every mandatory P1a acceptance criterion is met (details below). Phase C was not started.

## Legacy-path verdict

**LinkedIn ingestion → old v0.1 gate.**
- The only LinkedIn entry point (`python3 -m ingestion.run_linkedin_ingestion`) runs `ingestion.pipeline.LinkedInIngestionPipeline`. That calls `policy.gate.HardEligibilityGate` (v0.1) and writes the legacy `data/jobs-tracker.db` (`scraped_jobs`) plus the JSONL ledger.
- The review queue, decisions and timing (the CLIs and `api-server.py` `/api/review-queue`, `/api/review-decision`) read that v0.1 ledger through `review/ledger.py`, where the latest observation is taken as current.
- The v0.2 chain (`evaluation/` → `relevance/` → lanes → `store/`) is tested but reachable only from tests; no entry point uses it.
- The repository as a whole is therefore **mixed**, and **the original F4 defect is still live on the v0.1 path.**

## Legacy path (summary)

```
run_linkedin_ingestion.main → LinkedInIngestionPipeline.run
  → LinkedInSearchCLI (bun subprocess) → RawSourceStore
  → _gate_and_build → merge/extraction → HardEligibilityGate.evaluate_posting (v0.1)
  → CandidateStore.insert_candidates (data/jobs-tracker.db: scraped_jobs) → RunLedger (JSONL)
review.ReviewQueue.build → CandidateLedgerStore (current = observations[-1]) → identity (read-only) → v0.1 lanes
v2 (tests only): EvaluationService.ingest → extract → identity_resolution → store → selection (F4 fix) → engine → queue/digest
```

The full trace, including entry points, databases written, test coverage and the Phase C replacement plan, is in `docs/reports/JOBOPS_LEGACY_PATH_TRACE_2026-09-29.md`. The Phase C plan is documented only, not implemented.

## Rulings

- **Appended:** `OWNER_RULINGS_LOG.md` **Addendum B, OR-31 … OR-61** (31 entries). Each entry has the date, OI ids, RULING, BASIS and SUPERSEDES.

| Ruling | OI(s) | Answer |
|---|---|---|
| OR-31 | OI-025 | YES |
| OR-32 | OI-027 | YES |
| OR-33 | OI-036 | YES |
| OR-34 | OI-037 | YES |
| OR-35 | OI-038 | YES |
| OR-36 | OI-039 | NO → consistent CTC labels |
| OR-37 | OI-040 | YES, 14 days |
| OR-38 | OI-041 | YES |
| OR-39 | OI-042 | YES |
| OR-40 | OI-043 | YES |
| OR-41 | OI-044 | YES |
| OR-42 | OI-045 | YES |
| OR-43 | OI-046 | YES, grouped review card |
| OR-44 | OI-047 | NO |
| OR-45 | OI-048 | YES |
| OR-46 | OI-013 | Bengaluru onsite FAIL |
| OR-47 | OI-006, OI-008 | Floor/target ranges |
| OR-48 | OI-007 | CTC handling |
| OR-49 | OI-011, OI-012 | India listing; hub vs residence |
| OR-50 | OI-029 | EMEA FAIL / APAC UNKNOWN / work authorization |
| OR-51 | OI-014, OI-023 | Informational timezone/language; 0.95 |
| OR-52 | OI-020, OI-021, OI-022, OI-026 | Employment/employer decisions |
| OR-53 | OI-016 | REASONABLE experience |
| OR-54 | OI-015 | No-JD lanes |
| OR-55 | OI-017, OI-018 | Newness |
| OR-56 | OI-019 | Source precedence, conflict, identity |
| OR-57 | OI-034 | Legacy rows archived |
| OR-58 | OI-024 | Deferred |
| OR-59 | OI-031 | Permitted, not implemented |
| OR-60 | OI-032 | Quarantine, not a separate repo |
| OR-61 | OI-035 | Monthly × 12 |

OI-001 … OI-005, 009, 010, 028, 030 and 033 remain settled by OR-26 … OR-30.

- **Superseded (recorded, not rewritten):**
  - OR-15's "Bengaluru onsite → UNKNOWN";
  - OR-18's "₹18–25L → UNKNOWN" example;
  - the Phase B "exactly ₹18L → PASS, —" row;
  - OQ-02 for INR monthly figures;
  - the 2026-09-28 preferences;
  - the Company Radar Phase 1 constraint as a JobOps blocker;
  - 0.2.0's CTC flag sets, unlimited FX age and ungrouped review cap (via 0.2.1; 0.2.0 kept for replay).
- **Open items:** `docs/architecture/JOBOPS_V2_OPEN_ITEMS.md` "P1a status" now lists OI-001 … OI-048 as resolved, each with its OR number.

## Rulings-log preservation

A pre-P1a copy was taken before editing. Diffs after editing:

| Comparison | Result |
|---|---|
| vs the pre-P1a copy | The first 743 lines and every byte are identical. **Addendum B is a pure append.** |
| vs the pre-Phase-B copy | Only insertions (0 removed lines): the five authorized OR-26 … OR-30 RULING fills (hunks `676a677,680`, `686a691,696`, `695a706,709`, `704a719,722`, `714a733,736`) and the appended Addendum B (`721a744,1139`). |
| vs the original pre-Phase-A log | Its 367 lines are a byte-identical prefix. |

- **Addendum A index table:** not changed; it still shows OR-26 … OR-30 as OPEN (OI-047 = NO, stated in Addendum B).
- **No reordering and no whitespace normalization.** The byte-level comparisons above confirm this.

## Policy hashes

| Artifact | SHA-256 |
|---|---|
| v0.1.0 | `afe05e5a31777410668180a2d50a06da7cfa21736159946273060be6bf1c051f` |
| v0.2.0 before P1a | `65f74aec883d475989ea0594fac070f547c96a697bc1f7f4b46cf8e0d5dd567a` |
| v0.2.0 after P1a | `65f74aec883d475989ea0594fac070f547c96a697bc1f7f4b46cf8e0d5dd567a` |
| v0.2.1 | `af19a3fd998e945cba19ce68f0e36f2eba4156e8bfd5255ac4ea7dacf7f5ea7d` |

**The v0.2.0 hashes match.** 0.2.1 records both the v0.1.0 and v0.2.0 hashes, and a test asserts them.

## Policy default

**v0.2.1 activated** (`evaluation/policy_loader.DEFAULT_VERSION`).
- **Why:** the full scratch suite, including every 0.2.1 acceptance test, passed with 0.2.0 still the default (888 passed). The default was switched only then, and the suite was re-run (889 passed).
- **Replay:** 0.2.0 stays loadable via `load_policy_version("jobops-policy@0.2.0")`, and the golden fixture runs every case under both versions.
- **Why a code change is still 0.2.0-safe:** every behaviour change is gated by 0.2.1 policy data (parameters, lexicon, rules, queue config). A 0.2.0 replay therefore behaves exactly as before; the golden `@0.2.0` cases confirm this.

## Behaviour fixes

- **CTC (OI-039):**
  - 0.2.1 adds COMP-C06: a point ₹18L to below ₹24L → PASS + BELOW_TARGET + CTC_BASIS_UNVERIFIED.
  - COMP-C02 (range below ₹24L) → PASS + BELOW_TARGET + CTC_BASIS_UNVERIFIED.
  - A point at ₹24L+ → CTC_BASIS_UNVERIFIED only.
  - Below the floor → FAIL; straddle → UNKNOWN + CTC_RANGE_STRADDLES_FLOOR; base + CTC → base wins; no haircut.
  - Tests cover ₹17 / 18 / 20 / 23 / 24 / 18–22 / 24–30 / 15–20 CTC and base + CTC.
- **FX (OI-040):**
  - An injectable `EvaluationService.clock`; age measured against the evaluation date.
  - 13 and 14 days → usable; 15 and 51 days → UNKNOWN + FX_STALE (never FAIL). INR is unaffected.
  - The digest warns at ages above 7 and up to 14 days.
  - The evaluation hash keys on usable/stale, not on the daily age.
  - 0.2.0 keeps no age limit.
- **No-JD senior Tier 1 (OI-044):** Staff, Principal and Architect Tier 1 titles with no JD → REVIEW via LANE-R03, which precedes seniority parking. Verified.
- **Grouped identity review (OI-046):**
  - Under 0.2.1, `evaluation/queue.py` groups IDENTITY_UNCERTAIN requisitions linked by a PROBABLE_DUPLICATE identity link into one unit: `group_id = grp_<lowest member>`, with member ids and member details.
  - The unit uses one cap slot and is ordered by its best member.
  - Tests confirm: 10 units surfaced; 11 units = 12 requisitions all listed; both members retain separate requisitions, observations and evaluations, both flagged; deterministic; the digest shows the group.
  - 0.2.0 does not group.
- **Corrections found while verifying against the rulings sheet** (implemented in 0.2.1 only; 0.2.0 unchanged):
  1. `24,00,000 per annum` (Indian digit grouping with no currency symbol) was not recognised as INR. It was UNKNOWN in 0.2.0 and is PASS in 0.2.1 (G168).
  2. `₹24L` (unit letter attached to the figure) was not parsed. It was UNKNOWN in 0.2.0 and is PASS in 0.2.1 (G170), via a policy-declared number token.
  3. "Authorized to work in the country where this job is posted" (no country named) did not use the listing country. With a Toronto listing it was UNKNOWN in 0.2.0 and is FAIL in 0.2.1 (G175); an India listing stays PASS.
- **OI-036 … OI-045 verification:** all behaved as ruled with no change needed. Explicit tests: `test_oi036_*`, `test_oi037_*`, `test_oi038_*`, `test_oi041_*` (×2), `test_oi042_*`, `test_oi043_*` (0–2 / 1–2 / 2–3), `test_oi045_*` (required / mandatory / knowledge of / -speaking / plus), plus the golden cases G035, G137, G141, G171, G176–G177, G181–G182, G186–G187.
- **Tier 1 list check:** the 20 titles are identical across `policy/jobops-policy-0.2.0.json`, `0.2.1.json`, the Phase A draft `title_families` and OR-12. `JOBOPS_V2_OWNER_POLICY_SPEC.md` does not enumerate the list; §5 points to the draft as its source. That is a reference, not a disagreement, so no BLOCKED question was raised.

## Relevance distribution tool

- **Path:** `tools/relevance_distribution.py` (text or `--json`; `--policy` selects a version).
- **Tests:** `tests/test_relevance_distribution_tool.py`, 2 tests passed. They use three synthetic JDs plus one empty-body file (STRONG / MODERATE / WEAK / NOT_ASSESSED), check verbatim spans and determinism, and confirm the policy files are byte-unchanged after runs.
- **Thresholds unchanged:** strong 3 terms / 2 clusters; moderate 2. They are identical in 0.2.0 and 0.2.1, and a test asserts this.

## Tests (scratch copy, outbound network blocked process-wide)

| Scope | Total | Passed | Failed | Skipped / blocked |
|---|---|---|---|---|
| Full suite | 889 | 889 | 0 | 0 |
| New or modified by P1a (`test_p1a_policy_021.py` 50, `test_policy_v02_golden.py` 369, `test_v02_guardrails.py` 7, `test_v02_f4_replay.py` 7, `test_v02_relevance.py` 22) | 455 | 455 | 0 | 0 |
| Relevance distribution tool | 2 | 2 | 0 | 0 |

- **Golden fixture:** 184 cases, each run under 0.2.0 and 0.2.1, plus a shape test = 369.
- **The 363 pre-existing P0 tests** are unmodified and passing.
- **Two Phase B test edits, neither weakening:**
  1. The guardrail test now asserts the new default (0.2.1) and additionally that 0.2.0 remains loadable.
  2. One replay test looked up "the default policy's evaluation" by a hard-coded version string; it now uses the service's policy version, with the same assertion.

## New OIs

- **OI-049:** YES/NO — Should a CTC-only range that starts at or above ₹18L and reaches ₹24L or more (e.g. ₹18–25L CTC) carry CTC_BASIS_UNVERIFIED in addition to COMPENSATION_REVIEW?
  - **Reason:** OR-36 covers CTC points and CTC ranges wholly below or wholly at or above ₹24L, but not this spanning case.
  - **Implemented meanwhile:** COMPENSATION_REVIEW only (unchanged). The lane is REVIEW either way.

## Git

`git status --short` (exact):

```
 M .gitignore
 M api-server.py
D  data/jobs-tracker.db
 M docs/INDEX.md
?? JOBOPS_SCALING_CAPABILITY_INVENTORY.md
?? JOBOPS_SCALING_EXECUTION_PLAN.md
?? OWNER_RULINGS_LOG.md
?? P0_EXIT_REVIEW.md
?? P0_IMPLEMENTATION_SPEC.md
?? _quarantine/
?? company/
?? data/ingestion/
?? digest/
?? docs/P0_10_TIME_INSTRUMENTATION.md
?? docs/architecture/
?? docs/reports/JOBOPS_ACTIVATION_AUDIT_2026-09-29.md
?? docs/reports/JOBOPS_LEGACY_PATH_TRACE_2026-09-29.md
?? docs/reports/JOBOPS_PHASE_B_FOLLOWUP_REPORT_2026-09-29.md
?? docs/reports/JOBOPS_PHASE_B_IMPLEMENTATION_REPORT_2026-09-29.md
?? evaluation/
?? geo/
?? identity/
?? ingestion/
?? ops/
?? policy/
?? relevance/
?? review/
?? sources/
?? store/
?? tests/conftest.py
?? tests/fixtures/
?? tests/test_p0_02_gate.py
?? tests/test_p0_06_linkedin_ingestion.py
?? tests/test_p0_07_identity_dedup.py
?? tests/test_p0_08_review_queue.py
?? tests/test_p0_10_time_instrumentation.py
?? tests/test_p1a_policy_021.py
?? tests/test_policy_v02_golden.py
?? tests/test_relevance_distribution_tool.py
?? tests/test_v02_f4_replay.py
?? tests/test_v02_guardrails.py
?? tests/test_v02_identity_newness_conflict.py
?? tests/test_v02_lanes_queue.py
?? tests/test_v02_policy_engine.py
?? tests/test_v02_relevance.py
?? tests/test_v02_store_migrations.py
?? tests/v02_support.py
?? timing/
?? tools/
```

The index contains only the owner-approved `D  data/jobs-tracker.db` from Phase B (`git diff --cached --name-status` → `D data/jobs-tracker.db`). P1a changed nothing in the index.

## Scope

| Check | Answer |
|---|---|
| Network used | **NO.** Tests ran with sockets blocked; no HTTP, scraping, ATS, LinkedIn or Apify. |
| Live DB opened | **NO.** mtime `1788161814` is unchanged. The scratch copies carried a byte copy for the pre-existing P0 tests, as in the baseline. |
| `data/n8n` runtime/data opened | **NO.** Only `workflows/*.json` outside `data/n8n` was read, for node types; the file with a `credentials` key was not read further. |
| `.env` opened | **NO.** It was also excluded from the scratch copies. |
| Secrets accessed | **NO** |
| Dependencies added | **NO.** Standard library only. |
| Commits created | **NO** |
| Index modified by this follow-up | **NO** |
| Phase C started | **NO** |
| Ingestion rewired | **NO** |
| Scheduler started | **NO** |
| Application submission implemented | **NO** |
