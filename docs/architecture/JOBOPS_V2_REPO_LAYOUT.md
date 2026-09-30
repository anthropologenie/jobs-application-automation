# JobOps v2 — Repository Layout, Phase Plan and Source Reconnaissance Plan

**Phase:** A (specification only). **Nothing has been moved, deleted or created apart from the Phase A documents and fixtures.**
**Date:** 2026-09-29
**Baseline:** `docs/reports/JOBOPS_ACTIVATION_AUDIT_2026-09-29.md`. The existing suite passes on a scratch copy; 363 tests is the baseline to preserve.

Status legend:

| Status | Meaning |
|---|---|
| **EXISTS** | Present and usable as-is |
| **PARTIAL** | Present; needs extension or refactor |
| **MISSING** | Must be built |
| **STALE** | Present but out of date; update in place later |
| **QUARANTINE** | Keep, but move out of the active path (§6); not deleted |

---

## 1. Target conceptual layout

```
sources/      discovery adapters behind one interface (LinkedIn CLI adapter moves here)
company/      company registry, ATS identities, employer classification
geo/          geo reference data + normalization API (aliases, regions, work arrangement, tz, language, currency)
store/        SQLite access, paths, migration runner, backups, locks
evaluation/   evidence selection (precedence), evaluator, replay, lane derivation
relevance/    JD evidence extraction, capability clusters, title tiers, optional LLM extraction
digest/       daily digest and weekly PARKED digest (Markdown)
ops/          run orchestration, run lock, alerting, retention jobs
policy/       versioned policy artifacts + loader + gate (v0.1 active; v0.2 activated later)
identity/     canonicalization + resolution (L1-L4) feeding requisition assignment
review/       queue building, decisions, (later) UI endpoints
timing/       funnel instrumentation and KPIs
```

## 2. Mapping: target package vs current repository

| Target | Status | Current evidence | Reuse / action |
|---|---|---|---|
| `sources/` | **PARTIAL** | `ingestion/linkedin_cli.py`, `ingestion/pipeline.py` (`LinkedInIngestionPipeline`), `ingestion/rate_limit.py`, `ingestion/config.py`, `ingestion/linkedin-ingestion-0.1.0.json` | Extract a `SourceAdapter` interface from the pipeline (audit B1). LinkedIn becomes adapter #1 **with the OR-08 caps unchanged**. Parameterise `SOURCE_PORTAL` (`ingestion/provenance.py:42`) and the rate-limit state path (`ingestion/pipeline.py:134-135`). Add retry with backoff (audit B3). Do not duplicate `RawSourceStore`/`RunLedger` |
| `company/` | **MISSING** | `company_type_signal` accepted by the normalizer but never populated (audit C2) | New registry (tables in `JOBOPS_V2_DATA_MODEL.md` §2). Reuse `identity.canonical.normalize_company` and `identity/jobops-identity-0.1.0.json` `ats_systems` for slug extraction |
| `geo/` | **MISSING** | Work-mode vocabulary in `policy/jobops-policy-0.1.0.json:132-139`; location normalization in `identity.canonical.normalize_location` (no aliases) | New reference JSON + API (data model §6). The v0.1 vocabulary migrates in. Identity L3 consumes geo aliases (identity ruleset bump) |
| `store/` | **MISSING** | DB paths hard-coded in 4 places; no migration runner (JS-24); `migrations/002-006` + unnumbered file; 004 unapplied; DB tracked in Git | `store/paths.py`, `store/migrate.py`, `store/backup.py`, `store/lock.py` (data model §8–§11) |
| `evaluation/` | **MISSING** | `policy/gate.py` evaluates two hard-coded dimensions (`policy/gate.py:263-269`) | New evidence selector + replay + lane derivation; the gate becomes a data-driven dimension loop (audit D2) |
| `relevance/` | **MISSING** (the obsolete scorer is **QUARANTINE**) | `scrapers/simple_scorer.py`, `data/resume_config.json` | New rules-based extractor for clusters A–F with verbatim spans; optional LLM extraction with `model_id`/`prompt_version`/`content_hash` |
| `digest/` | **MISSING** | — | Daily digest (lanes × newness) and weekly PARKED digest |
| `ops/` | **MISSING** | `start-tracker.sh`, `stop-tracker.sh` (manual); no scheduler (audit A1) | Run orchestration + lock + alerting. **Scheduler activation is a later, separately authorized step** |
| `policy/` | **EXISTS** (v0.1) / v0.2 **draft** | `policy/gate.py`, `normalization.py`, `ruleset.py`, `jobops-policy-0.1.0.json`; draft in `docs/architecture/drafts/` | Keep v0.1 live. P1 adds the dimension loop and activates v0.2 by an authorized copy + version bump. Fix the "up to" parsing (audit C3) in the v0.2 normalizer, leaving v0.1 behaviour replayable |
| `identity/` | **PARTIAL** | L1–L4, host families (Greenhouse/Lever/Ashby/Workday/LinkedIn/RemoteOK), read-only resolver; not called at ingest (audit F1); DR-L3-LOCATION makes aliased locations DISTINCT (F2) | Call it at ingest; add geo aliasing; add the apply-URL → L4 path; prefer employer URL as canonical (NEW-R03) |
| `review/` | **PARTIAL** | Queue, decisions, lanes (`review/jobops-review-0.1.0.json`); CLI + unauthenticated API; no UI; 0 decisions | New lane set (policy spec §7), cap/carry in `queue_state`; decisions move to a table; UI in P4 |
| `timing/` | **PARTIAL** | Funnel counts, NOT_MEASURABLE discipline; no QAY / Interview Yield / review minutes | Extend in P4 |
| `ingestion/` (current) | **PARTIAL** → folds into `sources/` + `evaluation/` | See `sources/` | Move by refactor, not copy. Keep `merge.py` (within-observation merge) |
| `api-server.py` | **STALE** (security) | Binds all interfaces, `CORS *`, unauthenticated writes (audit H2) | P1: localhost bind + token; P4: review endpoints |
| `dashboard/` | **STALE** | No review-queue view; stale tracked PID | P4 review UI (could replace it) |
| `tests/` | **EXISTS** | 363 passing on a scratch copy; tests encode v0.1 behaviour | Keep untouched. Add v0.2 golden-case tests in P1 |
| `tests/fixtures/policy_v02_golden_cases.json` | **EXISTS** (Phase A) | 112 cases | Consumed by P1 tests |

