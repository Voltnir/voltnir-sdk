"""Typed exceptions for Voltnir gRPC errors.

Every RPC failure surfaces as a `VoltnirError` subclass keyed off the gRPC
status code returned by the server. The mapping mirrors the REST -> gRPC
table in `docs/grpc_api_v1.html`.

## The distinction that matters when you are trading

For an order-mutating call (`submit_order`, `modify_order`, `cancel_order`,
`cancel_all_orders`) the question is never just "did it fail". It is:

    Is my order definitely NOT on the book, or might it be resting right now?

Get that wrong and you either double your position by resubmitting, or carry
an exposure you believe you cancelled. An exchange refusal of a new order is
not an exception: `submit_order` returns `state == REJECTED` with a `reason`.
For everything else the exception type answers it:

**Definitely not live at the terms you asked for** (safe to fix and retry):
`InvalidArgument`, `PermissionDenied`, `FailedPrecondition`, `Unauthenticated`,
`NotFound`, `Aborted`. A definite answer that the operation did not take
effect. The gateway refuses most of these before anything is sent; on a modify,
cancel or cancel-all, `Aborted` also covers the exchange refusing a request it
received (see `Aborted`).

**Definitely not applied, and retryable as-is** (`OrderChanged`): the exchange
refused a modify or cancel because the order's revision moved under it — a fill
or another modify landed while the command was on its way. The order is resting
exactly as it was and nothing was applied. Retry the same command; the gateway
rebuilds it on the revision it now holds.

**Definitely not applied, retry once acknowledged** (`OrderPending`): a modify
or cancel named an order the gateway has sent and the exchange has not yet
acknowledged, so there is no exchange order to act on yet. Nothing was sent.
The order may well be resting by the time you read this; retry once it is
acknowledged, or wait for it on the order stream.

**Definitely not processed** (`RequestNotProcessed`): the request reached the
gateway, was published, and the message broker handed it back undelivered
because the exchange was not accepting it. That return is the one negative
acknowledgement the exchange protocol offers, so this is a proof and not a
guess. Resubmit the identical request, `client_order_id` included: the gateway
frees a key whose only record is a request the exchange never saw.

**Unknown, may be live** (`OrderOutcomeUnknown`): the request may have reached
M7. Do NOT blindly resubmit. Reconcile first with
`get_order(client_order_id=...)`, which is exactly why `client_order_id` is a
required argument on `submit_order`.

The uncertainty is real, not defensive over-engineering: the gateway maps its
own post-dispatch M7 acknowledgement timeout to `DEADLINE_EXCEEDED`, and it
deliberately retains the order as pending in that branch because the order may
well be resting. A client-side deadline produces the identical status code. The
two are indistinguishable from the wire, so the SDK reports both as unknown
rather than picking the optimistic reading.

**`cancel_all_orders` can fail after part of it took effect.** A member-scoped
caller's cancel-all sends one cancel per order, so an error whose message ends
with `(cancel-all incomplete: ...)` follows cancels the exchange acknowledged,
whatever its type: the message says how many of the targeted orders' cancels
the exchange acknowledged and how many may still be resting. Such an error
reports `request_definitely_rejected = False` whatever its type, because part
of the request did take effect. Calling `cancel_all_orders` again is safe,
since a cancel only removes exposure; confirm the book with `list_orders()`.
"""

from __future__ import annotations

import grpc

__all__ = [
    "VoltnirError",
    "Unauthenticated",
    "PermissionDenied",
    "NotFound",
    "InvalidArgument",
    "FailedPrecondition",
    "Aborted",
    "OrderChanged",
    "OrderPending",
    "Unavailable",
    "RequestNotProcessed",
    "DeadlineExceeded",
    "Internal",
    "ResourceExhausted",
    "ExportBusy",
    "Cancelled",
    "OrderOutcomeUnknown",
    "OrderValidationError",
    "ClientClosed",
    "CaCertificateError",
    "AsyncLoopError",
    "UNCERTAIN_CODES",
    "NOT_PROCESSED_PREFIX",
    "CANCEL_ALL_INCOMPLETE_PREFIX",
    "ORDER_CHANGED_PREFIX",
    "ORDER_PENDING_PREFIX",
    "translate",
]

