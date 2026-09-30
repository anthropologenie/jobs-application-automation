"""Place recognition over the policy's geo reference tables."""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

INDIA = "IN"


@dataclass(frozen=True)
class PlaceRef:
    kind: str                 # COUNTRY | REGION | CITY | WORLDWIDE | STATE
    ref: str                  # "IN", "APAC", "IN-bengaluru", "WORLDWIDE", "karnataka"
    country: Optional[str]    # ISO country for COUNTRY/CITY/STATE; None for REGION/WORLDWIDE
    text: str                 # the matched text

    @property
    def is_bengaluru(self) -> bool:
        return self.kind == "CITY" and self.ref == "IN-bengaluru"


class PlaceIndex:
    """
    Recognises places in free text.

    Names match case-insensitively on word boundaries; acronyms (US, UK, EU,
    EEA, EMEA, APAC ...) match case-sensitively so that "join us" is never read
    as the United States. Longer aliases win over shorter overlapping ones.
    """

    def __init__(self, geo: Dict[str, Any]):
        self.geo = geo
        self.bengaluru_id = geo["bengaluru"]["city_id"]
        entries: List[Tuple[str, bool, PlaceRef]] = []
        for alias in geo["bengaluru"]["aliases"]:
            entries.append((alias, False, PlaceRef("CITY", self.bengaluru_id, INDIA, alias)))
        for city_id, aliases in geo["india_cities"].items():
            for alias in aliases:
                entries.append((alias, False, PlaceRef("CITY", city_id, INDIA, alias)))
        for state in geo["india_states"]:
            entries.append((state, False, PlaceRef("STATE", state, INDIA, state)))
        for city_id, spec in geo["foreign_cities"].items():
            for alias in spec["aliases"]:
                entries.append((alias, False, PlaceRef("CITY", city_id, spec["country"], alias)))
        for code, spec in geo["countries"].items():
            for name in spec["names"]:
                entries.append((name, False, PlaceRef("COUNTRY", code, code, name)))
            for acr in spec["acronyms"]:
                entries.append((acr, True, PlaceRef("COUNTRY", code, code, acr)))
        self.region_members: Dict[str, Set[str]] = {}
        for region, spec in geo["regions"].items():
            self.region_members[region] = set(spec["members"])
            for name in spec["names"]:
                entries.append((name, False, PlaceRef("REGION", region, None, name)))
            for acr in spec["acronyms"]:
                entries.append((acr, True, PlaceRef("REGION", region, None, acr)))
        for alias in geo["worldwide_aliases"]:
            entries.append((alias, False, PlaceRef("WORLDWIDE", "WORLDWIDE", None, alias)))
        entries.sort(key=lambda e: -len(e[0]))
        self._patterns = []
        for alias, case_sensitive, ref in entries:
            flags = 0 if case_sensitive else re.I
            body = re.escape(alias).replace(r"\ ", r"[\s-]+")
            self._patterns.append((re.compile(rf"(?<![\w$]){body}(?![\w])", flags), ref))

    def find(self, text: Optional[str]) -> List[PlaceRef]:
        """Every place in `text`, in document order, without overlapping matches."""
        if not text:
            return []
        taken: List[Tuple[int, int]] = []
        found: List[Tuple[int, PlaceRef]] = []
        for pattern, ref in self._patterns:
            for m in pattern.finditer(text):
                s, e = m.span()
                if any(s < te and ts < e for ts, te in taken):
                    continue
                taken.append((s, e))
                found.append((s, PlaceRef(ref.kind, ref.ref, ref.country, m.group(0))))
        found.sort(key=lambda x: x[0])
        return [ref for _, ref in found]

    def region_contains(self, region: str, country: str) -> bool:
        return country in self.region_members.get(region, set())

    @staticmethod
    def city_class(places: List[PlaceRef]) -> Optional[str]:
        """BENGALURU | OTHER_INDIA | ABROAD | None (no city/country identifiable)."""
        if any(p.is_bengaluru for p in places):
            return "BENGALURU"
        cities = [p for p in places if p.kind == "CITY"]
        if any(p.country == INDIA for p in cities):
            return "OTHER_INDIA"
        if any(p.country and p.country != INDIA for p in places if p.kind in ("CITY", "COUNTRY")):
            return "ABROAD"
        return None
