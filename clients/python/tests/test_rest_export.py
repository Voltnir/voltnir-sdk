"""The report exports over the gateway's REST API, against a loopback fake.

`export_orders` / `export_trades` POST the export request, poll its token until
the file is ready, and stream the file back as bytes. These tests drive both
clients against `FakeRestExport` (in `conftest.py`), which speaks the gateway's
REST export contract, so the real request, polling and download code runs with
no gateway: the bytes, the request body, the error mapping, the timeouts and
the event loop staying free.
"""

from __future__ import annotations

import asyncio
import json
import socket
import ssl
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import ClassVar

import grpc
import pytest
import pytest_asyncio
from conftest import REST_KEY, REST_METHODS, REST_TOKEN
from voltnir_sdk import (
    AsyncVoltnirClient,
    CaCertificateError,
    ClientClosed,
    DeadlineExceeded,
    ExportBusy,
    Internal,
    InvalidArgument,
    NotFound,
    PermissionDenied,
    ResourceExhausted,
    Unauthenticated,
    Unavailable,
    VoltnirClient,
    VoltnirError,
    _rest_export,
)

_FROM, _TO = "2026-07-01T00:00:00Z", "2026-07-02T00:00:00Z"
_CSV = b"order_id,price\n1,5007\n2,-150\n"
_JSON = b'[\n  {\n    "order_id": 1,\n    "price": 5007\n  }\n]'
_CHUNK = _rest_export.CHUNK_BYTES

# A self-signed CA certificate (no key): only its subject is asserted.
_TEST_CA = b"""-----BEGIN CERTIFICATE-----
MIIBkjCCATmgAwIBAgIUSbLK2qECK4Oe5WaQteM4lsJLzscwCgYIKoZIzj0EAwIw
HjEcMBoGA1UEAwwTdm9sdG5pci1zZGstdGVzdC1jYTAgFw0yNjEwMDUwMjE5NTZa
GA8yMTI2MDkxMTAyMTk1NlowHjEcMBoGA1UEAwwTdm9sdG5pci1zZGstdGVzdC1j
YTBZMBMGByqGSM49AgEGCCqGSM49AwEHA0IABOSFbA4xjJATpFSRAoHa8p9IHxsj
lGFjA87DHDb3hmr/9H8BsQJjtHkcbp7N2j+wd5qra3d/G/1mBGlc8xzSOFijUzBR
MB0GA1UdDgQWBBTfPqBD4Dv4yvDxt+xe+lHVtTQV0TAfBgNVHSMEGDAWgBTfPqBD
4Dv4yvDxt+xe+lHVtTQV0TAPBgNVHRMBAf8EBTADAQH/MAoGCCqGSM49BAMCA0cA
MEQCIFRkZiS8prFSnN7yrFxtrr3f7xxc7sw5DakdBNo+nvLkAiAr1R8sp5JmJGq+
KkUy5llZv6JhdTOjH+WXHf0DjzX31A==
-----END CERTIFICATE-----
"""


@pytest.fixture
def rclient(server, rest):
    c = VoltnirClient(
        host="127.0.0.1", port=server, api_key=REST_KEY, timeout=5.0, rest_url=rest.url
    )
    yield c
    c.close()


@pytest_asyncio.fixture
async def raclient(server, rest):
    c = AsyncVoltnirClient(
        host="127.0.0.1", port=server, api_key=REST_KEY, timeout=5.0, rest_url=rest.url
    )
    yield c
    await c.close()


def _export(client, kind: str, **kw):
    kw.setdefault("format", "csv")
    return getattr(client, f"export_{kind}")(from_=_FROM, to=_TO, **kw)


async def _adrain(aiter) -> list[bytes]:
    return [chunk async for chunk in aiter]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ── happy ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("kind", ["orders", "trades"])
@pytest.mark.parametrize("fmt,body", [("csv", _CSV), ("json", _JSON)])
def test_happy_export_yields_the_served_file_byte_for_byte(rclient, rest, kind, fmt, body):
    rest.body = body
    data = b"".join(_export(rclient, kind, format=fmt))
    assert data == body
    _method, path, headers, sent = rest.posts()[0]
    assert path == f"/api/v1/audit/export/{kind}"
    assert sent == {"format": fmt, "from": _FROM, "to": _TO}
    assert headers["Authorization"] == f"Bearer {REST_KEY}"
    assert [p[1] for p in rest.polls()] == [f"/api/v1/audit/export/{REST_TOKEN}"]


