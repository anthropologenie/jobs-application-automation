# JobOps P9 — Phase C-lite: Manually Triggered Real-Export Sourcing Digest (2026-10-01)

## Executive result

```text
READY FOR MANUAL REAL-EXPORT PILOT
```

- **What was built.** P9 adds `python3 -m jobops source` and `python3 -m jobops decisions --import`. They consume a locally downloaded JSON / JSONL / CSV export, run it through the accepted engine on `jobops-policy@0.2.6`, and write a daily digest.
- **Engine use.** The engine is consumed unchanged: `EvaluationService` (identity, dedupe, newness, evidence, policy, relevance) and `evaluation.queue.plan_day` (cap, carry, OR-88).
- **Nothing tracked was modified.** Not the engine, policy, rulings, historical fixtures or tests. `git diff` on tracked files shows only two appended `.gitignore` lines.
- **Gate E: pending.** Round 4 has not been measured; Gate E PASS is not claimed, and Round 4 was not created.
- **Human control kept.** There is no scheduler, network, LLM, application submission, resume generation or recruiter contact.

## Baseline

| Item | Value |
|---|---|
| HEAD | `4f5c29f47c258807258a8961e9b82e4dbaa223f0` |
| Tag | `policy-0.2.6` → `4f5c29f` |
| Working tree at start | clean |
| Baseline tests | **3303 passed, 0 failed, 61 xfailed, 0 skipped, 0 errors** |

The four P0 tests that read `data/jobs-tracker.db` are excluded, as in P8 / P8b.

Policy hashes, identical before and after P9:

| Policy | SHA-256 |
|---|---|
| 0.2.0 | `65f74aec883d475989ea0594fac070f547c96a697bc1f7f4b46cf8e0d5dd567a` |
| 0.2.1 | `af19a3fd998e945cba19ce68f0e36f2eba4156e8bfd5255ac4ea7dacf7f5ea7d` |
| 0.2.2 | `3743bbaebce2b5f3143ec0a211d6c63aa35b8113dce03b1622876ef43eeed734` |
| 0.2.3 | `918bf66e7d83d06d7ff7b10c6d8b1309cbabd033331315510851110856659d77` |
| 0.2.4 | `735934bf33533a31d207349cf689a3df6dafcdacc9c6a11b889b92e5af8c8136` |
| 0.2.5 | `27fe5d1accff78ce9db8ccc5f42a7d905b3e709a474d93d446e19a795ad53c93` |
| 0.2.6 | `de527c5d1dceb400913ec42e5aa527f19cd809e5054fcef5c61337d7fb890455` |

## Implementation (new package `jobops/`; no existing module changed)

