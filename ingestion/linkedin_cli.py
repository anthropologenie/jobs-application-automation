#!/usr/bin/env python3
"""
LinkedIn CLI adapter - subprocess invocation with a stdout-JSON contract

Invokes the repository-approved linkedin-search CLI (OR-08, Path A) as a
subprocess and owns everything downstream of stdout. No module of
`ai-job-search` is imported: not its skill framework, not its agent dispatch,
not its file-based state (`seen_jobs.json`, `job_search_tracker.csv`). JS-R3
stands (P0_IMPLEMENTATION_SPEC.md 7.2).

The adapter's responsibilities are exactly the ones 7.2 assigns it: invocation,
rate limiting, retry policy above the CLI's own, raw capture, source
attribution, and failure classification.

It performs NO policy evaluation and discards NO posting for a policy reason.
Work mode and compensation are never read here.

Failure classification follows 7.4:

    exit 1 with {"error","code"}   record verbatim, continue the run
    429 / block page              stop this source for the run, `rate_limited`,
                                  never `broken`
    zero results                  `suspect`, surfaced - never "no jobs today"
    bun unavailable               explicit failure, no fallback to another
                                  source (a source substitution is a governance
                                  decision, not a runtime one)
    malformed JSON                raw retained, marked `unparseable`, excluded
                                  from normalization, surfaced

Author: Karthik Shetty
Created: 2026-08-31
"""

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .config import IngestionConfig
from .provenance import utc_now_iso

logger = logging.getLogger(__name__)

# stderr codes / message fragments that mean "LinkedIn is throttling or
# blocking", not "the CLI is broken". Per /scrape Step 4.75 as quoted in
# P0_SPEC 7.4, a 429 or block page is never evidence of breakage.
_RATE_LIMIT_MARKERS = (
    "429", "too many requests", "rate limit", "rate-limited",
    "blocked", "captcha", "999",
)

DEFAULT_TIMEOUT_SECONDS = 90


class RuntimeUnavailable(RuntimeError):
    """
    The CLI's runtime (`bun`) is not on PATH.

    Raised rather than handled: P0_SPEC 7.4 requires an explicit failure with a
    clear diagnostic and forbids a silent fallback to another source.
    """


class SourceRateLimited(RuntimeError):
    """LinkedIn returned 429 or a block page. This source stops for the run."""


@dataclass
class CliInvocation:
    """One subprocess call, retained verbatim as the raw source record."""
    command: List[str]
    cwd: str
    started_at: str
    finished_at: str
    exit_code: int
    stdout: str
    stderr: str
    outcome: str            # ok | error | rate_limited | unparseable
    parsed: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None

    def as_raw_payload(self) -> Dict[str, Any]:
        """
        The verbatim record retained in the raw store.

        stdout and stderr are kept as received, unparsed and untruncated, so the
        capture can reconstruct exactly what ingestion received - including in
        the unparseable case, where the parsed view does not exist.
        """
        return {
            "command": list(self.command),
            "cwd": self.cwd,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "outcome": self.outcome,
            "error": self.error,
        }


def _subprocess_runner(command: List[str], cwd: Path,
                       timeout: int) -> "subprocess.CompletedProcess[str]":
    return subprocess.run(command, cwd=str(cwd), capture_output=True,
                          text=True, timeout=timeout)