## 3. Implementation phases

Estimates are engineer-days for one person familiar with the repo. **Final application submission stays human-gated in every phase.**

### P0.5 — Policy freeze and specification (this phase)

- **Deliverables:** the Phase A documents, the draft policy, the golden cases, and rulings OR-11 … OR-30.
- **Acceptance:** Phase A §43 checklist. No code change; 363 tests still pass.
- **Remaining owner work:** answer `JOBOPS_V2_OPEN_ITEMS.md` (at minimum OI-001 … OI-005, OI-006, OI-007, OI-009, OI-015, OI-019, OI-020).
- **Effort:** done, plus about 1 hour of owner time.

### P1 — Core architecture (≈ 14–19 days)

**Scope:** source interface · normalization · canonical identity · evidence · policy v0.2 · evaluation · replay · newness · SQLite migration runner · DB out of Git · deterministic queue · run lock · daily digest.

| Work item | Days |
|---|---|
| `store/`: paths, lock, backup rotation, migration runner + baseline adoption (after OI-005) | 2.5 |
| DB out of Git (after OI-005; history purge only after OI-024) | 0.5 |
| v2 core schema migration (`0100_v2_core.sql`) | 1 |
| `sources/` interface + LinkedIn adapter refactor (caps unchanged) + retry/backoff | 2 |
| `geo/` reference data + API + lexicon (WFH, office days, work authorization, regions, tz) | 2 |
| Evidence extraction for the six eligibility dimensions + experience/seniority (rules, verbatim spans) | 2.5 |
| `evaluation/`: evidence precedence (§5 data model), evaluator, replay, lane derivation | 2 |
| Policy v0.2 activation: data-driven gate loop + version bump (authorized session) | 1 |
| Identity at ingest + requisition assignment + newness | 1.5 |
| Deterministic queue (cap/carry only if OI-003/OI-004 ruled) + daily digest | 1 |
| Golden-case test module + v0.1 replay of existing ledger | 1 |

