"""Live streams: every Watch* RPC on both clients. A subscribe that yields a
frame, closes cleanly, or idles to a bounded deadline all count as live; an
append-only tail on a quiet sim legitimately sends nothing. No iterator is left
open past its test."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from voltnir_sdk import ContractsEventType, InvalidArgument, Unauthenticated

from ._common import asubscribe_ok, subscribe_ok

_DUMMY_COID = "sdk-it-00000000-0000-4000-8000-000000000000"

# Streams that take no required argument beyond the deadline.
_SIMPLE = [
    pytest.param("watch_state", marks=pytest.mark.rpc("WatchState"), id="WatchState"),
    pytest.param("watch_status", marks=pytest.mark.rpc("WatchStatus"), id="WatchStatus"),
    pytest.param("watch_trades", marks=pytest.mark.rpc("WatchTrades"), id="WatchTrades"),
    pytest.param("watch_public_trades", marks=pytest.mark.rpc("WatchPublicTrades"), id="WatchPublicTrades"),
    pytest.param("watch_trade_tape", marks=pytest.mark.rpc("WatchTradeTape"), id="WatchTradeTape"),
    pytest.param("watch_pnl", marks=pytest.mark.rpc("WatchPnl"), id="WatchPnl"),
    pytest.param("watch_messages", marks=pytest.mark.rpc("WatchMessages"), id="WatchMessages"),
    pytest.param("watch_audit_events", marks=pytest.mark.rpc("WatchAuditEvents"), id="WatchAuditEvents"),
    pytest.param("watch_m7_errors", marks=pytest.mark.rpc("WatchM7Errors"), id="WatchM7Errors"),
    pytest.param("watch_exchange_messages", marks=pytest.mark.rpc("WatchExchangeMessages"), id="WatchExchangeMessages"),
    pytest.param("watch_system_log", marks=pytest.mark.rpc("WatchSystemLog"), id="WatchSystemLog"),
]


@pytest.mark.parametrize("method", _SIMPLE)
def test_happy_stream_subscribes(admin, method):
    assert subscribe_ok(lambda: getattr(admin, method)(timeout=4.0))


@pytest.mark.parametrize("method", _SIMPLE)
async def test_happy_stream_subscribes_async(aadmin, method):
    assert await asubscribe_ok(getattr(aadmin, method)(timeout=4.0))


@pytest.mark.parametrize("method", _SIMPLE)
def test_fail_stream_unauthenticated(badkey, method):
    with pytest.raises(Unauthenticated):
        for _ in getattr(badkey, method)(timeout=4.0):
            break


@pytest.mark.parametrize("method", _SIMPLE)
def test_edge_stream_honours_a_tight_deadline(admin, method):
    # A short deadline is honoured: the subscribe completes (a frame or a clean
    # deadline) inside the bound rather than blocking forever.
    assert subscribe_ok(lambda: getattr(admin, method)(timeout=1.0))


# ── WatchContracts (needs a contract) ───────────────────────────────────────


def _snapshot(stream):
    """The stream's first event, which must be its SNAPSHOT; the iterator is
    closed with the return."""
    try:
        for ev in stream:
            assert ev.type == ContractsEventType.SNAPSHOT, ev.type
            return ev
        raise AssertionError("the stream closed before its SNAPSHOT")
    finally:
        close = getattr(stream, "close", None)
        if callable(close):
            close()


def _product_of(admin, area, contract_id) -> str:
    listed = admin.list_contracts(area_id=area).contracts
    return next(c.prod for c in listed if c.contract_id == contract_id)


@pytest.mark.rpc("WatchContracts")
def test_happy_watch_contracts_one_id_holds_exactly_that_contract(admin, area, a_contract):
    first = _snapshot(
        admin.watch_contracts(areas=[area], contract_ids=[int(a_contract)], timeout=4.0)
    )
    assert [(c.area_id, c.contract_id) for c in first.contracts] == [(area, a_contract)]


@pytest.mark.rpc("WatchContracts")
def test_happy_watch_contracts_by_product_holds_only_that_product(admin, area, a_contract):
    prod = _product_of(admin, area, a_contract)
    first = _snapshot(admin.watch_contracts(areas=[area], products=[prod], timeout=4.0))
    assert a_contract in {c.contract_id for c in first.contracts}
    assert {(c.area_id, c.prod) for c in first.contracts} == {(area, prod)}


@pytest.mark.rpc("WatchContracts")
async def test_happy_watch_contracts_async(aadmin, area, a_contract):
    assert await asubscribe_ok(
        aadmin.watch_contracts(areas=[area], contract_ids=[int(a_contract)], timeout=4.0)
    )


@pytest.mark.rpc("WatchContracts")
def test_edge_watch_contracts_unknown_id_is_an_empty_snapshot(admin, area):
    first = _snapshot(admin.watch_contracts(areas=[area], contract_ids=[999_999_999], timeout=4.0))
    assert list(first.contracts) == []


@pytest.mark.rpc("WatchContracts")
def test_fail_watch_contracts_unauthenticated(badkey, area, a_contract):
    with pytest.raises(Unauthenticated):
        for _ in badkey.watch_contracts(areas=[area], contract_ids=[int(a_contract)], timeout=4.0):
            break


@pytest.mark.rpc("WatchContracts")
def test_edge_watch_contracts_honours_a_tight_deadline(admin, area, a_contract):
    assert subscribe_ok(
        lambda: admin.watch_contracts(areas=[area], contract_ids=[int(a_contract)], timeout=1.0)
    )


# ── WatchOrder (opens with a snapshot of the resting order) ──────────────────


@pytest.mark.rpc("WatchOrder")
def test_happy_watch_order(admin, resting_order):
    assert subscribe_ok(lambda: admin.watch_order(client_order_id=resting_order, timeout=4.0))


@pytest.mark.rpc("WatchOrder")
async def test_happy_watch_order_async(aadmin, resting_order):
    assert await asubscribe_ok(aadmin.watch_order(client_order_id=resting_order, timeout=4.0))


@pytest.mark.rpc("WatchOrder")
def test_fail_watch_order_unauthenticated(badkey):
    with pytest.raises(Unauthenticated):
        for _ in badkey.watch_order(client_order_id=_DUMMY_COID, timeout=4.0):
            break


@pytest.mark.rpc("WatchOrder")
def test_edge_watch_order_honours_a_tight_deadline(admin, resting_order):
    assert subscribe_ok(lambda: admin.watch_order(client_order_id=resting_order, timeout=1.0))


# ── WatchOrders (the account-wide order feed) ───────────────────────────────


@pytest.mark.rpc("WatchOrders")
def test_happy_watch_orders(admin, area):
    assert subscribe_ok(lambda: admin.watch_orders(delivery_area=area, timeout=4.0))


@pytest.mark.rpc("WatchOrders")
async def test_happy_watch_orders_async(aadmin, area):
    assert await asubscribe_ok(aadmin.watch_orders(delivery_area=area, timeout=4.0))


@pytest.mark.rpc("WatchOrders")
def test_fail_watch_orders_unauthenticated(badkey):
    with pytest.raises(Unauthenticated):
        for _ in badkey.watch_orders(timeout=4.0):
            break


@pytest.mark.rpc("WatchOrders")
def test_edge_watch_orders_honours_a_tight_deadline(admin):
    assert subscribe_ok(lambda: admin.watch_orders(timeout=1.0))


# ── WatchTradeTape (opens with a SNAPSHOT) ──────────────────────────────────


@pytest.mark.rpc("WatchTradeTape")
def test_happy_watch_trade_tape_opens_with_a_snapshot(admin):
    stream = admin.watch_trade_tape(timeout=4.0)
    try:
        first = next(iter(stream))
    finally:
        stream.close()
    assert first.type == type(first).SNAPSHOT
    times = [r.exec_time_ms for r in first.rows]
    assert times == sorted(times), "the snapshot is oldest first"


@pytest.mark.rpc("WatchTradeTape")
def test_fail_watch_trade_tape_unauthenticated(badkey):
    stream = badkey.watch_trade_tape(timeout=4.0)
    try:
        with pytest.raises(Unauthenticated):
            next(iter(stream))
    finally:
        stream.close()


@pytest.mark.rpc("WatchTradeTape")
def test_edge_watch_trade_tape_rows_are_listed_under_an_area(admin):
    # A print whose contract the gateway no longer holds is left out, so every
    # row it does send names its delivery area. An empty tape passes.
    stream = admin.watch_trade_tape(timeout=4.0)
    try:
        first = next(iter(stream))
    finally:
        stream.close()
    assert all(r.HasField("area_id") and r.area_id.value for r in first.rows)


# ── WatchHub2Hub (opens with a snapshot; XBID may never update on a sim) ────


def _hub_window(hours: int = 24) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return now.strftime(fmt), (now + timedelta(hours=hours)).strftime(fmt)


def _first_hub_event(client, area, win_from, win_to, timeout=4.0):
    stream = client.watch_hub2hub(
        delivery_area_from=area, delivery_from=win_from, delivery_to=win_to, timeout=timeout
    )
    try:
        return next(iter(stream))
    finally:
        stream.close()


@pytest.mark.rpc("WatchHub2Hub")
def test_happy_watch_hub2hub_opens_with_a_snapshot(admin, area):
    first = _first_hub_event(admin, area, *_hub_window())
    assert first.WhichOneof("event") == "snapshot"
    assert isinstance(first.snapshot.capacity_connected, bool)


@pytest.mark.rpc("WatchHub2Hub")
async def test_happy_watch_hub2hub_async(aadmin, area):
    win_from, win_to = _hub_window()
    assert await asubscribe_ok(
        aadmin.watch_hub2hub(
            delivery_area_from=area, delivery_from=win_from, delivery_to=win_to, timeout=4.0
        )
    )


@pytest.mark.rpc("WatchHub2Hub")
def test_fail_watch_hub2hub_unauthenticated(badkey, area):
    with pytest.raises(Unauthenticated):
        _first_hub_event(badkey, area, *_hub_window())


@pytest.mark.rpc("WatchHub2Hub")
def test_fail_watch_hub2hub_unparseable_window(admin, area):
    with pytest.raises(InvalidArgument, match="delivery_from"):
        _first_hub_event(admin, area, "yesterday", _hub_window()[1])


@pytest.mark.rpc("WatchHub2Hub")
def test_edge_watch_hub2hub_empty_window_is_an_empty_snapshot(admin, area):
    # A window that ends where it starts admits no delivery period.
    win_from, _ = _hub_window()
    first = _first_hub_event(admin, area, win_from, win_from)
    assert first.WhichOneof("event") == "snapshot"
    assert list(first.snapshot.data) == []
