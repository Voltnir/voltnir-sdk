"""Unit helpers and order-request construction: happy / fail / edge.

These are the highest-consequence code paths in the SDK and they are pure, so
they get tested directly rather than through a server. A wrong conversion here
is a wrong trade, and no amount of transport testing catches it.

The organising question throughout: *what does a trader lose if this is wrong?*
A silently rounded price loses a tick on every clip. A 100x unit error loses the
position. A MODIFY that restates the original size re-inflates an exposure the
trader believes is partly closed.

Note the split: the order builders take WIRE units (cents, sub-MW), matching the
REST / gRPC / WS contract and every response message. The `units` helpers exist
for display and reporting code that genuinely holds decimals, and are tested
here because a conversion bug in them is just as expensive.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from google.protobuf import wrappers_pb2

from voltnir_sdk import (
    CASH_SCALE,
    PNL_SCALE,
    PRICE_SCALE,
    QUANTITY_SCALE,
    OrderValidationError,
    UnitConversionError,
    cents_to_eur,
    cents_to_price,
    eur_to_cents,
    eur_to_q8,
    new_client_order_id,
    price_to_cents,
    q8_to_eur,
    quantity_to_sub_mw,
    sub_mw_to_quantity,
)
from voltnir_sdk._generated import voltnir_api_v1_pb2 as pb2
from voltnir_sdk._orders import (
    build_modify_order_request,
    build_patch_member_request,
    build_submit_order_request,
)

_OID = "11111111-1111-4111-8111-111111111111"
_AREA = "10YBE----------2"


def _submit(**overrides):
    base = dict(
        client_order_id=_OID,
        side=pb2.Side.BUY,
        delivery_area_id=_AREA,
        contract_id=12345,
        price_cents=5000,        # 50.00 CCY/MWh
        quantity_sub_mw=1000,    # 1.0 MW
    )
    base.update(overrides)
    return build_submit_order_request(**base)


# ── units: happy ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "value,expected",
    [
        (Decimal("50.07"), 5007),
        (50, 5000),
        ("50.07", 5007),
        (50.07, 5007),          # float via repr(), not binary approximation
        (Decimal("-12.50"), -1250),   # negative prices are real on power markets
        (0, 0),
        (Decimal("0.01"), 1),   # one tick
    ],
)
def test_happy_price_to_cents(value, expected):
    assert price_to_cents(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (Decimal("1.5"), 1500),
        (1, 1000),
        ("0.001", 1),           # one tick
        (0.5, 500),
    ],
)
def test_happy_quantity_to_sub_mw(value, expected):
    assert quantity_to_sub_mw(value) == expected


def test_happy_round_trip_is_exact():
    for cents in (5007, -1250, 0, 1, 999999):
        assert price_to_cents(cents_to_price(cents)) == cents
    for sub_mw in (1500, 1, 0, 250000):
        assert quantity_to_sub_mw(sub_mw_to_quantity(sub_mw)) == sub_mw


def test_happy_clean_floats_convert_exactly():
    """A float that IS an exact decimal converts to what it looks like.

    `Decimal(repr(1.1))` is exactly `1.1`, not the binary approximation
    1.100000000000000088817841970012523233890533447265625 that
    `Decimal(1.1)` would give.
    """
    assert price_to_cents(1.1) == 110
    assert price_to_cents(50.07) == 5007
    assert quantity_to_sub_mw(0.5) == 500


def test_fail_accumulated_float_error_is_rejected_not_rounded():
    """A float carrying arithmetic error is refused, not quietly snapped to a tick.

    `0.1 + 0.2` is 0.30000000000000004, which is not a representable price. The
    tempting behaviour is to round it to 30 cents "because that is obviously
    what they meant". The SDK refuses instead: if a desk's pricing arithmetic
    has drifted off the tick grid, silently correcting it hides the bug and
    trades a price nobody computed. The error names the value, so the fix
    (quantize deliberately, or use Decimal throughout) is obvious.
    """
    with pytest.raises(UnitConversionError, match="exact multiple"):
        price_to_cents(0.1 + 0.2)

    # ...and the deliberate fix works.
    assert price_to_cents(round(Decimal(repr(0.1 + 0.2)), 2)) == 30


# ── units: fail ─────────────────────────────────────────────────────────────


def test_fail_price_finer_than_a_tick_is_rejected_not_rounded():
    """A sub-tick price is an error, never a silent round.

    Rounding here would move a trader's price without telling them. On a large
    clip that is real money, and it would be invisible in every log.
    """
    with pytest.raises(UnitConversionError, match="exact multiple"):
        price_to_cents(Decimal("50.005"))


def test_fail_quantity_finer_than_a_tick_is_rejected():
    with pytest.raises(UnitConversionError, match="exact multiple"):
        quantity_to_sub_mw(Decimal("1.00005"))


def test_fail_negative_quantity_names_the_real_fix():
    """Size is unsigned; direction is `side`. The message must say so."""
    with pytest.raises(UnitConversionError, match="side"):
        quantity_to_sub_mw(Decimal("-1"))


@pytest.mark.parametrize("bad", ["abc", "", "1.2.3"])
def test_fail_unparseable_string_is_rejected(bad):
    with pytest.raises(UnitConversionError):
        price_to_cents(bad)


def test_fail_bool_is_not_a_price():
    """`True` is an int subclass, so it would otherwise convert to 100 cents."""
    with pytest.raises(UnitConversionError, match="bool"):
        price_to_cents(True)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_fail_non_finite_is_rejected(bad):
    with pytest.raises(UnitConversionError):
        price_to_cents(bad)


def test_fail_wrong_type_is_rejected():
    with pytest.raises(UnitConversionError, match="expected"):
        price_to_cents(object())


# ── units: edge ─────────────────────────────────────────────────────────────


def test_edge_large_values_stay_exact():
    """No float path means no precision loss at size."""
    assert price_to_cents(Decimal("999999999.99")) == 99999999999
    assert quantity_to_sub_mw(Decimal("100000")) == 100_000_000


def test_edge_trailing_zeros_do_not_change_the_value():
    assert price_to_cents(Decimal("50.10")) == price_to_cents(Decimal("50.1"))


def test_edge_error_message_names_the_field():
    """The message has to say WHICH argument was wrong, not just that one was."""
    with pytest.raises(UnitConversionError, match="quantity_mw"):
        quantity_to_sub_mw(Decimal("0.00001"))


# ── submit_order construction: happy ────────────────────────────────────────


def test_happy_submit_sends_wire_units_unchanged():
    """What you pass is what goes on the wire. No conversion on this path.

    The three transports document cents / sub-MW, every response carries them
    (`OwnOrder.price`, `OwnOrder.quantity`), and cash and position limits use
    them too. Converting here would leave a caller submitting in one unit and
    reading back in another.
    """
    req = _submit(price_cents=5007, quantity_sub_mw=1500)
    assert req.price == 5007
    assert req.quantity == 1500
    assert req.client_order_id == _OID
    assert req.side == pb2.Side.BUY


def test_happy_submit_defaults_match_the_gateway():
    """Defaults must be what the gateway would have inferred from UNSPECIFIED.

    The gateway maps ORDER_TYPE_UNSPECIFIED -> Regular, EXE_UNSPECIFIED -> Non,
    VALIDITY_UNSPECIFIED -> Gfs. Sending those explicitly is identical in
    behaviour and honest on the wire; if the SDK ever picks a different default
    it becomes a silent behaviour change, so pin it.
    """
    req = _submit()
    assert req.order_type == pb2.OrderType.REGULAR
    assert req.exe_restriction == pb2.ExeRestriction.NON
    assert req.validity_res == pb2.ValidityRes.GFS


def test_happy_submit_by_product_and_delivery_start():
    req = _submit(
        contract_id=0, product="XBID_Hour_Power", delivery_start="2026-07-20T10:00:00Z"
    )
    assert req.product == "XBID_Hour_Power"
    assert req.contract_id == 0


# ── submit_order construction: fail ─────────────────────────────────────────


def test_fail_submit_requires_client_order_id():
    """Required by the SDK even though the wire allows "".

    It is the key that makes recovery from an ambiguous failure possible, so the
    SDK refuses to let a desk trade without one.
    """
    with pytest.raises(OrderValidationError, match="client_order_id"):
        _submit(client_order_id="")


def test_fail_submit_rejects_unspecified_side():
    with pytest.raises(OrderValidationError, match="side"):
        _submit(side=pb2.Side.SIDE_UNSPECIFIED)


def test_fail_submit_rejects_a_float_price():
    """A float in a cents field means the caller is thinking in CCY/MWh.

    Truncating `50.07` to 50 would be a 100x error dressed up as a rounding, so
    it is refused and the message names the conversion helpers.
    """
    with pytest.raises(OrderValidationError, match="wire units"):
        _submit(price_cents=50.07)


def test_fail_submit_rejects_a_bool_quantity():
    """`True` is an int subclass and would otherwise pass as 1 sub-MW."""
    with pytest.raises(OrderValidationError, match="wire units"):
        _submit(quantity_sub_mw=True)


def test_fail_submit_requires_a_contract_identity():
    with pytest.raises(OrderValidationError, match="contract_id"):
        _submit(contract_id=0)


def test_fail_submit_rejects_zero_quantity():
    with pytest.raises(OrderValidationError, match="greater than zero"):
        _submit(quantity_sub_mw=0)


def test_fail_submit_rejects_negative_quantity_and_names_side():
    """Size is unsigned; direction is `side`. The message must say so."""
    with pytest.raises(OrderValidationError, match="side"):
        _submit(quantity_sub_mw=-1000)


def test_fail_submit_rejects_missing_delivery_area():
    with pytest.raises(OrderValidationError, match="delivery_area_id"):
        _submit(delivery_area_id="")


# ── submit_order construction: edge ─────────────────────────────────────────


def test_edge_iceberg_display_must_be_below_total():
    """The gateway enforces this; catching it locally means nothing dispatches."""
    with pytest.raises(OrderValidationError, match="less than"):
        _submit(
            order_type=pb2.OrderType.ICEBERG,
            quantity_sub_mw=1000,
            display_qty_sub_mw=1000,
        )

    req = _submit(
        order_type=pb2.OrderType.ICEBERG, quantity_sub_mw=1000, display_qty_sub_mw=250
    )
    assert req.display_qty == 250


def test_edge_negative_price_is_accepted():
    """Negative power prices are ordinary, not an error."""
    assert _submit(price_cents=-1550).price == -1550


def test_edge_zero_price_is_accepted():
    """A zero price is legal and must not be confused with "absent"."""
    assert _submit(price_cents=0).price == 0


def test_edge_new_client_order_id_is_a_unique_uuid():
    a, b = new_client_order_id(), new_client_order_id()
    assert a != b
    uuid.UUID(a)  # raises if malformed


def test_edge_conversion_helpers_remain_available_for_display_code():
    """The decimal helpers are still exported, just not on the order path.

    UI and reporting code legitimately works in CCY/MWh; it converts explicitly
    at its own call site rather than the SDK guessing.
    """
    assert price_to_cents(Decimal("50.07")) == 5007
    assert cents_to_price(5007) == Decimal("50.07")
    assert _submit(price_cents=price_to_cents(Decimal("50.07"))).price == 5007


# ── modify_order: the restatement trap ──────────────────────────────────────


def test_happy_modify_wraps_plain_ints():
    """Plain ints must work; wrapping is the SDK's job.

    Previously this raised a bare TypeError unless the caller imported
    google.protobuf.wrappers_pb2 themselves, which made repricing a resting
    order fail on the obvious call.
    """
    req = build_modify_order_request(
        client_order_id=_OID, price_cents=5100, quantity_sub_mw=800
    )
    assert req.price == wrappers_pb2.Int64Value(value=5100)
    assert req.quantity == wrappers_pb2.UInt32Value(value=800)


def test_fail_modify_requires_both_price_and_quantity():
    """A MODIFY is a full restatement, so a half-specified one is rejected.

    Letting it through is how a partially-filled order gets restated at its
    original size, re-inflating an exposure the trader thinks is partly closed.
    """
    with pytest.raises(OrderValidationError, match="restates the whole order"):
        build_modify_order_request(client_order_id=_OID, price_cents=5100)


def test_edge_activate_and_deactivate_need_no_price_or_quantity():
    for action in (pb2.ModifyAction.ACTIVATE, pb2.ModifyAction.DEACTIVATE):
        req = build_modify_order_request(client_order_id=_OID, action=action)
        assert req.action == action
        assert not req.HasField("price")
        assert not req.HasField("quantity")


def test_edge_modify_omits_unset_wrapper_fields_entirely():
    """Absent must be distinguishable from zero, which is the whole point of
    the wrapper types."""
    req = build_modify_order_request(
        client_order_id=_OID, action=pb2.ModifyAction.ACTIVATE
    )
    assert not req.HasField("price")

    zero = build_modify_order_request(
        client_order_id=_OID, price_cents=0, quantity_sub_mw=1
    )
    assert zero.HasField("price")
    assert zero.price.value == 0


# ── patch_member: a real patch, unlike modify_order ─────────────────────────


def test_happy_patch_member_sends_only_what_was_given():
    req = build_patch_member_request(id="m-1", name="desk-a")
    assert req.HasField("name")
    assert not req.HasField("max_position")
    assert not req.HasField("active")


def test_edge_patch_member_zero_cash_limit_is_sent_not_dropped():
    """0 means "clear the override", so it must reach the wire as a set field."""
    req = build_patch_member_request(id="m-1", cash_limit_cents=0)
    assert req.HasField("cash_limit")
    assert req.cash_limit.value == 0


def test_fail_patch_member_requires_an_id():
    with pytest.raises(OrderValidationError, match="id is required"):
        build_patch_member_request(id="")


# ── cash and P&L scales: the two that are easiest to confuse ────────────────
#
# Three scales exist (x100 price, x1000 size, x100_000 P&L) and a misread is
# silent. These pin each one and, more importantly, pin that they are DIFFERENT.


def test_happy_eur_to_cents_for_cash_limits():
    assert eur_to_cents("50000") == 5_000_000       # a 50,000 EUR limit
    assert eur_to_cents(Decimal("0.01")) == 1
    assert cents_to_eur(5_000_000) == Decimal("50000")


def test_happy_q8_to_eur_for_pnl():
    assert q8_to_eur(1_234_500) == Decimal("12.345")
    assert eur_to_q8("12.345") == 1_234_500
    assert q8_to_eur(-500_000) == Decimal("-5")      # losses are negative


def test_fail_reading_pnl_as_cents_is_a_1000x_error():
    """The specific misread this helper exists to prevent.

    Both readings of 1_234_500 are plausible money amounts, which is exactly
    why nothing catches it at runtime. Pin the gap so anyone tempted to reuse
    cents_to_eur for P&L sees the magnitude in a test name.
    """
    q8_value = 1_234_500
    correct = q8_to_eur(q8_value)
    wrong = cents_to_eur(q8_value)

    assert correct == Decimal("12.345")
    assert wrong == Decimal("12345")
    assert wrong == correct * 1000


def test_edge_the_scales_are_distinct_constants():
    """Guard against a future "simplification" collapsing them.

    PRICE_SCALE and CASH_SCALE share a value today but feed different fields;
    merging them would make a later divergence corrupt both silently.
    """
    assert PRICE_SCALE == 100
    assert CASH_SCALE == 100
    assert QUANTITY_SCALE == 1000
    assert PNL_SCALE == 100_000
    assert PNL_SCALE != CASH_SCALE * QUANTITY_SCALE / 10  # not derivable; independent


def test_fail_cash_and_pnl_helpers_reject_sub_tick_values():
    with pytest.raises(UnitConversionError, match="exact multiple"):
        eur_to_cents("0.005")           # half a cent
    with pytest.raises(UnitConversionError, match="exact multiple"):
        eur_to_q8("0.000005")           # finer than q8 resolution


def test_edge_pnl_round_trips_exactly_at_scale():
    for q8 in (0, 1, -1, 1_234_500, -999_999_999):
        assert eur_to_q8(q8_to_eur(q8)) == q8


# ── inputs that would otherwise produce a wrong or undefined order ──────────
#
# Each of these is accepted by protobuf and plausible from correct-looking
# code, so without a local check it reaches the exchange.


def test_fail_modify_rejects_zero_quantity():
    """A zero restatement quantity means a 0.0 MW order, not "no change".

    Reachable from correct-looking code: the documented way to reprice a
    partially-filled order is to pass the REMAINING quantity, and remaining is
    exactly zero when the order fills completely between the snapshot a client
    read and the modify it builds from that snapshot.

    To withdraw an order you cancel it, and the error says so.
    """
    with pytest.raises(OrderValidationError, match="greater than zero"):
        build_modify_order_request(
            client_order_id=_OID, price_cents=5100, quantity_sub_mw=0
        )


def test_fail_modify_rejects_negative_quantity():
    with pytest.raises(OrderValidationError, match="greater than zero"):
        build_modify_order_request(
            client_order_id=_OID, price_cents=5100, quantity_sub_mw=-100
        )


def test_edge_modify_error_points_at_cancel_not_a_zero_restatement():
    """The message must name the correct action, not just refuse."""
    with pytest.raises(OrderValidationError, match="cancel_order"):
        build_modify_order_request(
            client_order_id=_OID, price_cents=5100, quantity_sub_mw=0
        )


def test_fail_modify_display_must_be_below_quantity():
    """Mirrors the submit path, so the round trip is saved and the message is clearer."""
    with pytest.raises(OrderValidationError, match="less than"):
        build_modify_order_request(
            client_order_id=_OID,
            price_cents=5100,
            quantity_sub_mw=1000,
            display_qty_sub_mw=5000,
        )


def test_fail_display_qty_on_a_non_iceberg_order_is_rejected():
    """display_qty on a REGULAR order silently changes the order's shape.

    It is an iceberg concept, and a caller who sets it on any other type has
    almost certainly forgotten `order_type=ICEBERG`. Left unchecked, a 50 MW
    REGULAR order carrying a 0.1 MW display quantity is a real order with an
    exposure nobody described.
    """
    with pytest.raises(OrderValidationError, match="ICEBERG"):
        _submit(
            order_type=pb2.OrderType.REGULAR,
            quantity_sub_mw=50_000,
            display_qty_sub_mw=100,
        )

    # ...but an explicit 0 is accepted, matching the gateway. gRPC's proto3
    # field cannot express "absent", so 0 means absent on the wire; rejecting
    # it here would make the SDK stricter than the contract it documents.
    assert _submit(
        order_type=pb2.OrderType.REGULAR, quantity_sub_mw=50_000, display_qty_sub_mw=0
    ).display_qty == 0


def test_fail_iceberg_without_a_display_quantity_is_rejected():
    """The inverse: ICEBERG requires a visible peak. The gateway rejects it too."""
    with pytest.raises(OrderValidationError, match="requires display_qty"):
        _submit(order_type=pb2.OrderType.ICEBERG, quantity_sub_mw=1000)


@pytest.mark.parametrize(
    "restriction", [pb2.ExeRestriction.FOK, pb2.ExeRestriction.IOC]
)
def test_fail_fok_ioc_require_validity_non(restriction):
    """FOK/IOC require VALIDITY_NON; any other combination the gateway rejects.

    Caught locally because it is a guaranteed round-trip rejection on the most
    latency-sensitive order types, and because the enum member is
    `VALIDITY_NON` rather than `NON` (which exists only on `ExeRestriction`),
    so the obvious guess raises AttributeError instead.
    """
    with pytest.raises(OrderValidationError, match="VALIDITY_NON"):
        _submit(exe_restriction=restriction)

    req = _submit(
        exe_restriction=restriction, validity_res=pb2.ValidityRes.VALIDITY_NON
    )
    assert req.exe_restriction == restriction


def test_fail_out_of_range_values_raise_a_typed_error_not_a_bare_ValueError():
    """protobuf raises on overflow rather than wrapping. Confirm, and name the field.

    The catastrophic case would be a u32 quantity of 2**32+1000 silently
    wrapping to 1000. It does not: protobuf raises. But its own error names
    neither the field nor the expected type, so it is re-raised as
    `OrderValidationError` naming both.
    """
    with pytest.raises(OrderValidationError, match=r"quantity: expected uint32"):
        _submit(quantity_sub_mw=2**32 + 1000)

    with pytest.raises(OrderValidationError, match=r"price: expected sint64"):
        _submit(price_cents=2**63)


def test_edge_maximum_in_range_values_are_accepted_exactly():
    """The boundary itself must still work, unrounded."""
    assert _submit(quantity_sub_mw=2**32 - 1).quantity == 2**32 - 1
    assert _submit(price_cents=2**63 - 1).price == 2**63 - 1
    assert _submit(price_cents=-(2**63)).price == -(2**63)


# ── outbound helpers: wire int -> Decimal ───────────────────────────────────
#
# The direction-confusion cases are the ones worth guarding. Unchecked,
# `cents_to_price(True)` yields Decimal('0.01') and
# `sub_mw_to_quantity(1500.7)` yields Decimal('1.500700000000000045474735089'),
# putting a boolean and binary float noise into a trader's display.


_OUTBOUND = [
    ("cents_to_price", cents_to_price),
    ("sub_mw_to_quantity", sub_mw_to_quantity),
    ("cents_to_eur", cents_to_eur),
    ("q8_to_eur", q8_to_eur),
]


@pytest.mark.parametrize("name,fn", _OUTBOUND, ids=[n for n, _ in _OUTBOUND])
def test_fail_outbound_helpers_reject_a_bool(name, fn):
    """bool is an int subclass, so True would render as one minor unit."""
    with pytest.raises(UnitConversionError, match="expected an int from the wire"):
        fn(True)


@pytest.mark.parametrize("name,fn", _OUTBOUND, ids=[n for n, _ in _OUTBOUND])
def test_fail_outbound_helpers_reject_a_float(name, fn):
    """A float here means the caller has the direction backwards."""
    with pytest.raises(UnitConversionError, match="expected an int from the wire"):
        fn(1500.7)


@pytest.mark.parametrize("name,fn", _OUTBOUND, ids=[n for n, _ in _OUTBOUND])
def test_fail_outbound_helpers_reject_a_string(name, fn):
    with pytest.raises(UnitConversionError):
        fn("500")


@pytest.mark.parametrize("name,fn", _OUTBOUND, ids=[n for n, _ in _OUTBOUND])
def test_happy_outbound_helpers_accept_wire_integers(name, fn):
    """Including the values that matter: zero and negative."""
    assert fn(0) == 0
    assert fn(-100) < 0
    assert isinstance(fn(12345), Decimal)


def test_edge_outbound_error_names_the_inbound_helpers():
    """The message must point at the fix, not just refuse."""
    with pytest.raises(UnitConversionError, match="price_to_cents"):
        cents_to_price(50.07)


def test_fail_wrong_python_type_names_the_field_and_the_expected_wire_type():
    """A wrong type must not leak protobuf's own message, which names nothing.

    `'str' object cannot be interpreted as an integer` and `bad argument type
    for built-in operation` are what protobuf raises; neither says which field,
    which value, or what was expected.
    """
    with pytest.raises(OrderValidationError, match=r"contract_id: expected int64"):
        _submit(contract_id="12345")

    with pytest.raises(
        OrderValidationError, match=r"delivery_area_id: expected string"
    ):
        _submit(delivery_area_id=99)


def test_fail_string_contract_id_names_the_specific_first_day_trap():
    """The most likely first-day mistake gets the fix spelled out.

    `Contract.contract_id` is a STRING on the wire while
    `SubmitOrderRequest.contract_id` is an int64, so the natural join between
    the two documented examples -- `contract_id=contract.contract_id` -- fails.
    The message must say to wrap it in int().
    """
    with pytest.raises(OrderValidationError, match=r"int\(\.\.\.\)"):
        _submit(contract_id="12345")


def test_fail_unknown_field_name_is_reported_as_such():
    """A typo'd kwarg on a **kwargs wrapper must name itself.

    protobuf raises `Protocol message X has no "quantiy" field`, which is
    serviceable, but it arrives as a bare ValueError from inside the library.
    """
    from voltnir_sdk._orders import _build_message
    from voltnir_sdk._generated import voltnir_api_v1_pb2 as _pb2

    with pytest.raises(OrderValidationError, match="no such field 'quantiy'"):
        _build_message(_pb2.SubmitOrderRequest, "submit_order", quantiy=1)
