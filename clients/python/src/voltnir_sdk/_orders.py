"""Request builders for the order path, shared by the sync and async clients.

These live here rather than on either client so the two cannot drift. An order
builder that behaved differently depending on whether the caller happened to be
using asyncio would be a genuinely nasty bug to track down.

Everything here is pure: it builds and validates a protobuf message and never
touches a channel. So the validation is testable without a server, and it fails
before anything is dispatched, which means a rejection here is always
"definitely not submitted".

## Units

Wire units, matching the REST / gRPC / WebSocket docs exactly:

    price_cents        i64   Cents (CCY/MWh x 100). 5000 = 50.00 CCY/MWh.
    quantity_sub_mw    u32   Sub-MW (MW x 1000). 1000 = 1.0 MW. Must be > 0.

The SDK does NOT convert to or from decimal EUR/MWh on this path. Integer minor
units are what the three transports document, what every response carries
(`OwnOrder.price`, `OwnOrder.quantity`), and what cash and position limits are
expressed in, so an algo keeping its book in minor units talks to Voltnir in
exactly the units it already holds. Introducing decimals here would add a
rounding surface where the system deliberately has none, and would leave a
caller submitting in one unit and reading back in another.

What the parameter names DO carry is the unit itself. The hazard being fixed is
that a bare `price=50` reads as "50 EUR/MWh" and is silently accepted as 0.50;
`price_cents=50` cannot be misread. `voltnir_sdk.price_to_cents` and friends
remain available for display and UI code that genuinely works in decimals.
"""

from __future__ import annotations

import uuid

from google.protobuf import wrappers_pb2

from ._generated import voltnir_api_v1_pb2 as pb2
from .errors import OrderValidationError

__all__ = [
    "new_client_order_id",
    "build_submit_order_request",
    "build_submit_basket_request",
    "build_modify_order_request",
    "build_patch_member_request",
    "build_set_cash_limit_request",
]


def new_client_order_id() -> str:
    """Generate a fresh `client_order_id` for `submit_order` (a UUID4 string).

    How long the gateway refuses a reused key, and what frees one, is
    documented once, on `VoltnirClient.submit_order`.
    """
    return str(uuid.uuid4())


def _require_int(value, *, field: str, allow_none: bool = False) -> int | None:
    """Reject anything that is not a plain wire integer.

    `bool` is excluded explicitly because it is an `int` subclass, so `True`
    would otherwise sail through as 1. A `float` is rejected rather than
    truncated: a float reaching a cents field almost always means the caller is
    thinking in EUR/MWh, and silently taking `int(50.07)` would be a 100x error
    dressed up as a rounding.
    """
    if value is None:
        if allow_none:
            return None
        raise OrderValidationError(f"{field} is required")
    if isinstance(value, bool) or not isinstance(value, int):
        raise OrderValidationError(
            f"{field}: expected an int in wire units, got "
            f"{type(value).__name__} {value!r}. Prices are cents "
            f"(5000 = 50.00 CCY/MWh) and sizes are sub-MW (1000 = 1.0 MW); "
            f"use voltnir_sdk.price_to_cents / quantity_to_sub_mw if you are "
            f"holding decimals."
        )
    return value


# protobuf's own type errors name nothing useful. Setting a str where an int64
# is expected raises "'str' object cannot be interpreted as an integer"; a wrong
# type on some fields raises "bad argument type for built-in operation", which
# names neither the field nor the value. Both leak straight through a wrapper
# that is meticulous everywhere else, and the str-into-`contract_id` case is the
# single most likely first-day mistake: `Contract.contract_id` is a STRING on
# the wire while `SubmitOrderRequest.contract_id` is an int64, so the natural
# `contract_id=contract.contract_id` fails with no clue as to why.
#
# So fields are set ONE AT A TIME. The extra work buys the field name, the
# expected wire type, the offending value, and for the known traps, the fix.
_PROTO_TYPE_NAMES = {
    1: "double", 2: "float", 3: "int64", 4: "uint64", 5: "int32",
    6: "fixed64", 7: "fixed32", 8: "bool", 9: "string", 12: "bytes",
    13: "uint32", 15: "sfixed32", 16: "sfixed64", 17: "sint32", 18: "sint64",
}

