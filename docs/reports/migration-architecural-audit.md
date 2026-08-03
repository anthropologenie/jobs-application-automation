  JobOps Database Migration System — Architectural Audit

  Repo: /home/katte/projects/jobs-application-automation · HEAD: f29c31c · Branch: main (clean) · SQLite CLI: 3.45.1 · Audit date: 2026-08-03

  ---
  A. Migration System Assessment

  Current architecture

  There is no migration system. There is a directory named migrations/ containing six SQL files with no runner, no ordering enforcement, no history
  table, and no application-side invocation. Schema changes reach the database through five unrelated, uncoordinated channels:

  ┌───────────────────────────────────────────────────┬──────────────────────────────────────────────────────────────────────┐
  │                      Channel                      │                               Evidence                               │
  ├───────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────┤
  │ Manual sqlite3 db < file.sql                      │ Documented at README.md:526-532 and docs/SYSTEM_SUMMARY.md:966-978   │
  ├───────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────┤
  │ One-off bespoke shell runner (migration 004 only) │ scripts/apply_parliament_migration.sh                                │
  ├───────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────┤
  │ Embedded Python DDL at runtime                    │ scrapers/remoteok_integration.py:169-220 (create_scraped_jobs_table) │
  ├───────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────┤
  │ Direct binary edits to the committed .db file     │ Commit 09450f0 — M data/jobs-tracker.db, no SQL artifact added       │
  ├───────────────────────────────────────────────────┼──────────────────────────────────────────────────────────────────────┤
  │ Nothing at all (declared, never wired)            │ log-sql-practice.py:180-183 — _ensure_table_exists() body is pass    │
  └───────────────────────────────────────────────────┴──────────────────────────────────────────────────────────────────────┘

  Startup performs no schema work. start-tracker.sh:59-60 only warns if the file is absent. api-server.py opens DB_PATH (line 13) and issues queries
  with zero validation. scripts/setup.sh and scripts/backup.sh are 0 bytes — empty stubs.

  Migration history mechanism: none. PRAGMA user_version = 0, PRAGMA application_id = 0, and no schema_migrations-style table exists in
  sqlite_master. There is no way, from the database alone, to determine which migrations have been applied.

  Strengths

  1. Migrations are plain .sql files under version control — portable, reviewable, diffable.
  2. Migrations 003/004/006 use IF NOT EXISTS consistently and replay cleanly against the current runtime DB (verified: exit 0 for 003, 004, 005,
  006, add-sql-practice-tracking).
  3. Migration 006 is explicitly transactional (BEGIN/COMMIT) and carries a version-history header block — the only artifact showing
  migration-authoring discipline.
  4. The stashed 005_add_ml_features.sql contains a hand-written rollback section (lines under -- ROLLBACK:), showing rollback was at least
  considered once.
  5. scripts/db_inventory.py is a well-scoped, read-only, stdlib-only schema-introspection tool — a usable foundation for drift diagnostics.

  Weaknesses

  1. Migration 002 is destructive and currently broken (see §C, §H Phase 0). Applying the documented chain from scratch destroys the opportunities
  table.
  2. No migration 001. The chain begins at 002. git log --all --diff-filter=A over all refs confirms 001_* has never existed.
  3. Duplicate migration number 005 — 005_add_scraped_job_import.sql (tracked) and 005_add_ml_features.sql (stash 338b88e only).
  4. Filename number ≠ chronology. 003 was committed 2025-11-12 (ecb80f1); 002 was committed 2025-11-16 (d305eca) — four days later.
  5. One unnumbered migration — add-sql-practice-tracking.sql has no sequence position.
  6. ~40% of the live schema has no repository artifact (see §D).
  7. Three of six migrations are unapplied, and one of those gaps breaks a shipped API endpoint (see §D).
  8. The documented apply command lacks -bail, which defeats the transaction wrapper (proven in §C).
  9. The runtime database is committed to git (git ls-files -s data/jobs-tracker.db → blob f861637), creating a second, binary "source of truth"
  that merges catastrophically.

  ---
  B. Repository Inventory

  B.1 — Migration files (migrations/, dir mode 700)

  #: —
  File: add-sql-practice-tracking.sql (167 L)
  Purpose: SQL practice tracking
  Creates: table sql_practice_sessions; idx idx_practice_{date,platform,difficulty,correct}; views sql_keyword_mastery, weekly_practice_summary,
  common_practice_mistakes, practice_progress_by_difficulty
  Modifies: —
  Depends on: interview_questions (FK, line 38)
  Idempotent: ✅ yes
  ────────────────────────────────────────
  #: 002
  File: 002_remove_source_constraint.sql (64 L)
  Purpose: Drop source CHECK on opportunities
  Creates: opportunities_migrated→opportunities; trigger update_last_interaction
  Modifies: DROPS opportunities, DROPS trigger update_last_interaction
  Depends on: opportunities, interactions
  Idempotent: ❌ no — destructive
  ────────────────────────────────────────
  #: 003
  File: 003_add_sacred_work_tables.sql (52 L)
  Purpose: Sacred-work log
  Creates: table sacred_work_log; trigger update_sacred_work_timestamp; idx idx_sacred_work_{date,stone}; views sacred_work_progress,
  sacred_work_stats
  Modifies: —
  Depends on: none
  Idempotent: ✅ yes
  ────────────────────────────────────────
  #: 004
  File: 004_add_parliament_decisions.sql (65 L)
  Purpose: Parliament decision tracking
  Creates: table parliament_decisions; 5 indexes
  Modifies: —
  Depends on: scraped_jobs (FK, line 39)
  Idempotent: ✅ yes
  ────────────────────────────────────────
  #: 005
  File: 005_add_scraped_job_import.sql (7 L)
  Purpose: Import provenance column
  Creates: column opportunities.scraped_job_id
  Modifies: opportunities
  Depends on: opportunities
  Idempotent: ❌ no — bare ALTER TABLE ADD COLUMN
  ────────────────────────────────────────
  #: 006
  File: 006_add_practice_sessions.sql (116 L)
  Purpose: Unified practice sessions
  Creates: table practice_sessions; 5 indexes
  Modifies: —
  Depends on: none (no FK in v1.0)
  Idempotent: ✅ yes

  B.2 — Non-migrations/ schema artifacts

  Location: queries/schema.sql (129 L)
  Purpose: Original bootstrap "v1.0"
  Objects: tables opportunities, interactions, documents; 7 indexes; triggers update_opportunity_timestamp, update_last_interaction; views
  active_pipeline, todays_agenda
  Notes: Covers 3 of 10 live tables. Contains the source CHECK that 002 exists to remove — a conflicting definition.
  ────────────────────────────────────────
  Location: scrapers/remoteok_integration.py:169-220
  Purpose: Runtime bootstrap
  Objects: table scraped_jobs; idx idx_scraped_jobs_{score,classification,date}
  Notes: Executable-code DDL. Sole definition of scraped_jobs.
  ────────────────────────────────────────
  Location: scripts/apply_parliament_migration.sh (99 L)
  Purpose: Runner for 004 only
  Objects: —
  Notes: Hardcodes MIGRATION=migrations/004_.... Interactive read -p prompt (line 55) — not CI-safe. sqlite3 "$DB_PATH" < "$MIGRATION" (line 65), no

  -bail.
  ────────────────────────────────────────
  Location: scripts/setup.sh
  Purpose: Presumed bootstrap
  Objects: —
  Notes: 0 bytes
  ────────────────────────────────────────
  Location: scripts/backup.sh
  Purpose: Presumed backup
  Objects: —
  Notes: 0 bytes
  ────────────────────────────────────────
  Location: scripts/db_inventory.py (~260 L)
  Purpose: Read-only inventory report
  Objects: —
  Notes: Hardcodes expected table/view lists (lines 44-60); self-flags staleness risk at line 254.
  ────────────────────────────────────────
  Location: log-sql-practice.py:180-183
  Purpose: Claimed schema guard
  Objects: —
  Notes: No-op pass. Writes to sql_practice_sessions (line 204) with zero existence check.
  ────────────────────────────────────────
  Location: make-dbeaver-snapshot.sh
  Purpose: DB snapshot
  Objects: —
  Notes: Sets PRAGMA journal_mode=WAL (line 38) — mutates runtime DB config.
  ────────────────────────────────────────
  Location: data/jobs-tracker.db
  Purpose: Runtime database, git-tracked
  Objects: 10 tables, 11 views, 2 triggers, 25 indexes
  Notes: 462 KB binary in version control. Not in .gitignore.
  ────────────────────────────────────────
  Location: stash@{0} → 338b88e:migrations/005_add_ml_features.sql
  Purpose: ML feature engineering
  Objects: table ml_features; 4 cols on scraped_jobs; 6 indexes
  Notes: Never committed to main. Collides with tracked 005.

  B.3 — Test fixtures

  No test creates or modifies schema. All ten scripts in tests/ are read/DML-only assertions against a pre-existing database:
  - tests/test-sql-practice-system.sh:21,31 — asserts sql_practice_sessions + 4 views exist.
  - tests/validate-system.sh:3 — counts tables; asserts nothing specific.
  - tests/run-all-tests.sh:284 — asserts the .db file exists.
  - tests/test-new-features.sh:244, tests/test-complete-system.sh:111 — DELETE against the live DB (no fixture isolation).

  B.4 — Documentation

  ┌───────────────────────────────────┬────────────────────────────────────────────────────────────┬───────────────────────────────────────────┐
  │             Location              │                           Claim                            │                  Status                   │
  ├───────────────────────────────────┼────────────────────────────────────────────────────────────┼───────────────────────────────────────────┤
  │ README.md:523-533                 │ "Create migration file … sqlite3 data/jobs-tracker.db <    │ ⚠️ Unsafe pattern (no -bail); example     │
  │                                   │ migrations/003_your_feature.sql"                           │ number 003 is already taken               │
  ├───────────────────────────────────┼────────────────────────────────────────────────────────────┼───────────────────────────────────────────┤
  │ README.md:240-244                 │ Lists migrations/ as containing only 002_...               │ ❌ Stale — 6 files exist                  │
  ├───────────────────────────────────┼────────────────────────────────────────────────────────────┼───────────────────────────────────────────┤
  │                                   │ scraped_jobs schema with slug, position, logo_url, score,  │ ❌ Wrong — live columns are external_id,  │
  │ README.md:456-505                 │ fit_classification                                         │ job_title, job_url, match_score,          │
  │                                   │                                                            │ classification                            │
  ├───────────────────────────────────┼────────────────────────────────────────────────────────────┼───────────────────────────────────────────┤
  │ README.md:518                     │ View archived_pipeline                                     │ ❌ Does not exist in repo or runtime      │
  ├───────────────────────────────────┼────────────────────────────────────────────────────────────┼───────────────────────────────────────────┤
  │ docs/SYSTEM_SUMMARY.md:114-116,   │ Same stale listing + same unsafe apply pattern             │ ❌ Stale                                  │
  │ 966-978                           │                                                            │                                           │
  ├───────────────────────────────────┼────────────────────────────────────────────────────────────┼───────────────────────────────────────────┤
  │ CHANGELOG.md:280                  │ "Created migration file                                    │ ✅ Accurate                               │
  │                                   │ migrations/add-sql-practice-tracking.sql"                  │                                           │
  ├───────────────────────────────────┼────────────────────────────────────────────────────────────┼───────────────────────────────────────────┤
  │ CLAUDE.md,                        │ —                                                          │ Contain no migration policy (grep -rn     │
  │ .claude/settings.local.json       │                                                            │ "migrat" → no match)                      │
  └───────────────────────────────────┴────────────────────────────────────────────────────────────┴───────────────────────────────────────────┘

  ---
  C. Dependency Analysis

  C.1 — Intended vs. actual sequence

  Filename ordering implies 002 → 003 → 004 → 005 → 006, with add-sql-practice-tracking.sql and queries/schema.sql unpositioned. Commit chronology
  contradicts this:

  ┌───────┬─────────────────┬────────────┬────────────────────────────────────────────────────────────────┐
  │ Order │     Commit      │    Date    │                            Artifact                            │
  ├───────┼─────────────────┼────────────┼────────────────────────────────────────────────────────────────┤
  │ 1     │ 7067085         │ 2025-10-31 │ queries/schema.sql                                             │
  ├───────┼─────────────────┼────────────┼────────────────────────────────────────────────────────────────┤
  │ 2     │ 09450f0         │ 2025-11-01 │ (learning tables — binary .db only, no SQL)                    │
  ├───────┼─────────────────┼────────────┼────────────────────────────────────────────────────────────────┤
  │ 3     │ ecb80f1         │ 2025-11-12 │ 003_add_sacred_work_tables.sql + add-sql-practice-tracking.sql │
  ├───────┼─────────────────┼────────────┼────────────────────────────────────────────────────────────────┤
  │ 4     │ d305eca         │ 2025-11-16 │ 002_remove_source_constraint.sql ← out of order                │
  ├───────┼─────────────────┼────────────┼────────────────────────────────────────────────────────────────┤
  │ 5     │ ffbd8a8         │ 2025-11-19 │ 004_add_parliament_decisions.sql                               │
  ├───────┼─────────────────┼────────────┼────────────────────────────────────────────────────────────────┤
  │ 6     │ 338b88e         │ (stash)    │ 005_add_ml_features.sql ← never on main                        │
  ├───────┼─────────────────┼────────────┼────────────────────────────────────────────────────────────────┤
  │ 7     │ 6e655c1         │ 2026-07-15 │ 005_add_scraped_job_import.sql ← number collision              │
  ├───────┼─────────────────┼────────────┼────────────────────────────────────────────────────────────────┤
  │ 8     │ a90dcde→f29c31c │ 2026-08-03 │ 006_add_practice_sessions.sql                                  │
  └───────┴─────────────────┴────────────┴────────────────────────────────────────────────────────────────┘

  Are migrations cumulative? No. They are a partial, non-cumulative overlay on an undocumented baseline. queries/schema.sql produces only 3 of the
  10 live tables; nothing in the chain produces interview_questions, study_topics, learning_sessions, or job_sources.

  Expected baseline: queries/schema.sql is the only plausible root, but it is provably insufficient — 004 assumes scraped_jobs, which schema.sql
  never creates and which only exists because scrapers/remoteok_integration.py was executed at some point.

  C.2 — Dependency graph

                       queries/schema.sql  ──────┐   (opportunities, interactions, documents)
                                                 │
     [NO ARTIFACT — binary commit 09450f0] ──────┤   (interview_questions, study_topics,
                                                 │    learning_sessions, learning_gaps,
                                                 │    study_priority)
     [NO ARTIFACT — job_sources origin]  ────────┤
                                                 │
     scrapers/remoteok_integration.py:169 ───────┤   (scraped_jobs + 3 indexes)
                                                 │
                                ── implicit baseline ──
                                      │       │       │
          ┌───────────────────────────┘       │       └──────────────┐
          ▼                                   ▼                      ▼
     002 (opportunities)               add-sql-practice          004 (needs
     ⚠ DESTRUCTIVE                     (needs interview_             scraped_jobs)
     ⚠ drops idx_status,                questions FK)             ✗ UNAPPLIED
       idx_discovered_date,            ✅ APPLIED
       idx_remote, idx_priority,
       trigger update_opportunity_timestamp
     ✅ APPLIED (historically)
          │
          ▼
     005_add_scraped_job_import (needs opportunities)     003 (standalone)   006 (standalone)
     ✗ UNAPPLIED  →  BREAKS api-server.py:520             ✅ APPLIED         ✗ UNAPPLIED

     005_add_ml_features  [stash only, number collision, never applied]

  C.3 — Duplicate and conflicting definitions

  Object: opportunities
  Definition A: queries/schema.sql:4-31 (with source CHECK)
  Definition B: 002_...sql:12-42 (without CHECK)
  Conflict: Direct conflict. Live data proves B is required: job_sources contains Wellfound, AngelList, Indeed, TestDevJobs, TestSource123;
  opportunities.source contains Wellfound and Indeed — both rejected by A's CHECK.
  ────────────────────────────────────────
  Object: update_last_interaction
  Definition A: queries/schema.sql:85-90
  Definition B: 002_...sql:56-62
  Conflict: Duplicate, textually equivalent
  ────────────────────────────────────────
  Object: Practice-session model
  Definition A: add-sql-practice-tracking.sql → sql_practice_sessions
  Definition B: 006_...sql → practice_sessions
  Conflict: Competing designs. See §E.
  ────────────────────────────────────────
  Object: Migration slot 005
  Definition A: 005_add_scraped_job_import.sql
  Definition B: 005_add_ml_features.sql (stash)
  Conflict: Number collision
  ────────────────────────────────────────
  Object: scraped_jobs schema
  Definition A: remoteok_integration.py:179-200
  Definition B: README.md:490-502
  Conflict: Documentation contradicts code on every column name

  C.4 — Destructive operations

  Only 002 is destructive: DROP TRIGGER update_last_interaction (line 9), DROP TABLE opportunities (line 49), ALTER TABLE … RENAME (line 52), with
  PRAGMA foreign_keys=OFF (line 4).

  Critical defect — verified empirically. Applying queries/schema.sql then 002 to a fresh database on SQLite 3.45.1:

  $ sqlite3 fresh.db < queries/schema.sql          # ok
  $ sqlite3 fresh.db < migrations/002_remove_source_constraint.sql
  Runtime error near line 51: error in view active_pipeline: no such table: main.opportunities

  $ sqlite3 fresh.db "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'opportunit%';"
  opportunities_migrated

  The database is left with no opportunities table at all. Root cause: since SQLite 3.25, ALTER TABLE … RENAME rewrites references inside views;
  view active_pipeline still points at the just-dropped opportunities, so the rename aborts. Contributing factors:

  - PRAGMA legacy_alter_table=ON makes it succeed (verified: table opportunities present) — meaning 002 silently depends on pre-3.25 semantics that
  the file never declares.
  - The BEGIN/COMMIT wrapper does not protect you under the documented command. The sqlite3 CLI continues past errors unless -bail is passed, so it
  reaches COMMIT and persists the broken state. Verified: with -bail, the transaction rolls back and opportunities survives intact. README.md:532
  and apply_parliament_migration.sh:65 both omit -bail.
  - Also destructive by omission: 002 recreates update_last_interaction but not update_opportunity_timestamp, and recreates none of idx_status,
  idx_discovered_date, idx_remote, idx_priority.

  C.5 — Idempotency summary

  ┌───────────────────────────┬─────────────┬────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │         Migration         │ Re-runnable │                                             Mechanism                                              │
  ├───────────────────────────┼─────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ add-sql-practice-tracking │ ✅          │ IF NOT EXISTS throughout                                                                           │
  ├───────────────────────────┼─────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 002                       │ ❌          │ Unguarded CREATE TABLE opportunities_migrated + DROP TABLE; second run destroys data               │
  ├───────────────────────────┼─────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 003                       │ ✅          │ IF NOT EXISTS throughout                                                                           │
  ├───────────────────────────┼─────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 004                       │ ✅          │ IF NOT EXISTS throughout                                                                           │
  ├───────────────────────────┼─────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 005 (import)              │ ❌          │ Bare ALTER TABLE ADD COLUMN → duplicate column name on re-run                                      │
  ├───────────────────────────┼─────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 006                       │ ✅          │ IF NOT EXISTS + transaction                                                                        │
  ├───────────────────────────┼─────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ 005 (ml, stash)           │ ⚠️ partial  │ Table/indexes guarded; 4× ALTER TABLE ADD COLUMN unguarded — the file admits this in its own       │
  │                           │             │ comment                                                                                            │
  └───────────────────────────┴─────────────┴────────────────────────────────────────────────────────────────────────────────────────────────────┘

  ---
  D. Repository Drift Report

  D.1 — Runtime state (data/jobs-tracker.db, 462,848 bytes, WAL, user_version=0)

  10 tables · 11 views · 2 triggers · 25 indexes.

  ┌───────────────────────────────────────────────┬──────┐
  │                     Table                     │ Rows │
  ├───────────────────────────────────────────────┼──────┤
  │ scraped_jobs                                  │ 77   │
  ├───────────────────────────────────────────────┼──────┤
  │ opportunities                                 │ 12   │
  ├───────────────────────────────────────────────┼──────┤
  │ interview_questions                           │ 12   │
  ├───────────────────────────────────────────────┼──────┤
  │ job_sources                                   │ 10   │
  ├───────────────────────────────────────────────┼──────┤
  │ sql_practice_sessions                         │ 7    │
  ├───────────────────────────────────────────────┼──────┤
  │ study_topics                                  │ 5    │
  ├───────────────────────────────────────────────┼──────┤
  │ interactions                                  │ 3    │
  ├───────────────────────────────────────────────┼──────┤
  │ documents, learning_sessions, sacred_work_log │ 0    │
  └───────────────────────────────────────────────┴──────┘

  D.2 — In repository, MISSING from runtime (unapplied migrations)

  ┌──────────────────────────────────┬────────┬─────────────────────────────────────────────────────────────────────────────────────────────────┐
  │          Missing object          │ Source │                                             Impact                                              │
  ├──────────────────────────────────┼────────┼─────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ table parliament_decisions + 5   │ 004    │ Migration 004 never applied. scripts/apply_parliament_migration.sh exists but was never         │
  │ indexes                          │        │ successfully run. No consumer code references the table, so impact is latent.                   │
  ├──────────────────────────────────┼────────┼─────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ column                           │ 005    │ ACTIVE PRODUCTION BREAKAGE.                                                                     │
  │ opportunities.scraped_job_id     │        │                                                                                                 │
  ├──────────────────────────────────┼────────┼─────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ table practice_sessions + 5      │ 006    │ Migration 006 never applied. No consumer code yet.                                              │
  │ indexes                          │        │                                                                                                 │
  └──────────────────────────────────┴────────┴─────────────────────────────────────────────────────────────────────────────────────────────────┘

  Evidence of active breakage. api-server.py:508-553 implements _handle_import_scraped_job; line 520 executes SELECT id FROM opportunities WHERE
  scraped_job_id = ?, and line 535 inserts into that column. Replaying that query against the live database:

  $ sqlite3 data/jobs-tracker.db "SELECT id FROM opportunities WHERE scraped_job_id = 1;"
  Error: in prepare, no such column: scraped_job_id

  The scraped-job import endpoint — the entire deliverable of commit 6e655c1 — cannot execute. Consistent with the data: all 77 rows in scraped_jobs
  have imported_to_opportunities = 0. The feature has never successfully run.

  D.3 — In runtime, MISSING from repository (orphan schema — no SQL artifact anywhere)

  ┌────────────────────────────────┬───────┬────────────────────────────────────────────────────────────────────────────────────────────────────┐
  │         Orphan object          │ Type  │                                               Origin                                               │
  ├────────────────────────────────┼───────┼────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ interview_questions + 4        │ table │ commit 09450f0 (2025-11-01), binary .db diff only                                                  │
  │ indexes                        │       │                                                                                                    │
  ├────────────────────────────────┼───────┼────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ study_topics + 2 indexes       │ table │ same                                                                                               │
  ├────────────────────────────────┼───────┼────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ learning_sessions + 2 indexes  │ table │ same                                                                                               │
  ├────────────────────────────────┼───────┼────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ learning_gaps                  │ view  │ same                                                                                               │
  ├────────────────────────────────┼───────┼────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ study_priority                 │ view  │ same                                                                                               │
  ├────────────────────────────────┼───────┼────────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ job_sources                    │ table │ Evidence not found in repository — no CREATE TABLE job_sources in any tracked file or any          │
  │                                │       │ reachable commit                                                                                   │
  └────────────────────────────────┴───────┴────────────────────────────────────────────────────────────────────────────────────────────────────┘

  git show --name-status 09450f0 lists M api-server.py, M data/jobs-tracker.db, A learning-dashboard.html — and no .sql file. The schema was
  authored directly against the database (plausibly via DBeaver; make-dbeaver-snapshot.sh was added in the following commit 1c44e57).

  These orphans are not obscure: api-server.py queries learning_gaps (line 102), study_priority (line 107), interview_questions (lines 114, 299),
  and job_sources (lines 209, 401). CLAUDE.md names interview_questions, study_topics, and learning_gaps as core project tables. Four of the ten
  live tables, and two of the eleven live views, cannot be recreated from this repository.

  D.4 — Silent regressions (objects lost by migration 002, never restored)

  ┌──────────────────────────────────────┬──────────────────────────┬─────────────────────┐
  │             Lost object              │       Declared in        │       Status        │
  ├──────────────────────────────────────┼──────────────────────────┼─────────────────────┤
  │ trigger update_opportunity_timestamp │ queries/schema.sql:79-83 │ Absent from runtime │
  ├──────────────────────────────────────┼──────────────────────────┼─────────────────────┤
  │ index idx_status                     │ queries/schema.sql:70    │ Absent              │
  ├──────────────────────────────────────┼──────────────────────────┼─────────────────────┤
  │ index idx_discovered_date            │ queries/schema.sql:71    │ Absent              │
  ├──────────────────────────────────────┼──────────────────────────┼─────────────────────┤
  │ index idx_remote                     │ queries/schema.sql:72    │ Absent              │
  ├──────────────────────────────────────┼──────────────────────────┼─────────────────────┤
  │ index idx_priority                   │ queries/schema.sql:73    │ Absent              │
  └──────────────────────────────────────┴──────────────────────────┴─────────────────────┘

  $ sqlite3 data/jobs-tracker.db "PRAGMA index_list(opportunities);"
  (no rows)

  The opportunities table — the central entity, queried on status, is_remote, and priority at api-server.py:47-50 — has zero indexes.

  The lost trigger is a live correctness bug, confirmed by probe on a copy:

  before: id=1  updated_at=2025-11-14 15:49:47
          UPDATE opportunities SET notes='audit-probe' WHERE id=1;
  after:  id=1  updated_at=2025-11-14 15:49:47   ← unchanged

  opportunities.updated_at is dead. active_pipeline orders by o.updated_at DESC (schema.sql:110) and api-server.py:92 consumes it — pipeline
  ordering is silently stale.

  D.5 — Incompatible definitions

  queries/schema.sql's opportunities (with source CHECK) is incompatible with live data. Restoring schema.sql as-is would reject existing rows with
  source IN ('Wellfound','Indeed').

  D.6 — Intentional evolution vs. accidental drift

  ┌───────────────────────────────────┬─────────────────┬──────────────────────────────────────────────────────────────────────────────────────┐
  │            Difference             │     Verdict     │                                        Basis                                         │
  ├───────────────────────────────────┼─────────────────┼──────────────────────────────────────────────────────────────────────────────────────┤
  │ source CHECK removed              │ Intentional     │ Purpose-built migration 002 + job_sources table + CHANGELOG:75                       │
  ├───────────────────────────────────┼─────────────────┼──────────────────────────────────────────────────────────────────────────────────────┤
  │ scraped_jobs exists without a     │ Intentional but │ Deliberate create_scraped_jobs_table(); wrong layer                                  │
  │ migration                         │  misplaced      │                                                                                      │
  ├───────────────────────────────────┼─────────────────┼──────────────────────────────────────────────────────────────────────────────────────┤
  │ Learning tables absent from repo  │ Accidental      │ Schema authored in a GUI; never back-filled to SQL                                   │
  │                                   │ drift           │                                                                                      │
  ├───────────────────────────────────┼─────────────────┼──────────────────────────────────────────────────────────────────────────────────────┤
  │ job_sources absent from repo      │ Accidental      │ No artifact, no explanation anywhere                                                 │
  │                                   │ drift           │                                                                                      │
  ├───────────────────────────────────┼─────────────────┼──────────────────────────────────────────────────────────────────────────────────────┤
  │ 004 unapplied                     │ Accidental      │ A runner was written specifically for it (apply_parliament_migration.sh) — intent    │
  │                                   │                 │ was clearly to apply                                                                 │
  ├───────────────────────────────────┼─────────────────┼──────────────────────────────────────────────────────────────────────────────────────┤
  │ 005 unapplied                     │ Accidental —    │ Consumer code was shipped in the same commit and is broken                           │
  │                                   │ regression      │                                                                                      │
  ├───────────────────────────────────┼─────────────────┼──────────────────────────────────────────────────────────────────────────────────────┤
  │ 006 unapplied                     │ Ambiguous       │ Committed hours ago; no consumer exists. Consistent with in-flight work              │
  ├───────────────────────────────────┼─────────────────┼──────────────────────────────────────────────────────────────────────────────────────┤
  │ update_opportunity_timestamp + 4  │                 │ 002 explicitly restores one trigger (line 8: "Drop trigger that references           │
  │ indexes lost                      │ Accidental      │ opportunities"), showing the author tracked triggers — and simply missed the second  │
  │                                   │                 │ one and all four indexes                                                             │
  ├───────────────────────────────────┼─────────────────┼──────────────────────────────────────────────────────────────────────────────────────┤
  │ Runtime DB committed to git       │ Accidental      │ 16a3f25 "stop tracking SQLite runtime files" removed only -shm/-wal; the .db itself  │
  │                                   │                 │ remains tracked and is not in .gitignore                                             │
  └───────────────────────────────────┴─────────────────┴──────────────────────────────────────────────────────────────────────────────────────┘

  ---
  E. Practice Sessions Evolution Report

  E.1 — Historical reconstruction

  Phase 1 — Origin (2025-11-03, commit ecb80f1). migrations/add-sql-practice-tracking.sql introduces sql_practice_sessions: a SQL-only,
  tightly-constrained model. platform is NOT NULL CHECK IN ('sql-practice.com','programiz','dbeaver','other'); database_used CHECK IN
  ('Hospital','Northwind','Custom','None'); difficulty CHECK IN ('Easy','Medium','Hard'); FK related_question_id → interview_questions(id). Fields
  are SQL-specific by name: my_query, correct_query, keywords_used. Ships with 4 dependent views. Applied — present in runtime with all 4 indexes
  and all 4 views.

  Phase 2 — Accumulation (2025-11-03 → 2025-11-06). 7 rows written across two days via log-sql-practice.py. Consumers built: api-server.py:134,147,
  queries/weekly-practice-summary.sql, tests/test-sql-practice-system.sh, docs/guides/SQL_PRACTICE_GUIDE.md.

  Phase 3 — Generalization attempt v0 (2026-08-03, commit a90dcde). 006_add_practice_sessions.sql introduces practice_sessions, a domain-agnostic
  model. Renames my_query→my_solution, correct_query→correct_solution, keywords_used→concepts_used. Adds domain and source. Drops database_used.
  Initially more constrained than its predecessor: NOT NULL on practice_date, created_at, source, domain, question_text, my_solution, is_correct;
  CHECK on source, domain, difficulty; FK related_opportunity_id → opportunities(id) ON DELETE SET NULL.

  Phase 4 — Deliberate deconstraining v1.0 (2026-08-03, commit f29c31c). Commit message: "refine practice sessions migration after schema
  validation." The diff strips every NOT NULL, every CHECK, the FK, the related_opportunity_id column, and its index. BOOLEAN→INTEGER. A rationale
  block is added to the header:

  ▎ "No CHECK constraints in v1. No FOREIGN KEY relationships in v1. Validation will be driven by usage before introducing stricter schema
  ▎ constraints."

  E.2 — Why two competing designs exist

  This is not accidental duplication. The header of 006 states the intent explicitly (line 15): "Existing sql_practice_sessions remains unchanged."
  Two forces are in tension:

  1. Scope: sql_practice_sessions is hardwired to SQL. The stated goal is "SQL, Python, ETL, Data Warehouse, AI Quality, System Design and other
  learning domains" — unreachable without renaming columns and dropping the database_used CHECK.
  2. Constraint philosophy: v1's tight CHECK lists were written before the practice data existed. Live data already strains them — keywords_used
  contains 'concat', 'where, year', 'max, where' (lowercase, free-form) against a design that expected canonical SQL keywords. The Phase 3→4
  reversal is a direct response.

  E.3 — Canonical structure and migration relationship

  practice_sessions (migration 006) is the intended canonical structure: superset scope, cleaner naming, explicitly forward-looking.

  Does 006 supersede previous implementations? Not yet — it is additive-only. Evidence: 006 creates a new table and touches nothing else; the header
  disclaims any change to sql_practice_sessions; no INSERT INTO practice_sessions SELECT … FROM sql_practice_sessions exists; no view is repointed;
  no consumer references practice_sessions (grep across *.py, *.js, *.html, *.sh → matches only in the migration itself). All 4 legacy views still
  read sql_practice_sessions. The repository currently contains a replacement schema with no replacement path.

  E.4 — Data compatibility

  ┌─────────────────────────────────────────────────────────────────────────────┬──────────────────┬────────────────────────────────────────────┐
  │                                Source column                                │  Target column   │                  Lossless                  │
  ├─────────────────────────────────────────────────────────────────────────────┼──────────────────┼────────────────────────────────────────────┤
  │ id, practice_date, created_at, platform, question_text, is_correct,         │ identical names  │ ✅                                         │
  │ difficulty, time_spent_minutes, error_made, lesson_learned, notes           │                  │                                            │
  ├─────────────────────────────────────────────────────────────────────────────┼──────────────────┼────────────────────────────────────────────┤
  │ my_query                                                                    │ my_solution      │ ✅ rename                                  │
  ├─────────────────────────────────────────────────────────────────────────────┼──────────────────┼────────────────────────────────────────────┤
  │ correct_query                                                               │ correct_solution │ ✅ rename                                  │
  ├─────────────────────────────────────────────────────────────────────────────┼──────────────────┼────────────────────────────────────────────┤
  │ keywords_used                                                               │ concepts_used    │ ✅ rename                                  │
  ├─────────────────────────────────────────────────────────────────────────────┼──────────────────┼────────────────────────────────────────────┤
  │ database_used                                                               │ no target        │ ⚠️ would be lost — 6 of 7 rows carry a     │
  │                                                                             │                  │ value (Hospital×4, None, Northwind)        │
  ├─────────────────────────────────────────────────────────────────────────────┼──────────────────┼────────────────────────────────────────────┤
  │ related_question_id                                                         │ no target        │ ✅ no loss in practice — all 7 rows are    │
  │                                                                             │                  │ NULL                                       │
  ├─────────────────────────────────────────────────────────────────────────────┼──────────────────┼────────────────────────────────────────────┤
  │ —                                                                           │ domain           │ needs backfill; constant 'SQL' is correct  │
  │                                                                             │                  │ for all 7 rows                             │
  ├─────────────────────────────────────────────────────────────────────────────┼──────────────────┼────────────────────────────────────────────┤
  │ —                                                                           │ source           │ needs backfill; 'Practice' matches v0's    │
  │                                                                             │                  │ intended default                           │
  └─────────────────────────────────────────────────────────────────────────────┴──────────────────┴────────────────────────────────────────────┘

  Verdict: migration is lossless for 7 of 7 rows on 8 of 9 populated columns, with one genuine gap. database_used has no destination. It is fully
  recoverable into notes or concepts_used, but only if the migration is written to do so — nothing currently does. Volume is trivial (7 rows), so
  risk is low; the loss would be silent, which is the actual hazard.

  E.5 — Canonical recommendation for practice sessions

  Adopt practice_sessions as canonical, but treat migration 006 as incomplete. It is a schema-creation step masquerading as a replacement. Before
  sql_practice_sessions can be retired, three artifacts that do not exist are required: (1) a data-migration step including a database_used
  destination, (2) redefinition of the 4 dependent views against the new table, (3) updates to api-server.py:134,147, log-sql-practice.py:204,234,
  queries/weekly-practice-summary.sql, and tests/test-sql-practice-system.sh. Until those exist, retaining both tables is correct — but that state
  must be time-boxed, not permanent.

  ---
  F. Canonical Schema Recommendation

  F.1 — Candidate evaluation

  ┌────────────────────────────────┬─────────────────┬──────────────────────────────────────────────────────────────────────────────────────────┐
  │           Candidate            │    Coverage     │                                         Verdict                                          │
  ├────────────────────────────────┼─────────────────┼──────────────────────────────────────────────────────────────────────────────────────────┤
  │ queries/schema.sql             │ 3/10 tables,    │ ❌ Covers 30% of the schema. Contains a source CHECK that live data violates. Last       │
  │                                │ 2/11 views      │ touched 2025-10-31 — predates 8 of 10 tables.                                            │
  ├────────────────────────────────┼─────────────────┼──────────────────────────────────────────────────────────────────────────────────────────┤
  │                                │ Incomplete +    │ ❌ No 001. Cannot produce interview_questions, study_topics, learning_sessions,          │
  │ Migration chain 002…006        │ broken          │ job_sources, scraped_jobs. Migration 002 destroys opportunities when replayed from       │
  │                                │                 │ scratch (§C.4). Duplicate 005. Order ≠ chronology.                                       │
  ├────────────────────────────────┼─────────────────┼──────────────────────────────────────────────────────────────────────────────────────────┤
  │ Bootstrap code                 │ 1/10 tables     │ ❌ Single table, embedded in an unrelated scraper class.                                 │
  │ (remoteok_integration.py)      │                 │                                                                                          │
  ├────────────────────────────────┼─────────────────┼──────────────────────────────────────────────────────────────────────────────────────────┤
  │ Runtime DB                     │ 10/10 tables,   │ ⚠️ Only artifact describing the actual working system — but it is a 462 KB binary, is    │
  │ data/jobs-tracker.db           │ 11/11 views     │ missing migrations 004/005/006, has lost 1 trigger and 4 indexes, and is unreviewable    │
  │                                │                 │ and unmergeable in git.                                                                  │
  └────────────────────────────────┴─────────────────┴──────────────────────────────────────────────────────────────────────────────────────────┘

  No existing artifact is adequate as-is.

  F.2 — Recommendation

  The single canonical source of truth is the ordered, numbered migration chain in migrations/, re-rooted on a new 001_baseline.sql mechanically
  extracted from the current runtime database.

  One source of truth: migrations/. The runtime DB is the input used once to produce the baseline, then permanently demoted to a build artifact.

  F.3 — Justification from evidence

  1. Only the runtime DB describes the whole system. It is the sole location containing interview_questions, study_topics, learning_sessions,
  job_sources, learning_gaps, and study_priority (§D.3). No amount of repairing schema.sql or the chain recovers these — they must be extracted, and
  the runtime DB is the only place to extract them from.
  2. But the runtime DB cannot itself be canonical. It is provably incomplete relative to committed intent (004/005/006 unapplied, §D.2) and has
  silently lost declared objects (§D.4). §4 of this audit's charter — "do not assume the runtime database is correct" — is vindicated: a schema with
  zero indexes on its primary table and a dead updated_at trigger is not a specification. It is also a binary blob in git that no reviewer can diff
  and no merge can resolve.
  3. A migration chain is the only form that survives the observed failure mode. Every defect in this audit traces to one root cause: schema changes
  with no recorded, ordered, replayable representation. The learning tables were lost to the repo because a GUI wrote them. Migration 005 broke
  production because nothing enforced apply-before-ship. Migration 002 is dangerous because nothing ever replayed it. A numbered chain with a
  history table addresses all three; a golden schema.sql addresses none of them (it re-creates exactly the "edit the definition, forget the deployed
  DB" gap already seen).
  4. The chain must be re-rooted, not patched. Migration 002 in its current form destroys opportunities on replay (§C.4, empirically confirmed) and
  assumes pre-3.25 SQLite semantics it never declares. It cannot be part of a chain intended to run from empty. Folding 002's result into a baseline
  eliminates the most dangerous file in the repository without rewriting it — satisfying the constraint that no SQL be rewritten during
  remediation.
  5. The baseline must be corrected, not copied verbatim. The extract should restore update_opportunity_timestamp and the four opportunities indexes
  (§D.4), since these are declared intent in queries/schema.sql:70-83 and their absence is accidental drift, not evolution.
  6. Retire the competitors explicitly. After the baseline exists: queries/schema.sql becomes historical (move or clearly mark — it will otherwise
  keep being read as authoritative, as README.md:242 already does); create_scraped_jobs_table() in remoteok_integration.py becomes a no-op or an
  assertion; data/jobs-tracker.db is added to .gitignore and git rm --cached'd.

  ---
  G. Migration Framework Requirements

  Architectural requirements only. No implementation.

  G.1 — Migration history table

  - A dedicated table (e.g. schema_migrations) recording, per applied migration: version identifier, filename, SHA-256 of file content, applied-at
  timestamp, execution duration, and applying user/host.
  - Content checksum is required, not optional: migration 006 was edited after being committed (a90dcde→f29c31c). Without a checksum, an
  edited-after-apply migration is undetectable.
  - Must record failures, not only successes — a run that aborted mid-chain must be visible.
  - PRAGMA user_version is insufficient as the sole mechanism: it is a single integer, cannot express the current gap pattern
  (002/003/add-sql-practice applied; 004/005/006 not), and is already 0 in a database with 6 migrations' worth of schema.

  G.2 — Version tracking

  - Strict NNN_description.sql naming; NNN unique, zero-padded, monotonically increasing.
  - Collisions must be a hard error — the repository already contains two 005 files across refs (§B.2).
  - Chain must start at 001. The framework must reject a chain with no 001 rather than silently starting at 002.
  - Filename number is authoritative for ordering; commit date is not (003 predates 002 by 4 days, §C.1).

  G.3 — Discovery mechanism

  - Scan a single configured directory; no hardcoded per-migration paths (contrast apply_parliament_migration.sh:18).
  - Unnumbered files must be either rejected or explicitly ignored with a warning — never silently skipped. add-sql-practice-tracking.sql is
  currently invisible to any ordering scheme.
  - Discovery must be deterministic and independent of filesystem enumeration order.

  G.4 — Ordering rules

  - Apply in ascending numeric order, skipping those recorded in history.
  - Gap policy must be explicit. Define whether an unapplied lower-numbered migration discovered after a higher one has been applied is an error or
  a warning — the current state (004, 005, 006 pending) makes this immediately relevant.
  - Migrations declaring cross-object dependencies (004 → scraped_jobs; add-sql-practice-tracking → interview_questions) should have those
  preconditions checked before execution, not discovered as a runtime error.

  G.5 — Transactional execution

  - Each migration runs in its own transaction; a failure rolls that migration back entirely, and the history row is written in the same transaction
  as the DDL.
  - The runner must abort the entire chain on first error. This is the single highest-value requirement in this document: §C.4 proves that the
  currently documented sqlite3 db < file.sql reaches COMMIT after a fatal error and persists a destroyed schema, while the identical file under
  -bail rolls back cleanly.
  - Migrations must not embed their own BEGIN/COMMIT (006 currently does); transaction control belongs to the runner. Detect and reject embedded
  transaction statements, or define precedence explicitly.
  - Note the SQLite constraint: some PRAGMA statements (foreign_keys, used at 002:4) are no-ops inside a transaction. The framework must define
  where pragmas execute relative to the transaction boundary.

  G.6 — Rollback strategy

  - SQLite supports transactional DDL, so in-run rollback is achievable and should be the primary mechanism.
  - Post-commit down-migrations should be considered optional, not mandatory. Evidence: the only rollback ever authored in this repo (stashed
  005_add_ml_features.sql) documents in its own comments that reversing an ALTER TABLE ADD COLUMN requires a full table rebuild. Mandating
  down-migrations would create more table-rebuild code, and table rebuilds are precisely what produced the 002 disaster.
  - Recommended alternative: mandatory pre-run backup (§G.7) plus forward-only correction migrations.

  G.7 — Failure recovery

  - Automatic timestamped backup of the database file before any chain executes, with the path reported. scripts/backup.sh exists but is 0 bytes —
  this capability is currently absent entirely.
  - On failure: report the failing migration, the SQL statement, the SQLite error, and confirm rollback status.
  - Detect and refuse to proceed on an inconsistent history (checksum mismatch, or a history row marking a prior failure).
  - Since the DB runs in WAL mode, backup must capture a consistent snapshot (SQLite backup API or VACUUM INTO) rather than a raw file copy.

  G.8 — Idempotency

  - The framework guarantees at-most-once execution via the history table; migration authors should not rely on IF NOT EXISTS for safety.
  - However, a documented convention requiring IF NOT EXISTS remains valuable as defence-in-depth, since 2 of 6 current migrations (002, 005) fail
  destructively or noisily on re-run.
  - Requirement: onboarding the existing database must mark 002, 003, and add-sql-practice-tracking as already-applied without executing them (a
  "baseline/stamp" operation). Without this, the first framework run replays 002 and destroys the database.

  G.9 — Startup validation

  - api-server.py currently performs zero validation (line 13 opens the DB and queries immediately). A shipped endpoint has been broken since
  2026-07-15 and no startup path noticed.
  - Requirement: on startup, compare the migration history against discovered migrations and fail loudly on pending migrations, rather than serving
  a 500 at first request.
  - Validation must be a check, not an auto-apply. Auto-applying at startup invites concurrent-runner problems (§H.8).
  - Should also verify that objects the application actually queries exist — the scraped_job_id gap would have been caught immediately.

  G.10 — Logging

  - Per migration: identifier, checksum, start/end timestamp, duration, statement count, outcome.
  - Structured output (machine-parseable) in addition to human output, so CI can assert on it.
  - Log to logs/ alongside existing api-server.log; never only to stdout.
  - No interactive prompts in any code path — apply_parliament_migration.sh:55 uses read -p, which hangs CI.

  G.11 — Diagnostics

  - A status command: applied vs. pending, with checksum-mismatch flags. This state is currently unobtainable.
  - A drift command comparing live sqlite_master against the expected post-chain schema — this would surface the missing
  update_opportunity_timestamp trigger and the four absent opportunities indexes.
  - scripts/db_inventory.py is a viable foundation, but its hardcoded expectation lists (lines 44-60) must be derived from the migration chain
  rather than hand-maintained; the script flags this staleness risk itself at line 254.

  G.12 — Dry-run capability

  - Report exactly which migrations would run, in order, without touching the database.
  - A validation mode that executes the chain against a throwaway copy and reports the resulting schema. Every material defect in this audit — the
  002 destruction, the 005 dependency failure — was surfaced by exactly this technique in under a minute.
  - Dry-run must be the default in CI.

  ---
  H. Implementation Roadmap

  The charter's suggested phasing is sound, with one change: repository cleanup cannot come first. Migration 002 will destroy the database the
  moment a naïve runner touches it, so containment and backup must precede everything.

  Phase 0 — Containment and backup (blocking, do first)

  Implement the missing scripts/backup.sh (0 bytes today) and take a verified snapshot. Add data/jobs-tracker.db to .gitignore and git rm --cached
  it — commit 16a3f25 intended this but removed only -shm/-wal. Add a prominent warning header to 002_remove_source_constraint.sql and to
  README.md:523-533 / docs/SYSTEM_SUMMARY.md:966-978 that the documented sqlite3 db < file pattern is unsafe without -bail. No schema changes in
  this phase.

  Phase 1 — Canonical baseline extraction

  Extract 001_baseline.sql from the runtime database, restoring the accidentally-lost update_opportunity_timestamp trigger and the four
  opportunities indexes. Verify by building a fresh DB from the baseline and diffing sqlite_master against runtime. Move queries/schema.sql to a
  clearly historical location. This is the phase that finally puts interview_questions, study_topics, learning_sessions, and job_sources under
  version control.

  Phase 2 — Chain normalization

  With the baseline absorbing their effects, retire 002_remove_source_constraint.sql and add-sql-practice-tracking.sql from the active chain
  (archive, do not delete). Resolve the 005 collision — the stashed 005_add_ml_features.sql must be either renumbered and committed or explicitly
  abandoned; it is currently recoverable only from stash@{0}. Renumber the survivors into a gapless sequence.

  Phase 3 — Migration history + baseline stamp

  Introduce schema_migrations and stamp the existing database as already-carrying the baseline without executing it. Getting this wrong replays 002.
  This phase must land before any runner is pointed at the real database.

  Phase 4 — Migration runner

  Build to §G. Prove it on a copy first. Then apply the three genuinely-pending migrations (004, 005, 006) — applying 005 is what repairs the broken
  import endpoint at api-server.py:520.

  Phase 5 — Startup validation

  Add pending-migration checks to api-server.py startup and to start-tracker.sh (which currently only checks file existence at line 59).

  Phase 6 — Practice-sessions consolidation

  Only after the framework is trustworthy: write the data migration from sql_practice_sessions to practice_sessions with an explicit destination for
  database_used (§E.4), repoint the 4 dependent views, and update the 5 consumer sites. Retire sql_practice_sessions.

  Phase 7 — CI validation

  Enforce in CI: fresh-DB chain build from 001, dry-run on a runtime copy, checksum verification, numbering/collision lint. Rewrite the interactive
  scripts/apply_parliament_migration.sh or delete it — read -p at line 55 blocks CI.

  Phase 8 — Documentation reconciliation

  Correct README.md:456-505 (the scraped_jobs schema documented there matches no artifact in the system), remove the nonexistent archived_pipeline
  view at README.md:518, refresh the stale migrations/ listings at README.md:242 and docs/SYSTEM_SUMMARY.md:114-116, and record the migration policy
  in CLAUDE.md, which today contains no migration guidance at all.

  ---
  Summary of the four findings that matter most

  1. migrations/002 destroys the opportunities table when the chain is replayed from scratch on SQLite ≥3.25, and the documented apply command
  commits that destruction rather than rolling it back. Empirically confirmed.
  2. Migration 005 was never applied, so a shipped API endpoint has been broken since 2026-07-15. All 77 scraped jobs remain unimported. Empirically
  confirmed.
  3. Four live tables and two live views exist nowhere in the repository — the database cannot be rebuilt from source.
  4. opportunities has zero indexes and a dead updated_at trigger, silently lost to migration 002 and never noticed. Empirically confirmed.
