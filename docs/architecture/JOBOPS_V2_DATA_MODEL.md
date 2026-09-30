# JobOps v2 — Data Model, Evaluation Replay and Storage Design

**Phase:** A — design only. **No DDL in this document has been executed.** The live database has not been touched.
**Date:** 2026-09-29
**Related:** `JOBOPS_V2_OWNER_POLICY_SPEC.md` · `drafts/jobops-policy-0.2.0.draft.json` · `JOBOPS_V2_OPEN_ITEMS.md` (storage approval: OI-005 / R5) · audit `docs/reports/JOBOPS_ACTIVATION_AUDIT_2026-09-29.md` (findings C1, C2, F1–F4, H1–H7)

---

## 1. Principles

1. **Facts are separate from judgments.** Observations and evidence are facts about what a source said. Evaluations are judgments made under a named policy version. A judgment never rewrites a fact, and a newer judgment never rewrites an older one.
2. **Evidence is append-only.** An evidence row is never updated or deleted. A correction is a new row that supersedes the old one.
3. **Three-state discipline is kept** (`policy/normalization.py:102-106`, `NOT_CAPTURED`):
   - *not captured*: no evidence row exists;
   - *stated none*: a row exists with `normalized_value = null` and `state = STATED_NONE`;
   - *stated value*: a row with a value.

   The difference between the first two is a data fact, not a convention.
4. **Everything can be replayed without re-crawling.** Stored evidence is enough to re-evaluate any requisition under any policy version (§4).
5. **Existing abstractions are reused, not duplicated:**
   - `EvidenceItem`, the work-mode and compensation state enums, and `NOT_CAPTURED` (`policy/normalization.py`);
   - `SourceRecord` / `MergedRecord` field provenance (`ingestion/merge.py`);
   - `SourceProvenance`, `RawSourceStore` and `RunLedger` (`ingestion/provenance.py`);
   - identity layers and host families (`identity/`);
   - the machine/human/application separation (`review/queue.py`);
   - timing events (`timing/`).

   §10 maps each one onto v2.

---

## 2. Entities and relationships

```
company 1───* company_ats_identity
company 1───* company_classification (append-only; owner-confirmed rows outrank inferred)
company 1───* requisition
requisition 1───* observation ───* evidence            (evidence also keyed to requisition)
observation *───1 source_run *───1 run
requisition 1───* evaluation  (key: requisition_id + policy_version + evidence_hash)
evaluation  1───* evaluation_dimension
requisition 1───* identity_link (probable/confirmed relationships between requisitions)
requisition 1───* review_decision (human; append-only)      ← data/review/decisions.jsonl today
requisition 1───* submission_event (human-recorded)         ← data/application/submissions.jsonl today
requisition 1───1 queue_state (derived, rebuildable)
fx_snapshot (reference data) · geo reference data (versioned files, see §6)
legacy_link: requisition ↔ scraped_jobs.id / opportunities.id (bridge, read-only to legacy)
```

### 2.1 Field definitions

**company**

| Field | Type | Meaning |
|---|---|---|
| company_id | TEXT PK | `co_<ulid>` |
| canonical_name | TEXT | Display name |
| normalized_name | TEXT UNIQUE | Via `identity.canonical.normalize_company` (legal suffixes stripped, division qualifiers kept) |
| official_domain | TEXT NULL | e.g. `example.com`; evidence-backed |
| employer_type | TEXT | Current classification: PRODUCT, AI_NATIVE, GCC, ENGINEERING_LED, STAFFING, CONSULTANCY, IT_SERVICES, ENTERPRISE_DIRECT, UNKNOWN. **Derived** from `company_classification` (owner-confirmed first) |
| employer_type_evidence | TEXT (JSON) | Pointer to the winning classification row and its evidence IDs |
| india_hiring_evidence | TEXT (JSON) | Evidence IDs showing India hiring or EOR usage |
| created_at / updated_at | TEXT ISO-8601 UTC | |

