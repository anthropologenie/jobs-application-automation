"""
P9 input normalisation: a locally downloaded JSON / CSV job export -> canonical records -> ObservationInput.

Deterministic and offline. Nothing is fetched, guessed or invented:
  * a field the export does not carry stays None;
  * URLs are preserved byte-for-byte; a search-results URL is never presented as an application URL;
  * an export whose schema cannot be mapped fails with SchemaError (no partial, misleading output).

The canonical fields and the aliases accepted for each are listed in ALIASES (and in docs/SOURCING_RUNBOOK.md).
"""

import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sources.base import ObservationInput

# Canonical field -> accepted export keys (first non-empty wins, in this order). Matching is exact on the
# key, then case-insensitive with "_", "-" and spaces ignored.
ALIASES: Dict[str, List[str]] = {
    "title": ["title", "job_title", "jobTitle", "position", "positionName", "position_name"],
    "company": ["company", "company_name", "companyName", "employer", "employer_name", "organization"],
    "location": ["location", "job_location", "jobLocation", "formattedLocation", "formatted_location"],
    "job_url": ["job_url", "jobUrl", "url", "link", "job_link", "jobLink", "posting_url", "postingUrl"],
    "apply_url": ["apply_url", "applyUrl", "application_url", "applicationUrl", "apply_link", "applyLink"],
    "description": ["description", "job_description", "jobDescription", "descriptionText", "description_text",
                    "jd", "jd_text"],
    "work_mode": ["work_mode", "workMode", "workplace_type", "workplaceType", "work_type", "workType",
                  "remote_type", "remoteType"],
    "compensation": ["compensation", "salary", "salary_text", "salaryText", "salary_range", "salaryRange",
                     "salaryInfo", "salary_info", "pay"],
    "employment_type": ["employment_type", "employmentType", "contract_type", "contractType", "job_type",
                        "jobType"],
    "source": ["source", "source_name", "sourceName", "platform", "site"],
    "posted_at": ["posted_at", "postedAt", "posted_date", "postedDate", "date_posted", "datePosted",
                  "published_at", "publishedAt", "listed_at", "listedAt"],
    "external_id": ["external_id", "externalId", "job_id", "jobId", "source_job_id", "id"],
    "description_truncated": ["description_truncated", "descriptionTruncated", "jd_truncated", "truncated"],
}
REQUIRED = ("title",)
ONE_OF = ("company", "job_url", "apply_url", "external_id")
CONTAINER_KEYS = ("items", "jobs", "results", "data", "records")

# A description ending in one of these was cut off by the source ("… see more").
TRUNCATION_MARKERS = re.compile(r"(?:…|\.\.\.|\bsee more|\bshow more|\bread more)\s*$", re.I)
# A URL that is a search-results page, not a posting or an application page.
SEARCH_URL = re.compile(r"/jobs/search\b|/search[/?]|[?&](?:keywords|q|query|search)=", re.I)
TRUTHY = {"1", "true", "yes", "y", "x"}

ATS_SOURCES = {"ats", "greenhouse", "lever", "ashby", "workday", "smartrecruiters", "workable", "recruitee"}
COMPANY_SITE_SOURCES = {"company_site", "company-site", "careers", "career_site", "company"}


class SchemaError(ValueError):
    """The export cannot be mapped onto the canonical contract. Nothing is produced."""


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _squash(key: str) -> str:
    return re.sub(r"[\s_\-]", "", key).lower()


