"""`request_definitely_rejected` on an incomplete member-scoped cancel-all.

A member-scoped `cancel_all_orders` sends one cancel per order. When the
exchange acknowledges only some of them, the gateway fails the call with the
status of the failure that stopped it and appends the counts to the detail.
Cancels before that failure took effect, so no such error may claim the request
was definitely rejected, whatever its type. Every other error keeps its type's
value: a flag that turned False on a loose match would push a desk into a
needless reconciliation, and one that stayed True would tell it nothing was
cancelled when some of its book was.
"""

from __future__ import annotations

import grpc
import pytest

from voltnir_sdk import (
    Aborted,
    FailedPrecondition,
    InvalidArgument,
    NotFound,
    OrderOutcomeUnknown,
    RequestNotProcessed,
    VoltnirError,
)
from voltnir_sdk.errors import (
    CANCEL_ALL_INCOMPLETE_PREFIX,
    NOT_PROCESSED_PREFIX,
    translate,
)

_OID = "11111111-1111-4111-8111-111111111111"

_TAIL = (
    "(cancel-all incomplete: the exchange acknowledged the cancel for "
    "2 of 3 targeted orders; 1 may still be resting)"
)

# (status code, the cause the gateway reports under it, the SDK type) for every
# status an incomplete cancel-all can carry that is definite without the counts.
_DEFINITE_CAUSES = [
    (
        grpc.StatusCode.ABORTED,
        "exchange rejected the request: Order 1 not found.",
        Aborted,
    ),
    (
        grpc.StatusCode.FAILED_PRECONDITION,
        "product scale unsupported for contract 42",
        FailedPrecondition,
    ),
    (grpc.StatusCode.NOT_FOUND, "order 7 not found", NotFound),
    (grpc.StatusCode.INVALID_ARGUMENT, "bad request", InvalidArgument),
    (
        grpc.StatusCode.UNAVAILABLE,
        f"{NOT_PROCESSED_PREFIX} the request was returned undelivered by the "
        "exchange and was not processed; resubmit it with the same "
        "client_order_id (no route)",
        RequestNotProcessed,
    ),
]

_IDS = [cls.__name__ for _, _, cls in _DEFINITE_CAUSES]


def test_edge_prefix_is_the_start_of_the_example_clause():
    """The prefix is a literal of the documented clause, parenthesis included."""
    assert _TAIL.startswith(CANCEL_ALL_INCOMPLETE_PREFIX)
    assert CANCEL_ALL_INCOMPLETE_PREFIX.startswith("(cancel-all incomplete: ")


# ── happy: the incomplete clause clears the flag on every type ──────────────


@pytest.mark.parametrize("code,cause,cls", _DEFINITE_CAUSES, ids=_IDS)
def test_happy_incomplete_cancel_all_is_not_definitely_rejected(
    client, fake, code, cause, cls
):
    fake.abort_code = code
    fake.abort_details = f"{cause} {_TAIL}"
    with pytest.raises(cls) as excinfo:
        client.cancel_all_orders()

    assert type(excinfo.value) is cls
    assert excinfo.value.request_definitely_rejected is False
    assert excinfo.value.message.endswith(_TAIL)


@pytest.mark.parametrize("code,cause,cls", _DEFINITE_CAUSES, ids=_IDS)
async def test_happy_async_incomplete_cancel_all_is_not_definitely_rejected(
    aclient, fake, code, cause, cls
):
    fake.abort_code = code
    fake.abort_details = f"{cause} {_TAIL}"
    with pytest.raises(cls) as excinfo:
        await aclient.cancel_all_orders()

    assert type(excinfo.value) is cls
    assert excinfo.value.request_definitely_rejected is False


