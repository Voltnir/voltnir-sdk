"""`recall_trade` and `recall_order_trades`: the request each sends, and the
result each returns when the gateway answers a single-trade recall with a
failing status carrying the result in its trailing metadata."""

from __future__ import annotations

import grpc
import pytest

from voltnir_sdk import FailedPrecondition, NotFound, PermissionDenied
from voltnir_sdk._generated import voltnir_api_v1_pb2 as pb2
from voltnir_sdk._recall import RECALL_RESULT_TYPE_URL, STATUS_DETAILS_TRAILER, _Status


def _refused() -> pb2.RecallTradeResponse:
    return pb2.RecallTradeResponse(
        results=[
            pb2.RecallTradeResult(
                trade_id="1500000001",
                outcome="refused",
                state="ACTI",
                revision_no=1,
                m7_err_code=2013,
                m7_error_key="trade_execution_too_long_ago",
                reason="Trade execution too long ago!",
            )
        ]
    )


def _refuse_with_result(fake) -> None:
    fake.abort_code = grpc.StatusCode.FAILED_PRECONDITION
    fake.abort_details = "RECALL_REFUSED: recall of trade 1500000001"
    status = _Status(code=grpc.StatusCode.FAILED_PRECONDITION.value[0], message=fake.abort_details)
    detail = status.details.add()
    detail.type_url = RECALL_RESULT_TYPE_URL
    detail.value = _refused().SerializeToString()
    fake.abort_trailers = ((STATUS_DETAILS_TRAILER, status.SerializeToString()),)


def test_happy_recall_trade_sends_the_trade_and_its_revision(client, fake):
    client.recall_trade("1500000001", revision_no=4)
    sent = fake.requests["RecallTrade"]
    assert sent.WhichOneof("target") == "trade_id"
    assert sent.trade_id == "1500000001"
    assert sent.HasField("revision_no") and sent.revision_no == 4


def test_edge_recall_trade_without_a_revision_leaves_it_unset(client, fake):
    client.recall_trade("1500000001")
    assert not fake.requests["RecallTrade"].HasField("revision_no")


def test_happy_recall_order_trades_sends_only_the_order(client, fake):
    client.recall_order_trades("6f0c2a54-1111-4222-8333-944445555666")
    sent = fake.requests["RecallTrade"]
    assert sent.WhichOneof("target") == "client_order_id"
    assert sent.client_order_id == "6f0c2a54-1111-4222-8333-944445555666"
    assert not sent.HasField("revision_no")


def test_fail_a_refused_recall_returns_its_result(client, fake):
    _refuse_with_result(fake)
    result = client.recall_trade("1500000001").results[0]
    assert (result.outcome, result.m7_err_code) == ("refused", 2013)
    assert result.m7_error_key == "trade_execution_too_long_ago"


def test_edge_a_detail_of_another_type_is_not_read_as_a_result(client, fake):
    """A rich error whose detail is not a RecallTradeResponse raises as usual."""
    fake.abort_code = grpc.StatusCode.FAILED_PRECONDITION
    status = _Status(code=9, message="other")
    other = status.details.add()
    other.type_url = "type.googleapis.com/google.rpc.ErrorInfo"
    other.value = b"x"
    fake.abort_trailers = ((STATUS_DETAILS_TRAILER, status.SerializeToString()),)
    with pytest.raises(FailedPrecondition):
        client.recall_trade("1")


def test_fail_a_garbage_details_blob_re_raises_the_typed_error(client, fake):
    """A trailer that is not a google.rpc.Status leaves the typed error."""
    fake.abort_code = grpc.StatusCode.FAILED_PRECONDITION
    fake.abort_trailers = ((STATUS_DETAILS_TRAILER, b"\xff\xff\xff\xff"),)
    with pytest.raises(FailedPrecondition):
        client.recall_trade("1")


def test_fail_a_malformed_result_detail_re_raises_the_typed_error(client, fake):
    """A good envelope whose RecallTradeResponse bytes do not decode leaves
    the typed error."""
    fake.abort_code = grpc.StatusCode.FAILED_PRECONDITION
    status = _Status(code=9, message="RECALL_REFUSED: x")
    detail = status.details.add()
    detail.type_url = RECALL_RESULT_TYPE_URL
    detail.value = b"\xff\xff\xff\xff"
    fake.abort_trailers = ((STATUS_DETAILS_TRAILER, status.SerializeToString()),)
    with pytest.raises(FailedPrecondition):
        client.recall_trade("1")


def test_fail_a_whole_request_error_still_raises(client, fake):
    fake.abort_code = grpc.StatusCode.NOT_FOUND
    fake.abort_details = "TRADE_NOT_FOUND: trade 9 is not held"
    with pytest.raises(NotFound):
        client.recall_trade("9")
    fake.abort_code = grpc.StatusCode.PERMISSION_DENIED
    with pytest.raises(PermissionDenied):
        client.recall_order_trades("o")


async def test_happy_async_methods_send_the_same_requests(aclient, fake):
    await aclient.recall_trade("7", revision_no=2)
    sent = fake.requests["RecallTrade"]
    assert (sent.trade_id, sent.revision_no) == ("7", 2)
    await aclient.recall_order_trades("o")
    assert fake.requests["RecallTrade"].client_order_id == "o"


async def test_fail_async_refused_recall_returns_its_result(aclient, fake):
    _refuse_with_result(fake)
    result = (await aclient.recall_trade("1500000001")).results[0]
    assert (result.outcome, result.m7_err_code) == ("refused", 2013)


async def test_fail_async_whole_request_error_still_raises(aclient, fake):
    fake.abort_code = grpc.StatusCode.NOT_FOUND
    with pytest.raises(NotFound):
        await aclient.recall_order_trades("o")
