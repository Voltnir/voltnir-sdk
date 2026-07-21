"""Typed exceptions for Voltnir gRPC errors.

Every RPC failure surfaces as a `VoltnirError` subclass keyed off the gRPC
status code returned by the server. The mapping mirrors the REST -> gRPC
table in `docs/grpc_api_v1.html`.

## The distinction that matters when you are trading

For an order-mutating call (`submit_order`, `modify_order`, `cancel_order`,
`cancel_all_orders`) the question is never just "did it fail". It is:

    Is my order definitely NOT on the book, or might it be resting right now?

Get that wrong and you either double your position by resubmitting, or carry
an exposure you believe you cancelled. The exception type answers it:

**Definitely not submitted** (safe to retry as-is):
`InvalidArgument`, `PermissionDenied`, `FailedPrecondition`, `Unauthenticated`,
`NotFound`, `Aborted`. The gateway rejected the request during validation and
nothing reached the exchange.

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
    "Unavailable",
    "DeadlineExceeded",
    "Internal",
    "ResourceExhausted",
    "Cancelled",
    "OrderOutcomeUnknown",
    "OrderValidationError",
    "ClientClosed",
    "CaCertificateError",
    "AsyncLoopError",
    "UNCERTAIN_CODES",
    "translate",
]


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

    Raised for a missing `client_order_id`, an unspecified side, a
    non-integer value in a wire-unit field, a non-positive size, or a MODIFY
    that does not restate both price and quantity.
    """


class VoltnirError(Exception):
    """Base class for all SDK-raised gRPC errors."""

    #: True when this error proves the request had no effect on the exchange.
    #: `OrderOutcomeUnknown` overrides it to False. Non-order RPCs can ignore it.
    request_definitely_rejected: bool = True

    def __init__(self, code: grpc.StatusCode, message: str, rpc: str) -> None:
        super().__init__(f"{rpc}: {code.name}: {message}")
        self.code = code
        self.message = message
        self.rpc = rpc


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
    """A definitive negative: the order is not live at the terms you asked for.

    Three causes, and the distinction matters on a modify. `ModifyInProgress`
    and `OrderNotActive` are rejected before dispatch. `Rejected` means M7
    itself refused it, which is post-dispatch but still a definite answer.

    **On a modify or cancel, this does NOT mean the original order is gone.**
    A rejected modify leaves the order resting at its ORIGINAL price and size,
    so a desk that treats this as "my order is off the book" is carrying an
    exposure it believes it closed. Retrying the modify is safe; assuming
    flatness is not.
    """


class Unavailable(VoltnirError):
    """Service or a dependency is temporarily unavailable."""


class DeadlineExceeded(VoltnirError):
    """RPC deadline elapsed before the server completed the request.

    On an order-mutating RPC you get `OrderOutcomeUnknown` instead, because this
    code cannot distinguish "never dispatched" from "dispatched, awaiting M7
    acknowledgement".
    """


class Internal(VoltnirError):
    """Server-side bug or unexpected error."""


class ResourceExhausted(VoltnirError):
    """A limit was hit: message size, rate limit, or server capacity.

    The most common cause in practice is the *client-side* receive limit rather
    than anything server-side: a large `list_contracts` or `export_orders`
    response can exceed it. Raise the ceiling per client:

        VoltnirClient(
            ...,
            options=[("grpc.max_receive_message_length", 128 * 1024 * 1024)],
        )
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
# to resubmit a live order.
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
    statement about whether you are now short.
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

    if order_mutating and code in UNCERTAIN_CODES:
        return OrderOutcomeUnknown(
            code, details or "", rpc, client_order_id=client_order_id
        )

    cls = _CODE_TO_CLS.get(code, VoltnirError)
    return cls(code, details or "", rpc)