#: Prefix the gateway puts on the detail of an `UNAVAILABLE` it can prove the
#: exchange never received. It is part of the published gRPC contract, and the
#: only discriminator between the two kinds of `UNAVAILABLE` on an order path.
NOT_PROCESSED_PREFIX = "NOT_PROCESSED:"

#: Start of the parenthesised clause the gateway appends to a member-scoped
#: `CancelAllOrders` error when the exchange acknowledged the cancel for only
#: some of the targeted orders. The clause is always the last thing in the
#: detail: `(cancel-all incomplete: the exchange acknowledged the cancel for
#: N of M targeted orders; K may still be resting)`.
CANCEL_ALL_INCOMPLETE_PREFIX = (
    "(cancel-all incomplete: the exchange acknowledged the cancel for "
)

_CANCEL_ALL_RPC = "CancelAllOrders"


def _is_incomplete_cancel_all(rpc: str, message: str) -> bool:
    """True when `message` is a `CancelAllOrders` error ending in the
    incomplete clause, meaning some of its cancels took effect.

    The clause must close the message: a detail that quotes the words elsewhere
    is not the gateway's statement about this request.
    """
    if rpc != _CANCEL_ALL_RPC or not message.endswith(")"):
        return False
    start = message.rfind(CANCEL_ALL_INCOMPLETE_PREFIX)
    if start < 0:
        return False
    counts = message[start + len(CANCEL_ALL_INCOMPLETE_PREFIX) : -1]
    return ")" not in counts and "(" not in counts
#: Prefix the gateway puts on the detail of an `ABORTED` raised because the
#: order changed at the exchange while the command was on its way. It is part of
#: the published gRPC contract, and the only discriminator between that race and
#: every other `ABORTED` on an order path.
ORDER_CHANGED_PREFIX = "ORDER_CHANGED:"

#: Prefix the gateway puts on the detail of an `ABORTED` raised because a
#: modify or cancel named an order the exchange has not yet acknowledged. It is
#: part of the published gRPC contract, and the only discriminator between that
#: refusal and every other `ABORTED` on an order path.
ORDER_PENDING_PREFIX = "ORDER_PENDING:"


class AsyncLoopError(RuntimeError):
    """`AsyncVoltnirClient` was built or used against the wrong event loop.

    A `RuntimeError`, which is what the underlying failure already was, so
    existing handlers keep working; the point is that it now says what happened.

    grpc.aio binds a channel to the running loop at CONSTRUCTION. Building the
    client outside a loop (at import time, or in a DI container) and using it
    inside one produces a cross-loop failure whose native message is a wall of
    task repr with no mention of the client, plus a "coroutine was never
    awaited" warning from somewhere unrelated. Constructing inside the loop that
    will use it is the fix.
    """


class CaCertificateError(ValueError):
    """The TLS CA file could not be read, or is not a PEM certificate.

    A `ValueError`, not a `VoltnirError`: nothing was sent and no connection was
    attempted. Raised at client construction so a bad `ca_cert_path` fails where
    the mistake is, rather than as an opaque handshake error on the first RPC.
    """


class OrderValidationError(ValueError):
    """An order argument was rejected locally, before anything was sent.

    Deliberately a `ValueError` and NOT a `VoltnirError`: no RPC was attempted,
    so nothing reached the exchange. This is a bug in the calling code and it
    should not be swallowed by an `except VoltnirError` written to handle
    exchange failures.

    Raised by the order builders for every local check `submit_order` and
    `modify_order` run; the README table "What the SDK checks before anything
    is sent" lists them, with the reason for each. Also raised by
    `patch_member` (a missing `id`, or `max_slot_position` together with
    `clear_max_slot_position`), `set_self_trade_policy` (a policy other than
    "observe" or "reject") and `set_slot_limit` (a mode other than "off",
    "observe" or "reject"), and by `patch_member` and `set_slot_limit` for a
    field of the wrong type or one that does not fit its wire field.
    """


class VoltnirError(Exception):
    """Base class for all SDK-raised gRPC errors."""

    #: True when this error proves the request had no effect on the exchange.
    #: The class value is the default for its type; `OrderOutcomeUnknown`
    #: overrides it to False. Each instance carries its own value, which is
    #: False for an incomplete member-scoped `cancel_all_orders` whatever the
    #: type (see the module notes). Non-order RPCs can ignore it.
    request_definitely_rejected: bool = True

    def __init__(self, code: grpc.StatusCode, message: str, rpc: str) -> None:
        super().__init__(f"{rpc}: {code.name}: {message}")
        self.code = code
        self.message = message
        self.rpc = rpc
        self.request_definitely_rejected = (
            type(self).request_definitely_rejected
            and not _is_incomplete_cancel_all(rpc, message)
        )


