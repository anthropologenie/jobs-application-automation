# JobOps digest — 2026-10-01

- Input: `tiers_export.json` (SHA-256 `d355a011c798cad8b64096d770caf56bf941ff7b2ec3a8b59eb88fd56666b844`)
- Policy: 0.2.6
- Policy SHA: de527c5d1dceb400913ec42e5aa527f19cd809e5054fcef5c61337d7fb890455
- Gate E: pending — Round 4 has not yet been measured
- Nothing here applies, submits or contacts anyone. You decide and apply yourself.

REVIEW tiers for this export's 16 REVIEW jobs (presentation only; verdicts and lanes are unchanged):

| Tier | Count |
|------|------:|
| T1 — Nearly Ready | 7 |
| T2 — Stretch Experience Only | 2 |
| T3 — Location / Work Mode Unclear | 4 |
| T4 — Other | 3 |

## Metrics

| jobs in | unique | duplicates | ambiguous identity | missing JD | truncated JD | no apply URL |
|---:|---:|---:|---:|---:|---:|---:|
| 21 | 21 | 0 | 0 | 0 | 0 | 0 |

| SHORTLIST | REVIEW | PARKED | EXCLUDED |
|---:|---:|---:|---:|
| 2 | 16 | 1 | 2 |

| SHORTLIST | T1 | T2 | T3 | T4 | READY-ISH |
|---:|---:|---:|---:|---:|---:|
| 2 | 7 | 2 | 4 | 3 | 11 |

- **SHORTLIST:** actionable under the current policy without resolving an UNKNOWN.
- **T1:** potentially actionable after resolving only employer-unclassified / pay-not-stated uncertainty.
- **T2:** as T1, plus a STRETCH experience consideration.
- **READY-ISH = SHORTLIST + T1 + T2.** A diagnostic presentation metric: the remaining uncertainty is narrow and named on each card. It is not SHORTLIST and not "ready to apply".
- SHORTLIST + REVIEW = 18: a P9 count, not an estimate of actionable supply.

- **Illustrative one-day estimate — not an application-supply forecast.** Today 11 of 21 source jobs were READY-ISH (52.4%); at that rate about 48 source jobs would give 25 READY-ISH and 58 would give 30.
- **READY-ISH is below 25.** The largest blocker among T3 / T4 jobs is **employment type not stated** (2 jobs). More source volume alone does not remove this blocker.
- **Most frequent REVIEW blocker:** pay not stated (8 jobs).
- **Largest bottleneck:** compensation UNKNOWN (8 jobs). Diagnostic only. No policy change is implied.
- **Review queue:** 10 shown in 10 of 10 cap slots, filled T1 → T2 → T3 → T4; 6 in overflow (still REVIEW, carried to tomorrow); 0 parked today after 3 carry days (OR-88); 0 held for an incomplete JD.

- **Engine queue note:** 3 shown job(s) count as *carried* in the engine's queue, and 3 overflow job(s) count as *surfaced* (plan_day orders by its policy keys; tiers only change what is displayed). Carry days and OR-88 parking follow the engine's count. See open item OI-057.

### Eligibility by dimension

| dimension | PASS | UNKNOWN | FAIL |
|---|---:|---:|---:|
| geography | 16 | 4 | 1 |
| compensation | 13 | 8 | 0 |
| employment | 18 | 2 | 1 |
| employer | 18 | 3 | 0 |
| language | 21 | 0 | 0 |
| relationship | 21 | 0 | 0 |

## SHORTLIST

### AI Quality Engineer — Morrowgate  `req_0000001`
- **Where:** Remote, India · **Mode:** Remote
- **Pay:** ₹26 LPA – ₹32 LPA
- **Relevance:** STRONG · **Newness:** NEW · **Experience:** REASONABLE
- **Apply:** https://jobs.example-board.test/view/p10-001
- **Eligibility:** geography PASS · compensation PASS · employment PASS · employer PASS · language PASS
  > You will design evaluation harnesses and golden datasets for our LLM assistants, measure groundedness and faithfulness of RAG answers, and add guardrails that catch hallucinations before release.
