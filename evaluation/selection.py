"""
Per-dimension evidence selection across every observation of a requisition.

This is the F4 fix. For each dimension the governing observation is chosen by a
total order in which absence can never displace presence:

    1. has PRIMARY evidence for the dimension   (absence never wins)
    2. source authority tier                     (ATS/company site > board)
    3. observation completeness                  (FULL_JD > PARTIAL > SEARCH_ONLY)
    4. recency                                   (newer first, among equals only)
    5. observation_id                            (total order)

A later search-only sighting carries no JD-derived evidence, so it can never be
selected for those dimensions and can never downgrade an evaluation made on a
JD-bearing observation. Conflicting factual evidence from a different source is
preserved and reported (SOURCE_CONFLICT); it is never silently discarded.
"""

from typing import Any, Dict, List, Optional

from .textutil import epoch


def rank_key(obs: Dict[str, Any], has_primary: bool):
    return (0 if has_primary else 1, obs["source_authority_tier"], obs["completeness_rank"],
            -epoch(obs["observed_at"]), obs["observation_id"])


def select(observations: List[Dict[str, Any]], evidence: List[Dict[str, Any]],
           dimension: str, *, allow_context: bool = True) -> Optional[Dict[str, Any]]:
    """Return {observation, rows} for the governing observation, or None."""
    by_obs: Dict[str, List[Dict[str, Any]]] = {}
    for row in evidence:
        if row["dimension"] == dimension:
            by_obs.setdefault(row["observation_id"], []).append(row)
    candidates = []
    for obs in observations:
        rows = by_obs.get(obs["observation_id"])
        if not rows:
            continue
        primary = any(r["strength"] == "PRIMARY" for r in rows)
        if not primary and not allow_context:
            continue
        candidates.append((rank_key(obs, primary), obs, rows))
    if not candidates:
        return None
    candidates.sort(key=lambda c: c[0])
    _, obs, rows = candidates[0]
    return {"observation": obs, "rows": sorted(rows, key=lambda r: r["ordinal"]),
            "candidates": [(c[1], c[2]) for c in candidates]}


def conflicts(selected: Optional[Dict[str, Any]], dimension: str, comparable_fn,
              differs=None) -> List[Dict[str, Any]]:
    """
    Disagreements between the selected observation and other-source PRIMARY evidence.
    `differs` (0.2.3) decides disagreement; by default any inequality. Under 0.2.3 a detail
    absent on one side (a search card saying "Hybrid, Bengaluru" next to an ATS JD stating two
    office days) is not a contradiction (F4 / owner resolution of R2-SEQ-09).
    """
    differs = differs or (lambda a, b: a != b)
    if not selected:
        return []
    chosen_obs = selected["observation"]
    chosen_value = comparable_fn(selected["rows"])
    if chosen_value is None:
        return []
    found = []
    for obs, rows in selected["candidates"][1:]:
        if obs["source"] == chosen_obs["source"]:
            continue  # same source over time is an update, not a conflict
        if not any(r["strength"] == "PRIMARY" for r in rows):
            continue
        other = comparable_fn(rows)
        if other is not None and differs(other, chosen_value):
            found.append({"dimension": dimension,
                          "selected_observation": chosen_obs["observation_id"],
                          "selected_source": chosen_obs["source"],
                          "selected_value": list(chosen_value) if isinstance(chosen_value, tuple) else chosen_value,
                          "other_observation": obs["observation_id"],
                          "other_source": obs["source"],
                          "other_value": list(other) if isinstance(other, tuple) else other})
    return found
