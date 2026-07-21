"""gRPC channel construction for sync and async clients.

Voltnir runs plaintext HTTP/2 by default. TLS is opt-in. Self-signed dev
certs are supported by passing `ca_cert_path` so the SDK trusts the PEM the
server is presenting.

Channel options matter more here than in a typical RPC client, for two
reasons that both bite trading desks specifically:

**Keepalive.** `Watch*` subscriptions are long-lived and can be legitimately
quiet for minutes. Without HTTP/2 keepalive, a NAT table entry or a load
balancer idle timeout silently drops the connection and the iterator simply
blocks forever: no exception, no data. A desk stops receiving fills and cannot
distinguish that from a quiet market. The defaults below keep the connection
provably alive and surface a dead peer as an error instead of as silence.

Against a black-holed connection (an *established* stream that stops passing
traffic, as a NAT table eviction produces) these defaults surface
`Unavailable: Stream removed (ping timeout)`. Without keepalive the same
condition blocks indefinitely with no exception and no data.

Two operational caveats worth planning around:

- **Detection takes about 60 seconds and is not tunable downward.** Lowering
  `keepalive_time_ms` / `keepalive_timeout_ms` does not shorten it, so treat
  ~60s as the blind window and do not rely on the stream itself to notice
  faster than that.
- **gRPC silently ignores unknown option names**, so a typo in an `options`
  entry is invisible: no error, no warning, no effect.

**Message size.** gRPC defaults to a 4 MB receive limit. A `ListContracts` on
a large delivery area, or an `ExportOrders` chunk, exceeds that, and without a
way to raise it the failure is terminal for the caller: it is a client-side
limit, so no server-side change helps. The default here is 64 MB, and
`options` is a passthrough for anything else.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import grpc
import grpc.aio

from .errors import CaCertificateError

# 64 MiB. gRPC's own default is 4 MiB, which a busy delivery area exceeds on
# ListContracts alone. Raised rather than removed (-1 == unlimited) so a runaway
# response still fails loudly instead of exhausting the client's memory.
DEFAULT_MAX_MESSAGE_LENGTH = 64 * 1024 * 1024

# Keepalive tuned for long-lived Watch* streams through NAT and load balancers.
# 30s is comfortably under the common 60s idle timeout. permit_without_calls
# keeps an idle-but-subscribed connection alive, which is the exact case that
# breaks without it, and max_pings_without_data=0 disables gRPC's own throttling
# of pings on a quiet connection, which would otherwise defeat the purpose.
DEFAULT_CHANNEL_OPTIONS: tuple[tuple[str, int], ...] = (
    ("grpc.keepalive_time_ms", 30_000),
    ("grpc.keepalive_timeout_ms", 10_000),
    ("grpc.keepalive_permit_without_calls", 1),
    ("grpc.http2.max_pings_without_data", 0),
    ("grpc.max_receive_message_length", DEFAULT_MAX_MESSAGE_LENGTH),
    ("grpc.max_send_message_length", DEFAULT_MAX_MESSAGE_LENGTH),
)


def build_options(
    overrides: Sequence[tuple[str, object]] | None,
) -> list[tuple[str, object]]:
    """Merge caller options over the defaults; the caller wins on a key clash.

    gRPC itself takes the last value for a repeated key, so appending would be
    enough for it, but de-duplicating keeps the effective configuration
    inspectable: one entry per key is a thing you can read and assert on.
    """
    merged: dict[str, object] = dict(DEFAULT_CHANNEL_OPTIONS)
    for key, value in overrides or ():
        merged[key] = value
    return list(merged.items())


# A PEM certificate block. Checked structurally at construction rather than
# left to the first connect, because gRPC accepts arbitrary bytes here and the
# failure otherwise surfaces much later as an opaque TLS handshake error with
# no mention of the file that caused it.
_PEM_MARKER = b"-----BEGIN CERTIFICATE-----"


def _credentials(ca_cert_path: str | None) -> grpc.ChannelCredentials:
    if ca_cert_path is None:
        return grpc.ssl_channel_credentials()

    path = Path(ca_cert_path)
    try:
        pem = path.read_bytes()
    except OSError as exc:
        # A typo'd path must fail loudly and name itself, never fall back to
        # the system trust store: silently trusting a different set of roots
        # than the operator configured is the worst possible degradation.
        raise CaCertificateError(
            f"ca_cert_path {ca_cert_path!r} could not be read: {exc}"
        ) from exc

    if _PEM_MARKER not in pem:
        raise CaCertificateError(
            f"ca_cert_path {ca_cert_path!r} does not look like a PEM "
            f"certificate (no {_PEM_MARKER.decode()!r} block). gRPC accepts "
            f"these bytes and fails later with an opaque handshake error, so "
            f"it is rejected here instead."
        )
    return grpc.ssl_channel_credentials(root_certificates=pem)


def build_sync_channel(
    host: str,
    port: int,
    *,
    tls: bool,
    ca_cert_path: str | None,
    options: Sequence[tuple[str, object]] | None = None,
) -> grpc.Channel:
    target = f"{host}:{port}"
    opts = build_options(options)
    if tls:
        return grpc.secure_channel(target, _credentials(ca_cert_path), options=opts)
    return grpc.insecure_channel(target, options=opts)


def build_async_channel(
    host: str,
    port: int,
    *,
    tls: bool,
    ca_cert_path: str | None,
    options: Sequence[tuple[str, object]] | None = None,
) -> grpc.aio.Channel:
    target = f"{host}:{port}"
    opts = build_options(options)
    if tls:
        return grpc.aio.secure_channel(
            target, _credentials(ca_cert_path), options=opts
        )
    return grpc.aio.insecure_channel(target, options=opts)
