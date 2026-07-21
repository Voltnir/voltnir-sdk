"""Every RPC on both clients: breadth from the descriptor, depth where it matters.

Two sections, doing different jobs:

- **Breadth** derives the RPC list straight from the service descriptor and
  drives all 63 wrappers on ``VoltnirClient`` and ``AsyncVoltnirClient`` through
  happy / fail / edge. If an RPC lands in the proto without a wrapper, or a
  wrapper exists for no RPC, the coverage guardrails below fail, so the two
  cannot drift apart unnoticed.
- **Depth** asserts on payloads and, more importantly, that request *filter
  fields actually cross the wire*. Breadth proves a wrapper is reachable; only
  depth catches one that reaches the server having quietly dropped an argument.
"""

from __future__ import annotations

import inspect
import re

import grpc
import pytest
from google.protobuf import symbol_database

from voltnir_sdk import (
    Aborted,
    AsyncVoltnirClient,
    DeadlineExceeded,
    FailedPrecondition,
    Internal,
    InvalidArgument,
    NotFound,
    PermissionDenied,
    ResourceExhausted,
    SelfTradePolicy,
    TradeEventType,
    Unauthenticated,
    Unavailable,
    VoltnirClient,
    VoltnirError,
)
from voltnir_sdk._generated import voltnir_api_v1_pb2 as pb2

_DB = symbol_database.Default()
_SVC = pb2.DESCRIPTOR.services_by_name["VoltAPI"]

# The service size, asserted rather than assumed. A proto that gains or loses an
# RPC trips this deliberately: bump it in the same change that adds the wrapper.
EXPECTED_RPC_COUNT = 63

# Explicit, representative arguments for wrappers the generic builder cannot
# serve. Three reasons, and the first two would otherwise leave a request EMPTY
# on the wire while the test still passed:
#
#   1. `**kwargs` wrappers have no signature to inspect, so `_auto_kwargs`
#      returns {} and the RPC is called with a default-constructed message.
#   2. All-default wrappers (every filter optional) likewise produce nothing.
#   3. Wrappers doing client-side validation reject a generic dummy.
#
# `test_every_rpc_with_request_fields_sends_data` enforces that this table stays
# complete, so a new RPC cannot quietly join category 1 or 2.
_ORDER_ID = "11111111-1111-4111-8111-111111111111"

_OVERRIDES = {
    "set_self_trade_policy": {"policy": "observe"},
    # Order path: real trading values in wire units (cents / sub-MW), matching
    # what the REST / gRPC / WS docs specify and what responses carry.
    "submit_order": {
        "client_order_id": _ORDER_ID,
        "side": pb2.Side.BUY,
        "delivery_area_id": "10YBE----------2",
        "contract_id": 12345,
        "price_cents": 5007,        # 50.07 CCY/MWh
        "quantity_sub_mw": 1500,    # 1.5 MW
    },
    "modify_order": {
        "client_order_id": _ORDER_ID,
        "price_cents": 5100,
        "quantity_sub_mw": 800,
    },
    "patch_member": {
        "id": "member-uuid-1",
        "name": "desk-a",
        "max_position": 7,
        "active": True,
    },
    "list_orders": {"delivery_area": "10YBE----------2", "contract_id": 42},
    "get_pnl": {"v_member_short_id": "VM001"},
    "list_public_trades": {"limit": 5, "area_id": "10YBE----------2"},
    "watch_orders": {"delivery_area": "10YBE----------2"},
    "watch_pnl": {"v_member_short_id": "VM001"},
    "query_audit_orders": {"limit": 5},
    "query_audit_trades": {"limit": 5},
    "query_audit_public_trades": {"limit": 5},
    "query_audit_events": {"limit": 5, "action": "permissions_set"},
    "query_m7_errors": {"limit": 5, "kind": "err_resp"},
    "export_orders": {"from_": "2026-07-01T00:00:00Z", "to": "2026-07-02T00:00:00Z"},
    "export_trades": {"from_": "2026-07-01T00:00:00Z", "to": "2026-07-02T00:00:00Z"},
}