class LinkedInSearchCLI:
    """
    Thin, rate-limited wrapper over the linkedin-search CLI.

    `runner` is injected so deterministic tests can exercise every failure class
    without a network call or a `bun` install. Production uses subprocess.run.
    """

    def __init__(self, config: IngestionConfig, rate_limiter,
                 *, runner: Optional[Callable[..., Any]] = None,
                 timeout: int = DEFAULT_TIMEOUT_SECONDS):
        self.config = config
        self.rate_limiter = rate_limiter
        self._runner = runner or _subprocess_runner
        self.timeout = timeout
        self.invocations: List[CliInvocation] = []
        self._rate_limited = False

    # ------------------------------------------------------------- diagnostics

    @property
    def skill_dir(self) -> Path:
        return self.config.skill_dir

    def runtime_available(self) -> bool:
        return shutil.which(self.config.runtime) is not None

    def preflight(self) -> None:
        """
        Verify the runtime and the CLI entrypoint before any request is made.

        Both failures are explicit and terminal for this source. Neither is a
        reason to reach for a different portal.
        """
        if not self.skill_dir.exists():
            raise RuntimeUnavailable(
                f"linkedin-search skill directory not found: {self.skill_dir}. "
                "The approved ingestion path (OR-08, Path A) is unavailable. No "
                "substitute source is selected at runtime."
            )
        entry = self.skill_dir / self.config.entrypoint
        if not entry.exists():
            raise RuntimeUnavailable(
                f"linkedin-search CLI entrypoint not found: {entry}."
            )
        if not self.runtime_available():
            raise RuntimeUnavailable(
                f"`{self.config.runtime}` is not on PATH. The linkedin-search CLI "
                f"is a TypeScript entrypoint whose only stated dependency is "
                f"`{self.config.runtime}` (SKILL.md). P0_IMPLEMENTATION_SPEC.md "
                "7.4 requires an explicit failure here and forbids a silent "
                "fallback to another source - substituting a source is a "
                "governance decision, not a runtime one. Install the runtime, or "
                "obtain authorization for a different path, then re-run."
            )

    def cli_version(self) -> Dict[str, Any]:
        """
        Identify the CLI revision invoked, for the 7.5 `cli_version` field.

        Every component is read from the skill checkout; nothing is assumed. A
        component that cannot be read is recorded as null rather than guessed.
        """
        info: Dict[str, Any] = {
            "runtime": self.config.runtime,
            "skill_dir": str(self.skill_dir),
            "entrypoint": self.config.entrypoint,
            "package_version": None,
            "skill_version": None,
            "source_revision": None,
        }
        pkg = self.skill_dir / "cli" / "package.json"
        if pkg.exists():
            try:
                with open(pkg, "r", encoding="utf-8") as f:
                    info["package_version"] = json.load(f).get("version")
            except (json.JSONDecodeError, OSError):
                pass
        skill_md = self.skill_dir / "SKILL.md"
        if skill_md.exists():
            for line in skill_md.read_text(encoding="utf-8").splitlines()[:20]:
                if line.startswith("version:"):
                    info["skill_version"] = line.split(":", 1)[1].strip()
                    break
        try:
            rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                 cwd=str(self.skill_dir), capture_output=True,
                                 text=True, timeout=10)
            if rev.returncode == 0:
                info["source_revision"] = rev.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
        return info

    # -------------------------------------------------------------- invocation

    def _classify_stderr(self, stderr: str) -> Optional[Dict[str, Any]]:
        """Parse the CLI's stderr error contract: {"error","code"}."""
        text = stderr.strip()
        if not text:
            return None
        try:
            doc = json.loads(text)
        except json.JSONDecodeError:
            return {"error": text, "code": None, "verbatim_stderr": True}
        if isinstance(doc, dict) and "error" in doc:
            return {"error": doc.get("error"), "code": doc.get("code")}
        return {"error": text, "code": None, "verbatim_stderr": True}

    def _is_rate_limited(self, error: Optional[Dict[str, Any]]) -> bool:
        if not error:
            return False
        blob = f"{error.get('code') or ''} {error.get('error') or ''}".lower()
        return any(marker in blob for marker in _RATE_LIMIT_MARKERS)

    def _invoke(self, args: List[str]) -> CliInvocation:
        """
        Run one CLI subprocess and classify its outcome. Never raises for a
        posting-level failure; raises only for conditions that stop the source.
        """
        command = [self.config.runtime, *self.config.runtime_args,
                   self.config.entrypoint, *args]
        started = utc_now_iso()
        try:
            proc = self._runner(command, self.skill_dir, self.timeout)
        except FileNotFoundError as exc:
            raise RuntimeUnavailable(
                f"`{self.config.runtime}` could not be executed: {exc}. No "
                "fallback source is selected at runtime (P0_SPEC 7.4)."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            invocation = CliInvocation(
                command=command, cwd=str(self.skill_dir), started_at=started,
                finished_at=utc_now_iso(), exit_code=-1, stdout="",
                stderr=f"timeout after {self.timeout}s",
                outcome="error",
                error={"error": str(exc), "code": "TIMEOUT"})
            self.invocations.append(invocation)
            return invocation

        error = self._classify_stderr(proc.stderr)
        finished = utc_now_iso()

        if proc.returncode != 0 or error:
            outcome = "rate_limited" if self._is_rate_limited(error) else "error"
            invocation = CliInvocation(
                command=command, cwd=str(self.skill_dir), started_at=started,
                finished_at=finished, exit_code=proc.returncode,
                stdout=proc.stdout, stderr=proc.stderr,
                outcome=outcome, error=error)
            self.invocations.append(invocation)
            if outcome == "rate_limited":
                self._rate_limited = True
            return invocation

        try:
            parsed = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            # Raw is retained; the record is excluded from normalization rather
            # than partially guessed (P0_SPEC 7.4).
            invocation = CliInvocation(
                command=command, cwd=str(self.skill_dir), started_at=started,
                finished_at=finished, exit_code=proc.returncode,
                stdout=proc.stdout, stderr=proc.stderr, outcome="unparseable",
                error={"error": f"stdout is not JSON: {exc}", "code": "UNPARSEABLE"})
            self.invocations.append(invocation)
            return invocation

        invocation = CliInvocation(
            command=command, cwd=str(self.skill_dir), started_at=started,
            finished_at=finished, exit_code=proc.returncode,
            stdout=proc.stdout, stderr=proc.stderr, outcome="ok", parsed=parsed)
        self.invocations.append(invocation)
        return invocation

    # ----------------------------------------------------------------- commands

    def search(self, *, location: str, query: Optional[str] = None,
               jobage: Optional[int] = None, remote: Optional[str] = None,
               page: int = 1, limit: Optional[int] = None) -> CliInvocation:
        """
        One `search` call. Consumes one search budget unit.

        --location is required by the CLI. --jobage and --jobage-minutes
        conflict, so only --jobage is exposed here.
        """
        if self._rate_limited:
            raise SourceRateLimited(
                "LinkedIn rate-limited or blocked earlier in this run. This "
                "source is stopped for the run and is recorded as rate_limited, "
                "not broken.")
        self.rate_limiter.check_page(page)
        self.rate_limiter.acquire_search()

        args = ["search", "--location", location]
        if query:
            args += ["--query", query]
        if jobage is not None:
            args += ["--jobage", str(jobage)]
        if remote:
            args += ["--remote", remote]
        args += ["--page", str(page)]
        if limit is not None:
            args += ["--limit", str(limit)]
        args += ["--format", "json"]
        return self._invoke(args)

    def detail(self, job_id: str) -> CliInvocation:
        """One `detail` call. Consumes one detail budget unit."""
        if self._rate_limited:
            raise SourceRateLimited(
                "LinkedIn rate-limited or blocked earlier in this run.")
        self.rate_limiter.acquire_detail()
        return self._invoke(["detail", str(job_id), "--format", "json"])

    @staticmethod
    def search_results(invocation: CliInvocation) -> List[Dict[str, Any]]:
        """
        Extract the results array from a successful search.

        A payload whose shape does not match the CLI's documented contract
        yields no results rather than a guess at where the postings might be.
        """
        if invocation.outcome != "ok" or not isinstance(invocation.parsed, dict):
            return []
        results = invocation.parsed.get("results")
        return [r for r in results if isinstance(r, dict)] if isinstance(results, list) else []

    @staticmethod
    def command_display(invocation: CliInvocation) -> str:
        return " ".join(invocation.command)
