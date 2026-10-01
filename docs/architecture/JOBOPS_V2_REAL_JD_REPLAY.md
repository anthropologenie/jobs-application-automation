# JobOps v2 — Offline real-JD replay and owner labelling (P6)

Use this workflow to validate the engine on **real** job descriptions without wiring any ingestion. Everything is offline: an in-memory database, no network, no LLM, no application submission. Real JDs and filled labels are git-ignored (`data/replay/`, `data/real_jds/`, `*owner_labels*.csv`) and must never be committed.

## 1. Export real JDs from Apify

1. In Apify, open a finished run of your job scraper and choose **Export → JSON** (or CSV).
2. Save the file outside git-tracked paths, e.g. `data/real_jds/linkedin-2026-10-01.json`.
3. Do not add any credentials or cookies to the export.

Alternatively, save each JD as its own `.txt` file in a folder such as `data/real_jds/batch1/`. Put the title on the first line and the JD on the lines after it.

## 2. Fields to keep

| JobOps field | Required | Purpose |
|---|---|---|
| `title` | **yes** | title tier (weak prior) |
| `description` | recommended | relevance, employment, language, office days; without it relevance is NOT_ASSESSED |
| `company`, `location`, `work_mode`, `employment_type`, `salary` | recommended | structured evidence (outranks JD text) |
| `url`, `source`, `posted_date` | optional | audit trail |
| `company_type` | optional | `product`, `ai_native`, `gcc`, `enterprise`, `staffing`, `consultancy`, `it_services`, `engineering_led`, `third_party_payroll` |

## 3. Create a mapping

1. Copy `tools/replay_mapping.example.json`.
2. Under `fields`, set each value to the column name (CSV) or key (JSON; dotted paths such as `company.name` work) in your export. Delete any field your export does not have.
3. Set `id` to the export's unique id field.
4. For JSON, set `records_key` if the list sits inside an object.

`.txt` folders need no mapping.

## 4. Run the replay

```bash
python3 tools/replay_real_jds.py data/real_jds/linkedin-2026-10-01.json \
    --mapping my_mapping.json --as-of 2026-10-01 --out data/replay/run-2026-10-01
python3 tools/replay_real_jds.py data/real_jds/batch1/ --as-of 2026-10-01          # .txt folder
python3 tools/replay_real_jds.py ... --policy jobops-policy@0.2.3                  # policy override
```

`--as-of` fixes the evaluation date, which drives FX staleness and the digest date. Use the same date to get a byte-identical rerun. The default policy is `evaluation.policy_loader.DEFAULT_VERSION`.

## 5. FX rates

1. Copy `data/fx/fx_rates.template.csv` to `data/fx/fx_rates.csv`.
2. Add one dated row per currency you need (`currency,rate_to_inr,snapshot_date,source`).
3. Pass `--fx data/fx/fx_rates.csv`.

Without an FX file, or without a row for a currency, a foreign-only salary stays **UNKNOWN + FX_RATE_UNAVAILABLE**. A snapshot more than 14 days older than `--as-of` is **UNKNOWN + FX_STALE**. The tool never invents a rate.

## 6. Outputs

The tool writes to `--out`, defaulting to `data/replay/run-<as-of>/`:

| File | What it is |
|---|---|
| `digest.md` | Per posting, grouped by lane: title, company, lane and the reason for it, relevance label with its term evidence, verdicts for geography, compensation, employment, employer and language each with a verbatim evidence span and rule id, experience label and flags. It ends with the **EXCLUDED AUDIT**. |
| `owner_labels.csv` | One row per posting: engine columns plus **empty** `owner_relevance`, `owner_eligibility` and `owner_lane`. |
| `results.json` | The same results in machine-readable form. |

## 7. Fill the owner labels

Open `owner_labels.csv` and, for each row, fill in:

- `owner_relevance`: `STRONG`, `MODERATE` or `WEAK`
- `owner_eligibility`: `PASS`, `FAIL` or `UNKNOWN`
- `owner_lane`: `SHORTLIST`, `REVIEW`, `PARKED` or `EXCLUDED`

Leave a cell empty if you have not decided; unlabelled rows are counted but not scored. You may also add `owner_geography`, `owner_compensation`, `owner_employment_type`, `owner_employer_type` and `owner_language` columns to get per-dimension agreement. Label from the JD and your own judgment, not from the engine columns.

## 8. Run the scorer

```bash
python3 tools/score_owner_labels.py data/replay/run-2026-10-01/owner_labels.csv --out data/replay/run-2026-10-01/score.md
```

The scorer reports:

- relevance: confusion matrix (engine × owner), STRONG precision and recall, MODERATE and WEAK agreement, and disagreement examples;
- eligibility: overall and per-dimension agreement, engine EXCLUDED vs owner eligibility, and engine PARKED vs owner labels;
- **safety rows**: engine EXCLUDED but owner eligible, and engine SHORTLIST but owner ineligible;
- JD length: quartiles, plus median length by owner relevance. This is descriptive only, not causal.

## 9. EXCLUDED audit

The `## EXCLUDED AUDIT` section answers *"what did JobOps throw away?"* without opening any database. Each row gives the posting id, title, company, the failing dimension, the verdict (FAIL), the exact evidence span and the rule id (for example `GEO-R03`, `EMP-R04`).

Review this section first on every run. Any row where you disagree is a potential false exclusion, and it also shows up in the scorer's safety table once you label it.

## 10. Gate E vs Gate R (OR-82)

- **Gate E (eligibility and safety)** measures geography, compensation, employment type, employer type and language, per dimension (≥ 95 %), plus zero unexplained false EXCLUDED and zero unexplained false SHORTLIST. It is measured on blind eligibility corpora (Round 2, then Round 3).
- **Gate R (relevance)** is measured only on owner-labelled real JDs using this workflow. The STRONG definition (≥ 3 AI-specific terms across ≥ 2 clusters, OR-78) is not tuned to any corpus.

The two gates are never combined into one score. Owner relevance labels do not feed Gate E.
