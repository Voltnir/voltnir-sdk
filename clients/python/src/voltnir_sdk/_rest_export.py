"""Report exports over the gateway's REST API, shared by both clients.

The gateway builds an export in the background and serves it as a file, so the
SDK fetches it over REST, not gRPC:

1. ``POST /api/v1/audit/export/{orders|trades}`` with ``{format, from, to}``
   and the history read's filters (``area``, ``product``, ``user_code``,
   ``v_member_short_id``, ``voltnir_user_short_id``, ``voltnir_username``, plus
   ``status`` for orders or ``time_basis`` for trades), or ``POST /api/v1/audit/export/events`` (the audit
   trail) with ``{format, from, to, action?, target_type?, actor_short_id?,
   outcome?, v_member_short_id?}``, answers ``202 {token, download_url}``;
2. ``GET /api/v1/audit/export/{token}`` answers ``202`` while the file is being
   built and ``200`` with the file once it is ready;
3. the ``200`` body is read a chunk at a time and handed to the caller as it
   arrives, so a large report is never held in memory whole.

Only the standard library is used (``urllib``, ``ssl``, ``json``). Every request
carries the ``Authorization: Bearer <api key>`` header the gRPC calls carry, so a
redirect is never followed: following one would hand the key to whatever host
the ``Location`` names, over whatever scheme. A ``3xx`` is raised instead.

Every read is bounded twice: each socket read by ``REQUEST_TIMEOUT_S`` or what is
left of the caller's ``timeout``, whichever is shorter, and a chunk is returned as
soon as any bytes arrive, so a trickling body cannot outlast the ``timeout``.

Nothing here validates ``format`` or the window: the gateway does, and its
answer (``400`` with the reason, such as a window wider than 31 days and one hour) is raised
as ``InvalidArgument`` carrying the gateway's own words. The gateway builds one
report at a time, so a request made while another is generating is answered
``409`` and raised as ``ExportBusy``.
"""

from __future__ import annotations

import asyncio
import contextlib
import http.client
import json
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from typing import Any

import grpc

from .channel import read_ca_pem
from .errors import (
    CaCertificateError,
    DeadlineExceeded,
    ExportBusy,
    Internal,
    InvalidArgument,
    NotFound,
    PermissionDenied,
    ResourceExhausted,
    Unauthenticated,
    Unavailable,
    VoltnirError,
)

#: Largest piece of the file handed to the caller at once; a piece is handed
#: over as soon as any bytes arrive, so most are smaller.
CHUNK_BYTES = 64 * 1024
#: The longest one request may go without receiving a byte. It stops a stalled
#: connection hanging the export for ever when the caller set no `timeout`.
REQUEST_TIMEOUT_S = 30.0
#: The first wait between polls; each later wait doubles, up to MAX_POLL_S.
FIRST_POLL_S = 0.25
MAX_POLL_S = 2.0

_EXPORT_PATH = "/api/v1/audit/export/"
_ERROR_BODY_BYTES = 64 * 1024
_ERROR_TEXT_CHARS = 500

_STATUS_ERRORS: dict[int, tuple[type[VoltnirError], grpc.StatusCode]] = {
    400: (InvalidArgument, grpc.StatusCode.INVALID_ARGUMENT),
    401: (Unauthenticated, grpc.StatusCode.UNAUTHENTICATED),
    403: (PermissionDenied, grpc.StatusCode.PERMISSION_DENIED),
    404: (NotFound, grpc.StatusCode.NOT_FOUND),
    # Another export is generating; the gateway builds one at a time.
    409: (ExportBusy, grpc.StatusCode.ABORTED),
    # The gateway's per-key request bound; over gRPC it is RESOURCE_EXHAUSTED.
    429: (ResourceExhausted, grpc.StatusCode.RESOURCE_EXHAUSTED),
    500: (Internal, grpc.StatusCode.INTERNAL),
}


@dataclass(frozen=True)
class RestEndpoint:
    """Where the gateway's REST API answers, and how to trust and authorise it."""

    base_url: str
    api_key: str = field(repr=False)  # a bearer credential: never in a repr or a log
    ssl_context: ssl.SSLContext | None = None


