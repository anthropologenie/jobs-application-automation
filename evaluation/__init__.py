"""
JobOps v2 evaluation engine (Phase B).

    Observation -> Evidence (extract.py) -> per-dimension selection (selection.py)
                -> eligibility / relevance / preference / fit (engine.py)
                -> lane (lanes.py) -> daily REVIEW capacity (queue.py)

Every policy value is read from policy/jobops-policy-0.2.0.json through
evaluation.policy_loader. The v0.1 engine (policy/gate.py) is untouched and stays
pinned to jobops-policy@0.1.0; evaluation.v01_adapter replays stored evidence
through it.

Nothing in this package performs network I/O, submits an application, or makes
a human decision.
"""

__version__ = "0.2.0"

from .policy_loader import PolicyDriftError, PolicyV02, load_policy_v02  # noqa: F401