# Fields where the wrong type has a specific, known cause worth naming.
_FIELD_HINTS = {
    "contract_id": (
        "Contract.contract_id is a STRING on the wire while this field is an "
        "int64, so contract_id=contract.contract_id needs int(...) around it."
    ),
}


def _set_field(msg, name: str, value, *, context: str) -> None:
    field = msg.DESCRIPTOR.fields_by_name.get(name)
    if field is None:
        raise OrderValidationError(
            f"{context}: no such field {name!r} on "
            f"{msg.DESCRIPTOR.name}. Check the spelling against the API docs."
        )

    try:
        if field.is_repeated:
            del msg.__getattribute__(name)[:]
            msg.__getattribute__(name).extend(value)
        elif field.type == field.TYPE_MESSAGE:
            msg.__getattribute__(name).CopyFrom(value)
        else:
            setattr(msg, name, value)
    except (TypeError, ValueError) as exc:
        expected = _PROTO_TYPE_NAMES.get(field.type, "the declared type")
        hint = _FIELD_HINTS.get(name, "")
        raise OrderValidationError(
            f"{context}.{name}: expected {expected}, got "
            f"{type(value).__name__} {value!r} ({exc})."
            + (f" {hint}" if hint else "")
        ) from exc


def _build_message(cls, context: str, **kwargs):
    """Construct a protobuf message, naming the field on any type/range error.

    Range errors are worth keeping distinct from wrapping: protobuf RAISES on
    an out-of-range int rather than silently wrapping it, so a u32 quantity of
    2**32+1000 does not become 1000. That behaviour is correct; only the
    message was unhelpful.
    """
    msg = cls()
    for name, value in kwargs.items():
        if value is None:
            continue
        _set_field(msg, name, value, context=context)
    return msg


