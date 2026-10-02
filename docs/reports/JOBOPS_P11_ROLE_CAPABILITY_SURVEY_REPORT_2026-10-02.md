# JobOps P11 — Real-JD Role-Capability Survey (2026-10-01 pilot corpus)

> This survey is descriptive and does not modify JobOps eligibility, relevance, lane, queue, compensation,
> employer, geography, or policy.

**Status: complete, not committed.**

The survey covers all 207 unique jobs from the real 2026-10-01 pilot export. It runs offline and is deterministic: no network, no LLM, no new dependency.

Ground rules:
- **No scores.** There is no score, ranking or fit percentage.
- **Keywords are not expertise.** A keyword match shows what a JD *asks for*, not what the candidate can do.
- **JobOps unchanged:** P10 behaviour, policies 0.2.0 – 0.2.6, the frozen fixtures and `OWNER_RULINGS_LOG` are all unchanged.

## 1. What was implemented

| File | Status | Purpose |
|---|---|---|
| `tools/jd_skill_survey.py` | new | The survey (stdlib only). Reuses `jobops.normalize` readers (JSON / container / JSONL / CSV). |
| `tools/jd_survey_candidate_profile.json` | new | Candidate profile levels. A data file: correct it here, not in code. |
| `tests/test_p11_jd_skill_survey.py` | new | 40 tests on synthetic fixtures written for P11. |
| `runs/skill_survey_2026-10-02/` | git-ignored output | `summary.md`, `jobs.csv`, `capabilities.csv`, `gaps.csv`, `experience.csv`, `archetypes.csv`, `metrics.json` |

No tracked file was modified.

To reproduce:

```bash
python3 tools/jd_skill_survey.py --input exports/linkedin-2026-10-01.json \
  --out runs/skill_survey_2026-10-02 --decisions-db runs/state/jobops-p9.sqlite
```

**How JobOps context is attached.** The tool runs the unchanged P10 `run_source` on the same file, in a throwaway temporary directory. From that run it attaches `existing_lane`, `existing_relevance`, `existing_tier` and the requisition id. `--decisions-db` opens the pilot state read-only (`mode=ro`) to read human decisions; there are 0. JobOps context never filters the population.

## 2. Input population and deduplication

| Item | Value |
|---|---|
| Input | `exports/linkedin-2026-10-01.json`, SHA-256 `9af542a6c8b7fe29e2a819437d6b9c0f15ad66671d7355b6955e0fe3528f9805`; byte-identical before and after |
| Raw rows / unique jobs / duplicate records | **300 / 207 / 93** |
| Invalid records | 0 |
| Duplicate groups whose JD text differs | 0 |

**Dedup key**, in order:
1. LinkedIn `id`;
2. else the numeric id in `/jobs/view/…-<n>`;
3. else the URL without query or fragment;
4. else normalised `company|title|location`.

All 207 jobs were keyed by `id`. `link` is unique on every row (tracking parameters), so it can't serve as a key.

**Representative record:** the one with the longest description (HTML, then text); ties go to the first position.

**Cross-check against the engine:** the JobOps engine also forms 207 requisitions, and the mapping is one-to-one. The engine's lanes are EXCLUDED 21, PARKED 2, REVIEW 184, identical to the P9/P10 pilot.

## 3. Capability taxonomy

The seven clusters C1–C7 are as specified, implemented as a fixed regex lexicon of 123 canonical terms with alias normalisation. Examples of the normalisation:
- GPT-4 / ChatGPT → "OpenAI / GPT", in the LLM-API family;
- sklearn → scikit-learn;
- Lang Chain → LangChain;
- model-context protocol → MCP;
- retrieval augmented generation → RAG;
- pgvector → Vector DB;
- XGBoost / LightGBM / CatBoost → Gradient boosting family.

The matched original text is kept in `capabilities.csv` (`matched_text`).

**X0** is an extra bucket for non-AI stack terms such as Java, .NET, React, Spark and Kafka. It is reported in the technology and gap tables only and never feeds intensity or archetype.

**Traditional-ML terms come in two kinds:**
- **concrete** (`ml_strong`): scikit-learn, gradient boosting, PyTorch, TensorFlow, feature engineering, model training, hyperparameter tuning, classification / regression / forecasting models, recommendation systems, CV/OCR, statistical modelling, A/B testing, ML pipelines;
- **generic wording** (`ml_weak`): "machine learning", "AI/ML", "deep learning", "NLP", "data science", pandas/numpy. These count only as ML_MENTION and are never a gap.

