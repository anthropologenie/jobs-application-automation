# JobOps Legacy Path Trace — 2026-09-29 (P1a, read-only)

**Method:** static reading of the repository's import graph, entry points and function bodies, using `grep` over `*.py`, `*.sh` and `workflows/*.json`. Nothing was executed against real data. n8n workflow files outside `data/n8n` were read only for node types and target URLs. `workflows/claude-api-test-header-auth.json` contains a `credentials` key, so it was not read beyond its node types. `data/n8n/`, `.env` and the live DB were not opened.

Reachability vocabulary used below:
- **actively used**: invoked by a current operator entry point;
- **reachable but not default**: callable, but no entry point uses it by default;
- **unused by current entry points**: importable, but no entry point reaches it;
- **dead code**: unreachable from anything.

---

## A. Entry points

| # | Entry point | Kind | What it reaches |
|---|---|---|---|
| E1 | `python3 -m ingestion.run_linkedin_ingestion` (`ingestion/run_linkedin_ingestion.py:152 main`) | CLI, manual | **The only LinkedIn ingestion entry point.** Builds `CandidateStore` (`:159`), optionally `store.backup()` (`:175`), then `LinkedInIngestionPipeline.run([query])` (`:178`) |
| E2 | `python3 -m review.run_review_queue` (`review/run_review_queue.py:223 main`) | CLI, manual | `review.queue.ReviewQueue` → `review.ledger.CandidateLedgerStore`; with `--decide`, `review.decisions.DecisionStore` |
| E3 | `api-server.py` (started by `start-tracker.sh:126`) | HTTP, manual start | `GET /api/review-queue` (`:243` → `_handle_review_queue :700` → `ReviewQueue`); `POST /api/review-decision` (`:444` → `_handle_review_decision :753` → `ReviewQueue` + `DecisionStore`); `POST /api/import-scraped-job/{id}` (`:256` → `_handle_import_scraped_job :533`, which uses `ingestion.extraction.work_mode_from_candidate_fields` and the **v0.1** normalizer `HardEligibilityGate().normalizer` from `:30`). **No LinkedIn fetch.** |
| E4 | `python3 -m timing.run_timing_report` (`timing/run_timing_report.py:308 main`) | CLI, manual | `timing.lifecycle.LifecycleReader` → `review.queue.ReviewQueue` → `review.ledger` |
| E5 | `python3 scrapers/remoteok_integration.py` (`:512`) | CLI, manual | RemoteOK HTTP + `simple_scorer`; writes legacy `scraped_jobs`. **Not LinkedIn; no gate** |
| E6 | n8n `workflows/01-job-scraper-remoteok*.json` | n8n (container not running) | scheduleTrigger → `https://remoteok.com/api` → JSON file. **Not LinkedIn; no gate; no DB write** |
| E7 | n8n `workflows/05-dashboard-api-bash.json`, `06-opportunity-manager-bash.json` | n8n webhooks | `sqlite3 /data/jobs-tracker.db` reads / `executeCommand`. **Not LinkedIn** |
| E8 | n8n `workflows/claude-api-test*.json` | n8n manual | Anthropic API test calls. **Not ingestion** |
| E9 | `python3 -m store.migrate` (`store/migrate.py:173 main`) | CLI, manual (v2) | Schema only; no ingestion; refuses the legacy DB |
| — | `evaluation.service.EvaluationService` (v2) | library | **No entry point outside tests.** The only non-test importer of `evaluation` is `relevance/labeller.py`, and only for a helper (`evaluation.textutil`) |

A search of `workflows/*.json`, `start-tracker.sh`, `stop-tracker.sh`, `test-everything.sh` and `scripts/*` finds no "linkedin". There is no scheduler for any path (audit A1).

## B. Call graph (actual modules and functions)

