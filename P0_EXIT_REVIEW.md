# P0_EXIT_REVIEW.md

> **STATUS: IN PROGRESS — NOT A COMPLETED P0 EXIT REVIEW.**
>
> This document is the location `P0_IMPLEMENTATION_SPEC.md` §10.4 step 7 designates for
> recording migration application evidence while JS-24 is unbuilt, and the document
> §13 requires for recording exit criteria X1–X13 against named evidence.
>
> It is opened here to hold the migration-005 record and, since 2026-08-31, the §10.4
> step 6 functional verification of the repaired bridge. **No P0 exit is claimed.** Most of
> X1–X13 are unmet, and the criteria table below states which. Entries are added only as
> an authorized session produces the evidence for them.

---

## 1. Migration application record

The record `P0_IMPLEMENTATION_SPEC.md` §10.4 step 7 requires. Until JS-24 establishes a
history mechanism, this section — not the database — is the record of what was applied.
The step 6 functional verification of the bridge the migration repairs is recorded here too.

### 005_add_scraped_job_import.sql — APPLIED

| Field | Value |
|---|---|
| Migration | `migrations/005_add_scraped_job_import.sql` |
| Statement | `ALTER TABLE opportunities ADD COLUMN scraped_job_id INTEGER;` |
| Authority | CONFLICT-2(b), `OWNER_RULINGS_LOG.md`; execution authorized by the Repository Owner in a session dated 2026-08-29 |
| Applied date | 2026-08-29 |
| Approximate time | ~15:52 UTC — the evidence is the applied file's mtime and the session log; no more precise timestamp is claimed |
| Operator | An authorized Claude Code session acting under the Repository Owner's 2026-08-29 execution authorization. **No individual operator identity is asserted** — none is recorded by any mechanism in this repository |
| Execution method | `sqlite3 -bail data/jobs-tracker.db < migrations/005_add_scraped_job_import.sql` |
| Exit code | `0` |
| Target database | `data/jobs-tracker.db` |
| Procedure | `P0_IMPLEMENTATION_SPEC.md` §10.4 steps 1–5 |

**Precondition (read-only, before execution)**

- `opportunities.scraped_job_id` — **absent** (24 columns)
- `journal_mode` = `wal`; WAL sidecar **0 bytes** — no WAL-resident transactions
- `PRAGMA integrity_check` = `ok`
- `PRAGMA user_version` = `0`; `PRAGMA application_id` = `0`
- Migration file byte-identical to `HEAD` — SHA-256 `f2e5beadce7c804af19b3a99fca5320fef516d69f28caa551f4077d82cb8dac7`
- Database SHA-256 `6cd49b736fc4eb7fb426a91b189338b100bf6bab30baf79610cc63d9ef424c40`

**Postcondition (read-only, after execution)**

- `opportunities.scraped_job_id` — **present**, `cid=24`, type `INTEGER`, `notnull=0`, no default, not PK; NULL in all 22 existing rows
- Schema objects **54 → 54**; zero added, zero removed
- The only changed object is the `opportunities` table DDL; the diff is exactly `)` → `, scraped_job_id INTEGER)`
- Indexes, views, triggers and constraints unchanged
- `PRAGMA integrity_check` = `ok`; `PRAGMA foreign_key_check` = no violations
- Database SHA-256 `71d7b670ee0316e0f00a38d23523d94d0f20cd990080b45ac5634bc8ed154039`

**Row-count validation — all 11 tables unchanged**

| Table | Before | After | | Table | Before | After |
|---|---|---|---|---|---|---|
| `documents` | 0 | 0 | | `practice_sessions` | 5 | 5 |
| `interactions` | 3 | 3 | | `sacred_work_log` | 0 | 0 |
| `interview_questions` | 12 | 12 | | `scraped_jobs` | 77 | 77 |
| `job_sources` | 10 | 10 | | `sql_practice_sessions` | 7 | 7 |
| `learning_sessions` | 0 | 0 | | `study_topics` | 5 | 5 |
| `opportunities` | 22 | 22 | | | | |

**Integrity of the operation**

- The migration file was **not modified** — byte-identical to `HEAD` before and after.
- **No other migration was applied.** Migration 004 (`parliament_decisions`) remains unapplied and unauthorized per CONFLICT-2(c).
- CONFLICT-3 was **not** resolved and was not touched. No `git checkout`, reset, restore, replace, or manual checkpoint was performed on the tracked database; no WAL-resident transaction was discarded.
- Safety artifacts created before execution and retained: a raw byte-identical copy and a SQLite logical backup, both timestamped `pre005-20260829-155145` under `data/` and covered by `.gitignore`.

