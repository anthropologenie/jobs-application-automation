# Company Radar — Phase 1 Manual Discovery Worksheet

**Phase:** 1 — Manual Discovery Baseline
**Status:** OPEN — Search 001 complete, PAUSED after review (see §12 Decision Log)
**Owner / Searcher:** Karthik S R
**Agent role:** Recording, structuring, and evaluation only — the agent performed **no** discovery
**Authoritative spec:** [`../COMPANY_RADAR_EXPERIMENT.md`](../COMPANY_RADAR_EXPERIMENT.md)
**Created:** 2026-08-20
**Last updated:** 2026-08-20

---

## 0. Operating Instructions (Read First)

### 0.1 Who does what

| Activity | Owner |
|---|---|
| Running the searches (GitHub, careers pages/ATS, engineering blogs, POC lookup) | **Karthik — manually** |
| Reading results and deciding what is worth recording | **Karthik** |
| Structuring findings into this worksheet | Agent |
| Evaluating findings against the frozen Phase 1 criteria | Agent |
| Computing Phase 1 results and the exit-gate assessment | Agent |

**Hard rule:** the agent does not run web searches, call GitHub/Greenhouse/Lever/Ashby APIs, scrape careers pages, or use browser automation during Phase 1. Phase 3 will measure automated discovery *against* this baseline, so the baseline must be uncontaminated by agent-performed discovery.

### 0.2 How to record a finding

For each thing you find, capture the answers to these ten questions. Anything you can't answer, write `unknown` — do not guess, and do not let a blank field stop you from recording the finding.

| # | Question | Worksheet field |
|---|---|---|
| 1 | Which discovery term produced it? | `discovery_term` |
| 2 | Which channel produced it? | `channel` |
| 3 | What company was discovered? | `company` |
| 4 | Why is the company relevant? | `current_ai_activity` + `why_relevant` |
| 5 | What evidence supports that relevance? | `evidence` (specific URL / repo / post / posting) |
| 6 | Was a relevant person / POC identified? | `relevant_poc_name` |
| 7 | What is the person's role? | `relevant_poc_role` |
| 8 | How could they potentially be contacted? | `poc_contact_channel` |
| 9 | What is the quality / fit of the lead? | `initial_fit` |
| 10 | Would conventional job platforms likely have missed this? | `novel_vs_conventional` |

**Evidence standard (from spec §8):** evidence must be a *specific* artifact — a repo, a commit, a blog post, a job posting, a changelog — not a vague impression like "they seem to do AI." A finding with no citable artifact is recorded as a **weak match**, not a qualified company.

**Absence of a job opening is not disqualifying** (spec §8). The experiment is explicitly testing whether relevant companies can be found *before* a matching job title exists.

**Never fabricate.** No invented companies, people, emails, handles, job postings, or evidence links. `unknown` is always the correct answer when you don't know.

### 0.3 Recording rhythm

1. Run one search = one row in **§3 Search Log** (even if it produced zero findings — zero-yield searches are data for the hit-rate calculation).
2. Each company kept = one row in **§4 Findings Register** + one detail record in **§5**.
3. Each company rejected after a look = one row in **§6 Rejected / Weak Matches** with the reason.
4. Hand the raw notes to the agent in any format; the agent normalises them into these sections.

### 0.4 Time tracking

Log rough minutes per search session in §3. Spec §11 tracks *hours per qualified company* as a headline efficiency metric, and Phase 3 can only be compared to Phase 1 if Phase 1's manual cost was actually measured.

---

## 1. Frozen Phase 1 Scope (Do Not Extend)

### 1.1 Discovery terms (spec §6) — exactly three

1. `LLM evaluation`
2. `Agent evaluation`
3. `RAG reliability`

The wider ontology in spec §6 is **out of scope for Phase 1**.

### 1.2 Discovery channels (spec §7) — Channels A–D only, manual

| Code | Channel | Phase 1 use |
|---|---|---|
| A | GitHub — repos, orgs, contributors | Manual search |
| B | Company careers pages / ATS (Greenhouse, Lever, Ashby) | Manual lookup |
| C | Engineering blogs / technical activity | Manual review |
| D | POC identification + manual verification (via GitHub/company site, verified on LinkedIn) | Manual |

Channels E–H (LinkedIn/Wellfound as discovery, Slack/Discord, HN/Reddit, conferences) are **deferred** and must not be used as Phase 1 discovery sources. LinkedIn is permitted **only** as a Channel-D verification step for a POC already found via A–C.

### 1.3 Target company criteria (spec §5.1)

