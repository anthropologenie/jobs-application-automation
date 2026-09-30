"""Employer classification resolution (pure): owner-confirmed > registry > text signals > UNKNOWN."""

from typing import Any, Dict, List, Optional

_BASIS_RANK = {"OWNER_CONFIRMED": 0, "REGISTRY_LIST": 1, "INFERRED_FROM_EVIDENCE": 2}

# Deterministic resolution when text signals name more than one class: the more
# cautious reading first, so a staffing signal is never hidden by a product one.
_SIGNAL_ORDER = ["STAFFING", "CONSULTANCY", "IT_SERVICES", "GCC", "AI_NATIVE",
                 "ENGINEERING_LED", "PRODUCT"]


def resolve_classification(records: List[Dict[str, Any]],
                           text_signals: List[str]) -> Dict[str, Any]:
    """
    Pick the governing classification.

    `records` are company_classification rows (append-only; latest decided_at
    wins within a basis). `text_signals` are classes named by the JD.
    """
    if records:
        best = sorted(records, key=lambda r: (_BASIS_RANK.get(r["basis"], 9),
                                             _neg(r["decided_at"]), r["classification_id"]))[0]
        return {"classification": best["classification"], "basis": best["basis"],
                "classification_id": best["classification_id"]}
    for cls in _SIGNAL_ORDER:
        if cls in text_signals:
            return {"classification": cls, "basis": "INFERRED_FROM_TEXT", "classification_id": None}
    return {"classification": "UNKNOWN", "basis": "NO_EVIDENCE", "classification_id": None}


def _neg(iso: Optional[str]) -> str:
    # Sort descending on an ISO string by inverting characters' order-significance.
    return "".join(chr(0x10FFFF - ord(c)) for c in (iso or ""))
