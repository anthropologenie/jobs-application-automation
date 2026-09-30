"""
JobOps Review Package - P0-08 candidate review queue

    candidate ledger (machine verdict)  ─┐
    scraped_jobs (read-only)             ├─→  lanes  →  human decision
    identity/ (duplicate relationships)  │              (append-only ledger)
    decisions.jsonl (human decisions)   ─┘

Authority:
    P0_IMPLEMENTATION_SPEC.md 9           - review queue, lanes, inspection set
    P0_IMPLEMENTATION_SPEC.md 5.2 / 5.3   - FAIL is retained; a verdict is immutable
    P0_IMPLEMENTATION_SPEC.md 8.4         - suppression at L1/L2/L4
    review/jobops-review-0.1.0.json       - the review presentation artifact

This package holds no policy and no identity rules. It never evaluates a
posting, never derives or overrides a verdict, and never scores or ranks by
fit. It opens the database read-only, so it cannot delete, merge, re-status or
"clean up" anything.

The only thing it persists is a human decision, appended to
data/review/decisions.jsonl - deliberately in a different store from the
machine verdict, so the two can never be confused for one another.

Nothing here submits an application or contacts anyone. That boundary is
permanent (P0_SPEC 9.4).
"""

__version__ = "1.0.0"
__author__ = "Karthik Shetty"

from .decisions import ACTOR_HUMAN, Decision, DecisionError, DecisionStore, utc_now_iso
from .ledger import (
    NOT_CAPTURED,
    CandidateEvidence,
    CandidateLedgerStore,
    LedgerError,
    LedgerObservation,
)
from .queue import QueueBuild, QueueEntry, ReviewQueue
from .ruleset import ReviewDriftError, ReviewRuleset, load_review_ruleset

__all__ = [
    "ACTOR_HUMAN", "Decision", "DecisionError", "DecisionStore", "utc_now_iso",
    "NOT_CAPTURED", "CandidateEvidence", "CandidateLedgerStore", "LedgerError",
    "LedgerObservation",
    "QueueBuild", "QueueEntry", "ReviewQueue",
    "ReviewDriftError", "ReviewRuleset", "load_review_ruleset",
]