- [ ] Product company / startup / AI-focused firm — **not** staffing or services
- [ ] AI-native or AI-intensive product (LLMs, agents, RAG, model-driven decisions in the product itself)
- [ ] Remote-first, or hiring in India
- [ ] Demonstrable relevant engineering activity (repo, blog post, adjacent job posting)
- [ ] Evidence of plausible latent need in ≥1 of: AI Quality / AI Evaluation · LLM Testing / RAG Eval / Agent Eval · AI Data Quality · AI Reliability / Observability · AI Governance / Safety · AI Test Automation / Platform Quality

### 1.4 Target POC priority order (spec §5.2)

1. AI/ML Engineering Lead → 2. AI Platform Lead → 3. Engineering Manager → 4. Head of Eng / VP Eng → 5. CTO / Founder → 6. Technical Recruiter → 7. Talent Partner

### 1.5 Phase 1 exit gate (spec §9)

- **≥10–20 genuinely high-fit companies** discovered via Channels A–D
- **≥50% of them have an identified, verifiable POC**

---

## 2. Running Totals

| Metric | Value |
|---|---|
| Searches performed | 1 |
| Total findings recorded | 5 (4 kept, 1 rejected) |
| Qualified high-fit companies | 4 |
| Companies with identified POC | 0 (Channel D deferred — see §12) |
| Companies with **verified** POC | 0 |
| Verified-POC rate | 0% of qualified (4 findings) |
| Contactable leads | 0 confirmed (pending Channel D) |
| Weak matches / false positives | 1 (MedARC-AI/medmarks) |
| Novel vs. conventional platforms | 4 of 4 — see §9 |
| Manual time invested | ~35–45 min (est., Search 001 combined A+B pass) |

---

## 3. Search Log

| search_id | date | discovery_term | channel | query / surface actually used | results reviewed | findings kept | minutes | notes |
|---|---|---|---|---|---|---|---|---|
| 001 | 2026-08-20 | LLM evaluation | A (GitHub) + B (Careers, folded in) | GitHub Repositories search: `"LLM evaluation"` (~3.7k results) | Top ~30 by title scan; 5 opened in depth | 4 kept, 1 rejected | ~35–45 (est.) | Searcher scanned top 30 by title, opened 5 in depth. Careers pages checked directly on official sites for all 4 kept companies (Channel B folded into this search rather than run separately). |

---

## 4. Findings Register

| id | company | discovery_term | channel | why_discovered | evidence (link) | current_ai_activity | relevant_opening | relevant_poc_name | relevant_poc_role | poc_contact_channel | poc_verified | contactable | initial_fit | novel_vs_conventional | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| F-001 | Confident AI | LLM evaluation | A + B | GitHub repo search, top result by stars (17.7k) | https://github.com/confident-ai/deepeval | Enterprise AI evaluation/observability platform (DeepEval): pre-release eval, production monitoring, datasets, governance, red teaming | Relevant roles exist; onsite only (non-India/non-remote per available postings) | unknown | unknown | unknown | unknown | unknown | Perfect (product/company fit); location fit: No | Yes | Qualified |
| F-002 | LangWatch | LLM evaluation | A + B | GitHub repo search | https://github.com/langwatch/langwatch | End-to-end LLM/agent evaluation, simulation, observability, prompt optimization, governance | Relevant roles exist; onsite only (non-India/non-remote per available postings) | unknown | unknown | unknown | unknown | unknown | Perfect (product/company fit); location fit: No | Yes | Qualified |
| F-003 | Allen Institute for AI (AI2) | LLM evaluation | A + B | GitHub repo search | https://github.com/allenai/olmes | Reproducible LLM evaluation framework (OLMES) within AI2's open-LM research work | Relevant roles exist; onsite only (non-India/non-remote per available postings) | unknown | unknown | unknown | unknown | unknown | Good (research/nonprofit, not commercial product); location fit: No | Yes | Qualified |
| F-004 | Weights & Biases (W&B) | LLM evaluation | A + B | GitHub repo search | https://github.com/wandb/llm-leaderboard | LLM evaluation/benchmarking (Nejumi Leaderboard) within broader W&B AI developer platform | Relevant roles exist; onsite only (non-India/non-remote per available postings) | unknown | unknown | unknown | unknown | unknown | Good (benchmark project, not core eval product); location fit: No | Yes | Qualified |

**Field values**

