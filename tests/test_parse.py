import pytest

from civic_qa.parse import format_address, normalize_street_type, parse_address


@pytest.mark.parametrize(
    "text, expected",
    [
        ("2155 HORIZON DR", dict(house_number="2155", street_name="HORIZON", street_type="DR")),
        ("18-2155 Horizon Drive", dict(unit="18", house_number="2155", street_name="HORIZON", street_type="DR")),
        ("2155 HORIZON DR UNIT 18", dict(unit="18", house_number="2155", street_name="HORIZON", street_type="DR")),
        ("#4-10 MAIN ST", dict(unit="4", house_number="10", street_name="MAIN", street_type="ST")),
        ("123A Main St E", dict(house_number="123", number_suffix="A", street_name="MAIN", street_dir="E")),
        ("1475 HIGHWAY 61", dict(house_number="1475", street_name="HIGHWAY 61", street_type=None)),
        ("1885 WEST RIVERDALE RD", dict(street_name="WEST RIVERDALE", street_type="RD", street_dir=None)),
        ("10 N CENTRAL AVE", dict(street_dir="N", street_name="CENTRAL", street_type="AVE")),
        ("1 AVENUE RD", dict(street_name="AVENUE", street_type="RD")),
        ("55 ST. GEORGE ST", dict(street_name="ST GEORGE", street_type="ST")),
        ("963 1/2 HOLT PL", dict(house_number="963", number_suffix="1/2", street_name="HOLT", street_type="PL")),
        ("1044 GREENGATE CIRC", dict(street_name="GREENGATE", street_type="CIR")),
        ("  301   king  street  west ",dict(house_number="301", street_name="KING", street_type="ST", street_dir="W")),
    ],
)
def test_parse_address(text, expected):
    result = parse_address(text).to_dict()
    assert result["parsed"] is True
    for key, value in expected.items():
        assert result[key] == value, key


def test_hyphen_order_is_configurable():
    canada_post = parse_address("276-4 CARIBOU CRES")
    assert (canada_post.unit, canada_post.house_number) == ("276", "4")
    thunder_bay = parse_address("276-4 CARIBOU CRES", hyphen_order="number-unit")
    assert (thunder_bay.unit, thunder_bay.house_number) == ("4", "276")
    with pytest.raises(ValueError):
        parse_address("1 MAIN ST", hyphen_order="sideways")


@pytest.mark.parametrize("text", [None, "", "MAIN ST", "RR 2"])
def test_unparseable(text):
    assert parse_address(text).parsed is False


def test_normalize_street_type():
    assert normalize_street_type("Crescent") == "CRES"
    assert normalize_street_type("crt") == "CRT"
    assert normalize_street_type("XYZ") == "XYZ"
    assert normalize_street_type(None) is None


def test_format_address_round_trip():
    text = format_address("2155", "HORIZON", "DR", None, unit="18")
    assert text == "18-2155 HORIZON DR"
    assert parse_address(text).unit == "18"
    assert format_address(None, "MAIN") is None