**company_ats_identity:** `(company_id, ats_type, ats_slug)`, UNIQUE on `(ats_type, ats_slug)`, plus `discovered_via_observation_id` and `verified_at NULL`.

Any source can populate this table. A LinkedIn apply URL that resolves to `boards.greenhouse.io/<slug>` records the slug. **Discovery sources never own company identity.**

**company_classification** (append-only): `classification_id, company_id, classification, basis (INFERRED_FROM_EVIDENCE | REGISTRY_LIST | OWNER_CONFIRMED), evidence_ids JSON, decided_by, decided_at, supersedes NULL`.

**requisition**

| Field | Meaning |
|---|---|
| requisition_id | `req_<ulid>` |
| company_id | FK |
| canonical_title | From the highest-authority observation |
| canonical_url | Employer ATS/company URL when known; otherwise the best L2 canonical URL (NEW-R03) |
| normalized_location | geo reference, e.g. `geo:city:IN-bengaluru` / `geo:remote:worldwide` / `geo:remote:region:APAC` |
| employment_type | Last evaluated normalized value (a denormalized cache; the evaluation is authoritative) |
| canonical_posting_date | Earliest source-stated posting date, with `date_precision` |
| current_status | OPEN / CLOSED_AT_SOURCE / UNKNOWN (closed = not seen for N runs on an authoritative source, where N is a parameter) |
| identity_confidence | DEFINITE / PROBABLE / UNCERTAIN |
| first_seen_at, last_seen_at, source_first_seen_at (JSON per source), date_precision (DATE / TIMESTAMP / NONE), newness_state, newness_confidence | Newness block (§7) |
| created_at / updated_at | |

**observation** (one source sighting; immutable)

| Field | Meaning |
|---|---|
| observation_id | `obs_<ulid>` |
| requisition_id | FK. Assigned by identity resolution; may be re-pointed only by a recorded identity_link decision (never silently) |
| source | e.g. `linkedin-search`, `ats:greenhouse`, `company_site`, `apify_import:<actor>` |
| source_external_id | Namespaced, e.g. `linkedin:4459864135` |
| source_url, apply_url | Verbatim |
| run_id | FK run |
| observed_at | Fetch time (µs, UTC) |
| raw_title, raw_location, raw_salary, raw_employment_type | Verbatim |
| raw_text | JD body, if captured (or a pointer `raw_payload_ref` into the raw store for size) |
| raw_payload_ref | Path into `data/…/raw/<source>/<run_id>/` (existing `RawSourceStore` convention) |
| source_posted_date, source_updated_date | Verbatim, with `date_precision` |
| observation_completeness | FULL_JD / PARTIAL / SEARCH_ONLY |
| content_hash | sha256 of the normalized raw_text (empty-string hash when absent) |

**evidence** (append-only)

| Field | Meaning |
|---|---|
| evidence_id | `ev_<ulid>` |
| requisition_id, observation_id | FKs |
| evidence_type | Dimension-scoped: `geography.work_arrangement`, `geography.office_days`, `geography.region_eligibility`, `geography.work_authorization`, `timezone.requirement`, `language.required`, `language.detected`, `compensation.figure`, `compensation.type`, `employment.type`, `employment.duration`, `relationship.type`, `employer.classification_signal`, `experience.years`, `seniority.title_level`, `relevance.cluster_span`, `title.tier` |
| state | STATED / STATED_NONE (not-captured has no row) |
| source | `jd_body` / `portal_structured_field` / `portal_search_result` / `employer_ats_field` / `owner` / `external` (v0.1 vocabulary plus `employer_ats_field` and `owner`) |
| source_authority_tier | 1 employer ATS / company site · 2 job board with full JD · 3 job-board structured field · 4 search snippet · 5 external benchmark (§5) |
| evidence_class | v0.1 classes (EXPLICIT_POINT, EXPLICIT_RANGE, STRUCTURED_FIELD, JD_STATEMENT, PORTAL_SEARCH_FILTER, NON_NUMERIC_CLAIM, EXTERNAL_BENCHMARK) + `LLM_EXTRACTED_SPAN` |
| source_url | |
| quoted_span | Verbatim; **untrusted data** |
| normalized_value | JSON (e.g. `{"office_days":2,"city":"geo:city:IN-bengaluru"}`) |
| extractor, extractor_version | e.g. `rules:geo@0.2.0`, or `llm:<model_id>/<prompt_version>` |
| extracted_at | |
| content_hash | Hash of the observation text the span came from |
| supersedes_evidence_id | For corrections (extractor bug fixes) |