- `initial_fit`: `Perfect` / `Good` / `Moderate` / `Poor` — same scale as `opportunities.domain_match` (spec §8)
- `poc_verified`: `Yes` / `No` / `unknown` — all four `unknown` pending Channel D (see §12)
- `contactable`: `Yes` / `No` / `unknown` — all four `unknown` pending Channel D
- `novel_vs_conventional`: `Yes` (would likely not surface via LinkedIn/Naukri/Indeed keyword search) / `No` / `unclear` — all four `Yes`; none of these would plausibly surface from a "AI Quality Engineer" LinkedIn/Naukri search
- `status`: `Qualified` / `Weak match` / `Rejected` / `Needs more research`

---

## 5. Finding Detail Records

### F-001 — Confident AI

```
discovery_term:        LLM evaluation
channel:                A (GitHub) + B (Careers)
why_discovered:         Top GitHub result by stars (17.7k) for "LLM evaluation" search
evidence:                https://github.com/confident-ai/deepeval
current_ai_activity:    Enterprise AI evaluation and observability platform (DeepEval) — pre-release
                         evaluation, production monitoring, datasets, governance, red teaming
why_relevant:            AI-native product company, core offering IS LLM evaluation; direct domain match
relevant_opening:       Some relevant roles observed on careers page; specific titles not logged
location(s):             Onsite (non-India, non-remote per postings checked)
remote_india_fit:        No
location_note:           Current postings require onsite presence; not remote/India-eligible as observed
relevant_poc_name:       unknown — Channel D not yet executed
relevant_poc_role:       unknown
poc_contact_channel:     unknown
poc_verified:            unknown
contactable:             unknown
initial_fit:             Perfect (product/company fit) — location fit separately flagged as No
novel_vs_conventional:   Yes — would not surface via standard "AI Quality Engineer" LinkedIn/Naukri search
criteria_check:          Product co (pass) / AI-native (pass) / Remote-India (fail) / Eng activity (pass) / Latent need (pass — is the need)
open_questions:          POC identification and LinkedIn verification pending
notes:                   Strongest technical/product-fit candidate in this search; worth tracking even
                         without a current remote opening, per spec's "latent opportunity" framing
```

### F-002 — LangWatch

```
discovery_term:        LLM evaluation
channel:                A (GitHub) + B (Careers)
why_discovered:         GitHub repo search result
evidence:                https://github.com/langwatch/langwatch
current_ai_activity:    End-to-end LLM/AI-agent evaluation, simulation, observability, prompt
                         optimization, and governance platform
why_relevant:            AI-native product company, core offering directly overlaps with target
                         specialization (LLM + agent evaluation)
relevant_opening:       Some relevant roles observed on careers page; specific titles not logged
location(s):             Onsite (non-India, non-remote per postings checked)
remote_india_fit:        No
location_note:           Current postings require onsite presence; not remote/India-eligible as observed
relevant_poc_name:       unknown — Channel D not yet executed
relevant_poc_role:       unknown
poc_contact_channel:     unknown
poc_verified:            unknown
contactable:             unknown
initial_fit:             Perfect (product/company fit) — location fit separately flagged as No
novel_vs_conventional:   Yes
criteria_check:          Product co (pass) / AI-native (pass) / Remote-India (fail) / Eng activity (pass) / Latent need (pass)
open_questions:          POC identification and LinkedIn verification pending
notes:                   Second-strongest candidate; same location caveat as Confident AI
```

### F-003 — Allen Institute for AI (AI2)

```
discovery_term:        LLM evaluation
channel:                A (GitHub) + B (Careers)
why_discovered:         GitHub repo search result
evidence:                https://github.com/allenai/olmes
current_ai_activity:    Reproducible LLM evaluation framework (OLMES), part of AI2's open-language-model
                         research work
why_relevant:            Strong technical match to LLM evaluation focus
relevant_opening:       Some relevant roles observed on careers page; specific titles not logged
location(s):             Onsite (non-India, non-remote per postings checked)
remote_india_fit:        No
location_note:           Current postings require onsite presence; not remote/India-eligible as observed
relevant_poc_name:       unknown — Channel D not yet executed
relevant_poc_role:       unknown
poc_contact_channel:     unknown
poc_verified:            unknown
contactable:             unknown
initial_fit:             Good — research/nonprofit ecosystem rather than commercial product-hiring signal;
                         downgraded from Perfect on that basis, not on location
novel_vs_conventional:   Yes
criteria_check:          Product co (fail — nonprofit research org) / AI-native (pass) / Remote-India (fail)
                         / Eng activity (pass) / Latent need (pass)
open_questions:          POC identification and LinkedIn verification pending; worth revisiting whether
                         nonprofit research orgs should count toward the "target company" criterion at all
notes:                   Kept as Good rather than rejected outright — genuinely relevant technical org,
                         but weaker fit against spec's "product company / startup" criterion
```

