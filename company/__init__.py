"""
Company registry: canonical employer identity, ATS identities and employer
classification with evidence. Discovery sources never own company identity;
any source may contribute an ATS slug. An owner-confirmed classification always
outranks an inferred one (EMPR-R06).
"""

from .registry import resolve_classification  # noqa: F401