## 4. Evidence placement methodology

Each JD is split into blocks. HTML `<p>`, `<li>` and `<h*>` are used when present (205 jobs); otherwise text lines. A JD with fewer than 3 blocks is split into sentences (2 jobs).

**Headings** are blocks that are fully bold, ≤ 80 characters and don't end in "." (or short lines ending ":"). A heading applies **only until the next heading**, and its section class is matched in this order:
- **PREFERRED:** preferred, nice/good to have, bonus, desirable, plus …
- **ROLE:** summary, overview, about the role …
- **INCIDENTAL:** about us, benefits, EEO, compensation, location, hiring process …
- **CORE:** responsibilities, requirements, qualifications, must have, skills, experience …
- **STACK:** tech stack, tools …
- **UNKNOWN:** anything else.

**Block placement:**

| Section | Placement |
|---|---|
| CORE | CORE, unless the line has a preference cue ("is a plus", "preferred", "nice to have" …), then PREFERRED |
| PREFERRED | PREFERRED |
| INCIDENTAL | INCIDENTAL |
| ROLE / STACK / UNKNOWN / preamble | Decided by explicit cues only: a preference cue gives PREFERRED; a requirement cue ("must", "required", "N+ years", "experience with", "responsible for", or a responsibility verb opening a bullet) gives CORE; a company cue ("We are…", "Our platform…") gives INCIDENTAL; otherwise **UNKNOWN_PLACEMENT** (never forced) |

Inline labels ("Required Skills: Python, RAG") apply to their own line only. Degree / field-of-study lines ("B.Tech in CS, Statistics, Data Science") are INCIDENTAL.

**Title evidence** is held separately. A title-only term never counts as CORE and doesn't drive the archetype.

**Block totals across the corpus:** CORE 4112, UNKNOWN_PLACEMENT 1647, INCIDENTAL 1152, PREFERRED 792.

## 5. Intensity, Traditional-ML levels and archetypes

**Intensity per cluster** (C7 counts concrete terms only):

| Intensity | Rule |
|---|---|
| HIGH | ≥ 3 distinct CORE terms, or terms in ≥ 3 CORE blocks |
| MODERATE | 2 CORE terms or 2 CORE blocks, or 1 CORE + ≥ 1 PREFERRED |
| LOW | 1 CORE term, preferred-only, or (C7) generic wording in a CORE block |
| UNKNOWN | only UNKNOWN_PLACEMENT evidence |
| NONE | otherwise (incidental or title only) |

**ML levels** (highest reached):

| Level | Rule |
|---|---|
| ML_MENTION | any C7 wording, title included |
| ML_PREFERRED | a concrete term, preferred only |
| ML_REQUIRED | ≥ 1 concrete term in a CORE block |
| ML_SUBSTANTIVE | ≥ 2 concrete terms in **≥ 2 distinct CORE blocks** (one framework list is not enough) |
| ML_DOMINANT | SUBSTANTIVE + C7 HIGH + more C7 CORE blocks than any of C1–C4 |

**Primary archetype**, first match. "Blocks" means CORE blocks.

| Rule | Condition | Archetype |
|---|---|---|
| R1 | ML_DOMINANT and C1–C3 ≤ LOW | Traditional ML |
| R2 | ML_SUBSTANTIVE and any of C1–C4 ≥ MODERATE | Hybrid LLM + Traditional ML |
| R3 | ML_SUBSTANTIVE and C7 ≥ MODERATE | Traditional ML |
| R4 | C4 ≥ MODERATE and C4 blocks ≥ max(2, C1–C3 blocks) | Evaluation / Reliability |
| R5 | an AI-specific C6 CORE term, C6 ≥ MODERATE and C6 blocks ≥ max(2, C1–C3 blocks) | AI-SDLC |
| R6 | C2 or C3 ≥ MODERATE | LLM / RAG / Agentic |
| R7 | C1 and C5 ≥ MODERATE | LLM Application + Backend |
| R8 | C1 ≥ MODERATE | LLM / RAG / Agentic |
| R9 | C5 ≥ MODERATE with an AI-platform CORE term or some C1–C4 evidence | AI Backend / Platform |
| R10 | some CORE evidence | Generic AI / Data / Other |
| R11 | otherwise | AI keyword only / insufficient evidence |

