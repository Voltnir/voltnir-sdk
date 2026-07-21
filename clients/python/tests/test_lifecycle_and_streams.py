"""Client lifecycle and stream behaviour: happy / fail / edge.

None of this is cosmetic for a desk running the SDK for days at a time. A
channel leaked per reconnect exhausts file descriptors over a trading session.
A deadline that never applies turns a dead peer into a hang rather than an
error. A mid-stream failure that is swallowed means the feed stops and nothing
says so, which is indistinguishable from a quiet market.

So the properties pinned here are: `close()` closes, the context manager closes
on both normal and exceptional exit, the client-wide and per-call deadlines
reach the call, breaking out of a stream releases it, and a stream that fails
partway through raises rather than ending quietly.
"""

from __future__ import annotations

import asyncio
import concurrent.futures

import grpc
import pytest

from voltnir_sdk import (
    AsyncVoltnirClient,
    OrderValidationError,
    PermissionDenied,
    Unavailable,
    VoltnirClient,
    VoltnirError,
)
from voltnir_sdk._generated import voltnir_api_v1_pb2 as pb2
from voltnir_sdk._generated import voltnir_api_v1_pb2_grpc as pb2_grpc

from conftest import FakeVoltAPI


# ── lifecycle: close actually closes ────────────────────────────────────────


def test_fail_rpc_after_close_raises(server):
    """`close()` must really close.

    The visible symptom of a close that does not close is nothing at all, until
    the process runs out of file descriptors, which on a desk happens
    mid-session after enough reconnects.
    """
    c = VoltnirClient(host="127.0.0.1", port=server, api_key="k", timeout=5.0)
    assert c.get_me() is not None
    c.close()

    with pytest.raises(Exception) as excinfo:
        c.get_me()
    assert "closed" in str(excinfo.value).lower()


def test_happy_context_manager_closes_on_normal_exit(server):
    with VoltnirClient(host="127.0.0.1", port=server, api_key="k", timeout=5.0) as c:
        assert c.get_me() is not None

    with pytest.raises(Exception):
        c.get_me()


def test_happy_context_manager_closes_on_exception(server):
    """An exception inside the block must not leak the channel."""
    c = None
    with pytest.raises(RuntimeError):
        with VoltnirClient(host="127.0.0.1", port=server, api_key="k", timeout=5.0) as inner:
            c = inner
            raise RuntimeError("boom")

    with pytest.raises(Exception):
        c.get_me()


def test_edge_double_close_is_idempotent(server):
    c = VoltnirClient(host="127.0.0.1", port=server, api_key="k", timeout=5.0)
    c.close()
    c.close()  # must not raise


async def test_fail_async_rpc_after_close_raises(server):
    c = AsyncVoltnirClient(host="127.0.0.1", port=server, api_key="k", timeout=5.0)
    assert await c.get_me() is not None
    await c.close()

    with pytest.raises(Exception):
        await c.get_me()


async def test_happy_async_context_manager_closes(server):
    async with AsyncVoltnirClient(
        host="127.0.0.1", port=server, api_key="k", timeout=5.0
    ) as c:
        assert await c.get_me() is not None

    with pytest.raises(Exception):
        await c.get_me()


def test_edge_client_timeout_is_applied_to_unary_calls(server, monkeypatch):
    """The client-wide deadline must reach the call.

    A deadline that is silently `None` means a unary call against a dead peer
    blocks forever instead of raising.
    """
    c = VoltnirClient(host="127.0.0.1", port=server, api_key="k", timeout=7.5)
    seen: dict = {}
    original = c._stub.GetMe

    def _spy(request, **kwargs):
        seen.update(kwargs)
        return original(request, **kwargs)

    monkeypatch.setattr(c._stub, "GetMe", _spy)
    c.get_me()
    c.close()

    assert seen["timeout"] == 7.5


def test_edge_per_call_timeout_overrides_the_client_default(server, monkeypatch):
    c = VoltnirClient(host="127.0.0.1", port=server, api_key="k", timeout=7.5)
    seen: dict = {}
    original = c._stub.SubmitOrder

    def _spy(request, **kwargs):
        seen.update(kwargs)
        return original(request, **kwargs)

    monkeypatch.setattr(c._stub, "SubmitOrder", _spy)
    from voltnir_sdk import Side

    c.submit_order(
        client_order_id="11111111-1111-4111-8111-111111111111",
        side=Side.BUY,
        delivery_area_id="10YBE----------2",
        contract_id=1,
        price_cents=5000,
        quantity_sub_mw=1000,
        timeout=2.5,
    )
    c.close()
    assert seen["timeout"] == 2.5