def _snake(name: str) -> str:
    s = re.sub(r"(?<!^)(?=[A-Z0-9])", "_", name).lower()
    return s.replace("m_7", "m7").replace("hub_2_hub", "hub2hub").replace("a_p_i", "api")


def _sequence_dummy(annotation: str) -> list:
    """A one-element list for a `Sequence[...]` parameter.

    An empty list is a proto3 default and vanishes on the wire, so the repeated
    fields (`permissions`, `member_ids`, `holidays`) were never actually
    transmitted. The element type is read out of the annotation text because
    annotations are strings under `from __future__ import annotations`.
    """
    if "Holiday" in annotation:
        return [pb2.Holiday(date="2099-01-01", label="sentinel")]
    return ["x"]


def _auto_kwargs(method) -> dict:
    """Minimal kwargs for a wrapper: a dummy value per required parameter.

    Annotations are strings (``from __future__ import annotations``), so they're
    matched textually. Parameters with defaults (and ``timeout``) are skipped.
    """
    out: dict = {}
    for name, p in inspect.signature(method).parameters.items():
        if name in ("self", "timeout") or p.kind is p.VAR_KEYWORD:
            continue
        if p.default is not p.empty:
            continue
        ann = str(p.annotation)
        # Values must be NON-DEFAULT for proto3. A field set to its type default
        # (0, False, "", []) is not serialized at all, so `int -> 0` produced a
        # request indistinguishable from one where the wrapper had dropped the
        # argument entirely, and the happy test passed either way.
        if ann == "int":
            out[name] = 7
        elif ann == "bool":
            out[name] = True
        elif ann.startswith("Sequence"):
            out[name] = _sequence_dummy(ann)
        elif ann == "str":
            out[name] = "x"
        elif ".ValueType" in ann:
            # A proto enum. 1 is the first real member of every enum used in a
            # wrapper signature (BUY, REGULAR, NON, GFS, MODIFY) and is
            # non-default, so it serialises. Cases needing a SPECIFIC member
            # are pinned in _OVERRIDES.
            out[name] = 1
        else:
            # No silent fallback. An unannotated parameter would otherwise take
            # the "x" string, which only happens to be valid for `str`; for
            # anything else it surfaces as a confusing TypeError from deep
            # inside protobuf instead of naming the real problem. Fail loudly.
            raise AssertionError(
                f"{method.__qualname__}: parameter {name!r} has an annotation this "
                f"harness does not know how to build a dummy for ({ann!r}). Annotate "
                f"it (the SDK convention is Sequence[...] for repeated fields), or "
                f"teach _auto_kwargs about the new type."
            )
    return out


def _build_registry() -> list[tuple[str, str, bool, dict]]:
    reg = []
    for m in _SVC.methods:
        wrapper = _snake(m.name)
        kw = _auto_kwargs(getattr(VoltnirClient, wrapper))
        kw.update(_OVERRIDES.get(wrapper, {}))
        reg.append((m.name, wrapper, m.server_streaming, kw))
    return reg


REGISTRY = _build_registry()
UNARY = [r for r in REGISTRY if not r[2]]
STREAM = [r for r in REGISTRY if r[2]]
_UIDS = [r[1] for r in UNARY]
_SIDS = [r[1] for r in STREAM]

# The status codes errors.py maps to a dedicated subclass. The fallback path is
# exercised separately.
_CODE_MATRIX = [
    (grpc.StatusCode.UNAUTHENTICATED, Unauthenticated),
    (grpc.StatusCode.PERMISSION_DENIED, PermissionDenied),
    (grpc.StatusCode.NOT_FOUND, NotFound),
    (grpc.StatusCode.INVALID_ARGUMENT, InvalidArgument),
    (grpc.StatusCode.FAILED_PRECONDITION, FailedPrecondition),
    (grpc.StatusCode.ABORTED, Aborted),
    (grpc.StatusCode.UNAVAILABLE, Unavailable),
    (grpc.StatusCode.DEADLINE_EXCEEDED, DeadlineExceeded),
    (grpc.StatusCode.INTERNAL, Internal),
]
_CODE_IDS = [c.name for c, _ in _CODE_MATRIX]