**evaluation**

| Field | Meaning |
|---|---|
| evaluation_id | `eval_<ulid>` |
| requisition_id | |
| policy_version | e.g. `jobops-policy@0.2.0` |
| evidence_hash | sha256 over the sorted `(evidence_id, content_hash)` pairs **selected** by the precedence procedure (§5) |
| evaluated_at | |
| eligibility_dimensions | JSON `{dim: {verdict, rule_id, reason_code, evidence_id}}` (also normalized into `evaluation_dimension`) |
| eligibility_overall | PASS / UNKNOWN / FAIL |
| relevance_label | STRONG / MODERATE / WEAK / NOT_ASSESSED, with `relevance_evidence` JSON (clusters, spans, title_signal, experience_signal, seniority_signal, confidence, model_id, prompt_version, content_hash) |
| preference_attributes | JSON (`compensation_band`, `employer_preference`) |
| newness_state | Snapshot at evaluation time |
| review_flags | JSON array (flags registry) |
| queue_lane | Lane derived at evaluation time (the daily cap is applied later, in queue_state) |
| evaluator_version | Code version (git SHA of the evaluator package) |
| UNIQUE | `(requisition_id, policy_version, evidence_hash)` |

**review_decision / submission_event:** the existing JSONL schemas (`review/decisions.py`, `timing/submissions.py`) moved into tables unchanged, plus `requisition_id`. They stay append-only and human-authored.

**queue_state** (derived, rebuildable): `requisition_id, lane_effective, entered_review_on, carry_days, parked_by_overflow_on, last_digest_on`.

**fx_snapshot:** `snapshot_id, currency_pair, rate, source, snapshot_date, entered_by, entered_at`, UNIQUE `(currency_pair, snapshot_date, source)`. Design only; the source is OI-030.

**run / source_run:** extends the `RunLedger` manifest: `run_id, started_at, finished_at, terminating_condition, lock_holder_pid`; per source `counts, errors, caps, raw_dir`.

---

## 3. DDL sketch (DESIGN ONLY — not executed)

