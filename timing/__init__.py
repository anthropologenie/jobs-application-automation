"""
JobOps Timing Package - P0-10 per-candidate time instrumentation

    machine events (P0-06 ledger, run manifests)  ─┐
    human decisions (P0-08 decisions.jsonl)        ├─→  per-candidate timeline
    application state (opportunities, read-only)   │         ↓
    submissions.jsonl (P0-10, human-recorded)     ─┘    metrics, with a state

Authority:
    P0_IMPLEMENTATION_SPEC.md 11          - stages, derived measures, discipline
    P0_IMPLEMENTATION_SPEC.md 13 X10      - time instrumentation
    timing/jobops-timing-0.1.0.json       - the measurement artifact

This package OBSERVES the funnel. It does not shape it. It evaluates no policy,
derives no verdict, assigns no lane, scores nothing, and performs zero database
writes - the database is opened read-only, so it cannot.

The one thing it persists is an explicit human-recorded submission event, in
data/application/submissions.jsonl, kept apart from the machine verdict, the
human decision and the application state because it is a fourth, different
fact. Recording a submission is not submitting one: JobOps never submits an
application, never contacts an employer or ATS, and never infers a submission
from any other action.

ACTIVE HUMAN EFFORT IS NOT DIRECTLY MEASURABLE here. Nothing observes when a
person started or stopped working on a candidate, so every duration is elapsed
wall-clock time between two recorded events, and every quantity that would
require effort as its denominator is reported NOT_MEASURABLE.
"""

__version__ = "1.0.0"
__author__ = "Karthik Shetty"

from .clock import (
    TimestampError,
    minutes_between,
    parse_date_only,
    parse_timestamp,
    utc_day,
    utc_now_iso,
)
from .lifecycle import ACCEPT, CandidateTimeline, LifecycleReader
from .metrics import TimingReport, count, distribution, per_day, rate, unmeasurable
from .ruleset import (
    INCONSISTENT,
    INSUFFICIENT_DATA,
    MEASURED,
    MEASUREMENT_STATES,
    NOT_AVAILABLE,
    NOT_MEASURABLE,
    TimingDriftError,
    TimingRuleset,
    load_timing_ruleset,
)
from .submissions import (
    ACTOR_HUMAN,
    EVENT_APPLICATION_SUBMITTED,
    SOURCE_HUMAN_STATED,
    SOURCE_RECORDED_NOW,
    SubmissionError,
    SubmissionEvent,
    SubmissionStore,
)

__all__ = [
    "TimestampError", "minutes_between", "parse_date_only", "parse_timestamp",
    "utc_day", "utc_now_iso",
    "ACCEPT", "CandidateTimeline", "LifecycleReader",
    "TimingReport", "count", "distribution", "per_day", "rate", "unmeasurable",
    "INCONSISTENT", "INSUFFICIENT_DATA", "MEASURED", "MEASUREMENT_STATES",
    "NOT_AVAILABLE", "NOT_MEASURABLE", "TimingDriftError", "TimingRuleset",
    "load_timing_ruleset",
    "ACTOR_HUMAN", "EVENT_APPLICATION_SUBMITTED", "SOURCE_HUMAN_STATED",
    "SOURCE_RECORDED_NOW", "SubmissionError", "SubmissionEvent",
    "SubmissionStore",
]