def make_endpoint(
    rest_url: str | None, api_key: str, ca_cert_path: str | None
) -> RestEndpoint | None:
    """The endpoint for `rest_url`, or None when the client has none.

    Checked at client construction, like the gRPC channel's TLS file, so a bad
    URL or CA file fails where the mistake is rather than on the first export.
    """
    if rest_url is None:
        return None
    parts = urllib.parse.urlsplit(rest_url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError(
            f"rest_url {rest_url!r} is not an http:// or https:// URL; "
            f"pass the gateway's REST address, e.g. 'https://gateway.example:3000'"
        )
    context = _ssl_context(ca_cert_path) if parts.scheme == "https" else None
    return RestEndpoint(rest_url.rstrip("/"), api_key, context)


def _ssl_context(ca_cert_path: str | None) -> ssl.SSLContext:
    """The system trust store, or only the PEM at `ca_cert_path` when given."""
    if ca_cert_path is None:
        return ssl.create_default_context()
    pem = read_ca_pem(ca_cert_path).decode("ascii", errors="ignore")
    try:
        return ssl.create_default_context(cadata=pem)
    except ssl.SSLError as exc:
        raise CaCertificateError(
            f"ca_cert_path {ca_cert_path!r} holds a certificate block the TLS "
            f"library cannot load: {exc}"
        ) from exc


def require(endpoint: RestEndpoint | None, op: str) -> RestEndpoint:
    """The endpoint, or a `ValueError` naming `rest_url` before anything is sent."""
    if endpoint is None:
        raise ValueError(
            f"{op} downloads the report over the gateway's REST API, so the "
            f"client needs rest_url, e.g. rest_url='https://gateway.example:3000'"
        )
    return endpoint


def request_body(format: str, from_: str, to: str, **filters: str | None) -> dict[str, str]:
    """The POST body: the window, the format and the export's own filters, each
    under its wire name. An omitted filter is left out rather than sent empty."""
    body = {"format": format, "from": from_, "to": to}
    body.update({name: value for name, value in filters.items() if value is not None})
    return body


class Deadline:
    """The caller's overall `timeout`, measured from the start of the export."""

    def __init__(self, timeout: float | None) -> None:
        self.timeout = timeout
        self._end = None if timeout is None else time.monotonic() + timeout

    def remaining(self) -> float | None:
        return None if self._end is None else self._end - time.monotonic()

    def expired(self) -> bool:
        remaining = self.remaining()
        return remaining is not None and remaining <= 0

    def socket_timeout(self) -> float:
        """One request's socket timeout: REQUEST_TIMEOUT_S, cut to what is left."""
        remaining = self.remaining()
        if remaining is None:
            return REQUEST_TIMEOUT_S
        return max(min(REQUEST_TIMEOUT_S, remaining), 0.001)

    def check(self, op: str) -> None:
        if self.expired():
            raise self.error(op)

    def error(self, op: str) -> DeadlineExceeded:
        """The timeout that ended the export: the caller's, or one silent request."""
        if self.timeout is not None and (self.remaining() or 0.0) <= 0.05:
            text = f"the export did not finish within its {self.timeout:g} s timeout"
        else:
            text = f"the gateway's REST API sent nothing for {REQUEST_TIMEOUT_S:g} s"
        return DeadlineExceeded(grpc.StatusCode.DEADLINE_EXCEEDED, text, op)


def status_error(status: int, text: str, op: str) -> VoltnirError:
    """The typed error for an HTTP status, carrying the gateway's own text."""
    cls, code = _STATUS_ERRORS.get(status, (VoltnirError, grpc.StatusCode.UNKNOWN))
    if 300 <= status < 400:
        text = f"unexpected HTTP status {status}, a redirect, which is not followed: {text}"
    elif cls is VoltnirError:
        text = f"unexpected HTTP status {status}: {text}"
    return cls(code, text, op)


def _error_text(err: urllib.error.HTTPError) -> str:
    """The `message` field of a JSON error body, else its `error` field, else the
    body's text, else the reason. A rate-limit answer carries a code in `error`
    and the sentence in `message`; every other refusal carries only `error`."""
    try:
        raw = err.read(_ERROR_BODY_BYTES)
    except (OSError, http.client.HTTPException):
        raw = b""
    finally:
        err.close()
    text = raw.decode("utf-8", errors="replace").strip()
    try:
        payload = json.loads(text)
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        for key in ("message", "error"):
            if isinstance(payload.get(key), str):
                return payload[key]
    return text[:_ERROR_TEXT_CHARS] or str(err.reason)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse every redirect, so the 3xx surfaces as an HTTPError."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def _opener(endpoint: RestEndpoint) -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(
        _NoRedirect, urllib.request.HTTPSHandler(context=endpoint.ssl_context)
    )