# ── coverage guardrails ─────────────────────────────────────────────────────


def test_happy_auto_kwargs_builds_a_dummy_for_every_annotation_in_use():
    """Happy: the harness understands every annotation the wrappers actually use.

    Regression guard. `set_holidays(holidays=...)` shipped unannotated, so
    `_auto_kwargs` fell through to its `"x"` string default and passed a `str`
    where a repeated `Holiday` message was required. That surfaced as a
    TypeError from inside protobuf on four tests, which read as an environment
    problem rather than a missing annotation. Building kwargs for every wrapper
    without raising is what proves the fallback is gone.
    """
    for cls in (VoltnirClient, AsyncVoltnirClient):
        for _rpc, wrapper, _s, _kw in REGISTRY:
            _auto_kwargs(getattr(cls, wrapper))


def test_fail_auto_kwargs_rejects_an_unannotated_parameter():
    """Fail: an unannotated parameter is named loudly, not silently guessed."""

    class _Stub:
        def rpc_wrapper(self, *, thing):  # no annotation, the original bug
            raise AssertionError("never called")

    with pytest.raises(AssertionError, match=r"'thing'.*does not know how to build"):
        _auto_kwargs(_Stub.rpc_wrapper)


def test_edge_auto_kwargs_skips_kwargs_defaults_and_timeout():
    """Edge: only required, named parameters are built.

    `**kwargs`, anything with a default, and `timeout` must stay absent rather
    than being handed a dummy: several wrappers treat "field present" as
    "caller asked to change it", so a spurious key would change wire meaning.
    """

    class _Stub:
        def rpc_wrapper(self, *, needed: str, optional: str = "d", timeout: int = 1, **kwargs):
            raise AssertionError("never called")

    assert _auto_kwargs(_Stub.rpc_wrapper) == {"needed": "x"}


def test_registry_matches_descriptor():
    assert len(REGISTRY) == len(_SVC.methods)
    assert len(UNARY) + len(STREAM) == len(REGISTRY)
    # sanity: the service really does expose every RPC we expect to wrap.
    # Bump this when the proto gains/loses an RPC (intentional tripwire).
    assert len(REGISTRY) == EXPECTED_RPC_COUNT


def test_breadth_parametrization_covers_every_descriptor_rpc():
    """Every RPC the service declares is actually driven by the suites below.

    ``test_registry_matches_descriptor`` proves the registry is complete;
    this proves the registry is what the parametrized breadth tests consume,
    so "all 63 RPCs are exercised" is asserted rather than inferred from the
    two facts sitting next to each other.
    """
    driven = {rpc for rpc, _w, _s, _k in UNARY} | {rpc for rpc, _w, _s, _k in STREAM}
    declared = {m.name for m in _SVC.methods}

    assert driven == declared, f"not driven: {sorted(declared - driven)}"
    assert len(driven) == EXPECTED_RPC_COUNT


def test_every_rpc_with_request_fields_sends_data():
    """Every RPC that HAS request fields is exercised with at least one of them.

    The guard that keeps `_OVERRIDES` honest. Without it, an RPC whose wrapper
    takes `**kwargs` or has only optional filters silently joins the set that is
    "covered" by a happy test sending a completely empty message.

    If this fails, add a representative entry to `_OVERRIDES` naming real field
    values, rather than relaxing the assertion.
    """
    starved = [
        wrapper
        for rpc, wrapper, _s, kw in REGISTRY
        if _SVC.methods_by_name[rpc].input_type.fields and not kw
    ]
    assert not starved, (
        f"{len(starved)} RPC(s) have request fields but are called with no "
        f"arguments, so their happy test asserts nothing about the wire: "
        f"{starved}"
    )