class Unauthenticated(VoltnirError):
    """Bearer token missing, malformed, or unknown."""


class PermissionDenied(VoltnirError):
    """Authenticated user lacks the permission this RPC requires."""


class NotFound(VoltnirError):
    """Referenced contract / order / user / member does not exist."""


class InvalidArgument(VoltnirError):
    """Malformed request: bad enum, bad date, missing required field."""


class FailedPrecondition(VoltnirError):
    """State the request needs is not satisfied (e.g. position limit exceeded)."""


class Aborted(VoltnirError):
    """A definitive negative: the operation did not take effect.

    On an order call there are three causes. A modify already in progress, an
    order that is no longer active, or an order the exchange has not yet
    acknowledged (`OrderPending`), is refused by the gateway before anything is
    sent. Otherwise, on a modify, cancel or cancel-all, the exchange
    received the request and refused it, which is after dispatch but still a
    definite answer. A new order the exchange refuses does not raise: the call
    returns `state == REJECTED` with a `reason`, and it is not on the book.

    **On a modify or cancel, this does NOT mean the original order is gone.**
    A refused modify leaves the order resting at its ORIGINAL price and size,
    and a refused cancel leaves it resting unless it was filled or deleted in
    the meantime, so a desk that treats this as "my order is off the book" is
    carrying an exposure it believes it closed. Retrying the modify is safe;
    assuming flatness is not.

    **On `cancel_all_orders`, other orders may already be cancelled.** A
    member-scoped cancel-all sends one cancel per order and goes on past a
    refused one, so its `Aborted` follows cancels the exchange acknowledged:
    the message ends with how many, the rest may still be resting, and the
    error reports `request_definitely_rejected = False`. The account-wide
    cancel-all is one command, so its `Aborted` means it cancelled nothing.

    Outside the order calls it is a conflict with the current state, such as a
    username that already exists.
    """


class OrderChanged(Aborted):
    """A modify or cancel the exchange refused because the order had moved.

    A subclass of `Aborted`, because that is the status code it arrives on and
    an existing `except Aborted` should keep working.

    The exchange guards every order command with the revision the command was
    built on. A fill, or another modify, can move that revision in the moment
    between the gateway reading the order and the exchange applying the command,
    and the exchange then refuses the command outright. Nothing was applied: the
    order is resting exactly as it was, one revision further on, and no exposure
    changed.

    The answer is to retry the same command. The gateway rebuilds it against the
    revision it now holds, so the retry is not the request that just failed::

        try:
            client.cancel_order(client_order_id=oid)
        except OrderChanged:
            client.cancel_order(client_order_id=oid)   # rebuilt on the new revision

    Retry with a bound, not in an unbounded loop: an order filling repeatedly
    can lose the race more than once, and on a cancel the order may simply be
    gone by the next attempt, which comes back as `NotFound`.
    """


class OrderPending(Aborted):
    """A modify or cancel on an order the exchange has not yet acknowledged.

    A subclass of `Aborted`, because that is the status code it arrives on and
    an existing `except Aborted` should keep working.

    A new order answered `PENDING` (an `ack_only` submit, or one whose outcome
    did not arrive in time) has no exchange order id until the exchange's
    acknowledgement lands, and a modify or cancel needs one. The gateway refuses
    the command rather than holding it, and sends nothing. The order itself is
    unaffected and may be resting by now: this is not a sign that it is gone.

    Retry once the order is acknowledged, or wait for it on the order stream::

        try:
            client.cancel_order(client_order_id=oid)
        except OrderPending:
            # not acknowledged yet: retry shortly, with a bound
            ...

    On `cancel_all_orders` it means the cancel-all reached every acknowledged
    order it could, and one or more of yours were still awaiting their
    acknowledgement: the message ends with the counts, and the error reports
    `request_definitely_rejected = False`. Call `cancel_all_orders` again.
    """


class Unavailable(VoltnirError):
    """Service or a dependency is temporarily unavailable."""


