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
- **Review queue:** 16 shown in 16 of 20 cap slots, filled T1 → T2 → T3 → T4; 0 in overflow (still REVIEW, carried to tomorrow); 0 parked today after 3 carry days (OR-88); 0 held for an incomplete JD.

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

### AI Evaluation Engineer — Pikestaff  `req_0000014`
- **Where:** India · **Mode:** not stated
- **Pay:** ₹26 LPA – ₹32 LPA
- **Relevance:** STRONG · **Newness:** NEW · **Experience:** REASONABLE
- **Tier:** T3 — Location / Work Mode Unclear
- **Blockers:** geography unclear (work arrangement absent)
- **Apply:** https://jobs.example-board.test/view/p10-014
- **Eligibility:** geography UNKNOWN · compensation PASS · employment PASS · employer PASS · language PASS
- **Why:** geography UNKNOWN (GEO-R16): WORK_ARRANGEMENT_ABSENT
  > India
  > You will design evaluation harnesses and golden datasets for our LLM assistants, measure groundedness and faithfulness of RAG answers, and add guardrails that catch hallucinations before release.
- **Flags:** WORK_ARRANGEMENT_ABSENT, COMP_BASIS_UNSTATED, IN_TARGET

### GenAI Quality Engineer — Wrenfold  `req_0000015`
- **Where:** Bengaluru, Karnataka, India · **Mode:** Remote
- **Pay:** ₹26 LPA – ₹32 LPA
- **Relevance:** STRONG · **Newness:** NEW · **Experience:** REASONABLE
- **Tier:** T3 — Location / Work Mode Unclear
- **Blockers:** work mode conflict
- **Apply:** https://jobs.example-board.test/view/p10-021
- **Eligibility:** geography UNKNOWN · compensation PASS · employment PASS · employer PASS · language PASS
- **Why:** geography UNKNOWN (GEO-R25): A higher-precedence source states one work mode and a lower-precedence source makes a genuine work-arrangement statement of another (e.g. structured Remote + '…
  > This role is fully on-site at our Bengaluru office.
  > You will design evaluation harnesses and golden datasets for our LLM assistants, measure groundedness and faithfulness of RAG answers, and add guardrails that catch hallucinations before release.
- **Flags:** WORK_MODE_CONFLICT, COMP_BASIS_UNSTATED, IN_TARGET

### LLM Test Engineer — Oakhurst Digital  `req_0000013`
- **Where:** Bengaluru, Karnataka, India · **Mode:** Hybrid
- **Pay:** not stated
- **Relevance:** STRONG · **Newness:** NEW · **Experience:** REASONABLE
- **Tier:** T3 — Location / Work Mode Unclear
- **Blockers:** geography unclear (hybrid days unspecified); pay not stated
- **Apply:** https://jobs.example-board.test/view/p10-013
- **Eligibility:** geography UNKNOWN · compensation UNKNOWN · employment PASS · employer PASS · language PASS
- **Why:** geography UNKNOWN (GEO-R08): mode=HYBRID, city_class=BENGALURU, office_days is_null True; compensation UNKNOWN (COMP-R06): state=ABSENT
  > Bengaluru, Karnataka, India
  > You will design evaluation harnesses and golden datasets for our LLM assistants, measure groundedness and faithfulness of RAG answers, and add guardrails that catch hallucinations before release.
- **Flags:** COMP_UNDISCLOSED, HYBRID_DAYS_UNSPECIFIED

## REVIEW — T4 Other

### GenAI Test Engineer — Quernstone  `req_0000016`
- **Where:** Remote, India · **Mode:** Remote
- **Pay:** ₹26 LPA – ₹32 LPA
- **Relevance:** STRONG · **Newness:** NEW · **Experience:** REASONABLE
- **Tier:** T4 — Other
- **Blockers:** employment type not stated
- **Apply:** https://jobs.example-board.test/view/p10-015
- **Eligibility:** geography PASS · compensation PASS · employment UNKNOWN · employer PASS · language PASS
- **Why:** employment UNKNOWN (EMP-R12): EMPLOYMENT_UNSTATED
  > You will design evaluation harnesses and golden datasets for our LLM assistants, measure groundedness and faithfulness of RAG answers, and add guardrails that catch hallucinations before release.
- **Flags:** EMPLOYMENT_UNSTATED, COMP_BASIS_UNSTATED, IN_TARGET

### AI QA Engineer — Rushmoor Labs  `req_0000017`
- **Where:** Remote, India · **Mode:** Remote
- **Pay:** ₹20 LPA – ₹30 LPA
- **Relevance:** STRONG · **Newness:** NEW · **Experience:** REASONABLE
- **Tier:** T4 — Other
- **Blockers:** pay range starts below target
- **Apply:** https://jobs.example-board.test/view/p10-016
- **Eligibility:** geography PASS · compensation PASS · employment PASS · employer PASS · language PASS
  > You will design evaluation harnesses and golden datasets for our LLM assistants, measure groundedness and faithfulness of RAG answers, and add guardrails that catch hallucinations before release.
- **Flags:** COMPENSATION_REVIEW, COMP_BASIS_UNSTATED

### LLM Quality Analyst — Sedgefield AI  `req_0000018`
- **Where:** Remote, India · **Mode:** Remote
- **Pay:** not stated
- **Relevance:** STRONG · **Newness:** NEW · **Experience:** REASONABLE
- **Tier:** T4 — Other
- **Blockers:** pay not stated; employment type not stated
- **Apply:** https://jobs.example-board.test/view/p10-017
- **Eligibility:** geography PASS · compensation UNKNOWN · employment UNKNOWN · employer PASS · language PASS
- **Why:** compensation UNKNOWN (COMP-R06): state=ABSENT; employment UNKNOWN (EMP-R12): EMPLOYMENT_UNSTATED
  > You will design evaluation harnesses and golden datasets for our LLM assistants, measure groundedness and faithfulness of RAG answers, and add guardrails that catch hallucinations before release.
- **Flags:** COMP_UNDISCLOSED, EMPLOYMENT_UNSTATED

## REVIEW — Overflow

Still REVIEW: carried to tomorrow (a non-STRONG item carried three days is PARKED, OR-88). `engine:` is plan_day's own status for the item (surfaced today, or carried with its carry day).

| Tier | Overflow |
|------|------:|
| T1 — Nearly Ready | 0 |
| T2 — Stretch Experience Only | 0 |
| T3 — Location / Work Mode Unclear | 0 |
| T4 — Other | 0 |


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