**Acceptance criteria:**
1. The golden cases pass, with `OPEN:` cases skipped.
2. G109/G110 prove F4 cannot occur.
3. Replaying the 2026-08-31 ledger under v0.1 reproduces the recorded verdicts.
4. Re-running an identical fixture set writes 0 new evaluations.
5. A concurrent run exits on the lock.
6. The migration runner refuses 004 and records the baseline.
7. The 363 legacy tests still pass.
8. No network access in any test.

**Manual:** triggering runs (scheduler activation is a separate authorization), all review decisions, all applications.
**Automated:** normalization, identity, evaluation, lanes, digest generation.

### P2 — Discovery (≈ 8–12 days)

**Scope:** employer ATS adapters · public/open sources · existing LinkedIn adapter · source comparison · company registry.

**Pre-conditions:**
- the per-source reconnaissance in §5, recorded **before** each adapter is built;
- OI-027 (Company Radar overlap);
- OI-031 (LinkedIn seeds).

| Work item | Days |
|---|---|
| Company registry + ATS identity capture from any observation | 1.5 |
| Greenhouse, Lever, Ashby adapters (after recon) | 3 |
| Workable, SmartRecruiters, Recruitee adapters (after recon); Workday only if practical | 2–4 |
| Public/open remote boards (after recon) | 1 |
| Optional Apify **export-file import** (no API integration) | 0.5 |
| Source comparison report (candidate-level: unique qualified requisitions, overlap, UNKNOWN rate per dimension) | 1 |

**Acceptance:**
- Recorded-fixture tests for each adapter.
- Cross-source duplicates collapse into one requisition (G106).
- No adapter can raise another source's caps.
- LinkedIn volume stays within OR-08.

**Manual:** watchlist curation, owner confirmation of company classifications.

### P3 — Relevance (≈ 7–10 days)

**Scope:** JD evidence extraction · golden regression set · optional LLM-assisted extraction · employer evidence · global geo/language handling.

| Work item | Days |
|---|---|
| Cluster A–F span extractor + title tiers + experience/seniority signals | 3 |
| Golden relevance set from real JDs (owner-labelled), regression harness | 2 |
| Optional LLM extraction (schema-validated, spans must be verbatim substrings, cached by content hash) | 2–3 |
| Employer-classification evidence signals; language detection with confidence (OI-023) | 1.5 |

**Acceptance:**
- ≥ 90% agreement with owner labels on the golden relevance set.
- Every label cites spans.
- LLM output never sets a verdict directly.

**Manual:** labelling the golden set, confirming classifications.

### P4 — Review (≈ 7–9 days)

**Scope:** review UI · review actions · review timer · queue cap · weekly PARKED digest · application preparation.

| Work item | Days |
|---|---|
| Review UI (lanes × newness, evidence spans rendered as untrusted text) | 3 |
| One-action decide / promote / record-submission flow | 1.5 |
| Review-session timer (owner decision), QAY / Shortlist / Interview Yield | 1.5 |
| Weekly PARKED digest; cap/carry enforcement if OI-003/OI-004 ruled | 0.5 |
| Application preparation helpers (drafts from a **new** AI-engineer master resume; human edits and submits) | 1.5 |

**Acceptance:**
- A full lifecycle runs through one UI path.
- No code path submits anything.
- Yields are reported with sample sizes.

### P5 — Expansion and optimization (≈ 5–8 days, ongoing)

**Scope:** source recall comparison · dedup precision · candidate-level source comparison · freshness · operational monitoring and alerting.

**Acceptance:**
- Dedup precision and recall measured on a labelled pair set.
- Freshness measured as first-seen lag per source.
- Alerts fire on zero-result, rate-limited and adapter errors.

## 4. Manual vs automated responsibilities (end state)

| Always human | Automated |
|---|---|
| Final application submission (permanent) | Discovery within per-source caps |
| Review decisions (ACCEPT/SKIP/DEFER/RESOLVE_UNKNOWN) | Evidence extraction and normalization |
| Owner-confirmed company classifications | Identity/dedup, newness |
| Policy rulings and activation of policy versions | Eligibility evaluation, relevance labels, lanes, ordering |
| Migrations applied to the owner's DB | Digest generation, replay, backups, alerts |
| Watchlist curation (until a ruling says otherwise) | Pre-filled drafts for human editing (P4) |

