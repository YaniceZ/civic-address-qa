"""Data quality checks on a standardized address layer.

Each check counts failing rows and compares the rate with a threshold. A run with no rows at all is
an error, not a check result: an empty layer usually means something upstream broke silently.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import geopandas as gpd
import pandas as pd

from civic_qa.parse import CANONICAL_TYPES

# Rough bounding box for Canada in EPSG:4326 (min lon, min lat, max lon, max lat).
CANADA_BOUNDS = (-141.1, 41.6, -52.5, 83.2)

DEFAULT_THRESHOLDS = {
    "not_parsed": 0.01,
    "missing_house_number": 0.01,
    "missing_street_name": 0.01,
    "unknown_street_type": 0.02,
    "duplicate_address": 0.01,
    "empty_geometry": 0.0,
    "outside_canada": 0.0,
}


class EmptyOutputError(RuntimeError):
    pass


@dataclass
class CheckResult:
    name: str
    failed: int
    total: int
    threshold: float

    @property
    def rate(self) -> float:
        return self.failed / self.total if self.total else 0.0

    @property
    def passed(self) -> bool:
        return self.rate <= self.threshold

    def to_dict(self) -> dict:
        return {**asdict(self), "rate": round(self.rate, 6), "passed": self.passed}


def assert_not_empty(gdf: gpd.GeoDataFrame, label: str) -> None:
    if gdf is None or len(gdf) == 0:
        raise EmptyOutputError(f"{label}: output has no rows")


def _outside(gdf: gpd.GeoDataFrame, bounds: tuple[float, float, float, float]) -> pd.Series:
    min_x, min_y, max_x, max_y = bounds
    valid = ~(gdf.geometry.is_empty | gdf.geometry.isna())
    x = gdf.geometry.x.where(valid)
    y = gdf.geometry.y.where(valid)
    return valid & ((x < min_x) | (x > max_x) | (y < min_y) | (y > max_y))


def run_checks(
    gdf: gpd.GeoDataFrame,
    thresholds: dict[str, float] | None = None,
    bounds: tuple[float, float, float, float] = CANADA_BOUNDS,
) -> list[CheckResult]:
    assert_not_empty(gdf, "run_checks")
    limits = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    total = len(gdf)

    raw_type = gdf["raw_street_type"]
    key = gdf["full_address"].fillna("")
    failures = {
        "not_parsed": ~gdf["parsed"].astype(bool),
        "missing_house_number": gdf["house_number"].isna(),
        "missing_street_name": gdf["street_name"].isna(),
        "unknown_street_type": raw_type.notna() & ~gdf["street_type"].isin(CANONICAL_TYPES),
        "duplicate_address": (key != "") & key.duplicated(keep=False),
        "empty_geometry": gdf.geometry.isna() | gdf.geometry.is_empty,
        "outside_canada": _outside(gdf, bounds),
    }
    return [CheckResult(name, int(mask.sum()), total, limits[name]) for name, mask in failures.items()]


def failing_examples(gdf: gpd.GeoDataFrame, check: str, n: int = 5) -> list[str]:
    """A few example rows for a failed check, for the report."""
    if check == "unknown_street_type":
        rows = gdf[gdf["raw_street_type"].notna() & ~gdf["street_type"].isin(CANONICAL_TYPES)]
        return rows["raw_street_type"].value_counts().head(n).index.tolist()
    if check == "duplicate_address":
        key = gdf["full_address"].fillna("")
        return key[(key != "") & key.duplicated()].head(n).tolist()
    return []
