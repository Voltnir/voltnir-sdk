"""Every request field of every wrapper is a typed, named parameter.

A filter or order field that reaches the wire only through ``**kwargs`` is
reachable but undiscoverable: it does not appear in the signature, an editor
cannot complete it, a type checker cannot see a typo, and a wrong name is
silently dropped rather than rejected. For a trading API that is expensive --
a dropped ``v_member_short_id`` tags an order to the wrong member, a dropped
export range exports everything -- so the rule here is that every field of a
request message is spelled out as a keyword parameter on both clients.

The report exports are not RPCs: they send a REST request body, and the same
rule holds for its fields.

A handful of parameters carry a name that differs from the wire field. Each is
either a unit-carrying rename (the wire ``price`` becomes ``price_cents`` so a
bare ``price=50`` cannot be mistaken for 50.00) or the Python-keyword escape
(``from`` becomes ``from_``). Those are the only allowed differences, listed
in ``_FIELD_ALIASES`` and pinned by ``test_edge_alias_list_has_no_stale_entries``
so the allow-list cannot quietly grow into a blanket exemption.
"""

from __future__ import annotations

import inspect
import re

import pytest

from voltnir_sdk import AsyncVoltnirClient, VoltnirClient
from voltnir_sdk._generated import voltnir_api_v1_pb2 as pb2

from conftest import REST_METHODS

_SVC = pb2.DESCRIPTOR.services_by_name["VoltAPI"]
_CLIENTS = (VoltnirClient, AsyncVoltnirClient)
# The fields of each REST export's request body, as the gateway's REST
# reference lists them. Written out rather than read back from what the SDK
# sends, which could only ever agree with itself: a filter the gateway gains
# fails here until both clients take it. The history exports take the history
# read's filters (orders add `status`, trades `time_basis`); the audit-trail
# export takes the audit query's own.
_WINDOW = ("format", "from", "to")
_HISTORY_FILTERS = (
    "area",
    "product",
    "user_code",
    "v_member_short_id",
    "voltnir_user_short_id",
    "voltnir_username",
)
_REST_BODY_FIELDS: dict[str, tuple[str, ...]] = {
    "export_orders": (*_WINDOW, *_HISTORY_FILTERS, "status"),
    "export_trades": (*_WINDOW, *_HISTORY_FILTERS, "time_basis"),
    "export_audit": (
        *_WINDOW,
        "action",
        "target_type",
        "actor_short_id",
        "outcome",
        "v_member_short_id",
    ),
}

# Wire field name -> the parameter name(s) that may carry it. A field absent
# here must be a parameter of its own exact name. Every entry is a unit rename
# (the parameter name states the wire unit) or the `from` Python-keyword escape.
_FIELD_ALIASES: dict[str, set[str]] = {
    "price": {"price", "price_cents"},
    "quantity": {"quantity", "quantity_sub_mw"},
    "display_qty": {"display_qty", "display_qty_sub_mw"},
    "cash_limit": {"cash_limit", "cash_limit_cents"},
    "cash_limit_gbp": {"cash_limit_gbp", "cash_limit_gbp_cents"},
    "from": {"from_"},
}

# An RPC whose `oneof` target is split across two methods, one per target: the
# wire field -> the sibling method that carries it as a parameter. The RPC's own
# wrapper takes the other members of the `oneof`; the sibling must take this
# one (`test_edge_split_targets_are_carried_by_their_sibling`).
_SPLIT_TARGETS: dict[str, dict[str, str]] = {
    "RecallTrade": {"client_order_id": "recall_order_trades"},
}


def _snake(name: str) -> str:
    """PascalCase RPC name -> the SDK's snake_case wrapper name."""
    s = re.sub(r"(?<!^)(?=[A-Z0-9])", "_", name).lower()
    return s.replace("m_7", "m7").replace("hub_2_hub", "hub2hub").replace("a_p_i", "api")


def _named_params(fn) -> tuple[set[str], bool]:
    """The wrapper's explicit parameter names, and whether it takes ``**kwargs``."""
    names: set[str] = set()
    has_var_kw = False
    for p in inspect.signature(fn).parameters.values():
        if p.name == "self":
            continue
        if p.kind is p.VAR_KEYWORD:
            has_var_kw = True
            continue
        names.add(p.name)
    return names, has_var_kw


def _missing(fn, fields) -> list[str]:
    """The ``fields`` that no parameter of ``fn`` exposes (all, when no ``fn``)."""
    if fn is None:
        return list(fields)
    named, _ = _named_params(fn)
    return [f for f in fields if not (_FIELD_ALIASES.get(f, {f}) & named)]


def _uncovered_fields(cls, method) -> list[str]:
    """Request fields of ``method`` that no parameter on ``cls`` exposes."""
    split = _SPLIT_TARGETS.get(method.name, {})
    fields = [f.name for f in method.input_type.fields if f.name not in split]
    return _missing(getattr(cls, _snake(method.name), None), fields)


def _uncovered_rest_fields(cls, name: str) -> list[str]:
    """REST export body fields that no parameter of ``cls.<name>`` exposes."""
    return _missing(getattr(cls, name, None), _REST_BODY_FIELDS[name])


