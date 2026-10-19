"""The trade-tape and hub-to-hub stream wrappers: the RPC each one calls, what
it puts on the wire, and that a refusal reaches the caller as the SDK's typed
error. Both clients.
"""

from __future__ import annotations

import grpc
import pytest

from voltnir_sdk import InvalidArgument

_HUB = "10YNL----------L"
_FROM = "2026-10-08T00:00:00Z"
_TO = "2026-10-09T00:00:00Z"


# Happy: the tape wrapper calls WatchTradeTape and yields every event sent.
def test_happy_watch_trade_tape_calls_its_rpc(client, fake):
    events = list(client.watch_trade_tape(timeout=5.0))
    assert len(events) == fake.stream_count
    assert "WatchTradeTape" in fake.requests
    assert fake.requests["WatchTradeTape"].ByteSize() == 0


async def test_happy_async_watch_trade_tape_calls_its_rpc(aclient, fake):
    events = [e async for e in aclient.watch_trade_tape()]
    assert len(events) == fake.stream_count
    assert "WatchTradeTape" in fake.requests


# Happy: the hub-to-hub wrapper sends the hub and both window bounds.
def test_happy_watch_hub2hub_sends_the_hub_and_window(client, fake):
    events = list(
        client.watch_hub2hub(
            delivery_area_from=_HUB, delivery_from=_FROM, delivery_to=_TO, timeout=5.0
        )
    )
    assert len(events) == fake.stream_count
    req = fake.requests["WatchHub2Hub"]
    assert (req.delivery_area_from, req.delivery_from, req.delivery_to) == (_HUB, _FROM, _TO)


async def test_happy_async_watch_hub2hub_sends_the_hub_and_window(aclient, fake):
    events = [
        e
        async for e in aclient.watch_hub2hub(
            delivery_area_from=_HUB, delivery_from=_FROM, delivery_to=_TO
        )
    ]
    assert len(events) == fake.stream_count
    req = fake.requests["WatchHub2Hub"]
    assert (req.delivery_area_from, req.delivery_from, req.delivery_to) == (_HUB, _FROM, _TO)


# Fail: the gateway's refusal of a malformed window is the typed InvalidArgument
# carrying the gateway's message.
def test_fail_watch_hub2hub_bad_window_is_invalid_argument(client, fake):
    fake.abort_code = grpc.StatusCode.INVALID_ARGUMENT
    fake.abort_details = "invalid delivery_from: input contains invalid characters"
    with pytest.raises(InvalidArgument, match="invalid delivery_from"):
        list(
            client.watch_hub2hub(
                delivery_area_from=_HUB, delivery_from="yesterday", delivery_to=_TO, timeout=5.0
            )
        )


# Edge: the window is required; the wrapper offers no default for it.
def test_edge_watch_hub2hub_requires_the_window(client):
    with pytest.raises(TypeError):
        client.watch_hub2hub(delivery_area_from=_HUB)  # type: ignore[call-arg]