def test_happy_auth_metadata_reaches_the_server(client, fake):
    """Happy: the bearer credential is actually attached to the call.

    A fake that ignores metadata makes the whole auth path untestable: the
    credential could be malformed or absent and every test would still pass,
    while every real call failed with UNAUTHENTICATED.

    The server requires the lowercase header name and a capital-B `Bearer`
    prefix, so both are pinned exactly.
    """
    client.get_me()

    md = fake.metadata["GetMe"]
    assert "authorization" in md, f"no authorization metadata sent: {md}"
    assert md["authorization"] == "Bearer test-key", (
        f"expected 'Bearer test-key' exactly, got {md['authorization']!r}. "
        f"The gateway rejects a lowercase 'bearer' prefix."
    )


async def test_happy_auth_metadata_reaches_the_server_async(aclient, fake):
    """Happy: the async client attaches the same credential, byte for byte."""
    await aclient.get_me()
    assert fake.metadata["GetMe"]["authorization"] == "Bearer test-key"


def test_happy_auth_metadata_is_attached_to_streams_too(client, fake):
    """Happy: streaming calls carry the credential as well as unary ones.

    Streams go through a separate code path (`_stream`, not `_unary`), so unary
    coverage does not imply it.
    """
    list(client.watch_state(timeout=5.0))
    assert fake.metadata["WatchState"]["authorization"] == "Bearer test-key"


def test_every_rpc_has_a_wrapper_on_both_clients():
    for cls in (VoltnirClient, AsyncVoltnirClient):
        missing = [w for _rpc, w, _s, _k in REGISTRY if not callable(getattr(cls, w, None))]
        assert not missing, f"{cls.__name__} missing wrappers: {missing}"


# ── breadth, unary: happy / fail, sync + async ──────────────────────────────


@pytest.mark.parametrize("rpc,wrapper,_s,kw", UNARY, ids=_UIDS)
def test_unary_happy(client, fake, rpc, wrapper, _s, kw):
    resp = getattr(client, wrapper)(**kw)
    assert resp is not None
    assert rpc in fake.requests  # the request marshalled and reached the server

    # If we sent arguments, at least one field must have reached the server.
    # `rpc in fake.requests` alone is satisfied by a completely empty message,
    # which is exactly what a wrapper that drops its arguments produces.
    if kw:
        received = fake.requests[rpc]
        assert received.ListFields(), (
            f"{wrapper} was called with {kw!r} but the server received an empty "
            f"{type(received).__name__}: the wrapper is dropping its arguments."
        )


@pytest.mark.parametrize("rpc,wrapper,_s,kw", UNARY, ids=_UIDS)
def test_unary_error_translates(client, fake, rpc, wrapper, _s, kw):
    fake.abort_code = grpc.StatusCode.PERMISSION_DENIED
    with pytest.raises(VoltnirError):
        getattr(client, wrapper)(**kw)


@pytest.mark.parametrize("rpc,wrapper,_s,kw", UNARY, ids=_UIDS)
async def test_unary_happy_async(aclient, fake, rpc, wrapper, _s, kw):
    resp = await getattr(aclient, wrapper)(**kw)
    assert resp is not None
    assert rpc in fake.requests

    # The async wrappers build their own requests. Asserting only `resp is not
    # None` would let an async wrapper drop every argument, or build the wrong
    # message entirely, without failing.
    if kw:
        received = fake.requests[rpc]
        assert received.ListFields(), (
            f"async {wrapper} sent an empty {type(received).__name__}"
        )


@pytest.mark.parametrize("rpc,wrapper,_s,kw", UNARY, ids=_UIDS)
async def test_unary_error_translates_async(aclient, fake, rpc, wrapper, _s, kw):
    fake.abort_code = grpc.StatusCode.PERMISSION_DENIED
    with pytest.raises(VoltnirError):
        await getattr(aclient, wrapper)(**kw)


