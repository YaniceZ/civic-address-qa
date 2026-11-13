import geopandas as gpd
import pytest
from shapely.geometry import Point

from civic_qa.pipeline import process, render_markdown
from civic_qa.qa import EmptyOutputError, run_checks
from civic_qa.standardize import standardize

COMPONENTS = {
    "mode": "components",
    "province": "BC",
    "city": "TESTVILLE",
    "fields": {"house_number": "NUM", "unit": "UNIT", "street_name": "NAME", "street_type": "TYPE"},
}
PARSE = {
    "mode": "parse",
    "province": "ON",
    "full_address": "COMPLETE",
    "check_against": {"house_number": "NUM", "street_name": "NAME", "street_type": "TYPE"},
}


def layer(rows, points=None):
    points = points or [Point(-123.1, 49.2 + i * 0.001) for i in range(len(rows))]
    return gpd.GeoDataFrame(rows, geometry=points, crs="EPSG:4326")


def test_components_mapping():
    raw = layer([{"OBJECTID": 1, "NUM": "2155", "UNIT": "18", "NAME": "Horizon", "TYPE": "Drive"}])
    std = standardize(raw, "test", COMPONENTS)
    row = std.iloc[0]
    assert row["full_address"] == "18-2155 HORIZON DR"
    assert row["city"] == "TESTVILLE"
    assert row["parsed"]


def test_empty_layer_is_an_error():
    with pytest.raises(EmptyOutputError):
        process(layer([]), "test", COMPONENTS)


def test_checks_flag_duplicates_and_bad_coordinates():
    raw = layer(
        [
            {"OBJECTID": 1, "NUM": "1", "UNIT": None, "NAME": "MAIN", "TYPE": "ST"},
            {"OBJECTID": 2, "NUM": "1", "UNIT": None, "NAME": "MAIN", "TYPE": "ST"},
            {"OBJECTID": 3, "NUM": "2", "UNIT": None, "NAME": "MAIN", "TYPE": "QQ"},
        ],
        [Point(-123.1, 49.2), Point(-123.1, 49.3), Point(10.0, 50.0)],
    )
    results = {c.name: c for c in run_checks(standardize(raw, "test", COMPONENTS))}
    assert results["duplicate_address"].failed == 2
    assert results["outside_canada"].failed == 1
    assert results["unknown_street_type"].failed == 1
    assert not results["outside_canada"].passed


def test_parser_accuracy_in_report():
    raw = layer(
        [
            {"OBJECTID": 1, "COMPLETE": "10 MAIN ST", "NUM": 10.0, "NAME": "MAIN", "TYPE": "ST"},
            {"OBJECTID": 2, "COMPLETE": "20 KING ST", "NUM": 20, "NAME": "KING", "TYPE": "ST"},
        ]
    )
    std, report = process(raw, "test", PARSE)
    assert report["parser"]["all_fields_match"] == 1.0
    assert "Parser accuracy" in render_markdown({**report, "name": "Test", "url": "-"})
    assert len(std) == 2