## 5. Future source reconnaissance plan (NOT performed in Phase A)

No network request was made. For each candidate source, record the following in `docs/architecture/recon/<source>.md` **before** writing an adapter:

| Check | What to record |
|---|---|
| Terms | ToS / API terms: automated access, personal use, redistribution, attribution |
| Access method | Public JSON API / feed / HTML / authenticated API / file export |
| API availability | Endpoint(s), auth, pagination, fields provided (JD body? salary? location? employment type? updated_at?) |
| Rate limits | Documented limits; the self-imposed cap proposed |
| Robots / access constraints | robots.txt disposition for the paths used; login-gating |
| Source freshness | Timestamp precision (date vs datetime), update semantics, closed-posting behaviour |
| Structured data quality | Share of postings with salary, work arrangement, employment type as fields vs free text |
| Duplicate behaviour | Reposting patterns, multiple locations per requisition, stable IDs |
| Country coverage | India / remote-from-India share in a sample |

**Candidate sources, in priority order (spec §31):**

1. **Employer ATS / company career systems.** Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Recruitee, and Workday where practical. The identity layer already parses Greenhouse/Lever/Ashby/Workday URLs.
2. **Public/open job sources.** Remote job boards and open listings, selected after recon.
3. **The existing low-volume LinkedIn adapter.** OR-08 caps and ruling stay in force. There is no broadening, and seed changes need OI-031.
4. **Other sustainable sources.** Naukri stays behind its recon go/no-go (execution plan P2-05); no Naukri scraper.
5. **Apify: optional export-file import only.** It is not a strategic dependency, and there is no API integration.

## 6. Quarantine candidates (identify only; nothing deleted or moved)

| Artifact | Reason | Proposed disposition (later, authorized) |
|---|---|---|
| `scrapers/remoteok_integration.py`, `scrapers/example_usage.py`, `scrapers/view_scraped_jobs.sh`, `scrapers/*.md` | Dormant since 2025-11-14; QA/ETL keyword filter; ungated | Move to `quarantine/legacy_scrapers/`; RemoteOK re-enters only as a `sources/` adapter after recon |
| `scrapers/simple_scorer.py`, `data/resume_config.json`, `data/SCORING_GUIDE.md` | Obsolete QA/ETL composite scorer and config (historical 7-year profile, ₹18L old-semantics, auto-import ≥ 75) | `quarantine/legacy_scoring/`, marked historical |
| `prompts/job_analysis.txt`, `prompts/email_generation.txt` | QA Lead / Test Lead positioning | `quarantine/legacy_prompts/`; new prompts in P4 |
| `data/resumes/Karthik_SR_AI_ML_Test_Lead.docx`, `data/resumes/master_resume.json` | Historical Test Lead / QA positioning | Keep as history; a new AI-engineer master resume is needed before P4 drafting |
| `workflows/*.json` (7 n8n workflows incl. 3 `claude-api-test*`), `docker-compose.yml` | Dormant n8n; compose file holds a literal default password | `quarantine/n8n/`; remove the literal default before any reuse; `data/n8n/` never touched |
| `backup-20251116-103540/` | Stale copy of `scrapers/` + empty nested dir (gitignored) | Delete only by owner decision |
| `api-server.pid`, `dashboard/dashboard.pid` | Stale and tracked despite `*.pid` ignore | `git rm --cached` in P1 |
| `data/jobs-tracker.db.backup*` (8 files) | Unrotated manual backups | Move under the P1 backup rotation directory |
| `scripts/backup.sh`, `scripts/setup.sh` (0 bytes) | Empty | Replace with `store/backup.py` / setup docs |
| `learning-dashboard.html`, `log-sql-practice.py`, `queries/practice/`, `queries/weekly-practice-summary.sql`, `docs/guides/SQL_PRACTICE_GUIDE.md`, `tests/test-sql-practice-system.sh`, `tests/show-practice-summary.sh`, `migrations/006_add_practice_sessions.sql`, `migrations/add-sql-practice-tracking.sql`, `migrations/003_add_sacred_work_tables.sql`, `migrations/004_add_parliament_decisions.sql`; DB tables `interview_questions`, `study_topics`, `learning_sessions`, `practice_sessions`, `sql_practice_sessions`, `sacred_work_log` and their views | Learning / SQL-practice / sacred-work system sharing the repo and DB (audit A4) | Separate repository or `quarantine/learning/` (OI-032). The DB tables move with an export and are dropped from the JobOps DB only by an owner-approved migration |
| `CLAUDE.md` | Frames the repo as a learning system ("9 opportunities", SQL/Python goals) | Rewrite as the JobOps agent brief after OI-032; keep the learning version with the learning artifacts |
| `P0_EXIT_REVIEW.md`, `docs/SYSTEM_SUMMARY.md`, `docs/reports/NEW_FEATURES_REPORT.md`, `docs/reports/SCORER_IMPLEMENTATION_SUMMARY.md`, `docs/reports/TEST_REPORT.md`, `docs/reports/SESSION_CHANGES_SUMMARY.md` | Stale status reports | Mark "historical" in `docs/INDEX.md`; do not edit contents |
| `docs/Career_Strategy_and_Search_Preferences.md` §2/§4 | Superseded by OR-11 … OR-20 | Owner updates the document; the rulings log is the record |
| `ingestion/linkedin-ingestion-0.1.0.json` query seeds | Old QA-era buckets | New config version in P2 (OI-031) |
| `tests/*.sh`, `test-everything.sh`, `tests/last-test-run.log` | Legacy shell tests that start servers or write the DB | `quarantine/legacy_tests/` once pytest covers what they check |