def _scalar(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value if value.strip() else None
    # Nested structures are kept verbatim as compact JSON; nothing is interpreted out of them.
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _lookup(record: Dict[str, Any], field: str) -> Tuple[Optional[str], Optional[str]]:
    """(value, export key it came from)."""
    squashed = {_squash(k): k for k in record}
    for alias in ALIASES[field]:
        key = alias if alias in record else squashed.get(_squash(alias))
        if key is not None:
            value = _scalar(record[key])
            if value is not None:
                return value, key
    return None, None


def read_export(path: Path) -> List[Dict[str, Any]]:
    """Raw records from a .json / .jsonl / .csv export, in file order."""
    path = Path(path)
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8-sig")
    if suffix == ".csv":
        rows = list(csv.DictReader(text.splitlines()))
        if not rows:
            raise SchemaError(f"{path.name}: the CSV has a header but no rows, or no header")
        return [{k: v for k, v in r.items() if k is not None} for r in rows]
    if suffix == ".jsonl":
        try:
            data = [json.loads(line) for line in text.splitlines() if line.strip()]
        except json.JSONDecodeError as e:
            raise SchemaError(f"{path.name}: not valid JSON Lines ({e})") from e
    elif suffix == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise SchemaError(f"{path.name}: not valid JSON ({e})") from e
    else:
        raise SchemaError(f"{path.name}: unsupported file type {suffix!r} (use .json, .jsonl or .csv)")
    if isinstance(data, dict):
        container = next((k for k in CONTAINER_KEYS if isinstance(data.get(k), list)), None)
        if container is None:
            raise SchemaError(f"{path.name}: top-level JSON object has no list under any of {CONTAINER_KEYS}")
        data = data[container]
    if not isinstance(data, list) or not data:
        raise SchemaError(f"{path.name}: expected a non-empty list of job records")
    if not all(isinstance(r, dict) for r in data):
        raise SchemaError(f"{path.name}: every job record must be a JSON object")
    return data


def jd_status(description: Optional[str], truncated_flag: Optional[str]) -> str:
    if not description or not description.strip():
        return "JD_MISSING"
    if (truncated_flag or "").strip().lower() in TRUTHY or TRUNCATION_MARKERS.search(description.strip()):
        return "JD_TRUNCATED"
    return "JD_COMPLETE"


def is_search_url(url: Optional[str]) -> bool:
    return bool(url) and bool(SEARCH_URL.search(url))


def canonicalise(raw: Dict[str, Any], index: int) -> Dict[str, Any]:
    """One canonical record. `problems` lists why the record cannot be used (empty = usable)."""
    rec: Dict[str, Any] = {"index": index, "raw": raw, "mapped_from": {}}
    for field in ALIASES:
        value, key = _lookup(raw, field)
        rec[field] = value
        if key is not None:
            rec["mapped_from"][field] = key
    problems = [f"missing {f}" for f in REQUIRED if not rec[f]]
    if not any(rec[f] for f in ONE_OF):
        problems.append(f"needs at least one of {', '.join(ONE_OF)}")
    rec["problems"] = problems
    rec["jd_status"] = jd_status(rec["description"], rec["description_truncated"])
    # URL safety: preserved exactly; a search-results page is never an application URL.
    job_url = rec["job_url"] if not is_search_url(rec["job_url"]) else None
    apply_url = rec["apply_url"] if not is_search_url(rec["apply_url"]) else None
    rec["search_url_only"] = bool((rec["job_url"] or rec["apply_url"]) and not (job_url or apply_url))
    rec["application_url"] = apply_url or job_url  # exactly as supplied, or None (apply_url_missing)
    rec["source_url_kept"] = job_url
    rec["apply_url_kept"] = apply_url
    return rec


def map_schema(raws: List[Dict[str, Any]], name: str) -> List[Dict[str, Any]]:
    records = [canonicalise(r, i) for i, r in enumerate(raws)]
    if not any("title" in r["mapped_from"] for r in records):
        keys = sorted({k for r in raws for k in r})[:40]
        raise SchemaError(f"{name}: no record has a recognised title field. Accepted title keys: "
                          f"{ALIASES['title']}. Keys found in the export: {keys}")
    return records


def _source_kind(source: Optional[str]) -> str:
    s = (source or "").strip().lower()
    if s in ATS_SOURCES:
        return "EMPLOYER_ATS"
    if s in COMPANY_SITE_SOURCES:
        return "COMPANY_SITE"
    return "JOB_BOARD"


def _posted(value: Optional[str]) -> Optional[str]:
    m = re.match(r"^\d{4}-\d{2}-\d{2}(?:[T ][\d:.+\-Z]*)?$", (value or "").strip())
    return value.strip() if m else None


def to_observation(rec: Dict[str, Any], *, run_id: str, day: str) -> ObservationInput:
    completeness = {"JD_COMPLETE": "FULL_JD", "JD_TRUNCATED": "PARTIAL", "JD_MISSING": "SEARCH_ONLY"}[rec["jd_status"]]
    slug = re.sub(r"[^a-z0-9]+", "-", (rec["source"] or "export").lower()).strip("-") or "export"
    return ObservationInput(
        source=f"import:{slug}", source_kind=_source_kind(rec["source"]), observed_at=f"{day}T06:00:00+00:00",
        run_id=run_id, completeness=completeness, source_external_id=rec["external_id"],
        source_url=rec["source_url_kept"], apply_url=rec["apply_url_kept"],
        raw_title=rec["title"], raw_company=rec["company"], raw_location=rec["location"],
        raw_work_mode=rec["work_mode"], raw_salary=rec["compensation"],
        raw_employment_type=rec["employment_type"],
        raw_text=rec["description"] if rec["jd_status"] != "JD_MISSING" else None,
        source_posted_date=_posted(rec["posted_at"]))