# ── breadth, streaming: happy / empty (edge) / fail, sync + async ───────────


@pytest.mark.parametrize("rpc,wrapper,_s,kw", STREAM, ids=_SIDS)
def test_stream_happy(client, fake, rpc, wrapper, _s, kw):
    fake.stream_count = 3
    assert len(list(getattr(client, wrapper)(**kw))) == 3


@pytest.mark.parametrize("rpc,wrapper,_s,kw", STREAM, ids=_SIDS)
def test_stream_empty(client, fake, rpc, wrapper, _s, kw):
    fake.stream_count = 0
    assert list(getattr(client, wrapper)(**kw)) == []


@pytest.mark.parametrize("rpc,wrapper,_s,kw", STREAM, ids=_SIDS)
def test_stream_error_translates(client, fake, rpc, wrapper, _s, kw):
    fake.abort_code = grpc.StatusCode.PERMISSION_DENIED
    with pytest.raises(VoltnirError):
        list(getattr(client, wrapper)(**kw))


@pytest.mark.parametrize("rpc,wrapper,_s,kw", STREAM, ids=_SIDS)
async def test_stream_happy_async(aclient, fake, rpc, wrapper, _s, kw):
    fake.stream_count = 2
    items = [item async for item in getattr(aclient, wrapper)(**kw)]
    assert len(items) == 2


@pytest.mark.parametrize("rpc,wrapper,_s,kw", STREAM, ids=_SIDS)
async def test_stream_error_translates_async(aclient, fake, rpc, wrapper, _s, kw):
    fake.abort_code = grpc.StatusCode.PERMISSION_DENIED
    with pytest.raises(VoltnirError):
        async for _ in getattr(aclient, wrapper)(**kw):
            pass


# ── status-code translation: the whole errors.py table ──────────────────────
#
# The breadth suites above prove *some* VoltnirError is raised for all 63 RPCs,
# using one status code. These prove the mapping itself: each code reaching its
# own subclass, and an unmapped code falling back rather than raising KeyError.
# Without them a mistyped entry in the table would go unnoticed, because most
# subclasses would never be constructed at all.


@pytest.mark.parametrize("code,exc", _CODE_MATRIX, ids=_CODE_IDS)
def test_fail_each_status_code_maps_to_its_own_exception(client, fake, code, exc):
    fake.abort_code = code
    with pytest.raises(exc):
        client.get_me()


@pytest.mark.parametrize("code,exc", _CODE_MATRIX, ids=_CODE_IDS)
async def test_fail_each_status_code_maps_to_its_own_exception_async(aclient, fake, code, exc):
    fake.abort_code = code
    with pytest.raises(exc):
        await aclient.get_me()


def test_edge_unmapped_status_code_falls_back_to_base_error(client, fake):
    """Edge: a code with no dedicated subclass still raises, as the base class.

    UNIMPLEMENTED is not in the table. `translate` must fall back to
    `VoltnirError` rather than KeyError-ing, otherwise an unexpected server
    status turns into a confusing SDK-internal crash.
    """
    fake.abort_code = grpc.StatusCode.UNIMPLEMENTED
    with pytest.raises(VoltnirError) as excinfo:
        client.get_me()

    assert type(excinfo.value) is VoltnirError
    assert excinfo.value.code is grpc.StatusCode.UNIMPLEMENTED
    assert excinfo.value.rpc == "GetMe"


def test_fail_resource_exhausted_is_typed(client, fake):
    """Fail: a message-size / rate limit surfaces as its own class.

    This is the failure a customer hits first when a large `list_contracts`
    exceeds the receive limit, and the error text is the only place that tells
    them the ceiling is raisable per client.
    """
    fake.abort_code = grpc.StatusCode.RESOURCE_EXHAUSTED
    with pytest.raises(ResourceExhausted):
        client.list_contracts(area_id="10YBE----------2")