Each job's rule is recorded in `jobs.csv` (`archetype_rule`).

## 6. Candidate-profile methodology

The levels come from the P11 brief, cross-checked against `docs/Career_Strategy_and_Search_Preferences.md` §7, and are stored in `tools/jd_survey_candidate_profile.json`.

| Level | Contents |
|---|---|
| **CORE** | The brief's primary areas. "LLM application engineering" is expanded to LLM APIs / Generative AI / prompt engineering. Root-cause analysis comes from the doc's "AAVA multi-agent RCA pipeline (Strong)". |
| **WORKING** | LangChain, LangGraph, Ragas, DeepEval, MCP, Chroma. Never presented as production depth. |
| **SUPPORTING** | **Not a claim of experience.** A sub-topic of a named CORE area (e.g. Vector DB under FAISS/RAG, guardrails under AI quality), or a doc-named skill (Pandas, Snowflake). The basis is recorded per item. |
| **LIMITED** | Traditional ML development, scikit-learn, gradient boosting, training / tuning, feature engineering. |
| **NOT_ESTABLISHED** | Everything else. |

**Gap classes:**
- **CORE_GAP:** a term in a JD CORE block whose profile level is SUPPORTING / LIMITED / NOT_ESTABLISHED.
- **WORKING_GAP:** the profile level is WORKING.
- **PREFERRED_ONLY, INCIDENTAL_ONLY:** never gaps.
- **GENERIC_ML_MENTION:** generic ML wording; never a gap.

**`PRIMARY_CAPABILITY_ALIGNMENT`** is a category, not a score:

| Category | Rule |
|---|---|
| **DIRECT** | No hard AI-cluster gap (LIMITED / NOT_ESTABLISHED in C1–C4, C6), ≤ 1 WORKING, ≤ 1 hard stack gap, no concrete-ML gap |
| **ADJACENT** | No hard AI or ML gap, but more WORKING or stack gaps |
| **PARTIAL** | More AI-cluster CORE matches than hard gaps |
| **LIMITED** | Traditional-ML-primary, or hard gaps at least as many as matches |
| **INSUFFICIENT_EVIDENCE** | No usable CORE requirement evidence |

## 7. Major market findings (descriptive)

**Archetypes (207):**

| Archetype | Jobs | Share |
|---|---:|---:|
| LLM / RAG / Agentic | 118 | 57% |
| Hybrid LLM + Traditional ML | 25 | 12% |
| AI Backend / Platform | 16 | 8% |
| LLM Application + Backend | 15 | 7% |
| LLM Evaluation / Reliability | 12 | 6% |
| Traditional ML | 10 | 5% |
| Generic | 6 | 3% |
| AI-SDLC | 3 | 1% |
| Insufficient evidence | 2 | 1% |

**Cluster demand (CORE or PREFERRED postings):**

| Cluster | Postings | Share | HIGH |
|---|---:|---:|---:|
| C1 LLM application | 187 | 90% | 122 |
| C5 backend / platform | — | 97% | 158 |
| C3 agentic | 152 | 73% | 93 |
| C2 RAG / retrieval | 143 | 69% | 71 |
| C4 evaluation / reliability | 114 | 55% | 39 |
| C6 AI-SDLC | — | mostly LOW | — |

**Traditional ML is mentioned widely but rarely primary:**
- 155 postings mention ML vocabulary.
- 71 require at least one concrete ML technique, 35 are substantive, and 16 dominant.
- **10 (5%) are Traditional-ML-primary** and 25 (12%) are hybrid.
- Generic "AI/ML" wording in a CORE line appears in 123 postings and is never counted as a gap.

**Role combinations:**

| Combination | Postings |
|---|---:|
| LLM + Backend | 181 |
| Agentic + Backend | 147 |
| RAG + Agentic | 119 |
| Evaluation + Agentic | 92 |
| RAG + Evaluation | 89 |
| RAG + Agentic + Evaluation | 76 |
| LLM + concrete ML | 69 |

**Experience:**
- 155 of 207 postings state years; the median minimum is 5.
- By minimum: 0–3 years 32, 4–5 years 56, 6+ years 67, not stated 52.
- Median minimum by archetype: LLM / RAG / Agentic 5; Evaluation 5.5; Hybrid 6; Traditional ML 9.5.

**Market asks that are profile CORE strengths** (postings with the term in CORE):

