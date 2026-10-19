"""`Outcome` is part of the public package surface.

`modify_order` and `cancel_order` answer with an `outcome` that says whether the
exchange confirmed the change or only acknowledged receipt. `CONFIRMED` is the
enum's zero value, so truthiness cannot tell the two apart; the caller has to
compare against a named member, which must be importable from the package.
"""

from __future__ import annotations

import pytest

import voltnir_sdk
from voltnir_sdk import Outcome
from voltnir_sdk._generated import voltnir_api_v1_pb2 as pb2


def test_happy_cancel_outcome_compares_against_the_public_enum(client):
    resp = client.cancel_order(client_order_id="coid-1")
    assert resp.outcome == Outcome.CONFIRMED
    assert resp.outcome != Outcome.ACKNOWLEDGED


def test_fail_outcome_rejects_an_unknown_member_name():
    with pytest.raises(ValueError):
        Outcome.Value("PENDING")


def test_edge_public_outcome_is_the_wire_type_and_listed_in_all():
    assert Outcome is pb2.Outcome
    assert Outcome.CONFIRMED == 0
    assert Outcome.ACKNOWLEDGED == 1
    assert "Outcome" in voltnir_sdk.__all__
