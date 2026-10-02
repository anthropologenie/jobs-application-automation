# JobOps P10 — Digest Tiering for the Real-World Pilot (2026-10-01 pilot, built 2026-10-02)

## Final status

```text
READY FOR REVIEW
```

P10 changes only how the REVIEW lane is presented: four tiers, the order of the shown cards, and new metrics.

- **Nothing the engine decides has changed.** That means every verdict, flag, relevance label, experience label, lane, newness state and queue / carry / OR-88 state. Proof: an exact comparison with the unmodified P9 code on all four P9 fixture days, and with the real-pilot P9 state.
- **No policy was touched.** No policy, owner ruling, engine module or historical fixture was modified, and no 0.2.7 was created.
- **Not done, by design:** Round 4, Gate E, a scheduler and the network.

## Starting state

| Item | Value |
|---|---|
| Branch | `jobops-v2-engine` |
| HEAD | `6913f1237c31c3d78035fd0ce761657c5ef17ef3` (P9) |
| Policy tag | `policy-0.2.6` → `4f5c29f` (the P8b governance commit; P9 is one commit on top) |
| Working tree | clean |

## Baseline

The test command is the same as in P8 / P9. The four P0 tests that read `data/jobs-tracker.db` are excluded:

```bash
python3 -m pytest tests -q -p no:cacheprovider \
  --ignore=tests/test_p0_06_linkedin_ingestion.py --ignore=tests/test_p0_07_identity_dedup.py \
  --ignore=tests/test_p0_08_review_queue.py --ignore=tests/test_p0_10_time_instrumentation.py
```

Baseline result: **3349 passed, 0 failed, 61 xfailed, 0 skipped, 0 errors.** This matches the expected baseline.

| Policy | SHA-256 before P10 | After P10 |
|---|---|---|
| 0.2.0 | `65f74aec883d475989ea0594fac070f547c96a697bc1f7f4b46cf8e0d5dd567a` | identical |
| 0.2.1 | `af19a3fd998e945cba19ce68f0e36f2eba4156e8bfd5255ac4ea7dacf7f5ea7d` | identical |
| 0.2.2 | `3743bbaebce2b5f3143ec0a211d6c63aa35b8113dce03b1622876ef43eeed734` | identical |
| 0.2.3 | `918bf66e7d83d06d7ff7b10c6d8b1309cbabd033331315510851110856659d77` | identical |
| 0.2.4 | `735934bf33533a31d207349cf689a3df6dafcdacc9c6a11b889b92e5af8c8136` | identical |
| 0.2.5 | `27fe5d1accff78ce9db8ccc5f42a7d905b3e709a474d93d446e19a795ad53c93` | identical |
| 0.2.6 | `de527c5d1dceb400913ec42e5aa527f19cd809e5054fcef5c61337d7fb890455` | identical |

## Changes

### Files

| File | Change |
|---|---|
| `jobops/tiers.py` (new) | Tier rule, blockers, within-tier order key, unit ordering, counts. Pure functions over the stored evaluation; no I/O. |
| `jobops/sourcing.py` | `collect` annotates REVIEW jobs with tier and blockers. It re-orders today's pending REVIEW units (what `plan_day` returned: surfaced + carried) and shows the first `cap`. `plan_day` is called exactly as in P9, before any tiering. |
| `jobops/digest.py` | Tier table, tier sections, overflow by tier, READY-ISH metrics and estimate, EXCLUDED by Dimension, per-dimension table, labelled bottleneck, Pay / Mode "not stated", Tier / Blockers on every REVIEW card. |
| `jobops/cli.py` | stdout summary shows `READY_ISH` and `review_tiers`; docstring. |
| `tests/test_p10_tiering.py` (new) | 73 tests (below). |
| `tests/p10_engine_snapshot.py` (new) | Engine-state snapshot that reads only the v2 store, never the digest. It is also the generator of the P9 reference. |
| `tests/fixtures/p10/p9_engine_reference.json` (new) | Engine state from the **unmodified P9 code** (generated before any P10 edit, `jobops/` diff empty at the time) over the four P9 fixture days: 227 requisition-days. |
| `tests/fixtures/p10/make_tiers_export.py`, `tiers_export.json` (new) | Independently authored 21-job synthetic export that produces every tier, overflow and two EXCLUDED dimensions. Fictional companies only. |
| `tests/test_p9_sourcing.py` | **Section lookup only** (details below). |
| `docs/SOURCING_RUNBOOK.md` | Tiers, READY-ISH, the cap, the metrics table, and the `--companies` open item. |
| `docs/architecture/JOBOPS_V2_OPEN_ITEMS.md` | Appended "P10 Open": OI-056 … OI-060. |
| `docs/reports/p10_sample_digest/` (new) | Sample digests (synthetic only). |

