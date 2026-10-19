"""Synchronous Voltnir gRPC client."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any, Literal

import grpc

from . import _rest_export, auth, channel
from ._generated import voltnir_api_v1_pb2 as pb2
from ._generated import voltnir_api_v1_pb2_grpc as pb2_grpc
from ._orders import (
    build_modify_order_request,
    build_patch_member_request,
    build_set_cash_limit_request,
    build_set_self_trade_policy_request,
    build_set_slot_limit_request,
    build_submit_basket_request,
    build_submit_order_request,
)
from ._recall import returning_result
from .errors import ClientClosed, OrderValidationError, translate


_NOT_FIELDS = ("self", "timeout")


def _kwargs_request(cls: type, scope: dict[str, Any]):
    """Build `cls` from a wrapper's `locals()`, setting only the fields passed.

    The typed filter wrappers (audit, message logs) take one keyword
    per proto field, each defaulting to `None`. `None` means "not passed", so
    only non-`None` values reach the request. This preserves proto3 presence:
    an omitted `optional` field stays unset, distinct from an explicit 0.
    `self` and the per-call `timeout` are wrapper arguments, not fields.
    """
    return cls(
        **{k: v for k, v in scope.items() if k not in _NOT_FIELDS and v is not None}
    )


class VoltnirClient:
    """Sync client for `voltnir.api.v1.VoltAPI`.

    >>> with VoltnirClient(host="localhost", port=3443, api_key="...") as c:
    ...     me = c.get_me()
    ...     print(me.username)

    All RPCs raise a `VoltnirError` subclass on failure (see `errors.py`).

    The user and member methods (`list_users`, `create_user`, `delete_user`,
    `set_permissions`, `get_user_members`, `set_user_members`, `list_members`,
    `create_member`, `patch_member`, `delete_member`) are desk management and
    need the gateway's
    desk-management license as well as their permission. Under a trader
    license each raises `PermissionDenied` with the message
    `LICENSE_DESK_REQUIRED`, whatever the caller's permissions, so granting
    `manage_users` or `manage_members` does not lift it.
    """

    def __init__(
        self,
        host: str,
        port: int = 3443,
        *,
        api_key: str,
        tls: bool = False,
        ca_cert_path: str | None = None,
        timeout: float | None = 10.0,
        options: Sequence[tuple[str, object]] | None = None,
        rest_url: str | None = None,
    ) -> None:
        """Open a client.

        `options` are gRPC channel options, merged over the SDK defaults
        (keepalive tuned for long-lived `Watch*` streams, and a 64 MB message
        ceiling in place of gRPC's 4 MB). Caller values win per key. See
        `voltnir_sdk.channel.DEFAULT_CHANNEL_OPTIONS`.

        `timeout` is the default deadline, in seconds, for unary calls only;
        every method that calls the gateway takes its own `timeout=` that
        replaces it for that one call. Streams default to no deadline and are
        ended by breaking out of the iterator.

        `rest_url` is the gateway's REST address, e.g.
        `"https://gateway.example:3000"` (a trailing slash is fine). Only the
        report exports use it (`export_orders`, `export_trades`,
        `export_audit`), because the
        gateway serves a report as a file over REST. An `https` URL trusts
        `ca_cert_path` when given, else the system trust store; the API key is
        sent as the same bearer token. Without it every other method works and
        an export raises `ValueError`.
        """
        self._rest = _rest_export.make_endpoint(rest_url, api_key, ca_cert_path)
        self._channel = channel.build_sync_channel(
            host, port, tls=tls, ca_cert_path=ca_cert_path, options=options
        )
        self._stub = pb2_grpc.VoltAPIStub(self._channel)
        self._auth = auth.auth_metadata(api_key)
        self._timeout = timeout
        self._closed = False

    def __enter__(self) -> "VoltnirClient":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        """Close the channel. Further calls raise `ClientClosed`.

        Idempotent. Prefer the context manager, which closes on both normal and
        exceptional exit. Abandoned streams are cancelled when their iterator
        is dropped, so a long-lived consumer does not need to close each one."""
        self._closed = True
        self._channel.close()

    # ──────────────────────────────────────────────────────────────────────
    # Internal call helpers
    # ──────────────────────────────────────────────────────────────────────

    def _unary(
        self,
        rpc: str,
        request,
        *,
        timeout: float | None = None,
        order_mutating: bool = False,
        client_order_id: str | None = None,
    ):
        if self._closed:
            raise ClientClosed(rpc)
        method = getattr(self._stub, rpc)
        try:
            return method(
                request,
                timeout=timeout if timeout is not None else self._timeout,
                metadata=self._auth,
            )
        except grpc.RpcError as e:
            raise translate(
                e,
                rpc,
                order_mutating=order_mutating,
                client_order_id=client_order_id,
            ) from e

    def _stream(
        self, rpc: str, request, *, timeout: float | None = None
    ) -> Iterator:
        if self._closed:
            raise ClientClosed(rpc)
        method = getattr(self._stub, rpc)
        # No timeout on streams by default; callers cancel by breaking out
        # of the iterator (or calling .cancel() on the call object).
        call = method(
            request,
            timeout=timeout,
            metadata=self._auth,
        )
        try:
            for item in call:
                yield item
        except grpc.RpcError as e:
            raise translate(e, rpc) from e
        finally:
            # Explicit, not incidental. Dropping the generator would often
            # release the call anyway via CPython refcounting, but that is a
            # property of the interpreter rather than a guarantee of this code,
            # and it does not hold for the async equivalent at all.
            call.cancel()

    # ──────────────────────────────────────────────────────────────────────
    # Trading: orders
    # ──────────────────────────────────────────────────────────────────────

    def submit_order(
        self,
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
        timeout: float | None = None,
    ) -> pb2.SubmitOrderResponse:
        """Submit a new order.

        Requires the `create_order` permission.

        >>> from voltnir_sdk import Side, new_client_order_id
        >>> oid = new_client_order_id()
        >>> resp = client.submit_order(
        ...     client_order_id=oid,
        ...     side=Side.BUY,
        ...     delivery_area_id="10YBE----------2",
        ...     contract_id=12345,
        ...     price_cents=5007,        # 50.07 CCY/MWh
        ...     quantity_sub_mw=1500,    # 1.5 MW
        ... )

        **Units** are the wire units the REST / gRPC / WS docs specify, and the
        same ones every response carries: `price_cents` is cents (CCY/MWh x
        100, 5000 = 50.00) and `quantity_sub_mw` is sub-MW (MW x 1000, 1000 =
        1.0 MW, must be > 0). No decimal conversion happens on this path, so
        what you submit and what you read back on `OwnOrder` are the same unit.

        The names carry the unit deliberately: a bare `price=50` reads as 50
        CCY/MWh and would be silently accepted as 0.50. Non-integer values are
        rejected rather than truncated. If you are holding decimals, convert
        explicitly with `voltnir_sdk.price_to_cents` / `quantity_to_sub_mw`.

        **Reusing a key.** `client_order_id` is required, not optional as the
        wire allows. It is the key that makes recovery possible: the gateway
        refuses a reused key ("is already in use") while it holds the original
        order's record in memory, in any state. That record is not kept for
        ever. A gateway restart drops every record; the contract sweep, about
        an hour after the contract's delivery ends, drops a finished order's;
        and a resubscription to the exchange's order feed rebuilds the records
        from the orders still on the market, which frees the keys of filled
        and deleted orders. A rejected order was never on the market, so the
        rebuild keeps its record and its key until the contract sweep, or
        until a restart for an order on a contract the gateway never listed,
        such as a refused new block order. The refusal therefore guards against two
        live orders under one key; it is not a permanent ledger of every key
        used. A key written off after an unacknowledged submission stays
        refused ("was reclaimed after no exchange acknowledgement; use a new
        id"), so once reconciliation shows the order is not there, resubmit
        under a new key. The one key to reuse on purpose is the one a
        `RequestNotProcessed` hands back. Generate keys with
        `new_client_order_id()`.

        **The member.** `v_member_short_id=""` (the default) is an untagged
        House order, which needs the `trade_global` permission. Naming a
        member needs that member assigned to your account, or
        `bypass_member_check`; the member must also be active and allowed the
        order's delivery area. A missing, inactive or unassigned member is an
        `InvalidArgument`, and so is a House order without `trade_global`; a
        member not allowed the area is a `FailedPrecondition`.

        **Product bounds.** The gateway also holds the order to its product's
        price band, tick, quantity bounds and volume increment, and to the
        order-size limit the exchange reports for the member the gateway
        trades as; each refusal is an `InvalidArgument` naming the bound.

        **Failure.** `OrderOutcomeUnknown` means the order MAY be resting -
        reconcile with `get_order(client_order_id=...)` before resubmitting.
        Every other `VoltnirError` means the order was not placed. An exchange
        refusal of an order it received is NOT an exception: the call returns
        with `state == OrderState.REJECTED`, the exchange's text in `reason`
        and its numeric code in `err_code` (0 when the refusal carried no
        single code), so always check `state`.

        **`entry_state`** is `""`/`"ACTI"` (default: live and exposed to the
        market) or `"HIBE"` (hibernated: accepted and resting server-side but
        NOT exposed, so it can never fill until activated with
        `modify_order(action=ModifyAction.ACTIVATE)`). Passing `"HIBE"` in the
        belief that it means "active" leaves you holding an order that will
        never trade. A pre-arranged order cannot be entered `"HIBE"`: the
        exchange reports a hibernated pre-arranged order as inactive, so it
        could be neither activated nor cancelled, and the gateway refuses it.

        Identify the contract with `contract_id`, or with both `product` and
        `delivery_start`; `delivery_start` follows the rule on
        `get_contract_by_delivery`.

        **User-defined blocks.** `delivery_end` with `order_type=OrderType.BLOCK`,
        `product` and `delivery_start`, and no `contract_id`, creates a block
        over `[delivery_start, delivery_end)`: one order on at least two
        consecutive contracts of the product, filled all at once or not at all.
        The window must start and end on the product's contract boundaries,
        with no contract missing between them, and be no longer than the
        product's `blockMaximumHours`; a block takes `ExeRestriction.AON` or
        `ExeRestriction.FOK`. The gateway refuses anything else with a
        `BLOCK_*` code before the order reaches the exchange. The exchange
        creates the block's own contract on the first order for it; join an
        existing block with its `contract_id` and `order_type=OrderType.BLOCK`.
        While the exchange has not named the contract, the pending order
        carries a gateway placeholder `contract_id` (2**50 and above). `validity_date` is an RFC 3339 instant in the
        form the exchange's schema takes: an uppercase "T" and "Z", seconds up to
        59 and an offset within +/-14:00, which is forwarded unchanged; the
        exchange works in UTC, so send "Z"; the exchange GUI's "02:30A" form is
        refused.

        **Checked locally before dispatch** (raises `OrderValidationError`, a
        `ValueError`, so nothing was sent): a present `client_order_id`; a real
        `side`; a `delivery_area_id` of exactly 16 characters (the EIC code);
        a contract identity; integer wire values within their field
        width; `quantity_sub_mw > 0`; `display_qty_sub_mw` only on an ICEBERG
        order and below the total (and mandatory for one); and FOK/IOC only
        alongside `validity_res=ValidityRes.VALIDITY_NON`, which the gateway
        requires and which is spelled `VALIDITY_NON`, not `NON`; `delivery_end`
        only on a block create; and AON or FOK on a block order.

        All of these mirror rules the gateway also enforces, so the local check
        buys a round trip and a clearer message rather than being the only
        thing standing between you and a bad order.

        **`ack_only`** controls what the call waits for. Default `False` waits
        for the exchange's outcome: the response `state` is `ACTIVE` (or another
        settled state) once the confirming execution report has landed. `True`
        returns as soon as the exchange acknowledges receipt, with
        `state == PENDING` — received, outcome not yet known. The same
        `PENDING` is returned when a waited call's outcome does not arrive inside
        the gateway's outcome window. A refusal is never a `PENDING` response:
        it is a `VoltnirError`, or `state == REJECTED` when the exchange
        refused. An `ack_only=True` caller manages the
        lifecycle itself and must follow the order stream (`watch_orders`) to
        learn the resulting state or a later refusal.
        """
        request = build_submit_order_request(
            client_order_id=client_order_id,
            side=side,
            delivery_area_id=delivery_area_id,
            price_cents=price_cents,
            quantity_sub_mw=quantity_sub_mw,
            contract_id=contract_id,
            product=product,
            delivery_start=delivery_start,
            delivery_end=delivery_end,
            order_type=order_type,
            exe_restriction=exe_restriction,
            validity_res=validity_res,
            entry_state=entry_state,
            display_qty_sub_mw=display_qty_sub_mw,
            validity_date=validity_date,
            pre_arranged_acct=pre_arranged_acct,
            v_member_short_id=v_member_short_id,
            ack_only=ack_only,
        )
        return self._unary(
            "SubmitOrder",
            request,
            timeout=timeout,
            order_mutating=True,
            client_order_id=client_order_id,
        )

    def modify_order(
        self,
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
        timeout: float | None = None,
    ) -> pb2.ModifyOrderResponse:
        """Modify, activate, or deactivate an existing order.

        Requires the `modify_order` permission.

        **A MODIFY is a full restatement, not a patch.** Both price and quantity
        are required and whatever you pass becomes the resting order. To reprice
        a partially-filled order, pass the REMAINING quantity: restating the
        original size re-inflates an exposure you have partly closed. The SDK
        rejects a MODIFY missing either field rather than letting the exchange
        decide what you meant.

        >>> client.modify_order(
        ...     client_order_id=oid,
        ...     price_cents=5100,
        ...     quantity_sub_mw=800,    # what is LEFT, not the original
        ... )

        `ACTIVATE` / `DEACTIVATE` take neither price nor quantity: they put the
        order back on or take it off the book at the price and size it rests
        at, and the gateway ignores any price, quantity or display size passed
        with them, so the SDK holds them to none of the MODIFY rules: only
        that each is an int that fits its wire field.

        Units follow `submit_order`: cents and sub-MW. Plain ints are accepted,
        so the wire's `Int64Value` / `UInt32Value` wrapping is handled for you.
        `validity_date` follows the rule on `submit_order`.

        **A zero quantity on a MODIFY is rejected**, locally and by the
        gateway, as is a `display_qty_sub_mw` at or above the quantity. A zero
        is reachable from correct code: `remaining = original - filled` is
        exactly zero when the order fills completely between the snapshot you
        read and the modify you build from it, and a zero restatement means a
        0.0 MW order rather than "no change". To withdraw an order, use
        `cancel_order()`.

        **`v_member_short_id`** cannot move an order to another member: an
        order keeps its member for life. `""` (the default) acts on the order
        under its own member. A name given must be a member that exists, is
        active and is yours to act on (assigned, or `bypass_member_check`),
        else `InvalidArgument`; a name other than the order's own member is a
        `NotFound`, the same answer as an order you may not see.

        Raises `OrderOutcomeUnknown` if the outcome cannot be determined; the
        order may be resting at either the old or the new terms, so reconcile
        with `get_order(client_order_id=...)`.

        **`ack_only`** controls what the call waits for. Default `False` waits
        for the exchange's outcome; the response `outcome` is `CONFIRMED` once
        this call's own execution report has landed (of two modifies sent at
        one revision, the one the exchange refuses raises that refusal). `True`
        returns as soon as the exchange acknowledges receipt, with
        `outcome == ACKNOWLEDGED` — received, outcome not yet known. The same `ACKNOWLEDGED` is returned when a waited
        call's outcome does not arrive inside the gateway's outcome window.
        Either way a refusal is a `VoltnirError`, never an `ACKNOWLEDGED`
        response. An `ack_only=True` caller manages the lifecycle itself and must
        follow the order stream (`watch_orders`) to learn the outcome or a later
        refusal.
        """
        request = build_modify_order_request(
            client_order_id=client_order_id,
            action=action,
            price_cents=price_cents,
            quantity_sub_mw=quantity_sub_mw,
            display_qty_sub_mw=display_qty_sub_mw,
            validity_res=validity_res,
            validity_date=validity_date,
            v_member_short_id=v_member_short_id,
            ack_only=ack_only,
        )
        return self._unary(
            "ModifyOrder",
            request,
            timeout=timeout,
            order_mutating=True,
            client_order_id=client_order_id,
        )

    def cancel_order(
        self,
        *,
        client_order_id: str,
        ack_only: bool = False,
        timeout: float | None = None,
    ) -> pb2.CancelOrderResponse:
        """Cancel one resting order by its `client_order_id`.

        Requires the `delete_order` permission.

        Raises `OrderOutcomeUnknown` if the outcome cannot be determined, in
        which case the order may still be live: confirm with
        `get_order(client_order_id=...)` rather than assuming it is gone.

        **`ack_only`** controls what the call waits for. Default `False` waits
        for the exchange's outcome; the response `outcome` is `CONFIRMED` once
        the deletion's execution report has landed for this call (of two
        cancels of one order, the one the exchange refuses raises that
        refusal). `True` returns as soon as
        the exchange acknowledges receipt, with `outcome == ACKNOWLEDGED` —
        received, outcome not yet known. The same `ACKNOWLEDGED` is returned when
        a waited call's outcome does not arrive inside the gateway's outcome
        window. Either way a refusal is a `VoltnirError`, never an
        `ACKNOWLEDGED` response. An `ack_only=True` caller manages the lifecycle
        itself and must follow the order stream (`watch_orders`) to learn the
        outcome or a later refusal.
        """
        return self._unary(
            "CancelOrder",
            pb2.CancelOrderRequest(client_order_id=client_order_id, ack_only=ack_only),
            timeout=timeout,
            order_mutating=True,
            client_order_id=client_order_id,
        )

    def cancel_all_orders(self, timeout: float | None = None) -> pb2.CancelAllOrdersResponse:
        """Cancel every resting order for the caller. The kill switch.

        Requires the `delete_order` permission.

        `deleted` counts orders whose cancel the exchange acknowledged, not
        deletions it has confirmed. A member-scoped cancel the exchange did not
        acknowledge in full raises instead, with the targeted and acknowledged
        counts in the message. Neither is proof the book is clear: confirm
        with `list_orders()` before standing down.

        **Pass a larger `timeout` for a member-scoped cancel-all.** A caller
        without both `bypass_member_check` and `trade_global` gets one cancel
        per order, each waiting for the exchange's acknowledgement before the
        next is sent, so a large book can outrun the client's default deadline
        (10 seconds unless the client was built with another `timeout`). The
        gateway honours the call's deadline: when it passes, the sweep stops
        where it is. Cancels already sent stand, the orders it had not reached
        stay resting, and the call raises `OrderOutcomeUnknown`. Calling
        `cancel_all_orders` again is safe.

        Raises `OrderOutcomeUnknown` if the outcome cannot be determined.
        """
        return self._unary(
            "CancelAllOrders",
            pb2.CancelAllOrdersRequest(),
            timeout=timeout,
            order_mutating=True,
        )

    def submit_basket(
        self,
        *,
        list_exec_inst: str,
        orders: Sequence[dict[str, Any]],
        basket_ref: str = "",
        timeout: float | None = None,
    ) -> pb2.SubmitBasketResponse:
        """Enter 1 to 100 orders as one exchange order entry.

        Requires the `create_order` permission.

        >>> from voltnir_sdk import ExeRestriction, Side, ValidityRes, new_client_order_id
        >>> leg = dict(delivery_area_id="10YDE-RWENET---I", quantity_sub_mw=1000,
        ...            exe_restriction=ExeRestriction.FOK,
        ...            validity_res=ValidityRes.VALIDITY_NON)
        >>> resp = client.submit_basket(
        ...     list_exec_inst="linked",
        ...     basket_ref=new_client_order_id(),
        ...     orders=[
        ...         dict(leg, client_order_id=new_client_order_id(), side=Side.BUY,
        ...              contract_id=111, price_cents=5000),
        ...         dict(leg, client_order_id=new_client_order_id(), side=Side.SELL,
        ...              contract_id=222, price_cents=5100),
        ...     ],
        ... )

        Each order is a mapping of `submit_order` keyword arguments, with the
        same units and the same local checks. `list_exec_inst` says how the
        exchange treats the list:

        - `"none"`: each order is validated and processed on its own.
        - `"valid"`: every order must pass the exchange's entry validation or
          the whole list is rejected; accepted orders then rest independently.
        - `"linked"`: every order must be `ExeRestriction.FOK` (with
          `ValidityRes.VALIDITY_NON`); the list executes whole or is deleted
          whole, and its orders never match each other.

        **All or none at the gateway.** Every order is checked before anything
        is sent: product bounds, member, area, position, slot, cash and the
        self-cross policy. One refusal refuses the whole basket with
        `BASKET_REFUSED`, whose message lists each failing order as
        `[<index>] <CODE>: <text>`; nothing reaches the exchange. A `none` or
        `valid` basket is checked as if its orders were entered one after
        another, so a later order sees the earlier ones resting. A `linked`
        basket is checked on its net effect on position and slot, because it
        fills whole or not at all, while cash is the sum of each order's own
        requirement. A product that publishes `linked_order_product` false
        refuses a linked basket (`BASKET_LINKED_NOT_SUPPORTED`).

        **The answer** lists each order's `state`, `reason` and `err_code` in
        request order, as `submit_order` answers one order. An exchange
        rejection of the list, or the kill of a linked list, is each order's
        state, never an exception: a refused `valid` or `linked` list answers
        every order `REJECTED`, one the refusal did not name with its own
        reason and code. `PENDING` is an order whose outcome did not
        arrive in time: follow `watch_orders`. `basket_id` is the exchange's
        own id, 0 when it reported none.

        **`basket_ref`** is the basket's idempotency key, a UUID; "" lets the
        gateway mint one, which the response returns. A key the gateway still
        holds a basket under raises `BASKET_REF_IN_USE`. Each order carries it
        as `OwnOrder.basket_ref`, and an order that survives a gateway restart
        still carries it (the exchange may delete a basket's orders when the
        gateway logs out, although on its simulator it kept them through a
        restart); `cancel_basket` takes it.

        **Load management.** A basket spends one order transaction per order,
        and one that would cross the gateway's throttling threshold is refused
        whole.

        **Failure.** `OrderOutcomeUnknown` means the orders MAY be resting:
        reconcile each with `get_order(client_order_id=...)`. Every other
        `VoltnirError` means nothing was placed.
        """
        request = build_submit_basket_request(
            list_exec_inst=list_exec_inst, orders=orders, basket_ref=basket_ref
        )
        return self._unary(
            "SubmitBasket", request, timeout=timeout, order_mutating=True
        )

    def cancel_basket(
        self, basket_ref: str, *, timeout: float | None = None
    ) -> pb2.CancelBasketResponse:
        """Cancel every resting order of one basket.

        Requires the `delete_order` permission. One cancel per resting order
        of the basket that you may act on; each result says whether the
        exchange acknowledged it, or the code and text it was refused with
        (`ORDER_PENDING` for an order not yet acknowledged). A basket you hold
        no order of raises `NotFound` (`BASKET_NOT_FOUND`). `cancelled` counts
        acknowledged cancels, not confirmed deletions: confirm with
        `list_orders()`.
        """
        return self._unary(
            "CancelBasket",
            pb2.CancelBasketRequest(basket_ref=basket_ref),
            timeout=timeout,
            order_mutating=True,
        )

    def recall_trade(
        self,
        trade_id: str,
        *,
        revision_no: int | None = None,
        timeout: float | None = None,
    ) -> pb2.RecallTradeResponse:
        """Ask the exchange to recall one executed trade (a mistrade).

        Requires the `recall_trade` permission. Only a trade this gateway's
        exchange login placed can be recalled, for a member you may act on; a
        trade another exchange user on your balancing group placed raises
        `PermissionDenied`, and one you cannot see raises `NotFound`.

        `trade_id` is the exchange trade id. `revision_no` is the revision you
        saw: if the gateway holds a newer one, nothing is sent and `Aborted` is
        raised (`TRADE_CHANGED`), so you recall the trade you looked at. Omit it
        to recall at the gateway's latest revision.

        Returns the `RecallTradeResponse` with one result. Read its `outcome`:

        - `requested`: the exchange acknowledged and the trade moved to a
          recall state
          (`RREQ`, or `RSFA` for a trade with another exchange).
        - `submitted`: acknowledged, but the trade had not moved to a recall
          state (or moved to another, named in `reason`) within
          the gateway's wait. Watch the trade on `watch_trades`. A new recall
          of it is `not_recallable` until 60 seconds after the first was sent,
          unless the exchange refuses or returns the first sooner.
        - `refused`: the exchange refused it; `m7_err_code` and `m7_error_key`
          say why (2013 `trade_execution_too_long_ago` when the exchange's
          5-minute window after execution has passed).
        - `unknown`: no acknowledgement in time. The request may have reached
          the exchange: read the trade's state before asking again. A new
          recall of it is `not_recallable` until 60 seconds after the first
          was sent, unless the exchange refuses or returns the first sooner.
        - `not_recallable`: nothing was sent; the trade is not `ACTI`, or a
          recall of it (or of a trade recalled with it) is still awaiting
          the exchange.
        - `not_sent`: the exchange never received it; safe to ask again.

        A refused, unknown, not-recallable or not-sent recall still returns its
        result rather than raising. The gateway applies none of the exchange's
        windows; it forwards the request and reports the refusal. Market
        operations decide an accepted recall later: the trade then moves to
        `RGRA` (granted, reversed) or `RREJ` (rejected, it stands). A trade with
        a `parent_trade_id` is recalled together with every trade sharing that
        parent; `cascaded_with` names the ones you hold.

        The gateway waits for the exchange's acknowledgement and then for the
        trade to move, about 7 seconds together with its defaults
        (`order_ack_timeout_ms` 2000 plus `recall_outcome_wait_ms` 5000). Set
        `timeout` above that sum. A client-side deadline that passes first
        raises `DeadlineExceeded` with no result: the recall may have been sent,
        so read the trade's state before asking again.
        """
        request = pb2.RecallTradeRequest(trade_id=trade_id)
        if revision_no is not None:
            request.revision_no = revision_no
        return returning_result(
            lambda: self._unary("RecallTrade", request, timeout=timeout)
        )

    def recall_order_trades(
        self, client_order_id: str, *, timeout: float | None = None
    ) -> pb2.RecallTradeResponse:
        """Ask the exchange to recall every recallable trade of one order.

        Requires the `recall_trade` permission. An order that filled in
        several trades needs one recall per trade, each inside the exchange's
        window: this sends them all at once, one per `parent_trade_id` group,
        and returns one result per trade and `counts` per outcome. `outcome`
        is as on `recall_trade`, plus `cascaded` for a trade not sent itself
        because the exchange took the request of the trade in its
        `cascaded_with`, whose request covers it: it reads no stronger than
        that trade's own outcome (`submitted` there means the decision is
        still to come for both). When that request was refused,
        unknown or not sent, the trade carries the same outcome and reason
        instead. Every own trade of the order is answered, the ones not `ACTI`
        as `not_recallable`. Raises `NotFound` when you hold no trade of the
        order you may recall.

        Set `timeout` above the gateway's waits, as on `recall_trade`; on a
        client-side deadline, read the order's trades before asking again.
        """
        request = pb2.RecallTradeRequest(client_order_id=client_order_id)
        return returning_result(
            lambda: self._unary("RecallTrade", request, timeout=timeout)
        )

    def get_order(
        self, *, client_order_id: str, timeout: float | None = None
    ) -> pb2.GetOrderResponse:
        """Fetch one order by `client_order_id`.

        Exactly one of the `confirmed` / `pending` fields is populated, so test
        with `HasField` rather than truthiness. `pending` means dispatched but
        not yet acknowledged by M7.

        This is the authoritative reconciliation call after an
        `OrderOutcomeUnknown`. Treat a `NotFound` as conclusive only if it
        persists: an order still in flight reads as absent for a moment, and
        concluding "it never landed" too early is what leads to a resubmit that
        doubles the position.

        **Member-scoped:** an order of a member you are not assigned, or an
        untagged House order, reads as `NotFound` unless you hold
        `read_orders` / `bypass_member_check`, the same answer as an unknown
        id."""
        return self._unary(
            "GetOrder",
            pb2.GetOrderRequest(client_order_id=client_order_id),
            timeout=timeout,
        )

    def list_orders(
        self,
        *,
        delivery_area: str = "",
        contract_id: int = 0,
        product: str = "",
        delivery_start: str = "",
        v_member_short_id: str = "",
        timeout: float | None = None,
    ) -> pb2.ListOrdersResponse:
        """List confirmed resting orders, optionally filtered.

        Filter priority mirrors REST `GET /orders`: (delivery_area +
        contract_id) > (delivery_area + product [+ delivery_start]) >
        delivery_area alone (all orders in that area) > no filter.
        `contract_id` or `product` without `delivery_area`, or a
        negative `contract_id`, raises INVALID_ARGUMENT.

        Member-scoped by default: the result is narrowed to the virtual
        members assigned to the caller (untagged house orders withheld) unless
        the caller holds `read_orders` / `bypass_member_check`. Set
        `v_member_short_id` to narrow to one member; PERMISSION_DENIED unless
        the caller is assigned to it or holds broad order read.
        """
        return self._unary(
            "ListOrders",
            pb2.ListOrdersRequest(
                delivery_area=delivery_area,
                contract_id=contract_id,
                product=product,
                delivery_start=delivery_start,
                v_member_short_id=v_member_short_id,
            ),
            timeout=timeout,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Trading: contracts
    # ──────────────────────────────────────────────────────────────────────

    def list_contracts(
        self, *, area_id: str, timeout: float | None = None
    ) -> pb2.ListContractsResponse:
        """The contract catalogue of one delivery area, sorted by delivery start.

        A catalogue for finding contract ids: each `ContractSummary` names a
        contract, its product, its delivery period and its state and trading
        phase, and carries no order book and no prices. Call it at startup or
        when a new delivery day appears; never poll it. Read one contract's
        book with `get_contract` (or `get_contract_by_delivery`), and follow
        contracts live with `watch_contracts`, by id or by product.

        Authenticated; no permission required. The catalogue lists active
        contracts whose delivery period is known. `predefined=False` marks a
        user-defined block contract, which accepts only block orders; a
        regular order there is rejected by the exchange."""
        return self._unary(
            "ListContracts",
            pb2.ListContractsRequest(area_id=area_id),
            timeout=timeout,
        )

    def get_contract(
        self, *, area_id: str, contract_id: str, timeout: float | None = None
    ) -> pb2.ContractDetail:
        """Contract detail, including your working orders on it.

        **Check BOTH `orders_acknowledged` and `orders_pending`** when deciding
        whether you already have an order working here. An order that has been
        dispatched but not yet acknowledged by M7 appears only in the pending
        list, so looking at the acknowledged list alone is a duplicate-order
        path -- the same hazard `OrderOutcomeUnknown` reconciliation exists to
        prevent.

        **Member-scoped:** `orders_acknowledged`, `orders_pending`, `trades`
        and `net_pos` cover only the members assigned to you, with House
        orders and trades withheld, unless you hold `read_orders` /
        `bypass_member_check`. No exception says so.

        `contract` carries the order book and the exchange's reference price
        for its delivery area: `ref_px_cents`, `ref_px_type` ("C" closing --
        the exchange's default -- or "O" opening), `ref_px_date` (YYYY-MM-DD)
        and `ref_px_updated_ms`. Read `ref_px_cents` with `HasField`: it uses
        proto3 field presence because 0 and negative are real prices on a power
        market, so 0 cannot double as "not reported". It is reference data, not
        the mark `get_pnl` values open positions at.

        Units on the contract are wire units: prices in cents, quantities in
        sub-MW.
        """
        return self._unary(
            "GetContract",
            pb2.GetContractRequest(area_id=area_id, contract_id=contract_id),
            timeout=timeout,
        )

    def get_contract_by_delivery(
        self, *, area_id: str, prod: str, dlvry_start: str, timeout: float | None = None
    ) -> pb2.ContractDetail:
        """Look up one contract by product and delivery start, instead of by id.

        Authenticated; no permission required. `dlvry_start` is the contract's
        UTC delivery start in any RFC 3339 spelling: "2026-10-25T00:00:00Z",
        "2026-10-25T00:00:00.000Z" and "2026-10-25T02:00:00+02:00" name the same
        contract. On a clock-change day the doubled hour is two instants: on
        2026-10-25, 02:00 CEST is 00:00Z (hour "02A-02B") and 02:00 CET is 01:00Z
        (hour "02B-03"); the A/B marker exists only in contract names, so name the
        hour by its UTC start. A value that is not a timestamp is refused with
        INVALID_ARGUMENT. See `get_contract` for the caveat about checking both
        order lists."""
        return self._unary(
            "GetContractByDelivery",
            pb2.GetContractByDeliveryRequest(
                area_id=area_id, prod=prod, dlvry_start=dlvry_start
            ),
            timeout=timeout,
        )

    def get_hub2hub(
        self,
        *,
        delivery_area_from: str,
        delivery_from: str,
        delivery_to: str,
        delivery_area_to: str = "",
        timeout: float | None = None,
    ) -> pb2.GetHub2HubResponse:
        """ATC rows out of `delivery_area_from`, optionally limited to one
        destination via `delivery_area_to`.

        `delivery_from` and `delivery_to` are RFC 3339 bounds on the delivery
        start, the first inclusive and the second exclusive; a value that does
        not parse raises `InvalidArgument`.

        Units: `atc_out` / `atc_in` are signed SUB-MW (MW x 1000) -- negative
        ATC is real, not an error. The `*_best_bid` / `*_best_ask` fields on the
        same rows are CENTS (CCY/MWh x 100).
        """
        return self._unary(
            "GetHub2Hub",
            pb2.GetHub2HubRequest(
                delivery_area_from=delivery_area_from,
                delivery_from=delivery_from,
                delivery_to=delivery_to,
                delivery_area_to=delivery_area_to,
            ),
            timeout=timeout,
        )

    # ──────────────────────────────────────────────────────────────────────
    # System state / operator controls
    # ──────────────────────────────────────────────────────────────────────

    def get_state(self, *, timeout: float | None = None) -> pb2.SystemState:
        """Runtime health snapshot: uptime, operational flag, subsystem state.

        Requires the `read_state` permission. This is pure runtime health; the
        trading posture (kill switch, limits, license) lives on `get_status`."""
        return self._unary("GetState", pb2.GetStateRequest(), timeout=timeout)

    def get_status(self, *, timeout: float | None = None) -> pb2.SystemStatus:
        """Trading posture, scoped to the caller.

        Open to every authenticated caller, in layers. The base posture
        (`throttling`, `trading_enabled`, `operational`, `license_summary`) and
        the caller's own `accounts` are always set. The desk-wide money and full
        licence — `cash_limits`, `order_pos_limit`, `cash_limit`, `license`,
        `stranded_pending_count`, `stranded_pending_qty`, the four `claims_*`
        gauges and `m7_client_cert` — are set only for a caller holding
        `read_status`; without it the scalar fields are unset (use
        `HasField`), the message fields are unset, and `cash_limits` is empty.

        `accounts` are the accounts the caller may trade for: the House
        (`is_house`) when it holds `trade_global`, plus each assigned active
        member. `position_limit` and `effective_position_limit` are sub-MW, the
        effective one being `min(order_pos_limit, max_position)` for a member; a
        `0` limit or allocation is flat-only. `license_summary` carries only the
        status and expiry an expiry banner needs and the licence `mode`
        (`trader` or `desk`; on `trader` the user, member and permission
        management calls are refused with `LICENSE_DESK_REQUIRED`), not the
        holder or provenance the full `license` has. `order_pos_limit` is sub-MW, `cash_limit` fields
        are cents, and `cash_limits` is M7's raw feed scaled by each row's own
        `dec_shft` (see `get_cash_limits`). `stranded_pending_count` and
        `stranded_pending_qty` (sub-MW) are the headroom held by new orders past
        their expiry bound with no answer from the exchange, where a missed
        report or a late XBID answer cannot be ruled out; they go on consuming
        headroom until their report or refusal, the first order snapshot after
        the bound, or a gateway restart. `claims_count` and `claims_qty`
        (sub-MW) are the amendments and activations whose added exposure counts
        against the limits until the exchange answers them or their expiry
        bound passes; `claims_held_count` and `claims_held_qty` (sub-MW) are
        those held past the bound for the same reasons. The held figures are
        `0` on a healthy gateway. `m7_client_cert` is the exchange client
        certificate's `status_kind` (`valid`, `expiring_soon` from 30 days
        before expiry, `expired`, `not_yet_valid`, `unreadable`), its
        `status_days`, a `status_reason` when unreadable, and `not_after`; the
        exchange refuses the connection under an expired certificate, with no
        grace period."""
        return self._unary("GetStatus", pb2.GetStatusRequest(), timeout=timeout)

    def get_throttling(self, *, timeout: float | None = None) -> pb2.ThrottlingStatus:
        """M7's order load-management status, plus the gateway's own guard.

        Open to every authenticated caller — a base slice of the `get_status`
        snapshot: the order-management budget is shared by the desk's single M7
        login, and it carries counts only, no money or positions. Worth reading
        before a burst. `guard.headroom` is how many further order actions the
        gateway will admit before it starts refusing them, and
        `guard.blocked_reason` says why it is refusing when it is.

        The gateway refuses an order, reprice or activation with
        FAILED_PRECONDITION once the projected count would reach the exchange's
        warning threshold, or while the exchange has the member restricted.
        Cancels are refused only in the second case. Every period on this
        message is in SECONDS.

        `throttling_member_action` and `throttling_user_action` are what the
        gateway asks the exchange, at every login, to do with the book when it
        restricts the member: `HIBE_MBR_ORDERS` and `HIBE_USER_ORDERS` by
        default, which hibernate the orders. A hibernated order is listed with
        state `HIBERNATED`, holds no exposure, and comes back only through an
        activation, which the gateway admits like a new order."""
        return self._unary("GetThrottling", pb2.GetThrottlingRequest(), timeout=timeout)

    def get_system_info(self, *, timeout: float | None = None) -> pb2.SystemInfo:
        """Build and connection info: gateway version, M7 version, request limits.

        `products` carries each product's order bounds, decimal scale and
        user-defined block settings. `block_order_product` says whether the
        product takes blocks and `block_maximum_hours` how much one block may
        group, read both as a count of the product's contracts and as hours (a
        window is refused only when it exceeds both). `dst_block_product` is
        the product's treatment of contracts on the 25-hour clock-change day,
        as published; the gateway checks nothing against it and the exchange
        decides on that day. Each is unset when the
        product publishes no reading of it, and a published maximum of 0 reads
        the same as none: check `HasField` and treat an unset
        setting as no restriction, which is how the gateway itself treats it.

        Authenticated; no permission required."""
        return self._unary("GetSystemInfo", pb2.GetSystemInfoRequest(), timeout=timeout)

    def get_area_table(self, *, timeout: float | None = None) -> pb2.AreaTable:
        """The M7 EIC area reference table, live-name-overlaid.

        `areas` are the delivery / hub-to-hub areas and `market_areas` the market
        areas. Each area carries its EIC, the overlaid `short_name`/`long_name`,
        `area_class`, the EPEX-DA and hub-to-hub flags, its `assigned_products`,
        and `name_source` (`static` or `exchange`). `fill_country` is the whole
        country an area colours on a country-fill map, already folded so a virtual
        or control sub-zone carries its parent country; it is UNSET for a
        border/coupling area, which is a border and fills no country — treat an
        unset `fill_country` as "no country", never as a blank one. `parent_ma_eic`
        is unset for areas the table groups only by name.

        The embedded static table is the always-available floor: before the
        exchange has named any area every entry is its static row with
        `name_source` `static`. Authenticated; no permission required."""
        return self._unary("GetAreaTable", pb2.GetAreaTableRequest(), timeout=timeout)

    def get_contract_limit(
        self, *, timeout: float | None = None
    ) -> pb2.ContractLimitResponse:
        """Current per-contract net position limit, in sub-MW (MW x 1000).

        Requires the `read_status` permission: this exposes the desk-wide money the
        `get_status` snapshot carries only under that permission."""
        return self._unary(
            "GetContractLimit", pb2.GetContractLimitRequest(), timeout=timeout
        )

    def set_contract_limit(
        self, *, quantity: int, timeout: float | None = None
    ) -> pb2.ContractLimitResponse:
        """Set the per-contract net position limit, in SUB-MW (MW x 1000).

        **0 does NOT disable the limit. 0 BLOCKS all new position-taking.**
        The check stays active at zero, so setting this to 0 to "turn the limit
        off" halts the desk. `set_cash_limit(cap_cents=0)` reads the same way:
        zero is a real ceiling, not an off switch.

        Requires the `set_position_limit` permission.
        """
        return self._unary(
            "SetContractLimit",
            pb2.SetContractLimitRequest(quantity=quantity),
            timeout=timeout,
        )

    def get_slot_limit(self, *, timeout: float | None = None) -> pb2.SlotLimitResponse:
        """The slot position limit's mode and the House slot limit.

        The slot limit caps the net MW a desk may hold in one quarter-hour of
        one delivery area, summing every contract that covers that
        quarter-hour: an hour counts its full MW in each of its four
        quarter-hours, and MW is never divided by duration. It works alongside
        the per-contract limit (`get_contract_limit`). `house_limit` is sub-MW
        (MW x 1000, `sub_mw_to_quantity`); `mode` is a `SlotLimitMode`, read
        with `slot_limit_mode_name`. Requires the `read_status` permission."""
        return self._unary("GetSlotLimit", pb2.GetSlotLimitRequest(), timeout=timeout)

    def set_slot_limit(
        self, *, mode: str, house_limit: int, timeout: float | None = None
    ) -> pb2.SlotLimitResponse:
        """Set the slot position limit's mode and the House slot limit.

        `mode` is "off" (never checked), "observe" (every order is admitted,
        and one that "reject" would refuse is written to the audit trail) or
        "reject" (such an order is refused before it reaches the exchange); any
        other string raises `OrderValidationError` locally. `house_limit` is
        SUB-MW (MW x 1000, `quantity_to_sub_mw`) per quarter-hour; 0 is
        flat-only, not off, and a negative value is INVALID_ARGUMENT. Both are
        always set together; the gateway refuses a set that leaves either
        unset. Requires the `set_position_limit` permission."""
        return self._unary(
            "SetSlotLimit",
            build_set_slot_limit_request(mode=mode, house_limit=house_limit),
            timeout=timeout,
        )

    def get_slot_positions(
        self,
        *,
        delivery_area: str,
        from_ms: int,
        to_ms: int,
        v_member_short_id: str | None = None,
        timeout: float | None = None,
    ) -> pb2.SlotPositionsResponse:
        """Per-quarter-hour usage of the slot position limit for one area.

        `from_ms` / `to_ms` are UTC epoch milliseconds, `[from_ms, to_ms)`,
        `from_ms` rounded down to the quarter-hour, `to_ms` at most 48 hours after that
        (INVALID_ARGUMENT beyond). Every quarter-hour holding exposure is
        listed with, per scope, the executed `net`, the reachable `max_long`
        and `max_short` (an open buy never offsets an open sell), the `limit`
        and the `buy_headroom` / `sell_headroom` left, all sub-MW, summed over
        every contract that covers the quarter-hour. The House scope is shown
        only with `read_status`; a member scope only for a member assigned to
        the caller and active, and naming another is PERMISSION_DENIED. The
        figures are there in every mode, "off" included."""
        return self._unary(
            "GetSlotPositions",
            pb2.GetSlotPositionsRequest(
                delivery_area=delivery_area,
                from_ms=from_ms,
                to_ms=to_ms,
                v_member_short_id=v_member_short_id,
            ),
            timeout=timeout,
        )

    def get_cash_limit(self, *, timeout: float | None = None) -> pb2.CashLimitResponse:
        """Both cash pools: the exchange's cash limit for the desk, what the
        exchange still has available, the Voltnir cap, and the effective House
        limit every check uses.

        Each pool carries `ecc_limit_cents` (the exchange's limit, with its
        revision, and the date it takes effect as YYYY-MM-DD in the gateway's
        exposure timezone), `m7_remaining_cents` (what is left before
        the next booking cut), `cap_cents` (the Voltnir cap, unset when there is
        none), and `house_cents` = min(ecc_limit_cents, cap_cents). A limit the
        exchange has not reported counts as zero, so no order may add exposure
        in that pool. `cap_above_ecc` marks a cap the exchange has since dropped
        below; `breached` marks a pool the exchange has suspended.

        `reported_at_ms` is when the exchange last reported the pool, and
        `stale` says the gateway can no longer vouch for those figures: the
        broadcast channel carrying the pool's reports broke since they arrived.
        The exchange broadcasts a cash-limit change only when one happens, so on
        an unbroken channel silence does mean the limit held and a quiet pool is
        not stale; across a break it does not, so the figures count as unknown,
        which is zero, and every order that adds exposure in the pool is refused
        until it is reported again.

        `allocated_cents` is how much of `house_cents` the virtual members hold
        between them, and `unallocated_cents` = house - allocated is what is
        left for orders placed on the House account itself. It can go negative,
        flagged by `over_allocated`, when the exchange lowers its limit under
        allocations already granted: the allocations stand, House orders stop,
        and each member keeps trading inside its own.

        Distinct from get_cash_limits(), which reports the raw per-currency
        feed.

        Requires the `read_status` permission: this exposes the desk-wide money the
        `get_status` snapshot carries only under that permission."""
        return self._unary("GetCashLimit", pb2.GetCashLimitRequest(), timeout=timeout)

    def set_cash_limit(
        self,
        *,
        cap_cents: int | None = None,
        currency: str = "eur",
        timeout: float | None = None,
    ) -> pb2.CashLimitResponse:
        """Set or clear the Voltnir cap on one cash pool, in CENTS.

        The desk's cash limit comes from the exchange. A cap only ever tightens
        it: the limit in force is min(exchange limit, cap). `cap_cents=None`
        removes the cap and lets the exchange's limit bind on its own;
        `cap_cents=0` is a deliberate cap of zero, meaning no trading in that
        pool.

        `currency` is "eur" (default) or "gbp"; the two pools are settled
        separately and never net against each other.

        A cap above the exchange's limit is REJECTED, not clamped, and so is a
        cap set before the exchange has published a limit to tighten — the error
        names the pool and both amounts. A cap that would leave the desk's limit
        below what is already allocated to virtual members is rejected too:
        Voltnir never shrinks an allocation on its own, so lower the members
        first.

        Use `eur_to_cents()` if you are holding a decimal amount.
        Requires the set_cash_limit permission.
        """
        return self._unary(
            "SetCashLimit",
            build_set_cash_limit_request(cap_cents=cap_cents, currency=currency),
            timeout=timeout,
        )

    def get_holidays(self, *, timeout: float | None = None) -> pb2.HolidaysResponse:
        """Both ECC bank-holiday calendars (eur + gbp) for the cash-limit
        exposure window. Authenticated; no permission required."""
        return self._unary("GetHolidays", pb2.GetHolidaysRequest(), timeout=timeout)

    def set_holidays(
        self,
        *,
        currency: str,
        holidays: Sequence[pb2.Holiday],
        timeout: float | None = None,
    ) -> pb2.HolidaysResponse:
        """Replace one currency's whole calendar. `currency` is "eur" or "gbp";
        `holidays` is a sequence of `voltnir_sdk.Holiday` (date "YYYY-MM-DD", label).
        Requires set_cash_limit."""
        return self._unary(
            "SetHolidays",
            pb2.SetHolidaysRequest(currency=currency, holidays=list(holidays)),
            timeout=timeout,
        )

    def add_holiday(
        self, *, currency: str, date: str, label: str = "", timeout: float | None = None
    ) -> pb2.HolidaysResponse:
        """Add one date to a currency's calendar. Requires set_cash_limit."""
        return self._unary(
            "AddHoliday",
            pb2.AddHolidayRequest(currency=currency, date=date, label=label),
            timeout=timeout,
        )

    def remove_holiday(
        self, *, currency: str, date: str, timeout: float | None = None
    ) -> pb2.HolidaysResponse:
        """Remove one date from a currency's calendar. Requires set_cash_limit;
        NOT_FOUND when the date is not configured."""
        return self._unary(
            "RemoveHoliday",
            pb2.RemoveHolidayRequest(currency=currency, date=date),
            timeout=timeout,
        )

    def get_trading_allowed(
        self, *, timeout: float | None = None
    ) -> pb2.TradingAllowedResponse:
        """Whether trading is currently enabled (the kill switch).

        Open to every authenticated caller — the `trading_enabled` base slice of
        the `get_status` snapshot, which a trader needs to know whether it may
        submit at all. `set_trading_allowed` performs the write and is gated on
        `toggle_trading` instead."""
        return self._unary(
            "GetTradingAllowed",
            pb2.GetTradingAllowedRequest(),
            timeout=timeout,
        )

    def set_trading_allowed(
        self, *, allowed: bool, timeout: float | None = None
    ) -> pb2.TradingAllowedResponse:
        """The trading kill switch. `False` halts ALL new trading firm-wide.

        Disabling also asks the exchange to flatten the account. The flag is off
        whether or not that cancel was confirmed, so check `flatten` on the
        response: it is set only when disabling, and `flatten.ok` is true only
        when the exchange acknowledged the cancel. That acknowledgement is the
        exchange's receipt of the command, not proof the book is already empty;
        resulting order state converges on the order stream. A false `ok`
        carries the reason in `flatten.error` and means resting orders may still
        be live. Both the enqueue and the receipt wait are bounded by the
        gateway's ack window, so this call answers even with the exchange
        connection down. Requires the `toggle_trading` permission.
        """
        return self._unary(
            "SetTradingAllowed",
            pb2.SetTradingAllowedRequest(allowed=allowed),
            timeout=timeout,
        )

    def ack_trade_ingest_fault(
        self, reason: str, *, timeout: float | None = None
    ) -> pb2.AckTradeIngestFaultResponse:
        """Acknowledge a raised `trade_report refused` fault, reopening order admission.

        While the gateway holds a trade report it could not read, a trade the
        exchange executed is missing from its count: position, cash and P&L
        figures are understated, and under the default `trade_ingest_fault:
        close` policy new orders and modifies are refused. This reopens them for
        the gateway's acknowledgement TTL (`ttl_sec` on the response, 1800 s by
        default), and state and status read `admission == "degraded"` meanwhile.
        The exchange still checks the member's cash limit on every order; the
        gateway's own limits are measured on the understated figures, which is
        the risk the desk takes on. The acknowledgement ends early when the
        fault clears, a repeat call restarts the TTL (`renewed` is true), and a
        gateway restart drops it. While it holds, the gateway does not reconnect
        its exchange session over the fault; another order-critical issue
        closes admission as usual, and the TTL keeps running while it does.
        `reason` is recorded in the audit trail.

        Requires the `toggle_trading` permission. Raises `Aborted` when no fault
        is raised, or when the private consumer or the private-data stream is
        down (no trade report could arrive), and `InvalidArgument` when `reason`
        is empty or blank.
        """
        return self._unary(
            "AckTradeIngestFault",
            pb2.AckTradeIngestFaultRequest(reason=reason),
            timeout=timeout,
        )

    def get_self_trade_policy(
        self, *, timeout: float | None = None
    ) -> pb2.SelfTradePolicyResponse:
        """Current self-trade prevention policy: OBSERVE or REJECT.

        Authenticated; no permission required. Compare against
        `SelfTradePolicy`; `set_self_trade_policy` performs the write."""
        return self._unary(
            "GetSelfTradePolicy",
            pb2.GetSelfTradePolicyRequest(),
            timeout=timeout,
        )

    def set_self_trade_policy(
        self, *, policy: str, timeout: float | None = None
    ) -> pb2.SelfTradePolicyResponse:
        """Set self-trade prevention: "observe" or "reject".

        Requires the `set_self_trade_policy` permission. Any other string raises
        `OrderValidationError` locally, before anything is sent."""
        return self._unary(
            "SetSelfTradePolicy",
            build_set_self_trade_policy_request(policy=policy),
            timeout=timeout,
        )

    def restart(self, *, timeout: float | None = None) -> pb2.RestartResponse:
        """Restart the gateway. Every live stream a desk is consuming DROPS.

        There is no confirmation step and no undo. Consumers must resubscribe;
        anything mid-flight is subject to the same ambiguity as any other
        interrupted call. Requires the `restart_system` permission.
        """
        return self._unary("Restart", pb2.RestartRequest(), timeout=timeout)

    def restore_trade_history(
        self, *, days: int | None = None, timeout: float | None = None
    ) -> pb2.RestoreTradeHistoryResponse:
        """Backfill the persistent trade store from the exchange's history.

        Requires the `restore_trade_history` permission. Asks the exchange to
        resend the trade capture reports it still serves and persists them,
        isolated from the cash-exposure coverage gate.

        `days` bounds how far back to reach. Omit it (`None`) to restore the
        exchange's whole reach; a value beyond what the exchange retains is
        clamped to it. The distinction between omitted and `0` is deliberate and
        preserved on the wire: `None` restores everything, `0` is an empty
        no-op window. Read `effective_days` / `effective_from_ms` to see what
        the request resolved to after clamping.

        Delivery is asynchronous and paced, so the response returns before the
        history has landed: `chunk_count` is how many request chunks the window
        tiled into (0 for an empty window). Watch the `SystemState`
        `trades_received` / `trades_persisted` counters for progress.
        """
        request = pb2.RestoreTradeHistoryRequest()
        if days is not None:
            request.days = days
        return self._unary("RestoreTradeHistory", request, timeout=timeout)

    # ──────────────────────────────────────────────────────────────────────
    # Cash limits / PnL / Public trades
    # ──────────────────────────────────────────────────────────────────────

    def get_cash_limits(
        self, *, timeout: float | None = None
    ) -> pb2.GetCashLimitsResponse:
        """M7's per-currency cash/margin feed. NOT cents, and NOT a fixed scale.

        Each `CashLimit` row carries its own `dec_shft`, and the real amount is
        `raw / 10 ** dec_shft`. Do not use `cents_to_eur` here:

            for lim in client.get_cash_limits().limits:
                amount = Decimal(lim.current_limit) / (Decimal(10) ** (lim.dec_shft or 0))

        Distinct from `get_cash_limit()` (singular), which is Voltnir's own
        configured limit and IS in cents. `SystemStatus` carries both as
        adjacent fields, `cash_limit` and `cash_limits`, whose scales differ by
        an arbitrary power of ten.

        Requires the `read_status` permission: this exposes the desk-wide money the
        `get_status` snapshot carries only under that permission.
        """
        return self._unary("GetCashLimits", pb2.GetCashLimitsRequest(), timeout=timeout)

    def list_permissions(
        self, *, timeout: float | None = None
    ) -> pb2.ListPermissionsResponse:
        """Catalog of assignable permissions, each with a code and a
        human-readable description. Requires the manage_users permission."""
        return self._unary(
            "ListPermissions", pb2.ListPermissionsRequest(), timeout=timeout
        )

    def get_pnl(
        self, *, v_member_short_id: str = "", timeout: float | None = None
    ) -> pb2.PnlSnapshot:
        """Derived P&L. Note that this message mixes THREE unit scales.

        - `realized_pnl` / `unrealized_pnl`: q8, meaning the row's `currency`
          (EUR or GBP) x 100_000. Use `q8_to_eur`, which applies the scale
          whatever the currency. Reading these as cents overstates by 1000x.
        - `signed_position`: sub-MW (MW x 1000), + long / - short.
        - `avg_open_px` / `mark_px`: cents (CCY/MWh x 100).

        **Never add money across currencies.** Every row carries its
        `currency`, set by its delivery area; `totals` holds one realized and
        unrealized figure per currency, summed by the gateway. A trade whose
        delivery duration is not yet known is left out and counted in
        `unpriced_trades`. Contract rows carry their local `delivery_day`
        (YYYY-MM-DD, `""` when unknown). The README's units section covers the
        energy scaling.

        **Member-scoped by default:** without `read_pnl` /
        `bypass_member_check` the result covers only the virtual members
        assigned to the caller, silently. A desk that believes it is seeing the
        firm's whole book while seeing one member's slice will under-hedge, and
        no exception is raised. `v_member_short_id` narrows to one member.
        """
        return self._unary(
            "GetPnl",
            pb2.GetPnlRequest(v_member_short_id=v_member_short_id),
            timeout=timeout,
        )

    def list_public_trades(
        self,
        *,
        limit: int = 0,
        contract_id: int = 0,
        area_id: str = "",
        timeout: float | None = None,
    ) -> pb2.ListPublicTradesResponse:
        """Recent public trade tape for an area or contract.

        Authenticated; no permission required. `limit` 0 means the server
        default (100), capped at 1000. Units: `px` is cents, `qty` is sub-MW.
        Use this to seed history before subscribing with
        `watch_public_trades`, which sends no snapshot."""
        return self._unary(
            "ListPublicTrades",
            pb2.ListPublicTradesRequest(
                limit=limit,
                contract_id=contract_id,
                area_id=area_id,
            ),
            timeout=timeout,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Users / members
    # ──────────────────────────────────────────────────────────────────────

    def get_me(self, *, timeout: float | None = None) -> pb2.UserProfile:
        """The caller's own user record: id, username, and granted permissions.

        Authenticated; no permission required. Useful as a connectivity and
        credential smoke test, and to discover which of the permission-gated
        calls below will work for this key."""
        return self._unary("GetMe", pb2.GetMeRequest(), timeout=timeout)

    def get_my_members(self, *, timeout: float | None = None) -> pb2.MemberListResponse:
        """Virtual members assigned to the caller.

        Authenticated; no permission required. These are the members whose
        orders and P&L you see by default: several read paths are silently
        member-scoped to this set unless you hold that path's broad read
        (`read_orders` for orders, `read_pnl` for P&L) or
        `bypass_member_check`."""
        return self._unary("GetMyMembers", pb2.GetMyMembersRequest(), timeout=timeout)

    def list_users(self, *, timeout: float | None = None) -> pb2.ListUsersResponse:
        """All users and their permissions.

        Requires the `manage_users` permission and the desk-management license
        (see `VoltnirClient`)."""
        return self._unary("ListUsers", pb2.ListUsersRequest(), timeout=timeout)

    def create_user(
        self,
        *,
        username: str,
        permissions: Sequence[str] = (),
        timeout: float | None = None,
    ) -> pb2.CreateUserResponse:
        """Create a user. `permissions` is optional (matches the proto and
        the documented call shape); empty means no permissions granted.

        Requires the `manage_users` permission and the desk-management license
        (see `VoltnirClient`)."""
        return self._unary(
            "CreateUser",
            pb2.CreateUserRequest(username=username, permissions=list(permissions)),
            timeout=timeout,
        )

    def delete_user(self, *, user_id: str, timeout: float | None = None) -> pb2.Empty:
        """Delete a user by id. Their API key stops working immediately.

        Requires the `manage_users` permission and the desk-management license
        (see `VoltnirClient`). There is no undo. The deleted user's username
        and short id are never given to another user, so a create naming that
        username raises `Aborted`; restoring access means creating a user
        under a new username, which issues a new key."""
        return self._unary(
            "DeleteUser",
            pb2.DeleteUserRequest(user_id=user_id),
            timeout=timeout,
        )

    def set_permissions(
        self, *, user_id: str, permissions: Sequence[str], timeout: float | None = None
    ) -> pb2.Empty:
        """Replace a user's permissions with exactly this list.

        Requires the `manage_users` permission and the desk-management license
        (see `VoltnirClient`). This is replace-all, not a merge: any permission
        omitted is REVOKED. Read the current set with `list_users` first, and
        see `list_permissions` for the assignable catalog."""
        return self._unary(
            "SetPermissions",
            pb2.SetPermissionsRequest(user_id=user_id, permissions=list(permissions)),
            timeout=timeout,
        )

    def rotate_api_key(
        self, *, user_id: str, timeout: float | None = None
    ) -> pb2.RotateApiKeyResponse:
        """Issue a new API key for a user and invalidate the old one.

        Requires the `manage_users` permission. The new key is returned ONCE in
        the response and is not retrievable afterwards. Any client still using
        the old key begins failing with `Unauthenticated` immediately.

        Open under a trader license too, where a caller may rotate only its
        own key: any other `user_id` raises `NotFound`, the same answer as an
        unknown id, so the call never reveals whether a user exists."""
        return self._unary(
            "RotateApiKey",
            pb2.RotateApiKeyRequest(user_id=user_id),
            timeout=timeout,
        )

    def get_user_members(
        self, *, user_id: str, timeout: float | None = None
    ) -> pb2.UserMembersResponse:
        """The members a user is assigned to.

        Returns `UserMembersResponse.member_ids`: member UUIDs (`Member.id`),
        not VM-style short ids. Requires the `manage_users` permission and the
        desk-management license (see `VoltnirClient`)."""
        return self._unary(
            "GetUserMembers",
            pb2.GetUserMembersRequest(user_id=user_id),
            timeout=timeout,
        )

    def set_user_members(
        self, *, user_id: str, member_ids: Sequence[str], timeout: float | None = None
    ) -> pb2.Empty:
        """Replace a user's member assignment with exactly this list.

        Replace-all, not a merge. `member_ids` are member UUIDs (`Member.id`),
        not VM-style short ids. Requires the `manage_users` permission and the
        desk-management license (see `VoltnirClient`)."""
        return self._unary(
            "SetUserMembers",
            pb2.SetUserMembersRequest(
                user_id=user_id, member_ids=list(member_ids)
            ),
            timeout=timeout,
        )

    def list_members(self, *, timeout: float | None = None) -> pb2.MemberListResponse:
        """All virtual members, with their limits and live cash usage.

        Requires the `manage_members` permission and the desk-management
        license (see `VoltnirClient`). Units: `max_position` and
        `max_slot_position` (unset = no member slot limit) are sub-MW; every
        `*_cents` field is cents. `cash_limit` is the member's allocation out
        of the desk's cash limit, and `eur_limit_cents` is that same number as
        the enforced limit; 0 means no allocation, so the member cannot add
        exposure in that pool."""
        return self._unary("ListMembers", pb2.ListMembersRequest(), timeout=timeout)

    def create_member(
        self,
        *,
        name: str,
        max_position: int,
        cash_limit: int = 0,
        cash_limit_gbp: int = 0,
        max_slot_position: int | None = None,
        delivery_areas: pb2.DeliveryAreaScope | None = None,
        timeout: float | None = None,
    ) -> pb2.Member:
        """Create a virtual member. The VM-style `short_id` is generated
        server-side and returned in the `Member` response. Requires the
        `manage_members` permission and the desk-management license (see
        `VoltnirClient`).

        `cash_limit` (EUR cents) and `cash_limit_gbp` (GBP cents) are the
        member's ALLOCATIONS out of the desk's cash limit, not overrides of it.
        Per currency the allocations of all members sum to at most the desk's
        limit, so a member can only ever spend its own slice — one member can
        never consume another's. 0 means no allocation: the member cannot add
        exposure in that pool at all.

        INVALID_ARGUMENT when an allocation would push the pool past the desk's
        limit (the error names the pool, the amount available, and what is
        already allocated) or when the exchange has reported no limit for the
        pool to allocate out of.

        `max_slot_position` is the member's own slot position limit: the net
        MW its own orders and trades may reach in one quarter-hour of one
        delivery area, summing every contract that covers the quarter-hour, in
        SUB-MW. `None` (the default) is no member slot limit, which is not the
        same as 0: 0 is flat-only. It is separate from `max_position`, the
        per-contract limit, and a member order is held to the House slot limit
        as well.

        `delivery_areas` is the set of delivery areas the member may trade in,
        a `voltnir_sdk.DeliveryAreaScope`: `DeliveryAreaScope(all=True)` for
        every area, including one the gateway is configured for later, or
        `DeliveryAreaScope(area_ids=[...])` for a list of EIC codes the gateway
        is configured to trade. `None` (the default) creates the member with
        no areas: it can place no order until it is given some. Every order
        action of the member's outside its areas (new, modify, activate,
        deactivate, cancel) is refused `FailedPrecondition` with
        `MEMBER_AREA_NOT_ALLOWED` before it reaches the exchange.
        INVALID_ARGUMENT for an area the gateway does not trade, or for
        `all=True` together with `area_ids`."""
        return self._unary(
            "CreateMember",
            pb2.CreateMemberRequest(
                name=name, max_position=max_position,
                cash_limit=cash_limit, cash_limit_gbp=cash_limit_gbp,
                max_slot_position=max_slot_position,
                delivery_areas=delivery_areas,
            ),
            timeout=timeout,
        )

    def patch_member(
        self,
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
        timeout: float | None = None,
    ) -> pb2.Empty:
        """Update a member. Only the fields you pass are sent, and applied.

        Requires the `manage_members` permission and the desk-management
        license (see `VoltnirClient`).

        Genuinely a patch, unlike `modify_order`: an omitted field is left
        untouched server-side. Passing 0 for a cash limit takes the member's
        ALLOCATION away, so it can no longer add exposure in that pool; that
        always succeeds. Raising one is INVALID_ARGUMENT when the pool's
        allocations would then exceed the desk's limit.

        `id` is the member UUID (`Member.id`), not the VM-style `short_id`.
        Plain Python values are accepted; the wire's wrapper types are handled
        for you. `max_slot_position` (sub-MW) sets the member's slot limit and
        `clear_max_slot_position=True` removes it; passing both raises
        `OrderValidationError` locally.

        `delivery_areas` replaces the member's delivery areas whole (see
        `create_member`); `None` leaves them. INVALID_ARGUMENT, and nothing
        changes, when it would leave any of the member's resting or pending
        orders in an area outside it: cancel those orders first.
        """
        return self._unary(
            "PatchMember",
            build_patch_member_request(
                id=id,
                name=name,
                max_position=max_position,
                active=active,
                cash_limit_cents=cash_limit_cents,
                cash_limit_gbp_cents=cash_limit_gbp_cents,
                max_slot_position=max_slot_position,
                clear_max_slot_position=clear_max_slot_position,
                delivery_areas=delivery_areas,
            ),
            timeout=timeout,
        )

    def delete_member(self, *, member_id: str, timeout: float | None = None) -> pb2.Empty:
        """Delete a member by id (`Member.id`, not the VM-style `short_id`).

        Requires the `manage_members` permission and the desk-management
        license (see `VoltnirClient`). Raises `InvalidArgument`, and nothing
        changes, while the member has a resting or unconfirmed pending order,
        a non-zero executed position on a contract whose delivery has not
        ended, or consumed cash still counted in the current exposure window;
        the message names the order count, each such contract and its
        delivery area, or the consumed cash per pool in cents. Cancel the
        orders, flatten the positions, and delete after the next booking cut
        (16:00 on an ECC business day): the member's allocation is released
        with the delete, while cash it consumed keeps counting against the
        desk's limit until the cut. Any non-zero figure holds it, a credit
        included (named "EUR credit 4000 cents"). It also raises
        `InvalidArgument` while the gateway's cash sums cannot be fully
        priced, since the figure would then be short; retry.

        A deleted member takes no order, is unassigned from every user and
        leaves `list_members`; its orders and trades keep its name, and its
        `short_id` is never given to another member. There is no undo; a
        second delete, like any write on its id, raises `NotFound`."""
        return self._unary(
            "DeleteMember",
            pb2.DeleteMemberRequest(member_id=member_id),
            timeout=timeout,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Audit
    # ──────────────────────────────────────────────────────────────────────

    def query_audit_orders(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        area: str | None = None,
        product: str | None = None,
        status: str | None = None,
        user_code: str | None = None,
        v_member_short_id: str | None = None,
        voltnir_user_short_id: str | None = None,
        voltnir_username: str | None = None,
        sort_order: str | None = None,
        timeout: float | None = None,
    ) -> pb2.AuditOrdersResponse:
        """Query the historical order audit log.

        Needs no permission: member-scoped like `list_orders`, and
        `read_orders` / `bypass_member_check` widens it to the whole desk.
        `limit` 0 → 50, capped 200. Filter by `date_from` / `date_to`, `area`, `product`,
        `status`, `user_code`, `v_member_short_id`, `voltnir_user_short_id` and
        `voltnir_username`. Paginate with `next_cursor` from the response.

        `status` is the order state the exchange reported: `"ACTIVE"`
        (`"ACTI"`), `"INACTIVE"` (`"INAC"`) or `"HIBERNATED"` (`"HIB"`), in
        any case; unset or `""` means no filter, and any other value is
        `INVALID_ARGUMENT`. `"REJECTED"` is not an M7 order state: a plain
        order the exchange refuses has no row here, and its refusal is on the
        audit trail as `order_rejected`.

        `sort_order` sets the page direction for every audit query below:
        unset or `"DESC"` walks newest-first, `"ASC"` oldest-first, and any
        other value is `INVALID_ARGUMENT`. Newest-first is the default
        because a store holding months of history answers an oldest-first
        first page with rows so old they read as missing data."""
        return self._unary(
            "QueryAuditOrders",
            _kwargs_request(pb2.AuditOrdersRequest, locals()),
            timeout=timeout,
        )

    def query_audit_trades(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        area: str | None = None,
        product: str | None = None,
        user_code: str | None = None,
        v_member_short_id: str | None = None,
        time_basis: str | None = None,
        voltnir_user_short_id: str | None = None,
        voltnir_username: str | None = None,
        sort_order: str | None = None,
        contract_id: str | None = None,
        timeout: float | None = None,
    ) -> pb2.AuditTradesResponse:
        """Query the historical trade audit log.

        Needs no permission; member-scoped, and `read_orders` /
        `bypass_member_check` widens it to the whole desk. `limit`,
        `date_from` / `date_to`, `sort_order` and pagination match
        `query_audit_orders`. `time_basis`
        picks which timestamp `date_from` / `date_to` filter on: `""` /
        `"delivery"` is the contract delivery window (the default), `"execution"`
        is execution time; any other value is `INVALID_ARGUMENT`. `contract_id`
        filters to one contract by its M7 contract id, as the string the trade
        rows carry; an id no trade carries returns an empty page, not an error,
        and `None` or `""` is no filter. Units on the returned rows are wire
        units."""
        return self._unary(
            "QueryAuditTrades",
            _kwargs_request(pb2.AuditTradesRequest, locals()),
            timeout=timeout,
        )

    def query_audit_public_trades(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        area: str | None = None,
        product: str | None = None,
        state: str | None = None,
        sort_order: str | None = None,
        timeout: float | None = None,
    ) -> pb2.AuditPublicTradesResponse:
        """Query the historical public-trade audit log.

        Requires the `read_audit` permission. `limit`, `date_from` / `date_to`,
        `area`, `product`, `sort_order` and pagination match
        `query_audit_orders`; `state` filters on the trade state."""
        return self._unary(
            "QueryAuditPublicTrades",
            _kwargs_request(pb2.AuditPublicTradesRequest, locals()),
            timeout=timeout,
        )

    def query_audit_events(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        action: str | None = None,
        target_type: str | None = None,
        actor_short_id: str | None = None,
        outcome: str | None = None,
        sort_order: str | None = None,
        v_member_short_id: str | None = None,
        timeout: float | None = None,
    ) -> pb2.AuditEventsResponse:
        """Query the compliance audit-event log. Requires `read_audit`.
        `limit` 0 → 50, capped 200. Filter by `date_from` / `date_to`,
        `action`, `target_type`, `actor_short_id` and `outcome`; `sort_order`
        as on `query_audit_orders`.

        Member-scoped like `query_audit_orders`: `read_orders` /
        `bypass_member_check` reads the whole trail; without either you get
        only the order rows of your assigned members, each row naming its
        member in `v_member_short_id`, and no row that names no member.
        `v_member_short_id` narrows to one member and raises
        `PermissionDenied` for a member outside your scope."""
        return self._unary(
            "QueryAuditEvents",
            _kwargs_request(pb2.AuditEventsRequest, locals()),
            timeout=timeout,
        )

    # ──────────────────────────────────────────────────────────────────────
    # M7 errors
    # ──────────────────────────────────────────────────────────────────────

    def query_m7_errors(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        kind: str | None = None,
        category: str | None = None,
        err_code: int | None = None,
        sort_order: str | None = None,
        timeout: float | None = None,
    ) -> pb2.M7ErrorsResponse:
        """Query the persisted M7 exchange-error log. Requires `read_m7_errors`
        (a dedicated gate, not `read_audit`). `limit` 0 → 50, capped 200. Filter
        by `date_from` / `date_to`, `kind`, `category` and `err_code` (0 →
        unset); `sort_order` as on `query_audit_orders`."""
        return self._unary(
            "QueryM7Errors",
            _kwargs_request(pb2.M7ErrorsRequest, locals()),
            timeout=timeout,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Exchange messages
    # ──────────────────────────────────────────────────────────────────────

    def list_exchange_messages(
        self,
        *,
        cursor: str | None = None,
        limit: int | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        severity: str | None = None,
        scope: str | None = None,
        code: int | None = None,
        sort_order: str | None = None,
        timeout: float | None = None,
    ) -> pb2.ListExchangeMessagesResponse:
        """Query the exchange-message log: the append-only record of what the
        exchange said — cash-limit breaches, market and delivery-area halts,
        member suspensions, failover notices, automated order transfers. The
        companion to `query_m7_errors`, which records what went wrong instead.
        Requires the `read_m7_errors` permission, as that does.

        Filter fields: `cursor`, `limit` (0 → 50, capped 200), `date_from`,
        `date_to`, `severity` (`urgent` / `error` / `high` / `medium` / `low` /
        `unknown`), `scope` (`public` / `private`), `code` (0 → unset), `sort_order` as on `query_audit_orders`.

        Each `item.json` carries the row as JSON: `msg_id` (the exchange's own
        identifier and the de-duplication key), `code`, `key` (the catalogue
        name for that code, or null), `severity`, `text` with its placeholders
        already substituted, and the raw `vars`. Messages the exchange marks
        non-persistent are streamed by `watch_exchange_messages()` and never
        stored, so they never appear here."""
        return self._unary(
            "ListExchangeMessages",
            _kwargs_request(pb2.ListExchangeMessagesRequest, locals()),
            timeout=timeout,
        )


    # ──────────────────────────────────────────────────────────────────────
    # System log
    # ──────────────────────────────────────────────────────────────────────

    def list_system_log(
        self,
        *,
        cursor: int | None = None,
        limit: int | None = None,
        min_level: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        timeout: float | None = None,
    ) -> pb2.ListSystemLogResponse:
        """Read the gateway's own diagnostic log. Requires `read_logs`.

        This is the gateway's internal `tracing` output, not the exchange's
        messages (`list_exchange_messages`) and not the compliance trail
        (`query_audit_events`). It carries file paths, database errors and
        module names, which is why it has its own permission rather than
        sharing `read_m7_errors`.

        **Not an audit record.** The buffer is a bounded in-memory ring: it is
        capped by entry count first and age second, lives only in the running
        process, is lost on every restart, and drops the oldest entries under
        load. Anything that must survive an incident belongs in the audit log.

        Filter fields: `cursor` (omit for the newest page; set it — 0 included
        — to resume from that `seq`), `limit` (0 → 50, capped 200), `min_level`
        (`error` / `warn` / `info` / `debug`; "" → unset), `date_from`,
        `date_to`.

        Each `item.json` carries one entry: `seq` (the cursor), `ts_ms`,
        `level`, `target` (the emitting module) and `message`, truncated at
        4 KiB with a visible marker.

        `cursor` and `next_cursor` carry proto3 field presence: check
        `response.HasField("next_cursor")` to page (absent means no more), since
        `seq` 0 is a real entry, not an "unset" sentinel — do not test the
        integer for truthiness.

        Read `response.buffer` before presenting the result. `dropped` counts
        entries already evicted, `started_at_ms` is as far back as the buffer
        reaches, and `has_entries` says whether the `seq` and timestamp fields
        mean anything — proto3 cannot tell an unset integer from 0, and `seq`
        0 is a real entry. `response.truncated` says the `cursor` you passed
        had already been evicted, so this page resumes from the oldest
        surviving entry rather than from where you left off."""
        return self._unary(
            "ListSystemLog",
            _kwargs_request(pb2.ListSystemLogRequest, locals()),
            timeout=timeout,
        )
    # ──────────────────────────────────────────────────────────────────────
    # Report exports (over the gateway's REST API)
    # ──────────────────────────────────────────────────────────────────────

    def export_orders(
        self,
        *,
        format: Literal["json", "csv"],
        from_: str,
        to: str,
        area: str | None = None,
        product: str | None = None,
        status: str | None = None,
        user_code: str | None = None,
        v_member_short_id: str | None = None,
        voltnir_user_short_id: str | None = None,
        voltnir_username: str | None = None,
        timeout: float | None = None,
    ) -> Iterator[bytes]:
        """Export the order history of a window as a file, streamed as bytes.

        Requires the `export_reports` permission. The rows are the ones
        `query_audit_orders` would serve the caller for the same window and
        filters: its own members' unless `read_orders` or
        `bypass_member_check` widens them to the whole desk.

        `format` is `"json"` or `"csv"`. `from_` and `to` are RFC 3339
        timestamps, both inclusive (`from_` because `from` is a Python
        keyword). `area`, `product`, `status`, `user_code`,
        `v_member_short_id`, `voltnir_user_short_id` and `voltnir_username`
        narrow the rows as they narrow `query_audit_orders`, each an exact
        match; `None` or `""` is no filter. `status` takes the order states
        `query_audit_orders` lists, and any other value raises
        `InvalidArgument`; a `v_member_short_id` outside the caller's member
        scope raises `PermissionDenied`, as the history read refuses it. The
        gateway checks the request and answers a bad value with
        `InvalidArgument` in its own words, before any export starts.
        One export covers at most 31 days plus one hour (745 hours between
        `from_` and `to`, counted in the hours that pass, so a whole calendar
        month fits even in local time across the October clock change); a
        wider window raises `InvalidArgument` with "export range exceeds 31
        days". The gateway
        builds one export at a time for all its users: a request made while
        another is generating raises `ExportBusy` at once, and nothing is
        queued.

        Exports go over the gateway's REST API, so the client needs
        `rest_url`; without it this raises `ValueError` before anything is
        sent. The gateway builds the file in the background: the SDK requests
        it, polls until it is ready (0.25 s apart at first, backing off to
        2 s), then yields the file in chunks of up to 64 KiB as they arrive.
        Write each chunk in order rather than collecting them all.

        Nothing is sent until the first iteration. `timeout` bounds the whole
        export from then on, request, polling and download included, and
        raises `DeadlineExceeded`: each socket read is cut to what is left of
        it, and a chunk is handed over as soon as bytes arrive, so a slow
        trickle cannot outlast it. Without it the export takes as long as the
        gateway needs, but a read that receives nothing for 30 s still raises
        `DeadlineExceeded`.

        The gateway's refusal text is the exception's `message`: `400`
        raises `InvalidArgument`, `401` `Unauthenticated`, `403`
        `PermissionDenied`, `404` `NotFound`, `409` (another export is
        generating) `ExportBusy`, `429` (the per-key request bound)
        `ResourceExhausted`, a failed export (`500`) `Internal`, and any
        other status the base `VoltnirError` naming it. A redirect is never
        followed, because the request carries the API key; it raises
        `VoltnirError` naming the status. A connection failure, or a download
        that ends short of the size the gateway stated, raises `Unavailable`.
        """
        body = _rest_export.request_body(
            format,
            from_,
            to,
            area=area,
            product=product,
            status=status,
            user_code=user_code,
            v_member_short_id=v_member_short_id,
            voltnir_user_short_id=voltnir_user_short_id,
            voltnir_username=voltnir_username,
        )
        return self._export("orders", body, timeout)

    def export_trades(
        self,
        *,
        format: Literal["json", "csv"],
        from_: str,
        to: str,
        area: str | None = None,
        product: str | None = None,
        user_code: str | None = None,
        v_member_short_id: str | None = None,
        time_basis: str | None = None,
        voltnir_user_short_id: str | None = None,
        voltnir_username: str | None = None,
        timeout: float | None = None,
    ) -> Iterator[bytes]:
        """Export the trade history of a window as a file, streamed as bytes.

        Requires the `export_reports` permission. Parameters, transport and
        errors match `export_orders`, less `status` (a trade carries no order
        state) and plus `time_basis`; the rows are the ones
        `query_audit_trades` would serve for the same window and filters.

        `time_basis` picks which time `from_` and `to` bound, in any case:
        `"delivery"` (the default, also `None` or `""`) keeps a trade whose
        delivery period overlaps the window, `"execution"` one executed
        inside it. Any other value raises `InvalidArgument`. A trade recorded
        without its delivery period matches only `"execution"`."""
        body = _rest_export.request_body(
            format,
            from_,
            to,
            area=area,
            product=product,
            user_code=user_code,
            v_member_short_id=v_member_short_id,
            time_basis=time_basis,
            voltnir_user_short_id=voltnir_user_short_id,
            voltnir_username=voltnir_username,
        )
        return self._export("trades", body, timeout)

    def export_audit(
        self,
        *,
        format: Literal["json", "csv"],
        from_: str,
        to: str,
        action: str | None = None,
        target_type: str | None = None,
        actor_short_id: str | None = None,
        outcome: str | None = None,
        v_member_short_id: str | None = None,
        timeout: float | None = None,
    ) -> Iterator[bytes]:
        """Export the compliance audit trail of a window as a file, streamed as bytes.

        Requires the `export_reports` permission and also `read_audit`: a
        bulk extract of the trail takes both, and a caller missing either is
        refused with `PermissionDenied`. The rows are the ones
        `query_audit_events` serves the same caller for the same window and
        filters, oldest first, so the file is member-scoped as that read is.
        `action`, `target_type`, `actor_short_id`, `outcome` and
        `v_member_short_id` filter as they do there, each an exact match, so a
        value no row carries gives an empty file rather than an error, and a
        `v_member_short_id` outside your scope raises `PermissionDenied`. A `before` or
        `after` snapshot is a JSON value in a JSON file and its JSON text in
        one CSV cell. The window, `format`, the cap of 31 days plus one hour,
        the one export at a time, transport, `timeout` and errors match
        `export_orders`."""
        body = _rest_export.request_body(
            format,
            from_,
            to,
            action=action,
            target_type=target_type,
            actor_short_id=actor_short_id,
            outcome=outcome,
            v_member_short_id=v_member_short_id,
        )
        return self._export("events", body, timeout, op="export_audit")

    def _export(
        self, kind: str, body: dict[str, str], timeout: float | None, op: str | None = None
    ) -> Iterator[bytes]:
        op = op or f"export_{kind}"
        if self._closed:
            raise ClientClosed(op)
        endpoint = _rest_export.require(self._rest, op)
        return _rest_export.export(endpoint, kind, body, timeout, op)

    # ──────────────────────────────────────────────────────────────────────
    # Streaming RPCs
    # ──────────────────────────────────────────────────────────────────────

    def watch_contracts(
        self,
        *,
        areas: Sequence[str],
        products: Sequence[str] | None = None,
        contract_ids: Sequence[int] | None = None,
        timeout: float | None = None,
    ) -> Iterator[pb2.ContractsEvent]:
        """Watch contracts live: the one contract stream, for one contract or
        a whole product. The same stream, with the same filter, as the
        WebSocket `contracts` stream.

        A contract is included when its area is in `areas`, and then:

        - with no `contract_ids`, when its product is in `products`;
        - with `contract_ids`, when its id is one of them and, if `products` is
          given, when its product is in `products` as well.

        An empty `areas` matches nothing, and so does no `products` without
        `contract_ids`: the stream opens on an empty SNAPSHOT, which is not an
        error. An id that names no contract is absent from the SNAPSHOT, also
        not an error. Contract ids are integers here, while `ContractSummary`
        carries them as text. To follow one contract::

            client.watch_contracts(areas=[s.area_id], contract_ids=[int(s.contract_id)])

        The first event is a SNAPSHOT (`ContractsEventType.SNAPSHOT`) carrying
        every matching contract that is live with a known delivery period.
        Then each UPSERT carries exactly one contract, its complete current
        book, at most once per contract per 100 ms: a client that keeps up
        sees every change, coalesced, never an older book. A DELETE names a
        contract that left the market in `area_id` / `contract_id` and carries
        no contract; the stream stays open. Trades are not on this stream: use
        `watch_trades` and `watch_public_trades`.

        **Replace your whole view on every SNAPSHOT.** A client that falls
        behind receives one fresh SNAPSHOT, however much it missed; a contract
        missing from it has left the market.

        `timeout` is an overall gRPC deadline in seconds; when it fires, the
        iterator raises `DeadlineExceeded`. `None` (default) streams until
        cancelled.
        """
        return self._stream(
            "WatchContracts",
            pb2.WatchContractsRequest(
                areas=areas, products=products or (), contract_ids=contract_ids or ()
            ),
            timeout=timeout,
        )

    def watch_order(
        self, *, client_order_id: str, timeout: float | None = None
    ) -> Iterator[pb2.OrderEvent]:
        """Watch one order. **The stream ENDS when the order reaches a terminal
        state** -- FILLED, CANCELLED or REJECTED -- so you do not have to track
        lifecycle state yourself. FILLED carries the final order body.

        A clean end is NOT an error, which matters if you wrap this in the
        resubscribe loop documented for `watch_orders`: applied here, a filled
        order ends the stream, the loop resubscribes, the new stream ends
        immediately, and you spin. Treat stream end as "done", not "reconnect".

        The first event is a SNAPSHOT of the order as the gateway holds it:
        the confirmed body, or, before the exchange has acknowledged it, a
        PENDING body with `order_id` 0. An unknown id, or an order outside
        your member scope, raises `NotFound` at once, so submit before you
        watch. An order that has already finished when you open the watch
        (state REJECTED, or INACTIVE for any reason) still arrives as that
        SNAPSHOT, and the stream ends right after it.

        A reader that falls behind, and every reader after the gateway
        refreshes its order store (it resubscribed to the exchange's order
        feed, wrote off an unacknowledged order, or cleared a settled
        contract), gets the order read again: a live order arrives as a fresh
        SNAPSHOT and the stream continues; an order still awaiting the
        exchange's acknowledgement arrives as the PENDING SNAPSHOT and stays
        watched; an order that reached a terminal state in the meantime
        arrives as that terminal event (FILLED, CANCELLED or REJECTED), and
        the stream ends. On a re-read, only an order the gateway no longer
        holds, or one no longer in your member scope, ends the stream without
        a terminal event; reconcile that case with `get_order`.
        """
        return self._stream(
            "WatchOrder",
            pb2.WatchOrderRequest(client_order_id=client_order_id),
            timeout=timeout,
        )

    def watch_orders(
        self,
        *,
        delivery_area: str = "",
        contract_id: str = "",
        v_member_short_id: str = "",
        timeout: float | None = None,
    ) -> Iterator[pb2.OrdersEvent]:
        """Watch the caller's resting orders. Opens with a SNAPSHOT, then deltas.

        `delivery_area` and `contract_id` narrow the stream; `""` is no filter.
        A `contract_id` needs a `delivery_area` beside it, and one given alone
        raises `InvalidArgument` ("contract_id requires delivery_area").

        **Reset your state on every SNAPSHOT, not just the first.** The server
        re-sends a full snapshot when it falls behind; treating that as a delta
        accumulates phantom orders. Check `event.type` against
        `OrdersEventType.SNAPSHOT`.

        **Member-scoped by default,** exactly like `list_orders`: without
        `read_orders` / `bypass_member_check` you silently see only the virtual
        members assigned to you, and untagged house orders are withheld. No
        exception is raised, so a caller who believes they are watching the
        firm's book may be watching a slice of it.

        **A modify or cancel the exchange refuses after acknowledging receipt
        arrives as a REJECTED event.** `orders` carries the unchanged order (do
        not mutate your state from it), `reason` the exchange's own words,
        `rejected_action` the refused action (submit, modify, activate,
        deactivate or cancel) and `err_code` its numeric code (0 when the
        exchange sent none). It is emitted whether or not a caller was waiting on
        the outcome, so a caller who submitted with `ack_only=True` learns of the
        refusal here rather than from the call's return.

        Units on the events are wire units: prices in cents, quantities in
        sub-MW.
        """
        return self._stream(
            "WatchOrders",
            pb2.WatchOrdersRequest(
                delivery_area=delivery_area,
                contract_id=contract_id,
                v_member_short_id=v_member_short_id,
            ),
            timeout=timeout,
        )

    def watch_trades(self, *, timeout: float | None = None) -> Iterator[pb2.TradeEvent]:
        """Watch the caller's own trades. First message is SNAPSHOT (full
        current list); each later `TradeEvent` is UPSERTED with one trade. A
        fresh SNAPSHOT is re-emitted if the server falls behind."""
        return self._stream(
            "WatchTrades", pb2.WatchTradesRequest(), timeout=timeout
        )

    def watch_public_trades(
        self,
        *,
        contract_ids: Sequence[int] = (),
        timeout: float | None = None,
    ) -> Iterator[pb2.PublicTrade]:
        """Watch the public trade tape: `PublicTrade` events only, no
        snapshot. Seed history via `list_public_trades()`.

        `contract_ids` scopes the stream to the contracts named; the server
        drops every other print before it reaches the wire. Empty is the
        market-wide tape.

        A slow reader skips the prints it fell behind on, silently, and the
        stream stays open: fill a gap with `list_public_trades(contract_id=...)`
        and de-duplicate on `trade_id`, keeping the higher `revision_no`."""
        return self._stream(
            "WatchPublicTrades",
            pb2.WatchPublicTradesRequest(contract_ids=contract_ids),
            timeout=timeout,
        )

    def watch_trade_tape(
        self, *, timeout: float | None = None
    ) -> Iterator[pb2.TradeTapeEvent]:
        """Watch the market-wide trade tape with each print's contract metadata
        (`area_id`, `prod`, `name`, `delivery_start`) already resolved, so a
        cross-product tape needs no contract lookups of its own.

        The first `TradeTapeEvent` is SNAPSHOT: up to the 200 most recent
        prints, OLDEST FIRST, so you can walk them in order to derive each
        contract's tick direction. Every later event is UPSERTED with the rows
        of one print as it arrives or is revised. A print is listed once per
        delivery area it touches (a cross-border print gives two rows), and a
        print whose contract the gateway no longer holds is left out; the raw
        print is still on `watch_public_trades()`. A slow reader skips the
        prints it fell behind on; the stream stays open.

        Units: `px` is CENTS (CCY/MWh x 100), `qty` is SUB-MW (MW x 1000)."""
        return self._stream(
            "WatchTradeTape", pb2.WatchTradeTapeRequest(), timeout=timeout
        )

    def watch_pnl(
        self, *, v_member_short_id: str = "", timeout: float | None = None
    ) -> Iterator[pb2.PnlSnapshot]:
        """Watch derived P&L. Emits an immediate `PnlSnapshot` then a fresh
        one each second (polled; P&L is a computed view). Member-scoped like
        `get_pnl`; `v_member_short_id` narrows to one member."""
        return self._stream(
            "WatchPnl",
            pb2.WatchPnlRequest(v_member_short_id=v_member_short_id),
            timeout=timeout,
        )

    def watch_slot_positions(
        self,
        *,
        delivery_area: str,
        from_ms: int,
        to_ms: int,
        v_member_short_id: str | None = None,
        timeout: float | None = None,
    ) -> Iterator[pb2.SlotPositionsResponse]:
        """Watch slot limit usage, scoped and bounded like `get_slot_positions`.

        Every message is the FULL set for the range, never a delta: the first
        at subscribe, then the whole set again only when something in it
        changed (at most once per second from fills and orders, and at once
        when the slot mode, the house slot limit or a member's slot limit
        changes), so a client replaces what it holds and never merges. `seq`
        rises by one with each set; a client that reads slowly skips to
        the newest one, so a gap in `seq` loses nothing."""
        return self._stream(
            "WatchSlotPositions",
            pb2.WatchSlotPositionsRequest(
                delivery_area=delivery_area,
                from_ms=from_ms,
                to_ms=to_ms,
                v_member_short_id=v_member_short_id,
            ),
            timeout=timeout,
        )

    def watch_hub2hub(
        self,
        *,
        delivery_area_from: str,
        delivery_from: str,
        delivery_to: str,
        timeout: float | None = None,
    ) -> Iterator[pb2.Hub2HubEvent]:
        """Watch hub-to-hub ATC capacity out of `delivery_area_from` for
        deliveries starting in [`delivery_from`, `delivery_to`) (RFC 3339), the
        live form of `get_hub2hub()` (without its destination filter).

        Each `Hub2HubEvent` holds one of `snapshot`, `update` or `heartbeat`
        (`event.WhichOneof("event")`). The first is a `snapshot`; an `update` is
        the whole row for one source hub and delivery period and REPLACES what
        you hold for (`source_area`, `dlvry_start`), even when its `rows` are
        empty; a `heartbeat` reports the capacity feed's connection state. A
        slow reader is sent a fresh `snapshot`: replace everything you hold.

        With hub-to-hub disabled on the gateway the stream is one snapshot with
        `enabled` false and no data, and then it ends. An unparseable window
        raises `INVALID_ARGUMENT` naming the field. Units as `get_hub2hub()`."""
        return self._stream(
            "WatchHub2Hub",
            pb2.WatchHub2HubRequest(
                delivery_area_from=delivery_area_from,
                delivery_from=delivery_from,
                delivery_to=delivery_to,
            ),
            timeout=timeout,
        )

    def watch_state(self, *, timeout: float | None = None) -> Iterator[pb2.SystemState]:
        """Watch system state: a `SystemState` immediately, then a fresh one
        each second (polled). Requires the `read_state` permission."""
        return self._stream(
            "WatchState", pb2.WatchStateRequest(), timeout=timeout
        )

    def watch_status(self, *, timeout: float | None = None) -> Iterator[pb2.SystemStatus]:
        """Watch trading posture: a `SystemStatus` immediately, then a fresh one
        each second (polled). Open to every authenticated caller; each frame is
        scoped like `get_status`, so the desk-wide money and full licence are set
        only with `read_status`. The caller is re-resolved every frame, so a
        member reassignment shows on the next one."""
        return self._stream(
            "WatchStatus", pb2.WatchStatusRequest(), timeout=timeout
        )

    def watch_messages(self, *, timeout: float | None = None) -> Iterator[pb2.MessageItem]:
        """Watch the system / order-rejection message log. Each `MessageItem`
        carries one JSON row (`item.json`). The log is a rolling in-memory
        buffer polled each second: the rows it holds are sent on subscribe,
        then each row appended after."""
        return self._stream(
            "WatchMessages", pb2.WatchMessagesRequest(), timeout=timeout
        )

    def watch_audit_events(self, *, timeout: float | None = None) -> Iterator[pb2.AuditEventItem]:
        """Tail the compliance audit-event log. Requires `read_audit`, and
        member-scoped as `query_audit_events` is: `read_orders` /
        `bypass_member_check` tails the whole trail. No
        snapshot (seed via `query_audit_events()`); rows appended after
        subscribe are pushed. Clients filter inline. A slow reader skips the
        rows it fell behind on, silently, and the stream stays open: re-query
        `query_audit_events()` for the gap and de-duplicate on the row's
        `id`."""
        return self._stream(
            "WatchAuditEvents", pb2.WatchAuditEventsRequest(), timeout=timeout
        )

    def watch_m7_errors(self, *, timeout: float | None = None) -> Iterator[pb2.M7ErrorItem]:
        """Tail the M7 exchange-error log. Requires `read_m7_errors`. No
        snapshot (seed via `query_m7_errors()`); rows appended after subscribe
        are pushed. Clients filter inline. A slow reader skips the rows it
        fell behind on, silently, and the stream stays open: re-query
        `query_m7_errors()` for the gap and de-duplicate on the row's `id`."""
        return self._stream(
            "WatchM7Errors", pb2.WatchM7ErrorsRequest(), timeout=timeout
        )

    def watch_exchange_messages(
        self, *, timeout: float | None = None
    ) -> Iterator[pb2.ExchangeMessageItem]:
        """Tail the exchange's own message feed. Requires the `read_m7_errors`
        permission, the same one the *history* of this log carries on
        `list_exchange_messages()`: the tail and the history are the same rows,
        so subscribing is not a way around the gate on reading them.
        No snapshot (seed via `list_exchange_messages()`);
        messages received after subscribe are pushed, and clients de-duplicate
        on `msg_id`.

        The stream also carries the messages the exchange marks non-persistent,
        which are never stored: their `id` is null and they cannot be
        re-fetched, so a client that needs them must be subscribed when they
        arrive. A slow reader skips the messages it fell behind on, silently,
        and the stream stays open: re-query `list_exchange_messages()` for the
        stored ones, de-duplicating on `msg_id`; the non-persistent ones in
        the gap are lost."""
        return self._stream(
            "WatchExchangeMessages", pb2.WatchExchangeMessagesRequest(), timeout=timeout
        )

    def watch_system_log(
        self, *, timeout: float | None = None
    ) -> Iterator[pb2.SystemLogItem]:
        """Tail the gateway's own diagnostic log. Requires `read_logs`. No
        snapshot (seed via `list_system_log()`); entries captured after
        subscribe are pushed, and clients de-duplicate on `seq`.

        There is no level parameter, deliberately: the stream carries
        everything the gateway captures, so narrowing and then widening a
        filter can never leave a hole in your history. Filter on your side.

        An item whose `seq` is null and whose `target` is `voltnir.system_log`
        is a marker the server generated, not a captured line: it says this
        subscription fell behind and names how many entries were dropped on the
        way to it. Re-query `list_system_log()` to fill the gap."""
        return self._stream(
            "WatchSystemLog", pb2.WatchSystemLogRequest(), timeout=timeout
        )
