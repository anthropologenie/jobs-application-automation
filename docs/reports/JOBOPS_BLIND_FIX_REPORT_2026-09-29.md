# JobOps P3 — Blind-Validation Fix Pass (jobops-policy@0.2.2)

**Run date:** 2026-09-30 (P3 command dated 2026-09-29) · **Scratch copy:** `/tmp/jobops_p3` · **Network:** none

## Executive result

**PASS.**

| | Posting cases (stop-rule denominator = 144) | Sequences (reported separately, denominator = 12) |
|---|---|---|
| P2 initial (0.2.1, P2 adapter) | 35 / 144 mismatched = **24.3 %** | 3 / 12 mismatched |
| **P3 final (0.2.2, corrected adapter)** | **0 / 144 mismatched = 0.0 %** (144 pass) | **0 / 12 mismatched** (12 pass) |

- The ≤ 20 % condition is met, so classification was due. **No mismatches remain, so none were classified.** No xfail was created (`KNOWN_MISMATCHES` stays empty).
- The frozen blind fixture is byte-identical (`44de6af6d8b9bb505044d0b6b871e24cf88a19262bfb90b2b5cf2f6aecdf331a`). Its hash is verified on every run.
- **Every fix is general.** Each one is policy data plus a general parser, and each has its own new golden regression family: 89 new cases plus 6 new 0.2.2 expectations on existing cases. No case ID, exact sentence or test-specific branch appears in production code.
- `jobops-policy@0.2.0` and `@0.2.1` are byte-identical and reproduce all their historical golden expectations. The default is now `jobops-policy@0.2.2`, switched only after every acceptance condition passed with 0.2.1 still the default (§50).
- **Two new owner questions: OI-050 and OI-051.** Neither affects any blind case.

> **This fixture is no longer a holdout (§55).** The 144 cases were read during this fix pass, so 144/144 is evidence that the identified gaps are closed. It is **not** evidence of generalisation. A fresh blind set of at least 40 posting cases, written by a different fresh session, is needed before C1 or live discovery.

---

## 1. Root-cause audit (Phase 1, done before any code change)

I traced every mismatched case through the adapter, the evidence extractor, the fact summary, the rule table and the lane. I did not assume a shared cause per P2 group. The full per-case table as written before the fixes is reproduced in §1.2.

### 1.1 Verification of the P2 groups