### Functional verification of the repaired bridge — §10.4 step 6

Performed 2026-08-31 in a session authorized for the migration record and this verification
only. Scope was one controlled endpoint invocation; **no ingestion, scraping, n8n, Gmail, or
bulk import was run, and no migration was applied, altered, or rolled back.**

**Acceptance criterion under test** — `JOBOPS_SCALING_EXECUTION_PLAN.md` P0-05 and §10.4
step 6: *one import returns `200`; a repeat returns `409`; `imported_to_opportunities` flips;
provenance is queryable in both directions.*

**Procedure**

- API server started the way `start-tracker.sh:126` starts it — `python3 api-server.py`
  from the repository root, logging to `logs/api-server.log`, port `8081` — and **shut down
  after the run**. `api-server.pid` was not written or altered.
- Safety artifacts taken before the run and retained: a raw copy and a SQLite logical backup,
  both timestamped `pre-p0-05-verify-20260831-053546` under `data/`, `.gitignore`-covered.
  The logical backup verifies `integrity_check = ok`, 23 `opportunities`, 77 `scraped_jobs`.
- Pre- and post-state captured read-only (`sqlite3 -readonly`) as full row-count, per-row
  `opportunities`, per-row `scraped_jobs.imported_to_opportunities`, and `.schema` snapshots.

**Test input**

`scraped_jobs.id = 43` — Loop, "Data Engineer", RemoteOK `external_id 1128876`,
`match_score 62.4`, `classification LOW_FIT`. Selected because it was the highest-scoring row
still carrying `imported_to_opportunities = 0`, had no existing `opportunities` row by
`job_url` or by company/role, and no `opportunities` row referenced it. **No test fixture was
created and no row was invented** — the row is pre-existing scraped data.

**Requests and responses**

| # | Request | HTTP | Body | Writes |
|---|---|---|---|---|
| T1 | `POST /api/import-scraped-job/99999` | `404` | `{"error": "scraped job not found"}` | none |
| T2 | `POST /api/import-scraped-job/3` | `409` | `{"error": "already imported", "opportunity_id": 27}` | none |
| T3 | `POST /api/import-scraped-job/43` | `200` | `{"opportunity_id": 28, "scraped_job_id": 43, "status": "imported"}` | the one controlled import |
| T4 | `POST /api/import-scraped-job/43` (repeat) | `409` | `{"error": "already imported", "opportunity_id": 28}` | none |

T2 exercises the exact query the audit recorded as failing —
`SELECT id FROM opportunities WHERE scraped_job_id = ?` — which now returns a row instead of
`Error: in prepare, no such column: scraped_job_id`.

**Database delta — the complete set of changes**

| Object | Before | After |
|---|---|---|
| `opportunities` row count | 23 | 24 |
| `opportunities` row `id = 28` | absent | `Loop` · `Data Engineer` · `source RemoteOK` · `status Lead` · `scraped_job_id = 43` |
| `scraped_jobs.id = 43` `imported_to_opportunities` | `0` | `1` |
| The other 10 tables | unchanged | unchanged |
| `.schema` SHA-256 | `f97bb57948b37f28bb1d475bb04193ab59adfdc219cad9c0b5aaf8de6514d331` | identical |

- No pre-existing `opportunities` row was modified — every other row's `updated_at` is
  byte-identical across the snapshots.
- No `scraped_jobs` row other than `43` changed state.
- `PRAGMA integrity_check` = `ok`; `PRAGMA foreign_key_check` = no violations.

**Provenance verified in both directions**

- Forward — `opportunities.28 → scraped_jobs.43`, joining to `external_id 1128876`.
- Reverse — `SELECT id FROM opportunities WHERE scraped_job_id = 43` → `28`.
- Field fidelity — `company`, `role`←`job_title`, `job_url`, `source`, `salary_range`,
  `tech_stack`←`tags` all compare equal to the source row; `status = 'Lead'` as the contract
  specifies.

**No duplicate, no policy invocation**

- `GROUP BY scraped_job_id HAVING COUNT(*) > 1` over `opportunities` returns **no rows** — the
  provenance relationship is one-to-one.
- The Loop `job_url` appears in exactly one `opportunities` row.
- `api-server.py` imports nothing from `policy/` and the handler body
  (`api-server.py:508–558`) calls no gate, ruleset, or scorer. **No eligibility or scoring
  behaviour was invoked**, consistent with the endpoint's contract: it is the human accept
  action, not an ingestion filter.