| Term | Postings | Term | Postings |
|---|---:|---|---:|
| Python | 161 | Prompt engineering | 66 |
| LLMs | 147 | SQL | 58 |
| AI agents / agentic | 125 | LLM evaluation | 56 |
| REST / APIs | 120 | Embeddings | 49 |
| RAG | 108 | | |
| AWS | 79 | | |
| CI/CD | 69 | | |

**WORKING areas requested as CORE:** LangChain 53, LangGraph 39, MCP 33, Chroma 7, Ragas 1. These are developing areas, not absences.

**Most frequent CORE gaps:**

| Area | Gap | Postings |
|---|---|---:|
| Cloud and platform | Observability / monitoring | 69 |
| | Azure | 68 |
| | GCP | 49 |
| | MLOps / LLMOps | 48 |
| | Backend architecture | 43 |
| | Kubernetes | 39 |
| | Microservices | 30 |
| | Model serving | 30 |
| Supporting-level (adjacent to CORE RAG / AI quality) | Vector DB | 68 |
| | Vector / semantic search | 40 |
| | Guardrails | 37 |
| LLM | Fine-tuning | 39 |
| Concrete ML | PyTorch | 35 |
| | TensorFlow | 31 |
| Non-AI stack | Java | 34 |
| | JavaScript / TypeScript | 34 |

Full lists are in `summary.md` §12–14 and `gaps.csv`.

**Descriptive alignment:**

| DIRECT | ADJACENT | PARTIAL | LIMITED | INSUFFICIENT_EVIDENCE |
|---:|---:|---:|---:|---:|
| 29 | 40 | 85 | 49 | 4 |

This is not a fit score and is not used by JobOps.

**Market composition.** In this 207-job sample:
- 69% of roles contain RAG/retrieval as a CORE or PREFERRED requirement;
- 73% contain agentic AI and 55% evaluation/reliability;
- 5% are Traditional-ML-primary.

Most roles combine LLM application work with backend/platform engineering. The most frequent non-profile requirements are cloud-platform breadth (Azure / GCP / Kubernetes / MLOps) rather than traditional ML.

## 8. Sanity checks (manual inspection; nothing hand-edited)

I inspected:
- 10 LLM/RAG/Agentic jobs (Full Stack AI Developer, Lead Engineer AI Studio, Agent Harness ×3, Infra Agent Systems …);
- 5 Evaluation;
- 5 Traditional-ML / Hybrid;
- 6 Generic;
- 2 insufficient-evidence jobs.

**Defects found → rule fixes (applied to the tool, never to outputs):**

| # | Defect found | Fix |
|---|---|---|
| 1 | "Statistics" in degree lines counted as statistical modelling | Degree lines → INCIDENTAL; bare "statistics" removed |
| 2 | One bullet "TensorFlow, PyTorch, scikit-learn" made agentic roles "Hybrid" (42 → 25 after the fix) | ML_SUBSTANTIVE needs ≥ 2 CORE blocks |
| 3 | Evaluation-primary won whenever C4 had 3 terms in one sentence (35 → 12), e.g. an agentic role with 8 agentic CORE blocks vs 2 evaluation | Rule R4 uses block dominance |
| 4 | Over-broad terms: "monitoring" (120 → 89), "experimentation", "benchmarks" (matched "source online benchmarks"), OpenTelemetry treated as LLM tracing | Patterns narrowed |
| 5 | Degree regex matched the word "be" | Abbreviations made case-sensitive |
| 6 | A JD fused into one HTML block was marked entirely PREFERRED by one cue | Sentence split for JDs with < 3 blocks |
| 7 | Generic "AI/ML" wording was the top "CORE gap" (123) and inflated LIMITED / PARTIAL, plus "LLM + ML" combos (122 → 69) | Generic wording excluded from gaps, alignment and C7 combinations |

**Classifications that remain debatable (shown, not changed):**
- **4472145623, "AI Platform Engineer (Python, AWS)"** → Evaluation (R4: C4 3 blocks = C1 3 blocks), although its C5 has 13 blocks. Platform is arguably the better reading. The tie goes to Evaluation by rule order.
- **4471664198, "AI Software Engineer"** → Evaluation, from guardrails / evals / AI safety in a single paragraph that also covers product features.
- **4472486765, "Gen AI Python Developer"** → insufficient evidence. The source HTML has no separators at all ("…3/5Location: RemoteJob Type…"), so sentences can't be recovered. This is a data limitation.
- **4436714951, "Research SDE (MSR)"** → insufficient evidence. Every AI term sits under "Preferred"; correct per the rules.
- **4472689958, "Senior ML Engineer"** → Generic. "Propensity modelling" is not in the lexicon (a lexicon-coverage limitation).
- **NetApp-type postings** (frameworks in one bullet, no LLM evidence) → Generic, not ML-primary, by design of the ML_SUBSTANTIVE rule.