| Group | Case IDs | P2 hypothesis | Verified root cause | Verdict on hypothesis |
|---|---|---|---|---|
| **A. Technical hybrid** | B004, B020, B036, B040, B044, B048, B056, B060, B064, B068, B072, B076, B080, B088, B092, B096, B100, B106, B117, B118, B131 (21) | JD bullet "…hybrid BM25 + dense retrieval" read as a hybrid work arrangement | Confirmed. 0.2.1 `lexicon.hybrid` matches any "hybrid" not directly followed by a small list of nouns. "hybrid BM25" is not in that list, so the JD statement gets mode HYBRID. The listing gets REMOTE (or ONSITE). `summarize_geography` sees two modes → CONFLICTING → GEO-R19 UNKNOWN | **Confirmed for all 21.** B088 **also** has a second, independent cause (group F; see below). |
| **B. Office-day wording** (not in the P3 group list; P2 "Pattern B") | B012, B015, B027, B028, B030, B095, B144 (7) | Indian wording not parsed | Confirmed. `office_days` only matched "N days per/a week" and "N days in/at/from office". It missed "2 days WFO", "2 office days per week" and "5 days work from office". The result was `office_days = None` → GEO-R08 UNKNOWN (including the 5-day B015, which should FAIL). B028 also carries the BM25 bullet, but HYBRID + HYBRID is not a conflict; the days are the cause | Confirmed |
| **C. B009** | B009 | Adapter joins location and work mode | Confirmed, with one addition: the engine **had no work-mode input at all** (neither `ObservationInput` nor the `observation` table). The P2 adapter's join was therefore forced. It turned "Berlin, Germany — Remote" into a remote statement *naming* Germany → REGION_EXCLUDES_INDIA → GEO-R03 FAIL | Confirmed (input-contract gap) |
| **D. B054/B055** | B054, B055 | OI-049 not implemented | Confirmed. COMP-C03 flags = [COMPENSATION_REVIEW] only | Confirmed |
| **E. B058** | B058 | Pipe-separated base and CTC parsed as one CTC clause | Confirmed. `_CLAUSE_SPLIT` splits only on `; ( ) [ ]` and newlines, so "Base: ₹25 LPA \| CTC: ₹31 LPA" stays one clause. `basis` tests CTC before base → basis CTC → COMP-C01 → CTC_BASIS_UNVERIFIED → REVIEW | Confirmed |
| **F1. B082** | B082 | "employed directly by" not recognised | Confirmed. `direct_contract` knew only "direct contract/engagement" and "contract directly with" → EMP-R03 FAIL | Confirmed |
| **F2. B085/B086** | B085, B086 (+ B088) | Relationship signals read only from the JD body | Confirmed. `_relationship` ran over JD sentences only. "Employer of Record (Deel)" (B085), "Independent contractor" (B086) and "Hourly contractor" (B088) in the employment field were never seen | Confirmed, and **B088 added** (P2 had listed it under A only) |
| **G. S01** | S01 | Steps 1–2 geography attributed to A | **Refuted.** The S01 JD says "hybrid search", which 0.2.1 *already* excluded. The real causes are: step 1–2 geography = **B** ("Hybrid (2 days WFO)"); step 2 newness = **C** (joined listing string differs from the search-only re-sighting's → "location changed"); step 3 newness = cross-source ruling not implemented (OR-64) | Partly refuted |
| **G. S09** | S09 | Not diagnosed | **A** (BM25 bullet vs Remote) | Diagnosed |
| **G. S10** | S10 | Probably the adapter join | Confirmed **C**: "Remote - India — Remote" vs "Remote - India" | Confirmed |

One more case was **right for the wrong reason** under 0.2.1. B008 (Remote – APAC, expected UNKNOWN) reached UNKNOWN through the spurious GEO-R19 hybrid conflict. Under 0.2.2 it reaches UNKNOWN through the correct rule (GEO-R05, GEO_REGION_AMBIGUOUS).

### 1.2 Per-case table (as recorded before the fixes)

| ID | expected → actual (0.2.1) | parser / adapter path | root cause | group | fix |
|---|---|---|---|---|---|
| B004 | geo FAIL→UNKNOWN; lane EXCLUDED→REVIEW | JD HYBRID + listing REMOTE(US) → CONFLICTING → GEO-R19 | technical hybrid | A | contextual hybrid classifier |
| B020 | geo FAIL→UNKNOWN; lane EXCLUDED→REVIEW | JD HYBRID + listing ONSITE(Pune) → CONFLICTING | technical hybrid | A | same |
| B036 B040 B044 B048 B056 B060 B064 B068 B072 B076 B080 B092 B096 B100 B106 B117 B118 B131 | geo PASS→UNKNOWN (+lane SHORTLIST→REVIEW where asserted) | JD HYBRID vs listing REMOTE → GEO-R19 | technical hybrid | A | same |
| B088 | geo PASS→UNKNOWN; emp FAIL→UNKNOWN; lane EXCLUDED→REVIEW | (1) as A; (2) employment field "Hourly contractor": no employment kind, relationship not read from the field → EMP-R12 + REL-R01 | A **and** F2 | A+F2 | both |
| B012 B027 B028 B095 | geo PASS→UNKNOWN | "2 days WFO" → office_days None → GEO-R08 | office-day wording | B | office_days lexicon |
| B030 | geo PASS→UNKNOWN | "2 office days per week" | office-day wording | B | same |
| B144 | geo PASS→UNKNOWN | "3 days WFO" | office-day wording | B | same |
| B015 | geo FAIL→UNKNOWN | "5 days work from office" | office-day wording | B | same |
| B009 | geo UNKNOWN→FAIL; lane REVIEW→EXCLUDED | joined "Berlin, Germany — Remote" → REMOTE naming DE → GEO-R03 | no work-mode input → forced join | C | `raw_work_mode` input + precedence |
| B054 B055 | missing CTC_BASIS_UNVERIFIED | COMP-C03 | OI-049 | D | COMP-C03 flag (OR-62) |
| B058 | IN_TARGET expected; CTC flag present; lane SHORTLIST→REVIEW | one merged clause, basis CTC | no labelled-clause split | E | labelled split |
| B082 | emp UNKNOWN→FAIL; flag missing | direct=False → EMP-R03 | direct lexicon | F1 | direct lexicon |
| B085 | emp PASS; EOR expected | relationship not read from employment field | field not read | F2 | relationship_fields |
| B086 | emp UNKNOWN; FAIL expected | same | field not read | F2 | same (+ contractor employment kind) |
| S01 | steps 1–2 geo/lane; step 2 newness; step 3 newness | see §1.1 | B + C + OR-64 | B, C, G | office days, `raw_work_mode`, cross-source newness |
| S09 | steps 1–2 lane | JD HYBRID vs REMOTE | technical hybrid | A | classifier |
| S10 | step 2 newness | joined listing strings differ | adapter join | C | `raw_work_mode` |

---

## 2. Fixes (Phase 2–3), all in `jobops-policy@0.2.2`

| Group | Fix (policy data first; general code only) | New golden regression cases | Before → after (blind) |
|---|---|---|---|
| **A. Technical hybrid** | `lexicon.hybrid_semantics`: context lexicons of work-arrangement terms and technical terms, before and after the token. The first cue within the next 3 words decides. A weak technical cue ("model") becomes WORK only when the preceding words or an office-attendance cue show a work arrangement. With no contextual evidence, "hybrid" is WORK in a structured field or a title suffix ("(Hybrid)") and UNCLASSIFIED in the JD body, so no mode is inferred (§11). Implemented in `evaluation/extract.py::hybrid_usage` | 33 (9 technical positives, 8 technical negatives, 12 work-arrangement positives, 4 genuine conflicts) | 21 cases + S09 → 0 |
| **A′. Source precedence** | `lexicon.work_mode_sources`: work-mode field > location > title > JD. The highest-ranked source that states a mode decides. A lower-ranked source stating a different mode → new mode `CONFLICTING_SOURCES` → **GEO-R25 UNKNOWN + WORK_MODE_CONFLICT** (review-routing, §10). It is never a silent override. Implemented in `evaluation/dimensions.py::_resolve_mode` | (within the 33) | — |
| **B. Office days** | `lexicon.office_days` gains "N office/onsite/WFO days", "N days WFO / work from office / onsite / in-person / at the office" and "hybrid – N days" | 12 work-arrangement cases include WFO, "office days", "onsite", "hybrid 3/4 days" | 7 cases + S01 steps 1–2 → 0 |
| **C. B009 / structured geography** | New `ObservationInput.raw_work_mode` field. Migration **0102** adds a nullable `observation.raw_work_mode` column. `repository.insert_observation` stores it, and 0.2.2 reads it as the rank-1 source. The blind adapter now passes `location_text` and `work_mode_text` separately (the fixture is untouched) | 9 structured-geography cases (Berlin/London + Remote → UNKNOWN; US/EMEA → FAIL; APAC → UNKNOWN; Pune + Remote → CITY_HUB_LISTED; the "country where this job is posted" work-authorization rule, foreign vs India listing) | B009 + S01/S10 newness → 0 |
| **D. OI-049** | COMP-C03 flags += CTC_BASIS_UNVERIFIED (OR-62) | 7 CTC-lane cases | 2 → 0 |
| **CTC lane** | CTC_BASIS_UNVERIFIED moved from `review_routing` to `informational` (OR-63) | (same 7) + explicit parametrised lane test | B052 (UNDETERMINED lane) now SHORTLIST |
| **E. Base + CTC** | `lexicon.compensation.labelled_clause_split` splits before a basis label (base/fixed/CTC/…) after `\| / ; ,`, "and" or "with". A comma inside `24,00,000` is never split, because the lookahead requires a label | 12 base-vs-CTC cases, including base < floor with CTC > floor → FAIL (base wins) | 1 → 0 |
| **F1. Direct fixed-term** | `direct_contract` gains "employed/hired/engaged directly by/with", "directly employed by", "direct employment with", "on our own payroll", "no agency". `CONTRACT` gains "fixed-term" | 12 direct-contract cases (6 long-term direct → UNKNOWN; short-term, not-direct and contract-to-hire → FAIL; direct permanent → PASS; unstated duration → UNKNOWN, see OI-051) | 1 → 0 |
| **F2. EOR / contractor field** | `lexicon.relationship_fields` makes relationship signals read from the employment field as well as the JD. New employment kind `INDEPENDENT_CONTRACTOR` → **EMP-R13 FAIL** ("Independent contractor", "Hourly contractor", "B2B", "Contractor" as the whole field, "engaged as a contractor"). The relationship lexicon gains the whole-field forms, "Employer-of-Record" and "via an EOR" | 12 cases, including negatives ("work with external contractors", "B2B analytics software") | 3 (B085, B086, B088) → 0 |
| **G. Cross-source newness** | `newness.cross_source_update` (OR-64). A sighting from a *strictly higher-authority* source that changes the *accepted* value of title, arrangement, compensation or employment type → UPDATED. Otherwise → SEEN_BEFORE (SOURCE_CONFLICT still flagged). The JD hash and raw listing strings are not compared across sources. Not applied within the run that first saw the requisition (OI-050) | 4 multi-observation cases, plus existing G164 now UPDATED under 0.2.2 | S01 step 3 → 0 |
| **Carry counting** | No code change: `carry_days > 3` already parks on D+3 (OR-65) | `tests/test_p3_policy_022.py::test_carry_counting_first_overflow_day_is_carry_day_one` (D=1, D+1=2, D+2=3, D+3 PARKED; STRONG exempt) | S07 day-4 (UNDETERMINED) = parked on 2026-10-02 = D+3 |

**Mutation check (do the new cases actually catch each gap?).** I removed each 0.2.2 fix in memory, one at a time, and re-ran the 89 new cases:

| Fix removed | New cases failing |
|---|---|
| hybrid_semantics | 5 |
| work_mode_sources | 78 (the whole structured-field input disappears) |
| office_days | 5 |
| CTC lane rule | 3 |
| OI-049 flag | 2 |
| labelled split | 8 |
| direct lexicon | 7 |
| relationship_fields | 9 |
| cross-source newness | 2 |

With nothing removed, 0 fail. Every fix is covered by at least two cases.

### Technical "hybrid": impact (observed test behaviour only)

- **Why it was misread.** 0.2.1 decided "hybrid" with a single regex, `\bhybrid\b(?![- ](search|retrieval|cloud|models?|architecture|rag|ranking|index|infrastructure|systems?))`. That is a blacklist of the *next word* only. "hybrid BM25 + dense retrieval", "hybrid (BM25 + dense)" and "hybrid: BM25 first" all slipped through.
- **How it affected geography.** Each JD sentence with a work-mode word is its own geography statement. The misread sentence became a HYBRID statement. Next to the listing's REMOTE (or ONSITE) statement, that made the posting CONFLICTING → **GEO-R19 UNKNOWN + WORK_ARRANGEMENT_AMBIGUOUS**. It never produced FAIL.
- **How it changed lanes (blind fixture, 0.2.1).** 26 of the 144 JDs contain "hybrid BM25 + dense retrieval", and 22 of those hit GEO-R19. Under 0.2.2:
  - **9** move REVIEW → **SHORTLIST**: clean STRONG candidates that 0.2.1 sent to the capped review queue.
  - **3** move REVIEW → **EXCLUDED**: B004 (US-only), B020 (Pune office) and B088 (hourly contractor). The spurious UNKNOWN had been masking a real FAIL.
  - 8 stay REVIEW for other reasons.
  - 2 stay EXCLUDED.
  - 1 (B008) keeps its correct UNKNOWN, now for the right reason.

  The 38 JDs that say "hybrid search and re-ranking" were already handled by the 0.2.1 blacklist.
- **Effect on RAG/retrieval-heavy roles.** "Hybrid" in a technical sense appears mostly in retrieval, RAG and search JDs, which are core target roles. In this fixture, every affected posting was a STRONG-relevance retrieval JD. The effect was to push them into REVIEW (capacity 10/day, overflow → PARKED for non-STRONG), and in 3 cases to hide a disqualifier. The bug never excluded a posting by itself. I have not measured how often this occurs in live traffic (no live data was used).
- **Why the new parser distinguishes the two uses.** It classifies each "hybrid" token by what it describes: its neighbouring words, then any office-attendance cue in the sentence, then which field it sits in. It does not rely on a longer blacklist. Technical context and work context are both explicit lexicons in policy data. Tokens with neither are left unclassified instead of guessed. A structured work-mode field always outranks the JD, so technical prose cannot contradict it, while a *genuine* JD work statement still raises WORK_MODE_CONFLICT.

---

## 3. Remaining mismatches

**None.** Posting cases: 0 / 144. Sequences: 0 / 12.

## 4. Classification counts

| Class | Count |
|---|---|
| ENGINE_BUG | 0 |
| CASE_ERROR | 0 |
| SPEC_AMBIGUITY | 0 |
| ADAPTER_LIMIT | 0 |

No CASE_ERROR is claimed, so there are no self-granted exemptions.

The three UNDETERMINED fixture values are still not asserted, because the fixture is frozen. The owner's Addendum C rulings now decide them, and the engine matches each ruling:

| Item | Ruling | 0.2.2 result |
|---|---|---|
| B052 lane (CTC ₹24 LPA) | OR-63 | **SHORTLIST** |
| S05 step 2 newness | OR-64 | **UPDATED** + SOURCE_CONFLICT → REVIEW |
| S07 day-4 parked_ids | OR-65 | MODERATE item **parked on 2026-10-02 (= D+3)**; STRONG item keeps carrying |

## 5. Owner questions (new OI numbers)

| ID | Exact question | Behaviour meanwhile |
|---|---|---|
| **OI-050** | YES/NO — When a board sighting and a contradicting ATS/company-site sighting of the same requisition are both first observed in the SAME run, should newness be UPDATED (rather than NEW)? | NEW (unchanged, G111). SOURCE_CONFLICT and REVIEW either way. |
| **OI-051** | YES/NO — Should a direct-company contract whose duration is NOT stated (e.g. "Fixed-term contract, employed directly by X") be UNKNOWN (rather than FAIL)? | **UNKNOWN + CONTRACT_DURATION_UNSTATED** (EMP-R14, `owner_confirmed: false`), because uncertainty must not become FAIL. 0.2.0 and 0.2.1 keep FAIL. |

Neither item occurs in the blind fixture. Both were found while writing the generality cases.

OI-049 is marked resolved (OR-62) in `docs/architecture/JOBOPS_V2_OPEN_ITEMS.md` §P3 (append-only).

## 6. Owner rulings recorded

`OWNER_RULINGS_LOG.md` **Addendum C** is appended; the earlier content is byte-identical (prefix verified with `cmp`):

- **OR-62** — OI-049: a CTC range spanning the target carries CTC_BASIS_UNVERIFIED.
- **OR-63** — CTC_BASIS_UNVERIFIED alone does not route to REVIEW.
- **OR-64** — cross-source newness.
- **OR-65** — REVIEW carry counting (D → D+1, D+2 eligible → PARKED on D+3).

## 7. Changes to existing tests and fixtures (each justified)

| File | Change | Justification |
|---|---|---|
| `tests/test_policy_v02_blind.py` | Adapter passes `raw_location` and `raw_work_mode` separately. Runs pinned to `jobops-policy@0.2.2` (`TARGET`). Integrity test renamed to `test_target_policy_is_022` | §15 (adapter must not join the two fields). §45 (re-run on 0.2.2). The fixture, its hash check and the no-expectations-in-Python rule are unchanged |
| `tests/test_policy_v02_golden.py` | Supports three versions. Optional `policy_versions` for cases that exercise 0.2.2-only behaviour. Multi-observation cases can use `expected_by_version`. The shape check requires "not all versions identical" instead of `[0] != [1]` | Needed to run 0.2.0, 0.2.1 and 0.2.2 side by side (§44) |
| `tests/fixtures/policy_v02_golden_cases.json` | 89 new cases (G188–G276, 0.2.2 only). A 0.2.2 expectation was added to 15 existing cases. **No existing input and no 0.2.0/0.2.1 expectation changed (verified: 0 differences).** Six shared cases were split into per-version expectations: G048, G133 → SHORTLIST (OR-63); G132 + CTC_BASIS_UNVERIFIED (OR-62); G164 step 2 UPDATED (OR-64); G068, G071 employment_type FAIL via EMP-R13 (§24/§26, with overall verdict and lane unchanged). The other 9 per-version cases received a 0.2.2 entry equal to their 0.2.1 entry | §39. Each changed expectation names its ruling in `p3_version_note` |
| `tests/test_v02_store_migrations.py` | Expected migration list now includes `0102_observation_work_mode.sql` and `user_version` 102 | New forward-only migration |
| `tests/test_v02_guardrails.py` | Default policy assertion 0.2.1 → 0.2.2. Also asserts 0.2.1 stays loadable | §50 default switch |
| `tests/test_p3_policy_022.py` (new, 27 tests) | Older-artifact hashes; 0.2.2 flag registration; the OR-63 lane matrix (₹24L CTC → SHORTLIST, ₹18L CTC → REVIEW, ₹18–25L CTC → REVIEW, …); OR-65 carry sequence; the §11 hybrid boundary phrases; 0.2.0/0.2.1 ignore `raw_work_mode` (identical evidence hash) | §19, §38, §44 |

## 8. Fixture integrity

| Check | Result |
|---|---|
| Blind fixture SHA-256 | `44de6af6d8b9bb505044d0b6b871e24cf88a19262bfb90b2b5cf2f6aecdf331a` |
| `.sha256` file SHA-256 (before = after) | `05152e0a750f8cd73afc7ba3135e5af525367b1ee0402f875fc39ed281993137` |
| Hash verified | **YES** (every run: `test_frozen_fixture_hash`) |
| Fixture changed | **NO** |

## 9. Version hashes

| Artifact | SHA-256 |
|---|---|
| 0.2.0 before | `65f74aec883d475989ea0594fac070f547c96a697bc1f7f4b46cf8e0d5dd567a` |
| 0.2.0 after | `65f74aec883d475989ea0594fac070f547c96a697bc1f7f4b46cf8e0d5dd567a` ✔ |
| 0.2.1 before | `af19a3fd998e945cba19ce68f0e36f2eba4156e8bfd5255ac4ea7dacf7f5ea7d` |
| 0.2.1 after | `af19a3fd998e945cba19ce68f0e36f2eba4156e8bfd5255ac4ea7dacf7f5ea7d` ✔ |
| 0.2.2 first draft | `69adc706c6e6f83a8ae5b2442543e9a6ab60b71dfde2de3c8364b28a9b01f820` |
| 0.2.2 intermediate (OI-050 gate added) | `be9a996e2969c6be7067c68a5d3a6e42388903bbbe2db09a5b3489eff0db8e6c` |
| **0.2.2 final** | **`3743bbaebce2b5f3143ec0a211d6c63aa35b8113dce03b1622876ef43eeed734`** (EMP-R14 added). This hash is stable: regenerating from 0.2.1 gives identical bytes, and every suite in §10 ran on it |

## 10. Tests (all from `/tmp/jobops_p3`; default = 0.2.2)

| Suite | Total | Passed | Failed | xfailed | Skipped |
|---|---|---|---|---|---|
| 363 original tests (P0: gate, LinkedIn ingestion, identity, review queue, time) | 363 | 363 | 0 | 0 | 0 |
| Golden @ 0.2.0 | 184 | 184 | 0 | 0 | 0 |
| Golden @ 0.2.1 | 184 | 184 | 0 | 0 | 0 |
| Golden @ 0.2.2 (184 existing + 89 new) | 273 | 273 | 0 | 0 | 0 |
| Golden fixture shape | 1 | 1 | 0 | 0 | 0 |
| Blind posting cases (0.2.2) | 144 | 144 | 0 | 0 | 0 |
| Blind sequences (0.2.2) | 12 | 12 | 0 | 0 | 0 |
| Blind integrity (hash, target version) | 2 | 2 | 0 | 0 | 0 |
| P1a 0.2.1 acceptance (version replay) | 50 | 50 | 0 | 0 | 0 |
| P3 0.2.2 acceptance (new) | 27 | 27 | 0 | 0 | 0 |
| Other v0.2 modules (F4 replay 7, guardrails, identity/newness, lanes/queue, engine, relevance, migrations, tool) | 107 | 107 | 0 | 0 | 0 |
| **Full suite** | **1347** | **1347** | **0** | **0** | **0** |

- The full suite also passed (1347/1347) **before** the default switch, with 0.2.1 as the default.
- **F4** (a search-only re-sighting never replaces a JD-supported verdict) still holds: `test_v02_f4_replay` passes 7/7 on 0.2.2, and blind S01/S10 pass.
- **DB note.** The P0 modules need the legacy database, as P2 found. A byte copy (`cp`) of `data/jobs-tracker.db` was placed in the scratch tree only; the WAL file was 0 bytes. The live file's mtime is `1788161814` both before and after. The blind and golden suites use in-memory databases.

## 11. Git status

```
 M .gitignore
 M api-server.py
D  data/jobs-tracker.db
 M docs/INDEX.md
?? JOBOPS_SCALING_CAPABILITY_INVENTORY.md
?? JOBOPS_SCALING_EXECUTION_PLAN.md
?? OWNER_RULINGS_LOG.md
?? P0_EXIT_REVIEW.md
?? P0_IMPLEMENTATION_SPEC.md
?? _quarantine/
?? company/
?? data/ingestion/
?? digest/
?? docs/P0_10_TIME_INSTRUMENTATION.md
?? docs/architecture/
?? docs/reports/JOBOPS_ACTIVATION_AUDIT_2026-09-29.md
?? docs/reports/JOBOPS_BLIND_VALIDATION_REPORT_2026-09-29.md
?? docs/reports/JOBOPS_LEGACY_PATH_TRACE_2026-09-29.md
?? docs/reports/JOBOPS_PHASE_B_FOLLOWUP_REPORT_2026-09-29.md
?? docs/reports/JOBOPS_PHASE_B_IMPLEMENTATION_REPORT_2026-09-29.md
?? evaluation/
?? geo/
?? identity/
?? ingestion/
?? ops/
?? policy/
?? relevance/
?? review/
?? sources/
?? store/
?? tests/conftest.py
?? tests/fixtures/
?? tests/test_p0_02_gate.py … tests/test_v02_store_migrations.py (unchanged list)
?? tests/test_p3_policy_022.py   (new)
?? tests/v02_support.py
?? timing/
?? tools/
```

(This report file is also new and untracked.)

- **Index unchanged except the existing approved DB deletion.** `git diff --cached --name-status` = `D data/jobs-tracker.db` only.
- **No commits.** HEAD is still `bf22ca1`.

**Files changed by P3.**
- Modified: `evaluation/extract.py`, `evaluation/dimensions.py`, `evaluation/compensation.py`, `evaluation/newness.py`, `evaluation/service.py`, `evaluation/policy_loader.py` (registers 0.2.2 and sets the default), `sources/base.py` (+`raw_work_mode`), `store/repository.py` (stores it).
- Tests: `tests/test_policy_v02_blind.py`, `tests/test_policy_v02_golden.py`, `tests/test_v02_store_migrations.py`, `tests/test_v02_guardrails.py`, `tests/fixtures/policy_v02_golden_cases.json`.
- Appended: `OWNER_RULINGS_LOG.md`, `docs/architecture/JOBOPS_V2_OPEN_ITEMS.md`.
- New: `policy/jobops-policy-0.2.2.json`, `store/migrations/0102_observation_work_mode.sql`, `tests/test_p3_policy_022.py`, this report.

**Operational note.** Migration 0102 is additive (a nullable column) and forward-only. It was applied only to in-memory and scratch databases. Any runtime v2 database needs `store.migrate` run by the owner before observations carrying `raw_work_mode` can be stored. No production adapter produces that field yet.

## 12. Safety check

| Check | Result |
|---|---|
| network used | NO (tests refuse sockets; no HTTP, DNS, LinkedIn, ATS or Apify) |
| live DB opened | NO (byte copy via `cp` for the P0 suite only; mtime unchanged) |
| data/n8n opened | NO (excluded from the scratch copy) |
| .env opened | NO (excluded from the scratch copy) |
| secrets accessed | NO |
| blind fixture modified | NO |
| blind hash unchanged | YES |
| 0.2.0 modified | NO |
| 0.2.1 modified | NO |
| new dependencies | NO |
| Git index changed | NO |
| commits created | NO |
| production ingestion modified | NO (`ingestion/`, `LinkedInIngestionPipeline`, `HardEligibilityGate`, `CandidateStore`, `review.ledger`, `timing`, API endpoints untouched) |
| LinkedIn pipeline rewired | NO |
| ATS adapters created | NO (`sources/` still holds only `base.py` and `__init__.py`; the guardrail test passes) |
| scheduler created | NO |
| Phase C started | NO |

## 13. What should happen next

1. The owner answers **OI-050** and **OI-051** (yes/no).
2. **Fresh independent blind round (§55).** A different fresh session with no implementation knowledge writes at least 40 new posting cases from the rulings, *including Addendum C*. Run it against 0.2.2 before trusting the engine on live discovery or starting C1. This fixture (144/12) is exposed and must not be reused as the holdout.
3. The fresh round should deliberately probe the new heuristics: the "hybrid" context window (phrases outside both lexicons fall to UNCLASSIFIED/TECHNICAL), the labelled base/CTC split, the direct-contract lexicon and the contractor whole-field forms. These are the parts most likely to meet phrasing that this pass did not anticipate.