def _transport_error(
    endpoint: RestEndpoint, reason: object, deadline: Deadline, op: str
) -> VoltnirError:
    if isinstance(reason, TimeoutError):
        return deadline.error(op)
    return Unavailable(
        grpc.StatusCode.UNAVAILABLE,
        f"cannot reach the gateway's REST API at {endpoint.base_url}: {reason}",
        op,
    )


def _open(
    endpoint: RestEndpoint, path: str, body: bytes | None, deadline: Deadline, op: str
) -> http.client.HTTPResponse:
    """One request; a status of 400 or more is raised as its typed error."""
    deadline.check(op)
    headers = {"Authorization": f"Bearer {endpoint.api_key}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        endpoint.base_url + path,
        data=body,
        headers=headers,
        method="GET" if body is None else "POST",
    )
    try:
        return _opener(endpoint).open(req, timeout=deadline.socket_timeout())
    except urllib.error.HTTPError as err:
        raise status_error(err.code, _error_text(err), op) from err
    except urllib.error.URLError as err:
        raise _transport_error(endpoint, err.reason, deadline, op) from err
    except (OSError, http.client.HTTPException) as err:
        raise _transport_error(endpoint, err, deadline, op) from err


def _read(
    resp: http.client.HTTPResponse,
    size: int,
    endpoint: RestEndpoint,
    deadline: Deadline,
    op: str,
) -> bytes:
    """Up to `size` bytes of the body, as soon as any arrive; b"" at its end."""
    deadline.check(op)
    sock = _socket_of(resp)
    try:
        if sock is not None:
            sock.settimeout(deadline.socket_timeout())
        return resp.read1(size)
    except (OSError, http.client.HTTPException) as err:
        if isinstance(err, TimeoutError):
            raise deadline.error(op) from err
        raise Unavailable(
            grpc.StatusCode.UNAVAILABLE,
            f"the download from the gateway's REST API at {endpoint.base_url} "
            f"was interrupted: {err}",
            op,
        ) from err


def start(
    endpoint: RestEndpoint, kind: str, body: dict[str, str], deadline: Deadline, op: str
) -> str:
    """POST the export request; returns the path to poll for the file."""
    data = json.dumps(body).encode("utf-8")
    with _open(endpoint, _EXPORT_PATH + kind, data, deadline, op) as resp:
        status = resp.status
        raw = b""
        while len(raw) < _ERROR_BODY_BYTES and (
            piece := _read(resp, _ERROR_BODY_BYTES - len(raw), endpoint, deadline, op)
        ):
            raw += piece
    try:
        payload: Any = json.loads(raw)
    except ValueError:
        payload = None
    token = payload.get("token") if isinstance(payload, dict) else None
    if status != 202 or not isinstance(token, str) or not token:
        raise VoltnirError(
            grpc.StatusCode.UNKNOWN,
            f"unexpected HTTP status {status}: the export request was not "
            f"answered with a token",
            op,
        )
    return _EXPORT_PATH + urllib.parse.quote(token, safe="")


def poll(
    endpoint: RestEndpoint, path: str, deadline: Deadline, op: str
) -> http.client.HTTPResponse | None:
    """The ready file's open response, or None while it is still being built."""
    resp = _open(endpoint, path, None, deadline, op)
    if resp.status == 200:
        return resp
    resp.close()
    if resp.status == 202:
        return None
    raise VoltnirError(
        grpc.StatusCode.UNKNOWN,
        f"unexpected HTTP status {resp.status} while waiting for the export",
        op,
    )


def pause(delay: float, deadline: Deadline, op: str) -> float:
    """The wait before the next poll: `delay`, cut to what the timeout leaves."""
    remaining = deadline.remaining()
    if remaining is None:
        return delay
    if remaining <= 0:
        raise deadline.error(op)
    return min(delay, remaining)


