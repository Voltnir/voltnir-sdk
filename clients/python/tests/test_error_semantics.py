"""Error classification and channel tuning: happy / fail / edge.

The question these answer is the one a trading desk actually asks when a call
fails: *is my order on the book or not?* Getting it wrong costs money in both
directions, so the classification is tested directly rather than inferred from
the status code table.
"""

from __future__ import annotations

import grpc
import pytest

from voltnir_sdk import (
    DeadlineExceeded,
    FailedPrecondition,
    InvalidArgument,
    OrderOutcomeUnknown,
    PermissionDenied,
    Unavailable,
    VoltnirClient,
    VoltnirError,
)
from voltnir_sdk.channel import (
    DEFAULT_CHANNEL_OPTIONS,
    DEFAULT_MAX_MESSAGE_LENGTH,
    build_options,
)
from voltnir_sdk.errors import UNCERTAIN_CODES, translate

_OID = "11111111-1111-4111-8111-111111111111"
_AREA = "10YBE----------2"


def _submit(client, **overrides):
    from voltnir_sdk import Side

    kwargs = dict(
        client_order_id=_OID,
        side=Side.BUY,
        delivery_area_id=_AREA,
        contract_id=12345,
        price_cents=5000,
        quantity_sub_mw=1000,
    )
    kwargs.update(overrides)
    return client.submit_order(**kwargs)


# ── the distinction that matters: rejected vs unknown ───────────────────────


@pytest.mark.parametrize(
    "code,exc",
    [
        (grpc.StatusCode.INVALID_ARGUMENT, InvalidArgument),
        (grpc.StatusCode.PERMISSION_DENIED, PermissionDenied),
        (grpc.StatusCode.FAILED_PRECONDITION, FailedPrecondition),
    ],
    ids=["INVALID_ARGUMENT", "PERMISSION_DENIED", "FAILED_PRECONDITION"],
)
def test_happy_definite_rejections_keep_their_own_type(client, fake, code, exc):
    """A validation rejection proves nothing reached the exchange.

    These must NOT become OrderOutcomeUnknown: turning a definite rejection into
    an ambiguous one would send a desk into an unnecessary reconciliation on
    every fat-fingered price, and reconciliation costs a round trip in a market
    where that matters.
    """
    fake.abort_code = code
    with pytest.raises(exc) as excinfo:
        _submit(client)

    assert excinfo.value.request_definitely_rejected is True
    assert not isinstance(excinfo.value, OrderOutcomeUnknown)


@pytest.mark.parametrize(
    "code",
    [
        grpc.StatusCode.DEADLINE_EXCEEDED,
        grpc.StatusCode.UNAVAILABLE,
        grpc.StatusCode.INTERNAL,
        grpc.StatusCode.CANCELLED,
    ],
    ids=lambda c: c.name,
)
def test_fail_ambiguous_codes_become_order_outcome_unknown(client, fake, code):
    """A transport or timing failure on an order path is UNKNOWN, not "failed".

    The gateway maps its own post-dispatch M7 acknowledgement timeout to
    DEADLINE_EXCEEDED and deliberately retains the order as pending, because it
    may well be resting. A client-side deadline looks identical on the wire, so
    both are reported as unknown rather than guessing the optimistic reading.
    """
    fake.abort_code = code
    with pytest.raises(OrderOutcomeUnknown) as excinfo:
        _submit(client)

    assert excinfo.value.request_definitely_rejected is False
    assert excinfo.value.client_order_id == _OID
    # The reconciliation instruction has to be in the message: the catch site is
    # where someone decides whether to resubmit.
    assert "get_order" in str(excinfo.value)


def test_edge_non_order_rpcs_keep_the_plain_timeout_type(client, fake):
    """Only order-mutating calls get the ambiguity treatment.

    A timed-out `list_contracts` has no position consequences, so dressing it up
    as OrderOutcomeUnknown would be noise that trains people to ignore the type.
    """
    fake.abort_code = grpc.StatusCode.DEADLINE_EXCEEDED
    with pytest.raises(DeadlineExceeded) as excinfo:
        client.list_contracts(area_id=_AREA)

    assert not isinstance(excinfo.value, OrderOutcomeUnknown)