@pytest.mark.parametrize("kind", ["orders", "trades"])
@pytest.mark.parametrize("fmt,body", [("csv", _CSV), ("json", _JSON)])
async def test_happy_async_export_yields_the_served_file_byte_for_byte(
    raclient, rest, kind, fmt, body
):
    rest.body = body
    data = b"".join(await _adrain(_export(raclient, kind, format=fmt)))
    assert data == body
    assert rest.posts()[0][1] == f"/api/v1/audit/export/{kind}"
    assert rest.posts()[0][3] == {"format": fmt, "from": _FROM, "to": _TO}


def test_happy_pending_pending_ready_is_polled_to_the_file(rclient, rest):
    rest.body, rest.pending = _CSV, 2
    assert b"".join(_export(rclient, "orders")) == _CSV
    assert len(rest.polls()) == 3


async def test_happy_async_pending_pending_ready_is_polled_to_the_file(raclient, rest):
    rest.body, rest.pending = _CSV, 2
    assert b"".join(await _adrain(_export(raclient, "trades"))) == _CSV
    assert len(rest.polls()) == 3


def test_happy_filters_and_the_from_keyword_cross_as_json_keys(rclient, rest):
    """`from_` is sent as `from`; `area` / `product` only when passed."""
    list(_export(rclient, "orders", area="10YBE----------2", product="Intraday_Power_D"))
    list(_export(rclient, "orders"))
    with_filters, without = rest.posts()[0][3], rest.posts()[1][3]
    assert with_filters == {
        "format": "csv", "from": _FROM, "to": _TO,
        "area": "10YBE----------2", "product": "Intraday_Power_D",
    }
    assert without == {"format": "csv", "from": _FROM, "to": _TO}


async def test_happy_async_filters_cross_as_json_keys(raclient, rest):
    await _adrain(_export(raclient, "trades", format="json", area="10YNL----------L"))
    assert rest.posts()[0][3] == {
        "format": "json", "from": _FROM, "to": _TO, "area": "10YNL----------L"
    }


