# JobOps v2 — Phase B Implementation Report (2026-09-29)

**Scope:** policy engine v0.2, relevance labeller v1, queue lanes and capacity, SQLite persistence and migration runner, and the F4 regression fix.
**Not done (by instruction):** source adapters, scheduler, network discovery, review UI, application submission, commits.

## 1. Result

**PASS.** The full suite passes on a fresh scratch copy of the repository with outbound sockets blocked process-wide: **629 passed, 0 failed, 0 skipped.** That is the 363 pre-existing tests (unmodified) plus 266 new v0.2 tests.

## 2. Files

**Created**

| Area | Files |
|---|---|
| Policy | `policy/jobops-policy-0.2.0.json` |
| Evaluation | `evaluation/__init__.py`, `evaluation/policy_loader.py`, `evaluation/textutil.py`, `evaluation/compensation.py`, `evaluation/extract.py`, `evaluation/dimensions.py`, `evaluation/selection.py`, `evaluation/engine.py`, `evaluation/identity_resolution.py`, `evaluation/newness.py`, `evaluation/service.py`, `evaluation/queue.py`, `evaluation/v01_adapter.py` |
| Relevance | `relevance/__init__.py`, `relevance/labeller.py` |
| Geo | `geo/__init__.py`, `geo/places.py` |
| Company | `company/__init__.py`, `company/registry.py` |
| Sources | `sources/__init__.py`, `sources/base.py` (seam only) |
| Store | `store/__init__.py`, `store/paths.py`, `store/db.py`, `store/migrate.py`, `store/backup.py`, `store/lock.py`, `store/repository.py`, `store/migrations/0100_v2_core.sql`, `store/migrations/0101_legacy_archive.py` |
| Digest / ops | `digest/__init__.py`, `digest/render.py`, `ops/__init__.py` |
| Quarantine | `_quarantine/MANIFEST.md` |
| Tests | `tests/v02_support.py`, `tests/test_policy_v02_golden.py`, `tests/test_v02_policy_engine.py`, `tests/test_v02_relevance.py`, `tests/test_v02_lanes_queue.py`, `tests/test_v02_identity_newness_conflict.py`, `tests/test_v02_store_migrations.py`, `tests/test_v02_f4_replay.py`, `tests/test_v02_guardrails.py` |
| Report | this file |

**Modified**

- `tests/fixtures/policy_v02_golden_cases.json`: regenerated as executable. 161 cases; G001–G112 kept and G113–G164 added.
- `OWNER_RULINGS_LOG.md`: only the OR-26 … OR-30 RULING placeholders were filled. A diff shows 0 removed lines and 5 insertion blocks.
- `docs/architecture/JOBOPS_V2_OPEN_ITEMS.md`, `JOBOPS_V2_OWNER_POLICY_SPEC.md`, `JOBOPS_V2_DATA_MODEL.md`, `JOBOPS_V2_REPO_LAYOUT.md`: Phase B sections appended; earlier text unchanged.
- `.gitignore`: appended `data/runtime/` and `data/jobs-tracker.db`.
- Git index: `git rm --cached data/jobs-tracker.db`. This stages "stop tracking". The file itself is kept and unchanged, history is not rewritten, and **nothing was committed**.

**Unchanged:** `policy/jobops-policy-0.1.0.json` (sha256 `afe05e5a31777410668180a2d50a06da7cfa21736159946273060be6bf1c051f`, recorded in the v0.2 artifact), `policy/gate.py`, `policy/ruleset.py`, `ingestion/` (LinkedIn untouched), `identity/`, `review/`, `timing/`, `api-server.py`, and all existing tests.

## 3. Policy

- **Version:** `jobops-policy@0.2.0`, active for the v2 engine.
- **Data-driven:** the artifact holds all thresholds, regions (region → country membership), aliases, lexicons, the 20 Tier 1 titles, Tier 2 titles, relevance clusters and thresholds, experience bands, employer categories, lane rules, flag registry, cap, carry days and the language threshold. The engine interprets ordered rule tables with a small predicate language.
- **Drift guards:** refuse a fourth verdict, a non-FAIL>UNKNOWN>PASS precedence, unregistered flags, unknown `$params`, and a rule table without a catch-all.
- **v0.1 stays pinned:** the v0.1 engine keeps `EXPECTED_RULESET_VERSION = jobops-policy@0.1.0`, so the existing tests exercise exactly the v0.1 behaviour they always did. v0.1 can be replayed over v2 evidence with `evaluation/v01_adapter.py`.

## 4. Golden tests

- **Count:** 161 cases plus 1 fixture-shape test = 162.
- **Result:** 162 passed, 0 failed, 0 blocked.
- **What is checked:** each case asserts all six eligibility dimensions, the overall verdict, relevance label, title tier, clusters, experience and seniority signals, preference attributes, the exact flag set, newness and lane. Multi-observation cases also assert each step (same requisition, lane, newness and reason, and whether a new evaluation was written).

## 5. F4 regression — PASS

