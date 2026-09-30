#!/usr/bin/env python3
"""
The metrics - computed only where the events exist, labelled with what they mean

Every number this module emits carries three things: a STATE, a sample size,
and the events it came from. That is the whole design.

    MEASURED           computed from events that exist. 0 here is a real zero.
    NOT_AVAILABLE      the mechanism exists; nothing has been recorded yet.
    INSUFFICIENT_DATA  some data, below the declared minimum sample.
    NOT_MEASURABLE     no observation mechanism exists at all.
    INCONSISTENT       events exist but are ordered so the interval is negative.

A bare number is never returned for a missing measurement, so no caller can
mistake "nothing happened yet" for "it took no time".

What is deliberately not computed
---------------------------------
ACTIVE HUMAN EFFORT IS NOT DIRECTLY MEASURABLE in this architecture. Nothing
observes when a person started or stopped attending to a candidate, so every
duration below is elapsed wall-clock time between two recorded moments, and
`applications_per_unit_of_human_effort` is reported NOT_MEASURABLE rather than
being faked by dividing by an elapsed interval.

Populations, kept apart on purpose
----------------------------------
  * The CURRENT EVALUATED FUNNEL - candidates carrying a gate verdict - is the
    population every duration and every verdict rate is computed over.
  * LEGACY NOT_EVALUATED rows are counted once, alone, and enter nothing else.
    They are not backfilled and no evaluation timestamp is invented for them.
  * Definite duplicates suppressed at L1/L2/L4 are excluded from active
    throughput, so re-observing one posting cannot inflate it.
  * L3 / uncertain probable duplicates ARE review opportunities - a human must
    judge them - and are also reported on their own.

Author: Karthik Shetty
Created: 2026-09-07
"""

import logging
import statistics
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .clock import parse_timestamp, utc_day, utc_now_iso
from .lifecycle import CandidateTimeline, LifecycleReader
from .ruleset import (
    INCONSISTENT,
    INSUFFICIENT_DATA,
    MEASURED,
    NOT_AVAILABLE,
    NOT_MEASURABLE,
    TimingRuleset,
    load_timing_ruleset,
)

logger = logging.getLogger(__name__)

# Below this sample size a p90 is a ranked observation, not a tail estimate.
_STABLE_TAIL_N = 10


def _p90(values: Sequence[float]) -> float:
    """Linear-interpolated 90th percentile. Exact for n == 1."""
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = 0.9 * (len(ordered) - 1)
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def count(value: int, *, counts: str, note: Optional[str] = None) -> Dict[str, Any]:
    """A count. Always MEASURED - a counted zero is a fact, not a gap."""
    return {"state": MEASURED, "value": int(value), "unit": "candidates",
            "counts": counts, "note": note}


def unmeasurable(metric_id: str, why: str) -> Dict[str, Any]:
    return {"state": NOT_MEASURABLE, "value": None, "metric": metric_id,
            "note": why}


def rate(metric_id: str, numerator: int, denominator: int, *,
         numerator_events: str, denominator_events: str,
         note: Optional[str] = None) -> Dict[str, Any]:
    """
    A rate, or an explicit statement that the denominator is empty.

    An empty denominator is INSUFFICIENT_DATA, never 0.0: "none of them
    converted" and "there were none" are different facts.
    """
    record = {
        "metric": metric_id,
        "numerator": int(numerator),
        "denominator": int(denominator),
        "numerator_events": numerator_events,
        "denominator_events": denominator_events,
        "unit": "ratio",
        "note": note,
    }
    if denominator == 0:
        record.update({"state": INSUFFICIENT_DATA, "value": None,
                       "why": "The denominator population is empty, so no rate "
                              "exists. This is not a rate of zero."})
    else:
        record.update({"state": MEASURED, "value": numerator / denominator})
    return record


