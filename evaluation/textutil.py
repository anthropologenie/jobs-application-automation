"""Small deterministic text helpers shared by extraction and identity."""

import hashlib
import json
import re
from datetime import datetime
from typing import Any, List, Optional


def split_sentences(text: Optional[str], pattern: "re.Pattern[str]") -> List[str]:
    if not text:
        return []
    return [s.strip() for s in pattern.split(text) if s and s.strip()]


def normalize_words(value: Optional[str]) -> str:
    if not value:
        return ""
    lowered = "".join(ch.lower() if ch.isalnum() else " " for ch in value)
    return re.sub(r"\s+", " ", lowered).strip()


def content_hash(value: Optional[str]) -> str:
    return hashlib.sha256((value or "").encode("utf-8")).hexdigest()


def stable_hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                     default=str).encode("utf-8")).hexdigest()


def epoch(iso: Optional[str]) -> float:
    if not iso:
        return 0.0
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()


def date_precision(value: Optional[str]) -> str:
    if not value:
        return "NONE"
    return "TIMESTAMP" if ("T" in value or ":" in value) else "DATE"


def any_match(patterns, text: str) -> Optional["re.Match[str]"]:
    for p in patterns:
        m = p.search(text)
        if m:
            return m
    return None