```sql
-- migrations/0100_v2_core.sql  (numbering: §8)
CREATE TABLE company (
  company_id TEXT PRIMARY KEY, canonical_name TEXT NOT NULL,
  normalized_name TEXT NOT NULL UNIQUE, official_domain TEXT,
  employer_type TEXT NOT NULL DEFAULT 'UNKNOWN', employer_type_evidence TEXT,
  india_hiring_evidence TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);

CREATE TABLE company_ats_identity (
  company_id TEXT NOT NULL REFERENCES company(company_id),
  ats_type TEXT NOT NULL, ats_slug TEXT NOT NULL,
  discovered_via_observation_id TEXT, verified_at TEXT,
  PRIMARY KEY (ats_type, ats_slug));

CREATE TABLE company_classification (
  classification_id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES company(company_id),
  classification TEXT NOT NULL, basis TEXT NOT NULL
    CHECK (basis IN ('INFERRED_FROM_EVIDENCE','REGISTRY_LIST','OWNER_CONFIRMED')),
  evidence_ids TEXT, decided_by TEXT NOT NULL, decided_at TEXT NOT NULL,
  supersedes TEXT REFERENCES company_classification(classification_id));

CREATE TABLE run (
  run_id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT,
  terminating_condition TEXT, manifest_ref TEXT);

CREATE TABLE requisition (
  requisition_id TEXT PRIMARY KEY, company_id TEXT REFERENCES company(company_id),
  canonical_title TEXT, canonical_url TEXT, normalized_location TEXT,
  employment_type TEXT, canonical_posting_date TEXT,
  date_precision TEXT CHECK (date_precision IN ('DATE','TIMESTAMP','NONE')),
  current_status TEXT NOT NULL DEFAULT 'OPEN',
  identity_confidence TEXT NOT NULL DEFAULT 'DEFINITE',
  first_seen_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, source_first_seen_at TEXT,
  newness_state TEXT, newness_confidence TEXT,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE UNIQUE INDEX ux_requisition_canonical_url ON requisition(canonical_url)
  WHERE canonical_url IS NOT NULL;

CREATE TABLE observation (
  observation_id TEXT PRIMARY KEY,
  requisition_id TEXT NOT NULL REFERENCES requisition(requisition_id),
  source TEXT NOT NULL, source_external_id TEXT, source_url TEXT, apply_url TEXT,
  run_id TEXT NOT NULL REFERENCES run(run_id), observed_at TEXT NOT NULL,
  raw_title TEXT, raw_location TEXT, raw_salary TEXT, raw_employment_type TEXT,
  raw_text TEXT, raw_payload_ref TEXT,
  source_posted_date TEXT, source_updated_date TEXT, date_precision TEXT,
  observation_completeness TEXT NOT NULL
    CHECK (observation_completeness IN ('FULL_JD','PARTIAL','SEARCH_ONLY')),
  content_hash TEXT NOT NULL);
CREATE INDEX ix_observation_source_id ON observation(source, source_external_id);

CREATE TABLE evidence (
  evidence_id TEXT PRIMARY KEY,
  requisition_id TEXT NOT NULL REFERENCES requisition(requisition_id),
  observation_id TEXT REFERENCES observation(observation_id),  -- NULL only for source='owner'
  evidence_type TEXT NOT NULL, state TEXT NOT NULL CHECK (state IN ('STATED','STATED_NONE')),
  source TEXT NOT NULL, source_authority_tier INTEGER NOT NULL,
  evidence_class TEXT NOT NULL, source_url TEXT, quoted_span TEXT,
  normalized_value TEXT, extractor TEXT NOT NULL, extractor_version TEXT NOT NULL,
  extracted_at TEXT NOT NULL, content_hash TEXT NOT NULL,
  supersedes_evidence_id TEXT REFERENCES evidence(evidence_id));
CREATE INDEX ix_evidence_req_type ON evidence(requisition_id, evidence_type);
-- Append-only enforcement:
CREATE TRIGGER evidence_no_update BEFORE UPDATE ON evidence
  BEGIN SELECT RAISE(ABORT, 'evidence is append-only'); END;
CREATE TRIGGER evidence_no_delete BEFORE DELETE ON evidence
  BEGIN SELECT RAISE(ABORT, 'evidence is append-only'); END;

CREATE TABLE evaluation (
  evaluation_id TEXT PRIMARY KEY,
  requisition_id TEXT NOT NULL REFERENCES requisition(requisition_id),
  policy_version TEXT NOT NULL, evidence_hash TEXT NOT NULL, evaluated_at TEXT NOT NULL,
  eligibility_dimensions TEXT NOT NULL, eligibility_overall TEXT NOT NULL,
  relevance_label TEXT NOT NULL, relevance_evidence TEXT,
  preference_attributes TEXT, newness_state TEXT, review_flags TEXT,
  queue_lane TEXT NOT NULL, evaluator_version TEXT NOT NULL,
  UNIQUE (requisition_id, policy_version, evidence_hash));
CREATE TRIGGER evaluation_no_update BEFORE UPDATE ON evaluation
  BEGIN SELECT RAISE(ABORT, 'evaluations are immutable'); END;

CREATE TABLE evaluation_dimension (
  evaluation_id TEXT NOT NULL REFERENCES evaluation(evaluation_id),
  dimension TEXT NOT NULL, verdict TEXT NOT NULL, rule_id TEXT NOT NULL,
  reason_code TEXT, evidence_id TEXT REFERENCES evidence(evidence_id),
  PRIMARY KEY (evaluation_id, dimension));

CREATE TABLE identity_link (
  link_id TEXT PRIMARY KEY, requisition_a TEXT NOT NULL, requisition_b TEXT NOT NULL,
  outcome TEXT NOT NULL, layer TEXT, reason_codes TEXT, identity_version TEXT NOT NULL,
  decided_by TEXT NOT NULL, decided_at TEXT NOT NULL, supersedes TEXT);

CREATE TABLE review_decision (/* columns of review/decisions.py Decision.payload + requisition_id */);
CREATE TABLE submission_event (/* columns of timing/submissions.py SubmissionEvent.payload + requisition_id */);
CREATE TABLE queue_state (requisition_id TEXT PRIMARY KEY, lane_effective TEXT NOT NULL,
  entered_review_on TEXT, carry_days INTEGER NOT NULL DEFAULT 0,
  parked_by_overflow_on TEXT, last_digest_on TEXT);
CREATE TABLE fx_snapshot (snapshot_id TEXT PRIMARY KEY, currency_pair TEXT NOT NULL,
  rate REAL NOT NULL, source TEXT NOT NULL, snapshot_date TEXT NOT NULL,
  entered_by TEXT NOT NULL, entered_at TEXT NOT NULL,
  UNIQUE (currency_pair, snapshot_date, source));
CREATE TABLE legacy_link (requisition_id TEXT NOT NULL, legacy_table TEXT NOT NULL
  CHECK (legacy_table IN ('scraped_jobs','opportunities')), legacy_id INTEGER NOT NULL,
  PRIMARY KEY (legacy_table, legacy_id));

-- Convenience view: the current evaluation per requisition under the active policy.
-- (active policy version supplied by the application; SQLite has no session variables)
```