def distribution(metric_id: str, ruleset: TimingRuleset,
                 timelines: Iterable[CandidateTimeline]) -> Dict[str, Any]:
    """
    Median and p90 minutes for one interval across candidates.

    Candidates are partitioned honestly: measured, waiting on an endpoint that
    was never recorded, inconsistent, or not applicable. Only the measured ones
    enter the statistics, and the other three counts are reported beside them so
    the sample can never be mistaken for the population.
    """
    override = ruleset.state_override(metric_id)
    metric = ruleset.metric(metric_id)

    samples: List[float] = []
    missing: List[str] = []
    inconsistent: List[str] = []
    for timeline in timelines:
        interval = timeline.intervals.get(metric_id)
        if interval is None:
            continue
        if interval["state"] == MEASURED:
            samples.append(interval["minutes"])
        elif interval["state"] == INCONSISTENT:
            inconsistent.append(timeline.candidate_ref)
        elif interval["state"] == NOT_AVAILABLE:
            missing.append(timeline.candidate_ref)

    record: Dict[str, Any] = {
        "metric": metric_id,
        "unit": "minutes",
        "start_event": metric.get("start_event"),
        "end_event": metric.get("end_event"),
        "measures": metric.get("measures"),
        "is_active_human_effort": ruleset.measures_active_human_effort(metric_id),
        "n": len(samples),
        "candidates_awaiting_an_event": len(missing),
        "candidates_with_inconsistent_events": len(inconsistent),
        "inconsistent_candidates": sorted(inconsistent),
        "note": metric.get("integrity_note"),
    }

    if override:
        record.update({"state": override, "median": None, "p90": None,
                       "why": metric.get("integrity_note")})
        return record

    if not samples:
        record.update({
            "state": NOT_AVAILABLE,
            "median": None,
            "p90": None,
            "why": (f"No candidate has both {metric.get('start_event')} and "
                    f"{metric.get('end_event')} recorded. The mechanism exists; "
                    "nothing has been recorded through it. This is not zero "
                    "minutes."),
        })
        return record

    if len(samples) < ruleset.min_sample(metric_id):
        record.update({"state": INSUFFICIENT_DATA, "median": None, "p90": None,
                       "why": f"{len(samples)} sample(s), below the declared "
                              f"minimum of {ruleset.min_sample(metric_id)}."})
        return record

    record.update({
        "state": MEASURED,
        "median": statistics.median(samples),
        "p90": _p90(samples),
        "min": min(samples),
        "max": max(samples),
    })
    if len(samples) < _STABLE_TAIL_N:
        record["p90_caveat"] = (
            f"n={len(samples)}: the p90 is a ranked observation, not a stable "
            "tail estimate. Reported because withholding it would hide the "
            "sample, not because it is a reliable tail.")
    return record


def per_day(days: Iterable[Optional[str]]) -> Dict[str, Any]:
    """
    Counts per UTC calendar day, plus the span the data actually covers.

    The span is reported so nobody divides a two-day sample by seven. A rate per
    day over a period shorter than the period is not computed.
    """
    observed = [day for day in days if day]
    buckets: Dict[str, int] = {}
    for day in observed:
        buckets[day] = buckets.get(day, 0) + 1
    if not buckets:
        return {"state": NOT_AVAILABLE, "by_day": {}, "days_with_activity": 0,
                "span_days": 0, "total": 0,
                "why": "No event of this kind has been recorded, so there is no "
                       "daily series. This is not a series of zeros."}
    first, last = min(buckets), max(buckets)
    span = (parse_timestamp(last).date() - parse_timestamp(first).date()).days + 1
    return {
        "state": MEASURED,
        "by_day": dict(sorted(buckets.items())),
        "days_with_activity": len(buckets),
        "first_day": first,
        "last_day": last,
        "span_days": span,
        "total": sum(buckets.values()),
        "mean_per_active_day": sum(buckets.values()) / len(buckets),
        "note": "mean_per_active_day divides by days on which something was "
                "recorded, not by calendar days. Days with no activity are "
                "absent from the series rather than recorded as zero, because "
                "nothing distinguishes 'reviewed nothing' from 'did not use "
                "JobOps that day'.",
    }


