"""
In-memory fix-family mutations for jobops-policy@0.2.5 (P8 §17). Not collected by pytest (no test_ prefix).

Each mutation takes a deep copy of the 0.2.5 artifact and removes exactly one fix family by restoring the
0.2.4 data for that family (and dropping the 0.2.5-only keys that switch its engine code path on). Nothing
is written to disk; the frozen artifacts are only read. tests/test_p8_policy_025.py proves that every
family's own golden cases fail in the expected direction under its mutation.
"""

import copy

from evaluation.policy_loader import load_policy_version, policy_from_doc

V24, V25 = "jobops-policy@0.2.4", "jobops-policy@0.2.5"


def _revert_india_eligibility(doc, old):
    doc["lexicon"].pop("india_eligibility")


def _revert_locks(doc, old):
    lex, olex = doc["lexicon"], old["lexicon"]
    lex["residence_requirement"] = copy.deepcopy(olex["residence_requirement"])
    lex["work_authorization"] = copy.deepcopy(olex["work_authorization"])
    lex["relocation_negation"] = copy.deepcopy(olex["relocation_negation"])
    for k in ("lock_negation_before", "lock_negation_window_words", "lock_negation_note"):
        lex.pop(k)
    doc["parameters"]["lock_lists_including_india_do_not_exclude"] = False


def _revert_office_days(doc, old):
    doc["lexicon"]["office_day_normalization"] = copy.deepcopy(old["lexicon"]["office_day_normalization"])
    doc["rules"]["geography"] = [r for r in doc["rules"]["geography"] if r["rule_id"] != "GEO-R28"]


def _revert_office_day_context(doc, old):
    doc["lexicon"]["office_day_normalization"].pop("count_context_exclusions")


def _revert_between_thresholds(doc, old):
    doc["rules"]["geography"] = [r for r in doc["rules"]["geography"] if r["rule_id"] != "GEO-R28"]


def _revert_location_pay(doc, old):
    comp = doc["lexicon"]["compensation"]
    comp["location_adjusted"] = copy.deepcopy(old["lexicon"]["compensation"]["location_adjusted"])
    comp.pop("location_adjusted_negation")


def _revert_client_placement(doc, old):
    lex = doc["lexicon"]
    lex["relationship"] = copy.deepcopy(old["lexicon"]["relationship"])
    for k in ("relationship_negation_before", "relationship_negation_window_words", "relationship_negation_note"):
        lex.pop(k)


def _revert_language_preference(doc, old):
    lang, olang = doc["lexicon"]["language"], old["lexicon"]["language"]
    lang["names"] = list(olang["names"])
    lang["preferred"] = list(olang["preferred"])
    lang.pop("preference_overrides_weak_requirement")


def _revert_d3_parking(doc, old):
    doc["queue"]["d3_parking_unconditional"] = False


MUTATIONS = {
    "india_eligibility": _revert_india_eligibility,
    "region_residence_authorization": _revert_locks,
    "office_days": _revert_office_days,
    "office_days_context_exclusion": _revert_office_day_context,
    "office_days_between_thresholds": _revert_between_thresholds,
    "location_pay": _revert_location_pay,
    "client_placement": _revert_client_placement,
    "language_preference": _revert_language_preference,
    "d3_parking": _revert_d3_parking,
}


def mutated_policy(family: str):
    """0.2.5 with one fix family removed (in memory only)."""
    doc = copy.deepcopy(load_policy_version(V25).doc)
    old = load_policy_version(V24).doc
    MUTATIONS[family](doc, old)
    return policy_from_doc(doc)