class RequestNotProcessed(Unavailable):
    """An order-mutating RPC the exchange provably never received.

    A subclass of `Unavailable`, because that is the status code it arrives on
    and an existing `except Unavailable` should keep working.

    This is the one post-dispatch failure that is *not* ambiguous. The gateway
    publishes every request in mandatory mode, so a broker that cannot deliver
    one hands it back; that return is the only circumstance in which a client
    may conclude a request was not processed. The order is not on the book, no
    exposure was created, and no reconciliation is needed.

    Resubmit the identical request, `client_order_id` and all:

        try:
            client.submit_order(client_order_id=oid, ...)
        except RequestNotProcessed:
            client.submit_order(client_order_id=oid, ...)   # same key, on purpose

    Reusing the key is deliberate rather than tolerated. The exchange never saw
    it, so the gateway releases it and the resubmission replaces the record —
    which keeps the idempotency key doing its job across the outage instead of
    forcing a fresh one. Every other `UNAVAILABLE` on an order path stays
    `OrderOutcomeUnknown`.
    """

    def __init__(
        self,
        code: grpc.StatusCode,
        message: str,
        rpc: str,
        *,
        client_order_id: str | None = None,
    ) -> None:
        super().__init__(code, message, rpc)
        self.client_order_id = client_order_id


class DeadlineExceeded(VoltnirError):
    """RPC deadline elapsed before the server completed the request.

    On an order-mutating RPC you get `OrderOutcomeUnknown` instead, because this
    code cannot distinguish "never dispatched" from "dispatched, awaiting M7
    acknowledgement".
    """


class Internal(VoltnirError):
    """Server-side bug or unexpected error."""


class ResourceExhausted(VoltnirError):
    """A limit was hit: the gateway's request rate limit, or a message size.

    Every call except `cancel_order`, `cancel_all_orders` and switching trading
    off counts against the gateway's per-API-key request bound; past it the
    gateway refuses the call with "request rate limit exceeded", a message
    that names the bound. The call was not carried out: back off and retry.

    The other cause is the *client-side* receive limit: a large `list_orders`
    response can exceed it. Raise the ceiling per client:

        VoltnirClient(
            ...,
            options=[("grpc.max_receive_message_length", 128 * 1024 * 1024)],
        )
    """


class ExportBusy(VoltnirError):
    """A report export was refused because another one is being generated.

    The gateway builds one report at a time across all its users and queues
    none, so a request that arrives while one is generating is refused at once
    with HTTP 409 and nothing is started. The refusal says nothing about the
    request itself: send it again once the running export is done. The slot is
    freed when that report is ready or has failed, not when it is downloaded.
    The gateway's own text, "an export is already running, try again later", is
    the `message`.

    Raised only by `export_orders`, `export_trades` and `export_audit`. Its `code` is
    `ABORTED`, the status the gateway's REST-to-gRPC table pairs with 409. It
    is not `ResourceExhausted`, which is the per-key request bound (HTTP 429)
    and calls for slowing down rather than waiting for another export.
    """


class Cancelled(VoltnirError):
    """The call was cancelled, usually by the caller or a closing channel."""


class ClientClosed(VoltnirError):
    """An RPC was attempted on a client whose channel is already closed.

    A `VoltnirError` subclass deliberately. gRPC raises a bare `ValueError`
    ("Cannot invoke RPC on closed channel!") or a `cygrpc.UsageError` here,
    both of which escape an `except VoltnirError` supervisor loop and crash the
    process instead of triggering a reconnect. Since reconnecting is exactly
    what such a loop should do, this belongs inside the hierarchy.
    """

    def __init__(self, rpc: str) -> None:
        super().__init__(
            grpc.StatusCode.UNAVAILABLE,
            "client is closed; construct a new client to reconnect",
            rpc,
        )


class OrderOutcomeUnknown(VoltnirError):
    """An order-mutating RPC failed in a way that does NOT prove it had no effect.

    The order may be resting on the book right now. Reconcile before acting:

        try:
            client.submit_order(client_order_id=oid, ...)
        except OrderOutcomeUnknown:
            resp = client.get_order(client_order_id=oid)   # authoritative
            # ...only resubmit if the reconciliation says it is not there.

    Resubmitting without reconciling is how a desk ends up with double the
    intended position. `client_order_id` is carried on this exception so the
    reconciliation call is always available at the catch site.
    """

    request_definitely_rejected = False

    def __init__(
        self,
        code: grpc.StatusCode,
        message: str,
        rpc: str,
        *,
        client_order_id: str | None = None,
    ) -> None:
        super().__init__(code, message, rpc)
        self.client_order_id = client_order_id
        if client_order_id:
            self.args = (
                f"{rpc}: {code.name}: {message} "
                f"(order outcome UNKNOWN; reconcile with "
                f"get_order(client_order_id={client_order_id!r}))",
            )


