# JobOps Activation Audit — 2026-09-29

**Scope:** Read-only architecture audit of `jobs-application-automation`. The only file written is this report. No existing file was modified.
**Method:** I read the source, versioned JSON artifacts, planning docs and tests. I ran the pytest suite, the review-queue report and the timing report, plus pure (DB-free) calls to the policy normalizer. All of these ran against a **scratch copy** of the repository (`data/n8n/`, `.git` and DB backups excluded). The live database was never opened. I ran `sqlite3 -readonly` only on the scratch copy. I made no network calls, searches or scrapes (this also respects the Company Radar Phase 1 rule that the agent performs no discovery).
**Preference authority:** The owner's job-preferences document dated 28 Sep 2026, as supplied in the audit brief. Older repo artifacts are reported against it (§4) and are **not** resolved.
**Tags:** `[verified]` = I confirmed it by reading code or data, or by running something on the scratch copy. `[UNVERIFIED]` = inference, or depends on something I could not inspect.

---

## 1. Executive verdict

JobOps is **not close to active**. P0 built a careful, well-tested evaluation core: 363 tests pass on a scratch copy. But nothing runs unattended. There has been one live ingestion run ever (2026-08-31, 3 postings, 3/3 UNKNOWN), and no human decision or submission has ever been recorded.
**Single biggest blocker: the gate enforces an out-of-date preference policy.** It auto-FAILs every hybrid or on-site role, Bengaluru included. It evaluates only work mode and salary, so it ignores experience, title tier, staffing/consultancy and contract type. It also seeds LinkedIn with QA-era titles. Scheduling it as it stands would automate the wrong filter while still leaving about 100% of candidates for manual review.
**A second, scheduling-specific blocker:** re-running a query re-gates already-held postings *without their JD*, and that weaker verdict becomes the "current" one.
**Shortest safe path (about 9–12 engineer-days):**
1. The owner answers the open questions in §8.
2. Policy v0.2 adds per-criterion PASS/FAIL/UNKNOWN dimensions.
3. Extract a source-adapter seam from the LinkedIn pipeline, then add Greenhouse/Lever/Ashby and "Apify export import" adapters.
4. Wire identity resolution and first-seen tracking into ingestion, and fix the re-gate defect.
5. Run daily under a locked systemd user timer that emits a "new since last run" digest on top of the existing review queue.

---

## 2. Current-state map

| Component | Path | State | Runs unattended? | Evidence |
|---|---|---|---|---|
| Hard eligibility gate (work mode and salary) | `policy/` | Implemented and tested. Invoked only inside an ingestion run and by the import bridge's normalizer | No | `policy/gate.py:261-303`, `api-server.py:30` `[verified]` |
| LinkedIn ingestion (linkedin-search CLI via `bun`) | `ingestion/` | Implemented. **One live run** (2026-08-31, 1 query, 3 postings) | No. Manual CLI, one query per process | `data/ingestion/runs/linkedin-20260831T073639Z-5479.json`; `ingestion/run_linkedin_ingestion.py:151-179` `[verified]` |
| Identity / dedup (L1–L4) | `identity/` | Implemented. Called only while the review queue is being built, **not during ingestion** | No | `review/queue.py:318-329`; no identity import in `ingestion/` `[verified]` |
| Review queue and decisions | `review/`, `/api/review-queue`, `/api/review-decision` | Implemented. **0 decisions ever recorded** (`data/review/` does not exist). No UI: `dashboard/app.js` never calls these endpoints | No | Queue report on the copy: SHORTLIST 0, REVIEW 3, NOT_EVALUATED 75, SUPPRESSED 2 `[verified]` |
| Time instrumentation | `timing/` | Implemented. **0 submissions recorded** (`data/application/` does not exist) | No | Timing report on the copy: `unknown_rate 1.000 (3/3)`; every duration NOT_AVAILABLE `[verified]` |
| API server | `api-server.py` | Not running. `api-server.pid` (3184) is stale and **tracked in git** | No | `ps` shows no process; `git ls-files` `[verified]` |
| Legacy dashboard | `dashboard/` | Not running. `dashboard.pid` (3188) is stale and tracked. It has no review-queue view | No | `[verified]` |
| RemoteOK scraper and `simple_scorer` | `scrapers/` | Dormant. The last RemoteOK row is from 2025-11-14. Not wired to the gate | No | `scraped_jobs` max(scraped_at) for RemoteOK `[verified]` |
| n8n workflows (RemoteOK to JSON files, Claude API tests) | `workflows/`, `docker-compose.yml` | Dormant. No container running. Last JSON output 2025-10-30 | No | `docker ps` is empty; `data/jobs/` `[verified]` |
| Scheduler | none | **Absent.** The user crontab has only an unrelated `adexplain` job; the only systemd user timer is unrelated | — | `crontab -l`, `systemctl --user list-timers` `[verified]` |
| `backup-20251116-103540/` | — | Stale copy of `scrapers/` plus an empty nested directory. Gitignored | — | `[verified]` |
| `__pycache__/`, `.pytest_cache` | — | Build residue. Gitignored | — | `[verified]` |
| `scripts/backup.sh`, `scripts/setup.sh` | — | **0 bytes** | — | `wc -c` `[verified]` |
| `logs/` | — | `api-server.log` and `dashboard.log` are 0 bytes | — | `[verified]` |
| Learning / SQL-practice / "sacred work" / parliament artifacts | `learning-dashboard.html`, `log-sql-practice.py`, `queries/practice/`, tables `sql_practice_sessions`, `sacred_work_*`, `study_topics`, `interview_questions` | Unrelated to discovery. They share the same DB and repo. `CLAUDE.md` still describes the repo as a learning system ("9 opportunities"; the copy has 24) | — | `.tables` on the copy; `CLAUDE.md:6-9` `[verified]` |
| P0 exit status | `P0_EXIT_REVIEW.md` | **Stale.** It says X6–X8 and X10 are "Not implemented" and cites 105 tests. The code now exists and 363 tests pass. No P0 exit is claimed | — | `P0_EXIT_REVIEW.md:55-62` `[verified]` |

---

## 3. Findings A–H

### A. Activation gap

**A1 — BLOCKER — Nothing runs without the owner pressing something.** `[verified]`
There is no cron entry, systemd timer, n8n container or in-repo orchestrator for JobOps. The only entry point is `python3 -m ingestion.run_linkedin_ingestion`. Each invocation builds and runs **one** `QuerySpec`, defaulting to the first bucket in the ingestion config (`ingestion/run_linkedin_ingestion.py:61-78, 177`). Review and timing are also manual CLIs.

**A2 — HIGH — The P0 machinery has barely been exercised.** `[verified]`
- One live run on 2026-08-31 returned 3 postings (Elastic, Qentelli, SymphonyAI). All three are UNKNOWN on *both* dimensions (`WM-UNKNOWN-ABSENT` plus a compensation UNKNOWN).
- Recorded decisions: 0. Recorded submissions: 0.
- The gate has never produced a PASS or a FAIL on real data. As things stand it removes no manual work.