Tests: `tests/test_v02_f4_replay.py`
- `test_f4_jd_bearing_then_search_only_never_downgrades`
- `test_f4_search_only_then_jd_bearing_upgrades`
- `test_f4_multiple_sources_with_different_completeness`
- `test_f4_unchanged_identity_richer_evidence`
- `test_replay_under_variant_policy_without_recrawl_keeps_old_evaluation`
- `test_replay_under_v01_gate_from_stored_evidence`
- `test_current_evaluation_is_deterministic_across_databases`

Golden cases G109 and G110 cover the same scenarios.

**Mechanism:** per-dimension evidence selection (`evaluation/selection.py`) ranks observations by presence of primary evidence, then authority tier, then completeness, then recency, then id. Absence can therefore never displace presence. The evaluation key is (requisition, policy_version, content-hash of the selected evidence), so identical or sparse re-sightings reuse the existing evaluation.

## 6. Persistence

- **Migration runner:** `store/migrate.py`, applying `0100_v2_core.sql` and `0101_legacy_archive.py`.
  - A demo apply on a scratch DB applied both, and a re-run applied nothing.
  - Checksum drift stops the runner; a failing migration rolls back.
  - A pre-migration backup is taken when tables exist, with rotation.
  - `user_version` is set to 101.
- **Runtime DB path:** `JOBOPS_DB_PATH`, otherwise `data/runtime/jobops.db` (gitignored).
- **Legacy DB guard:** `data/jobs-tracker.db` is refused by the v2 store unless the owner passes `--allow-legacy-db`. This was verified: the refusal happens before any open.
- **Legacy 77 rows:** migration 0101 records every `scraped_jobs` row in the append-only `legacy_scraped_job` table. They are never evaluated and are absent from all lanes. Tested on a synthetic 77-row scratch DB; the real legacy DB was not used.
- **Immutability:** append-only and immutable triggers protect evidence, observations, evaluations, classifications, decisions and application events. CHECK constraints allow only PASS/FAIL/UNKNOWN as verdicts and `actor='human'` for decisions and application events.

## 7. Relevance

- **Tier 1:** 20 titles.
- **Tier 2 and Tier 3:** implemented. Tier 3 requires a STRONG or MODERATE JD.
- **Labels:**
  - STRONG = at least 3 distinct AI-specific terms across at least 2 clusters;
  - MODERATE = at least 2 AI-specific terms;
  - WEAK = otherwise;
  - NOT_ASSESSED = no JD.
- **Evidence:** verbatim JD spans are returned.
- **Excluded by design:** no score, no LLM, no embeddings, no network. Supporting terms (Python, Docker …) and traditional-QA terms never count.

## 8. Queue

| Lane | Condition |
|---|---|
| SUPPRESSED_DUPLICATE | duplicate requisition (kept, never deleted) |
| EXCLUDED | any FAIL |
| REVIEW | NOT_ASSESSED with a Tier 1 title |
| PARKED | NOT_ASSESSED otherwise, WEAK, or MODERATE with 7+ years or a Staff/Principal/Architect title |
| REVIEW | any UNKNOWN or review-routing flag |
| SHORTLIST | otherwise |

**Capacity:**
- REVIEW cap 10 per day.
- Deterministic categorical ordering: relevance, newness, completeness, REMOTE > BENGALURU_HYBRID, compensation band, employer, first_seen_at, requisition_id.
- 3-day carry, then PARKED; STRONG relevance is exempt.
- Items with a human decision leave the pending pool.

## 9. Quarantine

`_quarantine/MANIFEST.md` lists 14 categories: scrapers, QA scoring, prompts, resumes, n8n, learning/SQL, backups, PID/runtime files, empty scripts, shell tests, stale docs, legacy rows and LinkedIn seeds. **Nothing was moved.**

## 10. Scope guardrails

| Guardrail | Result |
|---|---|
| Network used | **NO.** The full suite ran with sockets blocked, and v0.2 tests also refuse sockets. |
| Live DB touched | **NO SQLite access.** mtime `1788161814` and sha256 prefix `bf17ebb1b97dd520` are unchanged before and after. The pre-existing P0 tests need a DB file, so the scratch copy contains a byte copy of it, exactly as in the Phase A baseline. |
| Secrets accessed | **NO.** `.env` was not opened. |
| New dependencies | **NO.** Standard library only. |
| Commits created | **NO.** One index-only change: `git rm --cached data/jobs-tracker.db`. |
| Application submission | **NO.** There is no code path, and a test asserts it. |

## 11. Deferred

- Source adapters (ATS, public, LinkedIn changes), source reconnaissance and the company-registry population flows (P2).
- Scheduler and orchestrator.
- JD fetching for NOT_ASSESSED items.
- LLM-assisted extraction (P3).
- Review UI, review timer, application-preparation helpers (P4).
- API localhost binding and authentication; moving live data into the v2 DB (an owner-authorized migration with `--allow-legacy-db` or a copy).
- LinkedIn seed change (OI-031).
- Correcting the Addendum A index table (OI-047) and recording the other Phase B rulings as OR-31+ (OI-048).

## 12. Open items

Still open from Phase A: **OI-025, OI-027.** New from implementation: **OI-036 … OI-048**, each implemented deterministically as documented. The exact wording is in `docs/architecture/JOBOPS_V2_OPEN_ITEMS.md` under "Phase B status".
