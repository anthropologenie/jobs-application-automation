# JobOps P5 — Round-2 Root-Cause Fix, 0.2.3, and Acceptance

**Date:** 2026-09-30 · **Branch:** `jobops-v2-engine` · **HEAD (unchanged, nothing committed):** `313ec4ca7b44c329ff9cc457f4259569a10e9b72`

---

## Executive Summary

`jobops-policy@0.2.3` implements Owner Addendum E (E1–E8). It also repairs the extraction defects behind the Round-2 false exclusions, the language mismatches and the office-day and work-mode errors.

On the frozen Round-2 corpus (SHA-256 `f54eb41b…ee421e5`, unchanged):

| | 0.2.2 (P4b baseline) | 0.2.3 |
|---|---|---|
| Posting mismatches | 106 / 124 = **85.48 %** | 57 / 124 = **45.97 %** |
| Posting mismatches, resolution-adjusted | 110 / 124 = 88.71 % | 59 / 124 = 47.58 % |
| Sequence mismatches | 6 / 10 = 60 % | 1 / 10 = 10 % |
| False EXCLUDED | 5 | 1 (explained) |
| False SHORTLIST | 1 | 0 |

54 of the 57 remaining posting mismatches differ **only in the relevance label**. In every one the corpus expects STRONG (or MODERATE) and the engine applies the unchanged owner threshold: STRONG needs at least 3 distinct AI-specific terms across at least 2 capability clusters. Most of these JDs are 8–35 words long.

The acceptance threshold is ≤ 20 %, and **45.97 % exceeds it. The §17 stop rule applies.** 0.2.3 is registered but **EXPERIMENTAL**, 0.2.2 stays the default, and no C1 work was started.

---

## Baseline (0.2.2, confirmed before any code change)

- **Round-2 replay:** reproduced from the persisted harness at 106 / 124 postings and 6 / 10 sequences. That's the P4b projection, and the P5 projection gives the same result on 0.2.2.
- **Raw mismatch fields:** relevance 99, lane 67, language 59, geography 17, compensation 8–9, flags 8–10, employment 3–5, employer 1.
- **Full suite:** **1347 passed** (scratch copy; P0 tests use a byte copy of the DB).
- **0.2.2 hash:** `3743bbae…eed734`.
- **Round-1 fixture:** `44de6af6…f331a`.

---

## Task 0 — Round-2 harness made durable

| File | Purpose |
|---|---|
| `tests/fixtures/policy_v02_blind_round2_cases.json` (+ `.sha256`, `_undetermined.md`) | byte-identical copy of the frozen corpus |
| `tests/fixtures/policy_v02_blind_round2_owner_resolutions.json` | the five P4b owner resolutions (overlay, separate from the fixture) |
| `tests/fixtures/policy_v02_blind_round2_p4b_raw_022.json` | the frozen P4b raw measurement (`e11c9f76…80b5`) |
| `tests/r2_blind_harness.py` | version-parameterised adapter; expectations read only from the fixture |
| `tests/r2_replay.py` | `python3 tests/r2_replay.py <version> [--projection p4b\|p5] [--out file]` |

Harness corrections, all documented in the module docstring:

1. **Projection `p5`:** employer_type and employment_type are kept separate. REL-R08 (a staffing classification seen through the relationship table) now counts toward employer_type. Projection `p4b` reproduces the P4b number.
2. **FX-unscorable fields:** the fixture carries `fx_snapshot_age_days` but no rate. The compensation and FX flags of those 15 cases are not scored (the lane too, when the actual lane is REVIEW). They are reported, never guessed.
3. **`third_party_payroll` hint:** now expressible as the `THIRD_PARTY_PAYROLL` classification (migration 0103).
4. **R2-SEQ-07 identity:** queue items carry an identity key, so the fixture's "earlier identical sighting" is the same requisition. In P4b it had become a separate one.

---

## Root-cause analysis (P5 Task 1)

