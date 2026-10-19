"""Reading a trade recall's result off a failed `RecallTrade` call.

A recall of one trade answers with the status of its one result, so a refused,
unknown, not-recallable or not-sent recall arrives as a failing status. The
gateway still sends the result, in gRPC's standard rich error model: the
`grpc-status-details-bin` trailer holds a `google.rpc.Status` whose one detail
is an `Any` packing the `RecallTradeResponse`. Both clients return it rather
than raising, so a caller reads every outcome the same way, from `outcome`.

The SDK depends on no `google.rpc` package, so `google.rpc.Status` is declared
here from its published three fields, in a private descriptor pool that cannot
clash with one an application loads.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from google.protobuf import any_pb2, descriptor_pb2, descriptor_pool, message_factory
from google.protobuf.message import DecodeError

from ._generated import voltnir_api_v1_pb2 as pb2
from .errors import VoltnirError

#: The trailer gRPC's rich error model carries `google.rpc.Status` in.
STATUS_DETAILS_TRAILER = "grpc-status-details-bin"

#: The `Any` type URL of the result a failed single-trade call carries.
RECALL_RESULT_TYPE_URL = "type.googleapis.com/voltnir.api.v1.RecallTradeResponse"


def _status_class():
    """`google.rpc.Status { int32 code = 1; string message = 2; repeated
    google.protobuf.Any details = 3; }`, built in a private pool."""
    pool = descriptor_pool.DescriptorPool()
    pool.Add(descriptor_pb2.FileDescriptorProto.FromString(any_pb2.DESCRIPTOR.serialized_pb))
    f = descriptor_pb2.FileDescriptorProto(
        name="voltnir_sdk/google_rpc_status.proto",
        package="google.rpc",
        syntax="proto3",
        dependency=["google/protobuf/any.proto"],
    )
    m = f.message_type.add(name="Status")
    fd = descriptor_pb2.FieldDescriptorProto
    m.field.add(name="code", number=1, type=fd.TYPE_INT32, label=fd.LABEL_OPTIONAL)
    m.field.add(name="message", number=2, type=fd.TYPE_STRING, label=fd.LABEL_OPTIONAL)
    m.field.add(
        name="details",
        number=3,
        type=fd.TYPE_MESSAGE,
        label=fd.LABEL_REPEATED,
        type_name=".google.protobuf.Any",
    )
    pool.Add(f)
    return message_factory.GetMessageClass(pool.FindMessageTypeByName("google.rpc.Status"))


_Status = _status_class()


def result_of(rpc_error: object) -> pb2.RecallTradeResponse | None:
    """The recall result a failed call carries, or `None` when it carries none.

    `None` is every whole-request refusal (no permission, not found, a changed
    revision, a malformed request), every failure the client itself raised,
    such as a client-side deadline, and a trailer or detail that does not
    decode: those carry no result to read, and the typed error stands.
    """
    trailing = getattr(rpc_error, "trailing_metadata", None)
    if not callable(trailing):
        return None
    for key, value in trailing() or ():
        if key != STATUS_DETAILS_TRAILER or not isinstance(value, bytes):
            continue
        try:
            details = _Status.FromString(value).details
            for detail in details:
                if detail.type_url == RECALL_RESULT_TYPE_URL:
                    return pb2.RecallTradeResponse.FromString(detail.value)
        except DecodeError:
            return None
    return None


def returning_result(call: Callable[[], pb2.RecallTradeResponse]) -> pb2.RecallTradeResponse:
    """Run a `RecallTrade` call, answering a failure that carries a result with
    that result and re-raising every other failure."""
    try:
        return call()
    except VoltnirError as e:
        result = result_of(e.__cause__)
        if result is None:
            raise
        return result


async def areturning_result(
    call: Awaitable[pb2.RecallTradeResponse],
) -> pb2.RecallTradeResponse:
    """`returning_result` for the async client."""
    try:
        return await call
    except VoltnirError as e:
        result = result_of(e.__cause__)
        if result is None:
            raise
        return result
