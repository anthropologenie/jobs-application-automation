# COMPANY_RADAR_EXPERIMENT.md

**Status:** Phase 1 — Manual Discovery Baseline In Progress (Phase 0 accepted; worksheet open, no findings recorded yet)
**Owner:** Karthik S R
**Parent system:** `jobs-application-automation` (JobOps)
**Relationship to `opportunities` table:** Additive, non-destructive. This experiment introduces a new `companies` table representing pre-application intelligence. The existing `opportunities` table is untouched conceptually — it continues to represent actual job opportunities and applications, not candidate companies under research.

---

## 1. Why This Document Exists

This project's own operating history (`ai-quality-engineering`, `ENGINEERING_JOURNEY.md`) has already demonstrated that scope creep is a real, recurring risk, and that the corrective question is always **"does this serve the project's actual purpose?"** rather than **"is this good engineering?"**. This experiment applies that same discipline before any code is written.

The temptation with this idea is to build a full recruiting automation platform — discovery agents, scoring engines, outreach generators, a dashboard — in one pass. That is explicitly rejected here. This document exists to freeze the experiment's actual question, its success criteria, and a phased roadmap with hard exit gates, so that later work can be checked against a written decision instead of momentum.

---

## 2. North Star

> **Find high-fit AI companies and relevant people before they become visible through conventional job-board searches, then measure whether direct, evidence-based engagement produces better outcomes than conventional job-board applications.**

This is motivated by a specific, named problem: LinkedIn, Naukri, and Indeed are increasingly crowded and dominated by service/staffing-firm postings that don't match the target role profile (AI Quality Engineer / AI Evaluation Engineer / AI Test Automation Engineer / AI Governance / Data & AI Quality Engineer, remote-first, product companies). The hypothesis is that a company-first, evidence-based sourcing funnel surfaces genuinely relevant opportunities that keyword-based job-board search does not — specifically because the target role may not exist under a recognizable job title yet at many companies who nonetheless have the underlying need.

---

## 3. What This Is Not

Explicitly out of scope for the experiment itself (not forever — just not yet, and not without re-approval after Phase 1 results are in):

- Not a mass-application bot. The unit of work is a **relationship**, not a submitted application.
- Not a LinkedIn scraper. LinkedIn is used manually, as a verification/relationship channel only.
- Not an automated outreach/DM system on any channel (Slack, Discord, email, LinkedIn). All outbound messages are human-drafted-or-approved and human-sent throughout every phase, including later automated phases.
- Not a full multi-agent architecture on day one. Agents are a Phase 10 idea, contingent on every earlier phase already having proven its value.

---

## 4. The Experiment: Two Funnels Compared

**Funnel A — Conventional**
```
Job board → Apply → Wait
```

**Funnel B — Company Radar**
```
Company discovery → Research → POC identification →
Evidence-based outreach → Conversation → Application
```

A third, lighter-weight funnel is tracked for completeness but not actively built:

**Funnel C — Technical Community**
```
GitHub / Discord / Slack / technical community →
Genuine contribution or interaction → Relationship → Opportunity
```

The three current applications already in the tracker (Firmable, Welldoc, Dautom) serve as the Funnel A baseline for comparison — they were sourced conventionally, so their eventual response/conversion outcomes give a real reference point rather than an assumed one.

---

## 5. Target Definition

### 5.1 Target Company Characteristics

- Product company, startup, or AI-focused firm — not a staffing/service-based firm
- AI-native or AI-intensive product (the product itself involves LLMs, agents, RAG, or model-driven decisions — not just "uses AI internally somewhere")
- Remote-first, or hiring in India
- Demonstrable relevant engineering activity (a repo, a blog post, a job posting in an adjacent discipline)
- Evidence of a plausible latent need in one or more of:
  - AI Quality / AI Evaluation
  - LLM Testing / RAG Evaluation / Agent Evaluation
  - AI Data Quality
  - AI Reliability / AI Observability
  - AI Governance / AI Safety
  - AI Test Automation / AI Platform Quality

### 5.2 Target People (in priority order)

1. AI/ML Engineering Lead
2. AI Platform Lead
3. Engineering Manager
4. Head of Engineering / VP Engineering
5. CTO / Founder
6. Technical Recruiter
7. Talent Partner

---

## 6. Discovery Ontology (Phase 1 Search Terms)

Phase 1 deliberately restricts itself to **three** concepts rather than the full ontology, to keep the first pass small and reviewable:

```
LLM evaluation
Agent evaluation
RAG reliability
```

The full ontology (for later phases, not Phase 1) is recorded here so it isn't reconstructed from scratch later:

```
AI evaluation            AI agents               Training data
model evaluation         agent infrastructure    annotation
eval harness              agent orchestration     dataset quality
AI reliability             MCP                     data-centric AI
AI observability          multi-agent             human-in-the-loop
hallucination detection    agent observability     model monitoring
agent evaluation           agent testing           data validation
agent reliability          agent security
AI testing
model quality               RAG
responsible AI              retrieval
                             semantic search
                             vector database
                             embeddings
                             knowledge systems
                             enterprise search
                             grounded generation
```

---

## 7. Discovery Channels (Ranked, per Phase 1 Scope)

Phase 1 uses only Channels A–D, manually. Channels E onward are explicitly deferred to later phases.

