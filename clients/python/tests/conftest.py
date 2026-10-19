"""Shared fixtures: an in-process fake VoltAPI gRPC server.

The fake implements *every* RPC in the service descriptor, so the suite can
drive every endpoint over a real insecure loopback channel, exercising the
actual gRPC wire path (request marshalling, status-code translation, stream
iteration) for both the sync and async clients without a live Voltnir backend.

Generic handlers are attached for every method straight from the proto service
descriptor; the two audit/M7 queries are overridden with populated responses
so the depth tests in `test_rpcs.py` can assert on real payload fields.
"""

from __future__ import annotations

import concurrent.futures
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import grpc
import pytest
import pytest_asyncio
from google.protobuf import symbol_database

from voltnir_sdk import AsyncVoltnirClient, VoltnirClient
from voltnir_sdk._generated import voltnir_api_v1_pb2 as pb2
from voltnir_sdk._generated import voltnir_api_v1_pb2_grpc as pb2_grpc

_DB = symbol_database.Default()
_SVC = pb2.DESCRIPTOR.services_by_name["VoltAPI"]

#: The client methods served over the gateway's REST API, not gRPC: the report
#: exports, which have no RPC. `test_rest_export.py` holds them to the REST
#: contract and `test_integration_coverage.py` to live coverage.
REST_METHODS: tuple[str, ...] = ("export_orders", "export_trades", "export_audit")


def _out_cls(method_name: str):
    """Resolve the response message class for an RPC from the descriptor."""
    return _DB.GetSymbol(_SVC.methods_by_name[method_name].output_type.full_name)


