"""Map a source layer onto one standard civic address schema."""

from __future__ import annotations

import geopandas as gpd
import pandas as pd

from civic_qa.parse import DIRECTIONS, clean, format_address, normalize_street_type, parse_address

SCHEMA = [
    "source",
    "source_id",
    "house_number",
    "number_suffix",
    "unit",
    "street_name",
    "street_type",
    "street_dir",
    "full_address",
    "city",
    "province",
    "parsed",
    "raw_street_type",
]


def _text(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    value = clean(value)
    return value or None


def _from_components(row: pd.Series, fields: dict) -> dict:
    raw_type = _text(row.get(fields.get("street_type")))
    direction = _text(row.get(fields.get("street_dir")))
    return {
        "house_number": _text(row.get(fields.get("house_number"))),
        "number_suffix": _text(row.get(fields.get("number_suffix"))),
        "unit": _text(row.get(fields.get("unit"))),
        "street_name": _text(row.get(fields.get("street_name"))),
        "street_type": normalize_street_type(raw_type),
        "street_dir": DIRECTIONS.get(direction, direction) if direction else None,
        "raw_street_type": raw_type,
    }


def _from_full_address(row: pd.Series, field: str, hyphen_order: str) -> dict:
    parsed = parse_address(row.get(field), hyphen_order).to_dict()
    parsed["raw_street_type"] = parsed["street_type"]
    return parsed


def standardize(gdf: gpd.GeoDataFrame, source_key: str, config: dict) -> gpd.GeoDataFrame:
    """Return a GeoDataFrame with the columns in SCHEMA plus geometry.

    config["mode"] is either "components" (fields already split) or "parse" (one address string).
    """
    mode = config["mode"]
    records = []
    for _, row in gdf.iterrows():
        if mode == "components":
            parts = _from_components(row, config["fields"])
            parts["parsed"] = parts["house_number"] is not None and parts["street_name"] is not None
        elif mode == "parse":
            parts = _from_full_address(row, config["full_address"], config.get("hyphen_order", "unit-number"))
        else:
            raise ValueError(f"Unknown mode {mode!r} for source {source_key}")

        parts["full_address"] = format_address(
            parts["house_number"],
            parts["street_name"],
            parts["street_type"],
            parts["street_dir"],
            parts["unit"],
            parts["number_suffix"],
        )
        parts["source"] = source_key
        parts["source_id"] = row.get(config.get("id_field", "OBJECTID"))
        parts["city"] = _text(row.get(config["city_field"])) if config.get("city_field") else config.get("city")
        parts["province"] = config.get("province")
        records.append(parts)

    out = pd.DataFrame.from_records(records, columns=SCHEMA)
    return gpd.GeoDataFrame(out, geometry=gdf.geometry.values, crs=gdf.crs)