def test_edge_error_carries_rpc_name_and_server_detail(client, fake):
    """Edge: the raised error names the RPC and echoes the server's detail string."""
    fake.abort_code = grpc.StatusCode.PERMISSION_DENIED
    fake.abort_details = "missing read_audit"

    with pytest.raises(PermissionDenied) as excinfo:
        client.query_audit_events()

    assert excinfo.value.rpc == "QueryAuditEvents"
    assert excinfo.value.message == "missing read_audit"
    assert "QueryAuditEvents" in str(excinfo.value)
    assert "missing read_audit" in str(excinfo.value)


# ── depth: filter fields must actually cross the wire ───────────────────────
#
# The highest-value assertions in the suite. Breadth cannot catch a wrapper that
# accepts an argument and then forgets to put it on the request; these can.

WATCH_METHODS = [
    "watch_trades",
    "watch_public_trades",
    "watch_pnl",
    "watch_state",
    "watch_messages",
    "watch_audit_events",
    "watch_m7_errors",
]


def test_query_audit_events_happy(client, fake):
    resp = client.query_audit_events(
        limit=5, action="permissions_set", outcome="ok", actor_short_id="U001"
    )
    assert len(resp.items) == 1
    assert resp.next_cursor == "c1"
    req = fake.requests["QueryAuditEvents"]
    assert req.limit == 5
    assert req.action == "permissions_set"
    assert req.outcome == "ok"
    assert req.actor_short_id == "U001"


def test_query_m7_errors_happy(client, fake):
    resp = client.query_m7_errors(limit=10, kind="err_resp", err_code=42)
    assert len(resp.items) == 1
    req = fake.requests["QueryM7Errors"]
    assert req.limit == 10
    assert req.kind == "err_resp"
    assert req.err_code == 42


def test_query_audit_events_permission_denied(client, fake):
    # read_audit gate rejected server-side.
    fake.abort_code = grpc.StatusCode.PERMISSION_DENIED
    with pytest.raises(PermissionDenied):
        client.query_audit_events()


def test_query_m7_errors_invalid_argument(client, fake):
    # e.g. a malformed date_from is rejected with INVALID_ARGUMENT.
    fake.abort_code = grpc.StatusCode.INVALID_ARGUMENT
    with pytest.raises(InvalidArgument):
        client.query_m7_errors(date_from="not-a-date")


def test_query_audit_events_no_filters_sends_defaults(client, fake):
    # Edge: zero kwargs → an all-default request, no fields spuriously set.
    client.query_audit_events()
    req = fake.requests["QueryAuditEvents"]
    assert req.limit == 0
    assert req.cursor == ""
    assert req.action == ""
    assert req.target_type == ""


def test_list_orders_forwards_every_filter(client, fake):
    """The documented filter-priority surface must reach the server intact."""
    client.list_orders(
        delivery_area="10YBE----------2",
        contract_id=42,
        product="XBID_Hour_Power",
        delivery_start="2026-07-20T10:00:00Z",
        v_member_short_id="VM001",
    )
    req = fake.requests["ListOrders"]
    assert req.delivery_area == "10YBE----------2"
    assert req.contract_id == 42
    assert req.product == "XBID_Hour_Power"
    assert req.delivery_start == "2026-07-20T10:00:00Z"
    assert req.v_member_short_id == "VM001"


def test_set_self_trade_policy_translates_the_string_to_its_enum(client, fake):
    """Edge: the wrapper maps "reject" → SELF_TRADE_POLICY_REJECT.

    One of two wrappers doing client-side argument transformation, so a broken
    mapping would send the wrong policy with no server-side complaint.
    """
    client.set_self_trade_policy(policy="reject")
    assert fake.requests["SetSelfTradePolicy"].policy == (
        SelfTradePolicy.SELF_TRADE_POLICY_REJECT
    )

    client.set_self_trade_policy(policy="observe")
    assert fake.requests["SetSelfTradePolicy"].policy == (
        SelfTradePolicy.SELF_TRADE_POLICY_OBSERVE
    )