def test_happy_a_large_file_arrives_in_chunks_before_the_server_finishes(rclient, rest):
    """Streamed, not buffered: the first three pieces arrive while the server is
    still held mid-file, and no chunk is larger than the documented 64 KiB."""
    rest.body = bytes(range(256)) * (6 * _CHUNK // 256)
    rest.gate_after = 3 * _CHUNK
    stream = _export(rclient, "orders")
    first = []
    while sum(map(len, first)) < 3 * _CHUNK:
        first.append(next(stream))
    assert not rest.finished.is_set(), "the whole file was written before a chunk arrived"
    rest.gate.set()
    chunks = first + list(stream)
    assert max(len(c) for c in chunks) <= _CHUNK and len(chunks) >= 6
    assert b"".join(chunks) == rest.body


async def test_happy_async_large_file_arrives_in_chunks_before_the_server_finishes(
    raclient, rest
):
    rest.body = b"x" * (5 * _CHUNK)
    rest.gate_after = 2 * _CHUNK
    stream = _export(raclient, "trades")
    first = []
    while sum(map(len, first)) < 2 * _CHUNK:
        first.append(await anext(stream))
    assert not rest.finished.is_set()
    rest.gate.set()
    chunks = first + await _adrain(stream)
    assert max(len(c) for c in chunks) <= _CHUNK
    assert b"".join(chunks) == rest.body


@pytest.mark.parametrize("method", REST_METHODS)
def test_happy_exports_never_reach_the_grpc_service(rclient, rest, fake, method):
    """The export methods go over REST: the gRPC fake sees no call at all."""
    list(getattr(rclient, method)(format="json", from_=_FROM, to=_TO))
    assert len(rest.posts()) == 1
    assert fake.requests == {}


# ── fail ────────────────────────────────────────────────────────────────────

_STATUS_MATRIX = [
    (400, InvalidArgument, grpc.StatusCode.INVALID_ARGUMENT),
    (401, Unauthenticated, grpc.StatusCode.UNAUTHENTICATED),
    (403, PermissionDenied, grpc.StatusCode.PERMISSION_DENIED),
    (404, NotFound, grpc.StatusCode.NOT_FOUND),
    (409, ExportBusy, grpc.StatusCode.ABORTED),
    (429, ResourceExhausted, grpc.StatusCode.RESOURCE_EXHAUSTED),
    (500, Internal, grpc.StatusCode.INTERNAL),
]
_STATUS_IDS = [str(status) for status, *_ in _STATUS_MATRIX]


@pytest.mark.parametrize("status,exc,code", _STATUS_MATRIX, ids=_STATUS_IDS)
def test_fail_a_refused_request_raises_its_type_with_the_gateway_text(
    rclient, rest, status, exc, code
):
    rest.post_status, rest.error = status, "from must be before to"
    with pytest.raises(exc) as info:
        list(_export(rclient, "orders"))
    assert type(info.value) is exc
    assert info.value.code is code
    assert info.value.message == "from must be before to"
    assert info.value.rpc == "export_orders"
    assert rest.polls() == []


@pytest.mark.parametrize("status,exc,code", _STATUS_MATRIX, ids=_STATUS_IDS)
async def test_fail_async_a_refused_poll_raises_its_type_with_the_gateway_text(
    raclient, rest, status, exc, code
):
    rest.poll_status, rest.error = status, "generation failed: disk full"
    with pytest.raises(exc) as info:
        await _adrain(_export(raclient, "trades"))
    assert type(info.value) is exc
    assert info.value.message == "generation failed: disk full"
    assert info.value.rpc == "export_trades"


_BUSY = "an export is already running, try again later"
_CAP = "export range exceeds 31 days"


def test_fail_a_busy_gateway_raises_export_busy_with_its_text(rclient, rest):
    """The gateway builds one export at a time and answers a second with 409:
    its own type, never the rate limit's, and nothing is polled."""
    rest.post_status, rest.error = 409, _BUSY
    with pytest.raises(ExportBusy) as info:
        list(_export(rclient, "trades"))
    assert type(info.value) is ExportBusy
    assert not isinstance(info.value, ResourceExhausted)
    assert info.value.code is grpc.StatusCode.ABORTED
    assert info.value.message == _BUSY
    assert info.value.rpc == "export_trades"
    assert info.value.request_definitely_rejected is True
    assert rest.polls() == []


async def test_fail_async_a_busy_gateway_raises_export_busy_with_its_text(raclient, rest):
    rest.post_status, rest.error = 409, _BUSY
    with pytest.raises(ExportBusy) as info:
        await _adrain(_export(raclient, "orders"))
    assert info.value.message == _BUSY
    assert info.value.rpc == "export_orders"


def test_fail_a_window_over_the_cap_raises_invalid_argument_with_its_text(rclient, rest):
    rest.post_status, rest.error = 400, _CAP
    with pytest.raises(InvalidArgument) as info:
        list(
            rclient.export_orders(
                format="csv", from_="2026-05-01T00:00:00Z", to="2026-06-01T01:00:00.001Z"
            )
        )
    assert info.value.code is grpc.StatusCode.INVALID_ARGUMENT
    assert info.value.message == _CAP
    assert rest.posts()[0][3]["to"] == "2026-06-01T01:00:00.001Z", "sent unchecked"
    assert rest.polls() == []


def test_edge_export_busy_is_a_documented_public_error():
    import voltnir_sdk

    assert voltnir_sdk.ExportBusy is ExportBusy
    assert "ExportBusy" in voltnir_sdk.__all__
    assert issubclass(ExportBusy, VoltnirError)
    assert "409" in (ExportBusy.__doc__ or "")


def test_fail_a_failed_generation_raises_internal_with_its_text(rclient, rest):
    rest.pending, rest.poll_status, rest.error = 0, 500, "query failed: database is locked"
    with pytest.raises(Internal, match="query failed: database is locked"):
        list(_export(rclient, "orders"))


def test_fail_any_other_status_raises_the_base_error_naming_it(rclient, rest):
    rest.post_status, rest.error = 418, "short and stout"
    with pytest.raises(VoltnirError) as info:
        list(_export(rclient, "orders"))
    assert type(info.value) is VoltnirError
    assert info.value.code is grpc.StatusCode.UNKNOWN
    assert "418" in info.value.message and "short and stout" in info.value.message


def test_fail_a_wrong_key_is_the_gateways_401(server, rest):
    with (
        VoltnirClient(host="127.0.0.1", port=server, api_key="wrong", rest_url=rest.url) as c,
        pytest.raises(Unauthenticated, match="Unauthorized"),
    ):
        list(_export(c, "orders"))


def test_fail_an_accepted_request_without_a_token_is_named(rclient, rest):
    rest.post_answer = (202, b'{"download_url": "/somewhere"}')
    with pytest.raises(VoltnirError, match="not answered with a token") as info:
        list(_export(rclient, "orders"))
    assert info.value.code is grpc.StatusCode.UNKNOWN


@pytest.mark.parametrize("cls", [VoltnirClient, AsyncVoltnirClient])
async def test_fail_without_rest_url_raises_naming_it_before_any_network_call(
    server, monkeypatch, cls
):
    def no_network(*_a, **_kw):
        raise AssertionError("a request was attempted")

    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", no_network)
    c = cls(host="127.0.0.1", port=server, api_key=REST_KEY)
    try:
        with pytest.raises(ValueError, match="rest_url"):
            c.export_orders(format="csv", from_=_FROM, to=_TO)
    finally:
        closing = c.close()
        if asyncio.iscoroutine(closing):
            await closing


def test_fail_the_overall_timeout_raises_deadline_exceeded(rclient, rest):
    rest.pending = 10**6
    started = time.monotonic()
    with pytest.raises(DeadlineExceeded, match=r"within its 0\.6 s timeout"):
        list(_export(rclient, "orders", timeout=0.6))
    assert time.monotonic() - started < 3.0


async def test_fail_async_the_overall_timeout_raises_deadline_exceeded(raclient, rest):
    rest.pending = 10**6
    started = time.monotonic()
    with pytest.raises(DeadlineExceeded, match=r"within its 0\.6 s timeout"):
        await _adrain(_export(raclient, "trades", timeout=0.6))
    assert time.monotonic() - started < 3.0


def test_fail_a_stalled_request_raises_deadline_exceeded_without_a_timeout(
    rclient, rest, monkeypatch
):
    monkeypatch.setattr(_rest_export, "REQUEST_TIMEOUT_S", 0.3)
    rest.poll_delay = 2.0
    started = time.monotonic()
    with pytest.raises(DeadlineExceeded, match=r"sent nothing for 0\.3 s"):
        list(_export(rclient, "orders"))
    assert time.monotonic() - started < 1.5


@pytest.mark.parametrize("cls", [VoltnirClient, AsyncVoltnirClient])
async def test_fail_a_refused_connection_raises_unavailable(server, cls):
    url = f"http://127.0.0.1:{_free_port()}"
    c = cls(host="127.0.0.1", port=server, api_key=REST_KEY, rest_url=url)
    try:
        stream = c.export_orders(format="csv", from_=_FROM, to=_TO)
        with pytest.raises(Unavailable, match=r"(?i)refused") as info:
            if isinstance(c, AsyncVoltnirClient):
                await _adrain(stream)
            else:
                list(stream)
        assert info.value.code is grpc.StatusCode.UNAVAILABLE
        assert url in info.value.message
    finally:
        closing = c.close()
        if asyncio.iscoroutine(closing):
            await closing


def test_fail_a_download_cut_short_raises_unavailable(rclient, rest):
    rest.body, rest.short_by = _CSV, 100
    with pytest.raises(Unavailable, match="cut short"):
        list(_export(rclient, "orders"))


def test_fail_a_closed_client_raises_client_closed(server, rest):
    c = VoltnirClient(host="127.0.0.1", port=server, api_key=REST_KEY, rest_url=rest.url)
    c.close()
    with pytest.raises(ClientClosed):
        c.export_trades(format="csv", from_=_FROM, to=_TO)


@pytest.mark.parametrize("url", ["gateway.example:3000", "ftp://gateway.example", "https://"])
def test_fail_a_rest_url_that_is_not_http_is_refused_at_construction(server, url):
    with pytest.raises(ValueError, match="rest_url"):
        VoltnirClient(host="127.0.0.1", port=server, api_key=REST_KEY, rest_url=url)


# ── edge ────────────────────────────────────────────────────────────────────


def test_edge_a_trailing_slash_on_rest_url_is_not_doubled(server, rest):
    with VoltnirClient(
        host="127.0.0.1", port=server, api_key=REST_KEY, rest_url=rest.url + "/"
    ) as c:
        assert b"".join(_export(c, "orders")) == rest.body
    assert rest.posts()[0][1] == "/api/v1/audit/export/orders"
    assert rest.polls()[0][1] == f"/api/v1/audit/export/{REST_TOKEN}"


def test_edge_an_empty_file_yields_nothing(rclient, rest):
    rest.body = b""
    assert list(_export(rclient, "trades")) == []


async def test_edge_async_an_empty_file_yields_nothing(raclient, rest):
    rest.body = b""
    assert await _adrain(_export(raclient, "orders")) == []


def test_edge_nothing_is_sent_until_the_first_iteration(rclient, rest):
    stream = _export(rclient, "orders")
    assert rest.requests == []
    assert b"".join(stream) == rest.body


def test_edge_https_rest_url_trusts_ca_cert_path(server, tmp_path, monkeypatch):
    pem = tmp_path / "ca.pem"
    pem.write_bytes(_TEST_CA)
    built: list[dict] = []
    real = ssl.create_default_context

    def spy(*args, **kwargs):
        built.append(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(ssl, "create_default_context", spy)
    with VoltnirClient(
        host="127.0.0.1", port=server, api_key=REST_KEY,
        ca_cert_path=str(pem), rest_url="https://gateway.example:3000",
    ) as c:
        subjects = [cert["subject"] for cert in c._rest.ssl_context.get_ca_certs()]
    assert built == [{"cadata": _TEST_CA.decode()}]
    assert subjects == [((("commonName", "voltnir-sdk-test-ca"),),)]


def test_edge_https_without_ca_cert_path_uses_the_system_trust_store(server, monkeypatch):
    built: list[dict] = []
    real = ssl.create_default_context
    monkeypatch.setattr(
        ssl, "create_default_context", lambda **kw: built.append(kw) or real(**kw)
    )
    VoltnirClient(
        host="127.0.0.1", port=server, api_key=REST_KEY, rest_url="https://gw.example:3000"
    ).close()
    assert built == [{}]


def test_edge_http_rest_url_builds_no_tls_context(server, tmp_path):
    pem = tmp_path / "ca.pem"
    pem.write_bytes(_TEST_CA)
    with VoltnirClient(
        host="127.0.0.1", port=server, api_key=REST_KEY,
        ca_cert_path=str(pem), rest_url="http://127.0.0.1:3000",
    ) as c:
        assert c._rest.ssl_context is None


def test_edge_a_ca_file_tls_cannot_load_is_refused_for_https(server, tmp_path):
    """A PEM-shaped file that is not a certificate gRPC would accept until the
    handshake; for an https rest_url it fails at construction, naming the file."""
    pem = tmp_path / "junk.pem"
    pem.write_bytes(b"-----BEGIN CERTIFICATE-----\nAAAA\n-----END CERTIFICATE-----\n")
    with pytest.raises(CaCertificateError, match=r"junk\.pem"):
        VoltnirClient(
            host="127.0.0.1", port=server, api_key=REST_KEY,
            ca_cert_path=str(pem), rest_url="https://gateway.example:3000",
        )


async def test_edge_async_export_leaves_the_event_loop_free(raclient, rest):
    """Another task keeps running while a slow poll is in flight."""
    rest.pending, rest.poll_delay = 1, 0.3
    ticks = 0

    async def ticker() -> None:
        nonlocal ticks
        while True:
            await asyncio.sleep(0.01)
            ticks += 1

    task = asyncio.create_task(ticker())
    try:
        assert b"".join(await _adrain(_export(raclient, "orders"))) == rest.body
    finally:
        task.cancel()
    # Two polls of 0.3 s plus one 0.25 s wait: a blocked loop would tick a few
    # times at most, a free one about eighty.
    assert ticks >= 30, f"the loop ticked only {ticks} times during the export"


def test_edge_polls_back_off_from_a_quarter_second_to_two():
    delays = [_rest_export.FIRST_POLL_S]
    for _ in range(5):
        delays.append(_rest_export.next_delay(delays[-1]))
    assert delays == [0.25, 0.5, 1.0, 2.0, 2.0, 2.0]


def test_edge_a_poll_wait_is_cut_to_what_the_timeout_leaves():
    deadline = _rest_export.Deadline(0.1)
    assert _rest_export.pause(2.0, deadline, "export_orders") <= 0.1
    assert _rest_export.pause(2.0, _rest_export.Deadline(None), "export_orders") == 2.0


# ── round two: redirects, rate limits, trickles, cancels, closes ────────────


def test_fail_a_rate_limit_carries_the_gateways_message_not_its_code(rclient, rest):
    """The gateway's 429 body is `{"error": "RATE_LIMITED", "message": ...}`:
    the sentence is the message, as the same refusal over gRPC reads."""
    sentence = "request rate limit exceeded: at most 6000 requests per 60s per API key"
    rest.post_answer = (429, json.dumps({"error": "RATE_LIMITED", "message": sentence}).encode())
    with pytest.raises(ResourceExhausted) as info:
        list(_export(rclient, "orders"))
    assert info.value.code is grpc.StatusCode.RESOURCE_EXHAUSTED
    assert info.value.message == sentence


class _Sink(BaseHTTPRequestHandler):
    seen: ClassVar[list[dict[str, str]]] = []

    def log_message(self, *args: object) -> None:
        return

    def do_GET(self) -> None:
        type(self).seen.append(dict(self.headers))
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_POST = do_GET


def test_fail_a_redirect_is_refused_and_the_key_never_leaves(rclient, rest):
    """A 302 to another host is not followed, so the bearer token is never sent
    there; the 3xx is raised naming its status."""
    _Sink.seen = []
    sink = ThreadingHTTPServer(("127.0.0.1", 0), _Sink)
    threading.Thread(target=sink.serve_forever, args=(0.02,), daemon=True).start()
    try:
        rest.redirect_to = f"http://localhost:{sink.server_address[1]}/elsewhere"
        with pytest.raises(VoltnirError) as info:
            list(_export(rclient, "orders"))
    finally:
        sink.shutdown()
        sink.server_close()
    assert type(info.value) is VoltnirError
    assert "302" in info.value.message and "not followed" in info.value.message
    assert _Sink.seen == []


def test_edge_the_api_key_is_not_in_the_endpoints_repr():
    endpoint = _rest_export.make_endpoint("http://127.0.0.1:1", "SECRET-KEY-123", None)
    assert "SECRET-KEY-123" not in repr(endpoint)
    assert endpoint.api_key == "SECRET-KEY-123"


def test_fail_a_trickling_body_cannot_outlast_the_timeout(rclient, rest):
    """One byte every 0.1 s: each read returns as bytes arrive and the overall
    timeout is checked between them, so the export ends at its timeout."""
    rest.body, rest.piece, rest.piece_delay = b"x" * 100, 1, 0.1
    started = time.monotonic()
    with pytest.raises(DeadlineExceeded, match=r"within its 1 s timeout"):
        list(_export(rclient, "orders", timeout=1.0))
    assert time.monotonic() - started < 1.5


def test_fail_a_stalled_body_read_raises_deadline_exceeded(rclient, rest, monkeypatch):
    """A body that stops mid-file is a read timeout, so DeadlineExceeded, not
    Unavailable."""
    monkeypatch.setattr(_rest_export, "REQUEST_TIMEOUT_S", 0.3)
    rest.body, rest.gate_after = b"x" * (2 * _CHUNK), _CHUNK
    stream = _export(rclient, "orders")
    assert len(next(stream)) <= _CHUNK
    with pytest.raises(DeadlineExceeded, match=r"sent nothing for 0\.3 s"):
        list(stream)


async def _ticking(coro) -> tuple[object, int]:
    """Await `coro` while a ticker task counts 10 ms sleeps."""
    ticks = 0

    async def ticker() -> None:
        nonlocal ticks
        while True:
            await asyncio.sleep(0.01)
            ticks += 1

    task = asyncio.create_task(ticker())
    try:
        return await coro, ticks
    finally:
        task.cancel()


async def test_edge_async_slow_body_reads_leave_the_loop_free(raclient, rest):
    """Four pieces 0.25 s apart: the reads run in a worker thread, so the loop
    keeps ticking while each waits for its bytes."""
    rest.body, rest.piece, rest.piece_delay = b"y" * 4096, 1024, 0.25
    chunks, ticks = await _ticking(_adrain(_export(raclient, "orders")))
    assert b"".join(chunks) == rest.body
    assert ticks >= 40, f"the loop ticked only {ticks} times during a 0.75 s body"


async def test_edge_async_slow_export_request_leaves_the_loop_free(raclient, rest):
    """A POST that takes 0.5 s to answer: the request runs in a worker thread."""
    rest.post_delay = 0.5
    chunks, ticks = await _ticking(_adrain(_export(raclient, "trades")))
    assert b"".join(chunks) == rest.body
    assert ticks >= 25, f"the loop ticked only {ticks} times during a 0.5 s POST"


async def test_edge_cancelling_a_stalled_async_read_does_not_hold_the_loop(raclient, rest):
    """A task awaiting the next chunk while the body stalls is cancelled: the
    cancel completes at once and the loop keeps ticking, rather than waiting for
    the blocked read to time out."""
    rest.body, rest.gate_after = b"z" * (3 * _CHUNK), _CHUNK
    stream = _export(raclient, "orders")
    assert await anext(stream)
    pending = asyncio.ensure_future(anext(stream))
    await asyncio.sleep(0.3)

    async def cancel() -> float:
        pending.cancel()
        started = time.monotonic()
        with pytest.raises(asyncio.CancelledError):
            await pending
        return time.monotonic() - started

    took, ticks = await _ticking(_settled(cancel()))
    assert took < 0.5, f"the cancel held the loop for {took:.2f} s"
    assert ticks >= 20, f"the loop ticked only {ticks} times around the cancel"


async def _settled(coro):
    """`coro`'s result, then a further 0.3 s so a ticker can show the loop is free."""
    result = await coro
    await asyncio.sleep(0.3)
    return result


def _spy_closes(monkeypatch) -> threading.Event:
    closed = threading.Event()
    real = _rest_export.Download.close

    def close(self) -> None:
        closed.set()
        real(self)

    monkeypatch.setattr(_rest_export.Download, "close", close)
    return closed


def test_edge_breaking_out_early_closes_the_download(rclient, rest, monkeypatch):
    closed = _spy_closes(monkeypatch)
    rest.body, rest.gate_after = b"w" * (4 * _CHUNK), _CHUNK
    stream = _export(rclient, "orders")
    assert next(stream)
    stream.close()  # what a `break` out of a `for` does once the iterator is dropped
    assert closed.is_set()
    rest.gate.set()
    assert rest.closed.wait(2), "the server kept writing to an open connection"


async def test_edge_async_breaking_out_early_closes_the_download(raclient, rest, monkeypatch):
    closed = _spy_closes(monkeypatch)
    rest.body, rest.gate_after = b"w" * (4 * _CHUNK), _CHUNK
    stream = _export(raclient, "trades")
    async for _chunk in stream:
        break
    await stream.aclose()
    assert await asyncio.to_thread(closed.wait, 2), "the download was never closed"
    rest.gate.set()
    assert await asyncio.to_thread(rest.closed.wait, 2)


def test_fail_a_stall_late_in_the_export_still_ends_at_the_timeout(rclient, rest):
    """Bytes trickle for 0.8 s, then stop: each read's socket timeout is cut to
    what is left of the 1 s timeout, so the stalled read ends at the timeout,
    not a whole socket timeout after it began."""
    rest.body, rest.piece, rest.piece_delay, rest.gate_after = b"x" * 100, 1, 0.1, 8
    started = time.monotonic()
    with pytest.raises(DeadlineExceeded, match=r"within its 1 s timeout"):
        list(_export(rclient, "orders", timeout=1.0))
    assert time.monotonic() - started < 1.4


def test_edge_a_real_response_exposes_the_socket_the_read_timeout_needs(rest):
    """Pins the private `SocketIO._sock` path `_socket_of` relies on: if a
    Python release drops it, the per-read timeout reset and the cancel abort
    stop working, so this must fail loudly rather than degrade silently."""
    endpoint = _rest_export.make_endpoint(rest.url, REST_KEY, None)
    body = json.dumps({"format": "csv", "from": _FROM, "to": _TO}).encode()
    resp = _rest_export._open(
        endpoint, "/api/v1/audit/export/orders", body, _rest_export.Deadline(5.0), "export_orders"
    )
    try:
        assert isinstance(_rest_export._socket_of(resp), socket.socket)
    finally:
        resp.close()
    assert _rest_export._socket_of(resp) is None
