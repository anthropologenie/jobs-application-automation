# Round 2 — Undetermined Cases

Each entry below is a question the Round 2 rulings sheet leaves open. Where the case record includes a `determined_subset`, it holds every expectation the rulings do settle.

| Case ID | Rule area | Unresolved question |
|---|---|---|
| R2-046 | Compensation / Lanes (S5, S6, S17) | Is `BELOW_TARGET` a **review flag** that sends an otherwise-clean case to REVIEW, or an **informational label** that leaves it in SHORTLIST? The rulings call `CTC_BASIS_UNVERIFIED` and `MONTHLY_ASSUMED` informational but say nothing about `BELOW_TARGET`. |
| R2-051 | Compensation / Lanes (S5, S17) | Is `COMPENSATION_REVIEW` a **review flag** that sends an otherwise-clean case to REVIEW, or informational? SHORTLIST requires "no review flag", but the rulings never say which flags are review flags. |
| R2-075 | Employment (S10, S11) | What `employment_type` verdict does an **Employer-of-Record** engagement get: PASS, UNKNOWN + flag, or FAIL as third-party payroll? Section 11 requires EOR coverage, but Section 10 gives it no verdict. An EOR is a payroll intermediary for the actual employer, not a placement at a client. |
| R2-076 | Employment (S10, S11) | Same EOR question as R2-075, with the EOR signal only in the JD body while the structured field says "Full-time". It is also unclear whether that JD signal overrides the structured field. |
| R2-SEQ-09 (run S9-R2) | Newness (S18, S19, S21) | When the same source goes from SEARCH_ONLY (no JD) to FULL_JD, is that a **JD-hash change** (UPDATED) or **enrichment of an unchanged requisition** (SEEN_BEFORE)? The step's verdict (PASS), relevance (STRONG) and lane (SHORTLIST) are settled; only its newness state is not. |