def test_edge_from_keyword_is_remapped_to_the_proto_from_field(client, fake):
    """Edge: `from` is a Python keyword, so the SDK accepts `from_`.

    `_build` rewrites it. If that rewrite broke, the export range would silently
    default to empty rather than erroring, which is the worst failure shape.
    """
    list(client.export_orders(from_="2026-07-01", to="2026-07-02"))
    req = fake.requests["ExportOrders"]
    assert getattr(req, "from") == "2026-07-01"
    assert req.to == "2026-07-02"


# ── depth: the Watch* streams ───────────────────────────────────────────────


@pytest.mark.parametrize("method", WATCH_METHODS)
def test_watch_stream_happy(client, fake, method):
    fake.stream_count = 3
    items = list(getattr(client, method)(timeout=5.0))
    assert len(items) == 3


@pytest.mark.parametrize("method", WATCH_METHODS)
def test_watch_stream_empty(client, fake, method):
    # Edge: a stream that closes without emitting yields no iterations.
    fake.stream_count = 0
    items = list(getattr(client, method)(timeout=5.0))
    assert items == []


@pytest.mark.parametrize(
    "method,code,exc",
    [
        ("watch_audit_events", grpc.StatusCode.PERMISSION_DENIED, PermissionDenied),
        ("watch_m7_errors", grpc.StatusCode.PERMISSION_DENIED, PermissionDenied),
        ("watch_trades", grpc.StatusCode.UNAVAILABLE, Unavailable),
    ],
)
def test_watch_stream_error_translates(client, fake, method, code, exc):
    fake.abort_code = code
    with pytest.raises(exc):
        list(getattr(client, method)(timeout=5.0))


def test_watch_pnl_passes_member_filter(client, fake):
    # Edge: the one Watch* RPC with a request field forwards it.
    fake.stream_count = 1
    list(client.watch_pnl(v_member_short_id="VM001", timeout=5.0))
    assert fake.requests["WatchPnl"].v_member_short_id == "VM001"


def test_watch_orders_passes_all_three_filters(client, fake):
    fake.stream_count = 1
    list(
        client.watch_orders(
            delivery_area="10YBE----------2",
            contract_id="42",
            v_member_short_id="VM001",
            timeout=5.0,
        )
    )
    req = fake.requests["WatchOrders"]
    assert req.delivery_area == "10YBE----------2"
    assert req.contract_id == "42"
    assert req.v_member_short_id == "VM001"


# ── depth: async surface mirrors the sync one ───────────────────────────────


async def test_async_query_audit_events_happy(aclient, fake):
    resp = await aclient.query_audit_events(limit=2)
    assert len(resp.items) == 1
    assert fake.requests["QueryAuditEvents"].limit == 2


async def test_async_query_m7_errors_permission_denied(aclient, fake):
    fake.abort_code = grpc.StatusCode.PERMISSION_DENIED
    with pytest.raises(PermissionDenied):
        await aclient.query_m7_errors()


@pytest.mark.parametrize("method", WATCH_METHODS)
async def test_async_watch_stream_happy(aclient, fake, method):
    fake.stream_count = 2
    items = [item async for item in getattr(aclient, method)(timeout=5.0)]
    assert len(items) == 2


async def test_async_watch_stream_error_translates(aclient, fake):
    fake.abort_code = grpc.StatusCode.PERMISSION_DENIED
    with pytest.raises(PermissionDenied):
        async for _ in aclient.watch_audit_events(timeout=5.0):
            pass


# ── enums re-exported from the generated pb2 ────────────────────────────────


def test_self_trade_policy_enum_resolves():
    assert (
        SelfTradePolicy.Value("SELF_TRADE_POLICY_REJECT")
        == SelfTradePolicy.SELF_TRADE_POLICY_REJECT
    )
    assert "SELF_TRADE_POLICY_OBSERVE" in SelfTradePolicy.keys()


def test_trade_event_type_enum_resolves():
    assert TradeEventType.SNAPSHOT == 0
    assert TradeEventType.UPSERTED == 1
