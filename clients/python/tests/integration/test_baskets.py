"""Basket orders against a live gateway, on hibernated orders priced far below
anything crossable, so nothing can trade. Every basket is cancelled before the
test ends."""

from __future__ import annotations

import pytest

from voltnir_sdk import NotFound, OrderState, PermissionDenied, Side, new_client_order_id

from ._common import (
    _SAFE_PRICE_CENTS,
    _SAFE_QTY_SUB_MW,
    _orderable_candidates,
    cancel_quietly,
    wait_confirmed,
)


def _hibernated(area: str, contract_id: str) -> dict:
    return dict(
        client_order_id=new_client_order_id(),
        side=Side.BUY,
        price_cents=_SAFE_PRICE_CENTS,
        quantity_sub_mw=_SAFE_QTY_SUB_MW,
        delivery_area_id=area,
        contract_id=int(contract_id),
        entry_state="HIBE",
    )


def _two_orders(admin, area: str) -> list[dict]:
    contracts = _orderable_candidates(admin, area)
    if not contracts:
        pytest.skip(f"no orderable contract in {area}")
    first = contracts[0].contract_id
    second = contracts[1].contract_id if len(contracts) > 1 else first
    return [_hibernated(area, first), _hibernated(area, second)]


# ── SubmitBasket (gated on create_order) ────────────────────────────────────


def _enter_basket(admin, area: str) -> tuple[str, list[dict]]:
    """A `none` basket of two hibernated orders, each confirmed carrying the
    basket's reference."""
    orders = _two_orders(admin, area)
    ref = new_client_order_id()
    resp = admin.submit_basket(list_exec_inst="none", orders=orders, basket_ref=ref)
    assert resp.basket_ref == ref
    assert resp.list_exec_inst == "none"
    assert [o.client_order_id for o in resp.orders] == [o["client_order_id"] for o in orders]
    for o in orders:
        assert wait_confirmed(admin, o["client_order_id"]).basket_ref == ref
    return ref, orders


@pytest.mark.rpc("SubmitBasket")
def test_happy_submit_basket(admin, area, trading_env):
    ref, orders = _enter_basket(admin, area)
    for o in orders:
        cancel_quietly(admin, o["client_order_id"])


@pytest.mark.rpc("CancelBasket")
def test_happy_cancel_basket(admin, area, trading_env):
    ref, orders = _enter_basket(admin, area)
    try:
        cancelled = admin.cancel_basket(ref)
        assert cancelled.basket_ref == ref
        assert cancelled.cancelled == len(orders)
    finally:
        for o in orders:
            cancel_quietly(admin, o["client_order_id"])


@pytest.mark.rpc("SubmitBasket")
def test_fail_submit_basket_denied(lowperm, area, a_contract):
    with pytest.raises(PermissionDenied):
        lowperm.submit_basket(list_exec_inst="none", orders=[_hibernated(area, a_contract)])


@pytest.mark.rpc("SubmitBasket")
def test_edge_a_one_order_basket_carries_the_basket_id_the_answer_reports(
    admin, area, a_contract, trading_env
):
    # Whether the exchange numbers a one-order list is its own decision; the
    # gateway reports what it said, and the order carries the same id.
    order = _hibernated(area, a_contract)
    try:
        resp = admin.submit_basket(list_exec_inst="valid", orders=[order])
        assert resp.basket_ref, "the gateway minted a reference"
        assert resp.orders[0].state != OrderState.REJECTED, resp.orders[0].reason
        held = wait_confirmed(admin, order["client_order_id"])
        assert held.basket_id == resp.basket_id
        assert held.basket_ref == resp.basket_ref
    finally:
        cancel_quietly(admin, order["client_order_id"])


# ── CancelBasket (gated on delete_order) ────────────────────────────────────


@pytest.mark.rpc("CancelBasket")
def test_fail_cancel_basket_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.cancel_basket(new_client_order_id())


@pytest.mark.rpc("CancelBasket")
def test_edge_cancel_basket_of_an_unknown_reference_is_not_found(admin):
    with pytest.raises(NotFound):
        admin.cancel_basket(new_client_order_id())
