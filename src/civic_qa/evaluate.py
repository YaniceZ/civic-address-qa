"""Measure the parser against sources that publish both a full address and its split fields."""

from __future__ import annotations

import geopandas as gpd
import pandas as pd

from civic_qa.parse import clean, normalize_street_type, parse_address

FIELDS = ("house_number", "street_name", "street_type")


def _as_text(value) -> str | None:
    """Numbers come back from ArcGIS as floats (1885.0); compare them as whole-number text."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return clean(value) or None


def _expected(row: pd.Series, mapping: dict) -> dict:
    value = {f: _as_text(row.get(col)) for f, col in mapping.items()}
    if "street_type" in value:
        value["street_type"] = normalize_street_type(value["street_type"])
    return value


def parser_accuracy(
    raw: gpd.GeoDataFrame, full_address_field: str, mapping: dict, hyphen_order: str = "unit-number"
) -> dict:
    """Compare parse_address() output with the source's own split fields.

    Returns per-field accuracy, the share of rows where every compared field matches, and examples
    of mismatches so the rules can be improved.
    """
    fields = [f for f in FIELDS if f in mapping]
    matches = {f: 0 for f in fields}
    all_match = 0
    mismatches: list[dict] = []
    rows = 0
    for _, row in raw.iterrows():
        if not clean(row.get(full_address_field)):
            continue
        rows += 1
        got = parse_address(row.get(full_address_field), hyphen_order).to_dict()
        want = _expected(row, mapping)
        ok = True
        for f in fields:
            if got.get(f) == want.get(f):
                matches[f] += 1
            else:
                ok = False
        if ok:
            all_match += 1
        elif len(mismatches) < 15:
            mismatches.append(
                {"address": row.get(full_address_field), "parsed": {f: got.get(f) for f in fields}, "expected": want}
            )
    return {
        "rows": rows,
        "field_accuracy": {f: round(matches[f] / rows, 4) if rows else None for f in fields},
        "all_fields_match": round(all_match / rows, 4) if rows else None,
        "mismatch_examples": mismatches,
    }
