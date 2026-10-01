# OWNER_RULINGS_LOG.md

**Type:** Repository Owner ruling record
**Repository:** `~/projects/jobs-application-automation` (JobOps)
**Opened:** 2026-08-28
**HEAD at opening:** `bf22ca1` — *docs(governance): register Career Strategy as authoritative career policy*
**Purpose:** close the five items that `JOBOPS_SCALING_EXECUTION_PLAN.md` §16 identifies as blocking all P0 work.

> **Rule for this file.** A `RULING:` field is filled **only** with what the Repository Owner explicitly states. No agent may populate a `RULING:` field with an inference, a recommendation, a default, or a "most likely" answer. **An empty `RULING:` field is the correct state until the Owner rules.**

**Status:** 7 of 7 ruled — log complete. (5 items closed 2026-08-28; `OQ-01` and `OQ-02` closed 2026-08-29.)

| id | Item | Status |
|---|---|---|
| OR-03a | Salary veto threshold | ☑ **RULED** 2026-08-28 |
| OR-03b | Unknown-salary treatment | ☑ **RULED** 2026-08-28 |
| OR-04 | Staffing / services firm engagement | ☑ **RULED** 2026-08-28 |
| OR-08 | LinkedIn ingestion scope | ☑ **RULED** 2026-08-28 |
| CONFLICT-2 | Migration authority + migration 005 | ☑ **RULED** 2026-08-28 |
| OQ-01 | Straddling salary range across ₹20 LPA | ☑ **RULED** 2026-08-29 |
| OQ-02 | Non-INR / non-annual compensation | ☑ **RULED** 2026-08-29 |

---

## 1. OR-03a — Salary veto threshold: ₹18L or ₹20L?

### Question

**What is the compensation threshold below which a posting is vetoed by the policy gate — ₹18 LPA or ₹20 LPA?**

The ₹18–20 LPA band is currently unclassified: it is below the stated target band but above the stated exception line, and no repository artifact says how a posting in that band should be treated.

### The textual conflict

**`docs/Career_Strategy_and_Search_Preferences.md` §4, "Compensation" — states two different figures:**

> - Target: ₹20–30+ LPA
> - Last drawn: ₹16 LPA (Ascendion, through 14-Aug-2026)
> - Below ₹18 LPA: only if role is otherwise exceptional (e.g., strong AI governance alignment, notable product company)

The target band opens at **₹20 LPA**. The exception clause is written at **₹18 LPA**. Neither states which is the gate threshold, and the band between them has no stated rule.

**`data/resume_config.json` — the only executable artifact — encodes ₹18 LPA:**

```json
"min_salary_inr": 1800000
"preferred_salary_range": { "min_inr": 1800000, "max_inr": 4000000 }
```

**`JOBOPS_SCALING_EXECUTION_PLAN.md` §3.1 OR-03 records a third position** — the proposed target state supplied at planning time stated *"Current target floor: ₹20 LPA for Indian permanent/stable opportunities"*, which the plan flagged as disagreeing with the career document's ₹18 LPA exception line.

### RULING:

RULING: ₹20 LPA is the compensation threshold below which a posting is vetoed by the policy gate. ₹20–30+ LPA is the target band. This supersedes the ₹18L figure in `data/resume_config.json`, which is stale configuration predating the current career strategy.

*Ruled 2026-08-28 by Repository Owner. Field closed.*

---

## 2. OR-03b — Unknown-salary treatment: UNKNOWN or FAIL?

### Question

**When a posting states no salary at all, does the gate emit `UNKNOWN` (candidate is queued, surfaced to the human, never auto-shortlisted) or `FAIL` (candidate is excluded)?**

This choice largely determines P0 queue volume, because most Indian postings state no compensation.

### The textual conflict

**`docs/Career_Strategy_and_Search_Preferences.md` §4 is silent on unknown salary.** It states a target band and an exception line (quoted in OR-03a above) but contains no rule for a posting that states no compensation figure. The absence is the conflict: the gate cannot be built without a rule here, and inventing one would be exactly the inference this log exists to prevent.

**The current implementation has no salary handling at all to fall back on.** `data/resume_config.json` `scoring_weights` contains five dimensions — `skills_match`, `experience_match`, `domain_match`, `location_match`, `red_flags` — and **no salary dimension**. `scrapers/simple_scorer.py` never reads `min_salary_inr`. `scraped_jobs.salary_range` is nullable free-text `TEXT` and is never parsed or filtered.

**`JOBOPS_SCALING_CAPABILITY_INVENTORY.md` finding F4** established that the existing scorer treats absent data as favourable — `calculate_experience_score()` returns `100` for an empty requirement string and `calculate_location_score()` returns `50` for an empty location — so there is no safe existing default to inherit.

**`JOBOPS_SCALING_EXECUTION_PLAN.md` §3.1 OR-03(b)** records the proposed target state as *"Salary UNKNOWN must never be treated as salary PASS"* — which rules out one option but does not choose between `UNKNOWN` and `FAIL`.

### RULING:

RULING: A) UNKNOWN — keep them in the queue and surface them for human review, but never treat UNKNOWN as satisfying the ₹20 LPA floor and never auto-shortlist UNKNOWN above a confirmed qualifying salary; and i will review it as it is escalated for human review

*Ruled 2026-08-28 by Repository Owner, quoted verbatim as stated. Field closed.*

---

## 3. OR-04 — Staffing / services firm: FAIL, or low-scoring PASS?

### Question

**Is a full-time, permanent role at a services / staffing / body-shopping firm a hard `FAIL` at the pre-scoring gate, or a `PASS` that simply scores low?**

The career document's hard-exclusion language appears **only inside the contract clause**; its full-time guidance uses soft ranking language.

### The textual conflict

**`docs/Career_Strategy_and_Search_Preferences.md` §4, "Employment Type" — hard exclusion, but scoped to contract engagements:**

> - **Full-time employment preferred by default.**
> - **Contract acceptable if:** minimum 6-month duration, **and** the engaging company is a **product company, not a service-based/staffing/body-shopping firm.** Short-term or service-based contract placements are not aligned with current goals.

**`docs/Career_Strategy_and_Search_Preferences.md` §4, "Company Type" — soft ranking language for the same firms:**

> - Preferred: Product companies, AI companies, cloud data companies, SaaS, analytics platforms
> - Acceptable: Large enterprises (direct product teams, not staffing arrangements), engineering consulting with a genuine product focus
> - Lower priority: Generic IT services, staff augmentation, maintenance-only projects

*"Lower priority"* is ranking language, not exclusion language.

**`docs/Career_Strategy_and_Search_Preferences.md` §4, "Work Mode" — refers to engagement type as an already-established hard veto:**

> Remote is not a weighted trade-off against compensation or role quality — it is a boundary condition on the search itself, **on the same footing as the engagement-type exclusion below.**

This sentence treats "the engagement-type exclusion" as a settled hard constraint of the same class as the remote requirement — but the only exclusion written below it is the contract-scoped one.

**`data/resume_config.json` encodes it as weighted penalties, not exclusion:** `red_flags.consultancy_signals` assigns `Client Placement: -20`, `Third Party: -20`, `Bench Sales: -20`, `Body Shopping: -20`, `Staff Augmentation: -18`. Per inventory finding **F3**, these are capped at a combined **−5.0 points on a 0–100 scale**. Separately, `filters.company_size_preference.avoid` lists `["Consulting", "Outsourcing", "Body Shopping"]` — and is **read by no code**.

### RULING:

RULING: A posting is eligible for scoring if it is remote and meets the ₹20 LPA compensation threshold. Hybrid and on-site postings are vetoed before scoring, on the same footing as compensation. Services/staffing/company type is NOT a separate hard veto for this ruling — it does not exclude a posting pre-scoring. It may influence scoring (Preference Fit / Opportunity Quality) downstream of the gate. Therefore, a remote role at a services/staffing company above ₹20 LPA remains eligible for scoring, same as a remote role at a product company above ₹20 LPA.

*Ruled 2026-08-28 by Repository Owner, quoted verbatim as stated. Field closed. See §Flagged Inconsistencies (F-01).*

---

## 4. OR-08 — Does the LinkedIn deferral bar ingestion in JobOps generally?

### Question

**Does `COMPANY_RADAR_EXPERIMENT.md` §7's LinkedIn deferral bar LinkedIn ingestion in JobOps as a whole, or does it scope only the Company Radar experiment?**

This selects P0's ingestion path: Path A (LinkedIn via the `linkedin-search` CLI) or Path B (RemoteOK fallback), per `JOBOPS_SCALING_EXECUTION_PLAN.md` §4.2.

### The textual conflict

**`docs/COMPANY_RADAR_EXPERIMENT.md` §7, Discovery Channels table:**

> | E. LinkedIn / Wellfound (as discovery, not verification) | No | Deferred indefinitely — verification-only role |

**`docs/COMPANY_RADAR_EXPERIMENT.md` §3, "What This Is Not":**

> - Not a LinkedIn scraper. LinkedIn is used manually, as a verification/relationship channel only.

**`docs/COMPANY_RADAR_EXPERIMENT.md` §10, "Explicitly Deferred (Not Rejected — Just Not Yet)"** lists *"LinkedIn scraping"* as the first item.

**The scoping ambiguity:** §1 states the document's own subject is the experiment — *"This document exists to freeze the experiment's actual question, its success criteria, and a phased roadmap with hard exit gates"* — and §7's table is headed *"Discovery Channels (Ranked, per Phase 1 Scope)"*, with a *"Phase 1 Use"* column. Whether a Phase-1-scoped channel table constrains JobOps ingestion outside the experiment is not stated either way.

**Counter-evidence in the live data:** LinkedIn is already the single largest discovery channel in the system of record. Of 22 rows in `opportunities`, **8 carry `source='LinkedIn'`**, including 5 of the 10 applications submitted on 2026-08-19 and 2026-08-20 — all entered manually.

**A third-party constraint that applies regardless of the ruling:** `ai-job-search/.agents/skills/linkedin-search/SKILL.md` carries its own notice —

> ⚠️ Personal use only — This uses LinkedIn's public job pages; automated access is against LinkedIn's Terms of Service, so **keep volume low and don't use it commercially or for bulk data collection.**

### RULING:

RULING: Radar-scoped only. COMPANY_RADAR_EXPERIMENT.md §7's LinkedIn deferral constrains the Company Radar experiment specifically, not JobOps ingestion generally. The document's own §1 states that its purpose is to freeze that experiment's rules, and §7's table is explicitly headed "per Phase 1 Scope." P0 may therefore use LinkedIn ingestion via the linkedin-search CLI, while honoring the CLI's stated personal-use-only and low-volume restriction as an operational constraint.

**Scope boundary stated by the Repository Owner alongside this ruling, quoted verbatim:** “Do not broaden it into permission for unrestricted LinkedIn scraping, bulk collection, commercial use, or any activity contrary to the CLI's stated restrictions.”

**Owner restatement of the same ruling, 2026-08-28, quoted verbatim as supplied at P0-specification time.** Substantively identical to the record above; retained because it names the ingestion path explicitly. Neither statement supersedes the other; both are the same ruling.

> RULING: Radar-scoped only. COMPANY_RADAR_EXPERIMENT.md §7's LinkedIn deferral constrains the Company Radar experiment specifically, not JobOps ingestion generally — the document's own §1 states its purpose is to freeze that experiment's rules, and §7's table is explicitly headed "per Phase 1 Scope." P0 takes Path A: LinkedIn ingestion via the linkedin-search CLI, honoring the CLI's own "personal use only, keep volume low" notice as a designed rate limit rather than a reason to avoid the source entirely.

*Ruled 2026-08-28 by Repository Owner, quoted verbatim as stated. Field closed.*

---

## 5. CONFLICT-2 — Migration authority, and is applying migration 005 authorized now?

### Question

**(a) Who may apply a database migration to `data/jobs-tracker.db`, and by what procedure?**
**(b) Is applying `migrations/005_add_scraped_job_import.sql` authorized now, to repair the broken `scraped_jobs` → `opportunities` bridge?**
**(c) Is a migration runner plus a history table (`JS-24`) a P0 prerequisite, or P0 scope?**

### The textual conflict

**`docs/reports/migration-architecural-audit.md` §A, "Current architecture":**

> There is no migration system. There is a directory named `migrations/` containing six SQL files with no runner, no ordering enforcement, no history table, and no application-side invocation.

> Migration history mechanism: none. `PRAGMA user_version = 0`, `PRAGMA application_id = 0`, and no `schema_migrations`-style table exists in `sqlite_master`. **There is no way, from the database alone, to determine which migrations have been applied.**

**The same audit, §D.2, records the specific breakage this ruling would repair:**

> | column `opportunities.scraped_job_id` | 005 | **ACTIVE PRODUCTION BREAKAGE.** |

> `api-server.py:508-553` implements `_handle_import_scraped_job`; line 520 executes `SELECT id FROM opportunities WHERE scraped_job_id = ?`, and line 535 inserts into that column. Replaying that query against the live database:
> `Error: in prepare, no such column: scraped_job_id`
> The scraped-job import endpoint — the entire deliverable of commit `6e655c1` — cannot execute.

**The migration in question is four lines of comment and one non-idempotent statement.** `migrations/005_add_scraped_job_import.sql`, in full:

> ```sql
> -- Migration 005: FEATURE-001 — Scraped Job Import provenance column
> -- Renumbered from the prepared 006 -> 005: live migrations/ only has
> -- 002, 003, 004 (no 001, no 005) so 005 is the actual next free number.
> --
> -- Additive only — nullable, no FK constraint, no data touched.
>
> ALTER TABLE opportunities ADD COLUMN scraped_job_id INTEGER;
> ```