def build_submit_order_request(
    *,
    client_order_id: str,
    side: pb2.Side.ValueType,
    delivery_area_id: str,
    price_cents: int,
    quantity_sub_mw: int,
    contract_id: int = 0,
    product: str = "",
    delivery_start: str = "",
    delivery_end: str = "",
    order_type: pb2.OrderType.ValueType = pb2.OrderType.REGULAR,
    exe_restriction: pb2.ExeRestriction.ValueType = pb2.ExeRestriction.NON,
    validity_res: pb2.ValidityRes.ValueType = pb2.ValidityRes.GFS,
    entry_state: str = "",
    display_qty_sub_mw: int | None = None,
    validity_date: str = "",
    pre_arranged_acct: str = "",
    v_member_short_id: str = "",
    ack_only: bool = False,
) -> pb2.SubmitOrderRequest:
    """Build and validate a `SubmitOrderRequest`. See `VoltnirClient.submit_order`."""
    if not client_order_id:
        raise OrderValidationError(
            "client_order_id is required. It is the idempotency key you need to "
            "reconcile after an ambiguous failure; use "
            "voltnir_sdk.new_client_order_id()."
        )
    if side not in (pb2.Side.BUY, pb2.Side.SELL):
        raise OrderValidationError(
            f"side must be Side.BUY or Side.SELL, got {side!r}. "
            f"SIDE_UNSPECIFIED is rejected by the gateway."
        )
    if not delivery_area_id:
        raise OrderValidationError("delivery_area_id is required (EIC area code)")
    # The exchange schema fixes the area at 16 characters (the EIC code) and
    # answers any other length with an error that names no order, so the
    # gateway refuses it; checking here names the field before the round trip.
    # A wrong Python type falls through to the field-typed error below.
    if isinstance(delivery_area_id, str) and len(delivery_area_id) != 16:
        raise OrderValidationError(
            f"delivery_area_id must be a 16-character EIC code, got "
            f"{len(delivery_area_id)} characters"
        )

    _check_block(order_type, exe_restriction, contract_id, product, delivery_start, delivery_end)

    # The contract can be named directly or by (product, delivery_start). The
    # gateway enforces this too; checking here turns a round-trip
    # INVALID_ARGUMENT into an immediate, local error naming both paths.
    if not contract_id and not (product and delivery_start):
        raise OrderValidationError(
            "identify the contract with either contract_id, or both product and "
            "delivery_start"
        )

    price = _require_int(price_cents, field="price_cents")
    quantity = _require_int(quantity_sub_mw, field="quantity_sub_mw")
    display = _require_int(
        display_qty_sub_mw, field="display_qty_sub_mw", allow_none=True
    )

    if quantity <= 0:
        raise OrderValidationError(
            f"quantity_sub_mw must be greater than zero, got {quantity}. "
            f"Direction is the `side` argument (BUY / SELL), not the sign."
        )

    # display_qty belongs to ICEBERG orders and ONLY to them. Checked locally so
    # the error names the likely fix (a forgotten order_type=ICEBERG) at the
    # call site rather than arriving as a round-trip INVALID_ARGUMENT. The
    # gateway enforces the same rule in its shared validator.
    # `display > 0`, matching the gateway: gRPC's proto3 field cannot express
    # "absent", so 0 means absent there, and the shared server-side validator
    # treats Some(0) as absent for the same reason. Rejecting 0 here would make
    # the SDK stricter than the wire contract it documents.
    is_iceberg = order_type == pb2.OrderType.ICEBERG
    if display is not None and display > 0 and not is_iceberg:
        raise OrderValidationError(
            f"display_qty_sub_mw is only meaningful on an ICEBERG order, but "
            f"order_type is {pb2.OrderType.Name(order_type)}. Pass "
            f"order_type=OrderType.ICEBERG, or drop display_qty_sub_mw."
        )
    if is_iceberg and not display:
        raise OrderValidationError(
            "an ICEBERG order requires display_qty_sub_mw (the visible peak)"
        )
    if display is not None and display >= quantity:
        raise OrderValidationError(
            f"display_qty_sub_mw ({display}) must be less than quantity_sub_mw "
            f"({quantity}) for an iceberg order"
        )

    # FOK / IOC are only accepted alongside VALIDITY_NON. Checking locally
    # turns a guaranteed round-trip rejection into an immediate error that
    # names the fix: the enum member is VALIDITY_NON, not NON (which exists
    # only on ExeRestriction), so the obvious guess raises AttributeError.
    if exe_restriction in (pb2.ExeRestriction.FOK, pb2.ExeRestriction.IOC):
        if validity_res != pb2.ValidityRes.VALIDITY_NON:
            raise OrderValidationError(
                f"exe_restriction="
                f"{pb2.ExeRestriction.Name(exe_restriction)} requires "
                f"validity_res=ValidityRes.VALIDITY_NON, got "
                f"{pb2.ValidityRes.Name(validity_res)}. The gateway rejects "
                f"any other combination."
            )

    return _build_message(
        pb2.SubmitOrderRequest,
        "submit_order",
        client_order_id=client_order_id,
        side=side,
        price=price,
        quantity=quantity,
        delivery_area_id=delivery_area_id,
        contract_id=contract_id,
        order_type=order_type,
        exe_restriction=exe_restriction,
        validity_res=validity_res,
        entry_state=entry_state,
        display_qty=display or 0,
        validity_date=validity_date,
        pre_arranged_acct=pre_arranged_acct,
        v_member_short_id=v_member_short_id,
        product=product,
        delivery_start=delivery_start,
        delivery_end=delivery_end,
        ack_only=ack_only,
    )


#: The list instructions a basket takes, as the gateway names them.
LIST_EXEC_INSTS = ("none", "valid", "linked")

#: The most orders one basket carries; the exchange refuses more.
MAX_BASKET_ORDERS = 100


def build_submit_basket_request(
    *,
    list_exec_inst: str,
    orders,
    basket_ref: str = "",
) -> pb2.SubmitBasketRequest:
    """Build and validate a `SubmitBasketRequest`. See `VoltnirClient.submit_basket`.

    Each order is a mapping of `submit_order` keyword arguments, checked by
    the same local rules; a refusal names the order's index first.
    """
    if list_exec_inst not in LIST_EXEC_INSTS:
        raise OrderValidationError(
            f"list_exec_inst must be one of {', '.join(LIST_EXEC_INSTS)}, got {list_exec_inst!r}"
        )
    orders = list(orders)
    if not orders:
        raise OrderValidationError("a basket carries at least one order")
    if len(orders) > MAX_BASKET_ORDERS:
        raise OrderValidationError(
            f"a basket carries at most {MAX_BASKET_ORDERS} orders; this one carries {len(orders)}"
        )
    built = []
    for i, order in enumerate(orders):
        if order.get("delivery_end"):
            raise OrderValidationError(
                f"[{i}] a basket cannot create a user-defined block; join an existing "
                f"block by its contract_id"
            )
        try:
            built.append(build_submit_order_request(**order))
        except OrderValidationError as e:
            raise OrderValidationError(f"[{i}] {e}") from e
    _check_basket_orders(list_exec_inst, built)
    return pb2.SubmitBasketRequest(
        basket_ref=basket_ref, list_exec_inst=list_exec_inst, orders=built
    )


