"""`Holiday` is part of the public package surface.

`set_holidays` takes a sequence of `Holiday` messages. Before this export the
only way to build one was an import from the private `_generated` module, which
the published documentation then had to show.
"""

from __future__ import annotations

import pytest

import voltnir_sdk
from voltnir_sdk import Holiday
from voltnir_sdk._generated import voltnir_api_v1_pb2 as pb2


def test_happy_set_holidays_accepts_the_public_holiday(client, fake):
    client.set_holidays(currency="eur", holidays=[Holiday(date="2099-12-25", label="xmas")])
    req = fake.requests["SetHolidays"]
    assert [(h.date, h.label) for h in req.holidays] == [("2099-12-25", "xmas")]


def test_fail_holiday_rejects_a_misspelled_field():
    with pytest.raises(ValueError, match='has no "day" field'):
        Holiday(day="2099-12-25")


def test_edge_public_holiday_is_the_wire_type_and_listed_in_all():
    assert Holiday is pb2.Holiday
    assert "Holiday" in voltnir_sdk.__all__
