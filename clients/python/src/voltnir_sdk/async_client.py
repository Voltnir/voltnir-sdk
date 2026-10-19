"""Asynchronous Voltnir gRPC client (asyncio + grpc.aio)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Sequence
from typing import Any, Literal

import grpc
import grpc.aio

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
from ._recall import areturning_result
from .errors import (
    AsyncLoopError,
    ClientClosed,
    OrderValidationError,
    translate,
)


_NOT_FIELDS = ("self", "timeout")


def _kwargs_request(cls: type, scope: dict[str, Any]):
    """Build `cls` from a wrapper's `locals()`, setting only the fields passed.

    See `voltnir_sdk.client._kwargs_request`. `None` means "not passed", so only
    non-`None` values reach the request, preserving proto3 presence.
    """
    return cls(
        **{k: v for k, v in scope.items() if k not in _NOT_FIELDS and v is not None}
    )


class AsyncVoltnirClient:
    """Async client for `voltnir.api.v1.VoltAPI`.

    >>> async with AsyncVoltnirClient(host="localhost", port=3443, api_key="...") as c:
    ...     me = await c.get_me()
    ...     async for ev in c.watch_contracts(areas=["10YBE----------2"], contract_ids=[12345]):
    ...         break

    Surface mirrors `VoltnirClient` exactly; every method is `async def` and
    streaming methods return an `AsyncIterator`.
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
        """Open an async client. See `VoltnirClient.__init__` for `options`
        and `rest_url`.

        NOTE: grpc.aio binds the channel to the running event loop at
        construction, so build this inside the loop that will use it. A client
        constructed at import time, or in a DI container outside the loop,
        fails later with a confusing cross-loop Future error.
        """
        # grpc.aio binds the channel to the running loop right here, so a
        # client built outside one is already broken; it just does not say so
        # until the first call, and then says it very badly. Fail at the
        # mistake instead.
        try:
            self._loop = asyncio.get_running_loop()
        except RuntimeError as exc:
            raise AsyncLoopError(
                "AsyncVoltnirClient must be constructed inside the running "
                "event loop that will use it: grpc.aio binds the channel to "
                "the loop at construction. Build it inside your async entry "
                "point (or use VoltnirClient for synchronous code)."
            ) from exc

        self._rest = _rest_export.make_endpoint(rest_url, api_key, ca_cert_path)
        self._channel = channel.build_async_channel(
            host, port, tls=tls, ca_cert_path=ca_cert_path, options=options
        )
        self._stub = pb2_grpc.VoltAPIStub(self._channel)
        self._auth = auth.auth_metadata(api_key)
        self._timeout = timeout
        self._closed = False

    def _check_loop(self) -> None:
        """Refuse to use a channel bound to a different loop than this one.

        Catches the case where the client outlives the loop it was built in, or
        is shared across `asyncio.run()` calls: the native failure there is
        "Event loop is closed" or a cross-loop Future error, neither of which
        names the client.
        """
        try:
            current = asyncio.get_running_loop()
        except RuntimeError as exc:
            raise AsyncLoopError(
                "AsyncVoltnirClient used outside a running event loop"
            ) from exc
        if current is not self._loop:
            raise AsyncLoopError(
                "AsyncVoltnirClient is bound to the event loop it was built "
                "in, and is being used from a different one. Build one client "
                "per loop; a client cannot be shared across asyncio.run() calls."
            )

    async def __aenter__(self) -> "AsyncVoltnirClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    async def close(self) -> None:
        """Close the channel. Further calls raise `ClientClosed`.

        Idempotent. Prefer the context manager, which closes on both normal and
        exceptional exit. Abandoned streams are cancelled when their iterator
        is dropped, so a long-lived consumer does not need to close each one."""
        self._closed = True
        await self._channel.close()

    # ──────────────────────────────────────────────────────────────────────
    # Internal call helpers
    # ──────────────────────────────────────────────────────────────────────

    async def _unary(
        self,
        rpc: str,
        request,
        *,
        timeout: float | None = None,
        order_mutating: bool = False,
        client_order_id: str | None = None,
    ):
        self._check_loop()
        if self._closed:
            raise ClientClosed(rpc)
        method = getattr(self._stub, rpc)
        try:
            return await method(
                request,
                timeout=timeout if timeout is not None else self._timeout,
                metadata=self._auth,
            )
        except grpc.RpcError as e:
            # grpc.RpcError, not grpc.aio.AioRpcError: the aio type is a subclass,
            # and a plain RpcError on the async path would otherwise escape
            # untranslated as a raw gRPC object.
            raise translate(
                e,
                rpc,
                order_mutating=order_mutating,
                client_order_id=client_order_id,
            ) from e

    async def _stream(
        self, rpc: str, request, *, timeout: float | None = None
    ) -> AsyncIterator:
        self._check_loop()
        if self._closed:
            raise ClientClosed(rpc)
        method = getattr(self._stub, rpc)
        call = method(request, timeout=timeout, metadata=self._auth)
        try:
            async for item in call:
                yield item
        except grpc.RpcError as e:
            raise translate(e, rpc) from e
        finally:
            # Cancel on ANY exit, including the caller simply breaking out of
            # the loop. Without this the server-side subscription stays open:
            # the Call sits in a coroutine/async-generator reference cycle, so
            # refcounting never reclaims it and only the cyclic GC (or
            # loop.shutdown_asyncgens) eventually does. Measured at 1:1 growth
            # per abandoned stream, surviving both `aclose()` and `close()`.
            #
            # The production failure is silent: with a bounded server handler
            # pool, leaked subscriptions starve it and NEW subscribes block
            # with no exception raised. A desk goes blind and gets no error.
            call.cancel()

    # ──────────────────────────────────────────────────────────────────────
    # Trading: orders
    # ──────────────────────────────────────────────────────────────────────

    async def submit_order(
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
        """Submit a new order. See `VoltnirClient.submit_order` for the full
        contract: units, idempotency, the `ack_only` receipt-vs-outcome choice,
        and the failure semantics that decide whether a retry is safe. Requires
        the `create_order` permission."""
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
        return await self._unary(
            "SubmitOrder",
            request,
            timeout=timeout,
            order_mutating=True,
            client_order_id=client_order_id,
        )

    async def modify_order(
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
        """Modify, activate, or deactivate an order. A MODIFY is a full
        restatement, not a patch, and `ack_only` chooses receipt vs outcome:
        see `VoltnirClient.modify_order`. Requires the `modify_order`
        permission."""
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
        return await self._unary(
            "ModifyOrder",
            request,
            timeout=timeout,
            order_mutating=True,
            client_order_id=client_order_id,
        )

    async def cancel_order(
        self,
        *,
        client_order_id: str,
        ack_only: bool = False,
        timeout: float | None = None,
    ) -> pb2.CancelOrderResponse:
        """Cancel one resting order. `ack_only` chooses receipt vs outcome and
        raises `OrderOutcomeUnknown` when the outcome cannot be determined; the
        order may still be live. See `VoltnirClient.cancel_order`. Requires the
        `delete_order` permission."""
        return await self._unary(
            "CancelOrder",
            pb2.CancelOrderRequest(client_order_id=client_order_id, ack_only=ack_only),
            timeout=timeout,
            order_mutating=True,
            client_order_id=client_order_id,
        )

    async def cancel_all_orders(self, timeout: float | None = None) -> pb2.CancelAllOrdersResponse:
        """Cancel every resting order for the caller. Requires the
        `delete_order` permission. What `deleted` counts, and the larger
        `timeout` a member-scoped cancel-all needs: see
        `VoltnirClient.cancel_all_orders`."""
        return await self._unary(
            "CancelAllOrders",
            pb2.CancelAllOrdersRequest(),
            timeout=timeout,
            order_mutating=True,
        )

    async def submit_basket(
        self,
        *,
        list_exec_inst: str,
        orders: Sequence[dict[str, Any]],
        basket_ref: str = "",
        timeout: float | None = None,
    ) -> pb2.SubmitBasketResponse:
        """Enter 1 to 100 orders as one exchange order entry. Requires the
        `create_order` permission. The list instructions, the all-or-none
        check, the answer and `basket_ref`: see `VoltnirClient.submit_basket`."""
        request = build_submit_basket_request(
            list_exec_inst=list_exec_inst, orders=orders, basket_ref=basket_ref
        )
        return await self._unary(
            "SubmitBasket", request, timeout=timeout, order_mutating=True
        )

    async def cancel_basket(
        self, basket_ref: str, *, timeout: float | None = None
    ) -> pb2.CancelBasketResponse:
        """Cancel every resting order of one basket. Requires the
        `delete_order` permission. See `VoltnirClient.cancel_basket`."""
        return await self._unary(
            "CancelBasket",
            pb2.CancelBasketRequest(basket_ref=basket_ref),
            timeout=timeout,
            order_mutating=True,
        )

    async def recall_trade(
        self,
        trade_id: str,
        *,
        revision_no: int | None = None,
        timeout: float | None = None,
    ) -> pb2.RecallTradeResponse:
        """Ask the exchange to recall one executed trade (a mistrade).

        Requires the `recall_trade` permission. See
        `VoltnirClient.recall_trade` for who may recall what, `revision_no`,
        how to read each `outcome`, and why `timeout` must exceed the
        gateway's waits.
        """
        request = pb2.RecallTradeRequest(trade_id=trade_id)
        if revision_no is not None:
            request.revision_no = revision_no
        return await areturning_result(
            self._unary("RecallTrade", request, timeout=timeout)
        )

    async def recall_order_trades(
        self, client_order_id: str, *, timeout: float | None = None
    ) -> pb2.RecallTradeResponse:
        """Ask the exchange to recall every recallable trade of one order.

        Requires the `recall_trade` permission. See
        `VoltnirClient.recall_order_trades`, including its `timeout` note.
        """
        request = pb2.RecallTradeRequest(client_order_id=client_order_id)
        return await areturning_result(
            self._unary("RecallTrade", request, timeout=timeout)
        )

    async def get_order(
        self, *, client_order_id: str, timeout: float | None = None
    ) -> pb2.GetOrderResponse:
        """Fetch one order by `client_order_id`, the reconciliation call
        after an `OrderOutcomeUnknown`. Member-scoped: without `read_orders` /
        `bypass_member_check` an order outside your members reads as
        `NotFound`. See `VoltnirClient.get_order`."""
        return await self._unary(
            "GetOrder",
            pb2.GetOrderRequest(client_order_id=client_order_id),
            timeout=timeout,
        )

    async def list_orders(
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
        return await self._unary(
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

    async def list_contracts(
        self, *, area_id: str, timeout: float | None = None
    ) -> pb2.ListContractsResponse:
        """The contract catalogue of one delivery area, sorted by delivery
        start: ids, delivery and state, with no book and no prices. When to
        call it and where the book comes from is on
        `VoltnirClient.list_contracts`."""
        return await self._unary(
            "ListContracts",
            pb2.ListContractsRequest(area_id=area_id),
            timeout=timeout,
        )

    async def get_contract(
        self, *, area_id: str, contract_id: str, timeout: float | None = None
    ) -> pb2.ContractDetail:
        """Contract detail, including your working orders on it. Check BOTH
        `orders_acknowledged` and `orders_pending`; the rows are member-scoped
        unless you hold `read_orders` / `bypass_member_check`. See
        `VoltnirClient.get_contract`."""
        return await self._unary(
            "GetContract",
            pb2.GetContractRequest(area_id=area_id, contract_id=contract_id),
            timeout=timeout,
        )

    async def get_contract_by_delivery(
        self, *, area_id: str, prod: str, dlvry_start: str, timeout: float | None = None
    ) -> pb2.ContractDetail:
        """Look up one contract by product and delivery start, instead of by id.

        Authenticated; no permission required. `dlvry_start` follows the rule
        on `VoltnirClient.get_contract_by_delivery`: any RFC 3339 spelling of the
        UTC delivery start. See `get_contract` for the caveat about checking both
        order lists."""
        return await self._unary(
            "GetContractByDelivery",
            pb2.GetContractByDeliveryRequest(
                area_id=area_id, prod=prod, dlvry_start=dlvry_start
            ),
            timeout=timeout,
        )

    async def get_hub2hub(
        self,
        *,
        delivery_area_from: str,
        delivery_from: str,
        delivery_to: str,
        delivery_area_to: str = "",
        timeout: float | None = None,
    ) -> pb2.GetHub2HubResponse:
        """ATC rows out of `delivery_area_from`, optionally limited to one
        destination via `delivery_area_to`. `atc_out` / `atc_in` are signed
        sub-MW (negative ATC is real) and the best bid/ask fields cents; the
        window and its `InvalidArgument` match `VoltnirClient.get_hub2hub`."""
        return await self._unary(
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

    async def get_state(self, *, timeout: float | None = None) -> pb2.SystemState:
        """Runtime health snapshot: uptime, operational flag, subsystem state.

        Requires the `read_state` permission. This is pure runtime health; the
        trading posture (kill switch, limits, license) lives on `get_status`."""
        return await self._unary("GetState", pb2.GetStateRequest(), timeout=timeout)

    async def get_status(self, *, timeout: float | None = None) -> pb2.SystemStatus:
        """Trading posture, scoped to the caller. See `VoltnirClient.get_status`
        for the layering: base posture and the caller's own `accounts` to every
        authenticated caller, the desk-wide money and full licence only with
        `read_status`."""
        return await self._unary("GetStatus", pb2.GetStatusRequest(), timeout=timeout)

    async def get_throttling(
        self, *, timeout: float | None = None
    ) -> pb2.ThrottlingStatus:
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
        message is in SECONDS. See `VoltnirClient.get_throttling` for the two
        throttling action fields."""
        return await self._unary(
            "GetThrottling", pb2.GetThrottlingRequest(), timeout=timeout
        )

    async def get_system_info(self, *, timeout: float | None = None) -> pb2.SystemInfo:
        """Build and connection info: gateway version, M7 version, request limits.
        See `VoltnirClient.get_system_info` for the products' block settings.

        Authenticated; no permission required."""
        return await self._unary(
            "GetSystemInfo", pb2.GetSystemInfoRequest(), timeout=timeout
        )

    async def get_area_table(self, *, timeout: float | None = None) -> pb2.AreaTable:
        """The M7 EIC area reference table, live-name-overlaid. See
        `VoltnirClient.get_area_table` for the field-by-field semantics, the
        unset-`fill_country` trap and the static floor. Authenticated; no
        permission required."""
        return await self._unary(
            "GetAreaTable", pb2.GetAreaTableRequest(), timeout=timeout
        )

    async def get_contract_limit(
        self, *, timeout: float | None = None
    ) -> pb2.ContractLimitResponse:
        """Current per-contract net position limit, in sub-MW (MW x 1000).

        Requires the `read_status` permission: this exposes the desk-wide money the
        `get_status` snapshot carries only under that permission."""
        return await self._unary(
            "GetContractLimit",
            pb2.GetContractLimitRequest(),
            timeout=timeout,
        )

    async def set_contract_limit(
        self, *, quantity: int, timeout: float | None = None
    ) -> pb2.ContractLimitResponse:
        """Set the per-contract net position limit, in SUB-MW (MW x 1000).

        **0 does NOT disable the limit. 0 BLOCKS all new position-taking.**
        The check stays active at zero, so setting this to 0 to "turn the limit
        off" halts the desk. `set_cash_limit(cap_cents=0)` reads the same way:
        zero is a real ceiling, not an off switch.

        Requires the `set_position_limit` permission.
        """
        return await self._unary(
            "SetContractLimit",
            pb2.SetContractLimitRequest(quantity=quantity),
            timeout=timeout,
        )

    async def get_slot_limit(
        self, *, timeout: float | None = None
    ) -> pb2.SlotLimitResponse:
        """The slot position limit's mode and House limit; see
        `VoltnirClient.get_slot_limit`. Requires the `read_status` permission."""
        return await self._unary(
            "GetSlotLimit", pb2.GetSlotLimitRequest(), timeout=timeout
        )

    async def set_slot_limit(
        self, *, mode: str, house_limit: int, timeout: float | None = None
    ) -> pb2.SlotLimitResponse:
        """Set the slot limit's mode ("off", "observe", "reject") and House
        limit in sub-MW; see `VoltnirClient.set_slot_limit`. Requires the
        `set_position_limit` permission."""
        return await self._unary(
            "SetSlotLimit",
            build_set_slot_limit_request(mode=mode, house_limit=house_limit),
            timeout=timeout,
        )

    async def get_slot_positions(
        self,
        *,
        delivery_area: str,
        from_ms: int,
        to_ms: int,
        v_member_short_id: str | None = None,
        timeout: float | None = None,
    ) -> pb2.SlotPositionsResponse:
        """Per-quarter-hour slot limit usage for one area, at most 48 hours;
        see `VoltnirClient.get_slot_positions`."""
        return await self._unary(
            "GetSlotPositions",
            pb2.GetSlotPositionsRequest(
                delivery_area=delivery_area,
                from_ms=from_ms,
                to_ms=to_ms,
                v_member_short_id=v_member_short_id,
            ),
            timeout=timeout,
        )

    async def get_cash_limit(
        self, *, timeout: float | None = None
    ) -> pb2.CashLimitResponse:
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

        Distinct from get_cash_limits(), which reports the raw per-currency
        feed.

        Requires the `read_status` permission: this exposes the desk-wide money the
        `get_status` snapshot carries only under that permission."""
        return await self._unary(
            "GetCashLimit", pb2.GetCashLimitRequest(), timeout=timeout
        )

    async def set_cash_limit(
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
        names the pool and both amounts.

        Use `eur_to_cents()` if you are holding a decimal amount.
        Requires the set_cash_limit permission.
        """
        return await self._unary(
            "SetCashLimit",
            build_set_cash_limit_request(cap_cents=cap_cents, currency=currency),
            timeout=timeout,
        )

    async def get_holidays(
        self, *, timeout: float | None = None
    ) -> pb2.HolidaysResponse:
        """Both ECC bank-holiday calendars (eur + gbp) for the cash-limit
        exposure window. Authenticated; no permission required."""
        return await self._unary(
            "GetHolidays", pb2.GetHolidaysRequest(), timeout=timeout
        )

    async def set_holidays(
        self,
        *,
        currency: str,
        holidays: Sequence[pb2.Holiday],
        timeout: float | None = None,
    ) -> pb2.HolidaysResponse:
        """Replace one currency's whole calendar. `currency` is "eur" or "gbp";
        `holidays` is a sequence of `voltnir_sdk.Holiday`. Requires set_cash_limit."""
        return await self._unary(
            "SetHolidays",
            pb2.SetHolidaysRequest(currency=currency, holidays=list(holidays)),
            timeout=timeout,
        )

    async def add_holiday(
        self, *, currency: str, date: str, label: str = "", timeout: float | None = None
    ) -> pb2.HolidaysResponse:
        """Add one date to a currency's calendar. Requires set_cash_limit."""
        return await self._unary(
            "AddHoliday",
            pb2.AddHolidayRequest(currency=currency, date=date, label=label),
            timeout=timeout,
        )

    async def remove_holiday(
        self, *, currency: str, date: str, timeout: float | None = None
    ) -> pb2.HolidaysResponse:
        """Remove one date from a currency's calendar. Requires set_cash_limit;
        NOT_FOUND when the date is not configured."""
        return await self._unary(
            "RemoveHoliday",
            pb2.RemoveHolidayRequest(currency=currency, date=date),
            timeout=timeout,
        )

    async def get_trading_allowed(
        self, *, timeout: float | None = None
    ) -> pb2.TradingAllowedResponse:
        """Whether trading is currently enabled (the kill switch).

        Open to every authenticated caller — the `trading_enabled` base slice of
        the `get_status` snapshot, which a trader needs to know whether it may
        submit at all. `set_trading_allowed` performs the write and is gated on
        `toggle_trading` instead."""
        return await self._unary(
            "GetTradingAllowed",
            pb2.GetTradingAllowedRequest(),
            timeout=timeout,
        )

    async def set_trading_allowed(
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
        return await self._unary(
            "SetTradingAllowed",
            pb2.SetTradingAllowedRequest(allowed=allowed),
            timeout=timeout,
        )

    async def ack_trade_ingest_fault(
        self, reason: str, *, timeout: float | None = None
    ) -> pb2.AckTradeIngestFaultResponse:
        """Acknowledge a raised `trade_report refused` fault, reopening order admission.

        Requires the `toggle_trading` permission. See
        `VoltnirClient.ack_trade_ingest_fault` for what the acknowledgement does,
        how long it lasts and its refusals (`Aborted`, `InvalidArgument`).
        """
        return await self._unary(
            "AckTradeIngestFault",
            pb2.AckTradeIngestFaultRequest(reason=reason),
            timeout=timeout,
        )

    async def get_self_trade_policy(
        self, *, timeout: float | None = None
    ) -> pb2.SelfTradePolicyResponse:
        """Current self-trade prevention policy: OBSERVE or REJECT.

        Authenticated; no permission required. Compare against
        `SelfTradePolicy`; `set_self_trade_policy` performs the write."""
        return await self._unary(
            "GetSelfTradePolicy",
            pb2.GetSelfTradePolicyRequest(),
            timeout=timeout,
        )

    async def set_self_trade_policy(
        self, *, policy: str, timeout: float | None = None
    ) -> pb2.SelfTradePolicyResponse:
        """Set self-trade prevention: "observe" or "reject".

        Requires the `set_self_trade_policy` permission. Any other string raises
        `OrderValidationError` locally, before anything is sent."""
        return await self._unary(
            "SetSelfTradePolicy",
            build_set_self_trade_policy_request(policy=policy),
            timeout=timeout,
        )

    async def restart(self, *, timeout: float | None = None) -> pb2.RestartResponse:
        """Restart the gateway. Every live stream a desk is consuming DROPS.

        There is no confirmation step and no undo. Consumers must resubscribe;
        anything mid-flight is subject to the same ambiguity as any other
        interrupted call. Requires the `restart_system` permission.
        """
        return await self._unary("Restart", pb2.RestartRequest(), timeout=timeout)

    async def restore_trade_history(
        self, *, days: int | None = None, timeout: float | None = None
    ) -> pb2.RestoreTradeHistoryResponse:
        """Backfill the persistent trade store from the exchange's history.

        Requires the `restore_trade_history` permission. See
        `VoltnirClient.restore_trade_history` for the
        absent-vs-`0` `days` rule, and how to follow progress on `SystemState`.
        """
        request = pb2.RestoreTradeHistoryRequest()
        if days is not None:
            request.days = days
        return await self._unary("RestoreTradeHistory", request, timeout=timeout)

    # ──────────────────────────────────────────────────────────────────────
    # Cash limits / PnL / Public trades
    # ──────────────────────────────────────────────────────────────────────

    async def get_cash_limits(
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
        return await self._unary(
            "GetCashLimits", pb2.GetCashLimitsRequest(), timeout=timeout
        )

    async def list_permissions(
        self, *, timeout: float | None = None
    ) -> pb2.ListPermissionsResponse:
        """Catalog of assignable permissions, each with a code and a
        human-readable description. Requires the manage_users permission."""
        return await self._unary(
            "ListPermissions", pb2.ListPermissionsRequest(), timeout=timeout
        )

    async def get_pnl(
        self, *, v_member_short_id: str = "", timeout: float | None = None
    ) -> pb2.PnlSnapshot:
        """Derived P&L, in three unit scales and per currency; never add
        money across currencies. Member-scoped by default: without `read_pnl` /
        `bypass_member_check` it covers only your members, silently. See
        `VoltnirClient.get_pnl`."""
        return await self._unary(
            "GetPnl",
            pb2.GetPnlRequest(v_member_short_id=v_member_short_id),
            timeout=timeout,
        )

    async def list_public_trades(
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
        return await self._unary(
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

    async def get_me(self, *, timeout: float | None = None) -> pb2.UserProfile:
        """The caller's own user record: id, username, and granted permissions.

        Authenticated; no permission required. Useful as a connectivity and
        credential smoke test, and to discover which of the permission-gated
        calls below will work for this key."""
        return await self._unary("GetMe", pb2.GetMeRequest(), timeout=timeout)

    async def get_my_members(
        self, *, timeout: float | None = None
    ) -> pb2.MemberListResponse:
        """Virtual members assigned to the caller.

        Authenticated; no permission required. These are the members whose
        orders and P&L you see by default: several read paths are silently
        member-scoped to this set unless you hold that path's broad read
        (`read_orders` for orders, `read_pnl` for P&L) or
        `bypass_member_check`."""
        return await self._unary(
            "GetMyMembers", pb2.GetMyMembersRequest(), timeout=timeout
        )

    async def list_users(
        self, *, timeout: float | None = None
    ) -> pb2.ListUsersResponse:
        """All users and their permissions.

        Requires the `manage_users` permission and the desk-management license
        (see `VoltnirClient`)."""
        return await self._unary("ListUsers", pb2.ListUsersRequest(), timeout=timeout)

    async def create_user(
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
        return await self._unary(
            "CreateUser",
            pb2.CreateUserRequest(
                username=username, permissions=list(permissions)
            ),
            timeout=timeout,
        )

    async def delete_user(
        self, *, user_id: str, timeout: float | None = None
    ) -> pb2.Empty:
        """Delete a user by id. Their API key stops working immediately. See
        `VoltnirClient.delete_user`: there is no undo, and the username is
        never given to another user, so restoring access means a new username.
        Requires the `manage_users` permission and the desk-management license
        (see `VoltnirClient`)."""
        return await self._unary(
            "DeleteUser",
            pb2.DeleteUserRequest(user_id=user_id),
            timeout=timeout,
        )

    async def set_permissions(
        self, *, user_id: str, permissions: Sequence[str], timeout: float | None = None
    ) -> pb2.Empty:
        """Replace a user's permissions with exactly this list.

        Requires the `manage_users` permission and the desk-management license
        (see `VoltnirClient`). This is replace-all, not a merge: any permission
        omitted is REVOKED. Read the current set with `list_users` first, and
        see `list_permissions` for the assignable catalog."""
        return await self._unary(
            "SetPermissions",
            pb2.SetPermissionsRequest(
                user_id=user_id, permissions=list(permissions)
            ),
            timeout=timeout,
        )

    async def rotate_api_key(
        self, *, user_id: str, timeout: float | None = None
    ) -> pb2.RotateApiKeyResponse:
        """Issue a new API key for a user and invalidate the old one.

        Requires the `manage_users` permission. The new key is returned ONCE in
        the response and is not retrievable afterwards. Any client still using
        the old key begins failing with `Unauthenticated` immediately.

        Open under a trader license too, where a caller may rotate only its
        own key: any other `user_id` raises `NotFound`, the same answer as an
        unknown id, so the call never reveals whether a user exists."""
        return await self._unary(
            "RotateApiKey",
            pb2.RotateApiKeyRequest(user_id=user_id),
            timeout=timeout,
        )

    async def get_user_members(
        self, *, user_id: str, timeout: float | None = None
    ) -> pb2.UserMembersResponse:
        """The members a user is assigned to; see `VoltnirClient.get_user_members`.

        Requires the `manage_users` permission and the desk-management license
        (see `VoltnirClient`)."""
        return await self._unary(
            "GetUserMembers",
            pb2.GetUserMembersRequest(user_id=user_id),
            timeout=timeout,
        )

    async def set_user_members(
        self, *, user_id: str, member_ids: Sequence[str], timeout: float | None = None
    ) -> pb2.Empty:
        """Replace a user's member assignment with exactly this list; see
        `VoltnirClient.set_user_members`.

        Requires the `manage_users` permission and the desk-management license
        (see `VoltnirClient`)."""
        return await self._unary(
            "SetUserMembers",
            pb2.SetUserMembersRequest(
                user_id=user_id, member_ids=list(member_ids)
            ),
            timeout=timeout,
        )

    async def list_members(
        self, *, timeout: float | None = None
    ) -> pb2.MemberListResponse:
        """All virtual members, with their limits and live cash usage.

        Requires the `manage_members` permission and the desk-management
        license (see `VoltnirClient`). Units: `max_position` and
        `max_slot_position` are sub-MW; every `*_cents` field is cents.
        `cash_limit` is the member's allocation out of the desk's cash limit,
        and `eur_limit_cents` is that same number as the enforced limit; 0
        means no allocation, so the member cannot add exposure in that pool."""
        return await self._unary(
            "ListMembers", pb2.ListMembersRequest(), timeout=timeout
        )

    async def create_member(
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
        """Create a virtual member; see `VoltnirClient.create_member`. Requires
        the `manage_members` permission and the desk-management license (see
        `VoltnirClient`).

        `cash_limit` (EUR cents) and `cash_limit_gbp` (GBP cents) are the
        member's allocations out of the desk's cash limit; 0 means no
        allocation. INVALID_ARGUMENT when the pool's allocations would exceed
        the desk's limit. `delivery_areas` (default: no areas) is the set of
        areas the member may trade in."""
        return await self._unary(
            "CreateMember",
            pb2.CreateMemberRequest(
                name=name, max_position=max_position,
                cash_limit=cash_limit, cash_limit_gbp=cash_limit_gbp,
                max_slot_position=max_slot_position,
                delivery_areas=delivery_areas,
            ),
            timeout=timeout,
        )

    async def patch_member(
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
        """Update a member; only supplied fields are sent. See
        `VoltnirClient.patch_member`. Requires the `manage_members` permission
        and the desk-management license (see `VoltnirClient`)."""
        return await self._unary(
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

    async def delete_member(
        self, *, member_id: str, timeout: float | None = None
    ) -> pb2.Empty:
        """Delete a member by id. See `VoltnirClient.delete_member`: raises
        `InvalidArgument`, and nothing changes, while the member has an open
        order, a position on a contract whose delivery has not ended, or
        consumed cash (a charge or a credit) counted until the next booking
        cut, and while the gateway's cash sums cannot be fully priced.
        Requires the `manage_members` permission and the desk-management
        license (see `VoltnirClient`)."""
        return await self._unary(
            "DeleteMember",
            pb2.DeleteMemberRequest(member_id=member_id),
            timeout=timeout,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Audit
    # ──────────────────────────────────────────────────────────────────────

    async def query_audit_orders(
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

        Fields and semantics are documented on
        `VoltnirClient.query_audit_orders`. Needs no permission; member-scoped,
        and `read_orders` / `bypass_member_check` widens it to the whole desk."""
        return await self._unary(
            "QueryAuditOrders",
            _kwargs_request(pb2.AuditOrdersRequest, locals()),
            timeout=timeout,
        )

    async def query_audit_trades(
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

        Fields and semantics are documented on
        `VoltnirClient.query_audit_trades`. Needs no permission; member-scoped,
        and `read_orders` / `bypass_member_check` widens it to the whole desk."""
        return await self._unary(
            "QueryAuditTrades",
            _kwargs_request(pb2.AuditTradesRequest, locals()),
            timeout=timeout,
        )

    async def query_audit_public_trades(
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

        Fields and semantics are documented on
        `VoltnirClient.query_audit_public_trades`. Requires `read_audit`."""
        return await self._unary(
            "QueryAuditPublicTrades",
            _kwargs_request(pb2.AuditPublicTradesRequest, locals()),
            timeout=timeout,
        )

    async def query_audit_events(
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
        Fields and semantics are documented on
        `VoltnirClient.query_audit_events`. Member-scoped, and `read_orders` /
        `bypass_member_check` widens it to the whole trail."""
        return await self._unary(
            "QueryAuditEvents",
            _kwargs_request(pb2.AuditEventsRequest, locals()),
            timeout=timeout,
        )

    # ──────────────────────────────────────────────────────────────────────
    # M7 errors
    # ──────────────────────────────────────────────────────────────────────

    async def query_m7_errors(
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
        """Query the persisted M7 exchange-error log. Requires `read_m7_errors`.
        Fields and semantics are documented on
        `VoltnirClient.query_m7_errors`."""
        return await self._unary(
            "QueryM7Errors",
            _kwargs_request(pb2.M7ErrorsRequest, locals()),
            timeout=timeout,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Exchange messages
    # ──────────────────────────────────────────────────────────────────────

    async def list_exchange_messages(
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
        """Query the exchange-message log. Requires `read_m7_errors`.
        Fields, the item shape and semantics are documented on
        `VoltnirClient.list_exchange_messages`."""
        return await self._unary(
            "ListExchangeMessages",
            _kwargs_request(pb2.ListExchangeMessagesRequest, locals()),
            timeout=timeout,
        )

    # ──────────────────────────────────────────────────────────────────────
    # System log
    # ──────────────────────────────────────────────────────────────────────

    async def list_system_log(
        self,
        *,
        cursor: int | None = None,
        limit: int | None = None,
        min_level: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        timeout: float | None = None,
    ) -> pb2.ListSystemLogResponse:
        """Read the gateway's own diagnostic log; see
        `VoltnirClient.list_system_log` for the filter fields, the entry shape
        and — importantly — why the `buffer` block on the response has to be
        read before the result is presented.

        Requires `read_logs`. Not an audit record: the buffer is a bounded
        in-memory ring, lost on restart and lossy under load."""
        return await self._unary(
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
    ) -> AsyncIterator[bytes]:
        """Export the order history of a window as a file, as an async iterator of bytes.

        Requires the `export_reports` permission. Parameters, filters,
        transport, the `timeout` and the errors match
        `VoltnirClient.export_orders`. Every blocking network step runs in a
        worker thread, so the event loop keeps serving other tasks while the
        gateway builds and sends the file."""
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
    ) -> AsyncIterator[bytes]:
        """Export the trade history of a window as a file, as an async iterator of bytes.

        Requires the `export_reports` permission. Parameters, filters,
        `time_basis`, transport and errors match
        `VoltnirClient.export_trades`."""
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
    ) -> AsyncIterator[bytes]:
        """Export the compliance audit trail of a window as a file, as an async iterator of bytes.

        Requires the `export_reports` permission and also `read_audit`.
        Parameters, rows, transport and errors match
        `VoltnirClient.export_audit`."""
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
    ) -> AsyncIterator[bytes]:
        op = op or f"export_{kind}"
        if self._closed:
            raise ClientClosed(op)
        endpoint = _rest_export.require(self._rest, op)
        return _rest_export.aexport(endpoint, kind, body, timeout, op)

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
    ) -> AsyncIterator[pb2.ContractsEvent]:
        """Watch contracts live, for one contract or a whole product.
        `timeout` is an overall gRPC deadline in seconds; when it fires, the
        iterator raises `DeadlineExceeded`. `None` (default) streams until
        cancelled. The filter rule, what each event carries, and how a client
        that falls behind is served, are on `VoltnirClient.watch_contracts`."""
        return self._stream(
            "WatchContracts",
            pb2.WatchContractsRequest(
                areas=areas, products=products or (), contract_ids=contract_ids or ()
            ),
            timeout=timeout,
        )

    def watch_order(
        self, *, client_order_id: str, timeout: float | None = None
    ) -> AsyncIterator[pb2.OrderEvent]:
        """Stream events for one order until it reaches a terminal state.

        The stream ENDS cleanly on FILLED / CANCELLED / REJECTED, so a
        resubscribe loop written for `watch_orders` will spin here. See
        `VoltnirClient.watch_order`."""
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
    ) -> AsyncIterator[pb2.OrdersEvent]:
        """Stream the caller's resting orders: a SNAPSHOT, then deltas.

        Reset state on EVERY snapshot, not just the first: a fresh one is
        re-sent when the server falls behind. Silently member-scoped without
        `read_orders` / `bypass_member_check`. See `VoltnirClient.watch_orders`."""
        return self._stream(
            "WatchOrders",
            pb2.WatchOrdersRequest(
                delivery_area=delivery_area,
                contract_id=contract_id,
                v_member_short_id=v_member_short_id,
            ),
            timeout=timeout,
        )

    def watch_trades(self, *, timeout: float | None = None) -> AsyncIterator[pb2.TradeEvent]:
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
    ) -> AsyncIterator[pb2.PublicTrade]:
        """Watch the public trade tape, no snapshot; a slow reader skips
        prints. See `VoltnirClient.watch_public_trades`."""
        return self._stream(
            "WatchPublicTrades",
            pb2.WatchPublicTradesRequest(contract_ids=contract_ids),
            timeout=timeout,
        )

    def watch_trade_tape(
        self, *, timeout: float | None = None
    ) -> AsyncIterator[pb2.TradeTapeEvent]:
        """Watch the enriched trade tape, a SNAPSHOT (oldest first) and then
        UPSERTED events; see `VoltnirClient.watch_trade_tape`."""
        return self._stream(
            "WatchTradeTape", pb2.WatchTradeTapeRequest(), timeout=timeout
        )

    def watch_pnl(
        self, *, v_member_short_id: str = "", timeout: float | None = None
    ) -> AsyncIterator[pb2.PnlSnapshot]:
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
    ) -> AsyncIterator[pb2.SlotPositionsResponse]:
        """Watch slot limit usage, every message the full set; see
        `VoltnirClient.watch_slot_positions`."""
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
    ) -> AsyncIterator[pb2.Hub2HubEvent]:
        """Watch hub-to-hub ATC capacity for one source hub and window, a
        snapshot first; see `VoltnirClient.watch_hub2hub`."""
        return self._stream(
            "WatchHub2Hub",
            pb2.WatchHub2HubRequest(
                delivery_area_from=delivery_area_from,
                delivery_from=delivery_from,
                delivery_to=delivery_to,
            ),
            timeout=timeout,
        )

    def watch_state(self, *, timeout: float | None = None) -> AsyncIterator[pb2.SystemState]:
        """Watch system state: a `SystemState` immediately, then a fresh one
        each second (polled). Requires the `read_state` permission."""
        return self._stream(
            "WatchState", pb2.WatchStateRequest(), timeout=timeout
        )

    def watch_status(self, *, timeout: float | None = None) -> AsyncIterator[pb2.SystemStatus]:
        """Watch trading posture: a `SystemStatus` immediately, then a fresh one
        each second (polled). Open to every authenticated caller; each frame is
        scoped like `get_status`, so the desk-wide money and full licence are set
        only with `read_status`, and the caller is re-resolved every frame."""
        return self._stream(
            "WatchStatus", pb2.WatchStatusRequest(), timeout=timeout
        )

    def watch_messages(self, *, timeout: float | None = None) -> AsyncIterator[pb2.MessageItem]:
        """Watch the system / order-rejection message log. Each `MessageItem`
        carries one JSON row (`item.json`). The log is a rolling in-memory
        buffer polled each second: the rows it holds are sent on subscribe,
        then each row appended after."""
        return self._stream(
            "WatchMessages", pb2.WatchMessagesRequest(), timeout=timeout
        )

    def watch_audit_events(
        self, *, timeout: float | None = None
    ) -> AsyncIterator[pb2.AuditEventItem]:
        """Tail the compliance audit-event log. Requires `read_audit`.
        Member-scoped, and `read_orders` / `bypass_member_check` widens it to
        the whole trail. No snapshot, and a slow reader skips rows: see
        `VoltnirClient.watch_audit_events`."""
        return self._stream(
            "WatchAuditEvents", pb2.WatchAuditEventsRequest(), timeout=timeout
        )

    def watch_m7_errors(
        self, *, timeout: float | None = None
    ) -> AsyncIterator[pb2.M7ErrorItem]:
        """Tail the M7 exchange-error log. Requires `read_m7_errors`. No
        snapshot, and a slow reader skips rows: see
        `VoltnirClient.watch_m7_errors`."""
        return self._stream(
            "WatchM7Errors", pb2.WatchM7ErrorsRequest(), timeout=timeout
        )

    def watch_exchange_messages(
        self, *, timeout: float | None = None
    ) -> AsyncIterator[pb2.ExchangeMessageItem]:
        """Tail the exchange's own message feed. Requires the `read_m7_errors`
        permission. No snapshot; a slow reader skips messages, and the
        non-persistent ones cannot be re-fetched: see
        `VoltnirClient.watch_exchange_messages`."""
        return self._stream(
            "WatchExchangeMessages", pb2.WatchExchangeMessagesRequest(), timeout=timeout
        )

    def watch_system_log(
        self, *, timeout: float | None = None
    ) -> AsyncIterator[pb2.SystemLogItem]:
        """Tail the gateway's own diagnostic log; see
        `VoltnirClient.watch_system_log`.

        Requires `read_logs`. No snapshot (seed via `list_system_log()`) and no
        level parameter — an item with a null `seq` and the
        `voltnir.system_log` target is a dropped-entries marker, not a captured
        line."""
        return self._stream(
            "WatchSystemLog", pb2.WatchSystemLogRequest(), timeout=timeout
        )
