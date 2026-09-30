# P0-10 — Per-Candidate Time Instrumentation

**Task:** P0-10 · **Artifact:** `timing/jobops-timing-0.1.0.json` (`jobops-timing@0.1.0`)
**Authority:** `P0_IMPLEMENTATION_SPEC.md` §11, §13 X10 · `JOBOPS_SCALING_EXECUTION_PLAN.md` §4 P0-10
**Status:** implemented. **No P0 exit is claimed** — X10 requires ≥7 days of recorded human
activity and none has been recorded yet.

P0-10 answers one question: *how much human effort does JobOps require to turn discovered
opportunities into deliberate application decisions, and is that improving?* It **observes**
the funnel. It does not reshape it, and it changes nothing about how a candidate is
evaluated, presented or decided.

---

## 1. The one thing P0-10 adds

Nothing in JobOps recorded **the moment an application was actually submitted**. Everything
else it needs already existed.

| Fact | Where it already lived | Added by P0-10 |
|---|---|---|
| Machine verdict | `data/ingestion/candidates/<run>.jsonl` | — |
| Human decision | `data/review/decisions.jsonl` | — |
| Application state | `data/jobs-tracker.db :: opportunities` | — |
| **Submission event** | **nowhere** | **`data/application/submissions.jsonl`** |

Four facts, four stores. They are not merged, and a submission is not folded into the
decision ledger, because "the human decided to apply" and "the human applied" must stay
grep-distinct.

---

## 2. Events, and exactly what each timestamp means

Every event below is declared in the artifact with its store, origin and precision.

### Observed (reused, unchanged)

| Event | Timestamp | Origin | Means |
|---|---|---|---|
| `CANDIDATE_OBSERVED` | `provenance.source_fetched_at` | machine | the source returned the posting to an ingestion run |
| `CANDIDATE_DETAIL_FETCHED` | `provenance.detail_fetched_at` | machine | the JD the gate evaluates was retrieved |
| `CANDIDATE_INGESTED` | `scraped_jobs.scraped_at` | machine | a candidate row was created (**not** discovery) |
| `CANDIDATE_EVALUATED` | `gate_verdict.evaluated_at` | machine | the gate produced a verdict under a named ruleset |
| `RUN_STARTED` / `RUN_FINISHED` | run manifest | machine | an ingestion run began / closed |
| `HUMAN_DECISION` | `decisions.jsonl :: decided_at` | human | the human recorded a review decision |
| `APPLICATION_PROMOTED` | `opportunities.created_at` (bridged rows) | machine record of a human action | the candidate entered the application workflow |

### Observed (new)

| Event | Timestamp | Origin | Means |
|---|---|---|---|
| `APPLICATION_SUBMITTED` | `submissions.jsonl :: submitted_at` | human | **the human states they submitted the application themselves, outside JobOps** |

Every submission record also carries `recorded_at` (when the line was appended) and
`submitted_at_source` (`human_stated` or `recorded_now`), so a record made three days later
stays visibly late rather than looking contemporaneous.

### Declared, not observed

| Quantity | Why not | Consequence |
|---|---|---|
| `QUEUE_AVAILABLE` | the queue is a pure projection — building it persists nothing, so nothing records that a candidate was surfaced to a person | `time_from_queue_availability_to_decision` is **NOT_MEASURABLE**. A run-close lower bound sits on the timeline, clearly labelled derived, and no metric consumes it |
| `REVIEW_STARTED` / `REVIEW_ENDED` | no command, endpoint or UI event marks human attention; `--show` is a read-only display and is not evidence a person read it | **ACTIVE HUMAN EFFORT IS NOT DIRECTLY MEASURABLE** |
| `APPLICATION_READY_TO_SUBMIT` | no readiness state exists; a `drafted`-equivalent status is JS-11 / P1-06 | the preparation stage of `P0_SPEC` §11.2 is NOT_MEASURABLE; its measurable neighbours are decision→promotion and decision→submission |
| per-candidate system stage timers | P0-06 records run-level wall time, not per-stage durations, and P0-10 does not edit the ingestion pipeline | run wall time and the observed→detail→evaluated instants bound the system cost instead |