The audit classifies it: *"Idempotent: ❌ no — bare ALTER TABLE ADD COLUMN"* — it will error rather than no-op if run twice.

**Why the authority question is genuinely open:** the audit records **five uncoordinated channels** by which schema has historically reached this database — manual `sqlite3 db < file.sql`, a one-off shell runner used for migration 004 only, embedded Python DDL at runtime in `scrapers/remoteok_integration.py`, direct binary edits to the committed `.db` file, and *"nothing at all (declared, never wired)"*. No artifact states who is permitted to use which.

**Related open items this ruling touches:** migration `004_add_parliament_decisions.sql` is also unapplied (`parliament_decisions` does not exist in the live database); and `data/jobs-tracker.db` is itself tracked in git (`CONFLICT-3`), which the audit calls *"a second, binary 'source of truth' that merges catastrophically."*

### RULING:

RULING:

(a) Database migrations may be applied only by the Repository Owner or by an explicitly authorized agent session acting on the Repository Owner's written ruling. No migration may be applied implicitly by application runtime code, n8n, scrapers, or other automation. Before application, the migration must be identified by filename and reviewed for scope and destructive/additive behavior.

(b) migrations/005_add_scraped_job_import.sql is authorized now as a scoped one-off migration because the existing scraped-job import endpoint is currently broken without the scraped_job_id column. Its application must be verified after execution, and no other unapplied migration is authorized by this ruling.

(c) A migration runner and migration history table (JS-24) are P0 scope, but they are not a prerequisite for applying migration 005. They should be designed and implemented as part of P0 so that subsequent migrations have an explicit, auditable application path. Migration 004 remains unapplied and unauthorized until separately reviewed.

**Owner restatement of the same ruling, 2026-08-28, quoted verbatim as supplied at P0-specification time.** Retained alongside the (a)/(b)/(c) record above rather than replacing it; the two are read together.

> RULING:
>
> The Repository Owner is the authority for database migrations. A migration must be explicitly reviewed and authorized before it is applied; there is no standing permission for autonomous or automatic migration execution.
>
> Migration 005, migrations/005_add_scraped_job_import.sql, is authorized as a scoped one-time migration to repair the broken scraped_jobs → opportunities bridge.
>
> The migration runner and migration history mechanism (JS-24) should be treated as a P0 prerequisite / governance mechanism for future migrations rather than allowing future migrations to continue through ad-hoc execution channels.

**Reconciliation note (recorded, not resolved by inference).** The restatement's JS-24 clause is qualified *"for future migrations"*, which is consistent with clause (c) above: JS-24 governs migrations after 005, and is not a precondition for 005 itself. The restatement is silent on migration 004; clause (c)'s sentence — *"Migration 004 remains unapplied and unauthorized until separately reviewed"* — therefore stands unmodified, since silence does not authorize.

*Ruled 2026-08-28 by Repository Owner, quoted verbatim as stated. Field closed. Migration 005 is AUTHORIZED but NOT YET APPLIED as of this log entry; migration 004 remains unapplied and unauthorized.*

---

## 6. OQ-01 — Straddling salary range across the ₹20 LPA threshold

### Question

**A posting states a salary range whose minimum is below ₹20 LPA and whose maximum is at or above ₹20 LPA — for example `₹18–24 LPA`. Does the gate emit `PASS` (on the maximum), `FAIL` (on the minimum), or `UNKNOWN`?**

### Why it was open

**`P0_IMPLEMENTATION_SPEC.md` §3.3** specified the straddling row as `UNKNOWN` / `COMP-UNKNOWN-RANGE-STRADDLES`, but flagged it explicitly as **derived, not ruled**:

> **⚠ One derived rule requires Owner confirmation.** The straddling-range row (`COMP-UNKNOWN-RANGE-STRADDLES`) is **derived** from OR-03b's principle that insufficient evidence yields UNKNOWN rather than favourable treatment. It is **not independently ruled.** A stated range of "₹18–24 LPA" is neither confirmed-compliant nor confirmed-non-compliant. Specifying it as UNKNOWN avoids both silently passing a possibly-sub-floor role and silently vetoing a possibly-qualifying one — but the alternative readings (take the minimum → FAIL; take the maximum → PASS) are equally constructible from the ruling text.

**OR-03a** sets the threshold at ₹20 LPA but says nothing about ranges. **OR-03b** rules only the *no stated salary* case. A range is neither: it is stated evidence that is insufficient to confirm compliance. Three readings were equally constructible from the existing rulings, so the ruleset could not be authored without an Owner decision.

**`P0_IMPLEMENTATION_SPEC.md` §18** carried it as `OQ-01`, *"OPEN — needs Owner confirmation"*, blocking the ruleset artifact (task 1).

### RULING:

RULING (OQ-01):
A stated salary range that straddles the ₹20 LPA threshold — where the
minimum is below ₹20 LPA and the maximum is at or above ₹20 LPA — is treated
as UNKNOWN for the policy gate.

It must:
- remain in the funnel;
- be surfaced for human review;
- NOT be treated as satisfying the ₹20 LPA floor;
- NOT be auto-shortlisted above a posting with confirmed qualifying
  compensation;
- NOT be converted into PASS merely because the maximum reaches ₹20 LPA;
- NOT be converted into FAIL merely because the minimum is below ₹20 LPA.

The purpose is to preserve potentially viable opportunities without allowing
the system to represent uncertain compensation as confirmed qualification.

*Ruled 2026-08-29 by Repository Owner, quoted verbatim as stated. Field closed. Confirms the derived rule in `P0_IMPLEMENTATION_SPEC.md` §3.3; reason code `COMP-UNKNOWN-RANGE-STRADDLES` is now ruled rather than derived.*

---

## 7. OQ-02 — Non-INR compensation

### Question

**A posting states compensation in a currency other than INR, or in a non-annual unit. How is it compared against the ₹20 LPA threshold?**

### Why it was open

**`P0_IMPLEMENTATION_SPEC.md` §4.2** recorded that no conversion basis and no non-INR threshold exists anywhere in the repository:

> **Non-INR compensation.** The career doc §4 states the ₹20–30+ LPA target for Indian roles; the strategic objective refers to *"equivalent appropriate USD compensation for international opportunities"* — but **no conversion basis or USD threshold is ruled**. P0 therefore records non-INR compensation as normalized evidence and emits `UNKNOWN` with reason `COMP-UNKNOWN-NO-INR-BASIS`, escalating to human review. **Open item `OQ-02` (§18).**

The same section already forbids the failure mode this ruling guards against — `INFERRED` compensation is classed **PROHIBITED**, and *"A figure whose currency or period cannot be determined is `UNKNOWN`, not a guess."*

**Verified repository state at ruling time:** no exchange-rate source, provider, cadence, or rate value exists anywhere in the repository. `grep -rniE "exchange[ _-]?rate|fx[ _-]rate|usd.?inr|inr.?usd"` across all `.md`, `.json`, `.py`, `.yml` and `.yaml` files returns **no match**. `docs/Career_Strategy_and_Search_Preferences.md` §4 states the target band in INR only.

### RULING:

RULING (OQ-02):
Non-INR compensation must not be silently compared against the ₹20 LPA
threshold using an undocumented conversion.

The policy ruleset must represent:
- currency;
- compensation period/unit;
- source/evidence;
- conversion basis;
- conversion date or validity period;
- resulting INR-equivalent value;
- confidence/status of the conversion.

For annual compensation stated in a foreign currency, the ruleset may convert
to INR using a versioned exchange-rate source/basis explicitly recorded in the
ruleset artifact.

The conversion mechanism must be deterministic and auditable.

If the posting provides only an hourly, daily, monthly, or otherwise
non-annual figure and the annual equivalent cannot be established reliably,
the salary determination is UNKNOWN and is escalated for human review.

Do not invent compensation, annualize using hidden assumptions, or silently
use an arbitrary exchange rate.

If the repository already specifies an approved exchange-rate source and
cadence, use that source. If it does not, create the ruleset with the
conversion-source field explicitly marked as requiring configuration rather
than inventing a provider or rate.

**Application of the final clause, recorded not inferred.** The repository specifies **no** approved exchange-rate source or cadence (verified above). Accordingly the ruleset artifact carries the conversion-source field explicitly marked as requiring configuration, and no provider or rate is invented. Until that field is configured by a separate Owner-authorized action, non-INR compensation resolves to `UNKNOWN` with reason `COMP-UNKNOWN-NO-INR-BASIS`, per `P0_IMPLEMENTATION_SPEC.md` §4.2.

*Ruled 2026-08-29 by Repository Owner, quoted verbatim as stated. Field closed.*

---

## Provenance

| Source | Used for |
|---|---|
| `docs/Career_Strategy_and_Search_Preferences.md` §4 | OR-03a, OR-03b, OR-04 |
| `docs/COMPANY_RADAR_EXPERIMENT.md` §1, §3, §7, §10 | OR-08 |
| `docs/reports/migration-architecural-audit.md` §A, §D.2 | CONFLICT-2 |
| `migrations/005_add_scraped_job_import.sql` | CONFLICT-2 |
| `data/resume_config.json` | OR-03a, OR-03b, OR-04 |
| `data/jobs-tracker.db` (`opportunities.source` distribution) | OR-08 counter-evidence |
| `ai-job-search/.agents/skills/linkedin-search/SKILL.md` | OR-08 third-party constraint |
| `JOBOPS_SCALING_CAPABILITY_INVENTORY.md` findings F2, F3, F4 | OR-03b, OR-04, CONFLICT-2 |
| `JOBOPS_SCALING_EXECUTION_PLAN.md` §3.1, §3.2, §4.2, §16 | All five items |
| `P0_IMPLEMENTATION_SPEC.md` §3.3, §4.2, §18 | OQ-01, OQ-02 |

---

## Flagged Inconsistencies — for future document edit, NOT resolved here

Recorded so a divergence between an Owner ruling and an authoritative document is visible rather than silently absorbed. **No entry here declares which side governs.** Resolving one requires an explicit Repository Owner decision and, where applicable, an edit to the authoritative document.

### F-01 — Career Strategy §4 "Work Mode" phrasing vs. ruling OR-04

**The document text**, `docs/Career_Strategy_and_Search_Preferences.md` §4, "Work Mode":

> Remote is not a weighted trade-off against compensation or role quality — it is a boundary condition on the search itself, **on the same footing as the engagement-type exclusion below.**

This phrasing presents an *engagement-type exclusion* as an already-established pre-scoring hard veto of the same class as the remote requirement.

**The ruling**, OR-04 (2026-08-28), states that *"Services/staffing/company type is NOT a separate hard veto for this ruling — it does not exclude a posting pre-scoring."*

**The inconsistency:** as written, the document's cross-reference implies a pre-scoring engagement-type veto that OR-04 does not establish. **Flagged only.** This log does not choose between them, does not amend the career document, and does not infer a veto that OR-04 did not state.

**Disposition:** open — awaiting a Repository Owner decision on whether the career document's §4 Work Mode phrasing is to be edited to match OR-04, or whether the ruling is to be revisited.


---

**STATUS: COMPLETE — 7 of 7 ruled. The five items that `JOBOPS_SCALING_EXECUTION_PLAN.md` §16 identified as blocking all P0 work were closed 2026-08-28. The two open questions that `P0_IMPLEMENTATION_SPEC.md` §18 identified as blocking the policy ruleset artifact (task 1) — `OQ-01` and `OQ-02` — were closed 2026-08-29. No gate implementation, scoring implementation, ingestion implementation, database migration, or configuration change was performed in the course of recording these rulings.**

---
---

# Addendum A — JobOps v2 Phase A owner policy (appended 2026-09-29)

**Append-only.** Nothing above this line has been edited. Rulings OR-03a, OR-03b, OR-04, OR-08, CONFLICT-2, OQ-01, OQ-02 and flagged inconsistency F-01 stay in the record exactly as written. Where a ruling below supersedes one of them, the earlier ruling remains historical evidence of what governed jobops-policy@0.1.0. Verdicts written under 0.1.0 are never rewritten.

**Source of the rulings below.** The owner-supplied *"JOBOPS V2 — PHASE A"* specification, 2026-09-29. Its §36 states that all rules explicitly stated in its §§4–23 are owner-confirmed, and that five recommendations (R1–R5) are **not** confirmed. The RULING fields below restate the specification's own wording. The unconfirmed items (OR-26 … OR-30) have **empty RULING fields**, as this file's rule requires.

**Machine-readable draft:** `docs/architecture/drafts/jobops-policy-0.2.0.draft.json` (INACTIVE). **Spec:** `docs/architecture/JOBOPS_V2_OWNER_POLICY_SPEC.md`. **Open questions:** `docs/architecture/JOBOPS_V2_OPEN_ITEMS.md`.