# ── streams: early exit, mid-stream failure, deadlines ──────────────────────


def test_happy_breaking_out_of_a_stream_releases_the_call(client, fake):
    """Breaking out of the loop is the documented way to cancel a stream.

    Reading one frame of a three-frame stream and leaving must not hang, and
    must not require draining the rest.
    """
    fake.stream_count = 3
    seen = 0
    for _ev in client.watch_state():
        seen += 1
        break
    assert seen == 1


def test_edge_many_abandoned_streams_do_not_accumulate(client, fake):
    """Subscribe-and-abandon in a loop must stay stable.

    A desk that resubscribes on every reconnect does this hundreds of times a
    session, so a call leaked per subscription is a slow resource exhaustion.
    """
    fake.stream_count = 5
    for _ in range(200):
        for _ev in client.watch_state():
            break
    assert client.get_me() is not None  # the channel is still usable


def test_fail_error_partway_through_a_stream_surfaces(monkeypatch):
    """A stream that fails after N frames must raise, not end quietly.

    Silently ending is indistinguishable from "the market went quiet", which is
    the worst failure shape a live feed can have.
    """
    fake = FakeVoltAPI()
    srv = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=4))

    def _failing(self, request, context):
        yield __import__(
            "voltnir_sdk._generated.voltnir_api_v1_pb2", fromlist=["x"]
        ).SystemState()
        context.abort(grpc.StatusCode.UNAVAILABLE, "peer went away")

    # monkeypatch, not a bare assignment: conftest installs the generic
    # handlers onto the CLASS at import time, so deleting one afterwards
    # removes it for every later test in the session.
    monkeypatch.setattr(FakeVoltAPI, "WatchState", _failing)
    try:
        pb2_grpc.add_VoltAPIServicer_to_server(fake, srv)
        port = srv.add_insecure_port("127.0.0.1:0")
        srv.start()

        c = VoltnirClient(host="127.0.0.1", port=port, api_key="k", timeout=5.0)
        received = 0
        with pytest.raises(Unavailable):
            for _ev in c.watch_state():
                received += 1
        c.close()

        assert received == 1, "the frame before the failure should still arrive"
    finally:
        srv.stop(None)


async def test_fail_async_error_partway_through_a_stream_surfaces(monkeypatch):
    """The same guarantee on the async client, which is a separate code path."""
    fake = FakeVoltAPI()
    srv = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=4))

    def _failing(self, request, context):
        yield __import__(
            "voltnir_sdk._generated.voltnir_api_v1_pb2", fromlist=["x"]
        ).SystemState()
        context.abort(grpc.StatusCode.PERMISSION_DENIED, "gate closed")

    # monkeypatch, not a bare assignment: conftest installs the generic
    # handlers onto the CLASS at import time, so deleting one afterwards
    # removes it for every later test in the session.
    monkeypatch.setattr(FakeVoltAPI, "WatchState", _failing)
    try:
        pb2_grpc.add_VoltAPIServicer_to_server(fake, srv)
        port = srv.add_insecure_port("127.0.0.1:0")
        srv.start()

        c = AsyncVoltnirClient(host="127.0.0.1", port=port, api_key="k", timeout=5.0)
        received = 0
        with pytest.raises(PermissionDenied):
            async for _ev in c.watch_state():
                received += 1
        await c.close()

        assert received == 1
    finally:
        srv.stop(None)


def test_edge_stream_deadline_raises_deadline_exceeded(monkeypatch):
    """A stream deadline must actually fire.

    A deadline that never applies is a stream that hangs on a dead peer instead
    of raising.
    """
    fake = FakeVoltAPI()
    srv = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=4))

    def _silent(self, request, context):
        import time as _t

        _t.sleep(3.0)  # outlives the caller's deadline, emits nothing
        return
        yield  # pragma: no cover - makes this a generator

    monkeypatch.setattr(FakeVoltAPI, "WatchState", _silent)
    try:
        pb2_grpc.add_VoltAPIServicer_to_server(fake, srv)
        port = srv.add_insecure_port("127.0.0.1:0")
        srv.start()

        c = VoltnirClient(host="127.0.0.1", port=port, api_key="k", timeout=5.0)
        from voltnir_sdk import DeadlineExceeded

        with pytest.raises(DeadlineExceeded):
            for _ev in c.watch_state(timeout=0.3):
                pass
        c.close()
    finally:
        srv.stop(None)