### F-004 — Weights & Biases (W&B)

```
discovery_term:        LLM evaluation
channel:                A (GitHub) + B (Careers)
why_discovered:         GitHub repo search result
evidence:                https://github.com/wandb/llm-leaderboard
current_ai_activity:    LLM evaluation/benchmarking (Nejumi Leaderboard) within broader W&B AI developer
                         platform (build/evaluate/monitor AI systems)
why_relevant:            Mature AI developer-platform company; strong ecosystem relevance, though this
                         specific repo is a niche benchmark rather than W&B's core eval offering
relevant_opening:       Some relevant roles observed on careers page; specific titles not logged
location(s):             Onsite (non-India, non-remote per postings checked)
remote_india_fit:        No
location_note:           Current postings require onsite presence; not remote/India-eligible as observed
relevant_poc_name:       unknown — Channel D not yet executed
relevant_poc_role:       unknown
poc_contact_channel:     unknown
poc_verified:            unknown
contactable:             unknown
initial_fit:             Good — repo itself is a side-project/benchmark, not direct evidence of a
                         dedicated AI-quality product or hiring need at company level
novel_vs_conventional:   Yes
criteria_check:          Product co (pass) / AI-native (pass, platform-level) / Remote-India (fail)
                         / Eng activity (pass) / Latent need (pass, inferred from platform not this repo)
open_questions:          Whether W&B's broader eng org (beyond this repo) has AI-quality-relevant roles;
                         POC identification and LinkedIn verification pending
notes:                   Weakest evidence chain of the four kept findings — repo-level evidence is thin,
                         company-level plausibility is what's carrying the "Good" rating
```

---

## 6. Rejected / Weak Matches

| id | company | discovery_term | channel | reason rejected | which criterion failed |
|---|---|---|---|---|---|
| R-001 | MedARC-AI (medmarks) | LLM evaluation | A (GitHub) | Open-source/research benchmark project, not an employer/company signal — no plausible hiring or contact path | Not a product/startup/AI-focused company (spec §5.1, criterion 1) |

---

## 7. Coverage Matrix

| | A. GitHub | B. Careers / ATS | C. Eng blogs | D. POC verification |
|---|---|---|---|---|
| **LLM evaluation** | ✅ done (Search 001) | ✅ done, folded into Search 001 | ☐ not searched | ☐ not searched (deferred, §12) |
| **Agent evaluation** | ☐ not searched | ☐ not searched | ☐ not searched | ☐ not searched |
| **RAG reliability** | ☐ not searched | ☐ not searched | ☐ not searched | ☐ not searched |

---

## 8. Ontology Observations