| Class | Stage | Root cause (0.2.2) |
|---|---|---|
| Language (59) | extraction | A stop-word-ratio heuristic returned `und` for short, bulleted or jargon-heavy English. Texts under 20 words got no detection at all. |
| Relevance (99) | extraction / vocabulary | The lexicon lacked evaluation, reliability and quality vocabulary (evals, golden sets, SLOs, judge calibration, red-teaming, prompt regression …). |
| Geography / office days (17) | extraction / normalisation | JD sentences with a day count but no mode word ("office on Tuesdays and Thursdays", "two days per week at HQ") were discarded. Weekday lists, ranges, "twice a week", monthly counts, alternate days and WFH-day wording were not parsed. "Friday is our WFH day" was read as a REMOTE statement. Negated "not a hybrid role" was read as HYBRID. |
| Work-mode conflicts | extraction | "Remote, India" plus "five days a week at our Chennai centre" produced no mode for the JD sentence, so it gave PASS / SHORTLIST (R2-025). |
| Employment (false EXCLUDED ×3 + SEQ-04) | extraction | The single word `contract` anywhere in the JD gave CONTRACT → EMP-R03 FAIL ("contract testing", "contract-review assistant"). Direct-employment evidence only counted inside the same sentence as the contract cue. The sentence splitter is compiled case-insensitive, so it also splits after ";" before lowercase words. |
| Employer type | schema / policy | The schema had no THIRD_PARTY_PAYROLL classification, and placement / third-party payroll failed only the relationship dimension. |
| Compensation (false EXCLUDED R2-066 …) | extraction | "US: $160k \| India: ₹42–55 LPA" was parsed as one INR clause. "₹27L fixed + up to 15% bonus" read 15 as a range bound. "25 lakh users" was read as salary. Table dot-leaders split the "Fixed base" label from its figure. "21 L" was not recognised as INR. SGD / CAD / AUD / AED were unknown currencies. |
| Lane (67) | projection | Almost entirely downstream of relevance (WEAK → PARKED) and language (UNKNOWN → REVIEW). |
| Sequences (SEQ-01/05/08/09) | evaluation | A sighting *missing* a detail was treated as contradicting or updating one that stated it (office days None vs 2 → SOURCE_CONFLICT / UPDATED). Office-day phrasing also affected these sequences. |

---

## Changes (0.2.2 → 0.2.3)

All engine code changes are **gated on keys that exist only in the 0.2.3 artifact**. 0.2.0, 0.2.1 and 0.2.2 replay byte-for-byte: their golden, Round-1 and P4b replays are unchanged.

### Evidence precision (E1, OR-66)
- `lexicon.employment_jd`: JD-body FAIL kinds require explicit multi-word statements such as "12-month contract", "contract role" or "temporary position". PASS kinds keep single-word vocabulary. A labelled JD line ("Employment type: Contract") uses the structured vocabulary.
- Expanded `employment_cue_exclusions`: contract testing / review / management / lifecycle, API / OpenAPI / data / vendor / smart contracts, contractual SLAs.
- Direct-employment evidence is posting-level (CONTEXT evidence rows).
- **EMP-R15:** a structured PERMANENT contradicted by an explicit JD FAIL-kind gives UNKNOWN + `EMPLOYMENT_SOURCE_CONFLICT` (new review flag).
- Negated "hybrid" is classified `NEGATED` and never becomes a work mode.
- `evaluation/extract.py::_employment_by_field`, `dimensions.summarize_employment`.

### Language (E4, OR-69)
- `extract._detect_language`: a deterministic function-word detector (English vs de / fr / es / pt / it / nl), plus lowercase Latin-diacritic words and non-Latin script measured in characters.
- URLs, e-mails and domains are stripped first, and a single stray foreign token is ignored.
- English share ≥ .95 gives PASS; a foreign share ≥ .5 gives NON_ENGLISH (FAIL when ≥ .95, else UNKNOWN); mixed text gives UNKNOWN.
- The evidence (counts, share, example tokens, confidence) is stored.
- Required-language patterns accept a parenthetical level ("Japanese (JLPT N2 or above) is mandatory").