| Channel | Phase 1 Use | Automation Level (later) |
|---|---|---|
| A. GitHub (repos, orgs, contributors) | Yes — manual search | High (Phase 3) |
| B. Company careers pages / ATS (Greenhouse, Lever, Ashby) | Yes — manual lookup | High (Phase 3) |
| C. Engineering blogs / technical activity | Yes — manual review | High (Phase 3) |
| D. POC identification + manual verification | Yes — manual, via GitHub/company site, verified via LinkedIn | Medium (Phase 5) |
| E. LinkedIn / Wellfound (as discovery, not verification) | No | Deferred indefinitely — verification-only role |
| F. Slack / Discord communities | No | Deferred — Phase 8, participation-based only, never scraping |
| G. Hacker News / Reddit | No | Deferred — Phase 3/8 |
| H. Conferences / speaker lists | No | Deferred — Phase 8 |

---

## 8. Data to Capture Per Company (Worksheet Schema)

This is the manual worksheet used in Phase 1, and the basis for the `companies` table introduced in Phase 2.

```
company
why_discovered            (which channel + search term surfaced it)
evidence                  (specific repo / blog post / job posting / commit — not a vague impression)
current_ai_activity       (what they are actually building)
relevant_opening          (if any — may be none; absence is not disqualifying)
relevant_poc_name
relevant_poc_role
poc_contact_channel       (GitHub, LinkedIn, company email, community — verification channel, not scrape source)
initial_fit               (Perfect / Good / Moderate / Poor — same scale as opportunities.domain_match, for consistency)
```

---

## 9. Phased Roadmap (Frozen — Exit Criteria Required to Advance)

| Phase | Objective | Automation | Exit Gate |
|---|---|---|---|
| 0 | Define experiment (this document) | None | This document reviewed and accepted |
| 1 | Manual discovery baseline | None | ≥10–20 genuinely high-fit companies found via Channels A–D; ≥50% have an identified, verifiable POC |
| 2 | Build `companies` intelligence schema | Low | Schema reviewed; Phase 1 worksheet data migrated in |
| 3 | Automate GitHub + ATS discovery | Medium | Automated discovery reproduces or exceeds Phase 1's manual hit rate |
| 4 | AI company qualification (LLM-scored, evidence-backed) | Medium | Every score traceable to cited evidence, no un-sourced scores |
| 5 | POC identification at scale | Medium | Verified-POC rate holds at or above Phase 1's 50% baseline |
| 6 | Latent opportunity inference (no job posting required) | High | Inferred opportunities validated against at least a few real outcomes before trusted further |
| 7 | Evidence-based outreach drafting | Human-in-loop, always | Every message is human-approved and human-sent — this gate never relaxes |
| 8 | Community/network layer (GitHub, Discord, Slack, conferences) | Mostly human | Participation-first; no scraping or automated DMs introduced at any point |
| 9 | Funnel measurement (Radar vs. conventional) | High | Enough volume in both funnels to compare hours-per-qualified-company, hours-per-conversation, hours-per-interview |
| 10 | Agentic radar (`skills/discover-github/`, `skills/qualify-company/`, etc.) | High | Only attempted once Phases 1–9 have independently proven value |

**Hard rule carried forward from this project's existing governance discipline:** an idea being good is not sufficient grounds to skip ahead. Each phase requires its own exit criterion to be met before the next phase begins. No phase is started because it is "obviously the next step" — it is started because the prior phase's data justified it.

---

## 10. Explicitly Deferred (Not Rejected — Just Not Yet)

- LinkedIn scraping
- Mass Easy Apply automation
- Automated LinkedIn/Slack/Discord messaging
- Discord/Slack harvesting or passive monitoring for lead generation
- Crawling hundreds of companies before Phase 1 proves the signal
- Full multi-agent architecture
- Complex dashboard / vector database / RAG over companies
- Fully autonomous applications

These are recorded here specifically so the reasoning isn't reconstructed from scratch if revisited later — consistent with how `Engineering_Lessons_Register.md` handles deferred-but-not-forgotten items in the sibling `ai-quality-engineering` repository.

---

## 11. Success Metrics (Tracked from Phase 9 Onward, Defined Now)

**Discovery**
- Companies discovered
- Companies qualified (passed fit screening)
- Companies novel relative to LinkedIn/Naukri/Indeed search (i.e., would not have surfaced there)

**Contact**
- POCs identified
- Outreach sent
- Response rate

**Conversion**
- Conversations started
- Referrals obtained
- Applications generated
- Interviews reached
- Offers received

**Efficiency**
- Hours per qualified company
- Hours per conversation
- Hours per interview

**The single metric that ultimately decides whether this experiment succeeded:** which funnel (A, B, or C) produces the most interview-quality opportunities per hour invested.

---

## 12. Relationship to Existing JobOps Architecture

- `opportunities` table: unchanged. Represents actual applications and their pipeline status (Lead → Applied → ... → Accepted/Rejected/Declined/Ghosted).
- `companies` table (new, Phase 2): pre-application intelligence. A company only gets linked to an `opportunities` row once it actually converts into a real application (via a `linked_opportunity_id` foreign key).
- This mirrors the existing separation already established between JobOps (production data source) and the `ai-quality-engineering` evaluation repository (downstream consumer, read-only, no writes back) — the same read-only, non-destructive relationship pattern is reused here between `companies` and `opportunities`.

---

## 13. Immediate Next Step

**Phase 1 only.** No code. Execute the manual discovery worksheet (Section 8) against the three Phase 1 search terms (Section 6) across Channels A–D (Section 7), and review the results against the Phase 1 exit gate (Section 9) before writing any automation or touching Phase 2's schema work.
