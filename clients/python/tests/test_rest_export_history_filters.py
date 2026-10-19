"""The history filters of `export_orders` and `export_trades`, against the
loopback REST fake.

Both exports take the filters of the history read they mirror, so a report
holds the rows `query_audit_orders` or `query_audit_trades` pages for the same
window and filters. Orders add `status`, trades add `time_basis`; the gateway
reads one body shape for both and ignores the other export's field, so each
export takes only its own. These tests pin that every filter reaches the wire
under its own name, that the gateway's refusal of a bad value surfaces as the
typed error naming the method, and that a filter one export does not have is
refused before anything is sent. `test_rest_export.py` holds the shared
request, polling, streaming and timeout behaviour.
"""

from __future__ import annotations

import inspect

import grpc
import pytest
import pytest_asyncio
from conftest import REST_KEY
from voltnir_sdk import (
    AsyncVoltnirClient,
    InvalidArgument,
    PermissionDenied,
    VoltnirClient,
)

_FROM, _TO = "2026-07-01T00:00:00Z", "2026-07-02T00:00:00Z"
_WINDOW = {"format": "json", "from": _FROM, "to": _TO}
_SHARED = {
    "area": "10YNL----------L",
    "product": "XBID_Quarter_Hour_Power",
    "user_code": "TRD001",
    "v_member_short_id": "VM001",
    "voltnir_user_short_id": "U001",
    "voltnir_username": "alice",
}
_ORDERS = {**_SHARED, "status": "ACTIVE"}
_TRADES = {**_SHARED, "time_basis": "execution"}
_BAD_TIME_BASIS = "invalid time_basis 'settlement': expected 'execution' or 'delivery'"
_BAD_STATUS = (
    "invalid status 'REJECTED': expected ACTIVE (ACTI), INACTIVE (INAC) or HIBERNATED "
    "(HIB), in any case. REJECTED is not an M7 order state: a plain order the "
    "exchange refuses has no row here, and its refusal is on the audit trail as "
    "order_rejected"
)


@pytest.fixture
def rclient(server, rest):
    c = VoltnirClient(
        host="127.0.0.1", port=server, api_key=REST_KEY, timeout=5.0, rest_url=rest.url
    )
    yield c
    c.close()


@pytest_asyncio.fixture
async def raclient(server, rest):
    c = AsyncVoltnirClient(
        host="127.0.0.1", port=server, api_key=REST_KEY, timeout=5.0, rest_url=rest.url
    )
    yield c
    await c.close()


def _posted(rest) -> tuple[str, dict]:
    _method, path, _headers, sent = rest.posts()[0]
    return path, sent


# ── happy ───────────────────────────────────────────────────────────────────


def test_happy_every_orders_filter_crosses_under_its_wire_name(rclient, rest):
    list(rclient.export_orders(format="json", from_=_FROM, to=_TO, **_ORDERS))
    assert _posted(rest) == ("/api/v1/audit/export/orders", {**_WINDOW, **_ORDERS})


def test_happy_every_trades_filter_crosses_under_its_wire_name(rclient, rest):
    list(rclient.export_trades(format="json", from_=_FROM, to=_TO, **_TRADES))
    assert _posted(rest) == ("/api/v1/audit/export/trades", {**_WINDOW, **_TRADES})


async def test_happy_async_orders_filters_cross_and_the_file_arrives(raclient, rest):
    rest.body, rest.pending = b'[{"order_id": 1}]', 1
    chunks = [
        c async for c in raclient.export_orders(format="json", from_=_FROM, to=_TO, **_ORDERS)
    ]
    assert b"".join(chunks) == b'[{"order_id": 1}]'
    assert _posted(rest) == ("/api/v1/audit/export/orders", {**_WINDOW, **_ORDERS})


async def test_happy_async_trades_filters_cross_and_the_file_arrives(raclient, rest):
    rest.body = b"trade_id\n7\n"
    chunks = [
        c async for c in raclient.export_trades(format="csv", from_=_FROM, to=_TO, **_TRADES)
    ]
    assert b"".join(chunks) == b"trade_id\n7\n"
    assert _posted(rest) == (
        "/api/v1/audit/export/trades",
        {**_WINDOW, "format": "csv", **_TRADES},
    )


# ── fail ────────────────────────────────────────────────────────────────────


