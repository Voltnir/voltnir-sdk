"""Every argument a caller passes reaches the server. Both clients.

A wrapper that accepts ten arguments and forwards nine is indistinguishable
from a correct one at the call site: no error, no warning, just an order that
is not the order you asked for. The consequences are specific and expensive:

    submit_order    losing display_qty          an iceberg becomes fully lit
    submit_order    losing v_member_short_id    order tagged to the wrong member
    create_member   losing cash_limit           a member with no cash ceiling
    set_cash_limit  ignoring currency           a GBP limit in the EUR pool
    set_permissions losing permissions          a user stripped of access

Each is a plausible one-line slip, so the money-touching wrappers are called
here with EVERY parameter set to a distinctive value and the received message
is asserted field by field.

Values must be non-default. proto3 does not serialise a field set to its type
default, so `assert req.foo == 0` holds whether or not the wrapper sent it.
"""

from __future__ import annotations

import pytest

from voltnir_sdk import Side
from voltnir_sdk._generated import voltnir_api_v1_pb2 as pb2

_OID = "11111111-1111-4111-8111-111111111111"
_AREA = "10YBE----------2"


# ── submit_order: the whole surface, both clients ───────────────────────────

_FULL_SUBMIT = dict(
    client_order_id=_OID,
    side=Side.SELL,
    delivery_area_id=_AREA,
    price_cents=5007,
    quantity_sub_mw=1500,
    contract_id=12345,
    order_type=pb2.OrderType.ICEBERG,
    exe_restriction=pb2.ExeRestriction.AON,
    validity_res=pb2.ValidityRes.GTD,
    entry_state="HIBE",
    display_qty_sub_mw=250,
    validity_date="2026-07-20T18:00:00Z",
    v_member_short_id="VM001",
)


def _assert_submit_fields(req) -> None:
    assert req.client_order_id == _OID
    assert req.side == Side.SELL
    assert req.delivery_area_id == _AREA
    assert req.price == 5007
    assert req.quantity == 1500
    assert req.contract_id == 12345
    assert req.order_type == pb2.OrderType.ICEBERG
    assert req.exe_restriction == pb2.ExeRestriction.AON
    assert req.validity_res == pb2.ValidityRes.GTD
    assert req.entry_state == "HIBE"
    assert req.display_qty == 250
    assert req.validity_date == "2026-07-20T18:00:00Z"
    assert req.v_member_short_id == "VM001"


def test_happy_submit_order_forwards_every_argument(client, fake):
    client.submit_order(**_FULL_SUBMIT)
    _assert_submit_fields(fake.requests["SubmitOrder"])


async def test_happy_submit_order_forwards_every_argument_async(aclient, fake):
    """The async client builds its own request, so sync coverage does not imply it."""
    await aclient.submit_order(**_FULL_SUBMIT)
    _assert_submit_fields(fake.requests["SubmitOrder"])


def test_happy_submit_order_forwards_the_product_path(client, fake):
    """The alternate contract identity, which the contract_id path never exercises."""
    client.submit_order(
        client_order_id=_OID,
        side=Side.BUY,
        delivery_area_id=_AREA,
        price_cents=5000,
        quantity_sub_mw=1000,
        product="XBID_Hour_Power",
        delivery_start="2026-07-20T10:00:00Z",
    )
    req = fake.requests["SubmitOrder"]
    assert req.product == "XBID_Hour_Power"
    assert req.delivery_start == "2026-07-20T10:00:00Z"


def test_happy_submit_order_forwards_pre_arranged_account(client, fake):
    """PRE_ARRANGED names a counterparty; dropping it sends the trade elsewhere."""
    client.submit_order(
        client_order_id=_OID,
        side=Side.BUY,
        delivery_area_id=_AREA,
        contract_id=1,
        price_cents=5000,
        quantity_sub_mw=1000,
        order_type=pb2.OrderType.PRE_ARRANGED,
        pre_arranged_acct="CPTY-42",
    )
    assert fake.requests["SubmitOrder"].pre_arranged_acct == "CPTY-42"


# ── modify_order ────────────────────────────────────────────────────────────

_FULL_MODIFY = dict(
    client_order_id=_OID,
    action=pb2.ModifyAction.MODIFY,
    price_cents=5100,
    quantity_sub_mw=800,
    display_qty_sub_mw=200,
    validity_res=pb2.ValidityRes.GTD,
    validity_date="2026-07-20T19:00:00Z",
    v_member_short_id="VM002",
)


