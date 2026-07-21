"""Shared fixtures: an in-process fake VoltAPI gRPC server.

The fake implements *every* RPC in the service descriptor, so the suite can
drive all 63 endpoints over a real insecure loopback channel, exercising the
actual gRPC wire path (request marshalling, status-code translation, stream
iteration) for both the sync and async clients without a live Voltnir backend.

Generic handlers are attached for every method straight from the proto service
descriptor; the two audit/M7 queries are overridden with populated responses
so the depth tests in `test_rpcs.py` can assert on real payload fields.
"""

from __future__ import annotations

import concurrent.futures

import grpc
import pytest
import pytest_asyncio
from google.protobuf import symbol_database

from voltnir_sdk import AsyncVoltnirClient, VoltnirClient
from voltnir_sdk._generated import voltnir_api_v1_pb2 as pb2
from voltnir_sdk._generated import voltnir_api_v1_pb2_grpc as pb2_grpc

_DB = symbol_database.Default()
_SVC = pb2.DESCRIPTOR.services_by_name["VoltAPI"]


def _out_cls(method_name: str):
    """Resolve the response message class for an RPC from the descriptor."""
    return _DB.GetSymbol(_SVC.methods_by_name[method_name].output_type.full_name)


class FakeVoltAPI(pb2_grpc.VoltAPIServicer):
    """Configurable fake. Per-test knobs (mutate on the `fake` fixture):

    - ``abort_code``: if set, every handler aborts with this status code.
    - ``abort_details``: detail string paired with ``abort_code``.
    - ``stream_count``: number of items each server-streaming RPC yields.
    - ``requests``: captures the received request per method name, so tests
      can assert filter fields crossed the wire.
    - ``metadata``: captures the received call metadata per method name, as a
      dict. Without it the auth path is structurally untestable: the SDK
      attaches ``authorization: Bearer <key>`` on every call, and a fake that
      never inspects metadata passes every test with the credential malformed
      or missing entirely.
    """

    def __init__(self) -> None:
        self.abort_code: grpc.StatusCode | None = None
        self.abort_details = "denied"
        self.stream_count = 2
        self.requests: dict[str, object] = {}
        self.metadata: dict[str, dict[str, str]] = {}

    def _record(self, method_name: str, request, context) -> None:
        self.requests[method_name] = request
        self.metadata[method_name] = dict(context.invocation_metadata())

    def _maybe_abort(self, context) -> None:
        if self.abort_code is not None:
            context.abort(self.abort_code, self.abort_details)

    # Populated overrides so the targeted tests can assert payload fields.
    def QueryAuditEvents(self, request, context):
        self._record("QueryAuditEvents", request, context)
        self._maybe_abort(context)
        return pb2.AuditEventsResponse(
            items=[pb2.AuditEventItem(json='{"action":"permissions_set"}')],
            next_cursor="c1",
            total_hint=1,
        )

    def ListContracts(self, request, context):
        # Populated so the README quickstart (`contracts.contracts[0]`) and the
        # contract-scoped steps in verify.py are genuinely exercised rather than
        # skipping on an empty list. ACTI with real prod/dlvry_start, because
        # verify.py deliberately prefers a contract carrying that metadata.
        self._record("ListContracts", request, context)
        self._maybe_abort(context)
        return pb2.ListContractsResponse(
            contracts=[
                pb2.Contract(
                    contract_id="12345",
                    area_id=request.area_id or "10YBE----------2",
                    prod="H",
                    name="H far-future",
                    # Deliberately far future: verify.py's mutate pass refuses to
                    # touch a contract whose delivery is imminent, so a
                    # near-dated fixture would silently skip the whole order
                    # lifecycle and leave those call sites unexecuted.
                    dlvry_start="2099-01-01T10:00:00Z",
                    dlvry_end="2099-01-01T11:00:00Z",
                    state=pb2.ContractState.ACTI,
                    # verify.py skips user-defined block contracts, which only
                    # accept block orders; without this the order lifecycle is
                    # never reached.
                    predefined=True,
                )
            ]
        )

    def SubmitOrder(self, request, context):
        # Echo the client_order_id back: verify.py bails out of the order
        # lifecycle if the response carries none, leaving the rest of the
        # lifecycle unexercised by the runner smoke test.
        self._record("SubmitOrder", request, context)
        self._maybe_abort(context)
        return pb2.SubmitOrderResponse(client_order_id=request.client_order_id)

    def GetOrder(self, request, context):
        # Return the order as CONFIRMED. verify.py polls GetOrder until the
        # order leaves the pending state, so a default-constructed response
        # (neither oneof arm set) would spin for the full timeout and then skip
        # the rest of the lifecycle. Confirming immediately is faster and
        # covers more.
        self._record("GetOrder", request, context)
        self._maybe_abort(context)
        return pb2.GetOrderResponse(
            confirmed=pb2.OwnOrder(
                client_order_id=request.client_order_id,
                order_id=987654,
                contract_id=12345,               # int64, unlike Contract.contract_id
                delivery_area="10YBE----------2",
                side=pb2.Side.BUY,
                price=100,                       # wire cents = 1.00 EUR/MWh
                quantity=100,                    # sub-MW = 0.1 MW
            )
        )

    def CreateMember(self, request, context):
        # Populated so the member lifecycle is really exercised: a
        # default-constructed Member has id "", which the gateway can never
        # return, and downstream steps would skip on it.
        self._record("CreateMember", request, context)
        self._maybe_abort(context)
        return pb2.Member(
            id="11111111-2222-4333-8444-555555555555",
            short_id="VM001",
            name=request.name,
            max_position=request.max_position,
            active=True,
        )

    def QueryM7Errors(self, request, context):
        self._record("QueryM7Errors", request, context)
        self._maybe_abort(context)
        return pb2.M7ErrorsResponse(
            items=[pb2.M7ErrorItem(json='{"kind":"err_resp"}')],
            next_cursor="c1",
            total_hint=1,
        )


def _make_unary(method_name: str, out_cls):
    def handler(self, request, context):
        self._record(method_name, request, context)
        self._maybe_abort(context)
        return out_cls()

    handler.__name__ = method_name
    return handler


def _make_stream(method_name: str, out_cls):
    def handler(self, request, context):
        self._record(method_name, request, context)
        self._maybe_abort(context)
        for _ in range(self.stream_count):
            yield out_cls()

    handler.__name__ = method_name
    return handler


# Attach a generic handler for every RPC not already defined explicitly above.
for _m in _SVC.methods:
    if _m.name in FakeVoltAPI.__dict__:
        continue
    _factory = _make_stream if _m.server_streaming else _make_unary
    setattr(FakeVoltAPI, _m.name, _factory(_m.name, _out_cls(_m.name)))


@pytest.fixture
def fake() -> FakeVoltAPI:
    return FakeVoltAPI()


@pytest.fixture
def server(fake):
    srv = grpc.server(concurrent.futures.ThreadPoolExecutor(max_workers=4))
    pb2_grpc.add_VoltAPIServicer_to_server(fake, srv)
    port = srv.add_insecure_port("127.0.0.1:0")
    srv.start()
    yield port
    srv.stop(None)


@pytest.fixture
def client(server):
    c = VoltnirClient(host="127.0.0.1", port=server, api_key="test-key", timeout=5.0)
    yield c
    c.close()


@pytest_asyncio.fixture
async def aclient(server):
    c = AsyncVoltnirClient(
        host="127.0.0.1", port=server, api_key="test-key", timeout=5.0
    )
    yield c
    await c.close()