def next_delay(delay: float) -> float:
    return min(delay * 2, MAX_POLL_S)


class Download:
    """The ready file's body, read a chunk at a time.

    The gateway states the file's size in `Content-Length` and closes the
    connection early if a read fails after the headers went out, so a body that
    ends short of that size is an interrupted download, never a whole file.
    """

    def __init__(
        self,
        resp: http.client.HTTPResponse,
        endpoint: RestEndpoint,
        deadline: Deadline,
        op: str,
    ) -> None:
        self._resp, self._endpoint = resp, endpoint
        self._deadline, self._op = deadline, op
        self._expected = _content_length(resp)
        self._received = 0

    def next_chunk(self) -> bytes:
        """The next piece of the file, or b"" once all of it has arrived."""
        chunk = _read(self._resp, CHUNK_BYTES, self._endpoint, self._deadline, self._op)
        self._received += len(chunk)
        short = self._expected is not None and self._received < self._expected
        if not chunk and short:
            raise Unavailable(
                grpc.StatusCode.UNAVAILABLE,
                f"the download was cut short: {self._received} of "
                f"{self._expected} bytes arrived",
                self._op,
            )
        return chunk

    def close(self) -> None:
        self._resp.close()

    def abort(self) -> None:
        """Wake a read blocked in another thread: shut the socket down, which
        needs none of the lock that read holds, so this never waits on it."""
        sock = _socket_of(self._resp)
        if sock is not None:
            with contextlib.suppress(OSError):  # already shut or closed
                sock.shutdown(socket.SHUT_RDWR)


def _socket_of(resp: http.client.HTTPResponse) -> socket.socket | None:
    """The response's socket, or None once it is closed. `http.client` reads
    the body through `sock.makefile("rb")`, a buffered reader over a SocketIO
    holding the socket; the socket is the only handle on the read timeout.

    `SocketIO._sock` is private, but it has been CPython's (and PyPy's) path
    since 3.0, and a test pins it on a real response. Without the socket the
    fallback is still safe: a read keeps the timeout it was opened with, so it
    can overrun the deadline by at most one socket timeout, and a cancelled
    async export closes after the blocked read returns, still off the loop."""
    sock = getattr(getattr(resp.fp, "raw", None), "_sock", None)
    return sock if isinstance(sock, socket.socket) else None


def _content_length(resp: http.client.HTTPResponse) -> int | None:
    value = resp.headers.get("Content-Length")
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def export(
    endpoint: RestEndpoint, kind: str, body: dict[str, str], timeout: float | None, op: str
) -> Iterator[bytes]:
    """Request, poll and stream one export (blocking). `kind` is the endpoint's
    last path segment; `op` is the client method named on every error."""
    deadline = Deadline(timeout)
    path = start(endpoint, kind, body, deadline, op)
    delay = FIRST_POLL_S
    while (resp := poll(endpoint, path, deadline, op)) is None:
        time.sleep(pause(delay, deadline, op))
        delay = next_delay(delay)
    download = Download(resp, endpoint, deadline, op)
    try:
        while chunk := download.next_chunk():
            yield chunk
    finally:
        download.close()


async def aexport(
    endpoint: RestEndpoint, kind: str, body: dict[str, str], timeout: float | None, op: str
) -> AsyncIterator[bytes]:
    """`export` for the event loop: every blocking step runs in a worker thread."""
    deadline = Deadline(timeout)
    path = await asyncio.to_thread(start, endpoint, kind, body, deadline, op)
    delay = FIRST_POLL_S
    while (resp := await asyncio.to_thread(poll, endpoint, path, deadline, op)) is None:
        await asyncio.sleep(pause(delay, deadline, op))
        delay = next_delay(delay)
    download = Download(resp, endpoint, deadline, op)
    try:
        while chunk := await asyncio.to_thread(download.next_chunk):
            yield chunk
    finally:
        # A cancel can land while a worker thread is blocked in a read holding
        # the response's lock; closing here would wait for that read on the
        # loop. Wake the read instead and close from a worker thread.
        download.abort()
        asyncio.get_running_loop().run_in_executor(None, download.close)
