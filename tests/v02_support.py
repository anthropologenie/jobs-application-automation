"""
Shared helpers for the v0.2 test modules (not collected: no test_ prefix).

Every v0.2 test runs against a fresh in-memory SQLite database created by the
migration runner. The live runtime database and the legacy data/jobs-tracker.db
are never opened. Outbound network connections are refused for the duration of
each v0.2 test.
"""

import socket

import pytest

from evaluation.policy_loader import load_policy_v02
from evaluation.service import EvaluationService
from sources.base import ObservationInput
from store.db import connect
from store.migrate import MigrationRunner


class NetworkAttempted(AssertionError):
    pass


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Any attempt to open an outbound socket fails the test."""
    def refuse(*args, **kwargs):
        raise NetworkAttempted(f"network access attempted: {args!r}")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    yield


def fresh_service(policy=None):
    conn = connect(":memory:")
    MigrationRunner(conn).apply_pending()
    return EvaluationService(conn, policy or load_policy_v02())


OBS_FIELDS = set(ObservationInput.__dataclass_fields__)


def observation(**fields) -> ObservationInput:
    defaults = {"source": "ats:greenhouse", "source_kind": "EMPLOYER_ATS", "completeness": "FULL_JD",
                "observed_at": "2026-09-20T06:00:00+00:00", "run_id": "t-run-1",
                "raw_title": "AI Engineer", "raw_company": "Synthetic Product Co"}
    defaults.update({k: v for k, v in fields.items() if k in OBS_FIELDS})
    return ObservationInput(**defaults)


BASE_TEXT = "\n".join([
    "Synthetic Product Co builds and sells its own AI software product.",
    "Location: Remote - India.",
    "Salary: ₹26 LPA fixed base.",
    "Employment type: Full-time, permanent.",
    "Working language: English.",
    "Experience: 3 years building AI applications.",
    "You will build a RAG pipeline using embeddings, vector retrieval with BM25 hybrid search, reranking and "
    "LLM evaluation (groundedness, faithfulness) in Python and FastAPI, deployed with Docker and CI/CD.",
])
EN = {"detected_language": "en", "confidence": 0.99}