- **Flags:** COMP_BASIS_UNSTATED, IN_TARGET

### LLM Evaluation Engineer — Pebblecourt  `req_0000002`
- **Where:** Remote, India · **Mode:** Remote
- **Pay:** ₹26 LPA – ₹32 LPA
- **Relevance:** STRONG · **Newness:** NEW · **Experience:** REASONABLE
- **Apply:** https://jobs.example-board.test/view/p10-002
- **Eligibility:** geography PASS · compensation PASS · employment PASS · employer PASS · language PASS
  > You will design evaluation harnesses and golden datasets for our LLM assistants, measure groundedness and faithfulness of RAG answers, and add guardrails that catch hallucinations before release.
- **Flags:** COMP_BASIS_UNSTATED, IN_TARGET

## REVIEW — T1 Nearly Ready

### LLM Quality Engineer — Dunmore Works  `req_0000007`
- **Where:** Remote, India · **Mode:** Remote
- **Pay:** ₹26 LPA – ₹32 LPA
- **Relevance:** STRONG · **Newness:** NEW · **Experience:** REASONABLE
- **Tier:** T1 — Nearly Ready
- **Blockers:** employer unclassified
- **Apply:** https://jobs.example-board.test/view/p10-007
- **Eligibility:** geography PASS · compensation PASS · employment PASS · employer UNKNOWN · language PASS
- **Why:** employer UNKNOWN (EMPR-R04): EMPLOYER_UNCLASSIFIED
  > You will design evaluation harnesses and golden datasets for our LLM assistants, measure groundedness and faithfulness of RAG answers, and add guardrails that catch hallucinations before release.
- **Flags:** EMPLOYER_UNCLASSIFIED, COMP_BASIS_UNSTATED, IN_TARGET

### Evaluation Engineer, GenAI — Ashgrove Partners  `req_0000008`
- **Where:** Remote, India · **Mode:** Remote
- **Pay:** ₹26 LPA – ₹32 LPA
- **Relevance:** STRONG · **Newness:** NEW · **Experience:** REASONABLE
- **Tier:** T1 — Nearly Ready
- **Blockers:** employer unclassified
- **Apply:** https://jobs.example-board.test/view/p10-008
- **Eligibility:** geography PASS · compensation PASS · employment PASS · employer UNKNOWN · language PASS
- **Why:** employer UNKNOWN (EMPR-R04): EMPLOYER_UNCLASSIFIED
  > You will design evaluation harnesses and golden datasets for our LLM assistants, measure groundedness and faithfulness of RAG answers, and add guardrails that catch hallucinations before release.
- **Flags:** EMPLOYER_UNCLASSIFIED, COMP_BASIS_UNSTATED, IN_TARGET

### AI Evaluation Engineer — Hollowmere  `req_0000003`
- **Where:** Remote, India · **Mode:** Remote
- **Pay:** not stated
- **Relevance:** STRONG · **Newness:** NEW · **Experience:** REASONABLE
- **Tier:** T1 — Nearly Ready
- **Blockers:** pay not stated
- **Apply:** https://jobs.example-board.test/view/p10-003
- **Eligibility:** geography PASS · compensation UNKNOWN · employment PASS · employer PASS · language PASS
- **Why:** compensation UNKNOWN (COMP-R06): state=ABSENT
  > You will design evaluation harnesses and golden datasets for our LLM assistants, measure groundedness and faithfulness of RAG answers, and add guardrails that catch hallucinations before release.
- **Flags:** COMP_UNDISCLOSED

### GenAI QA Engineer — Brindlepath  `req_0000004`
- **Where:** Remote, India · **Mode:** Remote
- **Pay:** not stated
- **Relevance:** STRONG · **Newness:** NEW · **Experience:** REASONABLE
- **Tier:** T1 — Nearly Ready
- **Blockers:** pay not stated
- **Apply:** https://jobs.example-board.test/view/p10-004
- **Eligibility:** geography PASS · compensation UNKNOWN · employment PASS · employer PASS · language PASS
- **Why:** compensation UNKNOWN (COMP-R06): state=ABSENT
  > You will design evaluation harnesses and golden datasets for our LLM assistants, measure groundedness and faithfulness of RAG answers, and add guardrails that catch hallucinations before release.