class TimingReport:
    """Computes the P0-10 report. Reads everything, writes nothing."""

    def __init__(self, *, db_path: Optional[Path] = None,
                 reader: Optional[LifecycleReader] = None,
                 ruleset: Optional[TimingRuleset] = None):
        self.ruleset = ruleset or load_timing_ruleset()
        self.reader = reader or LifecycleReader(db_path=db_path,
                                                ruleset=self.ruleset)

    # ----------------------------------------------------------- populations

    def _system_stages(self) -> Dict[str, Any]:
        """
        Run-level system cost, from the manifests P0-06 already writes.

        Per-candidate extraction, normalization and dedup timers do not exist
        (they would mean editing the ingestion pipeline, which P0-10 does not
        touch), so what is reported is run wall time, the candidate count it
        covered, and how much of it was deliberate rate-limit sleeping.
        """
        runs = []
        for manifest in self.reader.queue.ledger.run_manifests():
            started = parse_timestamp(manifest.get("started_at"))
            finished = parse_timestamp(manifest.get("finished_at"))
            counts = manifest.get("counts") or {}
            returned = next((v for k, v in counts.items()
                             if k.startswith("returned_by_")), None)
            wall = ((finished - started).total_seconds()
                    if started and finished else None)
            candidates = counts.get("normalized")
            runs.append({
                "run_id": manifest.get("run_id"),
                "started_at": manifest.get("started_at"),
                "finished_at": manifest.get("finished_at"),
                "wall_seconds": wall,
                "records_returned_by_source": returned,
                "candidates_normalized": candidates,
                "seconds_per_candidate": (wall / candidates
                                          if wall and candidates else None),
                "rate_limit_sleep_seconds": (
                    (manifest.get("rate_limiting") or {}).get("sleep_seconds_total")),
                "counts": counts,
            })
        return {
            "runs": runs,
            "per_candidate_stage_timers": unmeasurable(
                "per_candidate_system_stage_timers",
                self.ruleset.unobserved_event(
                    "PER_CANDIDATE_SYSTEM_STAGE_TIMERS")["why_not_observed"]),
        }

    # --------------------------------------------------------------- compute

    def build(self) -> Dict[str, Any]:
        queue_build = self.reader.queue.build()
        timelines = self.reader.timelines(queue_build)

        evaluated = [t for t in timelines if t.verdict_available]
        # Two different facts, kept apart: a row with no verdict that the human
        # is still shown (the NOT_EVALUATED lane), and a row with no verdict
        # that identity suppressed because it is already in opportunities.
        # Counting the second in the first would report 77 where the queue
        # shows 75.
        unevaluated = [t for t in timelines if not t.verdict_available]
        legacy = [t for t in unevaluated if not t.suppressed]
        legacy_suppressed = [t for t in unevaluated if t.suppressed]
        suppressed = [t for t in timelines if t.suppressed]
        active = [t for t in timelines if t.in_active_funnel]
        probable = [t for t in active if t.probable_duplicate]

        by_verdict = {verdict: [t for t in active if t.verdict == verdict]
                      for verdict in ("PASS", "UNKNOWN", "FAIL")}
        accepted = [t for t in timelines if t.standing_accept]
        reviewed = [t for t in timelines if t.human["reviewed"]]
        reviewed_active = [t for t in active if t.human["reviewed"]]
        submitted = [t for t in timelines if t.submission]
        promoted = [t for t in active
                    if t.events["APPLICATION_PROMOTED"]["observed"]]

        decision_records = sum(t.human["decision_count"] for t in timelines)
        ingested = [t for t in evaluated if t.events["CANDIDATE_INGESTED"]["observed"]]

        system = self._system_stages()
        discovered = [r["records_returned_by_source"] for r in system["runs"]
                      if r["records_returned_by_source"] is not None]

        funnel = {
            "candidates_discovered": (
                count(sum(discovered), counts="records returned by ingestion "
                                             "runs, from run manifests",
                      note="Records returned, not distinct candidates. The "
                           f"{len(unevaluated)} pre-P0-06 rows predate the "
                           "ingestion ledger and have no discovery record; "
                           "they are not included here.")
                if discovered else
                {"state": NOT_AVAILABLE, "value": None,
                 "why": "No run manifest records a source return count."}),
            "candidates_ingested": count(
                len(ingested), counts="evaluated candidates that became a "
                                      "scraped_jobs row"),
            "candidates_evaluated": count(
                len(evaluated), counts="distinct candidates with a gate verdict "
                                       "(the current evaluated funnel)"),
            "distinct_review_candidates": count(
                len(active), counts="evaluated candidates in an ACTIVE lane "
                                    "(definite duplicates excluded)"),
            "candidates_human_reviewed": count(
                len(reviewed), counts="distinct candidates with at least one "
                                      "recorded human decision",
                note="Reading a candidate without deciding leaves no trace, so "
                     "this under-counts review. It never over-counts it."),
            "candidates_human_reviewed_in_active_funnel": count(
                len(reviewed_active),
                counts="reviewed candidates that are also in the active "
                       "evaluated funnel"),
            "human_decisions": count(
                decision_records, counts="decision records in "
                                         "data/review/decisions.jsonl, "
                                         "superseded ones included"),
            "human_decisions_standing": count(
                len([t for t in timelines if t.human["standing_decision"]]),
                counts="candidates whose standing decision is not superseded"),
            "applications_promoted_from_evaluated_funnel": count(
                len(promoted), counts="active-funnel candidates with an "
                                      "opportunities row created by the bridge",
                note="Promotion into the application workflow. Not submission."),
            "actual_submissions": count(
                len(submitted), counts="standing APPLICATION_SUBMITTED records "
                                       "in data/application/submissions.jsonl",
                note="Recorded by a human who states they submitted the "
                     "application themselves. JobOps submits nothing."),
            "accepted_without_submission_record": count(
                len([t for t in accepted if not t.submission]),
                counts="candidates with a standing ACCEPT and no submission "
                       "record",
                note="These contribute to no duration. An ACCEPT is not a "
                     "submission and is never completed into one."),
            "legacy_not_evaluated_count": count(
                len(legacy), counts="scraped_jobs rows no gate evaluation "
                                    "covers",
                note="Reported alone. Excluded from candidates_evaluated, from "
                     "every duration, from every verdict rate and from every "
                     "throughput figure. Not backfilled; no evaluation "
                     "timestamp is invented for them."),
            "legacy_rows_suppressed_as_duplicates": count(
                len(legacy_suppressed),
                counts="unevaluated rows that identity suppressed because they "
                       "are already represented in opportunities",
                note="Counted here rather than in legacy_not_evaluated_count, "
                     "so the two populations sum to the rows that exist "
                     "without double-counting either."),
            "definite_duplicates_suppressed": count(
                len(suppressed), counts="candidates suppressed from the active "
                                        "queue at L1/L2/L4",
                note="Excluded from distinct_review_candidates so that "
                     "re-observing one posting cannot inflate throughput."),
            "probable_duplicates_needing_human_judgement": count(
                len(probable), counts="active-lane candidates whose identity "
                                      "outcome is PROBABLE_DUPLICATE or "
                                      "IDENTITY_UNCERTAIN",
                note="Counted as real review opportunities: a human must "
                     "decide. Never suppressed, never called definite."),
        }

        durations = {
            metric_id: distribution(metric_id, self.ruleset, timelines)
            for metric_id in ("time_from_evaluation_to_decision",
                              "time_from_queue_availability_to_decision",
                              "time_from_unknown_to_human_resolution",
                              "time_from_decision_to_submission",
                              "time_from_evaluation_to_submission",
                              "time_from_decision_to_promotion")
        }

        rates = {
            "unknown_rate": rate(
                "unknown_rate", len(by_verdict["UNKNOWN"]), len(active),
                numerator_events="CANDIDATE_EVALUATED with verdict UNKNOWN",
                denominator_events="active-lane evaluated candidates"),
            "pass_to_apply_rate": rate(
                "pass_to_apply_rate",
                len([t for t in by_verdict["PASS"] if t.standing_accept]),
                len(by_verdict["PASS"]),
                numerator_events="standing ACCEPT on a PASS candidate",
                denominator_events="active-lane PASS candidates"),
            "unknown_to_apply_rate": rate(
                "unknown_to_apply_rate",
                len([t for t in by_verdict["UNKNOWN"] if t.standing_accept]),
                len(by_verdict["UNKNOWN"]),
                numerator_events="standing ACCEPT on an UNKNOWN candidate",
                denominator_events="active-lane UNKNOWN candidates",
                note="Applying to an UNKNOWN does not make it a PASS. A rising "
                     "value here is a degradation signal (P0_SPEC 11.5), not a "
                     "throughput win."),
            "fail_to_application_rate": rate(
                "fail_to_application_rate",
                len([t for t in by_verdict["FAIL"] if t.standing_accept]),
                len(by_verdict["FAIL"]),
                numerator_events="standing ACCEPT on a FAIL candidate",
                denominator_events="active-lane FAIL candidates"),
            "definite_duplicate_suppression": rate(
                "definite_duplicate_suppression", len(suppressed), len(timelines),
                numerator_events="candidates suppressed at L1/L2/L4",
                denominator_events="all candidates the queue considered"),
        }

        throughput = {
            "candidates_reviewed_per_period": per_day(
                {t.candidate_ref: t.decision_day for t in reviewed}.values()),
            "decisions_per_period": per_day(t.decision_day for t in timelines),
            "submissions_per_period": per_day(t.submission_day for t in submitted),
            "applications_per_unit_of_human_effort": unmeasurable(
                "applications_per_unit_of_human_effort",
                self.ruleset.metric(
                    "applications_per_unit_of_human_effort")["integrity_note"]),
        }

        return {
            "built_at": utc_now_iso(),
            "timing_version": self.ruleset.version,
            "review_version": queue_build.review_version,
            "identity_version": queue_build.identity_version,
            "sources": self._sources(queue_build),
            "populations": self._populations(evaluated, legacy, active, suppressed),
            "funnel": funnel,
            "durations": durations,
            "rates": rates,
            "reporting_discipline": self._reporting_discipline(active),
            "throughput": throughput,
            "system_stages": system,
            "application_state": self.reader.application_state_summary(),
            "window": self._window(throughput),
            "not_measurable": self._not_measurable(),
            "limitations": self._limitations(),
        }

    # ---------------------------------------------------------------- blocks

    def _sources(self, queue_build) -> Dict[str, Any]:
        return {
            "machine_verdict": str(self.reader.queue.ledger.candidates_dir),
            "human_decision": str(self.reader.queue.decisions.path),
            "application_state": f"{self.reader.db_path} :: opportunities "
                                 "(read-only)",
            "submission_event": str(self.reader.submissions.path),
            "candidate_rows": f"{self.reader.db_path} :: scraped_jobs (read-only)",
            "queue": f"review {queue_build.review_version}, rebuilt for this "
                     "report",
            "writes_performed_by_this_report": "none",
        }

    def _populations(self, evaluated, legacy, active, suppressed) -> Dict[str, Any]:
        return {
            "current_evaluated_funnel": {
                "candidates": len(evaluated),
                "active": len(active),
                "definition": "Candidates carrying a gate verdict. Every "
                              "duration and every verdict rate is computed over "
                              "this population and no other.",
            },
            "legacy_not_evaluated": {
                "candidates": len(legacy),
                "definition": "Rows no gate evaluation covers - they predate "
                              "P0-02 or never went through the P0-06 pipeline.",
                "treatment": "Counted here and nowhere else. Never backfilled, "
                             "never given an invented evaluation timestamp, "
                             "never presented as newly evaluated.",
            },
            "suppressed_definite_duplicates": {
                "candidates": len(suppressed),
                "treatment": "Retained and retrievable; excluded from active "
                             "throughput so a re-observation cannot inflate it.",
            },
        }

    def _reporting_discipline(self, active) -> Dict[str, Any]:
        """
        P0_SPEC 11.4(2) and 11.4(3): never aggregate-only.

        Veto rate per reason code, because an over-broad rule and a correctly
        strict market are indistinguishable in aggregate. Unknown rate per
        dimension, because a blended figure hides which policy question the
        source cannot answer.
        """
        per_code: Dict[str, int] = {}
        for timeline in active:
            if timeline.verdict == "FAIL":
                for code in timeline.reason_codes:
                    per_code[code] = per_code.get(code, 0) + 1

        per_dimension: Dict[str, int] = {}
        for timeline in active:
            for dimension, verdict in timeline.dimension_verdicts.items():
                if verdict == "UNKNOWN":
                    per_dimension[dimension] = per_dimension.get(dimension, 0) + 1

        denominator = len(active)
        return {
            "veto_rate_per_reason_code": {
                code: rate("veto_rate_per_reason_code", n, denominator,
                           numerator_events=f"FAIL carrying {code}",
                           denominator_events="active-lane evaluated candidates")
                for code, n in sorted(per_code.items())
            } or {"state": NOT_AVAILABLE,
                  "why": "No FAIL verdict exists in the active funnel yet."},
            "unknown_rate_per_dimension": {
                dimension: rate("unknown_rate_per_dimension", n, denominator,
                                numerator_events=f"UNKNOWN on {dimension}",
                                denominator_events="active-lane evaluated "
                                                   "candidates")
                for dimension, n in sorted(per_dimension.items())
            } or {"state": NOT_AVAILABLE,
                  "why": "No dimension verdict is UNKNOWN in the active funnel."},
        }

    def _window(self, throughput) -> Dict[str, Any]:
        required = self.ruleset.exit_criterion_window_days
        decisions = throughput["decisions_per_period"]
        span = decisions.get("span_days", 0)
        return {
            "required_days_for_exit_criterion": required,
            "observed_span_days_of_human_events": span,
            "meets_exit_criterion_window": span >= required,
            "note": "X10 requires at least 7 days of data. A shorter span is "
                    "never extrapolated to a daily rate.",
        }

    def _not_measurable(self) -> List[Dict[str, Any]]:
        return [
            {"quantity": event_id,
             "why": self.ruleset.unobserved_event(event_id).get(
                 "why_not_observed"),
             "consequence": self.ruleset.unobserved_event(event_id).get(
                 "consequence")}
            for event_id in self.ruleset.unobserved_event_ids
        ]

    def _limitations(self) -> List[str]:
        return [
            "ACTIVE HUMAN EFFORT IS NOT DIRECTLY MEASURABLE. No event observes "
            "when a person started or stopped attending to a candidate. Every "
            "duration reported here is elapsed wall-clock time between two "
            "recorded moments, and none of them is review time or effort.",
            "Human review start is not observed, so time_from_queue_availability"
            "_to_decision is NOT_MEASURABLE rather than approximated from the "
            "run-close lower bound.",
            "A candidate the human read and did not decide on leaves no trace, "
            "so candidates_human_reviewed under-counts review.",
            "submitted_at is stated by the human. A record made days later with "
            "an accurate timestamp and one made at the moment of submission are "
            "distinguishable only by submitted_at_source and recorded_at, both "
            "of which are on every record.",
            "scraped_jobs.scraped_at and opportunities.created_at are stored "
            "without a timezone offset and are read as UTC, which is what "
            "SQLite's CURRENT_TIMESTAMP writes.",
            "opportunities.status transitions are not timestamped and "
            "applied_date is day precision, so no interval uses either.",
            "OR-09 and OR-10 remain open: what the ~15/day baseline counted, and "
            "whether 25-30 means surfaced or submitted. Both quantities are "
            "reported separately here and neither is asserted as a target.",
        ]