| id | Item | Supersedes | Status |
|---|---|---|---|
| OR-11 | Current candidate profile | Career doc §2 narrative; `resume_config.json` profile; prompts | ☑ RULED 2026-09-29 |
| OR-12 | Target role family and title tiers | Career doc §4 buckets; LinkedIn query seeds | ☑ RULED 2026-09-29 |
| OR-13 | Separation of eligibility / relevance / preference / newness / review; AI Quality vs traditional QA | OR-05 residual framing; `simple_scorer.py` composite | ☑ RULED 2026-09-29 |
| OR-14 | Global scope = remote-from-India + Bengaluru hybrid; remote eligibility | v0.1 WM-R1; Career doc §4 Work Mode | ☑ RULED 2026-09-29 |
| OR-15 | Bengaluru hybrid / onsite rules and aliases | v0.1 WM-R2, WM-R3; OR-04 hybrid/on-site veto clause | ☑ RULED 2026-09-29 |
| OR-16 | Time zone is flag-only | — | ☑ RULED 2026-09-29 |
| OR-17 | Language | — | ☑ RULED 2026-09-29 |
| OR-18 | Compensation floor, bands, basis and verdicts | OR-03a (₹20L); OQ-01 anchor; Career doc §4 Compensation | ☑ RULED 2026-09-29 (except OR-27) |
| OR-19 | Employment type | Career doc §4 Employment Type; OR-07 (open) | ☑ RULED 2026-09-29 |
| OR-20 | Staffing, placement, contractor and employer type | OR-04 staffing/company-type clause; F-01 | ☑ RULED 2026-09-29 (except OR-26) |
| OR-21 | Experience and seniority are fit signals | `resume_config.json` 7 years / 5–10 range | ☑ RULED 2026-09-29 |
| OR-22 | Queue lanes and philosophy | `review/jobops-review-0.1.0.json` lanes | ☑ RULED 2026-09-29 (except OR-28, OR-29) |
| OR-23 | Source strategy | — (OR-08 unchanged) | ☑ RULED 2026-09-29 |
| OR-24 | Newness, canonical identity, evaluation replay (F4) | — | ☑ RULED 2026-09-29 |
| OR-25 | Supersession of the 2026-09-28 preferences used by the 29-Sep audit | 2026-09-28 preferences where they differ | ☑ RULED 2026-09-29 (confirmation of scope: OI-025) |
| OR-26 | R1 — Permanent EOR | — | ☐ OPEN |
| OR-27 | R2 — Foreign compensation conversion | OQ-02 (only if ruled) | ☐ OPEN |
| OR-28 | R3 — Daily REVIEW cap | — | ☐ OPEN |
| OR-29 | R4 — REVIEW overflow to PARKED | — | ☐ OPEN |
| OR-30 | R5 — SQLite migration runner and DB out of Git | CONFLICT-3 (open) | ☐ OPEN |

---

## 8. OR-11 — Current candidate profile

**Supersedes:** `docs/Career_Strategy_and_Search_Preferences.md` §2 narrative and "seven years"; `data/resume_config.json` `profile` (7 years, "QA Lead / Data QA Engineer"); `prompts/job_analysis.txt` and `prompts/email_generation.txt` candidate profile; the compensation anchor in Career doc §4 ("Last drawn").

### RULING:

Relevant AI industry experience is approximately **3 years**, at Bosch, Happiest Minds and Ascendion. The old "QA Lead / ETL / Data Warehouse / 7 years" profile is historical and must not be used for role search, experience matching, relevance scoring, title matching, salary reasoning or job ranking. JobOps must not encode the old 7-year figure as the current profile, and must not anchor salary decisions to the old compensation figure.

*Recorded 2026-09-29 from the owner's Phase A specification §4. Field closed.*

---

## 9. OR-12 — Target role family and relevance tiers

**Supersedes:** Career doc §4 "Target Search Buckets"; `ingestion/linkedin-ingestion-0.1.0.json` `query_seeds.buckets` (the config file itself is unchanged until an implementation phase; see OI-031); `data/resume_config.json` `job_title_keywords`.

### RULING:

Tier 1 (direct target): AI Engineer, Applied AI Engineer, Agentic AI Engineer, Generative AI Engineer, AI/LLM Engineer, RAG Engineer, Retrieval Engineer, AI Evaluation Engineer, LLM Evaluation Engineer, AI Quality Engineer, AI Reliability Engineer, AI Testing Engineer, GenAI Quality Engineer, AI Platform Engineer, GenAI Backend Engineer, AI Solutions Engineer, AI Automation Engineer, AI-SDLC / Developer Productivity Engineer, LLMOps / AI Operations Engineer, AI Governance / AI Reliability Engineer.

Tier 2 (adjacent AI engineering), for example: ML / Machine Learning Engineer, NLP Engineer, MLOps Engineer, ML Platform Engineer, LLM Application Engineer, AI Application Engineer, AI Software Engineer, AI Backend Engineer, AI Integration Engineer, AI Product Engineer, AI Developer, Intelligent Automation Engineer, Data/AI Engineer, ML Infrastructure Engineer, and AI Solutions Architect only when genuinely hands-on.

Tier 3: any other title whose JD contains substantial real AI-engineering work.

The title is a weak prior; the JD is the primary evidence. Do not reject a job because its title does not match exactly. Do not automatically reject Tier 2 or Tier 3.

*Recorded 2026-09-29 from Phase A §5–§6. Field closed.*

---

## 10. OR-13 — Separation of concerns; relevance; AI Quality vs traditional QA

**Supersedes:** the framing of OR-05 residual (role/technology exclusions as a gate question) and OR-02 residual (buckets as eligibility); `scrapers/simple_scorer.py` and `data/resume_config.json` composite scoring.

### RULING:

Eligibility, relevance, preference, newness and review are separate outputs and are never collapsed into one composite score. There is no "best job" score. Salary preference, seniority, title and relevance must not become hidden eligibility vetoes unless explicitly stated.

Relevance is evidence-based, labelled STRONG / MODERATE / WEAK, with evidence spans. It is judged across capability clusters: AI application engineering; retrieval / knowledge systems; AI evaluation / reliability; AI infrastructure; agentic / AI-SDLC; governance / trust. Concrete engineering evidence is required; "experience with AI tools" is not sufficient by itself.

AI Quality Engineering (LLM, RAG and agent evaluation; AI testing; model evaluation; AI reliability; hallucination detection; groundedness; AI observability; GenAI quality) is in the target universe. Traditional QA (Selenium/Cypress/Playwright-only, manual, regression execution, UI, test-case execution, generic functional, mobile, ETL-only, generic test engineering) is not equivalent and should generally have LOW relevance when AI engineering is not substantial. Traditional QA is **never** an automatic eligibility FAIL; relevance determines where it goes.

If an LLM is used, its output is evidence extraction or classification only, never an opaque final verdict; `model_id`, `prompt_version` and `content_hash` are stored.

*Recorded 2026-09-29 from Phase A §3, §7, §8, §23. Field closed.*

---

## 11. OR-14 — Global scope and remote eligibility

**Supersedes:** `policy/jobops-policy-0.1.0.json` WM-R1 (any REMOTE → PASS); Career doc §4 "Work Mode — Hard Constraint".

### RULING:

The search is global, but the candidate's employment location is India. The scope is REMOTE-FROM-INDIA plus BENGALURU HYBRID. Relocation abroad, overseas on-site, overseas hybrid and visa-sponsored relocation are not sought. "Global" does not mean willing to relocate.

Remote worldwide, or remote with India explicitly eligible → PASS. Remote region-locked excluding India (US only, EU only, EEA only, UK only) → FAIL. A requirement to be authorized to work in another country, where India employment is not possible → FAIL. Ambiguous remote eligibility (e.g. "Remote – APAC" without India established) → UNKNOWN. APAC is not assumed to include India.

*Recorded 2026-09-29 from Phase A §9–§10. Field closed. Unresolved sub-questions: OI-011, OI-012, OI-029.*

---

## 12. OR-15 — Bengaluru hybrid, onsite and geography normalization

**Supersedes:** `policy/jobops-policy-0.1.0.json` WM-R2 (HYBRID → FAIL) and WM-R3 (ONSITE → FAIL); OR-04's clause *"Hybrid and on-site postings are vetoed before scoring"*.

### RULING:

Bengaluru hybrid is allowed; any Bengaluru locality counts, with aliases normalized by a geo alias table (Bengaluru, Bangalore, Bangalore Urban, Bengaluru Urban, Greater Bengaluru Area, Bengaluru East/North/South).

- Bengaluru hybrid, 0–3 office days/week → PASS.
- Bengaluru hybrid, 4–5 office days/week → FAIL.
- Bengaluru hybrid, days unspecified → UNKNOWN.
- "Flexible hybrid" → UNKNOWN.
- Bengaluru onsite → UNKNOWN (human-reviewable).
- Hybrid outside Bengaluru → FAIL.
- Onsite outside Bengaluru → FAIL.
- Onsite abroad → FAIL.
- Relocation abroad → FAIL.
- Visa-supported relocation → FAIL.

Bengaluru is one policy rule over normalized geography; it is not hard-coded throughout the gate.

*Recorded 2026-09-29 from Phase A §11, §29. Field closed. Internal tension recorded as OI-013.*

---

## 13. OR-16 — Time zone

### RULING:

Time zone is never an eligibility verdict. The candidate is flexible on overlap (US, European, UK, APAC). Overlap requirements are flags only, stored as `timezone_requirement`, `timezone_overlap_flag`, `detected_timezone` and evidence. Nothing is ever FAILed on time zone alone.

*Recorded 2026-09-29 from Phase A §12. Field closed. Routing of the flag: OI-014.*

---

## 14. OR-17 — Language

### RULING:

English is required.
- A non-English language explicitly REQUIRED → FAIL.
- A non-English language that is nice-to-have / preferred / a bonus → flag only (`LANGUAGE_PREFERENCE`), still eligible.
- The entire JD non-English with confident detection → FAIL.
- Detection uncertain → UNKNOWN.

*Recorded 2026-09-29 from Phase A §13. Field closed. Confidence threshold: OI-023.*

---

## 15. OR-18 — Compensation

**Supersedes:** OR-03a (₹20 LPA threshold); the OQ-01 anchor (straddle across ₹20L); Career doc §4 Compensation (₹20–30+ target, "Last drawn" anchor, below-₹18L exception wording); the ₹20L minimum in the 2026-09-28 preferences. **Reaffirms:** OR-03b (undisclosed → UNKNOWN, surfaced for human review).

### RULING:

**Thresholds.** Minimum disclosed ₹18 LPA; preferred ₹24–28 LPA; expected ask ₹26 LPA. One compensation floor across currencies; no separate USD/EUR floors.

**Basis.** Compare annual gross BASE salary. Ignore equity, stock, bonuses, commissions and sign-on bonuses, unless they are the only compensation information, in which case UNKNOWN. India CTC is distinguished from base and stored as `compensation_type = CTC`; it is not silently treated as foreign gross base. If the posting gives an India salary band, use it. A foreign posting with "US salary range with location-adjusted pay" and no India band → UNKNOWN; the US number is not assumed to be the India offer.

**Verdicts.**
- Clearly below ₹18L → FAIL.
- ₹24L or above → PASS.
- ₹18L to below ₹24L → ELIGIBILITY PASS, PREFERENCE BELOW_TARGET_BAND, LANE REVIEW. This is never an eligibility failure.
- Range overlapping ₹18L (e.g. ₹18–25L) → UNKNOWN.
- "Up to ₹30L" → UNKNOWN; "up to" is never treated as a guaranteed salary.
- Undisclosed → UNKNOWN.
- Variable / unclear → UNKNOWN.

The parser defect where "up to 30 LPA" became a point PASS is to be fixed.

**Stored fields.** `original_currency`, `original_amount`, `original_period`, `compensation_type`, `base_or_total`, `fx_rate`, `fx_source`, `fx_snapshot_date`, `normalized_inr_annual_base`. No live FX fetching is implemented in Phase A.

*Recorded 2026-09-29 from Phase A §14–§16. Field closed, except the foreign-conversion recommendation (OR-27). Unresolved: OI-006, OI-007, OI-008, OI-022, OI-035.*

---

## 16. OR-19 — Employment type

**Supersedes:** Career doc §4 Employment Type (*"Contract acceptable if: minimum 6-month duration, and ... product company"*). Answers the substance of OR-07, which was open.

### RULING:

- Permanent direct employment → PASS.
- Plain full-time → PASS.
- Contract, contract-to-hire, temporary, freelance, part-time, internship → FAIL.
- Short-term contract (< 6 months by default, configurable) → FAIL.
- Long-term direct-company contract → UNKNOWN + `LONG_TERM_DIRECT_CONTRACT` flag.
- Mixed wording ("Full-Time / Contractual") → UNKNOWN.
- Employment type unstated → UNKNOWN.

*Recorded 2026-09-29 from Phase A §17. Field closed. Overlap for contracts of unstated duration: OI-021.*

---

## 17. OR-20 — EOR, contractors, staffing, placement and employer type

**Supersedes:** OR-04's clause *"Services/staffing/company type is NOT a separate hard veto ... a remote role at a services/staffing company above ₹20 LPA therefore remains eligible for scoring"*, and `policy/jobops-policy-0.1.0.json` `dimensions.company_type` (`gating: false`). Resolves the substance of F-01; F-01 itself is left as written.

### RULING:

EOR is not the same as staffing or body-shopping, and the two are never collapsed into one category.

**Relationship.**
- Independent contractor, B2B, invoice-based, hourly contractor, contractor/freelance and contract-to-hire → FAIL.
- A staffing agency hiring the candidate and placing them at another client → FAIL.
- Third-party payroll / body-shopping placement → FAIL.
- Staffing/placement agency employer where the relationship is not yet sufficiently known → UNKNOWN + `EMPLOYER_TYPE_REVIEW`.

**Employer type** is a company attribute with evidence.
- Preferred categories (product company, AI-native, GCC, engineering-led) may receive positive preference signals.
- Staffing agency → UNKNOWN + flag.
- Consultancy → UNKNOWN + flag.
- IT services company → UNKNOWN + flag.
- IT services companies are not failed wholesale.
- STAFFING, CONSULTANCY and IT_SERVICES are kept as separate classifications.
- Unknown employer → UNKNOWN.
- An owner-confirmed company classification can override an inferred one.