**E1: LinkedIn ingestion (v0.1)**
```
ingestion/run_linkedin_ingestion.py:main
 → ingestion.pipeline.LinkedInIngestionPipeline.run            (pipeline.py:279)
    → ingestion.linkedin_cli.LinkedInSearchCLI.search/detail     (subprocess `bun`, rate_limit.RateLimiter)
    → ingestion.provenance.RawSourceStore.write                  (raw payloads)
    → detail skipped for already-held ids                        (pipeline.py:323-330)
    → _gate_and_build                                            (pipeline.py:388)
        → ingestion.merge.merge_source_records
        → ingestion.extraction.locate_*/select_*                 (_gate_input, pipeline.py:153)
        → policy.gate.HardEligibilityGate.evaluate_posting       (pipeline.py:402)  ← v0.1 gate
    → _persist → ingestion.persistence.CandidateStore.insert_candidates (pipeline.py:436)
    → ingestion.provenance.RunLedger.record_candidate / flush     (pipeline.py:453, :374)
 relevance: none · lanes: none at ingest · identity: L1 only (INSERT OR IGNORE)
```

**E2 / E3 / E4: review, decisions, timing (v0.1)**
```
review.queue.ReviewQueue.build
 → review.ledger.CandidateLedgerStore.load    (reads data/ingestion/candidates/*.jsonl)
 → CandidateEvidence.current == observations[-1]   (review/ledger.py:108-109)
 → identity.IdentityStore/IdentityResolver    (read-only over scraped_jobs + opportunities)
 → lanes from review/jobops-review-0.1.0.json (SHORTLIST/REVIEW/BELOW_THRESHOLD/EXCLUDED/NOT_EVALUATED/SUPPRESSED_DUPLICATE)
review.decisions.DecisionStore.record          (append data/review/decisions.jsonl)
timing.lifecycle.LifecycleReader → ReviewQueue (read-only) ; timing.submissions (append data/application/submissions.jsonl)
```

**v2 (Phase B), tests only**
```
EvaluationService.ingest (evaluation/service.py)
 → extract.extract → identity_resolution.resolve → store.repository (observation, evidence)
 → newness → EvaluationService.current_evaluation
    → selection.select (F4 fix) → engine.evaluate (v0.2 policy, relevance.labeller, lanes)
    → repository.insert_evaluation (idempotent key)
 evaluation.queue.plan_day → digest.render
```

## C. Gate usage

| Path | Engine |
|---|---|
| E1 LinkedIn ingestion | **v0.1** `policy.gate.HardEligibilityGate` reading `policy/jobops-policy-0.1.0.json` |
| E3 import bridge | **v0.1** normalizer only (`HardEligibilityGate().normalizer`), used for work mode; no verdict |
| E2/E3/E4 review / timing | No gate. They read v0.1 verdicts from the JSONL ledger |
| v2 `evaluation/` | **v0.2** policy (`policy/jobops-policy-0.2.0.json`); tests only. `evaluation/v01_adapter.py` can replay v0.1 over v2 evidence |

## D. Databases written

| Path | Writes |
|---|---|
| E1 | `data/jobs-tracker.db` → `scraped_jobs` (INSERT OR IGNORE); plus a full DB backup file per non-dry run; JSONL under `data/ingestion/{raw,candidates,runs,state}` |
| E2/E3 decisions | `data/review/decisions.jsonl` (the DB is opened read-only) |
| E3 import bridge | `data/jobs-tracker.db` → `opportunities` INSERT, `scraped_jobs.imported_to_opportunities` UPDATE |
| E4 | `data/application/submissions.jsonl` (only with `--record-submission`) |
| E5 | `data/jobs-tracker.db` → `scraped_jobs` |
| v2 | The DB given by `JOBOPS_DB_PATH` / `data/runtime/jobops.db`. **The legacy DB is refused** without `--allow-legacy-db`. In practice only `:memory:` and temporary DBs in tests so far |

## E. F4

- **Where the original defect lives:**
  1. `ingestion/pipeline.py:323-330` skips the detail fetch for already-held ids, but `_gate_and_build` (`:388-402`) still re-gates them from the search-only record (no description).
  2. `review/ledger.py:108-109` treats the latest observation as `current`.

  Together, a later search-only run replaces a JD-based verdict as the current one.