- **Flags:** COMP_UNDISCLOSED

### ML Test Engineer — Coldharbour AI  `req_0000005`
- **Where:** Remote, India · **Mode:** Remote
- **Pay:** not stated
- **Relevance:** STRONG · **Newness:** NEW · **Experience:** REASONABLE
- **Tier:** T1 — Nearly Ready
- **Blockers:** pay not stated
- **Apply:** https://jobs.example-board.test/view/p10-005
- **Eligibility:** geography PASS · compensation UNKNOWN · employment PASS · employer PASS · language PASS
- **Why:** compensation UNKNOWN (COMP-R06): state=ABSENT
  > You will design evaluation harnesses and golden datasets for our LLM assistants, measure groundedness and faithfulness of RAG answers, and add guardrails that catch hallucinations before release.
- **Flags:** COMP_UNDISCLOSED

### AI Reliability Engineer — Fennick  `req_0000006`
- **Where:** Remote, India · **Mode:** Remote
- **Pay:** not stated
- **Relevance:** STRONG · **Newness:** NEW · **Experience:** REASONABLE
- **Tier:** T1 — Nearly Ready
- **Blockers:** pay not stated
- **Apply:** https://jobs.example-board.test/view/p10-006
- **Eligibility:** geography PASS · compensation UNKNOWN · employment PASS · employer PASS · language PASS
- **Why:** compensation UNKNOWN (COMP-R06): state=ABSENT
  > You will design evaluation harnesses and golden datasets for our LLM assistants, measure groundedness and faithfulness of RAG answers, and add guardrails that catch hallucinations before release.
- **Flags:** COMP_UNDISCLOSED

_engine queue: carried (carry day 1; OR-65 / OR-88 count it as not surfaced)_

### AI Test Engineer — Kestrel Row  `req_0000009`
- **Where:** Remote, India · **Mode:** Remote
- **Pay:** not stated
- **Relevance:** STRONG · **Newness:** NEW · **Experience:** REASONABLE
- **Tier:** T1 — Nearly Ready
- **Blockers:** pay not stated; employer unclassified
- **Apply:** https://jobs.example-board.test/view/p10-009
- **Eligibility:** geography PASS · compensation UNKNOWN · employment PASS · employer UNKNOWN · language PASS
- **Why:** compensation UNKNOWN (COMP-R06): state=ABSENT; employer UNKNOWN (EMPR-R04): EMPLOYER_UNCLASSIFIED
  > You will design evaluation harnesses and golden datasets for our LLM assistants, measure groundedness and faithfulness of RAG answers, and add guardrails that catch hallucinations before release.
- **Flags:** COMP_UNDISCLOSED, EMPLOYER_UNCLASSIFIED

## REVIEW — T2 Stretch Experience Only

### Senior AI Quality Engineer — Lanternfield  `req_0000010`
- **Where:** Remote, India · **Mode:** Remote
- **Pay:** ₹26 LPA – ₹32 LPA
- **Relevance:** STRONG · **Newness:** NEW · **Experience:** STRETCH
- **Tier:** T2 — Stretch Experience Only
- **Blockers:** experience stretch
- **Apply:** https://jobs.example-board.test/view/p10-010
- **Eligibility:** geography PASS · compensation PASS · employment PASS · employer PASS · language PASS
  > You will design evaluation harnesses and golden datasets for our LLM assistants, measure groundedness and faithfulness of RAG answers, and add guardrails that catch hallucinations before release.
- **Flags:** EXPERIENCE_STRETCH, COMP_BASIS_UNSTATED, IN_TARGET, SENIORITY_SENIOR

_engine queue: carried (carry day 1; OR-65 / OR-88 count it as not surfaced)_

