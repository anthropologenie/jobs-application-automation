"""
Geography normalization for JobOps v2.

All reference data (countries, region -> country membership, city aliases,
Bengaluru localities, worldwide phrases, timezone tokens) lives in the policy
artifact's `geo` section. This package only interprets it. Bengaluru is a city
id (IN-bengaluru) consumed by policy rules, never a string check in the gate.
"""

from .places import PlaceIndex, PlaceRef  # noqa: F401