**A3 — MEDIUM — Status documents are stale and could mislead the next session.** `[verified]`
- `P0_EXIT_REVIEW.md:55-62` is out of date (see §2).
- `CLAUDE.md:6-9` still frames the repo around SQL/Python learning.
- `docs/INDEX.md` has uncommitted edits.

**A4 — LOW — Dead or stale artifacts.** `[verified]`
- `api-server.pid` and `dashboard/dashboard.pid` are tracked in git despite `*.pid` in `.gitignore`. They were committed before the ignore rule (commit `d305eca`).
- `backup-20251116-103540/`.
- Empty `scripts/backup.sh` and `scripts/setup.sh`.
- Seven n8n workflow JSONs, three of them `claude-api-test*` variants.
- `scrapers/` (RemoteOK only, with a QA/ETL keyword filter at `scrapers/remoteok_integration.py:125-165`).
- Learning and SQL-practice files and tables.

None of these is on the critical path. They are noise for anyone reading the repo to understand discovery.

**A5 — HIGH — What would break if a scheduler were added today.**

| # | Breakage | Evidence | Tag |
|---|---|---|---|
| 1 | Re-gate regression: postings already held are re-evaluated without a JD, and that becomes the current verdict (see F4) | `ingestion/pipeline.py:323-330, 388-399`; `review/ledger.py:107-110` | `[verified]` by code reading, not executed |
| 2 | `bun` lives in `~/.bun/bin`. A cron or systemd environment usually lacks it on PATH, so `preflight` raises `RuntimeUnavailable` and the run exits 2 | `ingestion/linkedin_cli.py:139-166` | `[verified]` path; cron PATH `[UNVERIFIED]` |
| 3 | Every non-dry run takes a full DB backup with no rotation, so disk use grows without bound (8 backup files already in `data/`) | `ingestion/run_linkedin_ingestion.py:173-175`, `ingestion/persistence.py:139-160` | `[verified]` |
| 4 | The runtime DB is tracked in git (CONFLICT-3 open), so the tree is dirty after every run | `git status` shows `M data/jobs-tracker.db` | `[verified]` |
| 5 | No run lock. The daily rate-limit counter is an unlocked read-modify-write JSON file, so overlapping runs can exceed the daily caps | `ingestion/rate_limit.py:90-119, 139-150` | `[verified]` |
| 6 | No alerting. "Suspect zero results" and `rate_limited` are written only to the run manifest, which nobody reads | `ingestion/pipeline.py:303-310, 355-360` | `[verified]` |
| 7 | WSL: timers fire only while the WSL VM is running | environment | `[UNVERIFIED]` |

### B. Discovery

**B1 — HIGH — There is no source-adapter interface. The pipeline is LinkedIn-shaped, but its downstream seam is clean.** `[verified]`

LinkedIn-specific couplings:
- The class is `LinkedInIngestionPipeline` (`ingestion/pipeline.py:106`).
- `SOURCE_PORTAL = "linkedin-search"` is a module constant used by the raw store and the ledger (`ingestion/provenance.py:42-43, 65-68`).
- The rate-limit state file is hard-wired (`ingestion/pipeline.py:134-135`).
- `_gate_input` reads LinkedIn field names `description`, `location`, `url` and `date` (`ingestion/pipeline.py:168-212`).
- The config artifact is pinned to one source (`ingestion/config.py:31, 76-82`).

What is already source-agnostic:
- The gate input dict (`work_mode_text`, `portal_work_mode_field`, `compensation_text`, `posting_stated_at`, `source_ref`).
- `merge_source_records` (`ingestion/merge.py`).
- `CandidateRow` and `INSERT OR IGNORE` persistence with namespaced `external_id`.
- Identity host families and ATS parsers. These already declare Greenhouse, Lever, Ashby, Workday and RemoteOK (`identity/jobops-identity-0.1.0.json`, `url_canonicalization.host_families` and `ats_systems`).

Adding an adapter therefore means one refactor (about 1.5 days) to parameterise the portal, the rate limiter and the field mapping. Each adapter then takes about 0.5–2 days. **The gate does not need to change** to add a source.

**B2 — HIGH — LinkedIn cannot carry the target funnel by design.** `[verified]`
- Caps: 2 searches and 10 results per run; 10 searches and 30 detail fetches per day; one query per process (`ingestion/linkedin-ingestion-0.1.0.json:26-35`).
- These caps are deliberate, per OR-08 and the CLI's "personal use only, keep volume low" notice (`OWNER_RULINGS_LOG.md:153-163`).
- Surfacing 5–15 qualified candidates from "dozens" per run needs other sources. LinkedIn should stay a low-volume input.

**B3 — MEDIUM — Rate limiting and run state are good; retries and retention are not.** `[verified]`

Good:
- Per-run and daily caps, persisted daily counters, and a minimum interval.
- 429/block handling classifies the source as `rate_limited`, never `broken`.
- Run-scoped raw payloads are never overwritten (`ingestion/rate_limit.py`, `ingestion/linkedin_cli.py:208-285`, `ingestion/provenance.py`).

Gaps:
- The module docstring promises a "retry policy above the CLI's own" (`ingestion/linkedin_cli.py:11-13`), but **no retry exists**. A timeout is recorded as an `error` and dropped (`ingestion/linkedin_cli.py:242-250`).
- There is no retention or rotation policy for `data/ingestion/raw/`.

**B4 — MEDIUM — Compliance and ToS need to be contained in the design.**
- LinkedIn access goes through a CLI whose own notice says automated access is against LinkedIn's ToS. OR-08 authorises **only the linkedin-search CLI, at low volume**, and explicitly forbids broadening into bulk collection (`OWNER_RULINGS_LOG.md:153-163`). `[verified]`
- Consequence: replacing the CLI with JobSpy's LinkedIn scraper is a **new ingestion path that needs a new ruling**, not a drop-in.
- Raw LinkedIn payloads are correctly gitignored (`.gitignore`, last block). `[verified]`
- Google SERP scraping has its own ToS exposure. Greenhouse, Lever and Ashby expose public job-board APIs intended for embedding, which makes them the lowest-risk sources. Their terms were not checked. `[UNVERIFIED]`

**B5 — HIGH — The discovery queries target the wrong roles.** `[verified]`
- The query seeds are "AI Quality Engineer / AI Test Automation Engineer / Data & AI Quality Engineer / AI Governance Engineer" (`ingestion/linkedin-ingestion-0.1.0.json:46-51`).
- `remote_filter: "remote"` (`ingestion/linkedin-ingestion-0.1.0.json:54`) hides Bengaluru non-remote roles at the source. See §4.

### C. Normalization and evidence model

**C1 — Strength, with a HIGH caveat — Uncertainty is modelled explicitly for the two dimensions that exist.** `[verified]`
- Work mode has five states (`REMOTE`, `HYBRID`, `ONSITE`, `AMBIGUOUS`, `ABSENT`) and is never collapsed to a boolean (`policy/jobops-policy-0.1.0.json:121-153`).
- Compensation has seven states, including `ABSENT`, `NON_NUMERIC_CLAIM` and `UNIT_UNDETERMINED`.
- There is a three-state null discipline (`policy/normalization.py:102-106`).
- A portal-vs-body conflict becomes AMBIGUOUS plus an `unresolved_evidence` entry (`policy/normalization.py:290-303`).
- Per-field merge provenance with erasure protection is in `ingestion/merge.py`.