@pytest.mark.parametrize("cls", _CLIENTS, ids=[c.__name__ for c in _CLIENTS])
def test_edge_split_targets_are_carried_by_their_sibling(cls):
    """Edge: a split `oneof` member is a real field of a real `oneof`, and the
    sibling method named for it takes it as a parameter, so the split is never
    a standing exemption for a dropped field."""
    for rpc, fields in _SPLIT_TARGETS.items():
        method = _SVC.methods_by_name[rpc]
        for field, sibling in fields.items():
            descriptor = method.input_type.fields_by_name[field]
            assert descriptor.containing_oneof is not None, f"{rpc}.{field} is not in a oneof"
            named, _ = _named_params(getattr(cls, sibling))
            assert field in named, f"{cls.__name__}.{sibling} does not take {field}"


@pytest.mark.parametrize("cls", _CLIENTS, ids=[c.__name__ for c in _CLIENTS])
def test_happy_every_request_field_is_a_named_parameter(cls):
    """Happy: on both clients, every request field is a keyword parameter."""
    gaps = {
        method.name: missing
        for method in _SVC.methods
        if (missing := _uncovered_fields(cls, method))
    }
    assert not gaps, (
        f"{cls.__name__}: request fields with no parameter (a caller cannot set "
        f"them, or a typo is silently dropped): {gaps}. Add the keyword, or, if "
        f"it is a unit/keyword rename, list it in _FIELD_ALIASES."
    )


@pytest.mark.parametrize("cls", _CLIENTS, ids=[c.__name__ for c in _CLIENTS])
def test_happy_every_rest_body_field_is_a_named_parameter(cls):
    """Happy: on both clients, every export body field is a keyword parameter."""
    gaps = {
        name: missing for name in REST_METHODS if (missing := _uncovered_rest_fields(cls, name))
    }
    assert not gaps, f"{cls.__name__}: export body fields with no parameter: {gaps}"


@pytest.mark.parametrize("cls", _CLIENTS, ids=[c.__name__ for c in _CLIENTS])
def test_edge_no_request_wrapper_hides_fields_behind_kwargs(cls):
    """Edge: a wrapper for an RPC that has request fields must not use ``**kwargs``.

    ``**kwargs`` would satisfy the coverage check above vacuously while leaving
    every field untyped and undiscoverable, which is the exact state this suite
    exists to forbid.
    """
    offenders = []
    for method in _SVC.methods:
        if not method.input_type.fields:
            continue
        fn = getattr(cls, _snake(method.name), None)
        if fn is None:
            continue
        _, has_var_kw = _named_params(fn)
        if has_var_kw:
            offenders.append(_snake(method.name))
    offenders += [n for n in REST_METHODS if _named_params(getattr(cls, n))[1]]
    assert not offenders, f"{cls.__name__}: wrappers still taking **kwargs: {offenders}"


def test_fail_detector_reports_a_wrapper_that_drops_a_field():
    """Fail: the coverage logic actually fires on a wrapper missing a field.

    A guard that cannot fail is worse than none, so drive ``_uncovered_fields``
    against a stand-in whose wrapper omits ``limit`` and assert it is named.
    """

    class _Stub:
        def query_audit_orders(self, *, cursor=None):  # `limit` and the rest dropped
            raise AssertionError("never called")

    method = _SVC.methods_by_name["QueryAuditOrders"]
    missing = _uncovered_fields(_Stub, method)
    assert "limit" in missing
    assert "cursor" not in missing


def test_fail_detector_reports_an_export_that_drops_a_body_field():
    """Fail: the REST body check fires on an export missing a filter, and the
    ``from_`` escape still counts for ``from``."""

    class _Stub:
        def export_orders(self, *, format, from_, to, product=None):  # `area` dropped
            raise AssertionError("never called")

    assert _uncovered_rest_fields(_Stub, "export_orders") == [
        "area",
        "user_code",
        "v_member_short_id",
        "voltnir_user_short_id",
        "voltnir_username",
        "status",
    ]


@pytest.mark.parametrize("cls", _CLIENTS, ids=[c.__name__ for c in _CLIENTS])
def test_edge_no_export_takes_a_filter_its_endpoint_ignores(cls):
    """Edge: an export parameter is a body field of that export, or `timeout`.

    The gateway reads one body shape for both history exports and ignores
    `status` on trades and `time_basis` on orders, so a filter offered on the
    wrong export would be accepted and silently do nothing."""
    extras = {
        name: sorted(
            p
            for p in _named_params(getattr(cls, name))[0] - {"timeout"}
            if not any(p in _FIELD_ALIASES.get(f, {f}) for f in _REST_BODY_FIELDS[name])
        )
        for name in REST_METHODS
    }
    assert extras == {name: [] for name in REST_METHODS}


def test_edge_alias_list_has_no_stale_entries():
    """Edge: every alias is a real field renamed by a real parameter.

    Keeps ``_FIELD_ALIASES`` honest: an entry naming a field no request has, or
    a parameter no wrapper defines, would be a standing exemption for a rename
    that no longer exists.
    """
    all_fields = {
        f.name for m in _SVC.methods for f in m.input_type.fields
    } | {f for fields in _REST_BODY_FIELDS.values() for f in fields}
    all_params: set[str] = set()
    for cls in _CLIENTS:
        names = [_snake(m.name) for m in _SVC.methods] + list(REST_METHODS)
        for name in names:
            fn = getattr(cls, name, None)
            if fn is not None:
                all_params |= _named_params(fn)[0]

    for field, aliases in _FIELD_ALIASES.items():
        assert field in all_fields, f"alias key {field!r} is not a request field"
        assert aliases & all_params, (
            f"alias {field!r} lists {aliases}, none of which any wrapper defines"
        )