Legacy tables (`scraped_jobs`, `opportunities`, `interactions`, `documents`) are **not altered** by v2. The import bridge (`POST /api/import-scraped-job/{id}`) keeps working. `legacy_link` connects the two worlds.

---

## 4. Evaluation replay

**Key.** `(requisition_id, policy_version, evidence_hash)`.

**Procedure** (`evaluation/replay.py`, P1):

1. Load every non-superseded evidence row for the requisition.
2. Select the evidence per dimension with the precedence procedure (§5).
3. Compute `evidence_hash` over the selected set.
4. If an evaluation with that key already exists, return it. **No second record is written**, which makes evaluation idempotent.
5. Otherwise run the pure evaluator `evaluate(selected_evidence, policy) -> Evaluation` and insert the result in one transaction together with its `evaluation_dimension` rows.

**Replay across versions.** Running step 1–5 with `policy_version = jobops-policy@0.1.0` (through an adapter mapping v2 evidence onto the v0.1 gate input) or `@0.2.0` needs only stored evidence. No source is contacted. Older evaluations are never rewritten (the `evaluation_no_update` trigger enforces this).

**Current evaluation.** The *current* evaluation for a requisition under the active policy is the evaluation whose `evidence_hash` equals the hash of the *currently selected* evidence set. It is unique by construction, and it is **not** "the latest `evaluated_at`".

**Purity.** The evaluator is a pure function of (selected evidence, policy artifact, geo reference version, FX snapshot IDs referenced by evidence). All of these are versioned inputs, so a replay reproduces the result bit for bit, apart from `evaluation_id` and `evaluated_at`.

---

## 5. Evidence precedence and the F4 fix

### 5.1 The defect (audit F4)

Two facts combine:

1. The ingestion pipeline re-gates a posting it already holds using only the search result, which has no description (`ingestion/pipeline.py:327-330, 388-399`).
2. The review ledger treats the latest observation as current (`review/ledger.py:107-110`).

So a PASS based on the JD becomes UNKNOWN on the next run.

### 5.2 Per-dimension selection (EVAL-R02, EVAL-R03, EVAL-R04)

For each `evidence_type` needed by a dimension, the selected evidence is the **first** candidate by this total order:

| Rank | Key | Order |
|---|---|---|
| 0 | Presence | A STATED or STATED_NONE row always beats *no row*. **Absence never displaces presence.** |
| 1 | Owner confirmation (employer classification only, EMPR-R06) | OWNER_CONFIRMED > anything else |
| 2 | `source_authority_tier` | 1 employer ATS / company site > 2 board with full JD > 3 board structured field > 4 search snippet > 5 external benchmark (never gate-admissible for compensation, as in v0.1) |
| 3 | `evidence_class` | explicit statement (JD_STATEMENT, EXPLICIT_POINT/RANGE) > STRUCTURED_FIELD > PORTAL_SEARCH_FILTER > NON_NUMERIC_CLAIM > LLM_EXTRACTED_SPAN (LLM spans must still quote verbatim text) |
| 4 | Observation completeness | FULL_JD > PARTIAL > SEARCH_ONLY |
| 5 | Recency | Newer `observed_at` first, **only among rows tied on ranks 0–4** |
| 6 | Tie-breaker | `evidence_id` ascending |

**Conflict rule (pending OI-019).**
- *Different tiers:* if two STATED rows for the same evidence type from **different** tiers disagree, the higher tier wins and `SOURCE_CONFLICT` is set. The flag is review-routing in the draft.
- *Same tier:* if they come from the **same** tier, disagree, and were observed at different times, recency wins. The requisition is marked `UPDATED`, which covers genuine changes at the employer.
- *Same tier, same time:* the dimension is UNKNOWN with `SOURCE_CONFLICT`. This generalises v0.1 WM-N1.

### 5.3 Why F4 cannot occur

A search-only observation produces evidence rows only for fields it actually carries: title, location string and date. It produces **no** rows for JD-derived evidence types (`geography.office_days`, `compensation.figure`, `relevance.cluster_span`, …). Rank 0 means absence cannot displace the JD-derived rows from the earlier FULL_JD observation.

Could the location string it does carry cause a downgrade? It is `source_authority_tier` 4, so it loses to the tier-2 JD statement at rank 2.

The selected set is therefore unchanged, the `evidence_hash` is unchanged, and step 4 of §4 returns the existing evaluation. The sparse sighting only updates `requisition.last_seen_at` and adds an observation row. Golden case **G109** asserts exactly this, and **G110** covers the reverse order (sparse, then rich: the evaluation upgrades).

This generalises the existing `ingestion/merge.py` invariant — "a record that supplied nothing never displaces one that did" — from within one run to across all runs and sources.

---

## 6. Geo module (design)

**Package:** `geo/`. Reference data is versioned JSON (`geo/geo-reference-0.1.0.json`), not code.

| Component | Content |
|---|---|
| countries | ISO-3166 alpha-2, names, aliases, currency, default languages, timezones |
| cities | `geo:city:<CC>-<slug>` with aliases. Bengaluru aliases: Bengaluru, Bangalore, Bangalore Urban, Bengaluru Urban, Greater Bengaluru Area, Bengaluru East/North/South, plus locality list |
| region groups | WORLDWIDE, EU, EEA, EMEA, APAC, LATAM, NA, UK; membership lists; **APAC membership never implies India eligibility** (GEO-R05) |
| phrase lexicon | remote / hybrid / onsite / office-days patterns ("N days per week in office"), relocation, visa sponsorship, work-authorization patterns ("authorized to work in the United States"), timezone-overlap patterns |
| API | `normalize_location(text) -> GeoRef[]`, `region_contains(region, country) -> bool/None`, `detect_work_arrangement(spans) -> WorkArrangement(mode, office_days, city, evidence)`, `detect_work_authorization(spans)`, `detect_timezone_requirement(spans)`, `currency_for(country)` |

Policy rules consume normalized `GeoRef` / `WorkArrangement` values. The gate contains **no** city strings. Bengaluru is referenced only as `geo:city:IN-bengaluru` in the policy draft.

The v0.1 work-mode vocabulary (`policy/jobops-policy-0.1.0.json:132-139`) migrates into the lexicon. The audit C3 misses ("Work from home", "WFH") are added as REMOTE-context phrases; this is a normalization vocabulary change, reviewed with the ruleset.