**Caveat:** all of this lives only in `data/ingestion/candidates/*.jsonl`. `scraped_jobs` has no verdict, state or evidence columns (`ingestion/run_linkedin_ingestion.py`, plan field `not_persisted_to_db`; `.schema scraped_jobs` on the copy). SQL cannot query "all UNKNOWN-salary Bengaluru roles".

**C2 — HIGH — Fields missing compared with the section-4 evidence-state model.**

| Proposed field | Repo equivalent | Status | Tag |
|---|---|---|---|
| `posted_at` | `scraped_jobs.posted_date` (TEXT, source string) and `posting_stated_at` in evidence | Partial. **No precision field**, so a date-only value (LinkedIn) looks the same as a timestamp (Naukri) | `[verified]` |
| `first_seen_at` | `scraped_at` (row creation) and the ledger `first_observed_at` per `external_id` | Partial. Keyed per source id, **not per identity**, so a cross-posting on a new source looks new | `[verified]` `review/ledger.py:116-121` |
| `newness_confidence` | none | **Missing** | `[verified]` |
| `remote_confidence` | `normalized_work_mode` (five-state enum) | **Exists** (enum, not float) | `[verified]` |
| `salary_confidence` | `compensation.state` (seven-state enum) | **Exists** | `[verified]` |
| `source_evidence` | `EvidenceItem` (verbatim, source, source_ref, fetched_at, extractor_version) | **Exists** | `[verified]` `policy/normalization.py:109-134` |
| `employer_evidence` / company type | `company_type_signal` is accepted as input, but **nothing populates it** (no occurrence in `ingestion/`) | **Missing in practice** | `[verified]` |
| Cross-source conflict (for example, "on LinkedIn, not on the employer's Greenhouse board") | `merge.py` conflicts, within one source's search and detail records only | **Missing.** No "not found on employer board" state | `[verified]` |
| Experience band evidence | none | **Missing** | `[verified]` |
| Role / title tier evidence | none | **Missing** | `[verified]` |
| Employment type (permanent vs contract) | LinkedIn `employmentType` is folded into free-text `tags` only (`ingestion/pipeline.py:233-236`) | **Captured, not evaluated** | `[verified]` |
| Seniority | LinkedIn `seniority` goes into `tags` only | **Captured, not evaluated** | `[verified]` |

**C3 — MEDIUM — Observed extraction and normalization defects.** I verified these by re-running the pure normalizer on the recorded spans and on probe strings (scratch copy, no writes).

1. **Compensation span false positives.** In the 31 Aug run:
   - Qentelli's selected "salary" span is *"…timeouts, **compensation paths**"* (a DAG sentence).
   - SymphonyAI's is *"4+ **Years** Experience … Bangalore"*. It matched because the figure marker `"rs "` is found inside "yea**rs** ".

   The locator uses raw substrings (`ingestion/extraction.py:62-69, 143-148`), unlike the normalizer's token-safe `_has_marker` (`policy/normalization.py:65-77`). The result is misleading UNKNOWN reasons shown to the reviewer.
2. **Common Indian work-mode and salary phrasing falls through.**
   - "Work from home" and "WFH" classify as `ABSENT`, not REMOTE (`policy/normalization.py:219-238`; the vocabulary comes from `policy/jobops-policy-0.1.0.json:132-139`).
   - "CTC: 24,00,000 per annum" is `UNIT_UNDETERMINED` because there is no currency token.

   Both are safe failures (UNKNOWN), but they inflate manual review on Naukri-style text.
3. **A favourable-reading defect.** "Up to 30 LPA" parses as a *point* figure, min = max = ₹30L, and therefore **PASS** (`policy/normalization.py:383-386`). An upper bound is not a confirmed minimum. This contradicts the artifact's own UNK-2 rule (`policy/jobops-policy-0.1.0.json:102`).

### D. Policy gate

**D1 — BLOCKER — The gate implements PASS/FAIL/UNKNOWN per criterion, but only for two criteria, and one of them encodes a superseded preference.** `[verified]`

`evaluate()` hard-codes exactly two dimensions (`policy/gate.py:263-269`). Precedence is FAIL > UNKNOWN > PASS. Criterion by criterion:

| Criterion | Gate behaviour | Hard-coded value / location | Current preference | Divergence | Tests |
|---|---|---|---|---|---|
| Salary floor | FAIL if confirmed annual_max < T; PASS if annual_min ≥ T | T = **2,000,000 INR**, inclusive (`policy/jobops-policy-0.1.0.json:161-168`) | Practical minimum about ₹20 LPA when disclosed | **Aligned.** The non-gating "target band ₹20–30+" (`:169`) differs from the ₹24–28 target (informational only) | Yes (V-01…V-05, boundary) |
| Unknown salary | UNKNOWN (COMP-R5); straddling range is UNKNOWN (COMP-R3) | `:217-231, 199-215` | Surface as UNKNOWN | **Aligned** | Yes |
| Remote vs hybrid | REMOTE is PASS. **HYBRID and ONSITE are FAIL.** "Remote-first" is AMBIGUOUS, which becomes UNKNOWN | `:122-128, 135` | Remote is strongest; **Bengaluru is relevant when fit is strong**; hybrid/on-site evaluated selectively | **Conflict.** Every Bengaluru hybrid/on-site role is auto-rejected. There is **no location dimension**, so Bengaluru cannot be told apart from other cities | Yes, and the tests **encode the old rule** (`tests/test_p0_02_gate.py:71-99, 156`) |
| Staffing / consultancy | **Not gating.** `company_type_signal` is recorded only, and never populated | `:291-307`; OR-04 | Avoid service-only, staffing, consultancy and body-shopping employers | **Conflict.** Tests assert staffing gets a verdict identical to product (`tests/test_p0_02_gate.py:680-685`) | Encodes the old rule |
| Experience band / 4–6 stretch | **Not evaluated** | — | Prefer 2–4 up to 1–6; 4–6 as a stretch; exclude 7+ | **Missing** | None |
| Role-title tiers | **Not evaluated** | — | Tier 1/2/3 | **Missing** | None |
| Avoid-list roles | **Not evaluated** (OR-05 open) | `:314` | Manual QA, Selenium-only, etc. | **Missing** | None (T-14 not implemented, `P0_EXIT_REVIEW.md:62`) |
| Contract / short-term | **Not evaluated** (OR-07 open) | `:315` | Permanent full-time; avoid short-term contracts | **Missing.** A test asserts a 3-month contract still PASSes (`tests/test_p0_02_gate.py:347-354`) | Encodes the old rule |
| Seniority exclusions | **Not evaluated** | — | Exclude Staff, Principal, Architect, intern and entry-level | **Missing** | None |