@pytest.mark.parametrize(
    "method,kwargs",
    [
        ("cancel_order", {"client_order_id": _OID}),
        ("cancel_all_orders", {}),
    ],
)
def test_fail_cancels_are_also_ambiguous_on_timeout(client, fake, method, kwargs):
    """A timed-out cancel is the dangerous direction: the order may still be live.

    Assuming a cancel succeeded is how a desk carries an exposure it believes is
    flat.
    """
    fake.abort_code = grpc.StatusCode.DEADLINE_EXCEEDED
    with pytest.raises(OrderOutcomeUnknown):
        getattr(client, method)(**kwargs)


async def test_fail_async_order_path_classifies_identically(aclient, fake):
    """The async client must not have a different safety story."""
    fake.abort_code = grpc.StatusCode.DEADLINE_EXCEEDED
    from voltnir_sdk import Side

    with pytest.raises(OrderOutcomeUnknown):
        await aclient.submit_order(
            client_order_id=_OID,
            side=Side.BUY,
            delivery_area_id=_AREA,
            contract_id=1,
            price_cents=5000,
            quantity_sub_mw=1000,
        )


def test_edge_translate_without_a_client_order_id_still_classifies():
    """cancel_all_orders has no order id, but is still ambiguous on timeout."""
    err = translate(
        grpc.RpcError(), "CancelAllOrders", order_mutating=True, client_order_id=None
    )
    assert isinstance(err, OrderOutcomeUnknown)
    assert err.client_order_id is None


def test_edge_uncertain_codes_is_a_deliberate_closed_set():
    """Pin the set, so widening or narrowing it is a conscious edit.

    UNAVAILABLE is in it on purpose: it usually means the connection never
    established, and "usually" is not a basis for deciding whether to resubmit
    a live order.
    """
    assert UNCERTAIN_CODES == frozenset(
        {
            grpc.StatusCode.DEADLINE_EXCEEDED,
            grpc.StatusCode.UNAVAILABLE,
            grpc.StatusCode.INTERNAL,
            grpc.StatusCode.CANCELLED,
            grpc.StatusCode.UNKNOWN,
        }
    )


def test_edge_base_class_defaults_to_definitely_rejected():
    """The safe default for an unclassified error is "nothing happened"...

    ...only because every ambiguous code is explicitly enumerated above. If a
    new code needs to be treated as uncertain it goes in UNCERTAIN_CODES, not
    left to the default.
    """
    assert VoltnirError.request_definitely_rejected is True
    assert OrderOutcomeUnknown.request_definitely_rejected is False


# ── channel options ─────────────────────────────────────────────────────────


def test_happy_defaults_include_keepalive_and_a_raised_message_ceiling():
    """Both defaults exist to fix a real customer-facing failure.

    Without keepalive a quiet Watch* stream dies silently behind NAT and the
    desk goes blind. Without a raised receive limit, a large list_contracts
    fails at gRPC's 4 MB default with no server-side fix available.
    """
    opts = dict(DEFAULT_CHANNEL_OPTIONS)
    assert opts["grpc.keepalive_time_ms"] == 30_000
    assert opts["grpc.keepalive_permit_without_calls"] == 1
    assert opts["grpc.max_receive_message_length"] == DEFAULT_MAX_MESSAGE_LENGTH
    assert DEFAULT_MAX_MESSAGE_LENGTH > 4 * 1024 * 1024


def test_happy_caller_options_override_the_defaults():
    merged = dict(build_options([("grpc.max_receive_message_length", 123)]))
    assert merged["grpc.max_receive_message_length"] == 123
    assert merged["grpc.keepalive_time_ms"] == 30_000  # untouched