**P9 test adaptation.** The P9 digest headings "REVIEW (shown today)" and "REVIEW overflow (carried to tomorrow)" are replaced by the tier sections and "REVIEW — Overflow", as P10 §16 requires. With the old headings, four P9 tests would have passed **vacuously**: the section lookup returned an empty string, so their assertions checked nothing. The lookups were therefore pointed at the new sections, with `assert candidates` / `assert shown` guards so they can never be vacuous again.

One assertion changed in substance: `test_ambiguous_identity_is_review_not_excluded`.
- **Before:** it expected both identity-uncertain cards among the shown cards.
- **Why that no longer holds:** the pair is tier T4, so with cap 10 it is now listed in the overflow.
- **After:** the test asserts both members are in REVIEW (shown or overflow), are labelled "identity uncertain", and are never EXCLUDED. That is the property the test's name states.

No other expected value in any P9 or historical test was changed.

### Tier calculation (`jobops/tiers.py`)

Tiers are computed for every job in this export's REVIEW population: the engine REVIEW lane, plus SHORTLIST jobs held for an incomplete JD. That is exactly the set the REVIEW metric counts, so T1 + T2 + T3 + T4 = REVIEW. The first match wins:

| Tier | Rule as implemented (stored data only) |
|---|---|
| T1 Nearly Ready | Every dimension PASS, except possibly employer UNKNOWN whose flags are exactly `{EMPLOYER_UNCLASSIFIED}` and/or compensation UNKNOWN whose flags are exactly `{COMP_UNDISCLOSED}`. The review-routing flags must be ⊆ {EMPLOYER_UNCLASSIFIED, COMP_UNDISCLOSED, EXPERIENCE_STRETCH}, so there is no IDENTITY_UNCERTAIN, SOURCE_CONFLICT, WORK_MODE_CONFLICT, BELOW_TARGET … The JD is complete, and experience is not STRETCH. |
| T2 Stretch Experience Only | As T1, with experience STRETCH (label STRETCH or flag EXPERIENCE_STRETCH). |
| T3 Location / Work Mode Unclear | Geography UNKNOWN, or a WORK_MODE_CONFLICT flag. |
| T4 Other | Everything else. |

**Interpretations, stated so the owner can check them:**
1. **Strict T1 / T2.** A job whose dimensions all PASS but which carries a review-routing pay flag (BELOW_TARGET, COMPENSATION_REVIEW) is **T4**, not T1. This follows the §8 list of allowed uncertainty and §13 (below-target pay is never lifted over undisclosed pay). Recorded as OI-058.
2. **T3 is first-match.** Geography UNKNOWN puts a job in T3 even when another blocker exists (e.g. also JD_MISSING), as §10 specifies.
3. **Held jobs are T4.** A SHORTLIST job held for an incomplete JD is T4, because JD_MISSING / JD_TRUNCATED disqualify T1 / T2. It keeps its P9 section, outside the daily cap.

**Blockers.** These come only from stored verdicts, flags, JD status and the relevance label. Examples: "employer unclassified", "pay not stated", "geography unclear (work arrangement absent)", "work mode conflict", "language unknown", "employer of record", "JD missing", "JD truncated", "identity uncertain", "pay below target". An unmapped flag is shown as its own name in lower case; nothing is invented.

### Review ordering

The key within a tier is: relevance (STRONG, MODERATE, then other), then newness (NEW, UPDATED, SEEN_BEFORE), then pay, then job id.
- **Pay:** 0 when the compensation verdict is PASS with IN_TARGET / ABOVE_TARGET and no BELOW_TARGET / COMPENSATION_REVIEW flag; otherwise 1.
- **Below-target pay:** a disclosed below-target salary ties with undisclosed pay and is never ranked above it.
- **Groups:** an identity-uncertain group keeps its member ids and takes its best member's key.

### Cap behaviour

`plan_day` runs unchanged. The pool is its `review_today` + `review_carried` units; its OR-88-parked units never enter the pool. The pool is sorted by tier key, the first `cap` units (default 10, or `--review-cap`) are shown, and the rest are listed as **REVIEW — Overflow**. The held-for-JD section stays outside the cap, as in P9. No lane or stored state is changed.

### Digest presentation

