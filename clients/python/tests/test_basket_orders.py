"""Basket orders: the request a basket builds, and the rules checked before
anything is sent."""

from __future__ import annotations

import pytest

from voltnir_sdk import ExeRestriction, OrderValidationError, Side, ValidityRes
from voltnir_sdk._orders import build_submit_basket_request

_AREA = "10YBE----------2"


def _order(n: int, **over) -> dict:
    order = dict(
        client_order_id=f"00000000-0000-4000-8000-{n:012}",
        side=Side.BUY,
        delivery_area_id=_AREA,
        contract_id=100 + n,
        price_cents=5000,
        quantity_sub_mw=1000,
    )
    order.update(over)
    return order


def _fok(n: int) -> dict:
    return _order(n, exe_restriction=ExeRestriction.FOK, validity_res=ValidityRes.VALIDITY_NON)


def test_happy_a_basket_carries_every_order_in_request_order():
    req = build_submit_basket_request(
        list_exec_inst="linked", orders=[_fok(1), _fok(2)], basket_ref="ref"
    )
    assert req.list_exec_inst == "linked"
    assert req.basket_ref == "ref"
    assert [o.contract_id for o in req.orders] == [101, 102]
    assert all(o.exe_restriction == ExeRestriction.FOK for o in req.orders)


def test_edge_a_hundred_orders_are_one_basket_and_the_reference_is_optional():
    req = build_submit_basket_request(
        list_exec_inst="none", orders=[_order(n) for n in range(100)]
    )
    assert len(req.orders) == 100
    assert req.basket_ref == ""


@pytest.mark.parametrize(
    "kwargs, says",
    [
        (dict(list_exec_inst="LNKD", orders=[_order(1)]), "list_exec_inst must be one of"),
        (dict(list_exec_inst="none", orders=[]), "at least one order"),
        (dict(list_exec_inst="none", orders=[_order(n) for n in range(101)]), "at most 100"),
        (dict(list_exec_inst="valid", orders=[_order(1), _order(1)]), "[1] client_order_id"),
        (dict(list_exec_inst="linked", orders=[_fok(1), _order(2)]), "[1] is not"),
        (
            dict(list_exec_inst="valid", orders=[_order(1), _order(2, delivery_end="2030-01-01T12:00:00Z")]),
            "[1] a basket cannot create a user-defined block",
        ),
        (dict(list_exec_inst="none", orders=[_order(1), _order(2, quantity_sub_mw=0)]), "[1] quantity_sub_mw"),
    ],
)
def test_fail_each_local_rule_names_the_order(kwargs, says):
    with pytest.raises(OrderValidationError) as exc:
        build_submit_basket_request(**kwargs)
    assert says in str(exc.value)
