#!/usr/bin/env python3
"""
P0-06 Ingestion Configuration - the volume ceiling, read from an artifact

Every rate/volume constraint the LinkedIn adapter honours is declared in
ingestion/linkedin-ingestion-0.1.0.json and read through here. Nothing
volume-bearing is hardcoded in the adapter, so a cap can be inspected and
audited without reading Python, and raising one is a visible edit to a
versioned artifact rather than a line change buried in a subprocess call.

Caps are ceilings, not targets (P0_IMPLEMENTATION_SPEC.md 7.3). Reaching one
terminates the run normally and is reported in the run summary.

This module holds NO policy. The compensation threshold, the work-mode
vocabulary and the verdict rules live in policy/jobops-policy-0.1.0.json and
are reached only through the policy package. data/resume_config.json is never
read here or anywhere else in this package.

Author: Karthik Shetty
Created: 2026-08-31
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent / "linkedin-ingestion-0.1.0.json"

EXPECTED_CONFIG_VERSION = "linkedin-ingestion@0.1.0"


class IngestionConfigError(RuntimeError):
    """Raised when the ingestion config artifact is absent, stale, or unreadable."""


@dataclass(frozen=True)
class VolumeCaps:
    """
    The ceilings enforced against LinkedIn.

    Per-run caps bound one invocation. Daily caps are enforced from a persisted
    counter, so opening a second process does not reset them.
    """
    max_search_calls_per_run: int
    max_detail_calls_per_run: int
    max_pages_per_query: int
    max_results_per_run: int
    daily_max_search_calls: int
    daily_max_detail_calls: int
    min_interval_seconds: float
    concurrency: int

    def __post_init__(self) -> None:
        if self.concurrency != 1:
            raise IngestionConfigError(
                "concurrency must be 1. P0_SPEC 7.3 forbids concurrency against "
                "this source, and the adapter implements no parallel path."
            )


class IngestionConfig:
    """Read-only accessor for the versioned ingestion config artifact."""

    def __init__(self, path: Optional[Path] = None, *,
                 expected_version: str = EXPECTED_CONFIG_VERSION):
        self.path = Path(path) if path else DEFAULT_CONFIG_PATH
        if not self.path.exists():
            raise IngestionConfigError(f"Ingestion config not found: {self.path}")

        with open(self.path, "r", encoding="utf-8") as f:
            self._doc: Dict[str, Any] = json.load(f)

        self.version: str = self._doc["artifact"]["config_version"]
        if expected_version and self.version != expected_version:
            raise IngestionConfigError(
                f"Ingestion config version mismatch: artifact is {self.version!r}, "
                f"this implementation is written against {expected_version!r}."
            )

    # ------------------------------------------------------------------- cli

    @property
    def skill_dir(self) -> Path:
        return Path(self._doc["cli"]["skill_dir"]).expanduser()

    @property
    def entrypoint(self) -> str:
        return self._doc["cli"]["entrypoint"]

    @property
    def runtime(self) -> str:
        return self._doc["cli"]["runtime"]

    @property
    def runtime_args(self) -> List[str]:
        return list(self._doc["cli"]["runtime_args"])

    @property
    def results_per_page(self) -> int:
        return int(self._doc["cli"]["results_per_page"])

    # ----------------------------------------------------------------- caps

    @property
    def caps(self) -> VolumeCaps:
        v = self._doc["volume_caps"]
        return VolumeCaps(
            max_search_calls_per_run=int(v["max_search_calls_per_run"]),
            max_detail_calls_per_run=int(v["max_detail_calls_per_run"]),
            max_pages_per_query=int(v["max_pages_per_query"]),
            max_results_per_run=int(v["max_results_per_run"]),
            daily_max_search_calls=int(v["daily_max_search_calls"]),
            daily_max_detail_calls=int(v["daily_max_detail_calls"]),
            min_interval_seconds=float(v["min_interval_seconds"]),
            concurrency=int(v["concurrency"]),
        )

    # -------------------------------------------------------------- queries

    @property
    def query_buckets(self) -> List[str]:
        return list(self._doc["query_seeds"]["buckets"])

    @property
    def default_location(self) -> str:
        return self._doc["query_seeds"]["default_location"]

    @property
    def default_jobage_days(self) -> int:
        return int(self._doc["query_seeds"]["default_jobage_days"])

    @property
    def remote_filter(self) -> Optional[str]:
        return self._doc["query_seeds"].get("remote_filter")

    # ---------------------------------------------------------- persistence

    @property
    def candidate_table(self) -> str:
        return self._doc["persistence"]["candidate_table"]

    @property
    def source_name(self) -> str:
        return self._doc["persistence"]["source_name"]

    @property
    def external_id_namespace(self) -> str:
        return self._doc["persistence"]["external_id_namespace"]

    def external_id_for(self, linkedin_job_id: str) -> str:
        """
        Namespace a LinkedIn job id for scraped_jobs.external_id.

        scraped_jobs.external_id is UNIQUE across the whole table, not per
        source, so a bare numeric LinkedIn id could collide with a bare numeric
        id from another portal. Namespacing makes the L1 key (source_portal,
        external_id) representable in the existing column without a migration.
        """
        return f"{self.external_id_namespace}:{linkedin_job_id}"

    # ------------------------------------------------------------ provenance

    def store_root(self, repo_root: Optional[Path] = None) -> Path:
        root = Path(repo_root) if repo_root else REPO_ROOT
        return root / self._doc["provenance_store"]["root"]

    @property
    def scoring_enabled(self) -> bool:
        return bool(self._doc["scoring"]["enabled"])

    @property
    def raw(self) -> Dict[str, Any]:
        return self._doc


def load_config(path: Optional[Path] = None) -> IngestionConfig:
    return IngestionConfig(path)
