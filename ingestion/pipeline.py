#!/usr/bin/env python3
"""
P0-06 LinkedIn ingestion pipeline

    linkedin-search CLI
        -> raw-source capture (verbatim, run-scoped, never overwritten)
        -> normalization (policy.EvidenceNormalizer, via the gate)
        -> P0-02 HardEligibilityGate
        -> GateResult (PASS / UNKNOWN / FAIL, unchanged)
        -> candidate persistence in scraped_jobs

What this module is not
-----------------------
It is not a scorer, not a ranker, not an Opportunity Quality model, and not a
second policy implementation. Salary thresholds, work-mode classification,
UNKNOWN handling, compensation parsing and verdict precedence are all reached
through the policy package, which reads policy/jobops-policy-0.1.0.json.
data/resume_config.json is never read.

It is also not the deduplication system.

The P0-06 / P0-07 boundary, stated exactly
------------------------------------------
P0-06 implements ONE identity behaviour, and only because the repository's
existing import contract already provides it:

    L1, single-source only. scraped_jobs.external_id is UNIQUE; LinkedIn ids
    are namespaced into it as `linkedin:<id>`; writes use INSERT OR IGNORE.
    Consequence: re-running the same bounded query inserts no duplicate rows,
    and a posting already held is reported as skipped_existing.

Everything else in P0_IMPLEMENTATION_SPEC.md 8 is P0-07 and is NOT implemented
here:

    - L2 canonicalized posting URL matching, including rejecting fragment-only
      and listing-page URLs as identities
    - L3 (normalized_company, normalized_title, normalized_location) matching
    - L4 employer ATS requisition id matching
    - matching a candidate against existing `opportunities` rows, so something
      already applied to is not re-surfaced
    - `identity_uncertain` marking, probable-match linking and human surfacing
      for near-matches
    - cross-source matching and the synthetic second-source demonstration (X7)

A LinkedIn posting that also exists under a different portal, or under a
different URL, WILL be ingested again as a separate candidate by this pipeline.
That is P0-07's problem by design, not a defect here.

Author: Karthik Shetty
Created: 2026-08-31
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from policy import HardEligibilityGate

from .config import IngestionConfig, load_config
from .extraction import (
    is_remote_flag,
    locate_compensation_spans,
    locate_work_mode_spans,
    select_compensation_span,
    select_work_mode_span,
)
from .merge import SourceRecord, merge_source_records
from .linkedin_cli import (
    CliInvocation,
    LinkedInSearchCLI,
    RuntimeUnavailable,
    SourceRateLimited,
)
from .persistence import CandidateRow, CandidateStore
from .provenance import (
    SOURCE_MECHANISM,
    SOURCE_PORTAL,
    RawSourceStore,
    RunLedger,
    SourceProvenance,
    new_run_id,
    utc_now_iso,
)
from .rate_limit import CapReached, RateLimiter

logger = logging.getLogger(__name__)


@dataclass
class QuerySpec:
    """One bounded search. `limit` is a client-side cap the CLI applies."""
    location: str
    query: Optional[str] = None
    jobage: Optional[int] = None
    remote: Optional[str] = None
    page: int = 1
    limit: Optional[int] = None

    def as_dict(self) -> Dict[str, Any]:
        return {"location": self.location, "query": self.query,
                "jobage": self.jobage, "remote": self.remote,
                "page": self.page, "limit": self.limit}


class LinkedInIngestionPipeline:
    """
    One bounded ingestion run.

    Every collaborator is injectable so the whole pipeline can be exercised
    deterministically from fixtures, without `bun`, without a network call, and
    against a temporary database.
    """

    def __init__(self, *, config: Optional[IngestionConfig] = None,
                 gate: Optional[HardEligibilityGate] = None,
                 store: Optional[CandidateStore] = None,
                 cli: Optional[LinkedInSearchCLI] = None,
                 rate_limiter: Optional[RateLimiter] = None,
                 store_root: Optional[Path] = None,
                 run_id: Optional[str] = None,
                 dry_run: bool = False):
        self.config = config or load_config()
        self.gate = gate or HardEligibilityGate()
        self.normalizer = self.gate.normalizer
        self.store = store
        self.dry_run = dry_run

        self.run_id = run_id or new_run_id()
        self.store_root = Path(store_root) if store_root else self.config.store_root()
        self.raw_store = RawSourceStore(self.store_root, self.run_id)
        self.ledger = RunLedger(self.store_root, self.run_id)

        self.rate_limiter = rate_limiter or RateLimiter(
            self.config.caps, self.store_root / "state" / "linkedin-rate-limit.json")
        self.cli = cli or LinkedInSearchCLI(self.config, self.rate_limiter)

        self._cli_version: Optional[Dict[str, Any]] = None

    # -------------------------------------------------------------- preflight

    def preflight(self) -> Dict[str, Any]:
        """Verify the source and the database before anything is fetched."""
        self.cli.preflight()
        if self.store is not None:
            self.store.verify_schema()
        self._cli_version = self.cli.cli_version()
        return {"cli_version": self._cli_version,
                "row_counts_before": self.store.row_counts() if self.store else None}

    # ------------------------------------------------------------ normalization

    def _gate_input(self, sources: List[SourceRecord],
                    fetched_at: str) -> Dict[str, Any]:
        """
        Build the raw posting the policy normalizer consumes.

        Only located, verbatim spans are supplied. Nothing is filled in, nothing
        is defaulted, and no value the posting did not state is invented.

        The search and detail observations are combined by
        ingestion/merge.py, which enriches without erasing: a detail response
        that states nothing for a field cannot delete evidence the search
        result supplied. The first real run lost three genuine posting dates
        that way (defect D1), and every field's merge outcome is now recorded
        in provenance rather than being implicit in dictionary ordering.
        """
        merge_record = merge_source_records(sources)
        merged = merge_record.values
        description = merged.get("description")
        location = merged.get("location")
        job_url = merged.get("url")

        wm_body = locate_work_mode_spans(self.normalizer, description,
                                         source="jd_body", field_name="description")
        wm_location = locate_work_mode_spans(self.normalizer, location,
                                             source="portal_search_result",
                                             field_name="location")
        selected_body = select_work_mode_span(wm_body)
        selected_location = select_work_mode_span(wm_location)

        # The posting's own location string is a portal structured field about
        # THIS posting, so the artifact admits it as portal-asserted work mode.
        #
        # The --remote search flag is deliberately NOT used here. P0_SPEC 7.6 is
        # explicit that it is "a server-side volume reducer, not evidence": it is
        # a query-wide parameter, identical for every hit, and letting it stand
        # in as a portal claim would manufacture REMOTE for a posting whose body
        # and location both say nothing. It is retained in source_query for
        # provenance, and it is never work-mode evidence.
        portal_claim = selected_location.text if selected_location else None

        comp_spans = locate_compensation_spans(description, source="jd_body",
                                               field_name="description")
        selected_comp = select_compensation_span(self.normalizer, comp_spans)

        raw: Dict[str, Any] = {
            "candidate_id": self.config.external_id_for(str(merged.get("id"))),
            "source_ref": job_url,
            "source_fetched_at": fetched_at,
        }
        if selected_body:
            raw["work_mode_text"] = selected_body.text
        if portal_claim:
            raw["portal_work_mode_field"] = portal_claim
        if selected_comp:
            raw["compensation_text"] = selected_comp.text
            raw["compensation_source_ref"] = job_url
        # Key present, value possibly null: the CLI always emits `date`, so
        # "the source stated none" is distinguishable from "not captured".
        if "date" in merged:
            raw["posting_stated_at"] = merged.get("date")

        located = {
            "work_mode": [s.as_dict() for s in wm_body + wm_location],
            "work_mode_selected": selected_body.as_dict() if selected_body else None,
            "work_mode_portal_claim": portal_claim,
            "compensation": [s.as_dict() for s in comp_spans],
            "compensation_selected": selected_comp.as_dict() if selected_comp else None,
        }
        return {"gate_input": raw, "located_evidence": located, "merged": merged,
                "merge_record": merge_record}

    def _candidate_row(self, merged: Dict[str, Any], external_id: str,
                       comp_span: Optional[Dict[str, Any]]) -> CandidateRow:
        """
        Map a LinkedIn posting onto the repository's scraped_jobs representation.

        Source identity is preserved as LinkedIn; the posting URL is preserved
        verbatim; the located compensation span is preserved in salary_range as
        the source stated it. Scoring columns are left untouched.
        """
        tags = ", ".join(
            str(merged[key]) for key in ("jobFunction", "industries",
                                         "employmentType", "seniority")
            if merged.get(key)) or None
        return CandidateRow(
            external_id=external_id,
            source=self.config.source_name,
            job_title=merged.get("title") or "(untitled)",
            company=merged.get("company") or "(unknown)",
            job_url=merged.get("url") or "",
            location=merged.get("location"),
            description=merged.get("description"),
            tags=tags,
            salary_range=comp_span["verbatim_text"] if comp_span else None,
            posted_date=merged.get("date"),
        )

    # ------------------------------------------------------------------- run

    def _record_search(self, query: QuerySpec) -> Optional[CliInvocation]:
        invocation = self.cli.search(
            location=query.location, query=query.query, jobage=query.jobage,
            remote=query.remote, page=query.page, limit=query.limit)
        ref = self.raw_store.write(
            f"search-p{query.page}-{len(self.cli.invocations):03d}.json",
            invocation.as_raw_payload())
        self.ledger.queries.append({
            "spec": query.as_dict(),
            "command": self.cli.command_display(invocation),
            "outcome": invocation.outcome,
            "raw_payload_ref": ref,
            "fetched_at": invocation.finished_at,
        })
        if invocation.outcome != "ok":
            self.ledger.record_error("search", {
                "command": self.cli.command_display(invocation),
                "outcome": invocation.outcome,
                "exit_code": invocation.exit_code,
                "error": invocation.error,
                "raw_payload_ref": ref,
            })
            if invocation.outcome == "unparseable":
                self.ledger.counts["rejected_unparseable"] += 1
            return None
        return invocation

    def run(self, queries: List[QuerySpec]) -> Dict[str, Any]:
        """
        Execute one bounded run and return its summary.

        Caps terminate the run normally. A rate limit stops this source for the
        run and is recorded as rate_limited, never as broken. Neither raises to
        the caller, and neither is ever worked around by relaxing a limit.
        """
        preflight = self.preflight()
        row_counts_before = preflight["row_counts_before"]

        pending: List[Dict[str, Any]] = []
        try:
            for query in queries:
                if len(pending) >= self.config.caps.max_results_per_run:
                    self.ledger.terminating_condition = "max_results_per_run reached"
                    break

                invocation = self._record_search(query)
                if invocation is None:
                    continue

                results = self.cli.search_results(invocation)
                self.ledger.counts["returned_by_linkedin"] += len(results)
                if not results:
                    # Never silently read as "no jobs today" (P0_SPEC 7.4).
                    self.ledger.record_error("search", {
                        "outcome": "suspect_zero_results",
                        "command": self.cli.command_display(invocation),
                        "note": "Zero results returned. Recorded as suspect and "
                                "surfaced; not interpreted as an absence of jobs.",
                    })

                headroom = self.config.caps.max_results_per_run - len(pending)
                for posting in results[:headroom]:
                    external_id = self.config.external_id_for(str(posting.get("id")))
                    pending.append({
                        "posting": posting,
                        "external_id": external_id,
                        "query": query,
                        "search_raw_ref": self.ledger.queries[-1]["raw_payload_ref"],
                        "search_fetched_at": invocation.finished_at,
                    })

            # detail is fetched only for postings not already held. An identity
            # pre-filter, never a policy one - no posting is dropped here.
            known = (self.store.existing_external_ids([p["external_id"] for p in pending])
                     if self.store else set())
            for item in pending:
                item["already_held"] = item["external_id"] in known
                if item["already_held"]:
                    continue
                try:
                    detail_invocation = self.cli.detail(str(item["posting"].get("id")))
                except CapReached as cap:
                    self.ledger.terminating_condition = str(cap)
                    break
                ref = self.raw_store.write(
                    f"detail-{item['posting'].get('id')}.json",
                    detail_invocation.as_raw_payload())
                item["detail_raw_ref"] = ref
                item["detail_fetched_at"] = detail_invocation.finished_at
                if detail_invocation.outcome == "ok" and isinstance(
                        detail_invocation.parsed, dict):
                    item["detail"] = detail_invocation.parsed
                    self.ledger.counts["detail_fetched"] += 1
                else:
                    if detail_invocation.outcome == "unparseable":
                        self.ledger.counts["rejected_unparseable"] += 1
                    self.ledger.record_error("detail", {
                        "external_id": item["external_id"],
                        "outcome": detail_invocation.outcome,
                        "error": detail_invocation.error,
                        "raw_payload_ref": ref,
                    })

        except CapReached as cap:
            self.ledger.terminating_condition = str(cap)
        except SourceRateLimited as limited:
            self.ledger.terminating_condition = f"rate_limited: {limited}"
            self.ledger.record_error("source", {"outcome": "rate_limited",
                                                "note": str(limited)})

        rows = self._gate_and_build(pending)
        persistence = self._persist(rows)

        summary = {
            **self.ledger.summary(),
            "cli_version": self._cli_version,
            "rate_limiting": self.rate_limiter.summary(),
            "row_counts_before": row_counts_before,
            "row_counts_after": self.store.row_counts() if self.store else None,
            "persistence": persistence,
            "dry_run": self.dry_run,
        }
        paths = self.ledger.flush({
            "cli_version": self._cli_version,
            "rate_limiting": self.rate_limiter.summary(),
            "row_counts_before": row_counts_before,
            "row_counts_after": summary["row_counts_after"],
            "persistence": persistence,
            "policy_ruleset_version": self.gate.ruleset.version,
            "ingestion_config_version": self.config.version,
            "dry_run": self.dry_run,
            "dedup_boundary": self.config.raw["persistence"]["dedup_boundary"],
        })
        summary["evidence_paths"] = paths
        return summary

    def _gate_and_build(self, pending: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize, gate, and build the candidate row for each posting."""
        built: List[Dict[str, Any]] = []
        for item in pending:
            sources = [SourceRecord("search", item["posting"],
                                    item["search_fetched_at"])]
            if item.get("detail") is not None:
                sources.append(SourceRecord("detail", item["detail"],
                                            item.get("detail_fetched_at")))
            prepared = self._gate_input(
                sources,
                item.get("detail_fetched_at") or item["search_fetched_at"])
            self.ledger.counts["normalized"] += 1

            result = self.gate.evaluate_posting(prepared["gate_input"])
            self.ledger.counts[f"gate_{result.verdict.lower()}"] += 1

            provenance = SourceProvenance(
                source_portal=SOURCE_PORTAL,
                source_mechanism=SOURCE_MECHANISM,
                source_query=item["query"].as_dict(),
                source_fetched_at=item["search_fetched_at"],
                raw_payload_ref=item["search_raw_ref"],
                cli_version=self._cli_version or {},
                source_url=prepared["merged"].get("url"),
                detail_raw_payload_ref=item.get("detail_raw_ref"),
                detail_fetched_at=item.get("detail_fetched_at"),
            )
            comp_selected = prepared["located_evidence"]["compensation_selected"]
            row = self._candidate_row(prepared["merged"], item["external_id"],
                                      comp_selected)
            built.append({"item": item, "prepared": prepared, "result": result,
                          "provenance": provenance, "row": row})
        return built

    def _persist(self, built: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Write candidates, then record one provenance entry per posting.

        Every verdict is retained, FAIL included: a FAIL is retained with its
        reason codes and stays visible to the human (P0_SPEC 5.2). Retention is
        how the career doc's "flagged for manual review" outcome is achieved.
        """
        rows = [b["row"] for b in built]
        if self.dry_run or self.store is None:
            outcome = {"inserted": [], "skipped_existing": [], "inserted_count": 0,
                       "skipped_count": 0, "dry_run": True}
        else:
            outcome = self.store.insert_candidates(rows)
        inserted = set(outcome["inserted"])
        skipped = set(outcome["skipped_existing"])

        for b in built:
            external_id = b["row"].external_id
            if external_id in inserted:
                state = "inserted"
                self.ledger.counts["persisted"] += 1
            elif external_id in skipped:
                state = "skipped_existing"
                self.ledger.counts["skipped_existing"] += 1
            else:
                state = "not_written_dry_run" if (self.dry_run or self.store is None) \
                    else "not_written"

            result = b["result"]
            self.ledger.record_candidate({
                "candidate_id": result.candidate_id,
                "external_id": external_id,
                "source_portal": SOURCE_PORTAL,
                "provenance": b["provenance"].as_dict(),
                "extractor_version": self.config.version,
                "normalizer_version": self.gate.ruleset.version,
                "derived_fields": {
                    "job_title": "results[].title",
                    "company": "results[].company",
                    "job_url": "results[].url, the first observation (see "
                               "field_provenance)",
                    "location": "results[].location",
                    "posted_date": "results[].date, retained against an empty "
                                   "detail.date (see field_provenance)",
                    "description": "detail.description",
                    "tags": "detail.jobFunction|industries|employmentType|seniority",
                    "salary_range": "located span in detail.description",
                    "normalized_work_mode": "located span in detail.description "
                                            "and results[].location",
                },
                "located_evidence": b["prepared"]["located_evidence"],
                "field_provenance": b["prepared"]["merge_record"].as_dict(),
                "normalized_candidate_row": b["row"].as_dict(),
                "normalized_work_mode": result.normalized_work_mode,
                "is_remote_flag": is_remote_flag(result.normalized_work_mode),
                "is_remote_flag_note": "Legacy boolean projection only. The "
                                       "normalized enum is the system of record "
                                       "(P0_SPEC 4.3).",
                "gate_verdict": result.as_dict(),
                "persistence": {"table": self.config.candidate_table,
                                "outcome": state},
                "dedup": {"layer_applied": "L1 (source_portal, external_id)",
                          "p0_07_not_applied": True},
            })
        return outcome