def _assert_modify_fields(req) -> None:
    assert req.client_order_id == _OID
    assert req.action == pb2.ModifyAction.MODIFY
    assert req.price.value == 5100
    assert req.quantity.value == 800
    assert req.display_qty == 200
    assert req.validity_res == pb2.ValidityRes.GTD
    assert req.validity_date == "2026-07-20T19:00:00Z"
    assert req.v_member_short_id == "VM002"


def test_happy_modify_order_forwards_every_argument(client, fake):
    client.modify_order(**_FULL_MODIFY)
    _assert_modify_fields(fake.requests["ModifyOrder"])


async def test_happy_modify_order_forwards_every_argument_async(aclient, fake):
    await aclient.modify_order(**_FULL_MODIFY)
    _assert_modify_fields(fake.requests["ModifyOrder"])


# ── risk controls: dropping any of these removes a limit ────────────────────


def test_happy_create_member_forwards_both_cash_limits(client, fake):
    """A dropped cash_limit creates a member with no cash ceiling."""
    client.create_member(
        name="desk-a", max_position=7000, cash_limit=500_000, cash_limit_gbp=250_000
    )
    req = fake.requests["CreateMember"]
    assert req.name == "desk-a"
    assert req.max_position == 7000
    assert req.cash_limit == 500_000
    assert req.cash_limit_gbp == 250_000


async def test_happy_create_member_forwards_both_cash_limits_async(aclient, fake):
    await aclient.create_member(
        name="desk-a", max_position=7000, cash_limit=500_000, cash_limit_gbp=250_000
    )
    req = fake.requests["CreateMember"]
    assert req.cash_limit == 500_000
    assert req.cash_limit_gbp == 250_000


def test_happy_patch_member_forwards_every_field(client, fake):
    client.patch_member(
        id="m-1",
        name="desk-b",
        max_position=9000,
        active=False,
        cash_limit_cents=111_000,
        cash_limit_gbp_cents=222_000,
    )
    req = fake.requests["PatchMember"]
    assert req.id == "m-1"
    assert req.name.value == "desk-b"
    assert req.max_position.value == 9000
    assert req.active.value is False
    assert req.cash_limit.value == 111_000
    assert req.cash_limit_gbp.value == 222_000


@pytest.mark.parametrize("currency", ["eur", "gbp"])
def test_happy_set_cash_limit_forwards_the_currency(client, fake, currency):
    """Ignoring `currency` writes a GBP limit into the EUR pool, or vice versa.

    The pools are enforced separately, so a misdirected limit silently removes
    the ceiling on one of them.
    """
    client.set_cash_limit(cents=750_000, currency=currency)
    req = fake.requests["SetCashLimit"]
    assert req.cents == 750_000
    assert req.currency == currency


@pytest.mark.parametrize("currency", ["eur", "gbp"])
def test_happy_holiday_calendar_ops_forward_the_currency(client, fake, currency):
    """The EUR and GBP calendars roll on different dates; the wrong one is wrong."""
    client.add_holiday(currency=currency, date="2099-01-01", label="sentinel")
    req = fake.requests["AddHoliday"]
    assert req.currency == currency
    assert req.date == "2099-01-01"
    assert req.label == "sentinel"

    client.remove_holiday(currency=currency, date="2099-01-01")
    assert fake.requests["RemoveHoliday"].currency == currency

    client.set_holidays(
        currency=currency, holidays=[pb2.Holiday(date="2099-12-25", label="xmas")]
    )
    req = fake.requests["SetHolidays"]
    assert req.currency == currency
    assert [h.date for h in req.holidays] == ["2099-12-25"]


def test_happy_set_permissions_forwards_the_permission_list(client, fake):
    """A dropped list silently strips every permission from the user."""
    client.set_permissions(user_id="u-1", permissions=["create_order", "read_state"])
    req = fake.requests["SetPermissions"]
    assert req.user_id == "u-1"
    assert list(req.permissions) == ["create_order", "read_state"]


def test_happy_create_user_forwards_the_permission_list(client, fake):
    client.create_user(username="alice", permissions=["read_state"])
    req = fake.requests["CreateUser"]
    assert req.username == "alice"
    assert list(req.permissions) == ["read_state"]