*Recorded 2026-09-29 from Phase A §18–§20. Field closed, except permanent EOR treatment (OR-26). Unresolved: OI-020, OI-026.*

---

## 18. OR-21 — Experience and seniority

**Supersedes:** `data/resume_config.json` `years_experience: 7` and `preferred_experience_range 5–10`; the 2026-09-28 preference to exclude 7+ years and Staff/Principal/Architect.

### RULING:

Relevant experience is 3 years. Experience is a FIT signal (DIRECT / REASONABLE / STRETCH), not an eligibility veto.
- JD asks 2–3 years or 3 years → DIRECT.
- 4–6 years → STRETCH / REVIEW.
- 7+ years → STRETCH / REVIEW.
- Unspecified → UNKNOWN FIT.
- Never FAIL solely because the JD asks for more experience.

Seniority (Senior, Lead, Staff, Principal, Architect) is a relevance/fit signal and never an automatic rejection. A highly relevant Staff/Principal AI engineering role, or a 7+ years role with strong AI engineering relevance, must remain reviewable and must not automatically go to PARKED.

*Recorded 2026-09-29 from Phase A §21–§22. Field closed. REASONABLE mapping: OI-016.*

---

## 19. OR-22 — Queue lanes and philosophy

**Supersedes:** `review/jobops-review-0.1.0.json` lanes (BELOW_THRESHOLD and NOT_EVALUATED do not appear in v2; see OI-034).

### RULING:

UNKNOWN does not automatically mean FAIL, and queue design must protect human review time. The lanes are SHORTLIST, REVIEW, PARKED, EXCLUDED and SUPPRESSED_DUPLICATE.

- **SHORTLIST:** no hard FAIL; relevance STRONG or MODERATE; no material unresolved eligibility uncertainty. ₹18–24L roles go to REVIEW rather than SHORTLIST.
- **REVIEW:** no hard FAIL; relevance STRONG or MODERATE; and at least one of: UNKNOWN eligibility, EOR, employer-classification uncertainty, salary uncertainty, employment uncertainty, location uncertainty, BELOW_TARGET_BAND, or another explicit owner-review flag.
- **PARKED:** only when the opportunity is not worth daily review capacity (WEAK relevance, low-value unresolved ambiguity, clearly low-priority fit). A role is never parked merely for being Staff or Principal, asking 7+ years, or being from another country, when its AI engineering relevance is STRONG.
- **EXCLUDED:** only on a clear hard FAIL.
- **SUPPRESSED_DUPLICATE:** canonical duplicate.

Review ordering is deterministic and uses ordered categorical dimensions, never a single composite score. SHORTLIST is not capped.

*Recorded 2026-09-29 from Phase A §24, §25 (non-R3/R4 parts), §39. Field closed, except cap (OR-28) and overflow (OR-29). Ordering conflict §25 vs §39: OI-009.*

---

## 20. OR-23 — Source strategy

**Does not supersede OR-08.** OR-08 and its low-volume LinkedIn constraints remain in force until explicitly changed.

### RULING:

The target architecture is company-first. Preferred discovery hierarchy:
1. Employer ATS / company career systems (Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Recruitee, and Workday where practical).
2. Public/open job sources.
3. The existing low-volume LinkedIn adapter.
4. Other sustainable sources.
5. Apify only as an optional import/fallback.

Apify is not a strategic dependency, and no Apify API integration is built. The existing LinkedIn adapter is not removed, and LinkedIn automation is not broadened. Discovery sources do not own canonical company identity; the company registry can be populated from every discovery source. Reconnaissance (terms, access method, API availability, rate limits, robots/access constraints, freshness, structured-data quality, duplicate behaviour, country coverage) is planned but not performed in Phase A.

*Recorded 2026-09-29 from Phase A §30–§31. Field closed.*

---

## 21. OR-24 — Newness, canonical identity and evaluation replay

### RULING:

Newness states are NEW, UPDATED and SEEN_BEFORE, with `first_seen_at`, `last_seen_at`, `source_first_seen_at`, `date_precision`, `newness_confidence` and `source_observations`. The same requisition across LinkedIn, employer ATS, company site, Naukri and other boards is one canonical requisition with multiple observations, and the employer requisition URL is preferred as the canonical identity.

Policy evaluation must be replayable from stored evidence under v0.1, v0.2 and future versions without re-crawling, keyed on requisition + policy_version + evidence_hash. The newest observation must not blindly replace the current verdict: a later, less informative observation must not downgrade an evaluation made on stronger evidence. The current evaluation derives from the richest valid evidence set under a deterministic evidence precedence. This is the explicit fix for audit finding F4.

*Recorded 2026-09-29 from Phase A §27–§28. Field closed. Sub-questions: OI-015, OI-017, OI-018, OI-019.*

---

## 22. OR-25 — Status of the 2026-09-28 preferences used by the 2026-09-29 audit

### RULING:

The Phase A specification is authoritative for every decision it states explicitly. Older repository documentation does not silently replace owner decisions. Where older rules conflict, the old artifact is preserved, the old rule is marked superseded, and the new owner ruling is recorded.

*Recorded 2026-09-29 from Phase A §1. The 2026-09-28 preferences (₹20L minimum; avoid staffing; exclude 7+ years and Staff/Principal/Architect) were supplied in the audit brief and are not a repository file. OI-025 asks the owner to confirm that they are superseded wherever they differ from OR-18, OR-20 and OR-21.*

---

## 23. OR-26 — R1: Permanent employment through an Employer of Record

**Question:** Is permanent employment through a genuine EOR `UNKNOWN` + `EOR` flag (routed to review)?
**Recommendation in the Phase A specification (not confirmed):** UNKNOWN + EOR flag.
**Open item:** OI-001.

### RULING:

RULING: YES (OI-001). Genuine permanent EOR employment for the hiring company: eligibility = UNKNOWN, flag = EOR, route to REVIEW. Independent contractor / B2B / hourly-only: FAIL. Staffing company hires the candidate and places them with a client: FAIL. Do NOT collapse genuine EOR employment into staffing/client placement.

*Recorded 2026-09-29 from the owner's Phase B implementation command §2 (R1). Field closed.*

---

## 24. OR-27 — R2: Foreign compensation conversion

**Question:** Should foreign salary conversion use one ₹18L-equivalent floor with dated weekly FX, annual gross base only, preferring the India band when available?
**Would supersede:** OQ-02's "UNKNOWN until an FX source is configured" (only once ruled **and** an FX source is authorized — OI-030).
**Open item:** OI-002.

### RULING:

RULING: YES (OI-002), per the owner's Phase B implementation command §2 (R2): where foreign compensation must be normalized — use one INR-equivalent floor; floor = ₹18L annual base equivalent; use dated FX; do not create separate USD/EUR floors; compare annual gross base only; ignore equity; ignore bonus; if India-specific compensation exists, use it; if a foreign band says "location-adjusted pay" but gives no India-specific band, compensation = UNKNOWN. P1 will use an owner-maintained weekly FX table (OI-030). Do NOT implement live FX lookup. Store source currency, original amount, compensation period, compensation type, base/CTC classification, FX rate, FX date, FX source, normalized INR annual base.

Supersedes OQ-02's "UNKNOWN until an FX source is configured" only where a dated owner-maintained FX snapshot exists; without one, non-INR compensation remains UNKNOWN (FX_RATE_UNAVAILABLE).

*Recorded 2026-09-29 from the owner's Phase B implementation command §2 (R2). Field closed.*

---

## 25. OR-28 — R3: Daily REVIEW cap

**Question:** Is the daily REVIEW cap 10?
**Open item:** OI-003.

### RULING:

RULING: YES (OI-003). Daily REVIEW cap: 10. Overflow order: 1. relevance, 2. newness, 3. evidence completeness, 4. preference alignment; within preference alignment REMOTE > BENGALURU_HYBRID (OI-009 resolved in favour of the §25 order; OI-028 resolved). SHORTLIST is not capped.

*Recorded 2026-09-29 from the owner's Phase B implementation command §23 (R3). Field closed.*

---

## 26. OR-29 — R4: REVIEW overflow to PARKED

**Question:** After up to 3 days of carry-forward, do unresolved low-priority REVIEW items move to PARKED (exposed in the weekly digest)?
**Open items:** OI-004; related contradiction OI-010.

### RULING:

RULING: YES (OI-004). Overflow REVIEW items carry for 3 days; after 3 days → PARKED; the weekly PARKED digest can surface them; do not discard them. Strong relevance is exempt from overflow parking (OI-010 resolved: YES).

*Recorded 2026-09-29 from the owner's Phase B implementation command §22-§23 (R4). Field closed.*

---

## 27. OR-30 — R5: SQLite migration runner and removal of the runtime database from Git

**Question:** Is the SQLite migration runner, together with moving the runtime database out of Git, approved for implementation?
**Relates to:** CONFLICT-3 (open); JS-24.
**Open items:** OI-005; related contradiction OI-033 (§32 "authorize" wording); history purge OI-024.

### RULING:

RULING: YES (OI-005). Implement the approved SQLite migration runner. Runtime DB: configurable path, outside Git tracking, ignored by .gitignore. Do NOT rewrite old Git history (OI-024: NO). Do NOT delete historical DB files. Only stop tracking runtime DB going forward. OI-033 is resolved by this OI-005 ruling.

*Recorded 2026-09-29 from the owner's Phase B implementation command §30 (R5). Field closed.*

---

## Addendum A — Flagged inconsistency update

**F-01 (above) is left unchanged.** For the record: OR-20 now states the engagement-type treatment explicitly (placement and contractor FAIL; staffing, consultancy and IT services UNKNOWN + flag). The career document's §4 phrasing therefore no longer determines policy. Editing the career document is still the owner's decision.

**Addendum A status:** 15 recorded (OR-11 … OR-25), 5 open (OR-26 … OR-30). No policy was activated, no gate/scoring/ingestion code changed, no migration applied, no configuration changed.

---
---

# Addendum B — P1a formal recording of owner rulings (appended 2026-09-29)

**Append-only.** Nothing above this line has been edited by P1a.

**On OR-26 … OR-30:** OR-26 through OR-30 were previously filled as authorized; the Addendum A index table is intentionally preserved unchanged because the ruling log is append-only. (The index table still shows them as "☐ OPEN"; their RULING fields above are authoritative.)

**Recording mechanism (OI-048 = YES):** this Addendum B is the formal record of:
- the owner's P1a rulings sheet (2026-09-29);
- the explicit Phase B owner decisions that had previously been recorded only in `docs/architecture/JOBOPS_V2_OPEN_ITEMS.md` ("Phase B status") and in the policy artifacts.

**Sources:** the owner's Phase B implementation command (2026-09-29) and the owner's P1a follow-up command and rulings sheet (2026-09-29).
**Machine-readable policy:** `policy/jobops-policy-0.2.1.json` (default since P1a). `policy/jobops-policy-0.2.0.json` is unchanged and replayable.

| id | OI(s) | Item | Status |
|---|---|---|---|
| OR-31 | OI-025 | 2026-09-28 preferences superseded | ☑ RULED |
| OR-32 | OI-027 | ATS polling permitted despite Company Radar Phase 1 (future phase) | ☑ RULED |
| OR-33 | OI-036 | Exact ₹18L carries BELOW_TARGET | ☑ RULED |
| OR-34 | OI-037 | ₹25–32L-type range = IN_TARGET | ☑ RULED |
| OR-35 | OI-038 | MONTHLY_ASSUMED informational | ☑ RULED |
| OR-36 | OI-039 | CTC label consistency | ☑ RULED |
| OR-37 | OI-040 | FX age limit 14 days, digest warning after 7 | ☑ RULED |
| OR-38 | OI-041 | Remote with no India evidence = UNKNOWN | ☑ RULED |
| OR-39 | OI-042 | Unspecified salary basis uses salary rules | ☑ RULED |
| OR-40 | OI-043 | Requirement ≤ 3 years = DIRECT | ☑ RULED |
| OR-41 | OI-044 | No-JD Tier 1 (incl. Staff/Principal/Architect) → REVIEW | ☑ RULED |
| OR-42 | OI-045 | 0.95 confidence applies to "required" | ☑ RULED |
| OR-43 | OI-046 | Identity-uncertain pair: grouped review card | ☑ RULED |
| OR-44 | OI-047 | Addendum A index table not edited | ☑ RULED |
| OR-45 | OI-048 | Addendum B is the recording mechanism | ☑ RULED |
| OR-46 | OI-013 | Bengaluru onsite = FAIL | ☑ RULED |
| OR-47 | OI-006, OI-008 | Compensation floor/target range logic | ☑ RULED |
| OR-48 | OI-007 | CTC handling | ☑ RULED |
| OR-49 | OI-011, OI-012 | India remote listing; city hub vs explicit residence | ☑ RULED |
| OR-50 | OI-029 | Region model: EMEA FAIL, APAC UNKNOWN; work authorization | ☑ RULED |
| OR-51 | OI-014, OI-023 | Timezone/language preference informational; language 0.95 | ☑ RULED |
| OR-52 | OI-020, OI-021, OI-022, OI-026 | Employment/employer/compensation-compatibility decisions | ☑ RULED |
| OR-53 | OI-016 | REASONABLE experience | ☑ RULED |
| OR-54 | OI-015 | No-JD lanes and MODERATE seniority parking | ☑ RULED |
| OR-55 | OI-017, OI-018 | Newness rules | ☑ RULED |
| OR-56 | OI-019 | Source precedence, conflict, identity uncertainty | ☑ RULED |
| OR-57 | OI-034 | Legacy rows archived, not re-evaluated | ☑ RULED |
| OR-58 | OI-024 | History purge deferred | ☑ RULED |
| OR-59 | OI-031 | LinkedIn seed change permitted, not implemented | ☑ RULED |
| OR-60 | OI-032 | Quarantine manifest, no separate repository | ☑ RULED |
| OR-61 | OI-035 | INR monthly × 12 | ☑ RULED |