| Component | Behaviour |
|---|---|
| **Source command** (`cli.py`, `sourcing.py`) | `source --input --policy (default 0.2.6) --out [--review-cap N] [--date]`. Prints the policy, its SHA and "Gate E: pending". Deterministic: observed time = `<date>T06:00Z`, the clock is `--date`, and run id = `p9-<date>-<input sha12>`. The run ledger is `<out>/state/runs.json`: a (date, input SHA) pair already processed is not re-ingested, so a rerun re-renders byte-identical outputs. A date earlier than the latest run is refused. |
| **Normalisation** (`normalize.py`) | JSON (list, or under `items` / `jobs` / `results` / `data` / `records`), JSONL and CSV. Canonical fields and aliases are in `ALIASES` (and the runbook). Missing fields stay None. Nested values are kept as compact JSON and never interpreted. If no record has a recognised title, the import fails with **SchemaError** and writes nothing. A record lacking a title or any of company / URL / id is rejected and counted, never repaired. |
| **URL safety** | URLs are preserved byte-for-byte. A search-results URL (`/jobs/search`, `?keywords=` …) is never used as an application URL. Missing → `apply_url_missing`, reported and counted, never fabricated. A missing URL never excludes a job. |
| **Identity / dedupe** | The existing v2 identity resolution, through `EvaluationService.ingest`, without a second system. A record with the same L1 id / L2 URL / L4 ATS key attaches to the same canonical requisition and is counted as a duplicate record. A sighting that bridges two requisitions → the engine's SUPPRESSED_DUPLICATE (never shown as a candidate). Company + title + location without a strong key → IDENTITY_UNCERTAIN → REVIEW, as one grouped card. |
| **Newness** | The engine's NEW / UPDATED / SEEN_BEFORE, persisted in `<out>/state/jobops-p9.sqlite`, a v2 store. `store.db.connect` refuses the legacy DB. |
| **JD handling** | Complete JD → FULL_JD. Truncated (trailing "…", "...", "see more", or an explicit flag) → PARTIAL with the partial text. Missing → SEARCH_ONLY with no text. Structured fields (location, pay, employment type) are still evaluated. JD-dependent dimensions get no false PASS: with no JD, language is UNKNOWN and relevance NOT_ASSESSED. A job is never EXCLUDED for a missing JD. A job the engine shortlists but whose JD is incomplete is **held in REVIEW** with JD_TRUNCATED / JD_MISSING; its verdicts and stored lane are not changed. |
| **Evaluation** | Every usable record goes through `EvaluationService.ingest` → policy 0.2.6 → relevance, with no alternate logic. Verdicts are PASS / UNKNOWN / FAIL, FAIL > UNKNOWN > PASS. |
| **Queue** | `plan_day` is reused unchanged. `--review-cap` is applied by a read-only adapter that changes only the value `plan_day` reads for `$review_daily_cap` (presentation). Evaluations use the real policy object, and the 0.2.6 artifact still says 10. Carry and OR-88 D+3 parking are `plan_day`'s own. |
| **Digest** (`digest.py`) | `<out>/<date>/digest.md` contains: a header (date, input, input SHA, policy, policy SHA, "Gate E: pending — Round 4 has not yet been measured"); metrics with a bottleneck line; SHORTLIST; REVIEW shown; REVIEW held (incomplete JD); REVIEW overflow; PARKED; EXCLUDED. Each SHORTLIST / REVIEW card shows title, company, location / work mode, pay as stated, relevance, newness, experience, application URL, verdicts, one-line reasons (rule note or the rule's policy condition), verbatim quotes, and flags. Sorting is STRONG first, then NEW > UPDATED > SEEN_BEFORE; REVIEW keeps `plan_day` order. |
| **JD files** | `jd/<job_id>.txt` for every SHORTLIST / REVIEW job: title, company, location, application URL, policy, flags, then the full available JD. |
| **excluded.csv** | `job_id, title, company, url, failing_dimension, verdict, reason, evidence`: one row per failing dimension of every EXCLUDED job in the export. |
| **decisions.csv** | Exactly `job_id, applied, skipped, skip_reason, notes`, blank, one row per SHORTLIST / REVIEW job. A sheet with human input is never overwritten; a fresh one goes to `decisions.pending.csv`. |
| **Decision import** (`decisions.py`) | `applied=yes` → review decision ACCEPT + application event SUBMITTED_BY_HUMAN, meaning the human applied elsewhere. `skipped=yes` → SKIP with "skip_reason \| notes". These use the existing append-only, human-only tables in the P9 state. Re-import is a no-op (a content-keyed ledger). Unknown ids and applied + skipped rows are rejected. Not Gate R; nothing is tuned. |
| **Metrics** | `metrics.json` and the digest top. It reports: jobs_in, rejected, unique_jobs, duplicates, ambiguous_identity, jd_missing / truncated, apply_url_missing, lane counts, SHORTLIST + REVIEW, per-dimension FAIL / UNKNOWN / PASS, queue (cap, shown, overflow, held, parked today), the observed conversion rate, gap_to_25 / 30, estimated source jobs for 25 / 30 (one-day estimate, labelled as such), `below_25`, and the largest bottleneck with the top 5. |

**Other changes:**
- `.gitignore` gains `/exports/` and `/runs/`, so pilot exports and local state are never committed.
- `docs/SOURCING_RUNBOOK.md` is new.

## Test results

| Result | Count |
|---|---:|
| passed | **3349** |
| failed | **0** |
| xfailed | 61 (unchanged, classified Round-2 xfails) |
| skipped | 0 |
| errors | **0** |

Of these, `tests/test_p9_sourcing.py` contributes **46** tests:

| Area | What is tested |
|---|---|
| JSON and CSV input | Day 1 (JSON) and day 2 (CSV, other aliases) run end-to-end |
| Outputs and headers | All outputs present; policy / SHA / Gate E header in the digest and on stdout |
| Metrics | Consistency: lane sum = unique jobs, per-dimension totals, gap arithmetic |
| Idempotence | A rerun of the same input and date gives byte-identical outputs; two fresh states give identical outputs; the date-order guard |
| Newness | Day 1 NEW; day 2 SEEN_BEFORE, plus UPDATED for both a pay change and a JD change |
| Dedupe | A duplicate record collapses to one canonical job; a bridging sighting → SUPPRESSED_DUPLICATE, never shown |
| Identity | Ambiguous identity → REVIEW, never EXCLUDED |
| Missing JD | Never EXCLUDED for the JD; only a structured geography FAIL excludes; language never PASS without a JD; the JD file says JD_MISSING |
| Truncated JD | Never SHORTLIST; held in REVIEW; in decisions.csv; JD file flagged |
| Review cap | Below, at and above the cap; the cap changes presentation only |
| OR-88 | D+3 non-STRONG parked with the day-4 queue below, at and over the cap; the 4-day default run parks exactly 2 on D+3 |
| Digest safety | EXCLUDED never appears in SHORTLIST / REVIEW / held / overflow / decisions (all 4 days) |
| decisions.csv | Exactly the 5 core columns, initially blank |
| Quotes and URLs | Quotes verbatim from the export; URLs preserved; search URL never presented; `apply_url_missing` counted |
| Schema | Schema error (exit 2, nothing written); record rejection; aliases and container keys |
| Decision import | Local state only; idempotent re-import; filled sheet never overwritten; decided jobs leave the next digest; unknown or contradictory rows rejected |
| **Verdict parity** | ≥ 45 jobs: every eligibility verdict, lane and relevance label equals a direct single-record engine evaluation, so P9 adds no verdict |
| Offline | Static AST check of `jobops/` imports (no socket / http / urllib / requests / ssl / subprocess / LLM SDKs); running the command loads no such module (verified at runtime); sockets refused by the autouse `no_network` fixture; the legacy DB is refused by the store |
| Integrity | 0.2.0–0.2.6 hashes; P9 fixtures contain no Round-3 ids or sentences |

## Dry-run result (synthetic, `tests/fixtures/p9/`)

The fixtures are independently authored, about 60 jobs on day 1, run over 4 days with the default cap of 10. Sample output is in `docs/reports/p9_sample_digest/`: four days of digest, metrics, excluded and decisions files, plus day-1 JD files.

| Metric | Day 1 (`day1_export.json`) |
|---|---:|
| Jobs in | 57 |
| Unique jobs | 53 |
| Duplicates | 4 (records re-listed with the same URL) |
| Ambiguous identity | 2 (one grouped REVIEW card) |
| Missing JD | 4: 2 REVIEW, 1 PARKED, 1 EXCLUDED on a structured on-site Mumbai location |
| Truncated JD | 2 (held in REVIEW) |
| No application URL | 5 (incl. 1 search-results-only URL) |
| SHORTLIST | 7 |
| REVIEW | 26 (11 shown in 10 cap slots, 13 overflow, 2 held) |
| PARKED | 9 |
| EXCLUDED | 11 |
| SHORTLIST + REVIEW | 33 (gap to 25 = 0, gap to 30 = 0) |
| Largest bottleneck | compensation UNKNOWN (19) |

- **Day 2 (`day2_export.csv`, 14 rows):** 2 UPDATED (pay figure, JD text), SEEN_BEFORE re-sightings, 4 NEW.
- **Days 3–4:** one new weak job each. On D+3 (2026-10-04) the two non-STRONG REVIEW items carried since day 1 are PARKED (OR-88).
- **Readability:** each digest is about 250 lines. Metrics and the bottleneck come first, then compact cards, so it reads in a few minutes.

## Policy integrity

- 0.2.0, 0.2.1, 0.2.2, 0.2.3, 0.2.4, 0.2.5 and 0.2.6 are unchanged and byte-identical (hashes above, re-verified after P9 and asserted by `test_policies_byte_identical`).
- No engine, policy, ruling or historical-fixture file was modified.

## Open items

None raised. No real export was available locally, so no real-input ambiguity could be observed, and no network access was attempted.

**Operational observation (not a defect, not an open item):** with an empty company registry, a JD that does not state the employer type gives employer UNKNOWN + `EMPLOYER_UNCLASSIFIED` → REVIEW. That is OR-20 as ruled. On real exports this will likely push many otherwise-clean jobs from SHORTLIST into REVIEW. If the pilot confirms it as the dominant bottleneck, the owner may want a separate task for an owner-maintained company classification list (the existing `classify_company`, OWNER_CONFIRMED). That would be an input, not a policy change. P9 does not implement it.

## Operational recommendation

The system is **ready for a manual real-export pilot**. First command:

```bash
cd ~/projects/jobs-application-automation
python3 -m jobops source \
  --input exports/<your-export>.json \
  --policy 0.2.6 \
  --out runs \
  --date YYYY-MM-DD
```

Then:
1. Read `runs/<date>/digest.md`.
2. Audit `runs/<date>/excluded.csv`.
3. Fill `runs/<date>/decisions.csv`.
4. Import it: `python3 -m jobops decisions --import runs/<date>/decisions.csv --out runs`.

See `docs/SOURCING_RUNBOOK.md`.

**Real-export mapping:** if the export's field names are not in the alias table, the run stops with a schema error that lists the keys it found. Report them; do not rename fields by hand.

## Not done (by design)

The following were not built or run: a scheduler, cron, n8n, live Apify / LinkedIn fetching, LLM extraction, resume tailoring, application submission, Round 4, Gate E measurement and Phase C beyond this manual digest.
