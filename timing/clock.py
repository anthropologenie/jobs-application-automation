#!/usr/bin/env python3
"""
Timestamp handling - one place, so every reading of a clock is stated

Three timestamp shapes reach this instrumentation, and conflating them is how a
duration silently gains or loses five and a half hours:

  1. ISO 8601 with an offset  - written by P0-02/P0-06/P0-08 Python code
                                (`datetime.now(timezone.utc).isoformat()`).
  2. "YYYY-MM-DD HH:MM:SS"    - SQLite CURRENT_TIMESTAMP: UTC, but stored with
                                no offset marker at all.
  3. "YYYY-MM-DD"             - a SQLite DATE column, day precision only.

Shape 2 is read as UTC because SQLite's CURRENT_TIMESTAMP is documented UTC.
That is an assumption about a naive string, so it is made once, here, and
stated in the artifact rather than being spread through the metric code.

Shape 3 is deliberately NOT promoted to a datetime. `opportunities.applied_date`
is a DATE: turning it into midnight UTC would manufacture a time of day that
nobody recorded, and a time-to-submit computed from it would be precise-looking
fiction. `parse_date_only` returns the date and says so; nothing in this package
uses it as an interval endpoint.

Author: Karthik Shetty
Created: 2026-09-07
"""

from datetime import date, datetime, timezone
from typing import Optional

# SQLite CURRENT_TIMESTAMP, and the same shape with a "T" separator.
_NAIVE_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S")


class TimestampError(ValueError):
    """Raised when a value cannot be read as a timestamp without guessing."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def parse_timestamp(value: Optional[str], *, field: str = "timestamp") -> Optional[datetime]:
    """
    Read a recorded timestamp as an aware UTC datetime, or return None.

    None in, None out: an event that was never recorded stays absent. It is
    never defaulted to "now", to epoch, or to any other value that would let a
    missing event participate in a duration.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None

    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
        for fmt in _NAIVE_FORMATS:
            try:
                parsed = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        if parsed is None:
            raise TimestampError(
                f"{field}={text!r} is not a timestamp this implementation can "
                "read without guessing its meaning.")

    if parsed.tzinfo is None:
        # SQLite CURRENT_TIMESTAMP. Stated, not silently assumed.
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_date_only(value: Optional[str]) -> Optional[date]:
    """
    Read a DATE column as a date. Never widened into a datetime.

    `opportunities.applied_date` is the only such column in play, and this
    function exists so that reading it cannot accidentally produce an interval
    endpoint with a manufactured time of day.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.strptime(text[:10], "%Y-%m-%d").date()
    except ValueError as exc:
        raise TimestampError(f"applied_date={text!r} is not a date.") from exc


def minutes_between(start: Optional[datetime], end: Optional[datetime]) -> Optional[float]:
    """
    Minutes from start to end, or None if either end of the interval is absent.

    A negative interval is NOT returned. Out-of-order events are a data fact the
    caller must surface as INCONSISTENT; returning a negative number here, or an
    absolute value, would let it be averaged into a plausible-looking figure.
    """
    if start is None or end is None:
        return None
    delta = (end - start).total_seconds() / 60.0
    return None if delta < 0 else delta


def is_out_of_order(start: Optional[datetime], end: Optional[datetime]) -> bool:
    """True only when both events exist and the later one came first."""
    return start is not None and end is not None and end < start


def utc_day(value: Optional[datetime]) -> Optional[str]:
    """The UTC calendar day an event fell on - the period every rate uses."""
    return None if value is None else value.date().isoformat()
