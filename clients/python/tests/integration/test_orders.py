"""The order lifecycle, driven entirely on hibernated orders so nothing can
trade. Every order is priced far below any crossable bid, rests in the
hibernated entry state, and is cancelled before the test ends."""

from __future__ import annotations

import pytest

from voltnir_sdk import (
    ModifyAction,
    NotFound,
    OrderValidationError,
    PermissionDenied,
    Side,
    Unauthenticated,
    VoltnirError,
    new_client_order_id,
)

from ._common import cancel_quietly, open_hibernated_order, wait_confirmed

_DUMMY_COID = "sdk-it-00000000-0000-4000-8000-000000000000"


# ── SubmitOrder (gated on create_order) ─────────────────────────────────────


@pytest.mark.rpc("SubmitOrder")
def test_happy_submit_order(admin, area, trading_env):
    coid, _cid = open_hibernated_order(admin, area)
    try:
        assert coid  # the response echoes the client_order_id we sent
        confirmed = wait_confirmed(admin, coid)
        assert confirmed.client_order_id == coid
    finally:
        cancel_quietly(admin, coid)


@pytest.mark.rpc("SubmitOrder")
def test_fail_submit_order_denied(lowperm, area, a_contract):
    with pytest.raises(PermissionDenied):
        lowperm.submit_order(
            client_order_id=new_client_order_id(),
            side=Side.BUY,
            price_cents=100,
            quantity_sub_mw=100,
            delivery_area_id=area,
            contract_id=int(a_contract),
            entry_state="HIBE",
        )


@pytest.mark.rpc("SubmitOrder")
def test_edge_submit_order_zero_quantity_rejected_locally(admin, area, a_contract):
    # A zero quantity is refused before anything is sent, so no order is placed.
    with pytest.raises(OrderValidationError):
        admin.submit_order(
            client_order_id=new_client_order_id(),
            side=Side.BUY,
            price_cents=100,
            quantity_sub_mw=0,
            delivery_area_id=area,
            contract_id=int(a_contract),
            entry_state="HIBE",
        )


# ── ModifyOrder (gated on modify_order) ─────────────────────────────────────


@pytest.mark.rpc("ModifyOrder")
def test_happy_modify_order_reprices(admin, resting_order):
    resp = admin.modify_order(
        client_order_id=resting_order,
        action=ModifyAction.MODIFY,
        price_cents=110,
        quantity_sub_mw=100,
    )
    assert resp.outcome in (0, 1)  # CONFIRMED / ACKNOWLEDGED


@pytest.mark.rpc("ModifyOrder")
def test_fail_modify_order_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.modify_order(
            client_order_id=_DUMMY_COID,
            action=ModifyAction.MODIFY,
            price_cents=110,
            quantity_sub_mw=100,
        )


@pytest.mark.rpc("ModifyOrder")
def test_edge_modify_order_zero_quantity_rejected_locally(admin):
    with pytest.raises(OrderValidationError):
        admin.modify_order(
            client_order_id=_DUMMY_COID,
            action=ModifyAction.MODIFY,
            price_cents=110,
            quantity_sub_mw=0,
        )


# ── CancelOrder (gated on cancel_order) ─────────────────────────────────────


@pytest.mark.rpc("CancelOrder")
def test_happy_cancel_order(admin, area, trading_env):
    coid, _cid = open_hibernated_order(admin, area)
    wait_confirmed(admin, coid)
    resp = admin.cancel_order(client_order_id=coid)
    assert resp.outcome in (0, 1)


@pytest.mark.rpc("CancelOrder")
def test_fail_cancel_order_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.cancel_order(client_order_id=_DUMMY_COID)


@pytest.mark.rpc("CancelOrder")
def test_edge_cancel_unknown_order_is_a_translated_error(admin):
    with pytest.raises(VoltnirError) as exc:
        admin.cancel_order(client_order_id=_DUMMY_COID)
    assert exc.value.rpc == "CancelOrder"


# ── CancelAllOrders (gated on cancel_order) ─────────────────────────────────


@pytest.mark.rpc("CancelAllOrders")
def test_happy_cancel_all_orders(admin, area, trading_env):
    coid, _cid = open_hibernated_order(admin, area)
    wait_confirmed(admin, coid)
    resp = admin.cancel_all_orders()
    assert resp.deleted >= 1


@pytest.mark.rpc("CancelAllOrders")
def test_fail_cancel_all_orders_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.cancel_all_orders()


@pytest.mark.rpc("CancelAllOrders")
def test_edge_cancel_all_orders_is_idempotent(admin, trading_env):
    admin.cancel_all_orders()
    assert admin.cancel_all_orders().deleted == 0


# ── GetOrder (member-scoped) ────────────────────────────────────────────────


@pytest.mark.rpc("GetOrder")
def test_happy_get_order(admin, resting_order):
    resp = admin.get_order(client_order_id=resting_order)
    assert resp.HasField("confirmed")
    assert resp.confirmed.client_order_id == resting_order


@pytest.mark.rpc("GetOrder")
async def test_happy_get_order_async(aadmin, resting_order):
    resp = await aadmin.get_order(client_order_id=resting_order)
    assert resp.confirmed.client_order_id == resting_order


@pytest.mark.rpc("GetOrder")
def test_fail_get_order_unauthenticated(badkey):
    with pytest.raises(Unauthenticated):
        badkey.get_order(client_order_id=_DUMMY_COID)


@pytest.mark.rpc("GetOrder")
def test_edge_get_order_unknown_id_is_not_found(admin):
    # An order the gateway has no record of is a not-found lookup.
    with pytest.raises(NotFound):
        admin.get_order(client_order_id=_DUMMY_COID)


# ── ListOrders (member-scoped) ──────────────────────────────────────────────


@pytest.mark.rpc("ListOrders")
def test_happy_list_orders_includes_the_resting_order(admin, area, resting_order):
    coids = {o.client_order_id for o in admin.list_orders(delivery_area=area).orders}
    assert resting_order in coids


@pytest.mark.rpc("ListOrders")
def test_fail_list_orders_unauthenticated(badkey):
    with pytest.raises(Unauthenticated):
        badkey.list_orders()


@pytest.mark.rpc("ListOrders")
def test_edge_list_orders_unknown_contract_is_empty(admin, area):
    # A contract filter matching nothing narrows to an empty book, not an error.
    # contract_id requires the area alongside it.
    orders = admin.list_orders(delivery_area=area, contract_id=999999999).orders
    assert list(orders) == []