**Finding — field mapping is partial (recorded, not fixed)**

`opportunities.28.is_remote = 0` (the column default) although `scraped_jobs.43.location`
is `Remote`. The handler's `INSERT` names eight columns and does not map `location`, so
`is_remote`, `domain_match`, and `notes` take defaults. This matches the endpoint's existing
contract and is **not** a regression from migration 005. It is recorded here as a known
fidelity gap for whichever later task owns the ingestion mapping; **nothing was changed.**

**Finding — an earlier undocumented import exists**

`opportunities.27` (YLD, `scraped_job_id = 3`, `created_at 2026-08-29 16:00:58`) predates this
session and **is not recorded anywhere in this repository.** It postdates this document's
migration record by roughly two minutes and is consistent with a post-migration bridge test
in the 2026-08-29 session, but **no actor, session, or purpose is asserted** — none is
recoverable from the repository, the logs (`logs/api-server.log` is empty), or the database.
It is stated here as observed pre-existing state. It was not altered or removed.

**Result — P0-05 acceptance criterion MET.** The discovery→opportunity bridge, which
`JOBOPS_SCALING_CAPABILITY_INVENTORY.md` F2 recorded as never having executed once, now
executes end-to-end.

### Observation — migration 006 pre-existing state

`practice_sessions` exists in `data/jobs-tracker.db`, and existed before the migration-005
operation. Migration `006_add_practice_sessions.sql` therefore **appears to have been
applied at some earlier point through a channel that left no record.**

This is an observation of pre-existing database state only. **No actor, channel, date, or
session is identified or inferred**, because none is recoverable from the repository or
the database. Migration 006 was not altered, reversed, or re-applied, and no retroactive
history entry was created for it.

### JS-24 — OPEN

Migration history remains underivable from the database alone: `user_version = 0`,
`application_id = 0`, and no `schema_migrations`-style table exists. The migration-006
observation above is direct evidence of the gap — the database records that a schema
change happened but not that a migration applied it.

**JS-24 is not resolved by this record and is not marked resolved.** This section is a
document, not a history mechanism; it records only what an authorized session observed.
Per CONFLICT-2, JS-24 governs future migrations and was not a precondition for 005.

---

## 2. Exit criteria — X1–X13

Per §13, each criterion requires named evidence and none is satisfied by assertion.

| # | Criterion | Status | Evidence |
|---|---|---|---|
| X1 | Deterministic gate | **MET** | `tests/test_p0_02_gate.py::test_evaluation_is_deterministic` |
| X2 | Remote/hybrid/on-site enforced | **MET** | T-06, T-07, T-10 equivalents pass; AMBIGUOUS never resolves to REMOTE |
| X3 | ₹20 LPA threshold enforced | **MET** | Threshold/boundary tests pass; T-13 equivalent confirms the ₹18L figure affects no verdict |
| X4 | UNKNOWN preserved and escalated | **PARTIAL** | Gate-side tests pass. The §7.7 human-sampling record is **outstanding** — it depends on ingestion |
| X5 | Services/staffing not incorrectly vetoed | **MET** | T-08/T-09 equivalents produce identical gate verdicts |
| X6 | LinkedIn ingestion within constraints | **NOT MET** | Not implemented |
| X7 | Duplicates controlled | **NOT MET** | Not implemented |
| X8 | Review queue works | **NOT MET** | Not implemented |
| X9 | Evidence and provenance visible | **MET** | T-15/T-16/T-17 equivalents pass; every FAIL and UNKNOWN carries a registry reason code |
| X10 | Time instrumentation | **NOT MET** | Not implemented |
| X11 | No scoring rule overrides eligibility | **MET** | T-18 equivalent passes; a structural AST check confirms the gate does not import the scorer |
| X12 | Migration state known and governed | **MET** | §1 above: 005 applied and verified per §10.4 and recorded; 004 confirmed still unapplied and unauthorized; JS-24 stated explicitly as open |
| X13 | All P0 acceptance tests pass | **PARTIAL** | 105 tests pass in a recorded run. T-14 (the `resume_config.json` Selenium contradiction) is **not implemented** — it is outside the gate per §3.5 and awaits OR-05 |

**The measured baseline and the "where candidate time went" finding required by §13 are
absent.** Both depend on X10, so no P1-vs-P2 fork decision is supported by this document.