| observation | supporting finding ids | implication for Phase 3 |
|---|---|---|
| GitHub-repo-first discovery for "LLM evaluation" surfaces genuine, high-fit AI-native companies (Confident AI, LangWatch) reliably within the top ~10 results by stars — the term itself has good precision at the top of the results list | F-001, F-002 | If Phase 3 automates this, ranking by stars/recency is likely a reasonable first filter rather than needing deep NLP relevance scoring |
| Manual GitHub-repo browsing (opening each repo, reading README, hunting for company/POC info) is high-effort relative to yield — ~35–45 min produced 4 qualified companies with *zero* POCs actually completed | F-001–F-004 | This specific manual workflow (Channel A alone, repo-by-repo) is a strong automation candidate for Phase 3 — the bottleneck is human research time, not signal scarcity |
| First pass produced a striking pattern: 4 of 4 qualified companies have zero India/remote-eligible postings among the roles observed | F-001–F-004 | Either (a) this term/channel combination skews toward SF/US-centric AI-eval companies, or (b) this is a genuinely representative finding about the current market for this specialization — Search 002 (different term or channel) needed before concluding either way |
| Research/nonprofit orgs (AI2) and adjacent-but-not-core-product repos (W&B's benchmark) surface alongside pure-play product companies and dilute average fit quality | F-003, F-004 | A future automated qualifier should weight "is the org's *core product* AI evaluation" more heavily than "does the org have *a* repo about AI evaluation" |

---

## 9. Conventional-Platform Comparison Notes

| company | would LinkedIn/Naukri/Indeed have surfaced it? | basis for that judgement |
|---|---|---|
| Confident AI | No | A "AI Quality Engineer" / "AI Evaluation Engineer" LinkedIn search targeting India/remote would not naturally surface a US-based company with no India/remote posting under that title |
| LangWatch | No | Same reasoning — small, technically-focused company unlikely to appear in a generic India/remote-filtered job-board search |
| Allen Institute for AI | No | Nonprofit research org rarely appears in commercial job-board searches under standard QA/AI-eval titles |
| Weights & Biases | Unclear | W&B is large enough that some of their India/remote roles might independently surface on LinkedIn under different titles — but this specific AI-eval angle would not |

---

## 10. Phase 1 Exit-Gate Tracker

| # | Exit criterion (spec §9) | Target | Current | Verdict |
|---|---|---|---|---|
| 1 | Genuinely high-fit companies found via Channels A–D | ≥10–20 | 4 | **IN PROGRESS** — below target, one search completed |
| 2 | Share of those with an identified, verifiable POC | ≥50% | 0% (0 of 4) | **NOT MET** — Channel D not yet executed for any finding |

**Overall Phase 1 decision:** Phase 1 remains IN PROGRESS. One search (LLM evaluation × GitHub/Careers) is complete with real, evidenced findings, but volume (4 of 10–20 target) and POC identification (0 of required ≥50%) are both short of the exit gate. See §12 for the decision on how to proceed.

**Advancement rule (spec §9):** Phase 2 (`companies` schema) does not begin until this gate is met **and** Karthik explicitly confirms advancement after reviewing the exit-gate report. An idea being good is not grounds to skip ahead.

---

## 11. Change Log

| date | change |
|---|---|
| 2026-08-20 | Worksheet created — empty structure, operating instructions, frozen scope, exit-gate tracker. No findings recorded; no discovery performed by the agent. |
| 2026-08-20 | Search 001 logged: LLM evaluation × GitHub (+ Careers folded in). 4 qualified findings (Confident AI, LangWatch — Perfect; AI2, W&B — Good), 1 rejected (MedARC-AI). Channel D (POC) deferred — see §12 Decision Log. |

---

## 12. Decision Log

This section exists so a pause or pivot in the experiment is a recorded decision with reasoning, not a silent stall — consistent with the parent project's documented preference for explicit STOP-and-report over letting work quietly drift.

### D-001 — 2026-08-20: Pause manual Channel-A GitHub-repo browsing; defer Channel D for Search 001

**What happened:** After completing Search 001 (term: `LLM evaluation`, channel: GitHub, with Careers checked directly for all 4 kept findings), the searcher assessed the manual repo-by-repo browsing approach as high-effort relative to yield, and chose to pause this specific discovery method rather than continue immediately into Channel D (POC identification) or a second search.

**Evidence supporting the pause:**
- ~35–45 minutes of manual effort produced 4 qualified companies and 1 rejection — a real but modest yield for the time invested, before POC work (the most labor-intensive step) had even started.
- All 4 qualified companies returned the same negative signal on remote/India fit, suggesting this particular term may be saturated with US/Europe-centric results at the top of GitHub's relevance ranking — a pattern worth checking against a different term or channel before investing more manual hours in the same approach.

**What is NOT happening:** This is not a decision that the Company Radar hypothesis has failed, and it is not a rejection of the `LLM evaluation` term or the GitHub channel. It is a pause on the *specific manual workflow* (opening individual repos one at a time, reading READMEs, hunting for org/POC info by hand) that proved effortful for this one search.

**Options considered for what comes next (not yet decided):**
1. Resume with Channel D (POC) for the 4 existing findings before running any new search — completes Search 001 fully.
2. Switch to a different term (`Agent evaluation` or `RAG reliability`) on Channel A, to test whether the remote/India-fit pattern is term-specific.
3. Switch to a different channel for the same term — e.g., go straight to Channel B (ATS/careers, via Greenhouse/Lever/Ashby job board search rather than company-by-company browsing) which may be lower-effort than repo-hunting.
4. Pause Phase 1 discovery entirely for now and return to it later, prioritizing other active work (InfoBeans follow-through, direct applications, resume/interview prep).

**Decision:** Deferred to Karthik. No option has been selected as of this entry. The worksheet is left in a valid, resumable state (4 findings recorded, exit gate not met, coverage matrix shows exactly what has and hasn't been covered) so that whichever option is chosen later, there is no reconstruction work needed.

**Phase 1 status implication:** Phase 1 is not abandoned and not advanced — it is paused mid-search with real findings on record. Per spec §9, no phase advances without its exit criterion being met and explicit confirmation, so this pause has no effect on the roadmap other than leaving Phase 2 unauthorized, exactly as it already was.