OI-001 … OI-005, OI-009, OI-010, OI-028, OI-030 and OI-033 are already settled by OR-26 … OR-30 and are not re-recorded here.

---

## 28. OR-31 — 2026-09-28 preferences superseded
**Date:** 2026-09-29 · **OI:** OI-025
### RULING:
YES. The 2026-09-28 job-preferences document (₹20L minimum, avoid staffing, exclude 7+ years and Staff/Principal) is superseded wherever it differs from the Phase A/B specifications and this addendum.
**BASIS:** Owner P1a rulings sheet, OI-025 = YES.
**SUPERSEDES:** the 2026-09-28 preferences as used by `docs/reports/JOBOPS_ACTIVATION_AUDIT_2026-09-29.md` (a brief, not a repository file).

---

## 29. OR-32 — Automated employer-ATS polling permitted (future phase)
**Date:** 2026-09-29 · **OI:** OI-027
### RULING:
YES. A later implementation phase may poll employer ATS boards automatically even though Company Radar Phase 1 requires manual-only discovery. This authorizes the design direction only. No polling, adapter or network access is implemented or permitted in P1a.
**BASIS:** Owner P1a rulings sheet, OI-027 = YES.
**SUPERSEDES:** the Company Radar Phase 1 manual-discovery constraint as a blocker for JobOps ATS ingestion. The constraint continues to govern the Company Radar experiment itself.

---

## 30. OR-33 — Exact ₹18L carries BELOW_TARGET
**Date:** 2026-09-29 · **OI:** OI-036
### RULING:
YES. An exact ₹18L figure is PASS + BELOW_TARGET (routes to REVIEW), like any whole range at or above ₹18L with upper bound below ₹24L.
**BASIS:** P1a rulings sheet §4 ("An exact ₹18L figure also carries BELOW_TARGET").
**SUPERSEDES:** the "exactly ₹18L → PASS, —" row of the Phase B command table.

---

## 31. OR-34 — Range starting inside the target band and ending above it
**Date:** 2026-09-29 · **OI:** OI-037
### RULING:
YES. A range beginning inside ₹24–28L and ending above ₹28L (e.g. ₹25–32L) is PASS + IN_TARGET, not ABOVE_TARGET. ABOVE_TARGET is compensation-compatible with IN_TARGET.
**BASIS:** P1a rulings sheet §4.
**SUPERSEDES:** nothing. It confirms the Phase B implementation convention (COMP-R18).

---

## 32. OR-35 — MONTHLY_ASSUMED is informational
**Date:** 2026-09-29 · **OI:** OI-038
### RULING:
YES. After an INR monthly figure is annualised × 12 and evaluated, MONTHLY_ASSUMED is informational and does not route to REVIEW.
**BASIS:** P1a rulings sheet §7.
**SUPERSEDES:** nothing (confirms Phase B behaviour).

---

## 33. OR-36 — CTC label consistency
**Date:** 2026-09-29 · **OI:** OI-039
### RULING:
NO to the literal Phase B asymmetry. Instead:
- CTC-only point ₹18L to below ₹24L → PASS + BELOW_TARGET + CTC_BASIS_UNVERIFIED;
- CTC-only point ₹24L+ → PASS + CTC_BASIS_UNVERIFIED (never IN_TARGET);
- CTC upper bound below ₹18L → FAIL;
- a non-failing CTC range below ₹24L (e.g. ₹18–22L) → PASS + BELOW_TARGET + CTC_BASIS_UNVERIFIED;
- a CTC range at or above ₹24L → PASS + CTC_BASIS_UNVERIFIED;
- a CTC range straddling ₹18L → UNKNOWN + CTC_RANGE_STRADDLES_FLOOR;
- base + CTC → base wins;
- no haircut or ratio, and base is never inferred.

**BASIS:** P1a rulings sheet §5 and §31.
**SUPERSEDES:** `policy/jobops-policy-0.2.0.json` COMP-C01/COMP-C02 flag sets, going forward, via `jobops-policy@0.2.1` (0.2.0 is retained for replay).

---

## 34. OR-37 — FX snapshot age
**Date:** 2026-09-29 · **OI:** OI-040
### RULING:
YES, 14 days.
- FX age is measured against the evaluation date, with an injectable clock.
- An age of 0–14 days is usable.
- Older than 14 days is unavailable: non-INR compensation → UNKNOWN + FX_STALE. Never FAIL solely because FX is stale.
- INR compensation is unaffected.
- The digest shows an FX freshness warning when the age is above 7 days and at most 14.

**BASIS:** P1a rulings sheet §8 and §32.
**SUPERSEDES:** the 0.2.0 behaviour of "no age limit, snapshot on or before the observation date" (`fx_max_age_days: null`), going forward, via 0.2.1.

---

## 35. OR-38 — Remote with no India evidence
**Date:** 2026-09-29 · **OI:** OI-041
### RULING:
YES. A remote posting that names no region and has no India listing (no listing, or a foreign listing only) → UNKNOWN (GEO_REGION_AMBIGUOUS).
**BASIS:** P1a rulings sheet §3.
**SUPERSEDES:** nothing (confirms Phase B behaviour).

---

## 36. OR-39 — Unspecified salary basis
**Date:** 2026-09-29 · **OI:** OI-042
### RULING:
YES. An INR figure labelled neither base nor CTC uses the normal salary rules plus the informational flag COMP_BASIS_UNSTATED. It is never treated as CTC merely because the basis is unspecified.
**BASIS:** P1a rulings sheet §6.
**SUPERSEDES:** nothing (confirms Phase B behaviour).

---

## 37. OR-40 — Requirement at or below 3 years
**Date:** 2026-09-29 · **OI:** OI-043
### RULING:
YES. A requirement entirely at or below 3 years (e.g. 0–2, 1–2) → DIRECT. Experience never produces FAIL.
**BASIS:** P1a rulings sheet §13.
**SUPERSEDES:** nothing (confirms Phase B behaviour).

---

## 38. OR-41 — No-JD Tier 1 senior titles
**Date:** 2026-09-29 · **OI:** OI-044
### RULING:
YES. A Tier 1 title with no JD → REVIEW, including Staff, Principal and Architect Tier 1 titles. The no-JD Tier 1 rule precedes seniority parking.
**BASIS:** P1a rulings sheet §17 and §33.
**SUPERSEDES:** nothing (confirms LANE-R03 ordering).

---

## 39. OR-42 — "Required" language confidence
**Date:** 2026-09-29 · **OI:** OI-045
### RULING:
YES. The ≥ 0.95 threshold applies both to whole-document language detection and to the confidence that a non-English language is actually REQUIRED.
- "German required" / "German mandatory" → required (FAIL).
- "knowledge of German" / "German-speaking" without explicit requirement evidence → UNKNOWN, unless stronger evidence raises requirement confidence to ≥ 0.95.
- Nice-to-have is informational.

**BASIS:** P1a rulings sheet §12.
**SUPERSEDES:** nothing (confirms Phase B behaviour).

---

## 40. OR-43 — Grouped review card for identity-uncertain pairs
**Date:** 2026-09-29 · **OI:** OI-046
### RULING:
YES, as a grouped review card. When two requisitions share company, title and normalised location but lack a suppression-grade identity key:
- both remain separate requisitions;
- both carry IDENTITY_UNCERTAIN and route to REVIEW;
- the queue/digest presents them as ONE review item (group id + member requisition ids) consuming ONE daily REVIEW cap slot.

Grouping is presentation and queue behaviour only. Requisitions, evidence, evaluations, observations and source records are never merged.
**BASIS:** P1a rulings sheet §20 and §34.
**SUPERSEDES:** the Phase B queue behaviour, which counted each member separately against the cap (0.2.0 retains it for replay).

---

## 41. OR-44 — Addendum A index table
**Date:** 2026-09-29 · **OI:** OI-047
### RULING:
NO. The Addendum A index table is not edited. OR-26 through OR-30 were previously filled as authorized; the Addendum A index table is intentionally preserved unchanged because the ruling log is append-only.
**BASIS:** P1a command §24.
**SUPERSEDES:** nothing.

---

## 42. OR-45 — Formal recording of Phase B rulings
**Date:** 2026-09-29 · **OI:** OI-048
### RULING:
YES. This Addendum B is the formal recording mechanism for the explicit Phase B owner rulings that were not previously entered in this log (OR-46 onward).
**BASIS:** P1a command §25.
**SUPERSEDES:** the Phase B restriction that limited log entries to OR-26 … OR-30.

---

## 43. OR-46 — Bengaluru onsite
**Date:** 2026-09-29 · **OI:** OI-013
### RULING:
Bengaluru onsite → FAIL. Hybrid outside Bengaluru, onsite elsewhere, onsite abroad, relocation and visa-dependent relocation → FAIL. Bengaluru hybrid: 0–3 office days PASS; 4–5 FAIL; unspecified or flexible without a day count UNKNOWN.
**BASIS:** Phase B command §8; P1a rulings sheet §3.
**SUPERSEDES:** OR-15's clause "Bengaluru onsite → UNKNOWN (human-reviewable)".

---

## 44. OR-47 — Compensation floor and target range logic
**Date:** 2026-09-29 · **OI:** OI-006, OI-008
### RULING:
The ₹18L hard floor always wins.
- Upper bound below ₹18L → FAIL.
- Minimum below ₹18L with maximum at or above ₹18L (e.g. ₹15–20L, ₹15–30L) → UNKNOWN + SALARY_RANGE_STRADDLES_FLOOR.
- A range with minimum ≥ ₹18L reaching ₹24L or more (e.g. ₹18–25L, ₹20–30L) → PASS + COMPENSATION_REVIEW.
- A whole range at or above ₹18L below ₹24L → PASS + BELOW_TARGET.
- ₹24–28L → PASS + IN_TARGET; above ₹28L → ABOVE_TARGET (compensation-compatible).
- "Up to ₹X" → UNKNOWN. Undisclosed → UNKNOWN.

**BASIS:** Phase B command §3 and §39; P1a rulings sheet §4.
**SUPERSEDES:** OR-18's example "₹18–25L → UNKNOWN".

---

## 45. OR-48 — CTC handling
**Date:** 2026-09-29 · **OI:** OI-007
### RULING:
CTC is stored as CTC and never converted to base by a haircut or ratio. When base and CTC are both stated, base decides eligibility and CTC is kept as evidence. CTC-only figures follow OR-36.
**BASIS:** Phase B command §4; P1a rulings sheet §5.
**SUPERSEDES:** nothing (OR-18 left CTC comparison open).

---

## 46. OR-49 — India remote listing; city hub vs explicit residence
**Date:** 2026-09-29 · **OI:** OI-011, OI-012
### RULING:
- Plain "Remote" on an India listing with no contradictory restriction → PASS.
- An explicit requirement to reside in, be based in, relocate to or be physically present in a non-Bengaluru Indian city → FAIL.
- A non-Bengaluru city merely listed as a hub on an otherwise remote role → UNKNOWN + CITY_HUB_LISTED.
- Bengaluru aliases (Bengaluru, Bangalore, Bengaluru East, Bangalore Urban, Greater Bengaluru Area, and localities) are one city. "WFH" means remote.

**BASIS:** Phase B command §8–§9; P1a rulings sheet §3.
**SUPERSEDES:** nothing (these questions were open).

---

## 47. OR-50 — Region model and work authorization
**Date:** 2026-09-29 · **OI:** OI-029
### RULING:
Region rules use a region → country membership model.
- A named region that excludes India (US, EU, EEA, UK, LATAM, EMEA …) → FAIL; hence "Remote – EMEA" → FAIL.
- A region containing India without naming it (e.g. "Remote – APAC") → UNKNOWN.
- A requirement to be authorized to work in the country of the posting (other than India) → FAIL.

**BASIS:** Phase B command §10; P1a rulings sheet §3.
**SUPERSEDES:** nothing (EMEA was open).

---

## 48. OR-51 — Timezone, language preference, language confidence
**Date:** 2026-09-29 · **OI:** OI-014, OI-023
### RULING:
- Timezone overlap is informational only: never FAIL, never REVIEW by itself.
- A preferred or nice-to-have language is informational only.
- A non-English JD or language requirement is FAIL only at confidence ≥ 0.95; below that, UNKNOWN.

**BASIS:** Phase B command §11–§12; P1a rulings sheet §3 and §12.
**SUPERSEDES:** nothing (these were open).

---

## 49. OR-52 — Employment and employer decisions
**Date:** 2026-09-29 · **OI:** OI-020, OI-021, OI-022, OI-026
### RULING:
- Plain "Contract" with no duration → FAIL.
- An unclassified employer → UNKNOWN + EMPLOYER_UNCLASSIFIED, never SHORTLIST (REVIEW if otherwise relevant).
- A non-tech enterprise hiring directly for an AI-engineering role (e.g. a bank) → employer_type PASS.
- ABOVE_TARGET is compensation-compatible (not a review flag).
- Product, AI-native, GCC and engineering-led employers → PASS.
- Staffing, consultancy and IT services → UNKNOWN + flag.
- Third-party payroll / body-shop → FAIL.
- An owner classification overrides inferred evidence.

