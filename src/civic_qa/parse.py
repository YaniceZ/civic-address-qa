"""Parse a single-line civic address into its parts.

The parser handles the forms that show up most often in Canadian municipal data:

    2155 HORIZON DR            number, street name, street type
    18-2155 HORIZON DR         unit before the number (Canada Post style)
    2155 HORIZON DR UNIT 18    unit after the street
    123A MAIN ST E             number suffix and a trailing direction
    1475 HIGHWAY 61            no street type

It is rule-based on purpose: every decision can be read in the code and tested.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

# Canada Post street type abbreviations (a working subset), keyed by every spelling we accept.
STREET_TYPES: dict[str, str] = {
    "AVENUE": "AVE", "AVE": "AVE", "AV": "AVE",
    "BAY": "BAY",
    "BOULEVARD": "BLVD", "BLVD": "BLVD",
    "CIRCLE": "CIR", "CIR": "CIR", "CIRC": "CIR",
    "CLOSE": "CLOSE",
    "CONCESSION": "CONC", "CONC": "CONC",
    "COURT": "CRT", "CRT": "CRT", "CT": "CRT",
    "COVE": "COVE",
    "CRESCENT": "CRES", "CRES": "CRES", "CR": "CRES",
    "DRIVE": "DR", "DR": "DR",
    "GATE": "GATE",
    "GREEN": "GREEN",
    "GROVE": "GROVE",
    "HEIGHTS": "HTS", "HTS": "HTS",
    "HIGHWAY": "HWY", "HWY": "HWY",
    "HILL": "HILL",
    "KEY": "KEY",
    "LANDING": "LANDNG", "LANDNG": "LANDNG", "LANDG": "LANDNG",
    "LANE": "LANE", "LN": "LANE",
    "LINE": "LINE",
    "LOOP": "LOOP",
    "MEWS": "MEWS",
    "PARKWAY": "PKY", "PKY": "PKY", "PKWY": "PKY",
    "PATH": "PATH",
    "PLACE": "PL", "PL": "PL",
    "POINT": "PT", "PT": "PT",
    "QUAY": "QUAY",
    "RIDGE": "RIDGE",
    "RISE": "RISE",
    "ROAD": "RD", "RD": "RD",
    "ROW": "ROW",
    "SIDEROAD": "SIDERD", "SIDERD": "SIDERD",
    "SQUARE": "SQ", "SQ": "SQ",
    "STREET": "ST", "ST": "ST",
    "TERRACE": "TERR", "TERR": "TERR",
    "TRAIL": "TRAIL", "TRL": "TRAIL",
    "VIEW": "VIEW",
    "WALK": "WALK",
    "WAY": "WAY",
}
CANONICAL_TYPES = frozenset(STREET_TYPES.values())

DIRECTIONS: dict[str, str] = {
    "N": "N", "S": "S", "E": "E", "W": "W",
    "NE": "NE", "NW": "NW", "SE": "SE", "SW": "SW",
    "NORTH": "N", "SOUTH": "S", "EAST": "E", "WEST": "W",
}
# Full words such as WEST at the start of a name are usually part of the name (WEST RIVERDALE RD),
# so only abbreviations are treated as a leading direction.
LEADING_DIRECTIONS = frozenset({"N", "S", "E", "W", "NE", "NW", "SE", "SW"})

_UNIT_AFTER = re.compile(r"\s+(?:UNIT|APT|SUITE|STE|#)\s*(?P<unit>[A-Z0-9]+)$")
_UNIT_BEFORE = re.compile(r"^#?(?P<unit>[A-Z0-9]+)\s*-\s*(?=\d)")
# Some municipalities write the hyphenated form the other way round: 276-4 means number 276, unit 4.
_UNIT_AFTER_NUMBER = re.compile(r"^(?P<number>\d+)\s*-\s*(?P<unit>[A-Z0-9]+)(?=\s)")
# A house number may carry a letter (123A) or a half (963 1/2).
_NUMBER = re.compile(r"^(?P<number>\d+)(?:(?P<suffix>[A-Z])|\s+(?P<half>1/2))?(?=\s)")


@dataclass
class ParsedAddress:
    house_number: str | None = None
    number_suffix: str | None = None
    unit: str | None = None
    street_name: str | None = None
    street_type: str | None = None
    street_dir: str | None = None
    parsed: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def clean(text: str | None) -> str:
    """Upper-case, drop punctuation that carries no meaning and collapse whitespace."""
    if text is None:
        return ""
    text = str(text).upper().replace(",", " ").replace(".", " ")
    return re.sub(r"\s+", " ", text).strip()


def normalize_street_type(value: str | None) -> str | None:
    value = clean(value)
    return STREET_TYPES.get(value, value or None)


def parse_address(text: str | None, hyphen_order: str = "unit-number") -> ParsedAddress:
    """Split a one-line address. Returns parsed=False when no house number or street name is found.

    hyphen_order says how to read "12-345": "unit-number" (Canada Post, the default) or "number-unit".
    """
    if hyphen_order not in ("unit-number", "number-unit"):
        raise ValueError(f"hyphen_order must be 'unit-number' or 'number-unit', not {hyphen_order!r}")
    s = clean(text)
    result = ParsedAddress()
    if not s:
        return result

    m = _UNIT_AFTER.search(s)
    if m:
        result.unit = m.group("unit")
        s = s[: m.start()]

    if hyphen_order == "number-unit":
        m = _UNIT_AFTER_NUMBER.match(s)
        if m:
            result.unit = m.group("unit")
            s = m.group("number") + s[m.end():]
    else:
        m = _UNIT_BEFORE.match(s)
        if m:
            result.unit = m.group("unit")
            s = s[m.end():]

    m = _NUMBER.match(s)
    if not m:
        return result
    result.house_number = m.group("number")
    result.number_suffix = m.group("suffix") or m.group("half")
    tokens = s[m.end():].split()

    if len(tokens) > 1 and tokens[-1] in DIRECTIONS:
        result.street_dir = DIRECTIONS[tokens.pop()]
    if len(tokens) > 1 and tokens[-1] in STREET_TYPES:
        result.street_type = STREET_TYPES[tokens.pop()]
    if result.street_dir is None and len(tokens) > 1 and tokens[0] in LEADING_DIRECTIONS:
        result.street_dir = tokens.pop(0)

    result.street_name = " ".join(tokens) or None
    result.parsed = result.street_name is not None
    return result


def format_address(
    house_number: str | None,
    street_name: str | None,
    street_type: str | None = None,
    street_dir: str | None = None,
    unit: str | None = None,
    number_suffix: str | None = None,
) -> str | None:
    """Build a one-line address in Canada Post order: UNIT-NUMBER NAME TYPE DIR."""
    if not house_number or not street_name:
        return None
    if number_suffix == "1/2":
        number = f"{house_number} 1/2"
    else:
        number = f"{house_number}{number_suffix or ''}"
    if unit:
        number = f"{unit}-{number}"
    parts = [number, street_name, street_type, street_dir]
    return " ".join(p for p in parts if p)
