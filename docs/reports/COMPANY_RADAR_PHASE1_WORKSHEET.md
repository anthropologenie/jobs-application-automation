# Company Radar — Phase 1 Manual Discovery Worksheet

**Phase:** 1 — Manual Discovery Baseline
**Status:** OPEN — awaiting manual findings (no findings recorded yet)
**Owner / Searcher:** Karthik S R
**Agent role:** Recording, structuring, and evaluation only — the agent performs **no** discovery
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

*Auto-maintained by the agent as findings arrive. All zero until manual findings are supplied.*

| Metric | Value |
|---|---|
| Searches performed | 0 |
| Total findings recorded | 0 |
| Qualified high-fit companies | 0 |
| Companies with identified POC | 0 |
| Companies with **verified** POC | 0 |
| Verified-POC rate | n/a |
| Contactable leads | 0 |
| Weak matches / false positives | 0 |
| Novel vs. conventional platforms | 0 |
| Manual time invested | 0 min |

---

## 3. Search Log

One row per search executed. Zero-yield searches must still be logged.

| search_id | date | discovery_term | channel | query / surface actually used | results reviewed | findings kept | minutes | notes |
|---|---|---|---|---|---|---|---|---|
| *(empty — no searches recorded yet)* | | | | | | | | |

---

## 4. Findings Register

One row per company kept. Full detail goes in §5; this table is the at-a-glance index.

| id | company | discovery_term | channel | why_discovered | evidence (link) | current_ai_activity | relevant_opening | relevant_poc_name | relevant_poc_role | poc_contact_channel | poc_verified | contactable | initial_fit | novel_vs_conventional | status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| *(empty — no findings recorded yet)* | | | | | | | | | | | | | | | |

**Field values**

- `initial_fit`: `Perfect` / `Good` / `Moderate` / `Poor` — same scale as `opportunities.domain_match` (spec §8)
- `poc_verified`: `Yes` (identity confirmed via a second source, e.g. LinkedIn confirming a GitHub identity) / `No` / `unknown`
- `contactable`: `Yes` (a concrete, legitimate channel exists) / `No` / `unknown`
- `novel_vs_conventional`: `Yes` (would likely not surface via LinkedIn/Naukri/Indeed keyword search) / `No` / `unclear` — the core question the experiment is testing (spec §11)
- `status`: `Qualified` / `Weak match` / `Rejected` / `Needs more research`

---

## 5. Finding Detail Records

Copy the template per company. Do not fill in a field you cannot evidence — use `unknown`.

<details>
<summary><strong>Template — copy for each finding</strong></summary>

```
### F-00X — <Company Name>

- discovery_term:        <LLM evaluation | Agent evaluation | RAG reliability>
- channel:               <A GitHub | B Careers/ATS | C Eng blog | D POC verification>
- why_discovered:        <what in that channel surfaced them>
- evidence:              <specific URL: repo / commit / post / posting>
- current_ai_activity:   <what they are actually building>
- why_relevant:          <which §5.1 criteria they hit, and why>
- relevant_opening:      <title + link, or "none visible">
- relevant_poc_name:     <name or unknown>
- relevant_poc_role:     <role, mapped to §5.2 priority tier>
- poc_contact_channel:   <GitHub / company site / public email / community — verification channel>
- poc_verified:          <Yes | No | unknown> — <how it was verified>
- contactable:           <Yes | No | unknown>
- initial_fit:           <Perfect | Good | Moderate | Poor>
- novel_vs_conventional: <Yes | No | unclear> — <reasoning>
- criteria_check:        <which §5.1 boxes pass / fail>
- open_questions:        <what still needs checking>
- notes:                 <anything else worth keeping>
```

</details>

*(No finding records yet.)*

---

## 6. Rejected / Weak Matches

Recording rejections matters: false-positive rate is part of judging whether the ontology is precise enough to automate in Phase 3.

| id | company | discovery_term | channel | reason rejected | which criterion failed |
|---|---|---|---|---|---|
| *(empty)* | | | | | |

---

## 7. Coverage Matrix

Tracks which term × channel combinations have actually been searched, so the baseline isn't accidentally built from one channel.

| | A. GitHub | B. Careers / ATS | C. Eng blogs | D. POC verification |
|---|---|---|---|---|
| **LLM evaluation** | ☐ not searched | ☐ not searched | ☐ not searched | ☐ not searched |
| **Agent evaluation** | ☐ not searched | ☐ not searched | ☐ not searched | ☐ not searched |
| **RAG reliability** | ☐ not searched | ☐ not searched | ☐ not searched | ☐ not searched |

---

## 8. Ontology Observations

Free-form log of what the three frozen terms are actually doing — this is the evidence base for whether the ontology survives into Phase 3, or needs revision first. Record both directions: terms that pulled good companies, and terms that pulled noise.

| observation | supporting finding ids | implication for Phase 3 |
|---|---|---|
| *(empty)* | | |

---

## 9. Conventional-Platform Comparison Notes

For each qualified company, the judgement that matters is whether Funnel A would have surfaced it. Record the reasoning, not just a yes/no.

| company | would LinkedIn/Naukri/Indeed have surfaced it? | basis for that judgement |
|---|---|---|
| *(empty)* | | |

---

## 10. Phase 1 Exit-Gate Tracker

**Do not treat the existence of this worksheet as progress against the gate.** The gate is evaluated only against recorded, evidenced findings.

| # | Exit criterion (spec §9) | Target | Current | Verdict |
|---|---|---|---|---|
| 1 | Genuinely high-fit companies found via Channels A–D | ≥10–20 | 0 | **INCONCLUSIVE** |
| 2 | Share of those with an identified, verifiable POC | ≥50% | n/a | **INCONCLUSIVE** |

**Overall Phase 1 decision:** Phase 1 remains INCOMPLETE — insufficient evidence for the exit gate.

**Advancement rule (spec §9):** Phase 2 (`companies` schema) does not begin until this gate is met **and** Karthik explicitly confirms advancement after reviewing the exit-gate report. An idea being good is not grounds to skip ahead.

---

## 11. Change Log

| date | change |
|---|---|
| 2026-08-20 | Worksheet created — empty structure, operating instructions, frozen scope, exit-gate tracker. No findings recorded; no discovery performed by the agent. |