## 7. Newness semantics

- **NEW:** the requisition's first observation happened in this run.
- **UPDATED:** a later observation, from the same or a higher authority tier, changed a material field. The draft definition of "material" is title, work arrangement or location, compensation, employment type, or the JD `content_hash` (OI-018). Enrichment of our own evidence alone does not count (OI-017).
- **SEEN_BEFORE:** otherwise.

`date_precision` stops a date-only LinkedIn `date` from being compared as though it were a timestamp. For such same-day sightings, `newness_confidence = LOW`.

**Cross-source resurfacing:** an observation on a new source attaches to the existing requisition. Newness stays SEEN_BEFORE, and `source_first_seen_at[<source>]` records the first sighting on that source.

## 8. Migration runner (design; approval pending OI-005 / R5)

- **Location:** `store/migrate.py`. Migrations live in `migrations/NNNN_description.sql`, where NNNN has four digits. v2 starts at **0100** to stay clear of the legacy `002`–`006` files and the unnumbered `add-sql-practice-tracking.sql`.
- **History table:** `schema_migrations(version TEXT PK, filename, sha256, applied_at, applied_by, duration_ms, backup_ref)`. `PRAGMA user_version` mirrors the highest applied numeric version.
- **Baseline adoption (first run):**
  - Introspect the live schema and write *baseline* rows for legacy migrations already present (002, 003, 005, 006 and add-sql-practice-tracking, each only if its objects exist), marked `applied_by = 'baseline-introspection'`.
  - 004 (`parliament_decisions`) is recorded as **NOT applied** (CONFLICT-2(c)).
  - The runner refuses to apply 004.
- **Per migration:**
  1. Acquire the run lock (§11).
  2. Verify the file's sha256 has not changed since it was recorded.
  3. Take a `sqlite3` backup-API copy.
  4. Run `PRAGMA integrity_check` and `foreign_key_check` before and after.
  5. Execute in `BEGIN IMMEDIATE … COMMIT`.
  6. Write the history row in the same transaction.
- **Forward-only.** Each migration may ship a `NNNN_description.down.sql`, used only by an explicit `--rollback NNNN` owner command. The default recovery path is to restore the pre-migration backup.
- **Authority:** applying a migration to the owner's database needs an explicit owner command. Implementation is P1, contingent on OI-005.

## 9. Runtime database out of Git (design; OI-005, OI-024)

Today `data/jobs-tracker.db` is tracked (CONFLICT-3; audit H1).

**Plan (P1):**
1. Introduce `JOBOPS_DB_PATH`, defaulting to `~/.local/share/jobops/jobops.db`. All modules resolve the path through one `store/paths.py`, replacing the hard-coded `data/jobs-tracker.db` in `ingestion/persistence.py:33`, `identity/index.py:44`, `review/queue.py:67` and `api-server.py:22`.
2. With the owner's command, copy the database using the backup API and verify integrity and row counts.
3. Run `git rm --cached data/jobs-tracker.db` and add `*.db` under `data/` to `.gitignore`.
4. Commit a schema-only snapshot (`store/schema_snapshot.sql`) for review diffs instead.
5. **History purge** (removing earlier DB blobs with personal data from Git history) is a separate, destructive, owner-only decision (OI-024).

Tests that currently read the live DB read-only (`tests/test_p0_07_identity_dedup.py:541, 633, 1092`, etc.) will resolve through the same path helper. Their behaviour is unchanged.

## 10. Mapping existing abstractions onto v2