The digest is laid out in this order:
1. header (policy, policy SHA, "Gate E: pending");
2. **tier table** (top);
3. metrics;
4. SHORTLIST;
5. the four REVIEW tier sections;
6. held;
7. Overflow, with counts by tier;
8. PARKED;
9. EXCLUDED;
10. **EXCLUDED by Dimension**, by dimension and by rule, from `excluded.csv`.

Every REVIEW card shows **Tier** and **Blockers**. Missing values display as **Pay: not stated** and **Mode: not stated**; the eligibility line still shows the engine's verdict.

The bottleneck line now reads "Diagnostic only. No policy change is implied." Because the shown set can differ from the engine's surfaced set (OI-057), each engine-carried shown card and each overflow line says what the engine did with it, and the digest prints an "Engine queue note" with both counts.

### Metrics

The original metrics are kept:
- jobs_in, rejected, unique_jobs, duplicates, ambiguous_identity, JD missing / truncated, apply URL missing;
- SHORTLIST / REVIEW / PARKED / EXCLUDED;
- per-dimension PASS / UNKNOWN / FAIL;
- queue counts and bottleneck.

New metrics:
- `review_tiers`;
- `READY_ISH` (= SHORTLIST + T1 + T2), with its definition;
- `ready_ish_conversion_rate`, `ready_ish_gap_to_25/30`, `ready_ish_below_25`;
- `illustrative_source_jobs_for_25/30_ready_ish`;
- `largest_blocker_outside_ready_ish` (most frequent blocker among T3 / T4) and `largest_blocker_in_review`;
- `excluded_by_dimension`, `excluded_by_rule`;
- `review_queue_tiers` (shown / overflow by tier, engine divergence counts).

**Corrected source-jobs estimate.** The P9 keys `estimated_source_jobs_for_25/30` and `observed_conversion_rate`, which were built on SHORTLIST + REVIEW, are **removed**. In their place:

```text
illustrative_source_jobs_for_T_ready_ish = ceil(T / (READY_ISH / jobs_in))   for T = 25, 30
```

It is computed only when READY-ISH > 0, and the digest labels it "Illustrative one-day estimate — not an application-supply forecast". When READY-ISH < 25, the digest prints "READY-ISH is below 25." and names the largest T3 / T4 blocker, adding that more source volume alone does not remove it.

`shortlist_plus_review` and `gap_to_25/30` remain as P9 counts. Both the digest and metrics.json label them "not an estimate of immediately actionable supply". "Gate E: pending" is unchanged.

### Company classification — investigation

**Result: not supported without a policy / architecture change, so not implemented and recorded as OI-056.**

What already exists:
- `EvaluationService.classify_company` and the append-only `company_classification` table, with basis OWNER_CONFIRMED / REGISTRY_LIST / INFERRED_FROM_EVIDENCE;
- `company.registry.resolve_classification`, used at evaluation time.

Why it cannot be used as is:
1. **An owner row outranks the JD.** `resolve_classification` returns any registry row before looking at text signals. An owner "direct" entry would therefore override a JD stating staffing / consultancy / IT services / third-party payroll, which violates P10 §28 ("never override an explicit negative employer classification").
2. **A run-time guard cannot fix it.** Rows are company-wide, persistent and append-only, so a guard at import cannot protect later sightings.
3. **"direct" has no single engine class.** ENTERPRISE_DIRECT gives EMPR-R07 PASS with NEUTRAL preference; PRODUCT / AI_NATIVE / GCC / ENGINEERING_LED give EMPR-R05 PASS with PREFERRED_* preference. Choosing one is an owner decision.

The smallest change, and which policy semantics would stay unchanged, are in OI-056. A test (`test_companies_option_not_implemented`) pins that `--companies` is not accepted.

## Policy integrity

- **0.2.0 – 0.2.6 unchanged.** Hashes above were re-verified after P10 and asserted by `test_policies_byte_identical`.
- **Nothing else governed was touched.** No file under `policy/`, `evaluation/`, `store/`, `company/` or `identity/` changed, and neither did `OWNER_RULINGS_LOG.md` or any historical fixture or expected output.
- **No 0.2.7.** No OR-ruling was added.

## Verdict integrity (P9 vs P10)

| Property | Result |
|---|---|
| Verdicts (all six dimensions, with rule ids and flags) | **unchanged** |
| Lanes | **unchanged** |
| Relevance | **unchanged** |
| Experience | **unchanged** |
| Newness | **unchanged** |
| Queue state (carry_days, first_review / last_planned / last_surfaced day, overflow_parked_on) | **unchanged** |