### Relevance (E7 / E8, OR-72 / OR-73)
- About 30 evaluation / reliability / quality / retrieval terms were added.
- Terms marked `context: ai` count only with an AI anchor elsewhere in the same sentence, never the term itself.
- Overlapping matches within one cluster count once.
- **Thresholds are unchanged.**
- **LANE-R10 plus the `RELEVANCE_TITLE_PRIOR` review flag:** Tier 1 title + WEAK + at least one AI-specific term → REVIEW. A rich Tier 1 JD with no AI term stays WEAK → PARKED.
- Two candidate terms (`summari[sz]*`, bare `prompts?`) were **removed** after they promoted golden G095 from its owner-approved MODERATE to STRONG by double-counting one LLM mention.

### Geography / work mode (E6, OR-71)
- New `evaluation/officedays.py`, driven by `lexicon.office_day_normalization`:
  - weekly counts and frequency words;
  - monthly counts ÷ `monthly_weeks` (4.33);
  - weekday lists and ranges, each weekday assigned to its nearest office or WFH cue, plus extra floating days;
  - WFH-day counts and WFH weekdays (5 − n);
  - alternate days = 2.5;
  - every weekday = 5.
- A normalised count with an attendance cue states the work mode (HYBRID if under 5 days, otherwise ONSITE). A WFH-derived count is never read as REMOTE.
- The method and verbatim span are stored in the evidence (`office_days_method`, `office_days_span`).
- India-eligibility statements are listing evidence (`lexicon.eligibility_line`).
- Sentence boundaries ignore dot leaders and split only before capitals.

### Employment / employer (E5, OR-70)
- **EMPR-R08:** the `THIRD_PARTY_PAYROLL` classification gives employer_type FAIL.
- **EMPR-R09:** placement / third-party-payroll relationship evidence gives employer_type FAIL, in addition to the existing relationship FAIL.
- Registry signal order puts THIRD_PARTY_PAYROLL first.

### Compensation (E2, OR-67)
- `component_split` on "+", "|" and "plus".
- `non_money_number_suffix`: percentages and counts are never amounts.
- `weak_currency_markers`: a lakh / "L" alone needs a compensation keyword.
- `variable_component`: a variable / bonus / incentive figure becomes `VARIABLE_FIGURE`, never selected and never added. An "inclusive of …" tail doesn't make a salary variable.
- `period_inheritance` inside a compensation table, same currency only.
- SGD / CAD / AUD / AED / CHF / JPY recognised. The FX policy is unchanged and no rates were invented.

### Experience (E3, OR-68)
- Behaviour unchanged: STRETCH → EXPERIENCE_STRETCH (review-routing) → REVIEW.
- The experience rules now reference the `$relevant_ai_experience_years` parameter (3). A test proves that changing the parameter changes the label.

### Newness / conflicts (F4 + owner resolution of R2-SEQ-09)
- `newness.differs(absent_tolerant)`: under 0.2.3, a detail absent on one side is neither UPDATED (`newness.absent_detail_is_enrichment`) nor SOURCE_CONFLICT (`source_authority.absent_detail_is_not_conflict`). Two stated, different values still are (tested).

### Schema
- `store/migrations/0103_third_party_payroll_classification.sql` rebuilds the append-only `company_classification` table with the new CHECK value. Every row is copied verbatim and the append-only triggers are recreated.
- It was applied only in in-memory and scratch databases. The live DB hash is unchanged (`bf17ebb1…3285`).

---

## Test coverage

Full suite (scratch copy): **1748 passed, 0 failed, 0 xfailed, 0 xpassed, 0 skipped, 0 errors**. The baseline was 1347.

| Group | Tests |
|---|---|
| Original P0 (p0_02 / 06 / 07 / 08 / 10) | 363 |
| 0.2.0 golden | 184 |
| 0.2.1 golden (+ `test_p1a_policy_021` 50) | 184 + 50 |
| 0.2.2 golden (+ `test_p3_policy_022` 27) | 273 + 27 |
| **0.2.3 golden** (the historical golden set under 0.2.3) | **272** (all but G072) |
| **0.2.3 new golden** (`policy_v023_golden_cases.json`) | **97** |
| **Mutation pairs** | **15** |
| P5 sequence / parameter / integrity / Round-2 ratchet tests | 17 |
| Round-1 blind (0.2.2, pinned) | 158 |
| v0.2 unit and support modules | 107 |
| Golden fixture shape | 1 |