def test_happy_set_user_members_forwards_the_member_list(client, fake):
    client.set_user_members(user_id="u-1", member_ids=["m-1", "m-2"])
    req = fake.requests["SetUserMembers"]
    assert list(req.member_ids) == ["m-1", "m-2"]


def test_happy_set_contract_limit_forwards_the_quantity(client, fake):
    client.set_contract_limit(quantity=4200)
    assert fake.requests["SetContractLimit"].quantity == 4200


def test_happy_set_trading_allowed_forwards_both_states(client, fake):
    """The kill switch must send what it was told, in both directions.

    `False` is the proto3 default, so it is the direction a dropped argument
    silently produces.
    """
    client.set_trading_allowed(allowed=True)
    assert fake.requests["SetTradingAllowed"].allowed is True

    client.set_trading_allowed(allowed=False)
    assert fake.requests["SetTradingAllowed"].allowed is False


def test_happy_set_cash_fail_closed_forwards_both_states(client, fake):
    client.set_cash_fail_closed(enabled=True)
    assert fake.requests["SetCashFailClosed"].enabled is True

    client.set_cash_fail_closed(enabled=False)
    assert fake.requests["SetCashFailClosed"].enabled is False


# ── read paths whose filters silently narrow results ────────────────────────


def test_happy_get_hub2hub_forwards_every_filter(client, fake):
    """A dropped delivery_area_to widens the query to every destination."""
    client.get_hub2hub(
        delivery_area_from=_AREA,
        delivery_from="2026-07-20T10:00:00Z",
        delivery_to="2026-07-21T10:00:00Z",
        delivery_area_to="10YNL----------L",
    )
    req = fake.requests["GetHub2Hub"]
    assert req.delivery_area_from == _AREA
    assert req.delivery_from == "2026-07-20T10:00:00Z"
    assert req.delivery_to == "2026-07-21T10:00:00Z"
    assert req.delivery_area_to == "10YNL----------L"


def test_happy_list_public_trades_forwards_every_filter(client, fake):
    client.list_public_trades(limit=25, contract_id=999, area_id=_AREA)
    req = fake.requests["ListPublicTrades"]
    assert req.limit == 25
    assert req.contract_id == 999
    assert req.area_id == _AREA


def test_happy_get_pnl_forwards_the_member_scope(client, fake):
    """Member scoping silently narrows the book you think you are seeing."""
    client.get_pnl(v_member_short_id="VM007")
    assert fake.requests["GetPnl"].v_member_short_id == "VM007"


def test_happy_export_forwards_its_date_range_on_both_clients(client, fake):
    """A dropped range exports everything, or nothing, with no error."""
    list(
        client.export_orders(
            format=pb2.ExportFormat.JSON,
            from_="2026-07-01T00:00:00Z",
            to="2026-07-02T00:00:00Z",
        )
    )
    req = fake.requests["ExportOrders"]
    assert getattr(req, "from") == "2026-07-01T00:00:00Z"
    assert req.to == "2026-07-02T00:00:00Z"
    assert req.format == pb2.ExportFormat.JSON


async def test_happy_export_forwards_its_date_range_async(aclient, fake):
    """The `from_` -> `from` remap is duplicated on the async client."""
    async for _ in aclient.export_orders(
        format=pb2.ExportFormat.JSON,
        from_="2026-07-01T00:00:00Z",
        to="2026-07-02T00:00:00Z",
    ):
        pass
    req = fake.requests["ExportOrders"]
    assert getattr(req, "from") == "2026-07-01T00:00:00Z"
    assert req.to == "2026-07-02T00:00:00Z"


async def test_happy_async_streams_forward_their_filters(aclient, fake):
    """Filters on an async subscription must reach the wire like the sync ones."""
    async for _ in aclient.watch_orders(
        delivery_area=_AREA, contract_id="42", v_member_short_id="VM001"
    ):
        break
    req = fake.requests["WatchOrders"]
    assert req.delivery_area == _AREA
    assert req.contract_id == "42"
    assert req.v_member_short_id == "VM001"


async def test_happy_async_streams_attach_auth_metadata(aclient, fake):
    """Streaming calls carry the credential too, on the async path as well."""
    async for _ in aclient.watch_state():
        break
    assert fake.metadata["WatchState"]["authorization"] == "Bearer test-key"
