#!/usr/bin/env python3
"""Voltnir gRPC SDK verification runner.

Exercises all 63 RPCs the service declares against a live Voltnir server and
prints [PASS]/[FAIL]/[SKIP] per step. Mirrors the parent repo's `bin/test_grpc`
runner: a single linear script, no test framework.

"All 63" is enforced, not asserted by hand. This runner is linear and
hand-written, so unlike the descriptor-driven offline suite it cannot notice a
new RPC by itself. Two guards close that: every call the clients make is
recorded (see `_CallRecorder`) and the run ends with a coverage line naming any
RPC it never attempted, and a static check in the offline suite walks this
file's AST and fails if any wrapper has no call site here.

Coverage:
- Read-only (default): every query + getter, plus first-frame/subscribe smokes
  for all live streams. Permission-gated reads (audit, M7 errors, user
  management, export) [SKIP] cleanly when the key lacks the permission.
- `--mutate`: the write surface, covering a hibernated order lifecycle
  (submit/modify/get/watch/cancel + cancel-all), operator Set* round-trips
  (read the current value, set it straight back, so no net change), the
  holiday calendars (SetHolidays writes back what GetHolidays returned;
  AddHoliday/RemoveHoliday run as a matched pair on a far-future sentinel
  date), throwaway user + member lifecycles (create/patch/rotate/delete), and
  the **reconciliation pass**: a deliberately tiny client-side deadline forces
  the ambiguous-failure path, then asserts that it raises OrderOutcomeUnknown
  (not DeadlineExceeded), that get_order resolves it definitively, and that
  reusing a live client_order_id is refused. That last property is what makes
  a retry after an ambiguous failure safe, and nothing else tests it.
- `--include-restart`: the one remaining RPC, Restart, run dead last.

Usage:
    python verify.py --host localhost --port 3443 \\
        --api-key "$VOLTNIR_KEY" --area 10YBE----------2
    python verify.py --host voltnir.example.com --tls --ca cert.pem \\
        --api-key "$KEY" --area 10Y1001A1001A82H --watch-events 3
    python verify.py --api-key "$KEY" --area "$AREA_EIC" --mutate

`--area` is required and deployment-specific: the EIC code of a delivery
area carried by your Voltnir's M7 connection (e.g. 10YBE----------2 for
Belgium, 10Y1001A1001A82H for Germany). `ListContracts` is scoped to it.

No mutating RPC ever sends a live order (orders are hibernated) or changes net
operator state (Set* round-trips restore the prior value). The one caveat:
CreateMember has no DeleteMember RPC, so `--mutate` leaves a deactivated test
member behind, which is fine on a sim but not for production keys.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from voltnir_sdk import (
    AsyncVoltnirClient,
    NotFound,
    OrderOutcomeUnknown,
    ContractState,
    DeadlineExceeded,
    ExportFormat,
    ModifyAction,
    OrderType,
    PermissionDenied,
    SelfTradePolicy,
    Side,
    Unauthenticated,
    VoltnirClient,
    VoltnirError,
    new_client_order_id,
)


# ────────────────────────────────────────────────────────────────────────────
# Step harness
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class Result:
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    failures: list[str] = field(default_factory=list)


class _CallRecorder:
    """Records which RPCs a run actually attempted, for the coverage line.

    Both clients funnel every call through `_unary` / `_stream`, which take the
    wire RPC name as their first argument, so wrapping those two methods
    captures the truth: what reached the transport, not what the step *names*
    claim. Step names are free text (``"ListOrders (scoped)"``) and several
    steps call more than one RPC, so parsing them would be guesswork.

    A PERMISSION_DENIED still counts as attempted. The question this answers is
    "does this runner have a step for every RPC", not "did the key hold every
    permission": different failures, and only the first is a gap in coverage.
    """

    def __init__(self) -> None:
        self.attempted: set[str] = set()
        self._undo: list[Callable[[], None]] = []

    def install(self, *classes: type) -> None:
        for cls in classes:
            for name in ("_unary", "_stream"):
                original = getattr(cls, name)
                setattr(cls, name, self._wrap(original))
                self._undo.append(
                    lambda c=cls, n=name, o=original: setattr(c, n, o)
                )

    def _wrap(self, original):
        recorder = self

        def wrapper(client_self, rpc, *a, **kw):
            recorder.attempted.add(rpc)
            return original(client_self, rpc, *a, **kw)

        return wrapper

    def uninstall(self) -> None:
        for undo in reversed(self._undo):
            undo()
        self._undo.clear()

    def missing(self) -> list[str]:
        """RPC names the service declares that this run never attempted."""
        from voltnir_sdk._generated import voltnir_api_v1_pb2 as pb2

        declared = {
            m.name for m in pb2.DESCRIPTOR.services_by_name["VoltAPI"].methods
        }
        return sorted(declared - self.attempted)

    def total_declared(self) -> int:
        from voltnir_sdk._generated import voltnir_api_v1_pb2 as pb2

        return len(pb2.DESCRIPTOR.services_by_name["VoltAPI"].methods)


def step(result: Result, name: str, fn: Callable[[], Any]) -> Any:
    print(f"  → {name} ... ", end="", flush=True)
    t0 = time.monotonic()
    try:
        out = fn()
    except VoltnirError as e:
        dt_ms = int((time.monotonic() - t0) * 1000)
        print(f"[FAIL {dt_ms}ms] {e.code.name}: {e.message}")
        result.failed += 1
        result.failures.append(f"{name}: {e.code.name}: {e.message}")
        return None
    except Exception as e:
        dt_ms = int((time.monotonic() - t0) * 1000)
        print(f"[FAIL {dt_ms}ms] {type(e).__name__}: {e}")
        result.failed += 1
        result.failures.append(f"{name}: {type(e).__name__}: {e}")
        return None
    dt_ms = int((time.monotonic() - t0) * 1000)
    print(f"[PASS {dt_ms}ms]")
    result.passed += 1
    return out


def skip(result: Result, name: str, reason: str) -> None:
    print(f"  → {name} ... [SKIP] {reason}")
    result.skipped += 1


def gated(result: Result, name: str, fn: Callable[[], Any]) -> Any:
    """Like `step`, but a PERMISSION_DENIED is a [SKIP], not a [FAIL]. For
    RPCs whose permission the verify key may legitimately lack."""
    print(f"  → {name} ... ", end="", flush=True)
    t0 = time.monotonic()
    try:
        out = fn()
    except PermissionDenied:
        print("[SKIP] permission not granted")
        result.skipped += 1
        return None
    except VoltnirError as e:
        dt_ms = int((time.monotonic() - t0) * 1000)
        print(f"[FAIL {dt_ms}ms] {e.code.name}: {e.message}")
        result.failed += 1
        result.failures.append(f"{name}: {e.code.name}: {e.message}")
        return None
    except Exception as e:
        dt_ms = int((time.monotonic() - t0) * 1000)
        print(f"[FAIL {dt_ms}ms] {type(e).__name__}: {e}")
        result.failed += 1
        result.failures.append(f"{name}: {type(e).__name__}: {e}")
        return None
    dt_ms = int((time.monotonic() - t0) * 1000)
    print(f"[PASS {dt_ms}ms]")
    result.passed += 1
    return out


def subscribe_smoke(
    result: Result, name: str, stream_factory: Callable[[], Any]
) -> None:
    """Verify a live stream *subscribes* cleanly. Append-only tails can
    legitimately stay silent on a quiet sim, so a frame OR a clean deadline
    both pass; PERMISSION_DENIED skips (the gate is the thing under test)."""
    print(f"  → {name} ... ", end="", flush=True)
    try:
        stream = stream_factory()
        got = False
        try:
            for _ev in stream:
                got = True
                break
        finally:
            close = getattr(stream, "close", None)
            if callable(close):
                close()
        print("[PASS] frame received" if got else "[PASS] subscribed (quiet)")
        result.passed += 1
    except DeadlineExceeded:
        print("[PASS] subscribed (idle to deadline)")
        result.passed += 1
    except PermissionDenied:
        print("[SKIP] permission not granted")
        result.skipped += 1
    except VoltnirError as e:
        print(f"[FAIL] {e.code.name}: {e.message}")
        result.failed += 1
        result.failures.append(f"{name}: {e.code.name}: {e.message}")


# ────────────────────────────────────────────────────────────────────────────
# Sync pass: read-only
# ────────────────────────────────────────────────────────────────────────────


def run_sync_readonly(client: VoltnirClient, area: str, watch_events: int) -> Result:
    r = Result()
    print("\n[sync] read-only pass")

    me = step(r, "GetMe", client.get_me)
    if me is not None:
        print(
            f"      user={me.username!r} permissions={list(me.permissions)}"
        )

    state = step(r, "GetState", client.get_state)
    if state is not None:
        print(
            f"      uptime={state.uptime} operational={state.operational}"
        )

    # Trading posture. Gated on read_status, unlike GetState above, which is
    # authenticated-only: the convenience fields (trading_enabled, limits,
    # license) moved out of SystemState into SystemStatus when status was
    # brought to full transport parity.
    status = gated(r, "GetStatus", client.get_status)
    if status is not None:
        print(
            f"      trading_enabled={status.trading_enabled} "
            f"order_pos_limit={status.order_pos_limit}"
        )

    step(r, "GetTradingAllowed", client.get_trading_allowed)
    step(r, "GetThrottling", client.get_throttling)
    step(r, "GetSystemInfo", client.get_system_info)
    step(r, "GetContractLimit", client.get_contract_limit)
    step(r, "GetCashLimit", client.get_cash_limit)

    # ECC fail-closed switch: when enabled, a 0/unset cash limit means "no
    # trading in that pool" rather than "limit disabled". Read-only here; the
    # restore round-trip is in the operator pass.
    cfc = step(r, "GetCashFailClosed", client.get_cash_fail_closed)
    if cfc is not None:
        print(f"      enabled={cfc.enabled}")

    # Both ECC bank-holiday calendars. Authenticated, no permission required.
    hol = step(r, "GetHolidays", client.get_holidays)
    if hol is not None:
        print(
            f"      eur={len(hol.eur)} dates, gbp={len(hol.gbp)} dates"
        )

    pol = step(r, "GetSelfTradePolicy", client.get_self_trade_policy)
    if pol is not None:
        print(f"      policy={SelfTradePolicy.Name(pol.policy)}")

    cash = step(r, "GetCashLimits", client.get_cash_limits)
    if cash is not None:
        print(f"      currencies={[lim.currency for lim in cash.limits]}")

    perms = step(r, "ListPermissions", client.list_permissions)
    if perms is not None:
        print(f"      catalog={len(perms.permissions)} permissions")

    pnl = step(r, "GetPnl", client.get_pnl)
    if pnl is not None:
        print(
            f"      per_contract={len(pnl.per_contract)} "
            f"per_vm={len(pnl.per_vm)} compute_us={pnl.compute_us}"
        )

    pt = step(
        r,
        "ListPublicTrades limit=10",
        lambda: client.list_public_trades(limit=10),
    )
    if pt is not None:
        print(f"      trades={len(pt.trades)}")

    contracts = step(
        r, f"ListContracts area={area}", lambda: client.list_contracts(area_id=area)
    )
    contract_id = 0
    contract_prod = ""
    contract_dlvry = ""
    if contracts is not None and contracts.contracts:
        # Prefer an ACTI contract with real metadata (non-empty prod and
        # dlvry_start); the list can lead with metadata-less placeholder
        # entries (order-book data seen before the ContractInfoRprt) that
        # never produce stream activity and break the by-delivery lookup.
        c = next(
            (
                c
                for c in contracts.contracts
                if c.state == ContractState.ACTI and c.prod and c.dlvry_start
            ),
            contracts.contracts[0],
        )
        contract_id = c.contract_id
        contract_prod = c.prod
        contract_dlvry = c.dlvry_start
        print(
            f"      {len(contracts.contracts)} contracts; "
            f"picked id={contract_id} prod={contract_prod!r} start={contract_dlvry!r}"
        )

    if contract_id:
        step(
            r,
            f"GetContract id={contract_id}",
            lambda: client.get_contract(area_id=area, contract_id=contract_id),
        )
        if contract_prod and contract_dlvry:
            step(
                r,
                "GetContractByDelivery",
                lambda: client.get_contract_by_delivery(
                    area_id=area, prod=contract_prod, dlvry_start=contract_dlvry
                ),
            )
        step(
            r,
            "ListOrders (scoped)",
            lambda: client.list_orders(
                delivery_area=area, contract_id=int(contract_id)
            ),
        )
    else:
        skip(r, "GetContract", "no contracts available")
        skip(r, "GetContractByDelivery", "no contracts available")
        skip(r, "ListOrders (scoped)", "no contracts available")

    step(r, "ListOrders (all)", client.list_orders)
    step(r, "ListMembers", client.list_members)
    step(r, "GetMyMembers", client.get_my_members)

    # Hub-to-hub ATC matrix (read-only); window the next 24h out of `area`.
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    win_from = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    win_to = (now + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    h2h = step(
        r,
        f"GetHub2Hub from={area}",
        lambda: client.get_hub2hub(
            delivery_area_from=area, delivery_from=win_from, delivery_to=win_to
        ),
    )
    if h2h is not None:
        print(
            f"      enabled={h2h.enabled} "
            f"capacity_connected={h2h.capacity_connected} rows={len(h2h.data)}"
        )

    # User-management reads, gated on ManageUsers.
    users = gated(r, "ListUsers", client.list_users)
    if users is not None:
        print(f"      {len(users.users)} users")
        target = me.id if me is not None else (
            users.users[0].id if users.users else ""
        )
        if target:
            um = gated(
                r,
                "GetUserMembers (self)",
                lambda: client.get_user_members(user_id=target),
            )
            if um is not None:
                print(f"      member_ids={len(um.member_ids)}")

    # Audit / M7-error queries gated on permission (read_audit / read_m7_errors).
    for name, call in (
        ("QueryAuditOrders", lambda: client.query_audit_orders(limit=5)),
        ("QueryAuditTrades", lambda: client.query_audit_trades(limit=5)),
        ("QueryAuditPublicTrades", lambda: client.query_audit_public_trades(limit=5)),
        ("QueryAuditEvents", lambda: client.query_audit_events(limit=5)),
        ("QueryM7Errors", lambda: client.query_m7_errors(limit=5)),
    ):
        try:
            out = call()
            print(
                f"  → {name} limit=5 ... "
                f"[PASS] items={len(out.items)} next_cursor={out.next_cursor!r}"
            )
            r.passed += 1
        except PermissionDenied:
            skip(r, name, "permission not granted")
        except VoltnirError as e:
            print(f"  → {name} limit=5 ... [FAIL] {e.code.name}: {e.message}")
            r.failed += 1
            r.failures.append(f"{name}: {e.code.name}: {e.message}")

    # Export streams, gated on ExportReports. Window the last 24h, drain
    # the chunk stream, and report the byte count.
    exp_from = (now - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    exp_to = win_from
    for name, call in (
        (
            "ExportOrders",
            lambda: client.export_orders(
                format=ExportFormat.JSON, from_=exp_from, to=exp_to
            ),
        ),
        (
            "ExportTrades",
            lambda: client.export_trades(
                format=ExportFormat.JSON, from_=exp_from, to=exp_to
            ),
        ),
    ):
        out = gated(r, name, lambda call=call: sum(len(c.data) for c in call()))
        if out is not None:
            print(f"      {out} bytes")

    # Polled live streams (WatchState / WatchPnl) emit an immediate frame on
    # subscribe, so a bounded read is a reliable smoke. The append-only tails
    # (WatchMessages / WatchTrades / WatchPublicTrades / WatchAuditEvents /
    # WatchM7Errors) can legitimately stay silent on a quiet sim, so they're
    # left to the unit suite rather than risking a hang here.
    def _watch_state_smoke() -> str:
        for ev in client.watch_state(timeout=15.0):
            return f"operational={ev.operational}"
        raise AssertionError("no SystemState frame within deadline")

    out = step(r, "WatchState (first frame)", _watch_state_smoke)
    if out is not None:
        print(f"      {out}")

    # WatchStatus is polled like WatchState, so a frame is guaranteed, but it
    # is gated on read_status: `gated` keeps the frame assertion strict while
    # letting a key without the permission [SKIP] instead of [FAIL].
    def _watch_status_smoke() -> str:
        for ev in client.watch_status(timeout=15.0):
            return (
                f"trading_enabled={ev.trading_enabled} "
                f"order_pos_limit={ev.order_pos_limit}"
            )
        raise AssertionError("no SystemStatus frame within deadline")

    out = gated(r, "WatchStatus (first frame)", _watch_status_smoke)
    if out is not None:
        print(f"      {out}")

    def _watch_pnl_smoke() -> str:
        for ev in client.watch_pnl(timeout=15.0):
            return f"per_contract={len(ev.per_contract)} per_vm={len(ev.per_vm)}"
        raise AssertionError("no PnlSnapshot frame within deadline")

    out = step(r, "WatchPnl (first frame)", _watch_pnl_smoke)
    if out is not None:
        print(f"      {out}")

    # WatchOrders / WatchTrades open with a SNAPSHOT, so a bounded first-frame
    # read is reliable.
    def _watch_orders_smoke() -> str:
        for ev in client.watch_orders(timeout=15.0):
            return f"type={ev.type} orders={len(ev.orders)}"
        raise AssertionError("no OrdersEvent within deadline")

    out = step(r, "WatchOrders (snapshot)", _watch_orders_smoke)
    if out is not None:
        print(f"      {out}")

    def _watch_trades_smoke() -> str:
        for ev in client.watch_trades(timeout=15.0):
            return f"type={ev.type} trades={len(ev.trades)}"
        raise AssertionError("no TradeEvent within deadline")

    out = step(r, "WatchTrades (snapshot)", _watch_trades_smoke)
    if out is not None:
        print(f"      {out}")

    # Append-only / events-only tails subscribe cleanly; a frame or a clean
    # short deadline both pass (audit / m7 also exercise the permission gate).
    subscribe_smoke(
        r, "WatchPublicTrades", lambda: client.watch_public_trades(timeout=5.0)
    )
    subscribe_smoke(r, "WatchMessages", lambda: client.watch_messages(timeout=5.0))
    subscribe_smoke(
        r, "WatchAuditEvents", lambda: client.watch_audit_events(timeout=5.0)
    )
    subscribe_smoke(r, "WatchM7Errors", lambda: client.watch_m7_errors(timeout=5.0))

    # Streaming smoke: WatchContract first event must be SNAPSHOT and
    # every event type must be in the declared vocabulary. Bounded by a
    # gRPC deadline so a quiet contract can't hang the runner: the
    # SNAPSHOT is mandatory; further live events are best-effort.
    if contract_id:
        def _watch_smoke() -> str:
            from voltnir_sdk import DeadlineExceeded
            from voltnir_sdk._generated import voltnir_api_v1_pb2 as pb2

            et = pb2.ContractEvent.EventType
            stream = client.watch_contract(
                area_id=area, contract_id=contract_id, timeout=30.0
            )
            seen = 0
            kinds: list[int] = []
            timed_out = False
            try:
                for ev in stream:
                    kinds.append(ev.type)
                    seen += 1
                    if seen >= max(1, watch_events):
                        break
            except DeadlineExceeded:
                timed_out = True
            assert kinds, "no events received (not even the SNAPSHOT)"
            assert kinds[0] == et.SNAPSHOT, (
                f"first event must be SNAPSHOT, got {et.Name(kinds[0])}"
            )
            known = {et.SNAPSHOT, et.ORDER_BOOK_UPDATE, et.STATE_CHANGE, et.TRADE}
            unknown = [k for k in kinds if k not in known]
            assert not unknown, f"unknown event types on the wire: {unknown}"
            names = ",".join(et.Name(k) for k in kinds)
            note = " (deadline before further live events; quiet contract)" if timed_out else ""
            return f"received {seen} event(s): {names}{note}"

        out = step(r, "WatchContract (smoke)", _watch_smoke)
        if out is not None:
            print(f"      {out}")
    else:
        skip(r, "WatchContract (smoke)", "no contract available")

    return r


# ────────────────────────────────────────────────────────────────────────────
# Sync pass: mutating tail
# ────────────────────────────────────────────────────────────────────────────


def _dlvry_start_is_safely_ahead(dlvry_start: str, margin_min: int = 20) -> bool:
    """True when the contract's delivery starts at least `margin_min`
    minutes from now, far enough that M7 gate closure can't reject the
    test order mid-run. Unparseable/empty timestamps return False."""
    from datetime import datetime, timedelta, timezone

    try:
        start = datetime.fromisoformat(dlvry_start.replace("Z", "+00:00"))
    except ValueError:
        return False
    return start >= datetime.now(timezone.utc) + timedelta(minutes=margin_min)


def _find_active_contract(
    client: VoltnirClient, area: str, contracts: list, max_probes: int = 30
) -> str:
    """Return the contract_id of an ACTI contract that is safe to order on.

    Some list entries are metadata-less placeholders (order-book data seen
    before the ContractInfoRprt), and the entries closest to delivery may
    already be past M7 gate closure even while still listed ACTI, and a test
    order on those is rejected ("Contract … not active for Delivery
    Area"). User-defined block contracts (`predefined is False`) only accept
    block orders; a regular order on them is rejected with "Can't enter OPEN
    order for user-defined blocks", so they are skipped too. Prefer an ACTI,
    non-block contract whose delivery starts comfortably in the future; fall
    back to any ACTI non-block entry, then to probing via GetContract.
    """
    for c in contracts:
        if (
            c.state == ContractState.ACTI
            and c.predefined
            and _dlvry_start_is_safely_ahead(c.dlvry_start)
        ):
            return c.contract_id
    for c in contracts:
        if c.state == ContractState.ACTI and c.predefined:
            return c.contract_id
    for c in contracts[:max_probes]:
        try:
            detail = client.get_contract(area_id=area, contract_id=c.contract_id)
        except VoltnirError:
            continue
        if detail.contract.state == ContractState.ACTI and detail.contract.predefined:
            return detail.contract.contract_id
    return ""


def run_sync_mutate(client: VoltnirClient, area: str) -> Result:
    """Submit a hibernated order, look it up, watch for one event, cancel."""
    r = Result()
    print("\n[sync] mutate pass: hibernated order lifecycle")

    contracts = step(
        r,
        f"ListContracts area={area}",
        lambda: client.list_contracts(area_id=area),
    )
    if contracts is None or not contracts.contracts:
        skip(r, "submit/get/watch/cancel", "no contracts available")
        return r

    contract_id = _find_active_contract(client, area, list(contracts.contracts))
    if not contract_id:
        skip(
            r,
            "submit/get/watch/cancel",
            "no ACTI contract found in the first 30 list entries",
        )
        return r
    print(f"      active contract id={contract_id}")

    # The fresh-DB default order position limit (the `contract_limit` knob,
    # i.e. order_pos_limit in sub-MW) is tiny, so even a 0.100 MW hibernated
    # order trips "position limit exceeded". Raise it for the lifecycle and
    # restore the prior value before returning (no net operator-state change).
    prior_pos_limit = None
    prior_cash_cents = None
    try:
        prior_pos_limit = client.get_contract_limit().quantity
        client.set_contract_limit(quantity=1_000_000_000)
        # A fresh DB also seeds the ECC fail-closed cash default (a 0/unset
        # cash limit means "no trading"), so the order also trips "cash limit
        # exceeded". Set a generous EUR House limit for the lifecycle and
        # restore the prior value after, keeping the fail-closed guard on,
        # the real operator workflow rather than disabling the guard.
        prior_cash_cents = client.get_cash_limit().cents
        client.set_cash_limit(cents=1_000_000_000_000, currency="eur")
    except Exception as e:  # noqa: BLE001 (best-effort setup on a throwaway sim)
        print(f"      (warning: could not relax order limits: {e})")

    def _restore_limits() -> None:
        if prior_pos_limit is not None:
            try:
                client.set_contract_limit(quantity=prior_pos_limit)
            except Exception as e:  # noqa: BLE001 (best-effort restore)
                print(f"      (warning: could not restore position limit: {e})")
        if prior_cash_cents is not None:
            try:
                client.set_cash_limit(cents=prior_cash_cents, currency="eur")
            except Exception as e:  # noqa: BLE001 (best-effort restore)
                print(f"      (warning: could not restore cash limit: {e})")

    submit = step(
        r,
        f"SubmitOrder HIBE contract={contract_id}",
        # quantity in sub-MW: M7 minimum is 0.100 MW = 100 sub-MW.
        # 100 cents = 1.00 CCY/MWh, well below any sensible bid, so the order
        # can never cross even if it accidentally activates. The parameter
        # names carry the unit, so this cannot be misread as 100 CCY/MWh.
        lambda: client.submit_order(
            client_order_id=new_client_order_id(),
            side=Side.BUY,
            price_cents=100,      # 1.00 CCY/MWh
            quantity_sub_mw=100,  # 0.1 MW
            delivery_area_id=area,
            contract_id=int(contract_id),
            order_type=OrderType.REGULAR,
            entry_state="HIBE",
        ),
    )
    if submit is None or not getattr(submit, "client_order_id", ""):
        _restore_limits()
        return r
    coid = submit.client_order_id
    print(f"      client_order_id={coid!r}")

    # Wait until M7 has acked the order. Until then, GetOrder returns it as
    # `pending` (WatchOrder would open with a PENDING snapshot). Poll for
    # up to 5s so the rest of the lifecycle runs against a confirmed order.
    def _wait_confirmed() -> str:
        from voltnir_sdk import OrderState

        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            resp = client.get_order(client_order_id=coid)
            if resp.HasField("confirmed"):
                if resp.confirmed.state == OrderState.REJECTED:
                    # Surface the M7 rejection text at the step where it
                    # happened instead of letting CancelOrder fail later.
                    raise AssertionError(
                        f"order rejected by M7: {resp.confirmed.text!r}"
                    )
                return f"confirmed order_id={resp.confirmed.order_id}"
            time.sleep(0.1)
        raise TimeoutError("order still pending after 5s")

    out = step(r, f"GetOrder until confirmed coid={coid}", _wait_confirmed)
    if out is not None:
        print(f"      {out}")
    confirmed = out is not None

    if confirmed:
        def _watch_one() -> str:
            stream = client.watch_order(client_order_id=coid)
            for ev in stream:
                stream.close()
                return f"first type={ev.type}"
            return "stream ended without events"

        step(r, "WatchOrder (one event)", _watch_one)

        # ModifyOrder: reprice the still-hibernated order (price/quantity use
        # protobuf wrappers; price stays far below any crossable bid).

        step(
            r,
            "ModifyOrder (reprice)",
            lambda: client.modify_order(
                client_order_id=coid,
                action=ModifyAction.MODIFY,
                price_cents=110,
                quantity_sub_mw=100,
            ),
        )

        # The modify is async at M7; cancelling before it confirms is rejected
        # with ABORTED "modify in progress". Retry until the modify settles.
        def _cancel_after_modify() -> str:
            from voltnir_sdk import Aborted

            deadline = time.monotonic() + 5.0
            while True:
                try:
                    client.cancel_order(client_order_id=coid)
                    return "cancelled"
                except Aborted as e:
                    if "modify in progress" in e.message and time.monotonic() < deadline:
                        time.sleep(0.2)
                        continue
                    raise

        step(r, f"CancelOrder coid={coid}", _cancel_after_modify)
    else:
        skip(r, "WatchOrder (one event)", "order never confirmed")
        skip(r, "ModifyOrder (reprice)", "order never confirmed")
        skip(r, "CancelOrder", "order never confirmed, nothing to cancel")

    # CancelAllOrders is safe cleanup: our single test order is already gone, so
    # this cancels nothing (or only stray residue from a prior aborted run).
    step(r, "CancelAllOrders", client.cancel_all_orders)

    _restore_limits()
    return r


def _relax_order_limits(client: VoltnirClient):
    """Raise the position and cash limits for a probe, returning a restorer.

    A fresh DB seeds a tiny order position limit and an ECC fail-closed cash
    default (a 0/unset limit means "no trading"), so even a 0.1 MW hibernated
    order trips both. Raise them for the duration and put the prior values back,
    keeping the fail-closed guard ON: the real operator workflow, not disabling
    the guard. Best-effort on a throwaway sim; failures are warned about rather
    than aborting the run.
    """
    prior_pos = None
    prior_cash = None
    try:
        prior_pos = client.get_contract_limit().quantity
        client.set_contract_limit(quantity=1_000_000_000)
        prior_cash = client.get_cash_limit().cents
        client.set_cash_limit(cents=1_000_000_000_000, currency="eur")
    except Exception as e:  # noqa: BLE001 (best-effort setup)
        print(f"      (warning: could not relax order limits: {e})")

    def _restore() -> None:
        if prior_pos is not None:
            try:
                client.set_contract_limit(quantity=prior_pos)
            except Exception as e:  # noqa: BLE001 (best-effort restore)
                print(f"      (warning: could not restore position limit: {e})")
        if prior_cash is not None:
            try:
                client.set_cash_limit(cents=prior_cash, currency="eur")
            except Exception as e:  # noqa: BLE001 (best-effort restore)
                print(f"      (warning: could not restore cash limit: {e})")

    return _restore


# ────────────────────────────────────────────────────────────────────────────
# Sync pass: timeout -> reconciliation (the ambiguity path)
# ────────────────────────────────────────────────────────────────────────────


def run_sync_reconciliation(client: VoltnirClient, area: str) -> Result:
    """Exercise the one path a fake server cannot verify: an ambiguous failure.

    This is the most expensive thing in the SDK to get wrong. When an order RPC
    fails without proving it had no effect, the trader has to answer "is my
    order on the book?", and the SDK's entire answer is: catch
    `OrderOutcomeUnknown`, then reconcile with `get_order(client_order_id=...)`.
    Every part of that advice is unverified against a real gateway until this
    runs.

    The probe forces a CLIENT-side deadline by submitting with a deliberately
    tiny timeout. That is not a synthetic condition; it is exactly the failure a
    desk hits on a slow link, and it leaves the genuinely ambiguous state (the
    order may or may not have reached M7) that reconciliation exists to resolve.

    Three properties, in order of what they cost to get wrong:

    1. The failure raises `OrderOutcomeUnknown`, not `DeadlineExceeded`. A desk
       that reads "deadline exceeded" as "it failed" resubmits and doubles up.
    2. `get_order(client_order_id=...)` returns a DEFINITIVE answer. Either
       answer is a pass; what must not happen is an unresolvable state.
    3. If the order did land, resubmitting the SAME `client_order_id` is
       REJECTED. That is the guarantee making a mistaken retry safe, and it has
       never been tested against a live gateway.

    Safety: the order is hibernated (`entry_state="HIBE"`, never exposed to the
    market) and priced far below anything crossable, and cleanup runs on every
    exit path. A cleanup failure is reported loudly rather than swallowed.
    """
    r = Result()
    print("\n[sync] reconciliation pass: ambiguous failure -> definitive answer")

    contracts = step(
        r, f"ListContracts area={area}", lambda: client.list_contracts(area_id=area)
    )
    if contracts is None or not contracts.contracts:
        skip(r, "timeout/reconcile probes", "no contracts available")
        return r

    contract_id = _find_active_contract(client, area, list(contracts.contracts))
    if not contract_id:
        skip(r, "timeout/reconcile probes", "no ACTI contract found")
        return r
    print(f"      probing on contract id={contract_id}")

    # The fresh-DB position and cash defaults reject even a 0.1 MW hibernated
    # order, exactly as in the lifecycle pass. Relax for the probes and restore
    # afterwards, so the pass leaves no net operator-state change.
    restore = _relax_order_limits(client)
    try:
        return _reconciliation_probes(r, client, area, contract_id)
    finally:
        restore()


def _reconciliation_probes(
    r: Result, client: VoltnirClient, area: str, contract_id: str
) -> Result:
    # Two probes: a deadline so short the request almost certainly never left,
    # and a longer one that may well have reached M7. Both must reconcile to a
    # definitive answer; only the second is likely to exercise the "it really is
    # resting" branch. Running both avoids guessing a magic number that happens
    # to work on one deployment's latency.
    for label, deadline_s in (("never-left", 0.001), ("may-have-landed", 0.08)):
        coid = new_client_order_id()
        answered = False

        def _probe(coid=coid, deadline_s=deadline_s) -> str:
            nonlocal answered
            try:
                client.submit_order(
                    client_order_id=coid,
                    side=Side.BUY,
                    price_cents=100,      # 1.00 CCY/MWh, never crossable
                    quantity_sub_mw=100,  # 0.1 MW
                    delivery_area_id=area,
                    contract_id=int(contract_id),
                    order_type=OrderType.REGULAR,
                    entry_state="HIBE",
                    timeout=deadline_s,
                )
            except OrderOutcomeUnknown as e:
                if e.client_order_id != coid:
                    raise AssertionError(
                        f"OrderOutcomeUnknown lost the client_order_id: "
                        f"{e.client_order_id!r} != {coid!r}"
                    )
                if e.request_definitely_rejected:
                    raise AssertionError(
                        "OrderOutcomeUnknown claims the request was definitely "
                        "rejected, which defeats the point of the type"
                    )
                return f"OrderOutcomeUnknown as expected ({e.code.name})"
            except DeadlineExceeded as e:
                # The exact misclassification this pass exists to catch.
                raise AssertionError(
                    f"a deadline on submit_order raised DeadlineExceeded "
                    f"({e.message}), not OrderOutcomeUnknown: a desk reading "
                    f"that as 'definitely failed' would resubmit and double up"
                ) from e
            answered = True
            return "no timeout (server answered first)"

        out = step(r, f"SubmitOrder timeout probe [{label}]", _probe)
        if out is None:
            _reconcile_cleanup(r, client, coid, label)
            continue
        print(f"      {out}")

        if answered:
            # Not an SDK failure; the probe simply did not trip. Say so, rather
            # than reporting a pass that proved nothing.
            skip(
                r,
                f"Reconcile after timeout [{label}]",
                "server answered before the deadline; ambiguity not exercised",
            )
            _reconcile_cleanup(r, client, coid, label)
            continue

        def _reconcile(coid=coid) -> str:
            # NOT_FOUND is NOT immediately conclusive. The submit may still be
            # in flight server-side, so an order that is about to exist reads as
            # absent for a moment. Concluding "never landed" on the first
            # NOT_FOUND is the dangerous direction: it is precisely what makes a
            # desk resubmit an order that then appears, doubling the position.
            # Only a NOT_FOUND that persists across the whole window is an
            # answer.
            deadline = time.monotonic() + 5.0
            saw_absent = False
            saw_pending = False
            while time.monotonic() < deadline:
                try:
                    resp = client.get_order(client_order_id=coid)
                except NotFound:
                    saw_absent = True
                    time.sleep(0.2)
                    continue
                if resp.HasField("confirmed"):
                    return (
                        f"definitive: order IS live "
                        f"(order_id={resp.confirmed.order_id})"
                    )
                if resp.HasField("pending"):
                    saw_pending = True
                    time.sleep(0.2)
                    continue
                saw_absent = True
                time.sleep(0.2)

            if saw_pending:
                # Still mid-flight after the window. Genuinely unresolved, and
                # saying so is the honest outcome: the desk must keep watching,
                # not resubmit.
                raise AssertionError(
                    "reconciliation never resolved (still pending after 5s): a "
                    "desk cannot decide whether to resubmit"
                )
            if saw_absent:
                return "definitive: order never landed (absent for the full window)"
            raise AssertionError("reconciliation produced no observation at all")

        verdict = step(r, f"Reconcile after timeout [{label}]", _reconcile)
        if verdict is not None:
            print(f"      {verdict}")

        if verdict and "IS live" in verdict:
            def _reuse_key(coid=coid) -> str:
                try:
                    client.submit_order(
                        client_order_id=coid,
                        side=Side.BUY,
                        price_cents=100,
                        quantity_sub_mw=100,
                        delivery_area_id=area,
                        contract_id=int(contract_id),
                        order_type=OrderType.REGULAR,
                        entry_state="HIBE",
                    )
                except VoltnirError as e:
                    return f"correctly refused ({e.code.name}): {e.message[:60]}"
                raise AssertionError(
                    "resubmitting a LIVE client_order_id was ACCEPTED: the "
                    "idempotency guarantee that the retry advice depends on "
                    "does not hold, and a retry after an ambiguous failure "
                    "would double the position"
                )

            out = step(r, f"Reuse client_order_id while live [{label}]", _reuse_key)
            if out is not None:
                print(f"      {out}")
        else:
            skip(
                r,
                f"Reuse client_order_id while live [{label}]",
                "order did not land, nothing to collide with",
            )

        _reconcile_cleanup(r, client, coid, label)

    return r


def _reconcile_cleanup(
    result: Result, client: VoltnirClient, coid: str, label: str
) -> None:
    """Cancel a probe order if it exists. Report loudly if it might not have.

    An order left resting is the one genuinely harmful outcome of this pass, so
    a cleanup failure is a FAIL with the client_order_id printed, never a
    swallowed exception. Only this probe's own order is ever cancelled: a
    cancel_all here would take out the desk's real book.
    """
    try:
        resp = client.get_order(client_order_id=coid)
    except NotFound:
        return
    except VoltnirError as e:
        result.failed += 1
        result.failures.append(
            f"cleanup [{label}]: could not determine state of {coid}: {e.message}"
        )
        print(f"  → cleanup [{label}] ... [FAIL] state unknown for {coid}")
        return

    if not (resp.HasField("confirmed") or resp.HasField("pending")):
        return

    try:
        client.cancel_order(client_order_id=coid)
        print(f"  → cleanup [{label}] ... [PASS] cancelled probe order {coid}")
        result.passed += 1
    except VoltnirError as e:
        result.failed += 1
        result.failures.append(
            f"cleanup [{label}]: PROBE ORDER MAY STILL BE RESTING, "
            f"client_order_id={coid}: {e.message}"
        )
        print(
            f"  → cleanup [{label}] ... [FAIL] could not cancel {coid} "
            f"({e.code.name}) - CHECK THE BOOK"
        )


# ────────────────────────────────────────────────────────────────────────────
# Sync pass: operator round-trips (read current value, set it back)
# ────────────────────────────────────────────────────────────────────────────


def run_sync_operator(client: VoltnirClient) -> Result:
    """Exercise the operator Set* RPCs without net state change: read the
    current value, then set it straight back. Each Set is gated on its own
    permission, so a read-only key just skips them."""
    r = Result()
    print("\n[sync] operator pass: read-then-restore (no net state change)")

    pol = step(r, "GetSelfTradePolicy", client.get_self_trade_policy)
    if pol is not None:
        name = SelfTradePolicy.Name(pol.policy)
        short = name.removeprefix("SELF_TRADE_POLICY_").lower()
        if short in ("observe", "reject"):
            gated(
                r,
                "SetSelfTradePolicy (restore)",
                lambda: client.set_self_trade_policy(policy=short),
            )
        else:
            skip(r, "SetSelfTradePolicy (restore)", f"unrestorable policy {name}")

    cl = step(r, "GetContractLimit", client.get_contract_limit)
    if cl is not None:
        gated(
            r,
            "SetContractLimit (restore)",
            lambda: client.set_contract_limit(quantity=cl.quantity),
        )

    ca = step(r, "GetCashLimit", client.get_cash_limit)
    if ca is not None:
        gated(
            r,
            "SetCashLimit (restore EUR)",
            lambda: client.set_cash_limit(cents=ca.cents, currency="eur"),
        )

    ta = step(r, "GetTradingAllowed", client.get_trading_allowed)
    if ta is not None:
        gated(
            r,
            "SetTradingAllowed (restore)",
            lambda: client.set_trading_allowed(allowed=ta.allowed),
        )

    cfc = step(r, "GetCashFailClosed", client.get_cash_fail_closed)
    if cfc is not None:
        gated(
            r,
            "SetCashFailClosed (restore)",
            lambda: client.set_cash_fail_closed(enabled=cfc.enabled),
        )

    # Holiday calendars. Two different restore shapes:
    #   SetHolidays  replaces a whole calendar, so writing back what was read
    #                is a no-op in the same read-then-restore style as above.
    #   Add/Remove   are inherently incremental, so they are exercised as a
    #                matched pair on a throwaway sentinel date that is removed
    #                again immediately. The date is deliberately far-future and
    #                labelled, so if a run dies between the two the leftover is
    #                obvious and harmless (the exposure window never reaches it).
    hol = step(r, "GetHolidays", client.get_holidays)
    if hol is not None:
        gated(
            r,
            "SetHolidays (restore EUR)",
            lambda: client.set_holidays(currency="eur", holidays=list(hol.eur)),
        )
        gated(
            r,
            "SetHolidays (restore GBP)",
            lambda: client.set_holidays(currency="gbp", holidays=list(hol.gbp)),
        )

        sentinel = "2099-01-01"
        added = gated(
            r,
            f"AddHoliday (sentinel {sentinel})",
            lambda: client.add_holiday(
                currency="eur", date=sentinel, label="voltnir verify.py sentinel"
            ),
        )
        if added is not None:
            present = any(h.date == sentinel for h in added.eur)
            if not present:
                r.failed += 1
                r.failures.append(
                    f"AddHoliday: {sentinel} absent from the returned EUR calendar"
                )
                print(f"      WARNING: {sentinel} not in the response calendar")
            gated(
                r,
                f"RemoveHoliday (sentinel {sentinel})",
                lambda: client.remove_holiday(currency="eur", date=sentinel),
            )
        else:
            # AddHoliday skipped (no set_cash_limit) or failed. Either way the
            # sentinel was never written, so removing it would be a spurious
            # NOT_FOUND rather than a real signal.
            skip(r, f"RemoveHoliday (sentinel {sentinel})", "AddHoliday did not run")

    return r


# ────────────────────────────────────────────────────────────────────────────
# Sync pass: user-management lifecycle (throwaway user)
# ────────────────────────────────────────────────────────────────────────────


def run_sync_user_lifecycle(client: VoltnirClient) -> Result:
    """Create a throwaway user, exercise every user RPC against it, delete it.
    Gated on ManageUsers; skips wholesale if the key lacks it. RotateApiKey
    runs on the throwaway (never the caller), so the verify key keeps working."""
    r = Result()
    print("\n[sync] user-management lifecycle (throwaway user)")

    uname = f"verify-tmp-{int(time.time())}"
    created = gated(
        r,
        f"CreateUser {uname}",
        lambda: client.create_user(username=uname, permissions=["read_pnl"]),
    )
    if created is None:
        skip(r, "Set/Rotate/Delete user", "user not created")
        return r
    uid = created.user.id
    print(f"      id={uid} short_id={created.user.short_id!r}")

    step(r, "ListUsers", client.list_users)
    step(
        r,
        "SetPermissions",
        lambda: client.set_permissions(
            user_id=uid, permissions=["read_pnl", "read_orders"]
        ),
    )
    step(r, "GetUserMembers", lambda: client.get_user_members(user_id=uid))
    step(
        r,
        "SetUserMembers (empty)",
        lambda: client.set_user_members(user_id=uid, member_ids=[]),
    )
    step(r, "RotateApiKey", lambda: client.rotate_api_key(user_id=uid))
    step(r, "DeleteUser", lambda: client.delete_user(user_id=uid))

    return r


# ────────────────────────────────────────────────────────────────────────────
# Sync pass: member lifecycle (Create + Patch; no DeleteMember RPC exists)
# ────────────────────────────────────────────────────────────────────────────


def run_sync_member_lifecycle(client: VoltnirClient) -> Result:
    """Create a throwaway virtual member and patch it inactive. Gated on
    ManageMembers. NOTE: there is no DeleteMember RPC, so a created member is
    left deactivated (residue), acceptable on the sim and flagged here."""
    r = Result()
    print("\n[sync] member lifecycle (CreateMember leaves a deactivated residue)")

    mname = f"verify-tmp-{int(time.time())}"
    member = gated(
        r,
        f"CreateMember {mname}",
        lambda: client.create_member(name=mname, max_position=1000),
    )
    if member is None:
        skip(r, "PatchMember", "member not created")
        return r
    print(f"      id={member.id} short_id={member.short_id!r}")

    if not member.id:
        # A member with no id cannot be patched: the id is the whole selector.
        # Guarding here keeps the failure honest (a [SKIP] naming the reason)
        # instead of a client-side validation error that reads like a bug in
        # this runner.
        skip(r, "PatchMember (deactivate)", "CreateMember returned no id")
        return r

    # Plain `False`, not BoolValue(value=False): the SDK wraps it now, so the
    # caller no longer needs to know the wire uses google.protobuf wrappers.
    step(
        r,
        "PatchMember (deactivate)",
        lambda: client.patch_member(id=member.id, active=False),
    )

    return r


# ────────────────────────────────────────────────────────────────────────────
# Async pass: sanity-check the second facade
# ────────────────────────────────────────────────────────────────────────────


async def run_async_smoke(
    host: str,
    port: int,
    api_key: str,
    tls: bool,
    ca_cert_path: str | None,
    area: str,
) -> Result:
    r = Result()
    print("\n[async] smoke pass")
    async with AsyncVoltnirClient(
        host=host,
        port=port,
        api_key=api_key,
        tls=tls,
        ca_cert_path=ca_cert_path,
    ) as c:
        try:
            me = await c.get_me()
            print(f"  → GetMe ... [PASS] user={me.username!r}")
            r.passed += 1
        except VoltnirError as e:
            print(f"  → GetMe ... [FAIL] {e.code.name}: {e.message}")
            r.failed += 1
            r.failures.append(f"async GetMe: {e.code.name}: {e.message}")

        try:
            await c.get_state()
            print("  → GetState ... [PASS]")
            r.passed += 1
        except VoltnirError as e:
            print(f"  → GetState ... [FAIL] {e.code.name}: {e.message}")
            r.failed += 1

        try:
            cs = await c.list_contracts(area_id=area)
            print(
                f"  → ListContracts area={area} ... [PASS] "
                f"{len(cs.contracts)} contracts"
            )
            r.passed += 1
            if cs.contracts:
                # Same selection rule as the sync pass: prefer an ACTI
                # contract with real metadata over leading placeholder
                # entries, and bound the stream with a deadline so a quiet
                # contract cannot hang the runner.
                pick = next(
                    (
                        c2
                        for c2 in cs.contracts
                        if c2.state == ContractState.ACTI
                        and c2.predefined
                        and c2.prod
                        and c2.dlvry_start
                    ),
                    cs.contracts[0],
                )
                cid = pick.contract_id
                # async streaming sanity: pull one event then bail out
                stream = c.watch_contract(
                    area_id=area, contract_id=cid, timeout=30.0
                )
                async for ev in stream:
                    print(
                        f"  → WatchContract id={cid} ... [PASS] "
                        f"first type={ev.type}"
                    )
                    r.passed += 1
                    break
        except VoltnirError as e:
            print(f"  → ListContracts/WatchContract ... [FAIL] {e.code.name}: {e.message}")
            r.failed += 1
            r.failures.append(
                f"async ListContracts/WatchContract: {e.code.name}: {e.message}"
            )

    return r


# ────────────────────────────────────────────────────────────────────────────
# Entry point
# ────────────────────────────────────────────────────────────────────────────


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Voltnir gRPC SDK end-to-end verification runner.",
    )
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=3443)
    p.add_argument("--api-key", required=True)
    p.add_argument("--tls", action="store_true", help="enable TLS")
    p.add_argument(
        "--ca",
        dest="ca_cert_path",
        default=None,
        help="trust this PEM as the CA root (for self-signed dev certs)",
    )
    p.add_argument(
        "--area",
        required=True,
        help=(
            "delivery area id (EIC code, deployment-specific; e.g. "
            "10YBE----------2 for Belgium, 10Y1001A1001A82H for Germany; "
            "ask your Voltnir operator for the codes their M7 connection "
            "carries)"
        ),
    )
    p.add_argument(
        "--watch-events",
        type=int,
        default=1,
        help="how many WatchContract events to receive before cancelling",
    )
    p.add_argument(
        "--mutate",
        action="store_true",
        help=(
            "also run the write RPCs: hibernated-order lifecycle "
            "(submit/modify/get/watch/cancel), operator read-then-restore "
            "round-trips, and throwaway user + member lifecycles. Never sends "
            "a live order; member creation leaves a deactivated residue."
        ),
    )
    p.add_argument(
        "--include-restart",
        action="store_true",
        help=(
            "also exercise Restart as the very last step (tears the server "
            "down; the only RPC not covered by --mutate). Off by default."
        ),
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="per-RPC timeout in seconds (default: 10)",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    print(
        f"voltnir-grpc-py-sdk verify | "
        f"host={args.host}:{args.port} tls={args.tls} area={args.area}"
    )

    aggregate = Result()

    recorder = _CallRecorder()
    recorder.install(VoltnirClient, AsyncVoltnirClient)

    try:
        with VoltnirClient(
            host=args.host,
            port=args.port,
            api_key=args.api_key,
            tls=args.tls,
            ca_cert_path=args.ca_cert_path,
            timeout=args.timeout,
        ) as client:
            ro = run_sync_readonly(client, args.area, args.watch_events)
            aggregate.passed += ro.passed
            aggregate.failed += ro.failed
            aggregate.skipped += ro.skipped
            aggregate.failures.extend(ro.failures)

            if args.mutate:
                for sub in (
                    run_sync_mutate(client, args.area),
                    run_sync_reconciliation(client, args.area),
                    run_sync_operator(client),
                    run_sync_user_lifecycle(client),
                    run_sync_member_lifecycle(client),
                ):
                    aggregate.passed += sub.passed
                    aggregate.failed += sub.failed
                    aggregate.skipped += sub.skipped
                    aggregate.failures.extend(sub.failures)
            else:
                print("\n[mutate] skipped (pass --mutate to enable)")
    except Unauthenticated as e:
        print(f"\nAUTH FAILED before any RPC could complete: {e.message}")
        print("Check --api-key.")
        return 2
    except Exception as e:
        print(f"\nFATAL: could not run sync pass: {type(e).__name__}: {e}")
        return 2

    try:
        async_result = asyncio.run(
            run_async_smoke(
                args.host,
                args.port,
                args.api_key,
                args.tls,
                args.ca_cert_path,
                args.area,
            )
        )
        aggregate.passed += async_result.passed
        aggregate.failed += async_result.failed
        aggregate.skipped += async_result.skipped
        aggregate.failures.extend(async_result.failures)
    except Exception as e:
        print(f"\nFATAL: async pass crashed: {type(e).__name__}: {e}")
        aggregate.failed += 1
        aggregate.failures.append(f"async pass: {e}")

    # Restart is the one RPC that tears the server down, so it runs dead last
    # and only when explicitly requested.
    if args.include_restart:
        print("\n[restart] Restart (the server will restart, ending the run)")
        try:
            with VoltnirClient(
                host=args.host,
                port=args.port,
                api_key=args.api_key,
                tls=args.tls,
                ca_cert_path=args.ca_cert_path,
                timeout=args.timeout,
            ) as c:
                c.restart()
            print("  → Restart ... [PASS] accepted")
            aggregate.passed += 1
        except PermissionDenied:
            skip(aggregate, "Restart", "RestartSystem permission not granted")
        except VoltnirError as e:
            # A dropped connection mid-restart is an expected outcome, not a
            # failure; the request was accepted.
            print(
                f"  → Restart ... [PASS] connection dropped on restart "
                f"({e.code.name})"
            )
            aggregate.passed += 1
    else:
        print("\n[restart] skipped (pass --include-restart to exercise Restart)")

    recorder.uninstall()

    print(
        f"\nresult: {aggregate.passed} passed, "
        f"{aggregate.failed} failed, {aggregate.skipped} skipped"
    )
    if aggregate.failures:
        print("failures:")
        for f in aggregate.failures:
            print(f"  - {f}")

    # Coverage line. Not a pass/fail signal: a partial run legitimately leaves
    # RPCs untouched (the write surface needs --mutate, Restart needs
    # --include-restart, contract-scoped steps need a contract on the sim). It
    # exists so an RPC with no step here is VISIBLE rather than silently
    # absent. The hard guarantee is the static AST check in the offline suite,
    # which fails if any wrapper has no call site in this file at all.
    missing = recorder.missing()
    total = recorder.total_declared()
    print(
        f"\ncoverage: attempted {len(recorder.attempted)}/{total} RPCs "
        f"in this run mode"
    )
    if missing:
        print(f"  not attempted ({len(missing)}): {', '.join(missing)}")
        if not (args.mutate and args.include_restart):
            print("  (a full run is: --mutate --include-restart)")

    return 0 if aggregate.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