## 7. Security and operational requirements (future; spec §40)

| Requirement | Design reference | Phase |
|---|---|---|
| DB outside Git | Data model §9 | P1 |
| Migrations with history, checksums, backups | Data model §8 | P1 |
| Run locks | Data model §11 | P1 |
| Backup rotation and retention | Data model §11 | P1 |
| Local-only API binding (`127.0.0.1`) | `api-server.py:915` today binds all interfaces | P1 |
| Authentication for write endpoints (token from env, never in Git) | `/api/review-decision`, `/api/import-scraped-job/{id}` | P1 |
| CORS restricted to the local UI origin (not `*`) | `api-server.py:528-530` | P1 |
| Secrets only in `.env` / environment; remove literal defaults from `docker-compose.yml` | Audit H3 | P1 |
| Alerting on zero-results, rate-limited, adapter errors, integrity-check failure | Digest banner + optional notification | P1 (banner) / P5 |
| Audit trail | Append-only evidence/decisions/classifications, `schema_migrations`, run manifests | P1 |
| Prompt-injection-resistant JD handling | JD text is data: never executed, never followed as instructions, no URL inside a JD is fetched. LLM prompts wrap JD in delimiters and require verbatim span output validated as substrings. LLM output is evidence only (RELV-R07) | P3 |
| Immutable evidence and evaluations | Append-only triggers (data model §3) | P1 |
| Provenance on every value | `evidence.source`, `source_url`, `extractor_version`, `content_hash`, raw payload ref | P1 |
| Deterministic evaluation | Pure evaluator, evaluation key, total ordering (data model §4, policy spec §7) | P1 |

---

## 8. Phase B amendment (2026-09-29)

| Target | Status after Phase B |
|---|---|
| `sources/` | PARTIAL — `ObservationInput` + `SourceAdapter` seam only; no adapters |
| `company/` | PARTIAL — classification resolution (owner > registry > text signals); tables in the store |
| `geo/` | EXISTS — place index over the policy's geo tables |
| `store/` | EXISTS — paths, connect, migrate, backup (rotation), run lock, repository |
| `evaluation/` | EXISTS — extraction, selection (F4), engine, lanes, identity resolution, newness, queue, service, v0.1 replay adapter |
| `relevance/` | EXISTS — deterministic labeller v1 |
| `digest/` | PARTIAL — Markdown rendering of daily and weekly PARKED digests; nothing is sent |
| `ops/` | SEAM ONLY — no scheduler (deferred) |
| `_quarantine/` | MANIFEST ONLY — `_quarantine/MANIFEST.md`; nothing moved |

The P1 items still to do after Phase B: scheduler/orchestrator (with the run lock), daily digest file output, API binding/auth hardening, and the owner-authorized move of the runtime data into the v2 DB.