def test_fail_an_unknown_time_basis_is_invalid_argument_naming_export_trades(rclient, rest):
    rest.post_status, rest.error = 400, _BAD_TIME_BASIS
    with pytest.raises(InvalidArgument) as info:
        list(rclient.export_trades(format="json", from_=_FROM, to=_TO, time_basis="settlement"))
    assert info.value.code is grpc.StatusCode.INVALID_ARGUMENT
    assert info.value.message == _BAD_TIME_BASIS
    assert info.value.rpc == "export_trades"
    assert _posted(rest)[1]["time_basis"] == "settlement"
    assert rest.polls() == []


async def test_fail_async_an_unknown_time_basis_is_invalid_argument(raclient, rest):
    rest.post_status, rest.error = 400, _BAD_TIME_BASIS
    with pytest.raises(InvalidArgument) as info:
        _ = [
            c
            async for c in raclient.export_trades(
                format="json", from_=_FROM, to=_TO, time_basis="settlement"
            )
        ]
    assert info.value.message == _BAD_TIME_BASIS
    assert info.value.rpc == "export_trades"
    assert rest.polls() == []


def test_fail_an_unknown_status_is_invalid_argument_naming_export_orders(rclient, rest):
    rest.post_status, rest.error = 400, _BAD_STATUS
    with pytest.raises(InvalidArgument) as info:
        list(rclient.export_orders(format="json", from_=_FROM, to=_TO, status="REJECTED"))
    assert info.value.code is grpc.StatusCode.INVALID_ARGUMENT
    assert info.value.message == _BAD_STATUS
    assert info.value.rpc == "export_orders"
    assert rest.polls() == []


@pytest.mark.parametrize("method", ["export_orders", "export_trades"])
def test_fail_a_member_outside_the_scope_is_permission_denied(rclient, rest, method):
    rest.post_status, rest.error = 403, "Forbidden"
    with pytest.raises(PermissionDenied, match="Forbidden") as info:
        list(
            getattr(rclient, method)(
                format="json", from_=_FROM, to=_TO, v_member_short_id="VM999"
            )
        )
    assert info.value.code is grpc.StatusCode.PERMISSION_DENIED
    assert info.value.rpc == method
    assert _posted(rest)[1]["v_member_short_id"] == "VM999"


@pytest.mark.parametrize(
    "method,foreign",
    [("export_trades", "status"), ("export_orders", "time_basis")],
)
def test_fail_the_other_exports_filter_is_refused_before_sending(rclient, rest, method, foreign):
    # The gateway would ignore it, so a report would silently come back unfiltered.
    with pytest.raises(TypeError, match=foreign):
        getattr(rclient, method)(format="json", from_=_FROM, to=_TO, **{foreign: "x"})
    assert rest.requests == []


# ── edge ────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("method", ["export_orders", "export_trades"])
def test_edge_an_omitted_filter_is_left_out_not_sent_empty(rclient, rest, method):
    list(getattr(rclient, method)(format="json", from_=_FROM, to=_TO, user_code=None))
    assert _posted(rest)[1] == _WINDOW


@pytest.mark.parametrize("method", ["export_orders", "export_trades"])
def test_edge_an_empty_filter_crosses_as_given_for_the_gateway_to_read_as_none(
    rclient, rest, method
):
    list(getattr(rclient, method)(format="json", from_=_FROM, to=_TO, voltnir_username=""))
    assert _posted(rest)[1] == {**_WINDOW, "voltnir_username": ""}


@pytest.mark.parametrize("basis", ["delivery", "Execution", "EXECUTION"])
def test_edge_time_basis_crosses_unchanged_for_the_gateway_to_read_in_any_case(
    rclient, rest, basis
):
    list(rclient.export_trades(format="json", from_=_FROM, to=_TO, time_basis=basis))
    assert _posted(rest)[1] == {**_WINDOW, "time_basis": basis}


@pytest.mark.parametrize("method", ["export_orders", "export_trades"])
def test_edge_both_clients_take_the_same_parameters(method):
    sync = inspect.signature(getattr(VoltnirClient, method)).parameters
    asyn = inspect.signature(getattr(AsyncVoltnirClient, method)).parameters
    assert list(sync) == list(asyn)
    assert [n for n, p in sync.items() if p.default is inspect.Parameter.empty] == [
        "self", "format", "from_", "to",
    ]


def test_edge_the_trades_docstring_states_both_time_bases_and_the_refusal():
    doc = inspect.getdoc(VoltnirClient.export_trades) or ""
    for phrase in ('`"delivery"`', '`"execution"`', "`InvalidArgument`", "overlaps"):
        assert phrase in doc, phrase