### Explicitly **not** submission events

- **`opportunities.status = 'Applied'`** — an application-workflow state in an 11-value enum.
  Nothing in this repository defines when it is set or by whom, and its companion
  `applied_date` is a `DATE` (day precision, no time of day). It is counted separately as
  `legacy_applied_rows` and is used in **no** interval.
- **`ACCEPT`** — the decision to apply. It is the *start* of time-to-submit and can never be
  its end.
- **`POST /api/import-scraped-job/{id}`** — the bridge copies a candidate into
  `opportunities` with status `Lead`. It contacts no employer.

---

## 3. Elapsed lifecycle time vs active human effort

**Every duration P0-10 reports is elapsed wall-clock time between two recorded moments.**
It spans nights, weekends and everything else the human was doing.

> A candidate evaluated at 10:00 and decided at 10:20 gives
> `time_from_evaluation_to_decision = 20 minutes`.
> That is **not** `human_review_time = 20 minutes`, and nothing in this package names it so.

`ACTIVE HUMAN EFFORT IS NOT DIRECTLY MEASURABLE` in the current architecture. Consequently
`applications_per_unit_of_human_effort` is reported `NOT_MEASURABLE` rather than faked by
dividing by an elapsed interval. Measuring it would require an explicit per-candidate
start/stop timer — an intrusive change to the operator's workflow that `P0_SPEC` §11 does not
require and P0-10 does not make.

---

## 4. Missing-data semantics — four different answers

| State | Meaning |
|---|---|
| `MEASURED` | computed from events that exist. **A value of 0 here is a real zero.** |
| `NOT_AVAILABLE` | the mechanism exists; nothing has been recorded through it yet |
| `INSUFFICIENT_DATA` | some data, below the declared minimum sample (an empty denominator is always this, never a rate of 0.0) |
| `NOT_MEASURABLE` | no observation mechanism exists at all |
| `INCONSISTENT` | both events exist but are out of order; the interval is **withheld**, never negated or absolute-valued |

A bare number is never emitted for a missing measurement, so no reader has to guess which of
the five a `0` meant.

---

## 5. Metrics

**Elapsed lifecycle durations** (median, p90, n; `p90` carries a caveat below n=10):
`time_from_evaluation_to_decision` · `time_from_unknown_to_human_resolution` ·
`time_from_decision_to_submission` · `time_from_evaluation_to_submission` ·
`time_from_decision_to_promotion` · `time_from_queue_availability_to_decision`
(**NOT_MEASURABLE**).

**Counts** — each counting a deliberately different thing:
`candidates_discovered` · `candidates_ingested` · `candidates_evaluated` ·
`distinct_review_candidates` · `candidates_human_reviewed` · `human_decisions` ·
`applications_promoted_from_evaluated_funnel` · `actual_submissions` ·
`accepted_without_submission_record` · `legacy_not_evaluated_count` ·
`legacy_rows_suppressed_as_duplicates` · `definite_duplicates_suppressed` ·
`probable_duplicates_needing_human_judgement`.

**Rates:** `unknown_rate` · `pass_to_apply_rate` · `unknown_to_apply_rate` ·
`fail_to_application_rate` · `definite_duplicate_suppression`.

**Per `P0_SPEC` §11.4, never aggregate-only:** `veto_rate_per_reason_code` and
`unknown_rate_per_dimension`.

**Throughput per UTC day:** `candidates_reviewed_per_period` · `decisions_per_period` ·
`submissions_per_period`. Days with no activity are **absent** from the series rather than
recorded as zero — nothing distinguishes "reviewed nothing" from "did not use JobOps".

---

## 6. Populations kept apart