### Senior LLM Evaluation Engineer — Marshwick  `req_0000011`
- **Where:** Remote, India · **Mode:** Remote
- **Pay:** not stated
- **Relevance:** STRONG · **Newness:** NEW · **Experience:** STRETCH
- **Tier:** T2 — Stretch Experience Only
- **Blockers:** pay not stated; experience stretch
- **Apply:** https://jobs.example-board.test/view/p10-011
- **Eligibility:** geography PASS · compensation UNKNOWN · employment PASS · employer PASS · language PASS
- **Why:** compensation UNKNOWN (COMP-R06): state=ABSENT
  > You will design evaluation harnesses and golden datasets for our LLM assistants, measure groundedness and faithfulness of RAG answers, and add guardrails that catch hallucinations before release.
- **Flags:** COMP_UNDISCLOSED, EXPERIENCE_STRETCH, SENIORITY_SENIOR

## REVIEW — T3 Location / Work Mode Unclear

_engine queue: carried (carry day 1; OR-65 / OR-88 count it as not surfaced)_

### AI Quality Engineer — Nettlebank  `req_0000012`
- **Where:** Bengaluru, Karnataka, India · **Mode:** Hybrid
- **Pay:** ₹26 LPA – ₹32 LPA
- **Relevance:** STRONG · **Newness:** NEW · **Experience:** REASONABLE
- **Tier:** T3 — Location / Work Mode Unclear
- **Blockers:** geography unclear (hybrid days unspecified)
- **Apply:** https://jobs.example-board.test/view/p10-012
- **Eligibility:** geography UNKNOWN · compensation PASS · employment PASS · employer PASS · language PASS
- **Why:** geography UNKNOWN (GEO-R08): mode=HYBRID, city_class=BENGALURU, office_days is_null True
  > Bengaluru, Karnataka, India
  > You will design evaluation harnesses and golden datasets for our LLM assistants, measure groundedness and faithfulness of RAG answers, and add guardrails that catch hallucinations before release.
- **Flags:** HYBRID_DAYS_UNSPECIFIED, COMP_BASIS_UNSTATED, IN_TARGET

## REVIEW — T4 Other

_None shown today._

## REVIEW — Overflow

Still REVIEW: carried to tomorrow (a non-STRONG item carried three days is PARKED, OR-88). `engine:` is plan_day's own status for the item (surfaced today, or carried with its carry day).

| Tier | Overflow |
|------|------:|
| T1 — Nearly Ready | 0 |
| T2 — Stretch Experience Only | 0 |
| T3 — Location / Work Mode Unclear | 3 |
| T4 — Other | 3 |

- `req_0000014` AI Evaluation Engineer — Pikestaff (T3; STRONG, NEW; geography unclear (work arrangement absent); engine: carried, day 1)
- `req_0000015` GenAI Quality Engineer — Wrenfold (T3; STRONG, NEW; work mode conflict; engine: surfaced)
- `req_0000013` LLM Test Engineer — Oakhurst Digital (T3; STRONG, NEW; geography unclear (hybrid days unspecified); pay not stated; engine: carried, day 1)
- `req_0000016` GenAI Test Engineer — Quernstone (T4; STRONG, NEW; employment type not stated; engine: surfaced)
- `req_0000017` AI QA Engineer — Rushmoor Labs (T4; STRONG, NEW; pay range starts below target; engine: surfaced)
- `req_0000018` LLM Quality Analyst — Sedgefield AI (T4; STRONG, NEW; pay not stated; employment type not stated; engine: carried, day 1)

## PARKED (1 from this export, 0 by overflow today)

- `req_0000021` Frontend Developer — Vintner Lane (relevance WEAK)

## EXCLUDED (2)

Listed with failing dimension and evidence in `excluded.csv`. Audit them for false exclusions.

## EXCLUDED by Dimension

Rows of `excluded.csv`; a job failing several dimensions counts once per dimension.

| dimension | jobs |
|---|---:|
| geography | 1 |
| compensation | 0 |
| employment | 1 |
| employer | 0 |
| language | 0 |
| relationship | 0 |

| rule | jobs |
|---|---:|
| EMP-R08 | 1 |
| GEO-R12 | 1 |