**Evidence:**
1. `test_parity_with_p9_engine_state_all_days` compares every requisition on every one of the four P9 fixture days (227 requisition-days) with the P9-generated reference, field for field.
2. The reference is sensitive: a cap-5 run differs from it on 26 requisition-days.
3. On the real pilot export, the P10 engine state equals the P9 pilot state (`runs/state`, opened read-only) for all 207 requisitions, including queue state.

## Test totals (after P10)

| Result | Count |
|---|---:|
| passed | **3422** (3349 baseline + 73 P10) |
| failed | **0** |
| xfailed | **61** (unchanged; not counted as passes) |
| skipped | **0** |
| errors | **0** |

**What the 73 P10 tests cover:**
- **Tier boundaries:** 24 parametrised cases, covering T1 / T2 / T3 / T4 boundaries and every "arbitrary UNKNOWN is not T1" case. Also: the tier does not mutate the view.
- **Blockers:** 10 cases; blockers derive from stored flags only.
- **Ordering:**
  - T1 > T2 > T3 > T4, with the lower tier holding stronger attributes;
  - STRONG > MODERATE, NEW > UPDATED > SEEN_BEFORE, job-id tie-break;
  - pay tie-break, which never lifts below-target pay and never outranks newness;
  - a group ranks by its best member.
- **Fixture and digest:**
  - every tier produced; READY-ISH and estimate arithmetic; READY-ISH 0 gives no estimate;
  - "ready to apply" appears only negated;
  - digest section order; Tier / Blockers on every card;
  - Pay / Mode "not stated" is display-only; EXCLUDED by Dimension equals `excluded.csv`.
- **Cap:** fewer than the cap (40), exactly the cap (16), more than the cap (10, default, 8). Fill order T1 → T2 → T3 → T4, and shown / overflow stay REVIEW. Different caps never change verdicts or lanes.
- **Carry and D+3:**
  - P9 parity on all four days; carry_days and newness equal P9 on each day;
  - D+3 parks req_0000027/28 (non-STRONG) on day 4, and they appear in no tier section or overflow;
  - a two-day re-sighting gives SEEN_BEFORE and carry day 2;
  - the engine-divergence counts match the store.
- **Idempotence:** a rerun on the same input, date, state and policy is byte-identical; two fresh states give byte-identical output.
- **Mutation (§35), in the suite and undone after each run:**

| Mutation | Caught by |
|---|---|
| reverse tiers | tier check + cap-fill check |
| drop tier | tier check + cap-fill check |
| reverse relevance | STRONG > MODERATE check |
| drop newness | newness check |
| drop pay tie-break | pay check |
| T1 / T2 rule always true | 18 of 24 tier cases fail |

  After restoring, every check passes.
- **Safety:**
  - a P10 run loads no network / LLM module (the P9 static AST check covers `jobops/tiers.py` too);
  - `--companies` is rejected;
  - the P10 fixture is independent of Round 3 and regenerates byte-identically.

## Tier counts

| Run | jobs in | SHORTLIST | REVIEW | T1 | T2 | T3 | T4 | READY-ISH | Illustrative source jobs for 25 / 30 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| P9 fixtures day 1 (`day1_export.json`) | 57 | 7 | 26 | 20 | 0 | 0 | 6 | 27 | 53 / 64 |
| P9 fixtures day 2 (`day2_export.csv`) | 14 | 6 | 8 | 8 | 0 | 0 | 0 | 14 | 25 / 30 |
| P9 fixtures day 3 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a (READY-ISH 0) |
| P9 fixtures day 4 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | n/a (READY-ISH 0) |
| P10 tiers fixture | 21 | 2 | 16 | 7 | 2 | 4 | 3 | 11 | 48 / 58 |

The P9 fixtures contain no STRETCH or geography-UNKNOWN REVIEW job, which is why the P10 tiers fixture was authored.

Day-1 T4 jobs:
- the identity-uncertain pair;
- two NOT_ASSESSED jobs with a missing JD and language unknown;
- two jobs held for a truncated JD.

## Cap result (default cap 10)

Counts are jobs. A grouped pair is one cap slot.

