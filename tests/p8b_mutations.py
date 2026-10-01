"""
In-memory ruling mutations for jobops-policy@0.2.6 (P8b §12). Not collected by pytest (no test_ prefix).

Each mutation deep-copies the 0.2.6 artifact and removes exactly one owner-ruling implementation. Nothing is
written to disk. OR-90 (OI-054) changed no behaviour, so it has no mutation.
"""

import copy

from evaluation.policy_loader import load_policy_version, policy_from_doc

V25, V26 = "jobops-policy@0.2.5", "jobops-policy@0.2.6"


def _remove_or89(doc, old):
    """OI-053 = YES removed entirely: preference is no longer eligibility (and its 0.2.6 lexicon goes back to 0.2.5)."""
    doc["parameters"]["india_preference_is_eligibility"] = False
    doc["lexicon"]["india_eligibility"] = copy.deepcopy(old["lexicon"]["india_eligibility"])


def _remove_or89_precedence(doc, old):
    """Only the exclusion-precedence guard removed: a preference would then outrank a negated India clause."""
    doc["lexicon"]["india_eligibility"].pop("precedence")


def _remove_or91(doc, old):
    """OI-055 = FAIL removed: a measurable office-day count no longer outranks the structured Hybrid label."""
    doc["parameters"]["office_days_override_hybrid_label"] = False


MUTATIONS = {"OR-89": _remove_or89, "OR-89-precedence": _remove_or89_precedence, "OR-91": _remove_or91}


def mutated_policy(name: str):
    doc = copy.deepcopy(load_policy_version(V26).doc)
    MUTATIONS[name](doc, load_policy_version(V25).doc)
    return policy_from_doc(doc)