def _check_basket_orders(list_exec_inst: str, built) -> None:
    """One client order id per order, and fill-or-kill on every order of a
    linked basket: the gateway refuses both, so the error names the order
    before the round trip."""
    seen: dict[str, int] = {}
    for i, req in enumerate(built):
        if req.client_order_id in seen:
            raise OrderValidationError(
                f"[{i}] client_order_id {req.client_order_id} repeats [{seen[req.client_order_id]}]"
            )
        seen[req.client_order_id] = i
    if list_exec_inst == "linked":
        not_fok = [i for i, r in enumerate(built) if r.exe_restriction != pb2.ExeRestriction.FOK]
        if not_fok:
            listed = ", ".join(f"[{i}]" for i in not_fok)
            raise OrderValidationError(
                f"every order in a linked basket must be ExeRestriction.FOK; {listed} is not"
            )


def _check_block(order_type, exe_restriction, contract_id, product, delivery_start, delivery_end):
    """The block-order rules the gateway refuses at its edge, checked first.

    `delivery_end` creates a user-defined block over
    `[delivery_start, delivery_end)`, so it needs a BLOCK order naming its
    `product` and `delivery_start` and no `contract_id`; a block order, created
    or joined, takes AON or FOK. NON is refused by the exchange on a block, and
    IOC makes a block a market sweep, which the gateway does not send. The
    window itself (consecutive contracts, the product's maximum) is checked by
    the gateway against its catalogue. The restriction is checked before
    `delivery_end`, as the gateway checks them. Here both run before the
    contract, size and validity checks; the gateway runs its field checks (the FOK/IOC
    validity rule among them) first. So a request that breaks a block rule and
    another rule can be named by a different rule on each side: a BLOCK with
    IOC and GFS raises BLOCK_SWEEP_UNSUPPORTED here, and the gateway refuses
    it for its validity.
    """
    is_block = order_type == pb2.OrderType.BLOCK
    if is_block and exe_restriction == pb2.ExeRestriction.NON:
        raise OrderValidationError(
            "BLOCK_RESTRICTION_NON: a block order takes exe_restriction "
            "ExeRestriction.AON or ExeRestriction.FOK, not NON"
        )
    if is_block and exe_restriction == pb2.ExeRestriction.IOC:
        raise OrderValidationError(
            "BLOCK_SWEEP_UNSUPPORTED: a block order with ExeRestriction.IOC is a "
            "market sweep, which is not supported; use AON or FOK"
        )
    if delivery_end and not (is_block and product and delivery_start and not contract_id):
        raise OrderValidationError(
            "BLOCK_DELIVERY_END_INVALID: delivery_end creates a block, so it needs "
            "order_type=OrderType.BLOCK with product and delivery_start, and no "
            "contract_id"
        )


def build_modify_order_request(
    *,
    client_order_id: str,
    action: pb2.ModifyAction.ValueType = pb2.ModifyAction.MODIFY,
    price_cents: int | None = None,
    quantity_sub_mw: int | None = None,
    display_qty_sub_mw: int | None = None,
    validity_res: pb2.ValidityRes.ValueType | None = None,
    validity_date: str = "",
    v_member_short_id: str = "",
    ack_only: bool = False,
) -> pb2.ModifyOrderRequest:
    """Build and validate a `ModifyOrderRequest`. See `VoltnirClient.modify_order`."""
    if not client_order_id:
        raise OrderValidationError("client_order_id is required")

    price = _require_int(price_cents, field="price_cents", allow_none=True)
    quantity = _require_int(
        quantity_sub_mw, field="quantity_sub_mw", allow_none=True
    )
    display = _require_int(
        display_qty_sub_mw, field="display_qty_sub_mw", allow_none=True
    )

    if action == pb2.ModifyAction.MODIFY:
        _check_restatement(price, quantity, display)

    req = _build_message(
        pb2.ModifyOrderRequest,
        "modify_order",
        client_order_id=client_order_id,
        action=action,
        display_qty=display or 0,
        validity_date=validity_date,
        v_member_short_id=v_member_short_id,
        ack_only=ack_only,
    )
    # Int64Value / UInt32Value on the wire, because for these two fields a zero
    # is meaningful and "absent" has to be distinguishable from it. Callers pass
    # plain ints; wrapping is the SDK's job, so repricing an order, the most
    # latency-sensitive call there is, needs no import of
    # google.protobuf.wrappers_pb2.
    if price is not None:
        req.price.CopyFrom(_wrapped(wrappers_pb2.Int64Value, price, "price_cents"))
    if quantity is not None:
        req.quantity.CopyFrom(_wrapped(wrappers_pb2.UInt32Value, quantity, "quantity_sub_mw"))
    if validity_res is not None:
        req.validity_res = validity_res
    return req