The overall judgement from inspection: LLM/RAG/Agentic, Traditional-ML and Hybrid assignments looked right in every inspected case. Evaluation-primary is the least stable category, because it's decided by block counts.

## 9. Tests

`tests/test_p11_jd_skill_survey.py`, 40 tests:

| Group | Tests |
|---|---|
| Input and population | JSON list; JSONL; duplicate ids (richest kept); duplicate links without id; missing id / link fallback |
| Placement | RAG core / preferred / incidental; preferred cue in a required section; unknown placement not forced; a Preferred section ends at the next heading; title-only RAG |
| Clusters and archetypes | Agentic core; LangGraph preferred; Evaluation core; Traditional-ML heavy; Hybrid; Generic / insufficient; an ML mention that must not become ML-heavy (incl. degree line); multiple clusters |
| Candidate alignment and gaps | CORE match (DIRECT); WORKING → WORKING_GAP, not absence; LIMITED; genuine CORE gap; preferred never a gap; generic ML wording never a gap |
| Experience | 4 phrasings; largest minimum; not stated (company "20 years" ignored) |
| Evidence and outputs | Snippets are verbatim substrings; no score / rank columns; no "you should apply" |
| Determinism and context | Byte-identical outputs; JobOps context attached, one-to-one, never filters |
| Integrity | Policy hashes before / after a run; no network / LLM imports; profile levels |

A mutation check was also run outside the suite. Disabling the preferred cue, the degree rule, the two-block ML rule, or section classification each made the targeted tests fail; all four were caught.

**Totals:**

| | Passed | Failed | xfailed | Skipped | Errors |
|---|---:|---:|---:|---:|---:|
| P11 file | 40 | 0 | — | — | — |
| Full suite (same command as P8–P10; four live-DB P0 tests excluded) | **3462** (3422 + 40) | 0 | 61 | 0 | 0 |

## 10. Policy / hash / P10 parity

| Check | Result |
|---|---|
| Policy 0.2.0 – 0.2.6 SHA-256 | Unchanged (0.2.6 `de527c5d…0455`); asserted in-test before and after a survey run |
| Engine, `jobops/`, `policy/`, `store/`, fixtures (Round 1/2/3, P9, P10), `OWNER_RULINGS_LOG.md`, open items | No diff (`git status` shows only the three new untracked files) |
| P10 behaviour | Unchanged: no `jobops/` change. The P10 suite passes, including P9 parity across 227 requisition-days. The survey's throwaway engine run reproduces the pilot lanes (184 / 2 / 21) |
| Eligibility / relevance / experience / lane / queue | Not touched. The survey only reads the engine's output in a temporary state |
| Real pilot input | Byte-identical (sha256 check) |
| `runs/state` (real pilot state) | Opened read-only only |

What could not be checked: nothing required was skipped.

## 11. Limitations

- **Lexicon coverage.** Capabilities outside the lexicon are invisible; examples include "propensity modelling", domain skills, and soft skills.
- **Placement is heuristic.** 1647 blocks remain UNKNOWN_PLACEMENT by design. A JD without headings relies on line cues.
- **Single-sentence clusters.** Several terms in one long sentence can make a cluster HIGH. Intensity is evidence breadth, not effort share.
- **Experience takes the largest stated minimum.** "2+ years in LLMs" inside "6+ years overall" yields 6, and years are never inferred.
- **Vendor-specific terms are separate.** Pinecone, Azure and the like are NOT_ESTABLISHED even where a sibling (FAISS, AWS) is CORE.
- **SUPPORTING is adjacency, not experience.** The owner should review that list.
- **One day, one source.** One day of LinkedIn/Apify results for this search; not a general market sample.

Nothing in this report is a recommendation, a JobOps input or a policy change.

## 12. Not done (by design)

No commit, stage or branch change. No policy edit, no 0.2.7, no OI-059 / OI-060 resolution. No Round 4, no Gate E, no scheduler, no live source, no LLM extraction. No change to relevance or lanes.
