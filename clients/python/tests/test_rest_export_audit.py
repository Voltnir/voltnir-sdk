"""`export_audit`, the audit-trail export, against the loopback REST fake.

It travels like the other exports (`test_rest_export.py` holds the shared
request, polling, streaming and timeout behaviour): these tests pin what is its
own. The endpoint is `POST /api/v1/audit/export/events`; the body carries the
audit query's filters under their wire names; every error names the method
`export_audit`; and both clients document the two permissions it needs.
"""

from __future__ import annotations

import inspect

import grpc
import pytest
import pytest_asyncio
from conftest import REST_KEY, REST_TOKEN
from voltnir_sdk import (
    AsyncVoltnirClient,
    ClientClosed,
    ExportBusy,
    Internal,
    InvalidArgument,
    NotFound,
    PermissionDenied,
    ResourceExhausted,
    Unauthenticated,
    VoltnirClient,
)

_FROM, _TO = "2026-07-01T00:00:00Z", "2026-07-02T00:00:00Z"
_PATH = "/api/v1/audit/export/events"
_CSV = b'action,after,before\npermissions_set,"{""n"":1,""note"":""a, \\""b\\""""}",\n'
_FILTERS = {
    "action": "permissions_set",
    "target_type": "user",
    "actor_short_id": "U001",
    "outcome": "denied",
    "v_member_short_id": "VM001",
}


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


# ── happy ───────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("fmt", ["csv", "json"])
def test_happy_export_audit_posts_to_the_events_endpoint_and_yields_the_file(rclient, rest, fmt):
    rest.body = _CSV
    data = b"".join(rclient.export_audit(format=fmt, from_=_FROM, to=_TO))
    assert data == _CSV
    _method, path, headers, sent = rest.posts()[0]
    assert path == _PATH
    assert sent == {"format": fmt, "from": _FROM, "to": _TO}
    assert headers["Authorization"] == f"Bearer {REST_KEY}"
    assert [p[1] for p in rest.polls()] == [f"/api/v1/audit/export/{REST_TOKEN}"]


def test_happy_every_filter_crosses_under_its_wire_name(rclient, rest):
    list(rclient.export_audit(format="json", from_=_FROM, to=_TO, **_FILTERS))
    assert rest.posts()[0][3] == {"format": "json", "from": _FROM, "to": _TO, **_FILTERS}


async def test_happy_async_export_audit_yields_the_file_with_its_filters(raclient, rest):
    rest.body, rest.pending = _CSV, 2
    chunks = [
        c async for c in raclient.export_audit(format="csv", from_=_FROM, to=_TO, outcome="ok")
    ]
    assert b"".join(chunks) == _CSV
    assert rest.posts()[0][1] == _PATH
    assert rest.posts()[0][3] == {"format": "csv", "from": _FROM, "to": _TO, "outcome": "ok"}
    assert len(rest.polls()) == 3


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


@pytest.mark.parametrize("status,exc,code", _STATUS_MATRIX, ids=[str(s) for s, *_ in _STATUS_MATRIX])
def test_fail_a_refused_request_raises_its_type_naming_export_audit(rclient, rest, status, exc, code):
    rest.post_status, rest.error = status, "the gateway's own words"
    with pytest.raises(exc) as info:
        list(rclient.export_audit(format="json", from_=_FROM, to=_TO))
    assert type(info.value) is exc
    assert info.value.code is code
    assert info.value.message == "the gateway's own words"
    assert info.value.rpc == "export_audit"
    assert rest.polls() == []


async def test_fail_async_a_busy_gateway_raises_export_busy_naming_export_audit(raclient, rest):
    rest.post_status, rest.error = 409, "an export is already running, try again later"
    with pytest.raises(ExportBusy) as info:
        _ = [c async for c in raclient.export_audit(format="csv", from_=_FROM, to=_TO)]
    assert info.value.message == "an export is already running, try again later"
    assert info.value.rpc == "export_audit"


def test_fail_a_missing_grant_is_permission_denied_with_the_gateway_text(rclient, rest):
    rest.post_status, rest.error = 403, "Forbidden"
    with pytest.raises(PermissionDenied, match="Forbidden") as info:
        list(rclient.export_audit(format="json", from_=_FROM, to=_TO))
    assert info.value.rpc == "export_audit"


def test_fail_without_rest_url_raises_naming_it_and_the_method(server):
    with VoltnirClient(host="127.0.0.1", port=server, api_key=REST_KEY, timeout=5.0) as c:
        with pytest.raises(ValueError, match="rest_url") as info:
            c.export_audit(format="json", from_=_FROM, to=_TO)
    assert "export_audit" in str(info.value)


async def test_fail_async_without_rest_url_raises_naming_it_and_the_method(server):
    c = AsyncVoltnirClient(host="127.0.0.1", port=server, api_key=REST_KEY, timeout=5.0)
    try:
        with pytest.raises(ValueError, match="rest_url") as info:
            c.export_audit(format="json", from_=_FROM, to=_TO)
    finally:
        await c.close()
    assert "export_audit" in str(info.value)


def test_fail_a_closed_client_raises_client_closed_naming_export_audit(server, rest):
    c = VoltnirClient(host="127.0.0.1", port=server, api_key=REST_KEY, rest_url=rest.url)
    c.close()
    with pytest.raises(ClientClosed) as info:
        c.export_audit(format="json", from_=_FROM, to=_TO)
    assert info.value.rpc == "export_audit"
    assert rest.requests == []


# ── edge ────────────────────────────────────────────────────────────────────


def test_edge_an_omitted_filter_is_left_out_not_sent_empty(rclient, rest):
    list(rclient.export_audit(format="csv", from_=_FROM, to=_TO, action=None, outcome="error"))
    assert rest.posts()[0][3] == {"format": "csv", "from": _FROM, "to": _TO, "outcome": "error"}


def test_edge_an_empty_file_yields_nothing(rclient, rest):
    rest.body = b""
    assert list(rclient.export_audit(format="csv", from_=_FROM, to=_TO)) == []


@pytest.mark.parametrize("cls", [VoltnirClient, AsyncVoltnirClient])
def test_edge_both_clients_document_both_permissions(cls):
    doc = inspect.getdoc(cls.export_audit) or ""
    assert "`export_reports`" in doc and "`read_audit`" in doc, doc


def test_edge_both_clients_take_the_same_parameters():
    sync = inspect.signature(VoltnirClient.export_audit).parameters
    asyn = inspect.signature(AsyncVoltnirClient.export_audit).parameters
    assert list(sync) == list(asyn)
    assert [n for n, p in sync.items() if p.default is inspect.Parameter.empty] == [
        "self", "format", "from_", "to",
    ]