def _check_restatement(price, quantity, display) -> None:
    """The rules a MODIFY's restated price and size answer to, checked first.

    The gateway checks these on a MODIFY only. An ACTIVATE or DEACTIVATE puts
    the order back on or takes it off the book at the price and size it rests
    at: the gateway ignores any price, quantity or display size the request
    carries, so there the SDK holds them only to being ints that fit their
    wire fields.
    """
    # A MODIFY is a full restatement, not a patch: the gateway requires both
    # price and quantity and applies exactly what it is given. Catching this
    # locally matters more than the round trip saved, because the failure mode
    # of getting it wrong is silently restating a partially-filled order at its
    # ORIGINAL size, which re-inflates an exposure the trader believes is
    # partly closed.
    if price is None or quantity is None:
        raise OrderValidationError(
            "a MODIFY restates the whole order, so both price_cents and "
            "quantity_sub_mw are required. This is not a patch: whatever you "
            "pass becomes the resting order. To reprice a partially-filled "
            "order, pass the REMAINING quantity, not the original."
        )
    # A zero restatement is a 0.0 MW order, and the gateway refuses it. It is
    # refused here first, with the remedy, because correct-looking code reaches
    # it: callers pass the REMAINING quantity, and remaining is exactly zero
    # the moment an order fills completely between a snapshot and the modify
    # built from it. To withdraw an order, cancel it.
    if quantity <= 0:
        raise OrderValidationError(
            f"quantity_sub_mw must be greater than zero on a MODIFY, got "
            f"{quantity}. A fully-filled order has nothing left to restate: "
            f"use cancel_order() to withdraw, rather than restating at zero."
        )
    # The gateway refuses a display size at or above the restated quantity.
    if display is not None and display >= quantity:
        raise OrderValidationError(
            f"display_qty_sub_mw ({display}) must be less than quantity_sub_mw "
            f"({quantity})"
        )


def _wrapped(cls, value: int, field: str):
    """`cls(value=value)` for a wrapper type, naming the field when the value
    does not fit: protobuf raises on an out-of-range int rather than wrapping
    it, with a message that names neither the field nor the message."""
    try:
        return cls(value=value)
    except (TypeError, ValueError) as exc:
        raise OrderValidationError(
            f"modify_order.{field}: {value!r} does not fit the wire field ({exc})"
        ) from exc