**D2 — MEDIUM — Extending the gate is a code change, not just a ruleset change.** `[verified]`
The artifact claims "adding a gate dimension is a ruleset change plus tests … never a code restructure" (`policy/jobops-policy-0.1.0.json:318`). But `HardEligibilityGate.evaluate` and `GateResult` name exactly `work_mode` and `compensation` (`policy/gate.py:263-303`), and the drift guard pins version `0.1.0` (`policy/ruleset.py:35`). This is a good design to keep, but v0.2 needs a data-driven dimension loop. Expect about 1–1.5 days for the refactor, plus about 0.5 day per new dimension including tests.

### E. Relevance scoring

**E1 — HIGH — `scrapers/simple_scorer.py` is QA/ETL-oriented and should be replaced, not tuned.** `[verified]`
- It produces one weighted number: skills 40%, experience 20%, domain 20%, location 10%, red flags 10% (`data/resume_config.json`, `scoring_weights`).
- Auto-import is set at ≥75 (`data/resume_config.json:179`).
- It reads `data/resume_config.json`: 7 years, "QA Lead", ₹18L, experience range 5–10, critical skills "ETL Testing" and "Data Warehouse Testing" (`data/resume_config.json:4-6, 183`).
- Location scoring: remote 100, **hybrid 50, unknown 50**, Bengaluru 30. Missing experience scores **100** (`scrapers/simple_scorer.py:266-283, 299-300`).
- It is wired only to the dormant RemoteOK scraper. The P0 pipeline has scoring disabled (`ingestion/linkedin-ingestion-0.1.0.json:77`) and the gate structurally excludes it.
- `data/SCORING_GUIDE.md` documents the same QA model.

**E2 — MEDIUM — The scorer cannot express separate axes.** Experience fit (Direct/Reasonable/Stretch), Technical fit (Strong/Moderate/Weak) and Location fit need to be **separate categorical labels**, each with rule IDs and verbatim evidence spans, in a versioned artifact like `policy/` and `identity/`. They should never be summed into a "best job" number. The review lanes are already structurally unranked (`review/queue.py:1-40`), so this fits.

