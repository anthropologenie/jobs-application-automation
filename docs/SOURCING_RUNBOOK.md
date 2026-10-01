# Sourcing runbook (P9, manual pilot)

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

**Metrics:**
- counts and SHORTLIST + REVIEW;
- the gap to 25 and to 30;
- the largest bottleneck.

**Sections:**
- **SHORTLIST:** every eligibility dimension passes, the JD is complete and relevance is high enough. Read these first.
- **REVIEW (shown today):** something is UNKNOWN or flagged; the "Why" line says what. Up to the cap. A grouped pair (IDENTITY_UNCERTAIN) may be one job listed twice.
- **REVIEW held from SHORTLIST:** would shortlist, but the JD was missing or cut off. Check the full posting before applying.
- **REVIEW overflow:** carried to tomorrow. A non-STRONG item carried three days is PARKED (OR-88).
- **PARKED:** weak relevance, or overflow parked. Skim weekly.
- **EXCLUDED:** see `excluded.csv`.

**Card fields:**
- Every quote (`> …`) is copied verbatim from the export.
- **Apply** is the URL exactly as exported. `apply_url_missing` means the export had none, or only a search-results link. Find the posting yourself.

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
| `shortlist_plus_review` | Today's viable candidates. |
| `gap_to_25`, `gap_to_30` | How far short of 25 or 30 candidates today is. |
| `estimated_source_jobs_for_25` | Today's conversion rate applied to 25; an estimate from one day, not a promise. |
| `bottleneck` | The single largest reason jobs did not reach SHORTLIST. Diagnostic only: the policy does not change because of one day. |

Common bottlenecks:
- **compensation UNKNOWN:** pay was not stated.
- **employer UNKNOWN:** the JD does not say what kind of company it is.
- **geography FAIL:** the role is not remote-from-India or Bengaluru hybrid.

## 9. Audit `excluded.csv`

Each row has:
- the job and its URL;
- the failing dimension;
- the rule ID and its condition;
- the evidence, quoted from the export.

During the pilot, read every row and ask: "was this really ineligible?" Record any false exclusion for the owner. Do not edit the policy yourself.