def build_patch_member_request(
    *,
    id: str,
    name: str | None = None,
    max_position: int | None = None,
    active: bool | None = None,
    cash_limit_cents: int | None = None,
    cash_limit_gbp_cents: int | None = None,
    max_slot_position: int | None = None,
    clear_max_slot_position: bool = False,
    delivery_areas: pb2.DeliveryAreaScope | None = None,
) -> pb2.PatchMemberRequest:
    """Build a `PatchMemberRequest`. Only supplied fields are sent, and applied.

    Unlike `modify_order`, this genuinely is a patch: the wrapper types mean an
    omitted field is left untouched server-side, and passing 0 for a cash limit
    takes the member's allocation out of the desk's limit away entirely.
    `max_slot_position` sets the member slot limit (sub-MW, 0 = flat-only);
    `clear_max_slot_position=True` removes it. The two together are refused
    locally, because the gateway refuses them too. `delivery_areas` replaces
    the member's delivery areas whole; `None` leaves them.
    """
    if not id:
        raise OrderValidationError(
            "id is required (the member UUID Member.id, not the VM-style short_id)"
        )
    if max_slot_position is not None and clear_max_slot_position:
        raise OrderValidationError(
            "max_slot_position and clear_max_slot_position are exclusive: "
            "pass a value to set the member slot limit, or clear it"
        )

    req = _build_message(pb2.PatchMemberRequest, "patch_member", id=id)
    if name is not None:
        req.name.CopyFrom(wrappers_pb2.StringValue(value=name))
    if max_position is not None:
        req.max_position.CopyFrom(wrappers_pb2.Int64Value(value=max_position))
    if active is not None:
        req.active.CopyFrom(wrappers_pb2.BoolValue(value=active))
    if cash_limit_cents is not None:
        req.cash_limit.CopyFrom(wrappers_pb2.Int64Value(value=cash_limit_cents))
    if cash_limit_gbp_cents is not None:
        req.cash_limit_gbp.CopyFrom(
            wrappers_pb2.Int64Value(value=cash_limit_gbp_cents)
        )
    if max_slot_position is not None:
        req.max_slot_position = max_slot_position
    req.clear_max_slot_position = clear_max_slot_position
    if delivery_areas is not None:
        req.delivery_areas.CopyFrom(delivery_areas)
    return req


_SELF_TRADE_POLICIES = ("observe", "reject")


def build_set_self_trade_policy_request(*, policy: str) -> pb2.SetSelfTradePolicyRequest:
    """Build a `SetSelfTradePolicyRequest` from a policy name.

    `policy` is "observe" or "reject", in any case; anything else raises
    `OrderValidationError` locally, before anything is sent. "unspecified"
    names the enum's zero value, which the gateway refuses rather than reading
    as a default, so it is refused here with the same words as any other
    unknown name.
    """
    name = policy.lower() if isinstance(policy, str) else ""
    if name not in _SELF_TRADE_POLICIES:
        raise OrderValidationError(f"policy must be 'observe' or 'reject', got {policy!r}")
    value = pb2.SelfTradePolicy.Value("SELF_TRADE_POLICY_" + name.upper())
    return pb2.SetSelfTradePolicyRequest(policy=value)


_SLOT_MODES = ("off", "observe", "reject")


def build_set_slot_limit_request(*, mode: str, house_limit: int) -> pb2.SetSlotLimitRequest:
    """Build a `SetSlotLimitRequest` from a mode name and a sub-MW limit.

    `mode` is "off", "observe" or "reject", in any case; anything else raises
    `OrderValidationError` locally, before anything is sent. The mode and the
    limit are always sent: the gateway refuses a set that leaves either unset.
    """
    name = mode.lower() if isinstance(mode, str) else ""
    if name not in _SLOT_MODES:
        raise OrderValidationError(
            f"mode must be 'off', 'observe' or 'reject', got {mode!r}"
        )
    value = pb2.SlotLimitMode.Value("SLOT_LIMIT_MODE_" + name.upper())
    return _build_message(
        pb2.SetSlotLimitRequest, "set_slot_limit", mode=value, house_limit=house_limit
    )


def slot_limit_mode_name(mode: int) -> str:
    """The name of a slot limit mode as the gateway sends it: "off",
    "observe" or "reject". UNSPECIFIED (0) reads as "off", the default."""
    names = {
        pb2.SlotLimitMode.SLOT_LIMIT_MODE_OBSERVE: "observe",
        pb2.SlotLimitMode.SLOT_LIMIT_MODE_REJECT: "reject",
    }
    return names.get(mode, "off")


def build_set_cash_limit_request(
    *,
    cap_cents: int | None = None,
    currency: str = "eur",
) -> pb2.SetCashLimitRequest:
    """Build a `SetCashLimitRequest` for the Voltnir cap on one cash pool.

    `cap_cents=None` leaves the wrapper unset, which the gateway reads as
    "remove the cap" — the exchange's own limit then binds alone. That is a
    different instruction from `cap_cents=0`, a deliberate cap of zero, which
    stops all trading in the pool. The wrapper type is what keeps the two
    distinguishable on the wire.
    """
    req = pb2.SetCashLimitRequest(currency=currency)
    if cap_cents is not None:
        req.cap_cents.CopyFrom(wrappers_pb2.Int64Value(value=cap_cents))
    return req