- **Current evaluated funnel** — candidates carrying a gate verdict. Every duration and every
  verdict rate is computed over this population and no other.
- **Legacy `NOT_EVALUATED`** — 75 rows no gate evaluation covers. Counted once, alone, as
  `legacy_not_evaluated_count`. **Not backfilled**, given no invented evaluation timestamp,
  and present in no throughput figure. (A further 2 unevaluated rows are suppressed as
  duplicates and counted as `legacy_rows_suppressed_as_duplicates`, so the two populations do
  not double-count.)
- **Definite duplicates** (L1/L2/L4) — suppressed from active review by P0-07/P0-08, excluded
  from `distinct_review_candidates` so re-observing one posting cannot inflate throughput.
- **Probable duplicates** (L3 / `IDENTITY_UNCERTAIN`) — counted as the real review
  opportunities they are, and reported separately so the human duplicate-judgement load is
  visible.

---

## 7. Commands

```bash
# the report
python3 -m timing.run_timing_report
python3 -m timing.run_timing_report --json

# one candidate's full timeline
python3 -m timing.run_timing_report --candidate scraped_jobs:78

# record that YOU submitted an application (the human's own statement)
python3 -m timing.run_timing_report --record-submission scraped_jobs:78 \
    --submitted-at 2026-09-07T10:30:00+00:00 \
    --method "company careers portal" --note "referral link"

# or, if it just happened
python3 -m timing.run_timing_report --record-submission scraped_jobs:78 --submitted-now

# correct an earlier record — append-only, the original stays readable
python3 -m timing.run_timing_report --record-submission scraped_jobs:78 \
    --submitted-at 2026-09-07T10:30:00+00:00 --supersedes sub-000000-abc123def456
```

**Recording a submission is not submitting one.** JobOps submits nothing, contacts no
employer or ATS, and makes no external request. The human remains the actor who applies;
this command writes one line in a file about something they already did elsewhere.

---

## 8. Metric-integrity properties

1. **`ACCEPT` never creates a submission timestamp.** The two live in different files, and no
   code path derives one from the other. A candidate with an `ACCEPT` and no submission is
   reported as `accepted_without_submission_record`, never as a 0-minute time-to-submit.
2. **No substitution.** A missing endpoint yields `NOT_AVAILABLE` naming the missing event.
   No timestamp stands in for another.
3. **Recording later makes the number worse, not better.** `submitted_at` is the human's
   stated moment; `recorded_at` is kept alongside it, so a late record is visible as late.
   The metric cannot be improved by pressing a button earlier.
4. **A suppressed duplicate is not a review opportunity**, so re-observing a posting cannot
   raise throughput.
5. **A negative interval is never reported.** Out-of-order events are `INCONSISTENT` and the
   candidate is named.
6. **P0-10 writes nothing another task owns** — one read-only SQLite connection, one
   append-only file, and no write to the ledger, the decision ledger, or the database.

---

## 9. Known limitations

- Active human effort is not measurable (§3).
- Human review *start* is not observed, so review duration cannot be measured; only
  evaluation→decision elapsed time can.
- A candidate the human reads and does not decide on leaves no trace, so
  `candidates_human_reviewed` **under-counts** review.
- `submitted_at` is self-reported. `submitted_at_source` and `recorded_at` are the only
  discriminators between a contemporaneous and a reconstructed record.
- `scraped_jobs.scraped_at` and `opportunities.created_at` are stored with no timezone
  offset and are read as UTC — which is what SQLite's `CURRENT_TIMESTAMP` writes.
- `opportunities.status` transitions are not timestamped and `applied_date` is day precision,
  so neither is an interval endpoint.
- **OR-09 and OR-10 remain open**: what the "~15/day" baseline counted, and whether 25–30
  means *surfaced* or *submitted*. Both quantities are reported separately and neither is
  asserted as a target (`P0_SPEC` §11.5).