@pytest.mark.parametrize(
    "code", [grpc.StatusCode.DEADLINE_EXCEEDED, grpc.StatusCode.INTERNAL]
)
def test_happy_incomplete_cancel_all_on_an_uncertain_code_stays_unknown(
    client, fake, code
):
    """An uncertain status keeps its type and stays False with the clause."""
    fake.abort_code = code
    fake.abort_details = f"exchange did not respond in time {_TAIL}"
    with pytest.raises(OrderOutcomeUnknown) as excinfo:
        client.cancel_all_orders()

    assert excinfo.value.request_definitely_rejected is False


# ── fail: without the clause every type keeps its value ────────────────────


@pytest.mark.parametrize("code,cause,cls", _DEFINITE_CAUSES, ids=_IDS)
def test_fail_cancel_all_without_the_clause_keeps_its_type_value(
    client, fake, code, cause, cls
):
    """The account-wide cancel-all is one command with no partial outcome, so
    its errors carry no counts and remain definite."""
    fake.abort_code = code
    fake.abort_details = cause
    with pytest.raises(cls) as excinfo:
        client.cancel_all_orders()

    assert excinfo.value.request_definitely_rejected is True


@pytest.mark.parametrize("code,cause,cls", _DEFINITE_CAUSES, ids=_IDS)
async def test_fail_async_cancel_all_without_the_clause_keeps_its_type_value(
    aclient, fake, code, cause, cls
):
    fake.abort_code = code
    fake.abort_details = cause
    with pytest.raises(cls) as excinfo:
        await aclient.cancel_all_orders()

    assert excinfo.value.request_definitely_rejected is True


def test_fail_clause_on_another_rpc_does_not_clear_the_flag(client, fake):
    """Only a cancel-all has a partial outcome; a single cancel refused by the
    exchange did not take effect, whatever its detail says."""
    fake.abort_code = grpc.StatusCode.ABORTED
    fake.abort_details = f"exchange rejected the request: x {_TAIL}"
    with pytest.raises(Aborted) as excinfo:
        client.cancel_order(client_order_id=_OID)

    assert excinfo.value.request_definitely_rejected is True


# ── edge: similar words are not the clause ─────────────────────────────────


@pytest.mark.parametrize(
    "detail",
    [
        # The words without the gateway's parenthesised clause.
        "exchange rejected the request: cancel-all incomplete: try again",
        # The words inside a cause, with the clause's text but no opening paren.
        "exchange rejected the request: cancel-all incomplete: the exchange "
        "acknowledged the cancel for 2 of 3 targeted orders",
        # The clause quoted mid-message rather than closing it.
        f"exchange rejected the request: {_TAIL} for order 9",
        # The clause quoted mid-message, followed by another parenthesis.
        f"exchange rejected the request: {_TAIL} (member order-restricted)",
        # An empty detail.
        "",
    ],
    ids=["words-only", "no-paren", "not-last", "followed-by-paren", "empty"],
)
def test_edge_similar_words_do_not_match(client, fake, detail):
    fake.abort_code = grpc.StatusCode.ABORTED
    fake.abort_details = detail
    with pytest.raises(Aborted) as excinfo:
        client.cancel_all_orders()

    assert excinfo.value.request_definitely_rejected is True


def test_edge_flag_is_per_instance_and_class_defaults_are_unchanged():
    """Clearing one instance must not leak into the type or later errors."""

    class _FakeRpcError(grpc.RpcError):
        def __init__(self, details: str) -> None:
            self._details = details

        def code(self):
            return grpc.StatusCode.ABORTED

        def details(self):
            return self._details

    partial = translate(
        _FakeRpcError(f"cause {_TAIL}"), "CancelAllOrders", order_mutating=True
    )
    whole = translate(
        _FakeRpcError("cause"), "CancelAllOrders", order_mutating=True
    )

    assert partial.request_definitely_rejected is False
    assert whole.request_definitely_rejected is True
    assert Aborted.request_definitely_rejected is True
    assert VoltnirError.request_definitely_rejected is True
    assert OrderOutcomeUnknown.request_definitely_rejected is False
    assert RequestNotProcessed.request_definitely_rejected is True
