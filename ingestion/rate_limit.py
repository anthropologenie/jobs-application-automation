#!/usr/bin/env python3
"""
Rate and volume control for the LinkedIn source

Implements the four constraints P0_IMPLEMENTATION_SPEC.md 7.3 requires as
first-class configuration: a per-run cap on search and detail calls, a daily
cap enforced from a persisted counter, a minimum inter-request delay, and no
concurrency. Pagination beyond the configured page cap is refused here rather
than being left to the caller's discipline.

The governing rule is that caps are ceilings, not targets. `CapReached` is not
an error type - the pipeline catches it, records it as the run's terminating
condition, and reports it. Nothing in this module can raise a cap.

Author: Karthik Shetty
Created: 2026-08-31
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Optional

from .config import VolumeCaps

logger = logging.getLogger(__name__)


class CapReached(Exception):
    """
    A configured ceiling was reached.

    A normal terminating condition, not a failure. Carries the cap name and its
    value so the run summary can state exactly which ceiling stopped the run.
    """

    def __init__(self, cap_name: str, cap_value: int, scope: str):
        self.cap_name = cap_name
        self.cap_value = cap_value
        self.scope = scope
        super().__init__(
            f"{scope} cap reached: {cap_name}={cap_value}. This terminates the run "
            "normally. Raising the cap is an authorized change to "
            "ingestion/linkedin-ingestion-0.1.0.json, not a runtime decision."
        )


@dataclass
class DailyCounters:
    """Search/detail call counts for one UTC date, persisted across processes."""
    date: str
    search_calls: int = 0
    detail_calls: int = 0

    def as_dict(self) -> Dict[str, object]:
        return {"date": self.date, "search_calls": self.search_calls,
                "detail_calls": self.detail_calls}


class RateLimiter:
    """
    Enforces per-run caps, daily caps and the inter-request delay.

    `sleeper` and `clock` are injected so tests can assert that the delay is
    actually requested without waiting for it. Production uses time.sleep and
    time.monotonic.
    """

    def __init__(self, caps: VolumeCaps, state_path: Path, *,
                 sleeper: Callable[[float], None] = time.sleep,
                 clock: Callable[[], float] = time.monotonic,
                 today: Optional[str] = None):
        self.caps = caps
        self.state_path = Path(state_path)
        self._sleep = sleeper
        self._clock = clock
        self._today = today or datetime.now(timezone.utc).date().isoformat()
        self._last_request_at: Optional[float] = None

        self.run_search_calls = 0
        self.run_detail_calls = 0
        self.sleep_seconds_total = 0.0
        self.daily = self._load_counters()

    # ------------------------------------------------------------- persistence

    def _load_counters(self) -> DailyCounters:
        """
        Load today's counters. A stored counter for a different date is a
        previous day's total and starts over - it is never carried forward and
        never merged, which would understate today's remaining headroom.
        """
        if not self.state_path.exists():
            return DailyCounters(date=self._today)
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                doc = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            # An unreadable counter file must not silently grant a fresh budget.
            raise RuntimeError(
                f"Daily rate-limit counters at {self.state_path} are unreadable "
                f"({exc}). Refusing to run against LinkedIn with an unknown "
                "daily total. Inspect or delete the file deliberately."
            ) from exc
        if doc.get("date") != self._today:
            return DailyCounters(date=self._today)
        return DailyCounters(date=self._today,
                             search_calls=int(doc.get("search_calls", 0)),
                             detail_calls=int(doc.get("detail_calls", 0)))

    def _persist(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.daily.as_dict(), f, indent=2)
        tmp.replace(self.state_path)

    # ------------------------------------------------------------------ checks

    def check_page(self, page: int) -> None:
        if page > self.caps.max_pages_per_query:
            raise CapReached("max_pages_per_query", self.caps.max_pages_per_query, "run")

    def _wait(self) -> None:
        """Hold the minimum inter-request delay. The first request does not wait."""
        if self._last_request_at is None:
            self._last_request_at = self._clock()
            return
        elapsed = self._clock() - self._last_request_at
        remaining = self.caps.min_interval_seconds - elapsed
        if remaining > 0:
            self._sleep(remaining)
            self.sleep_seconds_total += remaining
        self._last_request_at = self._clock()

    def acquire_search(self) -> None:
        """Reserve one search call, or raise CapReached. Waits out the delay."""
        if self.run_search_calls >= self.caps.max_search_calls_per_run:
            raise CapReached("max_search_calls_per_run",
                             self.caps.max_search_calls_per_run, "run")
        if self.daily.search_calls >= self.caps.daily_max_search_calls:
            raise CapReached("daily_max_search_calls",
                             self.caps.daily_max_search_calls, "daily")
        self._wait()
        self.run_search_calls += 1
        self.daily.search_calls += 1
        self._persist()

    def acquire_detail(self) -> None:
        """Reserve one detail call, or raise CapReached. Waits out the delay."""
        if self.run_detail_calls >= self.caps.max_detail_calls_per_run:
            raise CapReached("max_detail_calls_per_run",
                             self.caps.max_detail_calls_per_run, "run")
        if self.daily.detail_calls >= self.caps.daily_max_detail_calls:
            raise CapReached("daily_max_detail_calls",
                             self.caps.daily_max_detail_calls, "daily")
        self._wait()
        self.run_detail_calls += 1
        self.daily.detail_calls += 1
        self._persist()

    # ----------------------------------------------------------------- summary

    def summary(self) -> Dict[str, object]:
        return {
            "caps": {
                "max_search_calls_per_run": self.caps.max_search_calls_per_run,
                "max_detail_calls_per_run": self.caps.max_detail_calls_per_run,
                "max_pages_per_query": self.caps.max_pages_per_query,
                "max_results_per_run": self.caps.max_results_per_run,
                "daily_max_search_calls": self.caps.daily_max_search_calls,
                "daily_max_detail_calls": self.caps.daily_max_detail_calls,
                "min_interval_seconds": self.caps.min_interval_seconds,
                "concurrency": self.caps.concurrency,
            },
            "run_search_calls": self.run_search_calls,
            "run_detail_calls": self.run_detail_calls,
            "daily_after_run": self.daily.as_dict(),
            "sleep_seconds_total": round(self.sleep_seconds_total, 3),
        }
