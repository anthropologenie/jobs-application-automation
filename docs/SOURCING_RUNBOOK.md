# Sourcing runbook (P9 manual pilot, P10 digest tiers)

JobOps reads a job export **you** downloaded and writes a daily digest. It never fetches, applies, submits, writes to recruiters or tailors your resume. You decide and apply yourself.

## 1. Download an export

Export the jobs from your source (for example an Apify LinkedIn dataset) as **JSON** (`.json` / `.jsonl`) or **CSV** and save the file. JobOps makes no network call: no Apify token, no LinkedIn access.

## 2. Put it somewhere stable

```text
~/projects/jobs-application-automation/exports/2026-10-01-linkedin.json
```

Any path works. The SHA-256 of the file is printed in the digest, so keep the file and don't edit it.

## 3. Run

```bash
cd ~/projects/jobs-application-automation
python3 -m jobops source \
  --input exports/2026-10-01-linkedin.json \
  --policy 0.2.6 \
  --out runs \
  --date 2026-10-01
```

**Run rules:**
- Use the **same `--out`** every day. `runs/state/` holds newness, carry days and your decisions, and the live `data/jobs-tracker.db` is never opened.
- Run the dates **in order**. An earlier date after a later one is refused.
- Re-running the same file on the same date changes nothing and re-renders identical output.
- `--review-cap N` only changes how many REVIEW cards are shown today (the default is 10). Verdicts and the policy are unchanged.
- There is no `--companies` option: a company-classification input is open item OI-056 (see §4a).

**Accepted field names.** The first non-empty key wins; matching ignores case, `_`, `-` and spaces. You need a title, plus at least one of company, URL or id.

| Field | Accepted keys |
|---|---|
| title | title, job_title, jobTitle, position, positionName |
| company | company, company_name, companyName, employer, organization |
| location | location, job_location, jobLocation, formattedLocation |
| job URL (posting page) | job_url, jobUrl, url, link, job_link, posting_url |
| application URL | apply_url, applyUrl, application_url, applicationUrl, apply_link |
| description (JD) | description, job_description, jobDescription, descriptionText, jd |
| work mode | work_mode, workMode, workplace_type, workplaceType, work_type, remote_type |
| pay | compensation, salary, salary_text, salary_range, salaryInfo, pay |
| employment type | employment_type, employmentType, contract_type, job_type |
| source | source, platform, site |
| posted date | posted_at, postedAt, posted_date, datePosted, publishedAt, listedAt |
| id | external_id, job_id, jobId, source_job_id, id |
| truncated JD marker | description_truncated, jd_truncated, truncated |

A top-level JSON object is accepted if it holds the list under `items`, `jobs`, `results`, `data` or `records`. If no record has a recognised title, the run stops with a schema error and writes nothing. If your export uses other names, tell the owner rather than renaming fields by hand.

## 4. Read `runs/<date>/digest.md`

**Header:**
- the input SHA;
- the policy (0.2.6) and its SHA;
- "Gate E: pending". Round 4 has not been measured, so treat verdicts as assistance, not proof.

**Tier table (top).** How this export's REVIEW jobs split into the four tiers below.

**Metrics:**
- counts: jobs in, unique, duplicates, ambiguous identity, SHORTLIST / REVIEW / PARKED / EXCLUDED;
- SHORTLIST, T1, T2, T3, T4 and READY-ISH;
- eligibility by dimension (PASS / UNKNOWN / FAIL);
- the illustrative source-jobs estimate, and the largest blocker when READY-ISH is below 25;
- the bottleneck (diagnostic only; no policy change is implied).

**Sections, in order:**
- **SHORTLIST:** every eligibility dimension passes, the JD is complete and relevance is high enough. Read these first.
- **REVIEW — T1 / T2 / T3 / T4:** today's shown REVIEW cards, up to the cap, grouped by tier (below).
- **REVIEW — held from SHORTLIST:** would shortlist, but the JD was missing or cut off (tier T4, outside the cap). Check the full posting before applying.
- **REVIEW — Overflow:** still REVIEW, carried to tomorrow, with a count per tier. A non-STRONG item carried three days is PARKED (OR-88).
- **PARKED:** weak relevance, or overflow parked. Skim weekly.
- **EXCLUDED** and **EXCLUDED by Dimension:** counts per failing dimension and rule; details in `excluded.csv`.

**Card fields:**
- **Pay: not stated** and **Mode: not stated** mean the export had no value. These are display statements; the eligibility line shows the engine's actual verdict.
- **Tier** and **Blockers** say why the job is in REVIEW. Every blocker comes from the stored verdicts, flags and JD status, e.g. "employer unclassified", "pay not stated", "work mode conflict", "JD truncated".
- Every quote (`> …`) is copied verbatim from the export.
- **Apply** is the URL exactly as exported. `apply_url_missing` means the export had none, or only a search-results link. Find the posting yourself.

## 4a. REVIEW tiers (P10, presentation only)

A tier never changes a verdict, flag, relevance label, experience label, lane or the policy. It only decides the order in which REVIEW is shown. The first matching tier applies:

| Tier | Meaning |
|---|---|
| **T1 — Nearly Ready** | Every dimension passes, except possibly *employer unclassified* and/or *pay not stated*. No other flag, no identity or source conflict, the JD is complete, and experience is not STRETCH. |
| **T2 — Stretch Experience Only** | As T1, but experience is STRETCH. |
| **T3 — Location / Work Mode Unclear** | Geography is UNKNOWN, or the work mode conflicts. |
| **T4 — Other** | Everything else, e.g. identity uncertain, source conflict, language / relationship / employment unknown, pay below target, missing or truncated JD. |

**Order within a tier:**
1. STRONG before MODERATE (then other relevance);
2. NEW, then UPDATED, then SEEN_BEFORE;
3. stated pay in or above target before any other pay state (a disclosed below-target salary never ranks above undisclosed pay);
4. job id.

**The cap.** The daily cap (10, or `--review-cap N`) is filled T1 → T2 → T3 → T4 from today's pending REVIEW pool, and the rest is listed in Overflow. Overflow jobs stay REVIEW.

The engine's own queue (`plan_day`: carry days, OR-88 parking) is unchanged and still uses the policy's ordering, so a shown card can be "carried" in the engine's count and an overflow line can be "surfaced". Each card and overflow line says which. A non-STRONG job carried three engine days is parked by OR-88 even if it was shown (open item OI-057).

**READY-ISH = SHORTLIST + T1 + T2.**
- **SHORTLIST:** actionable under the current policy without resolving an UNKNOWN.
- **T1:** potentially actionable after resolving only employer / pay uncertainty.
- **T2:** as T1, plus a STRETCH experience consideration.

READY-ISH is a diagnostic presentation metric. It is not SHORTLIST and never means "ready to apply". It means the remaining uncertainty is narrow and named on the card.

**Company classification (`--companies`): not available.** The engine can store an owner classification, but an owner "direct" entry would outrank a staffing / consultancy statement in the JD, so it cannot be added without an owner ruling (OI-056). Until then an unclassified employer stays UNKNOWN → REVIEW (T1 when it is the only blocker).

## 5. JD files for resume tailoring

`runs/<date>/jd/<job_id>.txt` has the title, company, location, application URL, policy and flags, followed by the full JD. Paste it into Claude or ChatGPT yourself when you tailor your resume. JobOps does not call any LLM.

## 6. Fill `runs/<date>/decisions.csv`

There is one row per SHORTLIST or REVIEW job. Columns: `job_id, applied, skipped, skip_reason, notes`.

- **Applied:** put `yes` in `applied`.
- **Not applying:** put `yes` in `skipped` and a short `skip_reason`, e.g. "pay too low" or "stack mismatch".
- **Undecided:** leave the row blank. The job stays pending.

A re-run never overwrites a sheet you have started; a fresh blank sheet goes to `decisions.pending.csv`.

## 7. Import your decisions

```bash
python3 -m jobops decisions --import runs/2026-10-01/decisions.csv --out runs
```

- Decisions are stored only in `runs/state/`. Importing again is a no-op.
- Decided jobs leave the next digest.
- These labels are your record. They are not a Gate R measurement, and nothing is tuned from them automatically.

## 8. Interpret the metrics

| Metric | Meaning |
|---|---|
| `SHORTLIST`, `review_tiers` (T1–T4) | Lane count and REVIEW split by tier; T1 + T2 + T3 + T4 = REVIEW. |
| `READY_ISH` | SHORTLIST + T1 + T2. Diagnostic; not "ready to apply". |
| `illustrative_source_jobs_for_25_ready_ish` / `_30_` | Illustrative one-day estimate, not an application-supply forecast: 25 (or 30) ÷ (READY-ISH ÷ jobs in). Empty when READY-ISH is 0. |
| `ready_ish_below_25`, `largest_blocker_outside_ready_ish` | When READY-ISH is below 25, the most frequent blocker among T3 / T4 jobs. More source volume alone does not remove a blocker. |
| `shortlist_plus_review`, `gap_to_25`, `gap_to_30` | P9 counts kept for continuity. **Not** an estimate of actionable supply. |
| `bottleneck` | The single largest reason jobs did not reach SHORTLIST. Diagnostic only; no policy change is implied. |
| `excluded_by_dimension`, `excluded_by_rule` | Rows of `excluded.csv` per failing dimension / rule (a job failing two dimensions counts twice). |
| `review_queue_tiers` | Shown and overflow per tier, and how far the shown set differs from the engine's surfaced set (OI-057). |

Common blockers:
- **pay not stated:** compensation UNKNOWN (COMP_UNDISCLOSED).
- **employer unclassified:** the JD does not say what kind of company it is (EMPLOYER_UNCLASSIFIED).
- **geography unclear / work mode conflict:** the work arrangement is missing, hybrid days are not stated, or the sources disagree.
- **geography FAIL** (EXCLUDED): the role is not remote-from-India or Bengaluru hybrid.

## 9. Audit `excluded.csv`

Each row has:
- the job and its URL;
- the failing dimension;
- the rule ID and its condition;
- the evidence, quoted from the export.

During the pilot, read every row and ask: "was this really ineligible?" Record any false exclusion for the owner. Do not edit the policy yourself.