def test_edge_options_are_deduplicated_per_key():
    """One entry per key, so the effective config is readable and assertable."""
    merged = build_options([("grpc.keepalive_time_ms", 1), ("grpc.custom", 2)])
    keys = [k for k, _ in merged]
    assert len(keys) == len(set(keys))
    assert dict(merged)["grpc.keepalive_time_ms"] == 1


def test_edge_no_overrides_returns_the_defaults_unchanged():
    assert dict(build_options(None)) == dict(DEFAULT_CHANNEL_OPTIONS)


def test_happy_client_accepts_options_and_still_works(server, fake):
    """The passthrough must actually reach the channel and not break the client."""
    with VoltnirClient(
        host="127.0.0.1",
        port=server,
        api_key="test-key",
        timeout=5.0,
        options=[("grpc.max_receive_message_length", 8 * 1024 * 1024)],
    ) as c:
        assert c.get_me() is not None


# ── async order-safety parity ───────────────────────────────────────────────
#
# The async client must classify order failures exactly as the sync one does.
# If it did not, a desk on the async client would see Aborted or
# DeadlineExceeded on a timed-out cancel -- "your order is definitely gone" --
# for an order that may still be resting.


_ASYNC_ORDER_CALLS = [
    ("cancel_order", {"client_order_id": _OID}),
    ("cancel_all_orders", {}),
    (
        "modify_order",
        {"client_order_id": _OID, "price_cents": 5100, "quantity_sub_mw": 800},
    ),
]


@pytest.mark.parametrize(
    "method,kwargs", _ASYNC_ORDER_CALLS, ids=[m for m, _ in _ASYNC_ORDER_CALLS]
)
@pytest.mark.parametrize(
    "code",
    [
        grpc.StatusCode.DEADLINE_EXCEEDED,
        grpc.StatusCode.UNAVAILABLE,
        grpc.StatusCode.INTERNAL,
        grpc.StatusCode.CANCELLED,
    ],
    ids=lambda c: c.name,
)
async def test_fail_async_order_mutations_are_ambiguous(aclient, fake, method, kwargs, code):
    """Every async order-mutating RPC classifies exactly like its sync twin."""
    fake.abort_code = code
    with pytest.raises(OrderOutcomeUnknown) as excinfo:
        await getattr(aclient, method)(**kwargs)

    assert excinfo.value.request_definitely_rejected is False


@pytest.mark.parametrize(
    "method,kwargs", _ASYNC_ORDER_CALLS, ids=[m for m, _ in _ASYNC_ORDER_CALLS]
)
async def test_happy_async_order_rejections_stay_definite(aclient, fake, method, kwargs):
    """A validation rejection must NOT be dressed up as ambiguous on async either.

    Otherwise every fat-fingered async order costs an unnecessary
    reconciliation round trip.
    """
    fake.abort_code = grpc.StatusCode.INVALID_ARGUMENT
    with pytest.raises(InvalidArgument) as excinfo:
        await getattr(aclient, method)(**kwargs)

    assert excinfo.value.request_definitely_rejected is True
    assert not isinstance(excinfo.value, OrderOutcomeUnknown)


async def test_edge_async_order_outcome_carries_the_client_order_id(aclient, fake):
    """The reconciliation key must survive to the async catch site too."""
    fake.abort_code = grpc.StatusCode.DEADLINE_EXCEEDED
    with pytest.raises(OrderOutcomeUnknown) as excinfo:
        await aclient.cancel_order(client_order_id=_OID)

    assert excinfo.value.client_order_id == _OID
    assert "get_order" in str(excinfo.value)


async def test_edge_async_non_order_rpc_keeps_its_plain_type(aclient, fake):
    fake.abort_code = grpc.StatusCode.DEADLINE_EXCEEDED
    with pytest.raises(DeadlineExceeded) as excinfo:
        await aclient.list_contracts(area_id=_AREA)
    assert not isinstance(excinfo.value, OrderOutcomeUnknown)
