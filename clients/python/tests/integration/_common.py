"""Shared helpers for the live integration suite: contract selection, a
hibernated-order lifecycle, and a bounded stream subscribe.

None of these place an order that can trade: the order path always uses the
hibernated entry state and a price far below anything crossable, and every
helper cleans up after itself.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Callable

from voltnir_sdk import (
    ContractState,
    DeadlineExceeded,
    OrderState,
    OrderType,
    Side,
    VoltnirClient,
    VoltnirError,
    new_client_order_id,
)


def new_sync_client(api_key: str) -> VoltnirClient:
    """A sync client pointed at the runner-provided endpoint, for a given key."""
    return VoltnirClient(
        host=os.environ.get("VOLTNIR_IT_HOST", "127.0.0.1"),
        port=int(os.environ.get("VOLTNIR_IT_PORT", "3643")),
        api_key=api_key,
        timeout=15.0,
    )

# A hibernated order priced at 1.00 CCY/MWh for 0.1 MW: below any crossable bid
# and never exposed to the market, so it cannot trade even if it were activated.
_SAFE_PRICE_CENTS = 100
_SAFE_QTY_SUB_MW = 100


def _dlvry_start_safely_ahead(dlvry_start: str, margin_min: int = 20) -> bool:
    """True when delivery starts far enough ahead that gate closure will not
    reject a test order mid-run. Unparseable or empty timestamps are unsafe."""
    try:
        start = datetime.fromisoformat(dlvry_start.replace("Z", "+00:00"))
    except ValueError:
        return False
    return start >= datetime.now(timezone.utc) + timedelta(minutes=margin_min)


# Errors that mean "this contract will not take an order right now" — try the
# next candidate rather than failing. A listed, ACTI contract can still refuse
# an order because its trading session for the area is closed (its delivery is
# too far out for the session to have opened, or too near and past gate
# closure), or because it is a block-only contract.
_TRY_NEXT = (
    "session is closed",
    "not active for delivery",
    "not active for Delivery",
    "user-defined blocks",
    "gate closure",
    "past its gate",
)


def _orderable_candidates(client, area: str) -> list:
    """ACTI, non-block contracts in the continuous trading phase, nearest safe
    delivery first: the ones whose trading session is most likely open right
    now. A listing also carries the contracts the exchange has created but not
    yet opened, with phase "CLSD"; they are skipped."""
    contracts = [
        c
        for c in client.list_contracts(area_id=area).contracts
        if c.state == ContractState.ACTI
        and c.predefined
        and c.trading_phase == "CONT"
        and _dlvry_start_safely_ahead(c.dlvry_start)
    ]
    return sorted(contracts, key=lambda c: c.dlvry_start)


def find_orderable_contract(client, area: str) -> str:
    """The contract_id of an ACTI, non-block contract in `area` (for reads)."""
    candidates = _orderable_candidates(client, area)
    if candidates:
        return candidates[0].contract_id
    for c in client.list_contracts(area_id=area).contracts:
        if c.state == ContractState.ACTI and c.predefined:
            return c.contract_id
    return ""


def submit_hibernated(client, area: str, contract_id: str) -> str:
    """Rest a hibernated order on one contract and return its client_order_id."""
    resp = client.submit_order(
        client_order_id=new_client_order_id(),
        side=Side.BUY,
        price_cents=_SAFE_PRICE_CENTS,
        quantity_sub_mw=_SAFE_QTY_SUB_MW,
        delivery_area_id=area,
        contract_id=int(contract_id),
        order_type=OrderType.REGULAR,
        entry_state="HIBE",
    )
    return resp.client_order_id


def open_hibernated_order(client, area: str, max_tries: int = 20) -> tuple[str, str]:
    """Rest a hibernated order on the nearest contract whose session accepts it.

    Returns ``(client_order_id, contract_id)``. Tries candidates in order,
    skipping the ones the exchange refuses because their session is closed; a
    refusal rests nothing, so retrying is safe. Raises when no contract in the
    area will take an order, which is a real sim-state condition, not a silent
    skip.
    """
    last: Exception | None = None
    for c in _orderable_candidates(client, area)[:max_tries]:
        try:
            return submit_hibernated(client, area, c.contract_id), c.contract_id
        except VoltnirError as e:
            last = e
            if any(s in e.message for s in _TRY_NEXT):
                continue
            raise
    raise AssertionError(
        f"no ACTI contract in area {area} accepted a hibernated order "
        f"(sessions closed?); last refusal: {last}"
    )


def wait_confirmed(client, coid: str, timeout: float = 8.0):
    """Poll get_order until the order leaves the pending state, or time out.

    Returns the confirmed OwnOrder. Raises if the exchange rejected it, so the
    rejection text surfaces here rather than as a later cancel failure.
    """
    import time as _t

    deadline = _t.monotonic() + timeout
    while _t.monotonic() < deadline:
        resp = client.get_order(client_order_id=coid)
        if resp.HasField("confirmed"):
            if resp.confirmed.state == OrderState.REJECTED:
                raise AssertionError(f"order rejected by the exchange: {resp.confirmed.text!r}")
            return resp.confirmed
        _t.sleep(0.1)
    raise TimeoutError(f"order {coid} still pending after {timeout}s")


def cancel_quietly(client, coid: str) -> None:
    """Best-effort cancel of a resting order; a modify may still be settling."""
    import time as _t

    from voltnir_sdk import Aborted

    deadline = _t.monotonic() + 6.0
    while True:
        try:
            client.cancel_order(client_order_id=coid)
            return
        except Aborted as e:
            if "modify in progress" in e.message and _t.monotonic() < deadline:
                _t.sleep(0.2)
                continue
            return
        except VoltnirError:
            return


def subscribe_ok(stream_factory: Callable[[], object]) -> bool:
    """Subscribe to a stream and return once it proves live.

    A frame, a clean close, or an idle deadline all count: append-only tails on
    a quiet sim legitimately send nothing before the bounded deadline. Always
    closes the iterator so no subscription is left open.
    """
    stream = stream_factory()
    try:
        for _ev in stream:
            return True
        return True
    except DeadlineExceeded:
        return True
    finally:
        close = getattr(stream, "close", None)
        if callable(close):
            close()


async def asubscribe_ok(stream) -> bool:
    """Async twin of `subscribe_ok`: a frame, a clean close, or an idle deadline
    all prove the async subscription is live. Always closes the iterator."""
    try:
        async for _ev in stream:
            return True
        return True
    except DeadlineExceeded:
        return True
    finally:
        aclose = getattr(stream, "aclose", None)
        if aclose is not None:
            await aclose()