| Run | Shown T1 / T2 / T3 / T4 | Overflow T1 / T2 / T3 / T4 | Engine-surfaced but in overflow | Engine-carried but shown |
|---|---|---|---:|---:|
| P9 day 1 | 10 / 0 / 0 / 0 | 10 / 0 / 0 / 4 | 2 | 1 |
| P9 day 2 | 10 / 0 / 0 / 0 | 14 / 0 / 0 / 4 | 2 | 1 |
| P9 day 3 | 10 / 0 / 0 / 0 | 14 / 0 / 0 / 4 | 2 | 1 |
| P9 day 4 | 10 / 0 / 0 / 0 | 14 / 0 / 0 / 2 | 2 | 1 |
| P10 tiers fixture | 7 / 2 / 1 / 0 | 0 / 0 / 3 / 3 | 3 | 3 |
| P10 tiers fixture, `--review-cap 20` | 7 / 2 / 4 / 3 | 0 / 0 / 0 / 0 | 0 | 0 |

On day 4, the two non-STRONG T4 items were PARKED by OR-88, exactly as in P9.

## Company classification

**Not supported** without a policy / architecture change, so it was not implemented. There are no matched or affected counts. See OI-056.

## Open items (new; none answered)

| OI | Type | Summary |
|---|---|---|
| OI-056 | Architecture / policy | Company-classification file as structured evidence. A registry row outranks a negative JD signal, and "direct" has no single engine class. |
| OI-057 | Queue presentation vs OR-65 / OR-88 | The digest shows the tier order, but `plan_day` counts carry and D+3 by policy order. A non-STRONG job shown every day can still be parked on D+3; a STRONG job surfaced by the engine can sit in tier overflow indefinitely (seen in the P9 fixtures on all four days and in the real pilot, 10 / 10). |
| OI-058 | Presentation | Is an all-PASS job with BELOW_TARGET / COMPENSATION_REVIEW T1 or T4? (P10: T4.) |
| OI-059 | Policy (Q1) | Should undisclosed compensation stay UNKNOWN / review? Not answered. |
| OI-060 | Policy (Q2) | Should an unclassified employer stay UNKNOWN / review when there is no negative signal? Not answered. |

Each is recorded in `docs/architecture/JOBOPS_V2_OPEN_ITEMS.md` with its question, reason, affected policy and current behaviour.

## Real pilot observation (diagnostic only; nothing committed)

**Setup.**
- Input: `exports/linkedin-2026-10-01.json`, SHA-256 prefix `9af542a6c8b7` (the same file as the P9 pilot run).
- Run: P10, `--date 2026-10-01`, default cap, output into the session scratchpad.
- Real data was not touched: `runs/` and `exports/` were not modified, and both stay git-ignored.

**Unchanged from the P9 pilot run:**

| jobs in | unique | duplicates | ambiguous identity | SHORTLIST | REVIEW | PARKED | EXCLUDED |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 300 | 207 | 93 | 9 | 0 | 184 | 2 | 21 |

Per-dimension UNKNOWN: compensation 202, employer 185, geography 117 (same as P9).

**New presentation metrics:**

| T1 | T2 | T3 | T4 | READY-ISH | READY-ISH / jobs in | Illustrative source jobs for 25 / 30 |
|---:|---:|---:|---:|---:|---:|---|
| 13 | 25 | 110 | 36 | 38 | 12.7 % | 198 / 237 |

- **Most frequent REVIEW blocker:** employer unclassified (152), then pay not stated (139) and experience stretch (132).
- **Largest blocker outside READY-ISH (T3 / T4):** employer unclassified (117), then experience stretch (107), pay not stated (103), geography unclear (work arrangement absent) (60) and geography unclear (hybrid days unspecified) (24).
- **Queue:** 10 shown, all T1 and all STRONG; overflow is T1 3, T2 25, T3 110, T4 36. The engine-surfaced and tier-shown sets differ completely (10 / 10, OI-057). Because every shown job is STRONG, there is no D+3 consequence that day.
- **EXCLUDED by dimension:** geography 10, employment 6, compensation 3, employer 2, relationship 2, language 0. By rule: EMP-R03 6, COMP-R01 3, then GEO-R03 / R07 / R11 / R15, EMPR-R09 and REL-R06 at 2 each, and GEO-R10 / R12 at 1 each.

**Observation, not a recommendation.** READY-ISH (38) is above 25 on this single day. The T3 pool (110) is mostly missing work-arrangement information, and 117 of the T3 / T4 jobs also carry "employer unclassified". Volume alone does not clear either blocker; Q1 / Q2 / OI-056 are the owner's decisions.

## Not done (by design)

The following were not done:
- no policy 0.2.7, no OR-ruling and no owner-ruling change;
- no Round 4 corpus or measurement, and no Gate E claim;
- no `--companies` feature;
- no scheduler, cron, n8n, fetching, network, LLM, application submission, resume generation or recruiter contact;
- no git add / commit / push / tag.