**Making Tier 3 JD-content judgment reproducible and auditable:**
1. Write a versioned rubric JSON of JD signals, each mapped to the core stack (for example "builds/owns RAG or retrieval pipeline", "LLM evaluation harness / LLM-as-judge", "agent / tool-calling in production").
2. Each label must cite the verbatim spans that triggered it.
3. If an LLM assists extraction, it may only return quoted spans plus labels under a strict JSON schema. Record the model ID, prompt version and content hash, cache by hash, and treat the output as *evidence, never verdict*. Posting text stays untrusted data (the rule already exists at `policy/jobops-policy-0.1.0.json:384`).
4. Keep a labelled golden set of real JDs (the 29 Sep run's dozens of candidates are an ideal seed) as regression fixtures.

**E3 — LOW —** `JOBOPS_SCALING_EXECUTION_PLAN.md` P1-01 ("Extend" `simple_scorer`) predates the preference change. It should become "Replace".

### F. Identity, dedup and newness

**F1 — HIGH — Identity is not in the ingestion path.** `[verified]`
Ingestion dedups only at L1 (`INSERT OR IGNORE` on `external_id`, `ingestion/persistence.py:164-199`). L2, L3 and L4 run only when the review queue is built (`review/queue.py:325-329`). The ledger records `"p0_07_not_applied": true` (`ingestion/pipeline.py:485-486`).

**F2 — HIGH — The same role across LinkedIn, Naukri, Indeed and the employer board will usually be classified DISTINCT.** `[verified]` by reading the ruleset and payloads.
- The LinkedIn detail payload has no apply or requisition URL. Its keys are `company, companyUrl, date, description, employmentType, id, industries, jobFunction, location, seniority, title, url`. So L4, the ATS requisition match, cannot fire.
- L3 needs exact normalized company, title and location, with no city-alias mapping (`identity/jobops-identity-0.1.0.json:43`, `text_normalization.location.never`).
- When both locations are evaluable and differ, `DR-L3-LOCATION` declares the pair **DISTINCT** (`identity/jobops-identity-0.1.0.json:329`). "Bengaluru, Karnataka, India" vs "Bangalore" is therefore DISTINCT rather than UNCERTAIN.
- There is no rule preferring the employer requisition URL as canonical.

Conservative behaviour is correct for *suppression*. It is wrong for *surfacing* a "possible same role, verify on the employer board" link, which the LogicMonitor case needs.

**F3 — HIGH — Newness is not modelled.**
- Nothing distinguishes a newly opened requisition from an old listing resurfacing.
- Missing pieces:
  - identity-level `first_seen_at`;
  - a per-run membership snapshot (`seen_in_runs`);
  - a date-precision field;
  - a "previously seen under another source" link.
- The ledger's `first_observed_at` is per `external_id` (`review/ledger.py:116-121`), so it cannot detect cross-source resurfacing.
- Incremental *fetching* works: detail is skipped for L1-known postings (`ingestion/pipeline.py:323-330`). `[verified]`

**F4 — BLOCKER for scheduling — Re-runs degrade verdicts.** `[verified]` by code reading; not executed.
1. For an already-held posting, the pipeline skips the detail call but still gates it (`ingestion/pipeline.py:327-330, 388-399`).
2. Search results carry no `description`. The raw search payload keys are `company, companyUrl, date, id, location, title, url`.
3. So the re-evaluation sees no JD: work mode resolves from `location` only, and compensation is ABSENT.
4. The review ledger treats the **latest observation as current** (`review/ledger.py:107-110`).
5. A posting that was PASS on its JD becomes UNKNOWN the next time a daily query sees it.

Tests cover "no duplicate rows" and "no detail call" on a re-run (`tests/test_p0_06_linkedin_ingestion.py:699-740`), but not verdict stability.

### G. Review queue and manual-work reduction

**G1 — HIGH — The queue is sound but unused, with no UI and no newness lane.** `[verified]`
- Lanes: SHORTLIST (PASS), REVIEW (UNKNOWN), BELOW_THRESHOLD, EXCLUDED, NOT_EVALUATED, SUPPRESSED_DUPLICATE (`review/jobops-review-0.1.0.json`, `lanes`).
- The machine, human and application blocks are kept strictly separate (`review/queue.py:1-40`). This matches the three-axes idea in the section-4 plan.
- It is reachable only by CLI (`review/run_review_queue.py:52-84`) or unauthenticated JSON API. No dashboard view exists.
- There is no "new since last run" lane or ordering.

**G2 — HIGH — Manual steps still left per candidate, and which can be pre-filled safely.**

| Manual step today | Automatable as pre-fill or verification (submission stays human) | Phase |
|---|---|---|
| Read the whole JD to judge fit | Extract experience, seniority, employment type and title tier with cited spans; Tier 3 rubric labels | P1 (rules), P2 (rubric) |
| Verify remote status | Better vocabulary (WFH), location dimension; for UNKNOWN, JD fetch for shortlisted URLs | P1 / P2 |
| Verify salary | Fix "up to" parsing and Indian CTC formats; otherwise it stays UNKNOWN for the human | P1 |
| Judge employer type | Curated staffing/consultancy list plus JD signals producing `employer_evidence` | P1 (list), P2 (signals) |
| Find the employer requisition URL | Look up company plus title on the owner's ATS watchlist boards (read-only) and propose a link as UNCERTAIN | P2 |
| Check newness and duplicates | Identity at ingest plus first-seen; the digest shows "new / seen before / seen on another source" | P1 |
| Draft application material | Draft a cover note or answers from a *current* master resume for human edit. The existing prompts and resume are QA-era (§4) and must be replaced first | P3 |
| Record decision, promotion and submission | One command or UI action that records the decision *and* promotes; submission recording prompted at the same point | P3 |

**G3 — MEDIUM — `timing/` cannot compute the target KPIs yet.** `[verified]`
- **Qualified Application Yield** needs a "relevant/qualified" label, and none exists.
- **Shortlist Yield** can be computed from lane counts, but SHORTLIST (PASS) is unreachable while 100% of candidates are UNKNOWN.
- **Interview Yield**: `opportunities.status` has `Screening`, `Technical` and `Manager`, but timing does not derive the metric.
- **Review minutes per candidate** is `NOT_MEASURABLE` by design, because no review start or end event exists (`timing/jobops-timing-0.1.0.json:165-176, 386`).
- Cheapest honest fix: an explicit *review-session* start/stop, divided by the number of decisions recorded in the session. This is an owner decision.

**G4 — MEDIUM — Recording friction.** A decision (`--decide REF --kind …`) and a submission (`--record-submission REF --submitted-at …`) are two separate CLI commands keyed by internal refs. Zero records exist, which is consistent with that friction discouraging recording. `[verified]` counts; cause `[UNVERIFIED]`.

### H. Resilience and scale

| # | Sev | Finding | Evidence | Tag |
|---|---|---|---|---|
| H1 | HIGH | The runtime SQLite DB is tracked in git (CONFLICT-3 open). Scheduled writes would dirty the tree daily and risk committing personal data or getting binary merge conflicts | `git status`; `policy/jobops-policy-0.1.0.json:589` | `[verified]` |
| H2 | HIGH | The API binds all interfaces (`""`, port 8081) with `Access-Control-Allow-Origin: *` and **unauthenticated write endpoints** (`/api/review-decision`, `/api/import-scraped-job/{id}`). CONFLICT-8 is open | `api-server.py:21, 528-530, 915` | `[verified]` |
| H3 | MEDIUM | `docker-compose.yml` commits a literal default n8n basic-auth password as the fallback value. Rotate it if it was ever used; move it to `.env` only | `docker-compose.yml:30` | `[verified]` (value deliberately not reproduced) |
| H4 | MEDIUM | Two systems of record: machine verdicts, decisions and submissions are JSONL files, while candidates and applications are SQLite. They share no transaction, and a failure between `insert_candidates` and `ledger.flush` leaves rows without verdicts (`NOT_EVALUATED`) | `ingestion/pipeline.py:362-385` | `[verified]` path; failure `[UNVERIFIED]` |
| H5 | MEDIUM | Migrations: no history table, `user_version = 0`. The `scraped_jobs` DDL lives in `scrapers/remoteok_integration.py:179`, not in `migrations/` or `queries/schema.sql`. Migration 004 is unapplied. JS-24 (runner) is open. The P0 packages deliberately avoided migrations, which is why state went to JSONL | `P0_EXIT_REVIEW.md` §1; `migrations/` listing | `[verified]` |
| H6 | MEDIUM | Backups: a full copy on every run, no rotation; `scripts/backup.sh` is empty | A5 #3 | `[verified]` |
| H7 | MEDIUM | Concurrency: SQLite WAL is fine for one writer. The pipeline uses sqlite3's default 5 s timeout while the API uses 30 s. There is no run lock, and the rate-limit counter file is unlocked | `ingestion/persistence.py:79-82`; `api-server.py:37-49` | `[verified]` |
| H8 | MEDIUM | Logging and alerting: log files are empty; failures are visible only in manifests; there is no notification. There is precedent: the RemoteOK scraper went stale for 9 months unnoticed (`JOBOPS_SCALING_EXECUTION_PLAN.md` P1-07) | `logs/` | `[verified]` |
| H9 | LOW | Cost controls exist only as LinkedIn caps. No budget exists for LLM or Apify usage because neither is wired in | — | `[verified]` |
| H10 | Strength / LOW | Testability is good: injectable runner, clock, sleeper and DB paths, and 363 tests pass in 6 s. **However**, the P0-06, P0-07 and P0-08 tests read the live DB (read-only), so results depend on live data (`tests/test_p0_07_identity_dedup.py:541, 633, 1092`). There is no recorded multi-source fixture corpus | pytest run on the copy | `[verified]` |

---

## 4. Preference-conflict table

The current preferences are the 28 Sep 2026 document from the audit brief. **None of these conflicts is resolved here.** Several of them (rows 3–6) are also Owner rulings, so changing them needs a new ruling and a new ruleset version under the repo's own governance.

| # | Repo artifact | What it says | What current preferences say | Severity |
|---|---|---|---|---|
| 1 | `docs/Career_Strategy_and_Search_Preferences.md:46-48` | Target ₹20–30+ LPA; **"Last drawn: ₹16 LPA"**; below ₹18L only if exceptional | Target ₹24–28 LPA, ask ₹26 LPA, minimum about ₹20L when disclosed; **never anchor to ₹16L** | HIGH. This is the doc used for recruiter answers |
| 2 | `docs/Career_Strategy_and_Search_Preferences.md:55-60` | Remote is a **hard constraint**; hybrid/on-site excluded by default and never surfaced | Remote strongest; **Bengaluru relevant when technical fit is strong**; hybrid/on-site evaluated selectively | BLOCKER, because it drives the gate |
| 3 | `policy/jobops-policy-0.1.0.json:124-125` (WM-R2, WM-R3) | HYBRID → FAIL; ONSITE → FAIL | Selective evaluation; Bengaluru allowed on strong fit | **BLOCKER** |
| 4 | `policy/jobops-policy-0.1.0.json:291-307`; `OWNER_RULINGS_LOG.md` OR-04 (lines 117-121) | Services/staffing is **not** a veto; recorded only | Avoid service-only, staffing, consultancy placements and body-shopping | HIGH |
| 5 | `policy/jobops-policy-0.1.0.json:313-316` | Role/technology exclusions and contract duration not evaluated (OR-05, OR-07 open) | Explicit avoid-list roles; avoid short-term contracts | HIGH |
| 6 | `tests/test_p0_02_gate.py:71-99, 156, 347-354, 680-685` | Tests *assert* hybrid/on-site FAIL, a 3-month contract PASSes, and staffing gets the same verdict as product | As rows 3–5 | HIGH. Tests will resist the policy change by design |
| 7 | `docs/Career_Strategy_and_Search_Preferences.md:62-64` | Contract acceptable if ≥6 months at a product company | Permanent full-time; avoid short-term contracts (≥6-month product contract not addressed) | MEDIUM |
| 8 | `docs/Career_Strategy_and_Search_Preferences.md:71-77` | Four search buckets: AI Quality / AI Test Automation / Data & AI Quality / AI Governance-Trust Engineer | Tier 1: AI Engineer, Applied AI Engineer; Tiers 2 and 3 as listed | HIGH |
| 9 | `ingestion/linkedin-ingestion-0.1.0.json:46-51` | Query seeds = the four QA-era buckets | Tier 1/2 titles | HIGH. Discovery searches the wrong roles |
| 10 | `ingestion/linkedin-ingestion-0.1.0.json:54` | `remote_filter: "remote"` on every query | Bengaluru non-remote is also relevant | MEDIUM |
| 11 | `docs/Career_Strategy_and_Search_Preferences.md:20-27` | Narrative QA → Data Quality → AI Evaluation/Governance; "seven years" | AI Engineer / Applied AI Engineer; **about 3 years of directly relevant AI engineering** | MEDIUM. Affects drafted material |
| 12 | `policy/jobops-policy-0.1.0.json:135` | "Remote-first" is AMBIGUOUS | "Remote-first" companies are a positive signal (a posting-level remote statement is still needed) | LOW |
| 13 | `policy/jobops-policy-0.1.0.json:169` | Non-gating target band ₹20–30+ | Target ₹24–28 | LOW (informational) |
| 14 | `data/resume_config.json:4-6, 183, 191, 207` | 7 years; "QA Lead / Data QA Engineer"; `min_salary_inr` 18,00,000; experience range 5–10; "Hybrid" preferred; ETL Test Lead title boost | About 3 years AI; ₹20L minimum; AI Engineer tiers; hybrid not equivalent to remote | MEDIUM. Dormant, but it is the scorer's config |
| 15 | `data/SCORING_GUIDE.md:10-11, 66, 72` | Same values as row 14, documented | As row 14 | LOW (doc) |
| 16 | `scrapers/simple_scorer.py:266-283, 299-300` | Hybrid 50, unknown location 50, no experience = 100, single score | Separate fit axes; unknown is not favourable | MEDIUM |
| 17 | `scrapers/remoteok_integration.py:136-141` | Relevance keywords: qa, test, etl, sdet… | AI engineering stack | LOW (dormant) |
| 18 | `prompts/job_analysis.txt:1-18` | "QA Lead/ETL Testing Specialist", "Remote/Hybrid Senior QA Lead, Test Lead", seniority Senior/Lead = 20 points | AI Engineer; avoid Staff/Principal; ~3 years | MEDIUM |
| 19 | `prompts/email_generation.txt:1-6` | "QA Lead position", "7+ years QA Lead/ETL Testing" | As above | MEDIUM |
| 20 | `data/resumes/Karthik_SR_AI_ML_Test_Lead.docx`; `data/resumes/master_resume.json:10` | "Test Lead" resume; summary "seeking remote QA Lead and Data QA roles" | AI Engineer positioning | HIGH if used for any drafting helper |
| 21 | `OWNER_RULINGS_LOG.md` OR-03a / OR-03b / OQ-01 | ₹20L floor; unknown → UNKNOWN; straddle → UNKNOWN | ₹20L minimum when disclosed; undisclosed → UNKNOWN | **No conflict** (listed for completeness) |
| 22 | `CLAUDE.md:14-17` | Learning goals: SQL/Python mastery | (Not a search preference) | LOW. It shapes agent behaviour in this repo |

---

## 5. Assessment of the section-4 plan (item I)

| Plan element | Verdict | Reasoning grounded in the repo |
|---|---|---|
| Pluggable Discovery Adapter layer | **Agree, with changes** | The downstream seam already exists (gate input dict, `SourceRecord` merge, `CandidateRow`, identity host families for Greenhouse/Lever/Ashby/Workday). Build the adapter as a refactor of `LinkedInIngestionPipeline` (B1), with a versioned config per source (the existing `linkedin-ingestion-0.1.0.json` pattern) and per-source caps. Do not write a parallel pipeline |
| Pipeline order Discovery → Normalizer → Dedup → Evidence → Gate → Scorer → Queue → Review → Application | **Agree, with changes** | Matches `policy/jobops-policy-0.1.0.json:63-77` and the review design. Move **identity to before the gate** (F1) and add an explicit **Newness** step after dedup. Keep "no score can revive a FAIL" (`policy/gate.py:9-12`) |
| Playwright only for JD extraction of shortlisted URLs | **Agree** | Scope it to PASS/UNKNOWN candidates missing a JD. Treat fetched text as untrusted (`policy/jobops-policy-0.1.0.json:384`). Respect robots.txt and ToS per host. Record JD-fetch provenance as an extra `SourceRecord` so `merge.py` handles it |
| No heavy Naukri scraper | **Agree** | Consistent with `JOBOPS_SCALING_EXECUTION_PLAN.md:251, 261, 332-333` (Naukri recon first, P2-05 go/no-go) |
| Evidence-state model | **Agree, but ~60% already exists** (challenge 4) | Work-mode and salary confidence already exist as enums (C1), and `source_evidence` exists. Do **not** add parallel float "confidence" fields: extend the existing enum and evidence-item pattern. Genuinely missing: `posted_at_precision`, identity-level `first_seen_at` and run membership, `newness_state`, `employer_evidence`, experience/title/employment-type evidence, cross-source conflict records (C2) |
| Gate PASS/FAIL/UNKNOWN per criterion | **Agree** | Already implemented for two criteria. Extend under policy v0.2 with a data-driven dimension loop (D2). Each new dimension defaults to UNKNOWN when evidence is absent |
| Three axes: NEWNESS / FIT / APPLICATION | **Agree, with changes** | The queue already separates machine / human / application (G1). Add NEWNESS as a fourth block. Keep FIT (gate) separate from relevance labels (E2). "Fit" in the plan conflates eligibility with relevance |
| KPIs (QAY, Shortlist Yield, Interview Yield) | **Agree, with changes** | QAY needs a defined "relevant" label (G3). Interview Yield can come from `opportunities.status` today. Add **review minutes per qualified candidate** via an explicit session timer (owner decision) |
| Side-by-side Apify vs free adapters for 1–2 weeks | **Agree, with changes** | At 1–3 applications per run, 1–2 weeks yields too few applications to compare at application level. Compare at **candidate level**: unique qualified candidates, precision against a labelled set, cross-arm duplicate rate, UNKNOWN rate per dimension, newness correctness. Both arms must pass through the *same* identity layer, or "unique jobs" cannot be computed. Timing already offers per-dimension UNKNOWN rates |
| (1) Naukri via Google-indexed discovery only | **Disagree as the default path** | (a) Google indexing lags, which throws away Naukri's one advantage: exact timestamps. (b) The run evidence says Naukri JD pages did not render via generic fetch, so every Naukri candidate would arrive without a JD, 100% UNKNOWN, with no review-time saving. (c) SERP scraping carries its own ToS risk. The official search API has a small free quota and cost beyond it `[UNVERIFIED]`. (d) The repo's own docs call Naukri staffing-dominated noise. Recommendation: keep Naukri on the owner's existing Apify export (imported, see challenge 3) until the P2-05 recon decides go/no-go |
| (2) Reliance on JobSpy for LinkedIn | **Disagree** | The repo already has a working, rate-limited, ruling-backed LinkedIn path. OR-08 authorises **only the linkedin-search CLI** at low volume (`OWNER_RULINGS_LOG.md:153-163`). JobSpy's LinkedIn mode would be an unratified second scraper with the same ToS exposure and an extra third-party breakage surface `[UNVERIFIED stability]`. Use JobSpy, if at all, for Indeed/Glassdoor/Google Jobs as an *experimental* adapter behind the side-by-side |
| (3) Apify optional vs primary | **Primary for now, via file import; optional later** | Apify is the owner's current, proven loop. The cheapest way to absorb it is an **import adapter for Apify dataset exports** (JSON/CSV dropped into an inbox folder): no Apify API integration, no new paid dependency in JobOps. JobOps then takes over the expensive downstream work (dedup, gate, newness, review) from day one. Keep Apify as the baseline until the free adapters match it on qualified-candidate recall in the comparison; after that it becomes optional. The cost stays wherever the owner already pays it. JobOps adds none by default |
| (4) Evidence-state duplicates `policy/normalization.py`? | **Partly, yes** | See the "Evidence-state model" row. Reuse `EvidenceItem`, the state enums, `NOT_CAPTURED` three-state discipline and `merge.py` provenance. Add only the missing fields |

**Risks the plan misses:**
1. **Preference drift across four authorities.** The career doc, the rulings log, the policy JSON and the new preference document disagree (§4). Without a ratified v0.2 policy, every adapter just delivers more mis-filtered volume.
2. **UNKNOWN flood.** With two dimensions and weak extraction, 3/3 real postings were UNKNOWN. Multi-source volume multiplies review load unless extraction improves first.
3. **Re-gate regression** (F4) makes incremental daily runs actively harmful.
4. **Company Radar contamination.** Polling Greenhouse/Lever/Ashby boards overlaps Radar Phase 1 channel B, which the owner performs manually (`docs/COMPANY_RADAR_EXPERIMENT.md:124-132`). Scope and timing need an owner decision.
5. **Prompt injection** if an LLM reads JDs. Posting text must stay data, and LLM output must be evidence only.
6. **Employer identity mismatch across sources** ("Elastic" vs a legal entity name) and **city aliasing** undermine cross-source dedup (F2).
7. **Operational substrate:** WSL uptime, `bun` PATH, the DB in git, and the unauthenticated API bound to all interfaces (A5, H1, H2).
8. **Watchlist curation is manual work.** ATS polling only covers employers someone added, so it complements aggregator discovery rather than replacing it.

---

## 6. Gap-to-target architecture

Legend: `[E]` exists · `[P]` partial · `[M]` missing

```
                ┌──────────────────────────── DISCOVERY ADAPTERS ────────────────────────────┐
                │ [E] LinkedIn CLI      ingestion/linkedin_cli.py (caps, 429, raw capture)    │
                │ [M] ATS boards        (Greenhouse/Lever/Ashby JSON) — identity already       │
                │                       parses their URLs: identity/jobops-identity-0.1.0.json│
                │ [M] Apify export import (inbox folder)                                       │
                │ [P] RemoteOK          scrapers/remoteok_integration.py (legacy, ungated)     │
                │ [M] JobSpy (experimental) · [M] Naukri (recon first)                        │
                └───────────────────────────────┬─────────────────────────────────────────────┘
                   [M] Source-adapter interface │ (refactor of ingestion/pipeline.py)
                                                ▼
 [E] Raw evidence store ── data/ingestion/raw/<portal>/<run>/  (ingestion/provenance.py)
                                                ▼
 [P] Normalizer ── policy/normalization.py + ingestion/extraction.py + ingestion/merge.py
                   (work mode + salary only; missing experience/title/employer/employment type)
                                                ▼
 [P] Deduplicator ── identity/ (L1–L4, read-only)  — not called during ingestion
                                                ▼
 [M] Newness tracker ── identity-level first_seen_at, run membership, date precision
                                                ▼
 [P] Preference/Policy gate ── policy/gate.py (2 of ~7 criteria; v0.1.0 policy outdated)
                                                ▼
 [M] Relevance labels ── (scrapers/simple_scorer.py exists but obsolete → replace)
                                                ▼
 [P] Candidate queue ── review/queue.py (lanes; no newness lane; no UI)
                                                ▼
 [P] Human review ── review/run_review_queue.py, /api/review-decision (0 decisions so far)
     [M] Pre-fill helpers (employer URL lookup, JD fetch, draft material)
                                                ▼
 [E] Application (human-gated) ── opportunities + /api/import-scraped-job + timing/submissions.py
                                                ▼
 [P] Metrics ── timing/ (funnel counts; no QAY / Interview Yield / review minutes)

 Cross-cutting:  [M] scheduler + run lock + digest   [M] alerting   [P] backups (no rotation)
                 [M] migration runner (JS-24)        [P] DB-in-git (CONFLICT-3)   [M] API auth
```

---

## 7. Recommended phasing

Effort is in engineer-days for one person familiar with the repo. Every phase keeps final submission human-gated.

### P0.5 — Owner rulings (owner time about 1 hour; engineering 0.5 day to record)
- **Goal:** One ratified preference authority before any code encodes it.
- **Deliverables:** Answers to §8 Q1–Q5 recorded in `OWNER_RULINGS_LOG.md`, plus an update to the career doc, including removal of the ₹16L anchor.
- **Acceptance:** Each §4 row marked BLOCKER or HIGH has a ruling or an explicit deferral.
- **Stays manual:** Everything.
- **Metric moved:** None directly. It de-risks all later phases.

### P1 — Scheduled, multi-source, deduplicated, gate-checked daily run (about 9–12 days)
- **Goal:** Every morning, without a key press, a reviewable list of **new since last run** candidates with per-criterion PASS/FAIL/UNKNOWN verdicts and duplicate links.
- **Deliverables:**
  1. **Source-adapter seam:** generic pipeline, per-source config and caps, parameterised `SOURCE_PORTAL` and rate-limit state. LinkedIn becomes adapter #1, with query seeds updated to Tier 1/2 titles and location handling per the Q2 ruling. (2 days)
  2. **ATS-board adapter** for Greenhouse/Lever/Ashby public job JSON over an owner-curated `watchlist.json`. It has its own caps and retries with backoff. (2 days)
  3. **Apify export import adapter** that reads JSON/CSV from `data/ingestion/inbox/apify/` and records the actor name, dataset ID and export time as provenance. (1 day)
  4. **Policy v0.2.0** covering only what P0.5 ruled:
     - a data-driven dimension loop in the gate;
     - new dimensions: location/work mode (Bengaluru rule), experience/seniority (7+ and Staff/Principal/Intern → FAIL; 4–6 → PASS with a `STRETCH` flag), title tier and avoid-list titles, employment type, employer type via a curated staffing list;
     - absent evidence → UNKNOWN;
     - fixes for the extraction defects in C3 ("up to", `rs ` marker, "compensation paths", WFH, Indian CTC format);
     - updated tests that replace the ones encoding the old rules.

     (3–4 days)
  5. **Identity at ingest plus newness:** resolve each candidate during the run and write the resolution into the ledger. Add a file-based `data/ingestion/state/seen_index.jsonl` keyed by identity with `first_seen_at`, `last_seen_at`, `seen_in_runs` and `posted_at_precision`. File-based means no migration, unless Q8 says otherwise. Newness states: `NEW` / `POSSIBLY_NEW` (date-only on the same day) / `PREVIOUSLY_SEEN` / `SEEN_ON_OTHER_SOURCE` / `UNKNOWN`. (1.5 days)
  6. **Fix F4:** a search-only re-observation must not replace a JD-bearing current verdict. Either carry forward the last detail record as a `SourceRecord`, or skip re-gating when no new evidence arrived. (0.5 day)
  7. **Runner:** a `jobops daily` command with a `flock` lock, absolute `bun` path, per-source isolation (one source failing never blocks the others), backup rotation (keep N), a systemd user timer (systemd is active in this WSL instance), and a Markdown digest `data/digests/<date>.md` grouped by lane × newness. (1 day)
- **Acceptance tests:**
  - Recorded-fixture tests per adapter (no network).
  - A re-run of an identical fixture set inserts 0 rows **and** leaves every current verdict unchanged.
  - A fixture where the same Greenhouse requisition arrives via an Apify-LinkedIn export and via the ATS adapter produces a linked or UNCERTAIN identity, not two silent DISTINCT rows.
  - Three simulated consecutive days produce correct NEW / PREVIOUSLY_SEEN counts.
  - A concurrent second invocation exits on the lock.
  - Each §4 BLOCKER/HIGH ruling has a named gate test.
- **Stays manual:** Reading and deciding on candidates, the ATS watchlist, running the Apify actors (unchanged), and all application steps.
- **Metrics moved:** Manual discovery minutes per day (self-reported before and after), `unknown_rate` per dimension, cross-source duplicate rate, candidates surfaced per run.

### P2 — Evidence enrichment and relevance labels (about 8–11 days)
- **Goal:** Cut UNKNOWNs and make Tier 3 judgment reproducible.
- **Deliverables:**
  - JD fetch (Playwright or plain HTTP) for PASS/UNKNOWN candidates lacking a JD, with per-host allowlist and caps.
  - A versioned **relevance rubric** producing separate Experience / Technical / Location fit labels with cited spans. No composite score.
  - Optional LLM-assisted span extraction, schema-validated and cached by content hash.
  - A golden set of about 40–60 labelled JDs drawn from the owner's past runs.
  - Employer-board cross-check for LinkedIn-only listings, reporting "not found on board (N openings checked at T)" as evidence, not a verdict.
- **Acceptance:** The golden set reproduces labels at ≥90% agreement with the owner's labels. Every label cites a span. The `unknown_rate` for work mode drops measurably on the same fixture corpus.
- **Stays manual:** Final fit judgment and all decisions.
- **Metrics moved:** Shortlist precision, `unknown_rate`, review minutes per candidate.

### P3 — Review UX, pre-fill and KPIs (about 5–7 days)
- **Goal:** Make recording effortless and measure yield.
- **Deliverables:**
  - A review-queue view in the dashboard (lanes × newness).
  - A one-action decide-and-promote flow, with a submission-recording prompt.
  - Review-session timer (if Q-owner approves).
  - QAY, Shortlist Yield and Interview Yield in the timing report.
  - Replacement of the QA-era prompts and resume inputs, then draft-material helpers (human edits and submits).
- **Acceptance:**
  - A full candidate lifecycle (surface → decide → promote → record submission) takes one UI path.
  - The timing report shows all three yields with sample sizes.
  - No code path submits anything, asserted by a test in the style of the existing boundary tests.
- **Stays manual:** Editing and submitting applications.
- **Metrics moved:** Review minutes per qualified candidate, QAY, and recording completeness.

### P4 — Source comparison and expansion (about 3 engineering days; 2 calendar weeks)
- **Goal:** Decide Apify's long-term role on evidence.
- **Deliverables:**
  - The side-by-side run defined in §5, with a written comparison.
  - An experimental JobSpy adapter for Indeed/Google Jobs.
  - The Naukri recon note (P2-05).
  - Remote boards (RemoteOK, Remotive), re-wired through the adapter seam.
- **Acceptance:** The comparison report states unique qualified candidates per arm, the overlap, the UNKNOWN rate, and the cost per qualified candidate.
- **Stays manual:** The go/no-go decisions.
- **Metrics moved:** Qualified-candidate recall per unit of cost.

### P5 — Hardening (about 4–6 days; can interleave)
- Move the DB out of git (CONFLICT-3).
- Bind the API to localhost and add a token (CONFLICT-8).
- Remove the literal default secret from compose.
- Migration runner (JS-24), with verdict and newness state optionally moved into SQLite.
- Alerting (zero-results, rate-limited, adapter errors) via a digest banner and optional email.
- Raw-payload retention policy.
- Clean up dead artifacts (A4) and relocate the learning/SQL-practice artifacts out of the repo.

---

## 8. Open questions for the owner

1. Does the 28-Sep-2026 preference document supersede OR-04 and the career doc's remote-only hard constraint (yes/no)?
2. A Bengaluru hybrid/on-site role with a strong technical match: gate verdict UNKNOWN (review) or FAIL?
3. Staffing, consultancy and service-only employers: hard FAIL, UNKNOWN for review, or a non-gating flag?
4. A stated minimum of 7+ years, or a Staff/Principal/Architect title: hard FAIL (yes/no)? And is 4–6 years PASS-with-STRETCH (yes/no)?
5. Is Company Radar Phase 1 still active, and may JobOps automatically poll Greenhouse/Lever/Ashby boards now (yes/no)?
6. May JobOps ingest your Apify dataset exports from an inbox folder as a source (yes/no)?
7. Should LinkedIn stay at the current caps (10 searches and 30 details per day), or may the caps be raised, and to what?
8. For new state (verdicts, newness, identity links): file-based JSONL only, or is a SQLite migration authorised?

---

## 9. What I could not verify, and why

| Item | Why |
|---|---|
| JobSpy stability, Apify actor behaviour and pricing, Google search API quotas | No external calls were made, per audit rules and the Company Radar no-discovery rule |
| Whether Naukri job pages render, and Naukri ToS / robots.txt | The same; I relied on the owner's 29 Sep run notes in the brief |
| The LogicMonitor Greenhouse board contents | The same |
| The 29 Sep manual run itself (candidates, queries, applications) | Not recorded anywhere in the repository |
| The internals and ToS text of the linkedin-search CLI | It lives in `~/projects/ai-job-search`. I only confirmed it exists (`SKILL.md`, `cli/`) and that `bun` is installed. I quoted its notice via `OWNER_RULINGS_LOG.md` |
| Greenhouse/Lever/Ashby API terms | Not fetched |
| Runtime behaviour of F4 (re-gate regression) | Established by reading the code and the recorded payload shapes. No re-run was executed, because that would contact LinkedIn |
| Behaviour under cron/systemd (PATH, WSL uptime) | No scheduler was installed; that would have been a mutation |
| n8n internal state and credentials | `data/n8n/` was deliberately not opened |
| The contents of `.env` | Not opened. It holds secrets and is untracked |
| Legacy shell test scripts (`tests/*.sh`, `test-everything.sh`) | Not run. Some start servers or write to the DB |
| Dashboard rendering | Not launched |