The new golden cases break down as:

- Evidence precision: 24 (E1 20 + E5 4), 12 of them adversarial.
- Language: 17.
- Relevance: 17 (7 adversarial negatives).
- Office day / work mode: 25.
- Compensation: 10.
- Experience: 3.
- G072 under 0.2.3: 1.

Every expectation was written from the rulings. Where a first draft disagreed with the engine, the rulings decided which side changed:

- **OD08:** the rulings made my draft expectation wrong. Structured "Hybrid" plus "every weekday in office" is a genuine contradiction, so it is UNKNOWN + WORK_MODE_CONFLICT. That became OD25, and OD08 now tests the 5-day count with no structured field.
- **LA09:** the rulings showed an engine defect. Japanese has no spaces, so the whole sentence was one "word" and fell under the minimum-evidence rule. Non-Latin script is now measured in characters.

**Round-1 replay:** 0.2.2 gives 144/144 cases and 12/12 sequences; 0.2.3 also gives 144/144 and 12/12 (measured with the Round-1 harness, target swapped).

### Historical-test conflicts (documented, not silently rewritten)

- **`tests/fixtures/policy_v02_golden_cases.json`:** 0.2.3 was added to `policy_versions_under_test`. The per-version and 0.2.2-pinned cases gained a 0.2.3 entry equal to their 0.2.2 expectation, verified by execution.
  - **G072** is restricted to 0.2.0–0.2.2, because OR-70 makes its employer FAIL under 0.2.3. The new test `test_g072_placement_is_employer_fail_under_023` covers that.
  - A programmatic check confirms that **no existing expectation of any of the 273 cases changed**. Only `policy_versions` entries and `p5_note` were added.
- **`tests/test_v02_store_migrations.py`:** the pinned migration list gained `0103`, exactly as P3 did for `0102`. Migration 0103 is explicitly authorised by P5 §10.

---

## Round-2 before / after

Projection p5, fixture frozen, 124 postings.

| Field mismatches | 0.2.2 | 0.2.3 |
|---|---|---|
| relevance | 99 | 56 |
| language | 59 | **0** |
| geography | 17 | 2 |
| work mode (WORK_MODE_CONFLICT flag mismatches) | 3 | **0** |
| compensation | 8 | **0** |
| employment_type | 3 | **0** |
| employer_type | 1 | **0** |
| flags (must have / must not have) | 8 | **0** |
| lane | 67 | 6 |

The table counts field mismatches, so one case can appear in several rows.

| Category (a case can be in several) | 0.2.2 | 0.2.3 |
|---|---|---|
| false EXCLUDED | 5 | 1 |
| false SHORTLIST | 1 | 0 |
| incorrect REVIEW | 13 | 5 |
| incorrect PARKED | 48 | 0 |
| pure relevance mismatch (only the relevance label differs) | 30 | 54 |
| pure language mismatch | 3 | 0 |
| pure lane-projection mismatch | 0 | 1 |
| adapter / schema limitation (FX-unscorable fields) | 9 cases | 15 cases |
| fixture / case-definition issue | see below | see below |

**Sequences:** 0.2.2 had 6 / 10 mismatching (SEQ-01, 04, 05, 07, 08, 09); 0.2.3 has 1 / 10 (SEQ-07).

---

## Remaining mismatches (> 20 %: root-cause categories, then STOP)

The 57 remaining posting mismatches fall into these categories:

| Category | Cases | Belongs to |
|---|---|---|
| **A. STRONG expected; the engine applies the unchanged threshold (≥ 3 terms, ≥ 2 clusters) and gets MODERATE or WEAK.** Median JD length 19 words, e.g. R2-077 "Build LLM-based underwriting assistants and evals." R2-017 and R2-059 have 3–4 evaluation terms but all in one cluster. | 53: R2-006, 012, 016, 017, 024, 028, 029, 032, 034, 036, 040, 041, 042, 043, 045, 047, 052, 056, 057, 058, 059, 060, 062, 063, 064, 065, 066, 070, 074, 077, 078, 079, 084, 085, 086, 087, 088, 089, 090, 091, 092, 093, 095, 096, 111, 113, 117, 118, 119, 120, 121, 123, 124 | **fixture definition vs policy.** The Round-2 rulings sheet never defines STRONG. The author labelled one-line AI JDs STRONG; the owner's STRONG definition (OR-12/13) is quantitative and was not to be changed. In 3 of these (R2-029, 034, 123) the lane also differs: E7 sends Tier 1 + WEAK + AI term to REVIEW, where the corpus expects SHORTLIST. |
| **B. MODERATE expected, STRONG found (over-promotion).** R2-101 "Occasional evaluation of LLM rerankers" now counts evaluation + LLM + reranker. With EXPERIENCE_STRETCH (5–8 years) the lane is REVIEW, not PARKED. | 1: R2-101 | **extraction (vocabulary).** A genuine residual risk of the contextual `evaluat*` term. |
| **C. Fixture conflicts with an owner ruling** | R2-099: 9+ years + STRONG → EXPERIENCE_STRETCH → REVIEW (OR-68 / E3); corpus expects SHORTLIST. R2-023: "Remote — Canada" → GEO-R03 FAIL (OR-50: a named region excluding India fails); corpus expects UNKNOWN. R2-081: location "Remote" with no India listing → UNKNOWN (Round-2 rulings §3 and OR-38); corpus expects PASS. | **fixture / policy** |
| **D. Queue ordering semantics** (sequence R2-SEQ-07) | The engine's "evidence completeness" is the number of UNKNOWN dimensions, so a known consultancy employer (UNKNOWN) ranks like an undisclosed salary. The corpus treats only *missing* evidence as incomplete. The cap, carry, D+3 parking and STRONG exemption all match. | **policy (unspecified).** Not covered by Addendum E, so not changed. |
| **E. Adapter limitation** | 15 cases carry `fx_snapshot_age_days` but no rate; their compensation / FX flags are not scored. | **adapter / fixture** |

The resolution overlay adds R2-051 and R2-075 to the list, for the relevance label only (A). Their BELOW_TARGET / COMPENSATION_REVIEW / EOR routing matches the owner resolutions.

**Why the fixes were insufficient for the gate.** Every *eligibility* dimension now matches the corpus, except R2-023 and R2-081 (category C). Language, compensation, employment, employer and flags are all 0 mismatches. What keeps the rate above 20 % is the relevance label, and that is decided by an owner threshold this task forbade changing, applied to JDs far shorter than real postings.

Reaching the gate would require one of three changes:

1. lowering the STRONG threshold;
2. adding vocabulary that double-counts single mentions (demonstrated harmful by G095);
3. redefining the corpus's relevance expectations.

The first two are out of scope. The third is an owner decision.

---

## False Exclusions

| Case | Version | Evidence | Rule | Disposition |
|---|---|---|---|---|
| R2-066 | 0.2.2 → **fixed** | "Pay ranges — US: $160,000–$200,000 \| India: ₹42–55 LPA base" | COMP-R01 (read as ₹1.6–2.0 lakh) | Engine: component split + India band → ABOVE_TARGET PASS |
| R2-072 | 0.2.2 → **fixed** | "24-month fixed-term role; you'll be employed directly by …" | EMP-R03 | Engine: posting-level direct evidence → EMP-R10 UNKNOWN |
| R2-073 | 0.2.2 → **fixed** | structured "Contract"; JD "direct employee … on our own payroll" | EMP-R03 | Engine → EMP-R14 UNKNOWN + CONTRACT_DURATION_UNSTATED |
| R2-083 | 0.2.2 → **fixed** | "contract testing (Pact)", "OpenAPI contracts", "smart contract", "vendor contracts" | EMP-R03 | Engine: E1 exclusions → PERMANENT PASS |
| R2-SEQ-04 | 0.2.2 → **fixed** | "contract-review assistant" | EMP-R03 | Engine: E1 |
| **R2-023** | **0.2.3 remains** | location "Remote — Canada" | GEO-R03 (OR-50: named region excluding India → FAIL) | **Explained, not an engine defect.** The engine follows OR-50; the corpus reads a single foreign country as an unqualified listing (UNKNOWN). Owner question Q3 below. The fixture is not altered. |

