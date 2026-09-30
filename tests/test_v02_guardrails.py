"""Phase B scope guardrails, asserted structurally over the v2 packages."""

import ast
import json
from pathlib import Path

from evaluation.policy_loader import DEFAULT_POLICY_PATH
from policy.ruleset import EXPECTED_RULESET_VERSION
from v02_support import no_network  # noqa: F401

REPO = Path(__file__).resolve().parent.parent
V2_PACKAGES = ("evaluation", "relevance", "geo", "company", "store", "sources", "digest", "ops")


def _modules():
    for pkg in V2_PACKAGES:
        yield from (REPO / pkg).rglob("*.py")


def test_no_subprocess_scheduler_or_browser_in_v2_packages():
    forbidden = {"subprocess", "sched", "crontab", "schedule", "apscheduler", "selenium", "playwright", "webbrowser",
                 "smtplib", "ftplib"}
    for path in _modules():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else (
                [node.module] if isinstance(node, ast.ImportFrom) and node.module else [])
            for n in names:
                assert n.split(".")[0] not in forbidden, (path, n)


def test_no_application_submission_code_path():
    for path in _modules():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                assert not node.name.lower().startswith(("submit", "apply_to", "send_application")), (path, node.name)


def test_no_source_adapter_implementations_exist():
    files = sorted(p.name for p in (REPO / "sources").glob("*.py"))
    assert files == ["__init__.py", "base.py"]


def test_v01_engine_stays_pinned_and_default_v2_policy_is_022():
    # Default switched from 0.2.0 to 0.2.1 in P1a, and from 0.2.1 to 0.2.2 in P3,
    # each time only after that version's acceptance conditions passed.
    assert EXPECTED_RULESET_VERSION == "jobops-policy@0.1.0"
    doc = json.loads(DEFAULT_POLICY_PATH.read_text(encoding="utf-8"))
    assert doc["artifact"]["ruleset_version"] == "jobops-policy@0.2.2"


def test_020_remains_loadable_for_replay():
    from evaluation.policy_loader import load_policy_version
    assert load_policy_version("jobops-policy@0.2.0").version == "jobops-policy@0.2.0"
    assert load_policy_version("jobops-policy@0.2.1").version == "jobops-policy@0.2.1"


def test_draft_policy_remains_outside_the_loader_directory():
    assert (REPO / "docs" / "architecture" / "drafts" / "jobops-policy-0.2.0.draft.json").exists()
    assert not (REPO / "policy" / "jobops-policy-0.2.0.draft.json").exists()


def test_runtime_database_is_git_ignored():
    ignore = (REPO / ".gitignore").read_text(encoding="utf-8")
    assert "data/runtime/" in ignore
    assert "data/jobs-tracker.db" in ignore
