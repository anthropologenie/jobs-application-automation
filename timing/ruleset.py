#!/usr/bin/env python3
"""
Timing Ruleset Loader - P0-10 artifact access layer

Loads and version-pins timing/jobops-timing-0.1.0.json, which declares the
MEASUREMENT contract: which events exist, what each timestamp means, which
metrics may be computed from them, and which quantities must be reported as
unmeasured.

This module is the only place that reads the timing artifact. It declares no
event of its own: an event this artifact does not describe cannot be recorded,
and a metric it does not declare cannot be reported. That is deliberate - the
failure mode this instrumentation exists to prevent is a number whose meaning
was decided in code and never written down.

Authority:
    timing/jobops-timing-0.1.0.json    (timing_version jobops-timing@0.1.0)
    P0_IMPLEMENTATION_SPEC.md 11       (time instrumentation)

Author: Karthik Shetty
Created: 2026-09-07
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# The five states any reported measurement may be in. Declared in the artifact
# under `measurement_states` and mirrored here as constants; `TimingRuleset`
# checks on load that the two agree, so a state cannot exist in code without a
# written meaning.
MEASURED = "MEASURED"
NOT_AVAILABLE = "NOT_AVAILABLE"
INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
NOT_MEASURABLE = "NOT_MEASURABLE"
INCONSISTENT = "INCONSISTENT"

MEASUREMENT_STATES = (MEASURED, NOT_AVAILABLE, INSUFFICIENT_DATA,
                      NOT_MEASURABLE, INCONSISTENT)

EXPECTED_TIMING_VERSION = "jobops-timing@0.1.0"
DEFAULT_TIMING_PATH = Path(__file__).resolve().parent / "jobops-timing-0.1.0.json"


class TimingDriftError(RuntimeError):
    """
    Raised when the timing artifact and this implementation disagree.

    An event kind the recorder does not know how to write, a metric the report
    does not know how to compute, or an unexpected artifact version stops the
    run rather than being skipped. A measurement layer that silently drops a
    metric is a measurement layer that reports a smaller funnel than exists.
    """


class TimingRuleset:
    """Read-only accessor for the versioned timing artifact."""

    def __init__(self, path: Optional[Path] = None, *,
                 expected_version: str = EXPECTED_TIMING_VERSION):
        self.path = Path(path) if path else DEFAULT_TIMING_PATH
        if not self.path.exists():
            raise FileNotFoundError(f"Timing artifact not found: {self.path}")

        with open(self.path, "r", encoding="utf-8") as f:
            self._doc: Dict[str, Any] = json.load(f)

        self.version: str = self._doc["artifact"]["timing_version"]
        if expected_version and self.version != expected_version:
            raise TimingDriftError(
                f"Timing artifact version mismatch: artifact is {self.version!r}, "
                f"this implementation is written against {expected_version!r}.")
        declared = set(self._doc["measurement_states"]) - {"note"}
        if declared != set(MEASUREMENT_STATES):
            raise TimingDriftError(
                f"Timing artifact declares measurement states {sorted(declared)}, "
                f"this implementation knows {sorted(MEASUREMENT_STATES)}. A state "
                "with no written meaning cannot be reported.")

        logger.info("Loaded timing ruleset %s from %s", self.version, self.path)

    # ---------------------------------------------------------------- events

    @property
    def events(self) -> List[Dict[str, Any]]:
        return list(self._doc["events"])

    @property
    def event_ids(self) -> List[str]:
        return [event["id"] for event in self._doc["events"]]

    def event(self, event_id: str) -> Dict[str, Any]:
        for event in self._doc["events"]:
            if event["id"] == event_id:
                return dict(event)
        raise TimingDriftError(
            f"Timing artifact declares no event {event_id!r}. Events are "
            "declared in the artifact, never invented in code.")

    @property
    def unobserved_event_ids(self) -> List[str]:
        return [event["id"] for event in self._doc["unobserved_events"]]

    def unobserved_event(self, event_id: str) -> Dict[str, Any]:
        for event in self._doc["unobserved_events"]:
            if event["id"] == event_id:
                return dict(event)
        raise TimingDriftError(
            f"Timing artifact declares no unobserved event {event_id!r}.")

    def is_human_event(self, event_id: str) -> bool:
        return self.event(event_id)["origin"].startswith("human")

    # --------------------------------------------------------------- metrics

    @property
    def metrics(self) -> List[Dict[str, Any]]:
        return list(self._doc["metrics"])

    @property
    def metric_ids(self) -> List[str]:
        return [metric["id"] for metric in self._doc["metrics"]]

    def metric(self, metric_id: str) -> Dict[str, Any]:
        for metric in self._doc["metrics"]:
            if metric["id"] == metric_id:
                return dict(metric)
        raise TimingDriftError(
            f"Timing artifact declares no metric {metric_id!r}. A metric with "
            "no declared meaning is a number nobody can audit.")

    def state_override(self, metric_id: str) -> Optional[str]:
        """
        A metric the artifact declares permanently unmeasurable.

        Read from the artifact rather than hard-coded, so that the day an
        observation mechanism is built, the artifact - not a scattered set of
        conditionals - is what changes.
        """
        return self.metric(metric_id).get("state_override")

    def min_sample(self, metric_id: str) -> int:
        return int(self.metric(metric_id).get("min_sample", 1))

    def measures_active_human_effort(self, metric_id: str) -> bool:
        return bool(self.metric(metric_id).get("is_active_human_effort", False))

    # ------------------------------------------------------------ populations

    @property
    def measurement_states(self) -> Dict[str, Any]:
        return dict(self._doc["measurement_states"])

    @property
    def population_rules(self) -> Dict[str, Any]:
        return dict(self._doc["population_rules"])

    @property
    def non_events(self) -> List[Dict[str, Any]]:
        return list(self._doc["non_events"])

    @property
    def exit_criterion_window_days(self) -> int:
        return int(self._doc["windows"]["exit_criterion_window_days"])

    @property
    def prohibited(self) -> List[str]:
        return list(self._doc["prohibited"])

    @property
    def raw(self) -> Dict[str, Any]:
        return self._doc


def load_timing_ruleset(path: Optional[Path] = None) -> TimingRuleset:
    return TimingRuleset(path)
