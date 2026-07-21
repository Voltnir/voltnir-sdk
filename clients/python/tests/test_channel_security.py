"""The channel is configured the way the caller asked: happy/fail/edge.

Transport configuration fails silently when it fails at all. A `tls=True` that
produces a plaintext channel still connects, still works, and sends the bearer
token in the clear. A dropped keepalive option produces a stream that dies
quietly behind NAT. Neither raises anything.

So these assert on the arguments that actually reach gRPC, not on the SDK's own
constants. Comparing `DEFAULT_CHANNEL_OPTIONS` to itself is a change-detector:
it passes whether or not the options are applied, which is the one thing worth
knowing.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import grpc
import pytest

from voltnir_sdk import CaCertificateError, VoltnirClient
from voltnir_sdk.channel import (
    DEFAULT_MAX_MESSAGE_LENGTH,
    build_async_channel,
    build_sync_channel,
)


@pytest.fixture
def spy(monkeypatch):
    """Capture what actually reaches grpc's channel constructors."""
    calls: dict[str, dict] = {}

    def _record(name):
        def inner(target, *args, **kwargs):
            calls[name] = {"target": target, "args": args, "kwargs": kwargs}
            # MagicMock rather than a bare object: constructing VoltnirClient
            # builds a stub from the channel, which requires the channel API.
            # Nothing dials, because no RPC is ever issued in this module.
            return MagicMock()

        return inner

    monkeypatch.setattr(grpc, "insecure_channel", _record("insecure"))
    monkeypatch.setattr(grpc, "secure_channel", _record("secure"))
    monkeypatch.setattr(grpc.aio, "insecure_channel", _record("aio_insecure"))
    monkeypatch.setattr(grpc.aio, "secure_channel", _record("aio_secure"))
    return calls


# ── TLS is real TLS ─────────────────────────────────────────────────────────


def test_happy_tls_true_builds_a_secure_channel(spy):
    """tls=True must reach `secure_channel`, never `insecure_channel`.

    The failure this guards is silent and total: a plaintext channel under a
    `tls=True` the caller trusts, carrying the bearer token in the clear.
    """
    build_sync_channel("h", 1, tls=True, ca_cert_path=None)
    assert "secure" in spy, "tls=True did not build a secure channel"
    assert "insecure" not in spy


def test_happy_tls_false_builds_an_insecure_channel(spy):
    build_sync_channel("h", 1, tls=False, ca_cert_path=None)
    assert "insecure" in spy
    assert "secure" not in spy


def test_happy_async_tls_true_builds_a_secure_channel(spy):
    """The async path is a separate code path and needs its own proof."""
    build_async_channel("h", 1, tls=True, ca_cert_path=None)
    assert "aio_secure" in spy
    assert "aio_insecure" not in spy


def test_happy_ca_cert_is_read_and_passed_as_root_certificates(spy, tmp_path, monkeypatch):
    """A custom CA must reach the credentials, not be silently ignored.

    Ignoring it does not fail loudly: the connection falls back to the system
    trust store and either rejects a self-signed dev cert with a confusing TLS
    error, or succeeds against a peer the operator never chose to trust.
    """
    pem = tmp_path / "ca.pem"
    pem.write_bytes(b"-----BEGIN CERTIFICATE-----\nDEADBEEF\n-----END CERTIFICATE-----\n")

    seen: dict = {}

    def _creds(root_certificates=None):
        seen["root"] = root_certificates
        return object()

    monkeypatch.setattr(grpc, "ssl_channel_credentials", _creds)
    build_sync_channel("h", 1, tls=True, ca_cert_path=str(pem))

    assert seen["root"] == pem.read_bytes(), "ca_cert_path was not passed through"


def test_edge_no_ca_cert_uses_the_system_trust_store(spy, monkeypatch):
    seen: dict = {}

    def _creds(root_certificates=None):
        seen["root"] = root_certificates
        return object()

    monkeypatch.setattr(grpc, "ssl_channel_credentials", _creds)
    build_sync_channel("h", 1, tls=True, ca_cert_path=None)
    assert seen["root"] is None