- **`ingestion/pipeline.py`:** **actively used.** It is the default and only LinkedIn path (E1), invoked manually. The defect is therefore **still live on the v0.1 path.**
- **`review/ledger.py`:** **actively used** through E2, E3 (`/api/review-queue`, `/api/review-decision`) and E4.
- **v2 fix:** `evaluation/selection.py` (absence never displaces presence) + `evaluation/engine.py` (content-hash evaluation key) + `evaluation/service.py` (`current_evaluation`). **Reachable but not default:** no entry point invokes it; only tests do.
- **Dead code:** none identified on these paths. `scrapers/*` and the n8n RemoteOK workflows are **unused by current entry points for LinkedIn** but remain reachable manually for RemoteOK.

## F. Tests covering each path

| Path | Tests |
|---|---|
| E1 v0.1 LinkedIn pipeline | `tests/test_p0_06_linkedin_ingestion.py` (75); `tests/test_p0_02_gate.py` (105, gate); `tests/test_p0_07_identity_dedup.py` (77, identity, merge) |
| E2/E3 review queue, decisions | `tests/test_p0_08_review_queue.py` (54) |
| E4 timing | `tests/test_p0_10_time_instrumentation.py` (52) |
| v2 evaluation / relevance / lanes / store / F4 | `tests/test_policy_v02_golden.py`, `test_v02_*.py` (Phase B, extended in P1a) |
| E5/E6/E7 RemoteOK, n8n | Legacy shell tests only (`tests/*.sh`); not run |

## G. Final verdict

**LinkedIn ingestion → old v0.1 gate.**

The v0.2 chain (evaluation → relevance → lanes → store) exists and is tested, but no current entry point uses it. The repository as a whole is therefore **mixed**:
- LinkedIn ingestion (E1) → v0.1 gate → `scraped_jobs` + JSONL ledger;
- review/timing (E2–E4) → v0.1 ledger;
- v2 is tests-only.

## H. Phase C replacement plan (documented, NOT implemented)

1. **Rewire E1:**
   - Keep `ingestion/linkedin_cli.py`, `rate_limit.py`, `config.py`, `provenance.RawSourceStore` and OR-08 caps unchanged.
   - Replace `LinkedInIngestionPipeline.run`'s gate/persist stages (`_gate_and_build`, `_persist`, `pipeline.py:362-436`) with a `sources/linkedin_cli_adapter.py` that turns search and detail payloads into `sources.base.ObservationInput`. A search hit becomes `completeness=SEARCH_ONLY`; a detail becomes `FULL_JD`.
   - Call `evaluation.service.EvaluationService.ingest` for each, inside `store.lock.RunLock`.
2. **v2 entry point:** a new `ops/run_ingestion.py` (Phase C) that opens `store.db.connect(resolve_db_path())`, runs `store.migrate`, runs the adapter, then `evaluation.queue.plan_day` and `digest.render_daily`.
3. **Retire or isolate:**
   - `ingestion/pipeline.py` `_gate_and_build`/`_persist` and `ingestion/persistence.py`: isolate behind the old CLI flag; do not delete until parity is shown;
   - `review/ledger.py` "current = latest" (it becomes read-only history);
   - `review/queue.py` lanes, replaced by `evaluation/queue.py`;
   - the `api-server.py` review endpoints, to be repointed at v2 in a later UI phase.
4. **Tests to move or update:**
   - `test_p0_06` pipeline tests split: adapter tests (CLI contract, caps, 429 handling) stay; gate/persist assertions move to v2 tests;
   - `test_p0_08` and `test_p0_10` must be re-targeted when review and timing read v2 tables;
   - v0.1 gate tests (`test_p0_02`) stay as v0.1 replay tests.
5. **Data-store transition:**
   - Owner-authorized: copy `data/jobs-tracker.db` → the v2 runtime path, or run `store.migrate --allow-legacy-db` on a copy. Migration 0101 archives the 77 `scraped_jobs` rows (OI-034).
   - The existing `data/ingestion/candidates/*.jsonl` v0.1 verdicts stay as history. Optionally import their raw payloads as v2 observations (raw is retained, so no recrawl).
   - `decisions.jsonl` and `submissions.jsonl` are imported into `review_decision` / `application` with `actor='human'`.
   - v0.1 and v2 must not both write concurrently: use `RunLock`.
