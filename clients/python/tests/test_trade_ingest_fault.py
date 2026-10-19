"""`ack_trade_ingest_fault` on both clients: the reason it sends, the response it
returns, and how the gateway's refusals surface."""

from __future__ import annotations

import grpc
import pytest

from voltnir_sdk import Aborted, InvalidArgument, PermissionDenied


def test_happy_ack_sends_the_reason_and_returns_the_ttl(client, fake):
    resp = client.ack_trade_ingest_fault("balancing; support desk paged")
    assert fake.requests["AckTradeIngestFault"].reason == "balancing; support desk paged"
    assert (resp.ttl_sec, resp.expires_at_ms, resp.renewed) == (1800, 1_791_648_000_000, True)


async def test_happy_async_ack_sends_the_reason_and_returns_the_ttl(aclient, fake):
    resp = await aclient.ack_trade_ingest_fault(reason="balancing")
    assert fake.requests["AckTradeIngestFault"].reason == "balancing"
    assert resp.ttl_sec == 1800


@pytest.mark.parametrize(
    ("code", "exc"),
    [
        (grpc.StatusCode.ABORTED, Aborted),
        (grpc.StatusCode.PERMISSION_DENIED, PermissionDenied),
    ],
)
def test_fail_ack_refusals_raise_their_typed_error(client, fake, code, exc):
    fake.abort_code = code
    fake.abort_details = "CONFLICT: no trade_report refused fault is raised"
    with pytest.raises(exc) as info:
        client.ack_trade_ingest_fault("balancing")
    assert info.value.message == fake.abort_details


async def test_fail_async_ack_with_no_fault_raises_aborted(aclient, fake):
    fake.abort_code = grpc.StatusCode.ABORTED
    with pytest.raises(Aborted):
        await aclient.ack_trade_ingest_fault("balancing")


# edge: an empty reason is the gateway's to refuse; the SDK sends it as given
# and surfaces INVALID_ARGUMENT, so the rule lives in one place.
@pytest.mark.parametrize("reason", ["", "   "])
def test_edge_empty_reason_is_sent_and_refused_by_the_gateway(client, fake, reason):
    fake.abort_code = grpc.StatusCode.INVALID_ARGUMENT
    fake.abort_details = "BAD_REQUEST: reason is required and must not be empty"
    with pytest.raises(InvalidArgument):
        client.ack_trade_ingest_fault(reason)
    assert fake.requests["AckTradeIngestFault"].reason == reason


async def test_edge_async_empty_reason_is_refused_by_the_gateway(aclient, fake):
    fake.abort_code = grpc.StatusCode.INVALID_ARGUMENT
    with pytest.raises(InvalidArgument):
        await aclient.ack_trade_ingest_fault("")
