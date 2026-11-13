import re

import pytest

from civic_qa.pipeline import load_sources

SOURCES = load_sources()


@pytest.mark.parametrize("key", SOURCES)
def test_province_is_a_two_letter_string(key):
    # Regression: an unquoted `province: ON` is parsed by YAML 1.1 as the boolean True,
    # and every row of that source then carried True instead of "ON".
    province = SOURCES[key]["province"]
    assert isinstance(province, str)
    assert re.fullmatch(r"[A-Z]{2}", province)