Under 0.2.3 there are **zero unexplained false EXCLUDED**. This is enforced by `test_round2_replay_023_has_no_unexplained_false_excluded`.

## False Shortlists

| Case | Version | Disposition |
|---|---|---|
| R2-025 | 0.2.2 → **fixed** | "Remote, India" + "five days a week from our Chennai delivery centre" now gives CONFLICTING_SOURCES → UNKNOWN + WORK_MODE_CONFLICT → REVIEW (E6). |

Under 0.2.3 there are zero false shortlists.

## Lane Changes (Round-2, 0.2.2 → 0.2.3)

- **PARKED → SHORTLIST / REVIEW:** 48 incorrect PARKED became 0. Most were WEAK-relevance parking, now resolved by the E8 vocabulary, or Tier 1 + one AI term now going to REVIEW under E7 (LANE-R10).
- **REVIEW → SHORTLIST:** language UNKNOWN (LANGUAGE_UNCERTAIN) no longer sends English JDs to REVIEW. Office-day wording now resolves Bengaluru hybrid PASS / FAIL instead of HYBRID_DAYS_UNSPECIFIED.
- **EXCLUDED → REVIEW / SHORTLIST:** R2-066, 072, 073, 083 and SEQ-04 (E1, E2).
- **SHORTLIST → REVIEW:** R2-025 (E6 conflict), and SEQ-01 no longer carries a spurious SOURCE_CONFLICT.

## Policy Impact

- **Policy semantics changed only where Addendum E rules** (OR-66 … OR-73):
  - EMP-R15 (EMPLOYMENT_SOURCE_CONFLICT);
  - EMPR-R08 / R09 (third-party payroll → employer FAIL);
  - LANE-R10 + RELEVANCE_TITLE_PRIOR;
  - the E4 language thresholds;
  - E6 office-day normalisation;
  - E8 vocabulary.
- **Everything else is extraction repair:** it serves existing rulings and is listed in the rulings log as "implementation-level interpretations (recorded, not rulings)".
- **Unchanged:** thresholds, compensation bands, FX rules, the geography rule table, queue ordering, cap and carry.
- **Round-2 relevance labels:** no change to relevance thresholds was made to improve them.

## Version Integrity

| Artifact | SHA-256 |
|---|---|
| `policy/jobops-policy-0.2.0.json` | `65f74aec883d475989ea0594fac070f547c96a697bc1f7f4b46cf8e0d5dd567a` (unchanged) |
| `policy/jobops-policy-0.2.1.json` | `af19a3fd998e945cba19ce68f0e36f2eba4156e8bfd5255ac4ea7dacf7f5ea7d` (unchanged) |
| `policy/jobops-policy-0.2.2.json` | `3743bbaebce2b5f3143ec0a211d6c63aa35b8113dce03b1622876ef43eeed734` (unchanged) |
| `policy/jobops-policy-0.2.3.json` | `918bf66e7d83d06d7ff7b10c6d8b1309cbabd033331315510851110856659d77` (new, EXPERIMENTAL) |
| Round-1 fixture `tests/fixtures/policy_v02_blind_cases.json` | `44de6af6d8b9bb505044d0b6b871e24cf88a19262bfb90b2b5cf2f6aecdf331a` (unchanged) |
| Round-2 fixture (repo copy and `~/jobops-blind-round2/`) | `f54eb41bc805a28162e69e77495557b3647dd82e3b7c110c2987981edee421e5` (unchanged) |
| Live DB `data/jobs-tracker.db` | `bf17ebb1b97dd520680e84ac695c3fd1d280694587801278598b23dca1333285` (unchanged; only byte-copied into scratch) |