async def test_edge_async_stream_empty_yields_nothing(aclient, fake):
    """A stream that closes without emitting yields no iterations."""
    fake.stream_count = 0
    items = [item async for item in aclient.watch_state()]
    assert items == []


# ── argument validation that must not escape as a raw protobuf error ────────


@pytest.mark.parametrize("bad", ["bogus", "", "OBSERVE_PLEASE"])
def test_fail_set_self_trade_policy_rejects_an_unknown_policy(client, bad):
    """An unknown policy must name what IS accepted.

    protobuf's own error names a generated constant (`SELF_TRADE_POLICY_BOGUS`)
    which is neither what the caller passed nor anything visible in the
    signature.
    """
    with pytest.raises(OrderValidationError, match="observe.*reject"):
        client.set_self_trade_policy(policy=bad)


async def test_fail_async_set_self_trade_policy_rejects_an_unknown_policy(aclient):
    with pytest.raises(OrderValidationError, match="observe.*reject"):
        await aclient.set_self_trade_policy(policy="bogus")


@pytest.mark.parametrize("policy", ["observe", "reject", "OBSERVE", "Reject"])
def test_happy_set_self_trade_policy_accepts_either_case(client, fake, policy):
    client.set_self_trade_policy(policy=policy)
    assert fake.requests["SetSelfTradePolicy"].policy != 0


# ── found by a runtime-robustness audit; both were silent in production ─────


async def test_fail_abandoned_async_stream_releases_the_server_side(monkeypatch):
    """Breaking out of an async stream must release the SERVER-side subscription.

    An abandoned async generator does not release its gRPC call by refcounting
    alone: the Call sits in a reference cycle, so without an explicit cancel the
    subscription stays open server-side and accumulates one per abandonment.
    Against a bounded server handler pool that eventually starves the pool, and
    new subscribes then block with NO exception raised: a desk goes blind and
    gets no error.

    This asserts the observable property (the server sees the stream end)
    rather than the cancel call itself, because an async generator's `finally`
    runs at finalization and a mechanism-level spy is timing-dependent.
    """
    import threading
    import time as _time

    active = 0
    lock = threading.Lock()

    def _long_lived(self, request, context):
        nonlocal active
        with lock:
            active += 1
        try:
            while context.is_active():
                yield pb2.SystemState()
                _time.sleep(0.02)
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(FakeVoltAPI, "WatchState", _long_lived)

    fake = FakeVoltAPI()
    srv = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=32))
    pb2_grpc.add_VoltAPIServicer_to_server(fake, srv)
    port = srv.add_insecure_port("127.0.0.1:0")
    srv.start()
    try:
        c = AsyncVoltnirClient(host="127.0.0.1", port=port, api_key="k", timeout=5.0)
        for _ in range(12):
            async for _ev in c.watch_state():
                break
        await asyncio.sleep(0.5)
        leaked = active
        await c.close()
    finally:
        srv.stop(None)

    assert leaked == 0, f"{leaked} server-side streams leaked after abandoning 12"


async def test_happy_explicit_aclose_also_releases_the_server_side(monkeypatch):
    """The explicit-close shape must release it too."""
    import threading
    import time as _time

    active = 0
    lock = threading.Lock()

    def _long_lived(self, request, context):
        nonlocal active
        with lock:
            active += 1
        try:
            while context.is_active():
                yield pb2.SystemState()
                _time.sleep(0.02)
        finally:
            with lock:
                active -= 1

    monkeypatch.setattr(FakeVoltAPI, "WatchState", _long_lived)

    fake = FakeVoltAPI()
    srv = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=32))
    pb2_grpc.add_VoltAPIServicer_to_server(fake, srv)
    port = srv.add_insecure_port("127.0.0.1:0")
    srv.start()
    try:
        c = AsyncVoltnirClient(host="127.0.0.1", port=port, api_key="k", timeout=5.0)
        for _ in range(12):
            it = c.watch_state()
            async for _ev in it:
                break
            await it.aclose()
        await asyncio.sleep(0.5)
        leaked = active
        await c.close()
    finally:
        srv.stop(None)

    assert leaked == 0


