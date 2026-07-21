"""Synchronous Voltnir gRPC client."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

import grpc

from . import auth, channel
from ._generated import voltnir_api_v1_pb2 as pb2
from ._generated import voltnir_api_v1_pb2_grpc as pb2_grpc
from ._orders import (
    build_modify_order_request,
    build_patch_member_request,
    build_submit_order_request,
)
from .errors import ClientClosed, OrderValidationError, translate


def _build(cls: type, kwargs: dict[str, Any]):
    if "from_" in kwargs:
        kwargs["from"] = kwargs.pop("from_")
    return cls(**kwargs)


class VoltnirClient:
    """Sync client for `voltnir.api.v1.VoltAPI`.

    >>> with VoltnirClient(host="localhost", port=3443, api_key="...") as c:
    ...     me = c.get_me()
    ...     print(me.username)

    All RPCs raise a `VoltnirError` subclass on failure (see `errors.py`).
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
    ) -> None:
        """Open a client.

        `options` are gRPC channel options, merged over the SDK defaults
        (keepalive tuned for long-lived `Watch*` streams, and a 64 MB message
        ceiling in place of gRPC's 4 MB). Caller values win per key. See
        `voltnir_sdk.channel.DEFAULT_CHANNEL_OPTIONS`.

        `timeout` is the default deadline for unary calls only; streams default
        to no deadline and are ended by breaking out of the iterator.
        """
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
        order_type: pb2.OrderType.ValueType = pb2.OrderType.REGULAR,
        exe_restriction: pb2.ExeRestriction.ValueType = pb2.ExeRestriction.NON,
        validity_res: pb2.ValidityRes.ValueType = pb2.ValidityRes.GFS,
        entry_state: str = "",
        display_qty_sub_mw: int | None = None,
        validity_date: str = "",
        pre_arranged_acct: str = "",
        v_member_short_id: str = "",
        timeout: float | None = None,
    ) -> pb2.SubmitOrderResponse:
        """Submit a new order.

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

        **Idempotency.** `client_order_id` is required, not optional as the wire
        allows. It is the key that makes recovery possible: the gateway rejects
        a reused key while the original order is live, so after an ambiguous
        failure you can reconcile and, if needed, resubmit without doubling your
        position. Generate one with `new_client_order_id()`.

        **Failure.** `OrderOutcomeUnknown` means the order MAY be resting -
        reconcile with `get_order(client_order_id=...)` before resubmitting.
        Every other `VoltnirError` means the gateway rejected it and nothing
        reached the exchange.

        **`entry_state`** is `""`/`"ACTI"` (default: live and exposed to the
        market) or `"HIBE"` (hibernated: accepted and resting server-side but
        NOT exposed, so it can never fill until activated with
        `modify_order(action=ModifyAction.ACTIVATE)`). Passing `"HIBE"` in the
        belief that it means "active" leaves you holding an order that will
        never trade.

        Identify the contract with `contract_id`, or with both `product` and
        `delivery_start`.

        **Checked locally before dispatch** (raises `OrderValidationError`, a
        `ValueError`, so nothing was sent): a present `client_order_id`; a real
        `side`; a contract identity; integer wire values within their field
        width; `quantity_sub_mw > 0`; `display_qty_sub_mw` only on an ICEBERG
        order and below the total (and mandatory for one); and FOK/IOC only
        alongside `validity_res=ValidityRes.VALIDITY_NON`, which the gateway
        requires and which is spelled `VALIDITY_NON`, not `NON`.

        All of these mirror rules the gateway also enforces, so the local check
        buys a round trip and a clearer message rather than being the only
        thing standing between you and a bad order.
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
            order_type=order_type,
            exe_restriction=exe_restriction,
            validity_res=validity_res,
            entry_state=entry_state,
            display_qty_sub_mw=display_qty_sub_mw,
            validity_date=validity_date,
            pre_arranged_acct=pre_arranged_acct,
            v_member_short_id=v_member_short_id,
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
        timeout: float | None = None,
    ) -> pb2.ModifyOrderResponse:
        """Modify, activate, or deactivate an existing order.

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

        `ACTIVATE` / `DEACTIVATE` take neither price nor quantity.

        Units follow `submit_order`: cents and sub-MW. Plain ints are accepted,
        so the wire's `Int64Value` / `UInt32Value` wrapping is handled for you.

        **A zero quantity is rejected.** It is reachable from correct code:
        `remaining = original - filled` is exactly zero when the order fills
        completely between the snapshot you read and the modify you build from
        it, and a zero restatement means a 0.0 MW order rather than "no
        change". To withdraw an order, use `cancel_order()`.

        Raises `OrderOutcomeUnknown` if the outcome cannot be determined; the
        order may be resting at either the old or the new terms, so reconcile
        with `get_order(client_order_id=...)`.
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
        )
        return self._unary(
            "ModifyOrder",
            request,
            timeout=timeout,
            order_mutating=True,
            client_order_id=client_order_id,
        )

    def cancel_order(self, *, client_order_id: str, timeout: float | None = None) -> pb2.CancelOrderResponse:
        """Cancel one resting order by its `client_order_id`.

        Raises `OrderOutcomeUnknown` if the outcome cannot be determined, in
        which case the order may still be live: confirm with
        `get_order(client_order_id=...)` rather than assuming it is gone.
        """
        return self._unary(
            "CancelOrder",
            pb2.CancelOrderRequest(client_order_id=client_order_id),
            timeout=timeout,
            order_mutating=True,
            client_order_id=client_order_id,
        )

    def cancel_all_orders(self, timeout: float | None = None) -> pb2.CancelAllOrdersResponse:
        """Cancel every resting order for the caller. The kill switch.

        `deleted` counts orders TARGETED at dispatch time, not cancellation
        confirmations received from M7. A non-zero `deleted` is not proof the
        book is clear: confirm with `list_orders()` before standing down.

        Raises `OrderOutcomeUnknown` if the outcome cannot be determined.
        """
        return self._unary(
            "CancelAllOrders",
            pb2.CancelAllOrdersRequest(),
            timeout=timeout,
            order_mutating=True,
        )

    def get_order(self, *, client_order_id: str) -> pb2.GetOrderResponse:
        """Fetch an order by client_order_id. Returns a `GetOrderResponse`
        where exactly one of the `confirmed` / `pending` message fields is
        populated (check with `HasField`)."""
        return self._unary(
            "GetOrder", pb2.GetOrderRequest(client_order_id=client_order_id)
        )

    def list_orders(
        self,
        *,
        delivery_area: str = "",
        contract_id: int = 0,
        product: str = "",
        delivery_start: str = "",
        v_member_short_id: str = "",
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
        )

    # ──────────────────────────────────────────────────────────────────────
    # Trading: contracts
    # ──────────────────────────────────────────────────────────────────────

    def list_contracts(self, *, area_id: str) -> pb2.ListContractsResponse:
        """Contracts in one delivery area, sorted by delivery start.

        Authenticated; no permission required. Note two things before trading
        off this list:

        - Entries can be metadata-less placeholders (order-book data seen
          before the contract-info report), with empty `prod` / `dlvry_start`.
        - `predefined=False` marks a user-defined block contract, which accepts
          only block orders; a regular order there is rejected by the exchange.

        Units on the returned contracts are wire units: prices in cents,
        quantities in sub-MW."""
        return self._unary(
            "ListContracts", pb2.ListContractsRequest(area_id=area_id)
        )

    def get_contract(self, *, area_id: str, contract_id: str) -> pb2.ContractDetail:
        """Contract detail, including your working orders on it.

        **Check BOTH `orders_acknowledged` and `orders_pending`** when deciding
        whether you already have an order working here. An order that has been
        dispatched but not yet acknowledged by M7 appears only in the pending
        list, so looking at the acknowledged list alone is a duplicate-order
        path -- the same hazard `OrderOutcomeUnknown` reconciliation exists to
        prevent.
        """
        return self._unary(
            "GetContract",
            pb2.GetContractRequest(area_id=area_id, contract_id=contract_id),
        )

    def get_contract_by_delivery(self, *, area_id: str, prod: str, dlvry_start: str) -> pb2.ContractDetail:
        """Look up one contract by product and delivery start, instead of by id.

        Authenticated; no permission required. `dlvry_start` must match the
        contract-info format exactly (RFC 3339, e.g. "2026-04-16T22:00:00Z").
        See `get_contract` for the caveat about checking both order lists."""
        return self._unary(
            "GetContractByDelivery",
            pb2.GetContractByDeliveryRequest(
                area_id=area_id, prod=prod, dlvry_start=dlvry_start
            ),
        )

    def get_hub2hub(
        self,
        *,
        delivery_area_from: str,
        delivery_from: str,
        delivery_to: str,
        delivery_area_to: str = "",
    ) -> pb2.GetHub2HubResponse:
        """ATC rows out of `delivery_area_from`, optionally limited to one
        destination via `delivery_area_to`.

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
        )

    # ──────────────────────────────────────────────────────────────────────
    # System state / operator controls
    # ──────────────────────────────────────────────────────────────────────

    def get_state(self) -> pb2.SystemState:
        """Runtime health snapshot: uptime, operational flag, subsystem state.

        Requires the `read_state` permission. This is pure runtime health; the
        trading posture (kill switch, limits, license) lives on `get_status`."""
        return self._unary("GetState", pb2.GetStateRequest())

    def get_status(self) -> pb2.SystemStatus:
        """Trading posture: kill switch, limits, cash state, license.

        Requires the `read_status` permission, unlike `get_state`, which is
        gated separately. Units: `order_pos_limit` is sub-MW, `cash_limit`
        fields are cents, and the `cash_limits` list is M7's raw feed scaled by
        each row's own `dec_shft` (see `get_cash_limits`)."""
        return self._unary("GetStatus", pb2.GetStatusRequest())

    def get_throttling(self) -> pb2.ThrottlingStatus:
        """M7 order-message throttling counters and the current window.

        Authenticated; no permission required. Worth reading before a burst: the
        exchange rate-limits order messages, and this is where the remaining
        allowance is visible."""
        return self._unary("GetThrottling", pb2.GetThrottlingRequest())

    def get_system_info(self) -> pb2.SystemInfo:
        """Build and connection info: gateway version, M7 version, request limits.

        Authenticated; no permission required."""
        return self._unary("GetSystemInfo", pb2.GetSystemInfoRequest())

    def get_contract_limit(self) -> pb2.ContractLimitResponse:
        """Current per-contract net position limit, in sub-MW (MW x 1000)."""
        return self._unary("GetContractLimit", pb2.GetContractLimitRequest())

    def set_contract_limit(self, *, quantity: int) -> pb2.ContractLimitResponse:
        """Set the per-contract net position limit, in SUB-MW (MW x 1000).

        **0 does NOT disable the limit. 0 BLOCKS all new position-taking.**
        The check stays active at zero, so setting this to 0 to "turn the limit
        off" halts the desk. That is the opposite polarity to
        `set_cash_limit(cents=0)`, which does disable its pool.

        Requires the set_contract_limit permission.
        """
        return self._unary(
            "SetContractLimit", pb2.SetContractLimitRequest(quantity=quantity)
        )

    def get_cash_limit(self) -> pb2.CashLimitResponse:
        """Global (overarching-member) cash limit in EUR cents. Distinct from
        get_cash_limits(), which reports the M7-supplied per-currency feed."""
        return self._unary("GetCashLimit", pb2.GetCashLimitRequest())

    def set_cash_limit(self, *, cents: int, currency: str = "eur") -> pb2.CashLimitResponse:
        """Set the global cash limit for one currency pool, in CENTS.

        `currency` is "eur" (default) or "gbp"; the GBP pool is only enforced
        with `separate_gbp_pool`. Passing the wrong currency writes the limit
        into the wrong pool and silently leaves the other uncapped.

        **`cents=0` DISABLES the pool** (unbounded) -- unless
        `set_cash_fail_closed(True)` is set, in which case 0 means the opposite:
        no trading in that pool at all. Note also that
        `set_contract_limit(quantity=0)` means BLOCK, not disable. Three
        adjacent settings, three meanings of zero.

        Use `eur_to_cents()` if you are holding a decimal amount.
        Requires the set_cash_limit permission.
        """
        return self._unary(
            "SetCashLimit", pb2.SetCashLimitRequest(cents=cents, currency=currency)
        )

    def get_cash_fail_closed(self) -> pb2.CashFailClosedResponse:
        """ECC fail-closed switch. When enabled, a 0/unset cash limit means no
        trading in that pool (ECC parity) rather than 'disabled'."""
        return self._unary(
            "GetCashFailClosed", pb2.GetCashFailClosedRequest()
        )

    def set_cash_fail_closed(self, *, enabled: bool) -> pb2.CashFailClosedResponse:
        """ECC fail-closed switch. This FLIPS the meaning of a zero cash limit.

        `True`  -> a 0/unset cash limit means NO TRADING in that pool (ECC parity).
        `False` -> a 0/unset cash limit means the pool is unbounded.

        So enabling this on a desk that left a pool at 0 halts that pool
        immediately. Requires the set_cash_limit permission.
        """
        return self._unary(
            "SetCashFailClosed", pb2.SetCashFailClosedRequest(enabled=enabled)
        )

    def get_holidays(self) -> pb2.HolidaysResponse:
        """Both ECC bank-holiday calendars (eur + gbp) for the cash-limit
        exposure window. Authenticated; no permission required."""
        return self._unary("GetHolidays", pb2.GetHolidaysRequest())

    def set_holidays(self, *, currency: str, holidays: Sequence[pb2.Holiday]) -> pb2.HolidaysResponse:
        """Replace one currency's whole calendar. `currency` is "eur" or "gbp";
        `holidays` is a sequence of pb2.Holiday (date "YYYY-MM-DD", label).
        Requires set_cash_limit."""
        return self._unary(
            "SetHolidays",
            pb2.SetHolidaysRequest(currency=currency, holidays=list(holidays)),
        )

    def add_holiday(self, *, currency: str, date: str, label: str = "") -> pb2.HolidaysResponse:
        """Add one date to a currency's calendar. Requires set_cash_limit."""
        return self._unary(
            "AddHoliday",
            pb2.AddHolidayRequest(currency=currency, date=date, label=label),
        )

    def remove_holiday(self, *, currency: str, date: str) -> pb2.HolidaysResponse:
        """Remove one date from a currency's calendar. Requires set_cash_limit;
        NOT_FOUND when the date is not configured."""
        return self._unary(
            "RemoveHoliday",
            pb2.RemoveHolidayRequest(currency=currency, date=date),
        )

    def get_trading_allowed(self) -> pb2.TradingAllowedResponse:
        """Whether trading is currently enabled (the kill switch).

        Authenticated; no permission required. `set_trading_allowed` performs
        the write and is gated."""
        return self._unary(
            "GetTradingAllowed", pb2.GetTradingAllowedRequest()
        )

    def set_trading_allowed(self, *, allowed: bool) -> pb2.TradingAllowedResponse:
        """The trading kill switch. `False` halts ALL new trading firm-wide.

        Disabling also cancels resting orders server-side. Requires the
        set_trading_allowed permission.
        """
        return self._unary(
            "SetTradingAllowed", pb2.SetTradingAllowedRequest(allowed=allowed)
        )

    def get_self_trade_policy(self) -> pb2.SelfTradePolicyResponse:
        """Current self-trade prevention policy: OBSERVE or REJECT.

        Authenticated; no permission required. Compare against
        `SelfTradePolicy`; `set_self_trade_policy` performs the write."""
        return self._unary(
            "GetSelfTradePolicy", pb2.GetSelfTradePolicyRequest()
        )

    def set_self_trade_policy(self, *, policy: str) -> pb2.SelfTradePolicyResponse:
        """Fetch one order by `client_order_id`.

        Exactly one of the `confirmed` / `pending` fields is populated, so test
        with `HasField` rather than truthiness. `pending` means dispatched but
        not yet acknowledged by M7.

        This is the authoritative reconciliation call after an
        `OrderOutcomeUnknown`. Treat a `NotFound` as conclusive only if it
        persists: an order still in flight reads as absent for a moment, and
        concluding "it never landed" too early is what leads to a resubmit that
        doubles the position."""
        # policy is "observe" or "reject" (mirrors the REST endpoint).
        try:
            value = pb2.SelfTradePolicy.Value("SELF_TRADE_POLICY_" + policy.upper())
        except ValueError as exc:
            # protobuf's own message names the generated enum constant, which is
            # not a thing the caller passed or can see in this signature.
            raise OrderValidationError(
                f"policy must be 'observe' or 'reject', got {policy!r}"
            ) from exc
        return self._unary(
            "SetSelfTradePolicy", pb2.SetSelfTradePolicyRequest(policy=value)
        )

    def restart(self) -> pb2.RestartResponse:
        """Restart the gateway. Every live stream a desk is consuming DROPS.

        There is no confirmation step and no undo. Consumers must resubscribe;
        anything mid-flight is subject to the same ambiguity as any other
        interrupted call. Requires the restart permission.
        """
        return self._unary("Restart", pb2.RestartRequest())

    # ──────────────────────────────────────────────────────────────────────
    # Cash limits / PnL / Public trades
    # ──────────────────────────────────────────────────────────────────────

    def get_cash_limits(self) -> pb2.GetCashLimitsResponse:
        """M7's per-currency cash/margin feed. NOT cents, and NOT a fixed scale.

        Each `CashLimit` row carries its own `dec_shft`, and the real amount is
        `raw / 10 ** dec_shft`. Do not use `cents_to_eur` here:

            for lim in client.get_cash_limits().limits:
                amount = Decimal(lim.current_limit) / (Decimal(10) ** (lim.dec_shft or 0))

        Distinct from `get_cash_limit()` (singular), which is Voltnir's own
        configured limit and IS in cents. `SystemStatus` carries both as
        adjacent fields, `cash_limit` and `cash_limits`, whose scales differ by
        an arbitrary power of ten.
        """
        return self._unary("GetCashLimits", pb2.GetCashLimitsRequest())

    def list_permissions(self) -> pb2.ListPermissionsResponse:
        """Catalog of assignable permissions, each with a code and a
        human-readable description. Requires the manage_users permission."""
        return self._unary("ListPermissions", pb2.ListPermissionsRequest())

    def get_pnl(self, *, v_member_short_id: str = "") -> pb2.PnlSnapshot:
        """Derived P&L. Note that this message mixes THREE unit scales.

        - `realized_pnl` / `unrealized_pnl`: q8, meaning EUR x 100_000. Use
          `q8_to_eur`. Reading these as cents overstates by 1000x.
        - `signed_position`: sub-MW (MW x 1000), + long / - short.
        - `avg_open_px` / `mark_px`: cents (CCY/MWh x 100).

        **Member-scoped by default:** without `read_orders` /
        `bypass_member_check` the result covers only the virtual members
        assigned to the caller, silently. A desk that believes it is seeing the
        firm's whole book while seeing one member's slice will under-hedge, and
        no exception is raised. `v_member_short_id` narrows to one member.
        """
        return self._unary(
            "GetPnl", pb2.GetPnlRequest(v_member_short_id=v_member_short_id)
        )

    def list_public_trades(
        self,
        *,
        limit: int = 0,
        contract_id: int = 0,
        area_id: str = "",
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
        )

    # ──────────────────────────────────────────────────────────────────────
    # Users / members
    # ──────────────────────────────────────────────────────────────────────

    def get_me(self) -> pb2.UserProfile:
        """The caller's own user record: id, username, and granted permissions.

        Authenticated; no permission required. Useful as a connectivity and
        credential smoke test, and to discover which of the permission-gated
        calls below will work for this key."""
        return self._unary("GetMe", pb2.GetMeRequest())

    def get_my_members(self) -> pb2.MemberListResponse:
        """Virtual members assigned to the caller.

        Authenticated; no permission required. These are the members whose
        orders and P&L you see by default: several read paths are silently
        member-scoped to this set unless you hold `read_orders` /
        `bypass_member_check`."""
        return self._unary("GetMyMembers", pb2.GetMyMembersRequest())

    def list_users(self) -> pb2.ListUsersResponse:
        """Set self-trade prevention: "observe" or "reject".

        Requires the `set_self_trade_policy` permission. Any other string raises
        `OrderValidationError` locally, before anything is sent."""
        return self._unary("ListUsers", pb2.ListUsersRequest())

    def create_user(self, *, username: str, permissions: Sequence[str] = ()) -> pb2.CreateUserResponse:
        """Create a user. `permissions` is optional (matches the proto and
        the documented call shape); empty means no permissions granted."""
        return self._unary(
            "CreateUser",
            pb2.CreateUserRequest(username=username, permissions=list(permissions)),
        )

    def delete_user(self, *, user_id: str) -> pb2.Empty:
        """All users and their permissions.

        Requires the `manage_users` permission."""
        return self._unary(
            "DeleteUser", pb2.DeleteUserRequest(user_id=user_id)
        )

    def set_permissions(self, *, user_id: str, permissions: Sequence[str]) -> pb2.Empty:
        """Delete a user by id. Their API key stops working immediately.

        Requires the `manage_users` permission. There is no undo; recreate the
        user to restore access, which issues a new key."""
        return self._unary(
            "SetPermissions",
            pb2.SetPermissionsRequest(user_id=user_id, permissions=list(permissions)),
        )

    def rotate_api_key(self, *, user_id: str) -> pb2.RotateApiKeyResponse:
        """Issue a new API key for a user and invalidate the old one.

        Requires the `manage_users` permission. The new key is returned ONCE in
        the response and is not retrievable afterwards. Any client still using
        the old key begins failing with `Unauthenticated` immediately."""
        return self._unary(
            "RotateApiKey", pb2.RotateApiKeyRequest(user_id=user_id)
        )

    def get_user_members(self, *, user_id: str) -> pb2.UserMembersResponse:
        """Returns `UserMembersResponse.member_ids`: member UUIDs
        (`Member.id`), not VM-style short ids."""
        return self._unary(
            "GetUserMembers", pb2.GetUserMembersRequest(user_id=user_id)
        )

    def set_user_members(self, *, user_id: str, member_ids: Sequence[str]) -> pb2.Empty:
        """Replace-all assignment. `member_ids` are member UUIDs
        (`Member.id`), not VM-style short ids."""
        return self._unary(
            "SetUserMembers",
            pb2.SetUserMembersRequest(
                user_id=user_id, member_ids=list(member_ids)
            ),
        )

    def list_members(self) -> pb2.MemberListResponse:
        """All virtual members, with their limits and live cash usage.

        Requires the `manage_members` permission. Units: `max_position` is
        sub-MW; every `*_cents` field is cents. `cash_limit` 0 means no
        per-member override, so the global limit applies."""
        return self._unary("ListMembers", pb2.ListMembersRequest())

    def create_member(self, *, name: str, max_position: int, cash_limit: int = 0, cash_limit_gbp: int = 0) -> pb2.Member:
        """Create a virtual member. The VM-style `short_id` is generated
        server-side and returned in the `Member` response. `cash_limit` is in
        EUR cents and `cash_limit_gbp` in GBP cents (separate-pool mode); 0 = no
        per-member override → the global limit applies."""
        return self._unary(
            "CreateMember",
            pb2.CreateMemberRequest(
                name=name, max_position=max_position,
                cash_limit=cash_limit, cash_limit_gbp=cash_limit_gbp,
            ),
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
        timeout: float | None = None,
    ) -> pb2.Empty:
        """Update a member. Only the fields you pass are sent, and applied.

        Genuinely a patch, unlike `modify_order`: an omitted field is left
        untouched server-side. Passing 0 for a cash limit explicitly CLEARS the
        per-member override so the global limit applies again.

        `id` is the member UUID (`Member.id`), not the VM-style `short_id`.
        Plain Python values are accepted; the wire's wrapper types are handled
        for you.
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
            ),
            timeout=timeout,
        )

    # ──────────────────────────────────────────────────────────────────────
    # Audit
    # ──────────────────────────────────────────────────────────────────────

    def query_audit_orders(self, **kwargs) -> pb2.AuditOrdersResponse:
        """Query the historical order audit log.

        Requires the `read_audit` permission. Filters: `cursor`, `limit`
        (0 -> 50, capped 200), `date_from`, `date_to`, and the order fields.
        Paginate with `next_cursor` from the response."""
        return self._unary(
            "QueryAuditOrders", _build(pb2.AuditOrdersRequest, kwargs)
        )

    def query_audit_trades(self, **kwargs) -> pb2.AuditTradesResponse:
        """Query the historical trade audit log.

        Requires the `read_audit` permission. Filters and pagination match
        `query_audit_orders`. Units on the returned rows are wire units."""
        return self._unary(
            "QueryAuditTrades", _build(pb2.AuditTradesRequest, kwargs)
        )

    def query_audit_public_trades(self, **kwargs) -> pb2.AuditPublicTradesResponse:
        """Query the historical public-trade audit log.

        Requires the `read_audit` permission. Filters and pagination match
        `query_audit_orders`."""
        return self._unary(
            "QueryAuditPublicTrades", _build(pb2.AuditPublicTradesRequest, kwargs)
        )

    def query_audit_events(self, **kwargs) -> pb2.AuditEventsResponse:
        """Query the compliance audit-event log. Requires `read_audit`.
        Filter fields: `cursor`, `limit` (0 → 50, capped 200), `date_from`,
        `date_to`, `action`, `target_type`, `actor_short_id`, `outcome`."""
        return self._unary(
            "QueryAuditEvents", _build(pb2.AuditEventsRequest, kwargs)
        )

    # ──────────────────────────────────────────────────────────────────────
    # M7 errors
    # ──────────────────────────────────────────────────────────────────────

    def query_m7_errors(self, **kwargs) -> pb2.M7ErrorsResponse:
        """Query the persisted M7 exchange-error log. Requires `read_m7_errors`
        (a dedicated gate, not `read_audit`). Filter fields: `cursor`, `limit`
        (0 → 50, capped 200), `date_from`, `date_to`, `kind`, `category`,
        `err_code` (0 → unset)."""
        return self._unary(
            "QueryM7Errors", _build(pb2.M7ErrorsRequest, kwargs)
        )

    # ──────────────────────────────────────────────────────────────────────
    # Streaming RPCs
    # ──────────────────────────────────────────────────────────────────────

    def export_orders(self, **kwargs) -> Iterator[pb2.ExportChunk]:
        """Stream `ExportChunk`s. Pass `from_` for the proto's `from` field
        (it's a Python keyword)."""
        return self._stream("ExportOrders", _build(pb2.ExportRequest, kwargs))

    def export_trades(self, **kwargs) -> Iterator[pb2.ExportChunk]:
        """Stream an order-history export as `ExportChunk`s.

        Requires the `export_reports` permission. Pass `from_` for the proto's
        `from` field, which is a Python keyword. Drain the iterator and
        concatenate `chunk.data`."""
        return self._stream("ExportTrades", _build(pb2.ExportRequest, kwargs))

    def watch_contract(
        self, *, area_id: str, contract_id: str, timeout: float | None = None
    ) -> Iterator[pb2.ContractEvent]:
        """Watch one contract: an initial SNAPSHOT, then order-book and state
        events.

        **Reset on every SNAPSHOT.** Like `watch_orders`, a lag-recovery
        snapshot can arrive mid-stream. Recovery is coalesced, so a burst of lag
        yields at most one, and it is skipped entirely when the contract has not
        changed since your last event -- do not rely on one snapshot per lagged
        event.

        `timeout` is an overall gRPC deadline in seconds; when it fires, the
        iterator raises `DeadlineExceeded`. `None` (default) streams until
        cancelled or the contract closes.
        """
        return self._stream(
            "WatchContract",
            pb2.WatchContractRequest(area_id=area_id, contract_id=contract_id),
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

        **Reset your state on every SNAPSHOT, not just the first.** The server
        re-sends a full snapshot when it falls behind; treating that as a delta
        accumulates phantom orders. Check `event.type` against
        `OrdersEventType.SNAPSHOT`.

        **Member-scoped by default,** exactly like `list_orders`: without
        `read_orders` / `bypass_member_check` you silently see only the virtual
        members assigned to you, and untagged house orders are withheld. No
        exception is raised, so a caller who believes they are watching the
        firm's book may be watching a slice of it.

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

    def watch_public_trades(self, *, timeout: float | None = None) -> Iterator[pb2.PublicTrade]:
        """Watch the public trade tape: `PublicTrade` events only, no
        snapshot. Seed history via `list_public_trades()`."""
        return self._stream(
            "WatchPublicTrades", pb2.WatchPublicTradesRequest(), timeout=timeout
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

    def watch_state(self, *, timeout: float | None = None) -> Iterator[pb2.SystemState]:
        """Watch system state: a `SystemState` immediately, then a fresh one
        each second (polled)."""
        return self._stream(
            "WatchState", pb2.WatchStateRequest(), timeout=timeout
        )

    def watch_status(self, *, timeout: float | None = None) -> Iterator[pb2.SystemStatus]:
        """Watch trading posture: a `SystemStatus` immediately, then a fresh one
        each second (polled). Requires the `read_status` permission."""
        return self._stream(
            "WatchStatus", pb2.WatchStatusRequest(), timeout=timeout
        )

    def watch_messages(self, *, timeout: float | None = None) -> Iterator[pb2.MessageItem]:
        """Watch the system / order-rejection message log. Each `MessageItem`
        carries one JSON row (`item.json`). No snapshot; rows appended after
        subscribe are pushed; seed via `get_state()`."""
        return self._stream(
            "WatchMessages", pb2.WatchMessagesRequest(), timeout=timeout
        )

    def watch_audit_events(self, *, timeout: float | None = None) -> Iterator[pb2.AuditEventItem]:
        """Tail the compliance audit-event log. Requires `read_audit`. No
        snapshot (seed via `query_audit_events()`); rows appended after
        subscribe are pushed. Clients filter inline."""
        return self._stream(
            "WatchAuditEvents", pb2.WatchAuditEventsRequest(), timeout=timeout
        )

    def watch_m7_errors(self, *, timeout: float | None = None) -> Iterator[pb2.M7ErrorItem]:
        """Tail the M7 exchange-error log. Requires `read_m7_errors`. No
        snapshot (seed via `query_m7_errors()`); rows appended after subscribe
        are pushed. Clients filter inline."""
        return self._stream(
            "WatchM7Errors", pb2.WatchM7ErrorsRequest(), timeout=timeout
        )