`evaluation/policy_loader.DEFAULT_VERSION` = **`jobops-policy@0.2.2`**. 0.2.3 is registered in `POLICY_PATHS` for replay and testing only.

## Acceptance Decision

**NOT ACCEPTED — 0.2.2 remains default**

## Remaining Risks

- **Adapter / schema gaps:** blind fixtures without FX rates leave compensation for foreign bands unscorable, and foreign bands without "per year" are PERIOD_UNSTATED (UNKNOWN). Evidence completeness in queue ordering doesn't distinguish missing evidence from known-UNKNOWN facts.
- **Natural-language long tail:**
  - office-day phrasing outside the normaliser, such as "every second week" or "most days";
  - employment phrasing outside the multi-word vocabulary, such as "a six-month engagement";
  - the nearest-cue assignment of weekdays is heuristic.
- **Language detection limits:** function-word lists cover six Latin-script languages plus any non-Latin script. Other Latin-script languages (Polish, Swedish, Turkish …) are detected only through diacritics, and a short mixed text can land in UNKNOWN.
- **Office-day ambiguity:** "alternate days" = 2.5 is an interpretation of "normalise alternate-day language". Weeks other than Monday–Friday are assumed standard.
- **FX:** there is still no owner FX table in the repository, so every foreign-only band is UNKNOWN in practice.
- **Relevance vocabulary:**
  - contextual `evaluat*` can promote classical ML/NLP roles (R2-101);
  - short real JDs will be MODERATE / WEAK under the unchanged threshold;
  - the E7 title prior mitigates only for Tier 1 titles.

## Future Recommendation

This is justified by the measured residual.

1. **The residual is not a long-tail extraction problem.** After P5, the eligibility and extraction dimensions match the corpus except for 2 policy-conflict cases. The remaining 54 mismatches are relevance labels on very short JDs. An LLM extraction layer would not change them without also changing the relevance definition, so **an LLM-assisted extraction layer is not recommended on this evidence**.
2. **Before Round 3**, the owner should decide Q1 below. Round 3 should also use realistic JD lengths or state the relevance expectation rule, so it measures the engine rather than the definition gap.
3. If a later round shows extraction long-tail failures (office-day and employment phrasing), revisit an LLM *evidence extractor* ahead of the deterministic engine, with verbatim spans and no verdicts.

### Owner questions (not resolved by P5)

- **Q1 (relevance definition):** Should a JD of one or two sentences that names two AI capabilities (e.g. "Build LLM-based underwriting assistants and evals") be STRONG? Yes or no. The current owner definition says no.
- **Q2 (queue ordering):** Should "evidence completeness" count only UNKNOWNs caused by missing evidence, not UNKNOWNs from known facts such as a consultancy employer? Yes or no.
- **Q3 (OR-50 vs Round-2 §3):** Is "Remote — <single foreign country>" a region lock (FAIL, OR-50) or an unqualified foreign listing (UNKNOWN)? Choose one.
- **Q4:** Should the Addendum D items proposed in P4b (OI-050 = NO, OI-051 = YES) now be recorded in the rulings log? P5 did not record them.

## Git status

No commit, no staging, no branch change: HEAD is `313ec4ca7b44c329ff9cc457f4259569a10e9b72`.

**Modified:**
- `OWNER_RULINGS_LOG.md` (append-only)
- `company/registry.py`
- `evaluation/{compensation,dimensions,engine,extract,newness,policy_loader,selection,service}.py`
- `relevance/labeller.py`
- `tests/fixtures/policy_v02_golden_cases.json` (additive)
- `tests/test_v02_store_migrations.py`

**New:**
- `evaluation/officedays.py`
- `policy/jobops-policy-0.2.3.json`
- `store/migrations/0103_third_party_payroll_classification.sql`
- `tests/fixtures/policy_v023_golden_cases.json`
- `tests/fixtures/policy_v02_blind_round2_*` (5 files)
- `tests/r2_blind_harness.py`, `tests/r2_replay.py`, `tests/test_p5_policy_023.py`
- this report
- the P4b report (untracked since P4b)