def test_fail_missing_ca_file_raises_a_typed_error(tmp_path):
    """A typo'd CA path must fail loudly, not silently degrade trust.

    Falling back to the system trust store means trusting a different set of
    roots than the operator configured. That is the worst kind of degradation,
    because it succeeds.
    """
    with pytest.raises(CaCertificateError, match="could not be read"):
        build_sync_channel(
            "h", 1, tls=True, ca_cert_path=str(tmp_path / "does-not-exist.pem")
        )


def test_fail_garbage_ca_file_is_rejected_at_construction(tmp_path):
    """A non-PEM file must fail here, not as an opaque handshake error later.

    gRPC accepts arbitrary bytes as `root_certificates`, so a truncated
    download or a wrong path would otherwise surface much later as a TLS
    failure that never mentions the file responsible.
    """
    bad = tmp_path / "garbage.pem"
    bad.write_bytes(b"this is not a certificate\n")

    with pytest.raises(CaCertificateError, match="does not look like a PEM"):
        build_sync_channel("h", 1, tls=True, ca_cert_path=str(bad))


def test_happy_a_well_formed_pem_is_accepted(tmp_path, spy, monkeypatch):
    """Edge: the check is structural only and must not reject a real CA.

    It looks for the PEM block marker and nothing more. Validating the
    certificate is gRPC's job; duplicating that here would reject valid
    material.
    """
    monkeypatch.setattr(grpc, "ssl_channel_credentials", lambda **kw: object())
    good = tmp_path / "ca.pem"
    good.write_bytes(
        b"-----BEGIN CERTIFICATE-----\nAAAA\n-----END CERTIFICATE-----\n"
    )
    build_sync_channel("h", 1, tls=True, ca_cert_path=str(good))
    assert "secure" in spy


# ── options actually reach the channel ──────────────────────────────────────


def test_happy_default_options_reach_the_channel(spy):
    """Keepalive and the raised message ceiling must arrive at gRPC.

    Both defaults address a silent failure: a `Watch*` stream that dies behind
    NAT with no exception, and a `list_contracts` larger than gRPC's own 4 MB
    receive limit. Asserting the constants proves nothing about whether they
    are applied.
    """
    build_sync_channel("h", 1, tls=False, ca_cert_path=None)
    opts = dict(spy["insecure"]["kwargs"]["options"])

    assert opts["grpc.keepalive_time_ms"] == 30_000
    assert opts["grpc.keepalive_permit_without_calls"] == 1
    assert opts["grpc.max_receive_message_length"] == DEFAULT_MAX_MESSAGE_LENGTH


def test_happy_caller_options_reach_the_channel(spy):
    build_sync_channel(
        "h", 1, tls=False, ca_cert_path=None,
        options=[("grpc.max_receive_message_length", 123)],
    )
    opts = dict(spy["insecure"]["kwargs"]["options"])
    assert opts["grpc.max_receive_message_length"] == 123
    assert opts["grpc.keepalive_time_ms"] == 30_000  # defaults survive


def test_happy_options_reach_the_channel_through_the_client(spy):
    """End to end from the public constructor, not just the helper."""
    VoltnirClient(
        host="h", port=1, api_key="k",
        options=[("grpc.keepalive_time_ms", 5_000)],
    )
    opts = dict(spy["insecure"]["kwargs"]["options"])
    assert opts["grpc.keepalive_time_ms"] == 5_000
    assert opts["grpc.max_receive_message_length"] == DEFAULT_MAX_MESSAGE_LENGTH


def test_happy_async_options_reach_the_channel(spy):
    build_async_channel("h", 1, tls=False, ca_cert_path=None)
    opts = dict(spy["aio_insecure"]["kwargs"]["options"])
    assert opts["grpc.keepalive_time_ms"] == 30_000


def test_happy_secure_channel_also_receives_the_options(spy, monkeypatch):
    """TLS must not quietly drop the tuning; it is a separate call site."""
    monkeypatch.setattr(grpc, "ssl_channel_credentials", lambda **kw: object())
    build_sync_channel("h", 1, tls=True, ca_cert_path=None)
    opts = dict(spy["secure"]["kwargs"]["options"])
    assert opts["grpc.keepalive_time_ms"] == 30_000
    assert opts["grpc.max_receive_message_length"] == DEFAULT_MAX_MESSAGE_LENGTH


def test_edge_target_is_host_colon_port(spy):
    build_sync_channel("example.test", 3443, tls=False, ca_cert_path=None)
    assert spy["insecure"]["target"] == "example.test:3443"