**BASIS:** Phase B command §6–§7; P1a rulings sheet §4, §10–§11.
**SUPERSEDES:** nothing (these were open).

---

## 50. OR-53 — REASONABLE experience
**Date:** 2026-09-29 · **OI:** OI-016
### RULING:
Ranges containing 3 years and extending above it (e.g. 2–5, 3–5) → REASONABLE. 4–6, 5–7 and 7+ → STRETCH. Experience is never an eligibility FAIL.
**BASIS:** Phase B command §13; P1a rulings sheet §13.
**SUPERSEDES:** nothing (REASONABLE was undefined).

---

## 51. OR-54 — No-JD lanes and MODERATE seniority parking
**Date:** 2026-09-29 · **OI:** OI-015
### RULING:
- No JD → relevance NOT_ASSESSED (never guessed from the title). A Tier 1 title → REVIEW; any other title → PARKED.
- PARKED also covers WEAK relevance, and MODERATE relevance with 7+ years or a Staff/Principal/Architect title. STRONG relevance overrides seniority parking.
- Queue order and the overflow exemption remain as OR-28 and OR-29.

**BASIS:** Phase B command §21–§22; P1a rulings sheet §17.
**SUPERSEDES:** nothing (these were open).

---

## 52. OR-55 — Newness
**Date:** 2026-09-29 · **OI:** OI-017, OI-018
### RULING:
- NEW / UPDATED / SEEN_BEFORE per canonical requisition.
- UPDATED only when title, location, compensation, employment type or JD hash changes.
- Own evidence enrichment of an unchanged requisition → SEEN_BEFORE.

**BASIS:** Phase B command §24–§25; P1a rulings sheet §18.
**SUPERSEDES:** nothing (these were open).

---

## 53. OR-56 — Source precedence, conflicts and identity uncertainty
**Date:** 2026-09-29 · **OI:** OI-019
### RULING:
- ATS/company-site evidence outranks job boards for factual fields. Job boards may win on freshness / first-seen date.
- Both observations are kept.
- Any factual conflict → SOURCE_CONFLICT → REVIEW; neither source is silently discarded.
- Unresolvable canonical identity → IDENTITY_UNCERTAIN → REVIEW (grouping per OR-43).
- A search-only re-observation never replaces or downgrades a JD-based verdict; a later richer observation may change it (F4).

**BASIS:** Phase B command §26–§27, §37; P1a rulings sheet §19–§21.
**SUPERSEDES:** nothing (this was open).

---

## 54. OR-57 — Legacy scraped rows
**Date:** 2026-09-29 · **OI:** OI-034
### RULING:
The 77 pre-v0.2 `scraped_jobs` rows are archived as legacy (migration 0101). They are never re-evaluated under v0.2, never enter v2 lanes, and are preserved in place.
**BASIS:** Phase B command §29.
**SUPERSEDES:** nothing (this was open).

---

## 55. OR-58 — Git history purge deferred
**Date:** 2026-09-29 · **OI:** OI-024
### RULING:
Deferred. No Git history rewrite and no deletion of historical DB files. The runtime DB is only untracked going forward (OR-30). Any future purge needs a new explicit ruling.
**BASIS:** Phase B command §30; P1a command §22.
**SUPERSEDES:** nothing.

---

## 56. OR-59 — LinkedIn seeds
**Date:** 2026-09-29 · **OI:** OI-031
### RULING:
Permitted but not implemented. LinkedIn query seeds may later move toward Tier 1 titles within the existing OR-08 caps. No change has been made, and OR-08 stays in force.
**BASIS:** Phase B command §33.
**SUPERSEDES:** nothing.

---

## 57. OR-60 — Quarantine rather than a separate repository
**Date:** 2026-09-29 · **OI:** OI-032
### RULING:
NO separate repository. Legacy and out-of-scope material (learning/SQL, old scrapers, QA scoring, n8n, stale backups, PID files, stale docs) is identified in `_quarantine/MANIFEST.md`. Nothing is moved without a later authorized session.
**BASIS:** Phase B command §31–§32.
**SUPERSEDES:** nothing.

---

## 58. OR-61 — INR monthly compensation
**Date:** 2026-09-29 · **OI:** OI-035
### RULING:
An INR monthly figure with no stated annual basis is annualised × 12, flagged MONTHLY_ASSUMED (informational per OR-35), and then evaluated under the normal annual rules.
**BASIS:** Phase B command §5; P1a rulings sheet §7.
**SUPERSEDES:** OQ-02's "no annualisation without a stated basis", for INR monthly figures only.

---

**Addendum B status:** OR-31 … OR-61 recorded (31 entries). No earlier content of this log was modified by P1a. Policy `jobops-policy@0.2.1` implements OR-36, OR-37 and OR-43, and the parsing clarifications of the P1a rulings sheet §3 and §9. `jobops-policy@0.2.0` is byte-identical and replayable.

---

# Addendum C — P3 blind-validation fix pass: owner rulings (appended 2026-09-30)

**Source:** Owner P3 command "JOBOPS — P3 BLIND VALIDATION FIX PASS", §36 (rulings dated 2026-09-29).
**Recording rule:** each `RULING:` field below states only what the Owner stated in that command. No earlier content of this log is modified; numbering continues from OR-61.

| id | OI | Item | Status |
|---|---|---|---|
| OR-62 | OI-049 | CTC-only range spanning ₹24L also carries CTC_BASIS_UNVERIFIED | ☑ RULED |
| OR-63 | — | CTC lane rule: CTC_BASIS_UNVERIFIED alone does not route to REVIEW | ☑ RULED |
| OR-64 | — (blind S05 question) | Cross-source newness | ☑ RULED |
| OR-65 | — (blind S07 question) | REVIEW carry counting | ☑ RULED |

---

## 59. OR-62 — CTC-only range spanning the target (OI-049)
**Date:** 2026-09-29 · **OI:** OI-049
### RULING:
YES. A CTC-only range starting at or above ₹18L and reaching ₹24L or more carries CTC_BASIS_UNVERIFIED in addition to COMPENSATION_REVIEW when the range qualifies for compensation review.
**BASIS:** P3 command §36 (OI-049), §18.
**SUPERSEDES:** `jobops-policy@0.2.1` COMP-C03 flag set, going forward, via `jobops-policy@0.2.2` (0.2.0 and 0.2.1 are retained for replay).

---

## 60. OR-63 — CTC lane rule
**Date:** 2026-09-29 · **OI:** none (blind case B052 UNDETERMINED lane)
### RULING:
CTC_BASIS_UNVERIFIED alone does not route to REVIEW. It is informational. Other review-triggering conditions continue to route to REVIEW (e.g. BELOW_TARGET, COMPENSATION_REVIEW).
**BASIS:** P3 command §19, §31, §36.
**SUPERSEDES:** the review-routing registration of CTC_BASIS_UNVERIFIED in `jobops-policy@0.2.0` / `0.2.1`, going forward, via `jobops-policy@0.2.2`.

---

## 61. OR-64 — Cross-source newness
**Date:** 2026-09-29 · **OI:** none (blind sequence S05 UNDETERMINED newness)
### RULING:
When an ATS/company-site observation changes the accepted material value relative to an earlier board observation: UPDATED, with SOURCE_CONFLICT, and REVIEW. If the accepted value is unchanged: SEEN_BEFORE (the conflict evidence is preserved).
**BASIS:** P3 command §32, §36.
**SUPERSEDES:** the Phase B newness convention "a disagreement between different sources is a SOURCE_CONFLICT, not an update", going forward, via `jobops-policy@0.2.2`.

---

## 62. OR-65 — REVIEW carry counting
**Date:** 2026-09-29 · **OI:** none (blind sequence S07 UNDETERMINED parked day)
### RULING:
The first overflow day counts as carry day 1. An item that overflows on D is eligible on D+1 and D+2 and becomes PARKED on D+3, after three daily plans have considered it. STRONG items are exempt from overflow parking.
**BASIS:** P3 command §31, §36.
**SUPERSEDES:** nothing. It confirms the existing queue behaviour (carry_days > review_carry_days parks on D+3).

---

**Addendum C status:** OR-62 … OR-65 recorded (4 entries). No earlier content of this log was modified by P3. `jobops-policy@0.2.2` implements OR-62, OR-63 and OR-64; OR-65 matches existing behaviour and is covered by a regression test. `jobops-policy@0.2.0` and `jobops-policy@0.2.1` are byte-identical and replayable. New owner questions from P3 are OI-050 and OI-051 (`docs/architecture/JOBOPS_V2_OPEN_ITEMS.md`, section P3).

---

# Addendum E — P5 Round-2 root-cause fix: owner rulings (appended 2026-09-30)

**Source:** Owner P5 command "JobOps P5 — Round-2 Root-Cause Fix, 0.2.3, and Acceptance", §3 (Addendum E1–E8).
**Recording rule:** each `RULING:` field below states only what the Owner stated in that command. No earlier content of this log is modified; numbering continues from OR-65. The letter D is not used here: the Addendum D items proposed in P4b (OI-050, OI-051) remain a separate recording task and are not entered by P5.

| id | Owner item | Item | Status |
|---|---|---|---|
| OR-66 | E1 | Evidence precision | ☑ RULED |
| OR-67 | E2 | Fixed/guaranteed base vs variable | ☑ RULED |
| OR-68 | E3 | EXPERIENCE_STRETCH → REVIEW | ☑ RULED |
| OR-69 | E4 | Built-in language detection | ☑ RULED |
| OR-70 | E5 | THIRD_PARTY_PAYROLL employer classification | ☑ RULED |
| OR-71 | E6 | Office-day normalization | ☑ RULED |
| OR-72 | E7 | Tier 1 title prior | ☑ RULED |
| OR-73 | E8 | AI relevance vocabulary | ☑ RULED |

---

## 63. OR-66 — Evidence precision (E1)
**Date:** 2026-09-30
### RULING:
A hard FAIL may only be emitted from (a) structured field evidence or (b) explicit, unambiguous multi-word free-text evidence. Single-word or ambiguous cues ("contract", "hybrid", a bare number, isolated terminology) must not directly produce FAIL; they may at most produce UNKNOWN / a flag until context establishes their meaning. Structured field evidence outranks free text. If structured and free-text evidence conflict: UNKNOWN + conflict flag, never FAIL merely because the free text contains a hard-looking keyword.
**BASIS:** P5 command §3 E1.
**SUPERSEDES:** the JD-body use of the single-word employment vocabulary (e.g. `\bcontract(?:ual)?\b`) in `jobops-policy@0.2.2` and earlier, going forward, via `jobops-policy@0.2.3` (EMP-R15, `lexicon.employment_jd`).

---

## 64. OR-67 — Fixed/guaranteed base vs variable (E2)
**Date:** 2026-09-30
### RULING:
A fixed/guaranteed annual component is base compensation. Variable compensation is not added to base ("₹15L fixed + ₹5L variable" means base = ₹15L, not ₹20L). Annual gross base is used for the compensation policy.
**BASIS:** P5 command §3 E2 (answers the P4b owner question on R2-040).
**SUPERSEDES:** nothing (confirms the reading already applied by `jobops-policy@0.2.2` to R2-040).

---

## 65. OR-68 — EXPERIENCE_STRETCH → REVIEW (E3)
**Date:** 2026-09-30
### RULING:
If experience is classified STRETCH it routes to REVIEW. It must not automatically become EXCLUDED.
**BASIS:** P5 command §3 E3, §12. The relevant AI experience of 3 years remains a policy input (parameter `relevant_ai_experience_years` in 0.2.3).
**SUPERSEDES:** nothing (confirms the review-routing registration of EXPERIENCE_STRETCH in 0.2.x).

---

## 66. OR-69 — Built-in language detection (E4)
**Date:** 2026-09-30
### RULING:
Language detection is built into the engine; no external language service. Overwhelmingly English JD, confidence ≥ .95 → PASS. Genuine non-English suspicion, confidence .50–.94 → UNKNOWN. Genuine non-English, confidence ≥ .95 → FAIL. An explicit required non-English language → FAIL. Normal English technical terminology must not be marked non-English. A confidence/evidence path is preserved for audit.
**BASIS:** P5 command §3 E4, §7.
**SUPERSEDES:** the stop-word ratio heuristic capped at 0.9 (`heuristic_language_max_confidence`) as the document-language detector, going forward, via `jobops-policy@0.2.3` (`lexicon.language.detector`).

---

## 67. OR-70 — THIRD_PARTY_PAYROLL employer classification (E5)
**Date:** 2026-09-30
### RULING:
THIRD_PARTY_PAYROLL is an explicit employer classification. Third-party payroll / body-shop / client-placement → employer_type = FAIL. This is not represented merely as an employment_type failure; employer_type and employment_type stay conceptually separate.
**BASIS:** P5 command §3 E5, §10. Schema: migration `0103_third_party_payroll_classification.sql`.
**SUPERSEDES:** the employer_type verdict UNKNOWN for such postings in `jobops-policy@0.2.2` and earlier (golden G072 keeps its historical expectation for 0.2.0–0.2.2), going forward, via `jobops-policy@0.2.3` (EMPR-R08, EMPR-R09).

---