_CODE_TO_CLS: dict[grpc.StatusCode, type[VoltnirError]] = {
    grpc.StatusCode.UNAUTHENTICATED: Unauthenticated,
    grpc.StatusCode.PERMISSION_DENIED: PermissionDenied,
    grpc.StatusCode.NOT_FOUND: NotFound,
    grpc.StatusCode.INVALID_ARGUMENT: InvalidArgument,
    grpc.StatusCode.FAILED_PRECONDITION: FailedPrecondition,
    grpc.StatusCode.ABORTED: Aborted,
    grpc.StatusCode.UNAVAILABLE: Unavailable,
    grpc.StatusCode.DEADLINE_EXCEEDED: DeadlineExceeded,
    grpc.StatusCode.INTERNAL: Internal,
    grpc.StatusCode.RESOURCE_EXHAUSTED: ResourceExhausted,
    grpc.StatusCode.CANCELLED: Cancelled,
}

# Status codes that do NOT prove the exchange was left untouched. Everything
# here is a transport or timing failure that can strike after the gateway has
# already published to M7.
#
# UNAVAILABLE is included deliberately, even though it usually means the
# connection never established: "usually" is not a basis for deciding whether
# to resubmit a live order. The one exception is an UNAVAILABLE whose detail
# carries `NOT_PROCESSED_PREFIX`, which is a proof rather than a likelihood and
# is split out into `RequestNotProcessed` before this set is consulted.
UNCERTAIN_CODES: frozenset[grpc.StatusCode] = frozenset(
    {
        grpc.StatusCode.DEADLINE_EXCEEDED,
        grpc.StatusCode.UNAVAILABLE,
        grpc.StatusCode.INTERNAL,
        grpc.StatusCode.CANCELLED,
        grpc.StatusCode.UNKNOWN,
    }
)


def translate(
    rpc_error: grpc.RpcError,
    rpc: str,
    *,
    order_mutating: bool = False,
    client_order_id: str | None = None,
) -> VoltnirError:
    """Convert a `grpc.RpcError` into the matching `VoltnirError` subclass.

    Falls back to the base `VoltnirError` for status codes with no dedicated
    subclass. When `order_mutating` is set and the code is one that cannot rule
    out an effect on the exchange, returns `OrderOutcomeUnknown` instead of the
    code's usual class: on an order path, "the deadline passed" is not a
    statement about whether you are now short. The exception is an `UNAVAILABLE`
    the gateway has marked `NOT_PROCESSED:`, which proves the exchange never
    received the request and becomes `RequestNotProcessed`.

    An `ABORTED` the gateway has marked `ORDER_CHANGED:` becomes `OrderChanged`
    whether or not `order_mutating` is set: the marker is only ever put on an
    order command's refusal, and the retry it calls for is the same either way.
    An `ABORTED` marked `ORDER_PENDING:` becomes `OrderPending` on the same
    terms.
    """
    code = (
        rpc_error.code()
        if callable(getattr(rpc_error, "code", None))
        else grpc.StatusCode.UNKNOWN
    )
    details = (
        rpc_error.details()
        if callable(getattr(rpc_error, "details", None))
        else str(rpc_error)
    )

    if code is grpc.StatusCode.ABORTED and (details or "").startswith(
        ORDER_CHANGED_PREFIX
    ):
        return OrderChanged(code, details or "", rpc)

    if code is grpc.StatusCode.ABORTED and (details or "").startswith(
        ORDER_PENDING_PREFIX
    ):
        return OrderPending(code, details or "", rpc)

    if (
        order_mutating
        and code is grpc.StatusCode.UNAVAILABLE
        and (details or "").startswith(NOT_PROCESSED_PREFIX)
    ):
        return RequestNotProcessed(
            code, details or "", rpc, client_order_id=client_order_id
        )

    if order_mutating and code in UNCERTAIN_CODES:
        return OrderOutcomeUnknown(
            code, details or "", rpc, client_order_id=client_order_id
        )

    cls = _CODE_TO_CLS.get(code, VoltnirError)
    return cls(code, details or "", rpc)