def test_fail_use_after_close_raises_a_voltnir_error(server):
    """Using a closed client must stay inside the error hierarchy.

    A reconnect loop written around `VoltnirError` is the obvious way to
    survive a dropped connection. gRPC's own error here is a bare `ValueError`
    ("Cannot invoke RPC on closed channel!"), which would pass straight through
    such a loop and crash the process instead of triggering a reconnect.
    """
    from voltnir_sdk import ClientClosed

    c = VoltnirClient(host="127.0.0.1", port=server, api_key="k", timeout=5.0)
    c.close()

    with pytest.raises(ClientClosed) as excinfo:
        c.get_me()
    assert isinstance(excinfo.value, VoltnirError)
    assert excinfo.value.rpc == "GetMe"


def test_fail_use_after_close_on_a_stream_raises_a_voltnir_error(server):
    from voltnir_sdk import ClientClosed

    c = VoltnirClient(host="127.0.0.1", port=server, api_key="k", timeout=5.0)
    c.close()

    with pytest.raises(ClientClosed):
        list(c.watch_state())


async def test_fail_async_use_after_close_raises_a_voltnir_error(server):
    """The async path raises `cygrpc.UsageError`, which is not even a ValueError."""
    from voltnir_sdk import ClientClosed

    c = AsyncVoltnirClient(host="127.0.0.1", port=server, api_key="k", timeout=5.0)
    await c.close()

    with pytest.raises(ClientClosed):
        await c.get_me()


async def test_fail_async_use_after_close_on_a_stream_raises(server):
    from voltnir_sdk import ClientClosed

    c = AsyncVoltnirClient(host="127.0.0.1", port=server, api_key="k", timeout=5.0)
    await c.close()

    with pytest.raises(ClientClosed):
        async for _ in c.watch_state():
            pass


def test_edge_a_supervisor_loop_can_catch_close_and_reconnect(server):
    """The shape this exists for: catch VoltnirError, rebuild, carry on."""
    c = VoltnirClient(host="127.0.0.1", port=server, api_key="k", timeout=5.0)
    c.close()

    reconnected = False
    try:
        c.get_me()
    except VoltnirError:
        c = VoltnirClient(host="127.0.0.1", port=server, api_key="k", timeout=5.0)
        assert c.get_me() is not None
        reconnected = True
        c.close()

    assert reconnected


# ── async loop affinity ─────────────────────────────────────────────────────
#
# grpc.aio binds the channel to the running loop at CONSTRUCTION, so a client
# built outside one is already broken. Left unchecked it reports that only at
# the first call, as a wall of task repr plus an unrelated-looking "coroutine
# was never awaited" warning.


def test_fail_constructing_outside_a_running_loop_is_refused():
    """Fail at the mistake, not three frames later inside grpc.

    DI containers and module-level singletons are the common way to hit this,
    and both look perfectly reasonable until the first RPC.
    """
    from voltnir_sdk import AsyncLoopError

    with pytest.raises(AsyncLoopError, match="constructed inside the running"):
        AsyncVoltnirClient(host="h", port=1, api_key="k")


def test_fail_reusing_a_client_across_event_loops_is_refused(server):
    """A client cannot outlive the loop it was built in.

    Sharing one across `asyncio.run()` calls otherwise produces "Event loop is
    closed" or a cross-loop Future error, neither of which names the client as
    the cause.
    """
    import asyncio as _asyncio

    from voltnir_sdk import AsyncLoopError

    async def _build():
        return AsyncVoltnirClient(
            host="127.0.0.1", port=server, api_key="k", timeout=5.0
        )

    client = _asyncio.run(_build())

    async def _use():
        with pytest.raises(AsyncLoopError, match="bound to the event loop"):
            await client.get_me()

    _asyncio.run(_use())


async def test_happy_a_client_built_inside_the_loop_works(server):
    """Edge: the guard must not fire on the correct usage."""
    c = AsyncVoltnirClient(host="127.0.0.1", port=server, api_key="k", timeout=5.0)
    assert await c.get_me() is not None
    await c.close()


async def test_edge_loop_guard_also_covers_streams(server, fake):
    """Streams take a separate code path and need the same guard."""
    c = AsyncVoltnirClient(host="127.0.0.1", port=server, api_key="k", timeout=5.0)
    async for _ev in c.watch_state():
        break
    await c.close()