## 68. OR-71 — Office-day normalization (E6)
**Date:** 2026-09-30
### RULING:
Office-day requirements are normalized across natural language (e.g. "Tuesdays and Thursdays", "3 days/week", "Mon/Wed/Thu", "alternate days", "one fixed anchor day", "8 days/month", "WFH Friday", weekday office requirements). For a normal 5-day week: office days/week ≤ 3 → acceptable Bengaluru hybrid; ≥ 4 → FAIL. Monthly: office days/month ÷ 4.33. Alternate-day language is normalized rather than treated as opaque. "Friday is WFH" implies the other four weekdays are office days when a standard Monday–Friday week is established. Negated hybrid language ("not a hybrid role", "this is not hybrid") must not produce HYBRID. Remote + an explicit 5-day onsite requirement elsewhere is a work-mode conflict: UNKNOWN + WORK_MODE_CONFLICT, never SHORTLIST.
**BASIS:** P5 command §3 E6, §9.
**SUPERSEDES:** nothing (extends OR-46 / P3 §13 parsing).

---

## 69. OR-72 — Tier 1 title prior (E7)
**Date:** 2026-09-30
### RULING:
A Tier 1 title is a prior, not proof of relevance. Tier 1 title AND weak relevance AND at least one AI-specific term → REVIEW + RELEVANCE_TITLE_PRIOR. A rich Tier 1 JD with no AI-specific term → relevance WEAK, lane PARKED. Tier 1 without JD → REVIEW. The underlying relevance thresholds are not altered to improve the Round-2 result.
**BASIS:** P5 command §3 E7, §8.
**SUPERSEDES:** LANE-R05 (WEAK → PARKED) for the Tier 1 + AI-term case, going forward, via `jobops-policy@0.2.3` (LANE-R10).

---

## 70. OR-73 — AI relevance vocabulary (E8)
**Date:** 2026-09-30
### RULING:
The deterministic relevance vocabulary is expanded to recognise legitimate AI/LLM evaluation, reliability and quality concepts (evals, evaluation harness, golden sets, guardrails, hallucination evaluation, faithfulness, groundedness, context precision/recall, LLM/agent evaluation and observability, AI-specific SLOs, prompt regression, RAG/retrieval evaluation, red teaming, safety evaluation, benchmark and regression evaluation, LLM test generation, AI defect prediction, GenAI/agentic testing, LLM validation, …). The list is illustrative, not permission to match keywords blindly: contextual evidence is required and no single keyword may cause STRONG relevance.
**BASIS:** P5 command §3 E8, §8.
**SUPERSEDES:** nothing (extends the OR-12 / OR-13 vocabulary; thresholds unchanged).

---

### Addendum E — implementation-level interpretations (recorded, not rulings)

The following are how `jobops-policy@0.2.3` implements existing rulings or repairs extraction defects found in P5. They introduce no new policy semantics; each cites the ruling it serves.

1. **Employment (OR-66):** PASS kinds (PERMANENT, FULL_TIME) keep single-word vocabulary in the JD because they can never produce FAIL; a labelled JD line ("Employment type: Contract") is explicit evidence and uses the structured vocabulary; direct-employment evidence ("employed directly by", "on our payroll") is posting-level, because it is often in a different sentence from the contract cue. A structured PERMANENT field contradicted by an explicit JD FAIL-kind (temporary, contract, internship …) is EMPLOYMENT_SOURCE_CONFLICT (EMP-R15).
2. **Compensation (OR-67, OR-47, OR-48):** components separated by "+", "|" or "plus" are separate clauses; percentages and counts ("25 lakh users") are never amounts; a lakh word alone does not open a salary clause without a compensation keyword or currency marker; "21 L" after a compensation keyword is INR; a compensation table's single stated period is inherited by an unlabelled line in the same currency; SGD, CAD, AUD, AED, CHF and JPY are recognised currencies (the FX policy OR-27 / OR-37 is unchanged).
3. **Office days (OR-71):** alternate days are normalised to 2.5 office days per week; weekday tokens are assigned to the nearest office or WFH cue; in the JD body an attendance cue is required for a day count to state a work mode; structured Hybrid contradicted by "every weekday in the office" is WORK_MODE_CONFLICT (precedence rule, P3 §8).
4. **Language (OR-69):** function-word evidence per language; URLs, e-mails and domains are removed before detection; a single stray foreign token is noise; capitalised words with diacritics are proper nouns; scripts written without spaces are measured in characters.
5. **Newness and conflicts (OR-55, OR-56, OR-64; owner resolution of R2-SEQ-09 recorded in P4b):** a detail absent in one sighting and present in another (office days, a JD) is neither UPDATED nor SOURCE_CONFLICT; two stated, different values still are.
6. **Relevance (OR-73):** a contextual term counts only with an AI anchor elsewhere in the same sentence (never itself); overlapping matches within one capability cluster count once; thresholds unchanged.
7. **Sentence boundaries:** dot leaders ("........") are not sentence ends and the capital-letter lookahead is case-sensitive, as the lexicon's intent always was.
8. **Geography:** India-eligibility statements ("India-based freelancers welcome", "hiring in India") are listing evidence.

**Addendum E status:** OR-66 … OR-73 recorded (8 entries). No earlier content of this log was modified by P5. `jobops-policy@0.2.3` implements OR-66 … OR-73 and is **EXPERIMENTAL**: it did not pass the P5 acceptance gate (frozen Round-2 replay 57/124 = 45.97 % posting mismatch > 20 %), so `jobops-policy@0.2.2` remains the default. See `docs/reports/JOBOPS_P5_FIX_REPORT_2026-09-30.md`.

---

# Addendum D (late) — P4b / Round-2 owner resolutions (appended 2026-09-30, in P6)

**Source:** Owner P4b command §10 and §30 (Round-2 owner resolutions and proposed Addendum D), confirmed as authoritative in the Owner P6 command §17.
**Recording rule:** append-only; numbering continues from OR-73. Resolutions already recorded are referenced, not duplicated.

| id | OI / item | Item | Status |
|---|---|---|---|
| OR-74 | OI-050 | Same-run board/ATS contradiction on first observation | ☑ RULED (NO) |
| OR-75 | OI-051 | Direct-company contract with no stated duration | ☑ RULED (YES) |
| OR-76 | R2-075 / R2-076 | Permanent role through an Employer of Record | ☑ RULED |
| OR-77 | R2-SEQ-09 | SEARCH_ONLY → FULL_JD on the same source | ☑ RULED |
| (OR-63) | R2-046 / R2-051 | BELOW_TARGET and COMPENSATION_REVIEW are review flags | already recorded in OR-63 — referenced, not duplicated |

---

## 71. OR-74 — Same-run board/ATS contradiction (OI-050)
**Date:** 2026-09-30 · **OI:** OI-050
### RULING:
NO. When a board sighting and a contradicting ATS/company-site sighting of the same requisition are first observed in the same run, newness is NEW (not UPDATED), with SOURCE_CONFLICT, and the lane is REVIEW.
**BASIS:** Owner P4b command §30 (proposed Addendum D, OI-050 = NO); Owner P6 command §17.
**SUPERSEDES:** nothing. Confirms `newness.cross_source_update.applies_after_first_run = true` (0.2.2 onward) and golden G111.

---

## 72. OR-75 — Direct-company contract with no stated duration (OI-051)
**Date:** 2026-09-30 · **OI:** OI-051
### RULING:
YES. A direct-company contract with direct-employment evidence and no stated duration → UNKNOWN + CONTRACT_DURATION_UNSTATED. A plain "Contract" with neither direct-employment evidence nor a duration → FAIL.
**BASIS:** Owner P4b command §30 (OI-051 = YES); Owner P6 command §17.
**SUPERSEDES:** the `owner_confirmed: false` status of EMP-R14 (0.2.2 onward); 0.2.0 / 0.2.1 keep EMP-R03 FAIL for replay.

---

## 73. OR-76 — Permanent role through an Employer of Record
**Date:** 2026-09-30 · **Item:** Round-2 R2-075 / R2-076
### RULING:
A genuine permanent role through an Employer of Record → employment UNKNOWN + EOR → REVIEW. An EOR signal in the JD body counts; a structured "Full-time" does not override it (the two are compatible). A genuine EOR is not third-party payroll / body-shop merely because an intermediary exists.
**BASIS:** Owner P4b command §10 and §25; Owner P6 command §7, §17.
**SUPERSEDES:** nothing (confirms EOR-R01 and the JD-body relationship reading of 0.2.2 onward).

---

## 74. OR-77 — SEARCH_ONLY → FULL_JD on the same source
**Date:** 2026-09-30 · **Item:** Round-2 R2-SEQ-09
### RULING:
When the same source goes from SEARCH_ONLY to FULL_JD without changing title, location, compensation or employment type, the observation is enrichment of the same requisition: SEEN_BEFORE. A fuller JD may change relevance or eligibility, but that alone does not make the requisition UPDATED.
**BASIS:** Owner P4b command §10 and §26; Owner P6 command §17.
**SUPERSEDES:** nothing. Implemented in `jobops-policy@0.2.3` (`newness.absent_detail_is_enrichment`; Addendum E implementation note 5), which is hereby a ruling rather than an interpretation.

---

**Addendum D (late) status:** OR-74 … OR-77 recorded; BELOW_TARGET / COMPENSATION_REVIEW review routing is OR-63 (not duplicated). No earlier content of this log was modified.

---

# Addendum F — Split acceptance gates and relevance calibration (appended 2026-09-30)

**Source:** Owner P6 command "JOBOPS P6 — Rulings catch-up, split acceptance gates, policy 0.2.4, offline real-JD replay", §5, §11–§16, §18. Resolves P5 owner questions Q1–Q4.

| id | Owner item | Item | Status |
|---|---|---|---|
| OR-78 | F1 | STRONG is not redefined; relevance calibrated on owner-labelled real JDs | ☑ RULED |
| OR-79 | F2 | Single foreign-country Remote is a region lock | ☑ RULED |
| OR-80 | F3 | Evidence completeness has exactly two classes | ☑ RULED |
| OR-81 | F4 | Informational flags never route to REVIEW alone | ☑ RULED |
| OR-82 | F5 | Acceptance gates split into Gate E and Gate R | ☑ RULED |

---