| Existing | v2 role |
|---|---|
| `policy.normalization.EvidenceItem` (dimension, evidence_class, verbatim_text, source, source_ref, source_fetched_at, extractor_version, posting_stated_at) | Becomes the in-memory form of an `evidence` row; fields map 1:1, plus `evidence_type`, `state`, `source_authority_tier`, `content_hash` |
| `NOT_CAPTURED` sentinel | "No evidence row"; `STATED_NONE` = null key present |
| `NormalizedCompensation` states | Kept; `compensation_type`, `base_or_total`, `fx_*`, `normalized_inr_annual_base` added |
| Work-mode enum REMOTE/HYBRID/ONSITE/AMBIGUOUS/ABSENT | Superseded by `WorkArrangement(mode, office_days, city, region)` from `geo/`. The v0.1 enum stays derivable for v0.1 replay |
| `ingestion.merge.merge_source_records` + `MergedRecord.field_provenance` | Within-observation merge stays (search + detail from one run). Cross-observation selection is §5 |
| `ingestion.provenance.RawSourceStore` / `RunLedger` / `SourceProvenance` | Kept for raw payloads and manifests. `SOURCE_PORTAL` is parameterised per source |
| `identity/` layers L1–L4, host families, ATS parsers | Kept as the identity engine that assigns `observation.requisition_id`. Geo aliasing is added to the L3 location key (identity ruleset bump) |
| `review/decisions.py` DecisionStore | Moved into the `review_decision` table; semantics unchanged |
| `review/queue.py` machine/human/application blocks | Queue built from `evaluation` + `queue_state`; the block separation is kept |
| `timing/` events | Event sources become tables; derived metrics unchanged; Interview Yield and QAY added (P4) |

## 11. Operations: backup, retention, integrity, concurrency, transactions

| Concern | Design |
|---|---|
| Run lock | `fcntl.flock` on `$JOBOPS_STATE/run.lock`. A second run exits 0 with `terminating_condition = locked`. The migration runner, daily run and replay all take it |
| SQLite concurrency | WAL mode, `busy_timeout = 30000`, one writer (the run). The API is read-only except review decisions, which use short `BEGIN IMMEDIATE` transactions |
| Transactional evaluation writes | One transaction per requisition: new observation(s), new evidence rows, optional evaluation plus dimensions, requisition newness fields, queue_state. A failure rolls back all of it; the raw payload stays on disk for retry |
| Backups | Backup-API copy before each run and each migration, into `$JOBOPS_BACKUP_DIR`. Rotation: keep 7 daily, 4 weekly, 3 pre-migration (parameters). Integrity check on every backup |
| Retention | Evidence and evaluations: forever (small). Raw payloads: 180 days by default (parameter), then compressed or archived. LinkedIn raw payloads stay local-only (existing `.gitignore` rule) |
| Integrity | `PRAGMA integrity_check` at run start; append-only triggers; the evaluation UNIQUE key; foreign keys ON |
| Audit trail | `run` manifests, `schema_migrations`, append-only evidence, classification, decision and submission rows, plus `identity_link.decided_by` |

---

## 12. Phase B amendment (2026-09-29): as implemented

- **Schema:** `store/migrations/0100_v2_core.sql` and `store/migrations/0101_legacy_archive.py`. This follows the design above with these additions:
  - `requisition_key` (L1/L2/L4 key index);
  - `requisition.duplicate_of` (suppressed duplicates are kept, never deleted);
  - `evidence.ordinal`, `evidence.strength` (PRIMARY/CONTEXT) and `evidence.extractor_version` (evidence for a new policy version is re-extracted from stored observations; nothing is recrawled);
  - an `application` table (human-recorded events only);
  - `fx_rate` (owner-maintained);
  - `legacy_scraped_job` (archive of pre-v0.2 rows).
- **Migration location:** migrations live in `store/migrations/` (not the legacy `migrations/` directory). The runner is `store/migrate.py` with checksums, BEGIN IMMEDIATE, backup-before-apply, and integrity and foreign-key checks. The legacy DB is refused without `--allow-legacy-db`.
- **Evidence hash:** hashes evidence *content* (type, strength, verbatim span, normalized value) plus classification, FX, identity flags and conflicts. An identical re-sighting therefore reuses the existing evaluation, and a sparse re-sighting cannot change the selected evidence (F4).
- **Runtime DB:** default `data/runtime/jobops.db`, overridable with `JOBOPS_DB_PATH`, gitignored. `data/jobs-tracker.db` is untracked going forward (`git rm --cached`; the file is kept, history is not rewritten).