class FakeVoltAPI(pb2_grpc.VoltAPIServicer):
    """Configurable fake. Per-test knobs (mutate on the `fake` fixture):

    - ``abort_code``: if set, every handler aborts with this status code.
    - ``abort_details``: detail string paired with ``abort_code``.
    - ``abort_trailers``: trailing metadata sent with the abort, as the gateway
      sends a recall's result beside a failing status.
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
        self.abort_trailers: tuple[tuple[str, object], ...] = ()
        self.stream_count = 2
        self.requests: dict[str, object] = {}
        self.metadata: dict[str, dict[str, str]] = {}

    def _record(self, method_name: str, request, context) -> None:
        self.requests[method_name] = request
        self.metadata[method_name] = dict(context.invocation_metadata())

    def _maybe_abort(self, context) -> None:
        if self.abort_code is not None:
            if self.abort_trailers:
                context.set_trailing_metadata(self.abort_trailers)
            context.abort(self.abort_code, self.abort_details)

    # Populated overrides so the targeted tests can assert payload fields.
    def QueryAuditEvents(self, request, context):
        self._record("QueryAuditEvents", request, context)
        self._maybe_abort(context)
        return pb2.AuditEventsResponse(
            items=[pb2.AuditEventItem(json='{"action":"permissions_set"}')],
            next_cursor="c1",
        )

    def AckTradeIngestFault(self, request, context):
        # Populated so the wrapper tests see every response field cross the wire.
        self._record("AckTradeIngestFault", request, context)
        self._maybe_abort(context)
        return pb2.AckTradeIngestFaultResponse(
            ttl_sec=1800, expires_at_ms=1_791_648_000_000, renewed=True
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
                pb2.ContractSummary(
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
                    # verify.py orders only on a contract in continuous trading.
                    trading_phase="CONT",
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
            # The gateway reads back what it stored: the requested scope, or
            # no areas when none was sent.
            delivery_areas=request.delivery_areas,
        )

    def QueryM7Errors(self, request, context):
        self._record("QueryM7Errors", request, context)
        self._maybe_abort(context)
        return pb2.M7ErrorsResponse(
            items=[pb2.M7ErrorItem(json='{"kind":"err_resp"}')],
            next_cursor="c1",
        )

    def ListExchangeMessages(self, request, context):
        self._record("ListExchangeMessages", request, context)
        self._maybe_abort(context)
        return pb2.ListExchangeMessagesResponse(
            items=[
                pb2.ExchangeMessageItem(
                    json='{"msg_id":90210,"code":158,"severity":"error"}'
                )
            ],
            next_cursor="c1",
        )

    def ListSystemLog(self, request, context):
        self._record("ListSystemLog", request, context)
        self._maybe_abort(context)
        # The buffer block is always populated: a response without it is what a
        # panel would misread as "the log is complete".
        return pb2.ListSystemLogResponse(
            items=[
                pb2.SystemLogItem(
                    json='{"seq":41,"ts_ms":1,"level":"warn",'
                    '"target":"voltnir_backend::m7","message":"reconnecting"}'
                )
            ],
            next_cursor=41,
            truncated=True,
            buffer=pb2.SystemLogBuffer(
                enabled=True,
                level="info",
                capacity=20000,
                len=1,
                oldest_seq=41,
                oldest_ts_ms=1,
                newest_seq=41,
                started_at_ms=1,
                dropped=9,
                has_entries=True,
            ),
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


# ── the REST export contract, served on loopback ────────────────────────────

REST_KEY = "test-key"
REST_TOKEN = "550e8400-e29b-41d4-a716-446655440000"
_EXPORT_PREFIX = "/api/v1/audit/export/"


class FakeRestExport:
    """A loopback HTTP server speaking the gateway's REST export contract.

    ``POST /api/v1/audit/export/{orders|trades|events}`` answers ``202`` with a token,
    ``GET /api/v1/audit/export/{token}`` answers ``202 pending`` ``pending``
    times and then the file. A bearer other than ``REST_KEY`` is ``401``.

    Knobs, set before the export starts:

    - ``body``: the file served once ready.
    - ``pending``: how many polls answer ``202 {"status":"pending"}`` first.
    - ``post_status`` / ``poll_status`` with ``error``: answer the POST, or
      every poll, with that status and ``{"error": error}``.
    - ``post_answer``: a raw ``(status, body bytes)`` for the POST instead.
    - ``piece`` and ``gate_after`` / ``gate``: write the file ``piece`` bytes at
      a time, and wait for the ``gate`` event before writing past
      ``gate_after`` bytes, so a test sees chunks arrive while the server is
      still writing. ``finished`` is set once the last byte is written.
    - ``short_by``: state a ``Content-Length`` that many bytes past the body,
      then close: an interrupted download.
    - ``poll_delay``: seconds each poll takes before it answers.
    - ``post_delay``: seconds the POST takes before it answers.
    - ``piece_delay``: seconds between two written pieces of the file.
    - ``redirect_to``: answer the POST with a ``302`` to this URL.

    ``requests`` records ``(method, path, headers, json body or None)``.
    """

    def __init__(self) -> None:
        self.body = b"[]"
        self.pending = 0
        self.post_status: int | None = None
        self.poll_status: int | None = None
        self.error = "refused"
        self.post_answer: tuple[int, bytes] | None = None
        self.piece = 64 * 1024
        self.gate_after: int | None = None
        self.gate = threading.Event()
        self.finished = threading.Event()
        self.short_by = 0
        self.poll_delay = 0.0
        self.post_delay = 0.0
        self.piece_delay = 0.0
        self.redirect_to: str | None = None
        self.closed = threading.Event()  # the client closed the download early
        self.requests: list[tuple[str, str, dict[str, str], object]] = []
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _rest_handler(self))
        self._server.daemon_threads = True
        threading.Thread(
            target=self._server.serve_forever, args=(0.02,), daemon=True
        ).start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def posts(self) -> list[tuple[str, str, dict[str, str], object]]:
        return [r for r in self.requests if r[0] == "POST"]

    def polls(self) -> list[tuple[str, str, dict[str, str], object]]:
        return [r for r in self.requests if r[0] == "GET"]

    def stop(self) -> None:
        self.gate.set()  # release a handler still waiting to write
        self._server.shutdown()
        self._server.server_close()


def _rest_handler(fx: FakeRestExport) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            return

        def _json(self, status: int, payload: object) -> None:
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _authorised(self, body: object) -> bool:
            fx.requests.append((self.command, self.path, dict(self.headers), body))
            if self.headers.get("Authorization") != f"Bearer {REST_KEY}":
                self._json(401, {"error": "Unauthorized"})
                return False
            return True

        def do_POST(self) -> None:  # noqa: N802 - the http.server hook name
            raw = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            if not self._authorised(json.loads(raw or b"null")):
                return
            time.sleep(fx.post_delay)
            if fx.redirect_to is not None:
                self.send_response(302)
                self.send_header("Location", fx.redirect_to)
                self.send_header("Content-Length", "0")
                self.end_headers()
            elif fx.post_answer is not None:
                status, data = fx.post_answer
                self.send_response(status)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            elif fx.post_status is not None:
                self._json(fx.post_status, {"error": fx.error})
            else:
                token = {"token": REST_TOKEN, "download_url": _EXPORT_PREFIX + REST_TOKEN}
                self._json(202, token)

        def do_GET(self) -> None:  # noqa: N802 - the http.server hook name
            if not self._authorised(None):
                return
            time.sleep(fx.poll_delay)
            if self.path != _EXPORT_PREFIX + REST_TOKEN:
                self._json(404, {"error": "token not found"})
            elif fx.poll_status is not None:
                self._json(fx.poll_status, {"error": fx.error})
            elif fx.pending > 0:
                fx.pending -= 1
                self._json(202, {"status": "pending"})
            else:
                self._file()

        def _file(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/csv")
            self.send_header("Content-Disposition", 'attachment; filename="report.csv"')
            self.send_header("Content-Length", str(len(fx.body) + fx.short_by))
            self.end_headers()
            try:
                for at in range(0, len(fx.body), fx.piece):
                    if fx.gate_after is not None and at >= fx.gate_after:
                        fx.gate.wait(10)
                    elif at:
                        time.sleep(fx.piece_delay)
                    self.wfile.write(fx.body[at : at + fx.piece])
            except (BrokenPipeError, ConnectionResetError):
                fx.closed.set()
                return
            fx.finished.set()

    return Handler


@pytest.fixture
def rest(monkeypatch):
    """The REST export fake, reached directly even where a proxy is configured."""
    for name in ("NO_PROXY", "no_proxy"):
        monkeypatch.setenv(name, "127.0.0.1,localhost")
    fx = FakeRestExport()
    yield fx
    fx.stop()