## 75. OR-78 — STRONG is not redefined (F1)
**Date:** 2026-09-30 · **Resolves:** P5 Q1
### RULING:
STRONG remains ≥ 3 distinct AI-specific terms across ≥ 2 capability clusters; MODERATE ≥ 2 terms; WEAK fewer; NOT_ASSESSED only when no JD was captured. There is no short-JD exception. Relevance is validated on real JDs labelled by the owner. A blind author may assert STRONG only when the JD plainly contains 3+ unmistakable AI terms across 2+ capability clusters, WEAK only when the role is plainly not about AI, NOT_ASSESSED only when no JD was captured; otherwise the relevance expectation is omitted.
**BASIS:** Owner P6 command §11, §12, §18 F1.
**SUPERSEDES:** nothing (confirms OR-12 / OR-13 and OR-73's unchanged thresholds). Round-2 relevance expectations authored without this rule are diagnostic only.

---

## 76. OR-79 — Single foreign-country Remote (F2)
**Date:** 2026-09-30 · **Resolves:** P5 Q3
### RULING:
A remote posting naming a single foreign country ("Remote — Canada", "Remote, Germany", "Remote - Japan") is a region lock → FAIL, unless the JD explicitly states that candidates in India, or worldwide candidates, are eligible ("candidates in India are eligible", "India candidates are welcome", "worldwide candidates are eligible", "work from anywhere in the world") → PASS. Plain "Remote" with no India listing and no region → UNKNOWN. "Remote — APAC" → UNKNOWN.
**BASIS:** Owner P6 command §5, §18 F2.
**SUPERSEDES:** nothing for the lock itself (consistent with OR-50). Adds the explicit-eligibility exception, implemented in `jobops-policy@0.2.4`. The Round-2 expectation for R2-081 (PASS) is a case error under this rule.

---

## 77. OR-80 — Evidence completeness has exactly two classes (F3)
**Date:** 2026-09-30 · **Resolves:** P5 Q2
### RULING:
Every UNKNOWN is either **missing** (caused by missing information: salary undisclosed, no JD, work arrangement absent …) or **known** (caused by a known fact the policy deliberately leaves unresolved: consultancy, staffing, EOR …). Only missing counts toward queue evidence completeness. No third class (e.g. policy_uncertainty, ambiguity, known_ambiguity) is introduced; if real-JD evidence shows two classes are insufficient, a new owner OI is raised.
**BASIS:** Owner P6 command §14, §18 F3.
**SUPERSEDES:** the queue ordering key "number of UNKNOWN dimensions" of 0.2.0–0.2.3, going forward, via `jobops-policy@0.2.4` (older versions keep their ordering for replay).

---

## 78. OR-81 — Informational flags (F4)
**Date:** 2026-09-30
### RULING:
These flags are informational and never route to REVIEW by themselves: ABOVE_TARGET, IN_TARGET, CTC_BASIS_UNVERIFIED, MONTHLY_ASSUMED, COMP_BASIS_UNSTATED, LANGUAGE_PREFERENCE, TIMEZONE_OVERLAP_US / UK / EU / APAC, SENIORITY_*, EXPERIENCE_SUBSTANTIAL_MISMATCH. All other flags route to REVIEW.
**BASIS:** Owner P6 command §18 F4.
**SUPERSEDES:** nothing (matches the `flags.informational` registration of 0.2.2 and 0.2.3; locked by a 0.2.4 test).

---

## 79. OR-82 — Split acceptance gates (F5)
**Date:** 2026-09-30
### RULING:
The single aggregate Round-2 posting-mismatch gate is retired. **Gate E** (eligibility and safety) measures geography, compensation, employment_type, employer_type and language: each scorable dimension ≥ 95 % accuracy, zero unexplained false EXCLUDED, zero unexplained false SHORTLIST, and sequences passing or explicitly classified. **Gate R** (relevance) is measured separately on owner-labelled real JDs and is never folded into Gate E or into a composite score. No "overall Round-2 pass/fail" percentage is used for acceptance.
**BASIS:** Owner P6 command §15, §16, §18 F5.
**SUPERSEDES:** the P5 §17 aggregate ≤ 20 % posting-mismatch acceptance rule.

---

**Addendum F status:** OR-78 … OR-82 recorded. No earlier content of this log was modified.

---

# Post-P6 ruling (appended 2026-09-30)

| id | OI | Item | Status |
|---|---|---|---|
| OR-83 | OI-052 | Explicit India/worldwide eligibility overrides an India-excluding region | ☑ RULED (YES) |

---

## 80. OR-83 — Explicit India/worldwide eligibility overrides an India-excluding region (OI-052)
**Date:** 2026-09-30 · **OI:** OI-052
### RULING:
YES. An explicit statement that candidates in India (or worldwide candidates) are eligible overrides a regional label that would otherwise exclude India.
- "Remote — EMEA" + "candidates in India are eligible" → PASS.
- "Remote — EMEA" + "worldwide candidates are eligible" → PASS.
- "Remote — APAC" + "candidates in India are eligible" → PASS.
- "Remote — EMEA" without India/worldwide eligibility → FAIL.
- "Remote — APAC" without India eligibility → UNKNOWN.
- Plain "Remote" with no India listing and no region → UNKNOWN.

Precedence: (1) explicit India/worldwide eligibility statement; (2) explicit regional/country restriction; (3) plain Remote with insufficient eligibility evidence. The single foreign-country rule of OR-79 is unchanged ("Remote — Canada" → FAIL; + India/worldwide eligibility → PASS); the same evidence precedence now applies to multi-country regions (EMEA, LATAM, UK/Europe, …).
**BASIS:** Owner post-P6 command resolving OI-052.
**SUPERSEDES:** the temporary recall-safe reading of OI-052 (UNKNOWN + GEO_REGION_AMBIGUOUS, GEO-R27) in the P6 build of `jobops-policy@0.2.4`, going forward, via the updated `jobops-policy@0.2.4` (GEO-R27 → PASS). 0.2.0–0.2.3 are unchanged.

---

# Addendum G — P7a-Final Round-3 corpus resolutions (appended 2026-10-01)

**Source:** Owner command "JobOps v2 — P7a-Final Round3 Corpus Resolution" §1–§4.
**Recording rule:** append-only; numbering continues from OR-83. No earlier entry is rewritten.
**Effective policy version:** `jobops-policy@0.2.4` for all four. Each ruling makes explicit a boundary that the accepted 0.2.4 rules already apply. None changes policy semantics, so no 0.2.5 is created and the 0.2.4 artifact and its accepted hash are untouched. 0.2.0–0.2.3 are unchanged.
**Corpus:** `data/fixtures/round3/blind_cases_round3.json`. Pre-resolution authoring hash `1ad02692fcdad4a9fd02070a8a30e7b20cd3f3d4fa5180cc9d6c2d69172429fe`; the final measurement hash is in `blind_cases_round3.sha256`.

| id | Corpus item | Item | Status |
|---|---|---|---|
| OR-84 | R3-105 | An 8–10 year requirement is STRETCH | ☑ RULED (YES) |
| OR-85 | R3-106 | Range with minimum < ₹18L and maximum exactly ₹18L | ☑ RULED (UNKNOWN) |
| OR-86 | R3-107 | Direct fixed-term contract of exactly 6 months | ☑ RULED (UNKNOWN) |
| OR-87 | S-08 | Order of newness states in the REVIEW queue | ☑ RULED |

---

## 81. OR-84 — An 8–10 year requirement is STRETCH (R3-105)
**Date:** 2026-10-01 · **Affects:** Round-3 R3-105 · **Effective:** `jobops-policy@0.2.4`
**Question:** Is an 8–10 year experience requirement classified as STRETCH?
### RULING:
YES. `experience_label = STRETCH`. A stated range whose minimum is above the relevant experience (3 years) is STRETCH, whatever its upper bound. DIRECT (range entirely ≤ 3) and REASONABLE (range containing 3 and extending above it) keep the definitions of OR-21 and OR-53. STRETCH carries `EXPERIENCE_STRETCH` and routes to REVIEW, never EXCLUDED (OR-68). An 8+ year minimum is also a "7+ years" seniority-parking signal under OR-54, which affects the lane only when relevance is MODERATE. Experience is never an eligibility FAIL.
**RATIONALE:** OR-21 lists "7+ years → STRETCH" and OR-53 lists "4–6, 5–7 and 7+ → STRETCH". 8–10 lies entirely above 7, so STRETCH is the only label consistent with both. 0.2.4 rule EXP-R07 (RANGE, minimum > 3 → STRETCH) already implements this. The owner sheet given to the corpus author left the STRETCH boundary out, but the policy did not.
**SUPERSEDES:** nothing. Makes the STRETCH range boundary explicit.

---

## 82. OR-85 — Compensation range ending exactly at ₹18L (R3-106)
**Date:** 2026-10-01 · **Affects:** Round-3 R3-106 · **Effective:** `jobops-policy@0.2.4`
**Question:** Is a compensation range with minimum < ₹18L and maximum = ₹18L (e.g. ₹12–18L) FAIL, UNKNOWN or PASS?
### RULING:
UNKNOWN. This is the general boundary rule, not a special case: a range is FAIL only when its maximum is strictly below ₹18L. A range whose minimum is below ₹18L and whose maximum is at or above ₹18L (the maximum may equal ₹18L) is a floor straddle → UNKNOWN + `SALARY_RANGE_STRADDLES_FLOOR` (base salary) or `CTC_RANGE_STRADDLES_FLOOR` (CTC), which routes to REVIEW. It is never EXCLUDED on compensation.
**RATIONALE:** OR-18 fails only compensation that is "clearly below ₹18L". A ₹12–18L range can be paid at the floor, and OR-33 holds that exactly ₹18L passes eligibility. So the range is not clearly below the floor, and not wholly at or above it either. That is the straddle condition. 0.2.4 already applies it: COMP-R01 fails only on `max_inr < floor`, and COMP-R04 / COMP-C05 return UNKNOWN + straddle flag on `min_inr < floor`.
**SUPERSEDES:** nothing. Makes the inclusive upper-bound boundary of the straddle rule explicit.

---

## 83. OR-86 — Direct fixed-term contract of exactly 6 months (R3-107)
**Date:** 2026-10-01 · **Affects:** Round-3 R3-107 · **Effective:** `jobops-policy@0.2.4`
**Question:** Is a direct-company fixed-term contract of exactly 6 months FAIL, UNKNOWN or PASS?
### RULING:
UNKNOWN + `LONG_TERM_DIRECT_CONTRACT`, routing to REVIEW. Short-term means strictly under 6 months (`contract_months < short_term_contract_months`, default 6). A direct-company contract of 6 months or more is long-term. This is an explicit ruling on the 6-month boundary, not an inference from "< 6 months". A 6-month contract with no direct-employment evidence is still governed by OR-19 / OR-75 (plain contract → FAIL), and a 6-month internship or temporary role is still FAIL as internship or temporary.
**RATIONALE:** OR-19 defines short-term as "< 6 months". The Career doc wording it superseded called a 6-month duration the minimum acceptable one. Treating exactly 6 months as long-term keeps that intent, and REVIEW rather than FAIL is the recall-safe reading at the boundary. 0.2.4 rules EMP-R09 (`lt 6` → FAIL) and EMP-R10 (direct, `gte 6` → UNKNOWN + LONG_TERM_DIRECT_CONTRACT) already implement it.
**SUPERSEDES:** nothing. Makes the 6-month boundary of OR-19 explicit.

---

## 84. OR-87 — Order of newness states in the REVIEW queue (S-08)
**Date:** 2026-10-01 · **Affects:** Round-3 sequence S-08 · **Effective:** `jobops-policy@0.2.4`
**Question:** Within the newness ordering key, what is the relative order of NEW, UPDATED and SEEN_BEFORE?
### RULING:
NEW > UPDATED > SEEN_BEFORE, strictly. There are no ties. Newness is the second ordering key, after relevance and before evidence completeness (OR-28), so it decides only between items of equal relevance. Overflow carry-forward and the STRONG exemption are unchanged (OR-29, OR-65). An item carried over from an earlier day is SEEN_BEFORE unless a material change makes it UPDATED.
**RATIONALE:** OR-28 made newness the second overflow key without stating the order of its states. 0.2.4 `queue.ordering[newness]` already lists `["NEW", "UPDATED", "SEEN_BEFORE"]`. Unseen requisitions are surfaced first. A materially changed requisition needs a fresh look, so it outranks one already seen unchanged, but not a never-seen one.
**SUPERSEDES:** nothing. Makes the 0.2.4 newness order an owner ruling. The S-08 corpus assumption ("NEW ranks above SEEN_BEFORE") is confirmed and is no longer an assumption.

---

**Addendum G status:** OR-84 … OR-87 recorded. No earlier content of this log was modified. No policy artifact was created or changed.

---

# Addendum H — P7b Round-3 follow-up: OR-88 and the Round-3 authoring defect (appended 2026-10-01)

**Source:** Owner command "JobOps v2 — P7b Follow-up: OR-88 + Round 3 Author-Correction Overlay" §3–§5.
**Recording rule:** append-only; numbering continues from OR-87. No earlier entry, including Addendum G, is rewritten.
**Effective policy version:** `jobops-policy@0.2.4`. No 0.2.5 is created; the 0.2.4 artifact and its accepted hash (`735934bf33533a31d207349cf689a3df6dafcdacc9c6a11b889b92e5af8c8136`) are untouched. 0.2.0–0.2.3 are unchanged.
**Corpus:** `data/fixtures/round3/blind_cases_round3.json`, SHA-256 `25aef0e0c0096d31231cc8ea96ea8c4796ba981c0160daa148ebeecad7c639cb` (unchanged).

| id | Corpus item | Item | Status |
|---|---|---|---|
| OR-88 | S-08 | D+3 overflow parking is time-based and unconditional | ☑ RULED (YES) |
| — | R3-004, 007, 011, 012, 014, 017, 018, 025, 026, 027, 029 | Round-3 authoring defect: expected-output corrections | ☑ RECORDED |

---

## 85. OR-88 — S-08 D+3 parking behaviour
**Date:** 2026-10-01 · **Affects:** Round-3 sequence S-08 · **Effective:** `jobops-policy@0.2.4`
**Question:** Does the D+3 parking rule apply unconditionally to a non-STRONG item, or only when the REVIEW queue has exhausted its daily capacity?
### RULING:
YES — D+3 parking is time-based and unconditional. A non-STRONG item reaching D+3 is PARKED regardless of whether the REVIEW queue currently has fewer than 10 items. The daily REVIEW cap of 10 is an independent capacity constraint; it does not override the D+3 parking rule. **D+3 + non-STRONG → PARKED**, even when the REVIEW queue size is < 10. The STRONG exemption (OR-29) and the carry counting of OR-65 (first overflow day D is carry day 1; eligible D+1 and D+2) are unchanged.
**RATIONALE:** The existing Addendum D language (OR-65) says a non-STRONG item is "PARKED at D+3". Reading this as conditional on queue capacity would introduce a new condition not stated by the existing rule.
**SUPERSEDES:** no ruling. It resolves the P7b SPEC_AMBIGUITY on S-08 and confirms the S-08 corpus expectation (N01 PARKED on 2026-09-27). Note: OR-65 described the then-existing queue behaviour as already implementing D+3 parking; the P7b measurement shows the 0.2.4 `plan_day` parks a carried item only when it overflows the cap again, so the implementation does not yet conform to OR-88 when the queue is below the cap. The 0.2.4 implementation is not altered by this ruling.

---

## Round-3 authoring defect — author expected-output corrections (R3-004, R3-007, R3-011, R3-012, R3-014, R3-017, R3-018, R3-025, R3-026, R3-027, R3-029)
**Date:** 2026-10-01 · **Found by:** P7b initial measurement (`docs/reports/JOBOPS_P7B_ROUND3_GATE_E_MEASUREMENT_2026-10-01.md`)
### RECORD:
The frozen Round-3 corpus contains an authoring defect in 11 posting cases. Each case's own `tests` label and `rationale` already specify geography FAIL, but the `expected` object carries `geography = PASS` and `excluded = false`. The defect was a failure to copy the intended FAIL verdict into the `expected` object. The intended expectation for each of the 11 cases is `geography = FAIL`, `excluded = true`; no other dimension, posting text, test label or rationale is affected.
- **The frozen corpus remains unchanged** and byte-identical; **its SHA-256 remains `25aef0e0c0096d31231cc8ea96ea8c4796ba981c0160daa148ebeecad7c639cb`.**
- The correction is represented by an external expected-output overlay, `data/fixtures/round3/blind_round3_expected_output_corrections.json` ("author expected-output corrections (authoring defect)", `applies_to_hash` = the frozen corpus SHA).
- This is a **corpus expected-output error, not an engine error.** These 11 cases are not engine failures.
- The overlay is for measurement only. It does not alter policy semantics, rulings, the corpus or its hash.
**SUPERSEDES:** nothing.

---

**Addendum H status:** OR-88 and the Round-3 authoring-defect record appended. No earlier content of this log was modified. No policy artifact was created or changed.
