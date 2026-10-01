# Round 3 undetermined items and authoring notes

## Cases marked UNDETERMINED

None. Every posting case and sequence that P7b scores has an expectation.

## Resolved by owner ruling (Addendum G, 2026-10-01, effective `jobops-policy@0.2.4`)

Pre-resolution authoring hash: `1ad02692fcdad4a9fd02070a8a30e7b20cd3f3d4fa5180cc9d6c2d69172429fe`. The final measurement hash is in `blind_cases_round3.sha256`.

- **R3-105** (was UNDETERMINED): 8–10 years → `experience_label = STRETCH`. **OR-84.**
- **R3-106** (was UNDETERMINED): ₹12–18L → compensation UNKNOWN. A range is FAIL only when its maximum is strictly below ₹18L; minimum < ₹18L with maximum ≥ ₹18L is a floor straddle. **OR-85.**
- **R3-107** (was UNDETERMINED): direct fixed term of exactly 6 months → employment UNKNOWN (long-term direct contract; short-term is strictly under 6 months). **OR-86.**
- **S-08** (was an assumption): newness order is NEW > UPDATED > SEEN_BEFORE, strictly. The assumption that NEW ranks above SEEN_BEFORE is confirmed and the sequence expectation is unchanged. **OR-87.**

The flag names now fixed by these rulings (`EXPERIENCE_STRETCH`, `SALARY_RANGE_STRADDLES_FLOOR`, `LONG_TERM_DIRECT_CONTRACT`) are not asserted in the corpus, matching sibling cases R3-039 and R3-071. Only the dimension verdicts and the experience label are asserted.

## Fields deliberately omitted because the sheet does not decide them

- Employer-type verdict for an `unclassified` hint (cases with `EMPLOYER_UNCLASSIFIED`): the sheet fixes the flag and the REVIEW routing but not the dimension verdict.
- Language dimension on no-JD search-only records: no text exists to detect, so it is omitted.
- Flag names for a long-term direct fixed-term arrangement and for free-text-versus-structured employment conflicts: the sheet says 'flag' without naming them, so only the dimension verdict is asserted. (OR-86 later names `LONG_TERM_DIRECT_CONTRACT`; the corpus still asserts only the verdict.)

## Assumptions the owner should know about

- ~~S-08 assumes queue ordering ranks NEW above SEEN_BEFORE inside the 'newness' step.~~ Resolved by OR-87.
- FX staleness is measured against `evaluation_date`, set equal to the posting's `posted_date` (fresh snapshot 2026-09-26, stale snapshot 2026-09-03 against 2026-09-28).
- Cases that assert `experience_label` use DIRECT and REASONABLE, plus STRETCH for R3-105 under OR-84.
- Two fully non-English JDs (German, French) assert language FAIL on the 0.95 rule; they are overwhelmingly non-English text.
- Relevance is asserted only where the JD plainly holds three or more AI terms across two or more clusters (STRONG), where the role is plainly not AI (WEAK), or where no JD exists (NOT_ASSESSED).
