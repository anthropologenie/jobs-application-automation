"""
Writes tests/fixtures/p10/tiers_export.json: an independently authored synthetic export (P10) whose REVIEW jobs
cover every presentation tier (T1, T2, T3, T4), more REVIEW units than the default cap of 10 (overflow), and
EXCLUDED jobs on several dimensions. Fictional companies and URLs only; no Round-3 / Round-4 content and no
real export data. Deterministic: re-running rewrites the same bytes.

    python3 tests/fixtures/p10/make_tiers_export.py
"""

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent / "tiers_export.json"

PRODUCT = "{co} builds and sells its own AI product for {domain}. "
WORK = ("You will design evaluation harnesses and golden datasets for our LLM assistants, measure groundedness and "
        "faithfulness of RAG answers, and add guardrails that catch hallucinations before release. Python, pytest "
        "and CI are part of the daily work. ")
EXP_OK = "Experience: 3 to 5 years in software testing or ML engineering."
EXP_STRETCH = "Experience: 5+ years in software testing or ML engineering."
PAY = "₹26 LPA – ₹32 LPA"


def job(n, title, co, domain, *, product=True, exp=EXP_OK, extra="", **fields):
    rec = {"id": f"p10-{n:03d}", "title": title, "companyName": co, "location": "Remote, India",
           "workplaceType": "Remote", "salary": PAY, "employmentType": "Full-time", "source": "linkedin",
           "postedAt": "2026-09-30",
           "description": (PRODUCT.format(co=co, domain=domain) if product else "") + WORK + extra + exp,
           "link": f"https://jobs.example-board.test/view/p10-{n:03d}"}
    rec.update(fields)
    return {k: v for k, v in rec.items() if v is not None}


RECORDS = [
    # SHORTLIST: every dimension PASS, complete JD.
    job(1, "AI Quality Engineer", "Morrowgate", "freight routing"),
    job(2, "LLM Evaluation Engineer", "Pebblecourt", "court scheduling"),
    # T1: pay not stated only.
    job(3, "AI Evaluation Engineer", "Hollowmere", "dental imaging", salary=None),
    job(4, "GenAI QA Engineer", "Brindlepath", "library catalogues", salary=None),
    job(5, "ML Test Engineer", "Coldharbour AI", "wind forecasting", salary=None),
    job(6, "AI Reliability Engineer", "Fennick", "parcel lockers", salary=None),
    # T1: employer unclassified only (no product statement), pay stated.
    job(7, "LLM Quality Engineer", "Dunmore Works", "", product=False),
    job(8, "Evaluation Engineer, GenAI", "Ashgrove Partners", "", product=False),
    # T1: employer unclassified and pay not stated.
    job(9, "AI Test Engineer", "Kestrel Row", "", product=False, salary=None),
    # T2: STRETCH experience, otherwise as T1 / clean.
    job(10, "Senior AI Quality Engineer", "Lanternfield", "grain storage", exp=EXP_STRETCH),
    job(11, "Senior LLM Evaluation Engineer", "Marshwick", "ferry ticketing", exp=EXP_STRETCH, salary=None),
    # T3: geography unclear (hybrid Bengaluru, office days not stated; no work arrangement at all).
    job(12, "AI Quality Engineer", "Nettlebank", "pharmacy stock", location="Bengaluru, Karnataka, India",
        workplaceType="Hybrid"),
    job(13, "LLM Test Engineer", "Oakhurst Digital", "event ticketing", location="Bengaluru, Karnataka, India",
        workplaceType="Hybrid", salary=None),
    job(14, "AI Evaluation Engineer", "Pikestaff", "water metering", location="India", workplaceType=None),
    # T3: work-mode conflict (structured Remote, JD says on-site).
    job(21, "GenAI Quality Engineer", "Wrenfold", "tide tables", location="Bengaluru, Karnataka, India",
        extra="This role is fully on-site at our Bengaluru office. "),
    # T4: employment type not stated; pay range starting below target; language requirement uncertain.
    job(15, "GenAI Test Engineer", "Quernstone", "solar billing", employmentType=None),
    job(16, "AI QA Engineer", "Rushmoor Labs", "clinic booking", salary="₹20 LPA – ₹30 LPA"),
    job(17, "LLM Quality Analyst", "Sedgefield AI", "museum guides", employmentType=None, salary=None),
    # EXCLUDED: on-site outside Bengaluru (geography); internship (employment).
    job(18, "AI Test Engineer", "Tollbridge", "port logistics", location="Mumbai, Maharashtra, India",
        workplaceType="On-site"),
    job(19, "AI Quality Intern", "Umberleigh", "crop insurance", employmentType="Internship"),
    # PARKED: weak relevance.
    job(20, "Frontend Developer", "Vintner Lane", "wine retail",
        description="Vintner Lane builds and sells its own product for wine retail. You will build React "
                    "components and CSS layouts for our storefront. Experience: 3 to 5 years."),
]


if __name__ == "__main__":
    OUT.write_text(json.dumps(RECORDS, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(OUT, len(RECORDS))
