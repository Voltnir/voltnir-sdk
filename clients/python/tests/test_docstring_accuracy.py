"""Method docstrings state the right permission and describe their own method.

A docstring is what an editor shows on hover and what ``help()`` prints, so a
wrong one is read as the contract. Three failure shapes are guarded here: a
"Requires ..." sentence naming a permission other than the method's gate (or a
name that is not a permission at all), which sends an operator to grant the
wrong thing; a member-scoped read naming a broad-read permission other than the
one that widens it, which does the same; and a docstring that opens by
describing a different method.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from voltnir_sdk import AsyncVoltnirClient, VoltnirClient

_CLIENTS = (VoltnirClient, AsyncVoltnirClient)

# Every permission the gateway assigns (ListPermissions / the permission table
# in the gRPC reference).
_CATALOG = {
    "create_order", "modify_order", "delete_order", "toggle_trading",
    "set_position_limit", "set_cash_limit", "set_self_trade_policy",
    "manage_users", "manage_members", "read_audit", "read_m7_errors",
    "read_logs", "read_pnl", "read_orders", "read_state", "read_status",
    "read_metrics", "export_reports", "restart_system",
    "restore_trade_history", "bypass_member_check", "trade_global",
    "recall_trade",
}

# Base permission of every gated method. A method absent here needs only an
# authenticated key, so its docstring must not claim a permission is required.
_GATES = {
    "submit_order": "create_order",
    "modify_order": "modify_order",
    "cancel_order": "delete_order",
    "cancel_all_orders": "delete_order",
    "submit_basket": "create_order",
    "cancel_basket": "delete_order",
    "recall_trade": "recall_trade",
    "recall_order_trades": "recall_trade",
    "get_state": "read_state",
    "watch_state": "read_state",
    "get_cash_limits": "read_status",
    "get_cash_limit": "read_status",
    "get_contract_limit": "read_status",
    "set_trading_allowed": "toggle_trading",
    "ack_trade_ingest_fault": "toggle_trading",
    "set_contract_limit": "set_position_limit",
    "set_cash_limit": "set_cash_limit",
    "set_holidays": "set_cash_limit",
    "add_holiday": "set_cash_limit",
    "remove_holiday": "set_cash_limit",
    "set_self_trade_policy": "set_self_trade_policy",
    "get_slot_limit": "read_status",
    "set_slot_limit": "set_position_limit",
    "restart": "restart_system",
    "restore_trade_history": "restore_trade_history",
    "list_users": "manage_users",
    "create_user": "manage_users",
    "delete_user": "manage_users",
    "set_permissions": "manage_users",
    "rotate_api_key": "manage_users",
    "get_user_members": "manage_users",
    "set_user_members": "manage_users",
    "list_permissions": "manage_users",
    "list_members": "manage_members",
    "create_member": "manage_members",
    "patch_member": "manage_members",
    "delete_member": "manage_members",
    "query_audit_public_trades": "read_audit",
    "query_audit_events": "read_audit",
    "watch_audit_events": "read_audit",
    "query_m7_errors": "read_m7_errors",
    "watch_m7_errors": "read_m7_errors",
    "list_exchange_messages": "read_m7_errors",
    "watch_exchange_messages": "read_m7_errors",
    "list_system_log": "read_logs",
    "watch_system_log": "read_logs",
    "export_orders": "export_reports",
    "export_trades": "export_reports",
    # The audit-trail export also needs read_audit; the opening "Requires"
    # names export_reports, and test_rest_export_audit holds both names.
    "export_audit": "export_reports",
}

# "Requires the `x` permission", "Requires `x`", "Requires x": the word after it.
_REQUIRES = re.compile(r"Requires\s+(?:the\s+)?`?([a-z_0-9]+)`?")

# Methods whose opening line must name what they do. Each phrase is specific
# enough that a docstring written for a neighbouring method cannot contain it.
_OPENING = {
    "get_order": "Fetch one order",
    "set_self_trade_policy": "Set self-trade prevention",
    "list_users": "All users",
    "delete_user": "Delete a user",
    "delete_member": "Delete a member",
    "set_permissions": "Replace a user's permissions",
}


def _public_methods(cls):
    return {
        name: fn
        for name, fn in inspect.getmembers(cls, callable)
        if not name.startswith("_") and name != "close"
    }


def _required_permissions(fn) -> list[str]:
    return _REQUIRES.findall(inspect.getdoc(fn) or "")


@pytest.mark.parametrize("cls", _CLIENTS, ids=lambda c: c.__name__)
def test_happy_every_stated_requirement_is_the_methods_own_gate(cls):
    wrong = {
        name: (stated, _GATES.get(name))
        for name, fn in _public_methods(cls).items()
        for stated in _required_permissions(fn)
        if stated != _GATES.get(name)
    }
    assert wrong == {}, f"docstring names the wrong permission (stated, actual): {wrong}"


@pytest.mark.parametrize("cls", _CLIENTS, ids=lambda c: c.__name__)
def test_fail_no_docstring_names_a_permission_outside_the_catalog(cls):
    unknown = {
        name: stated
        for name, fn in _public_methods(cls).items()
        for stated in _required_permissions(fn)
        if stated not in _CATALOG
    }
    assert unknown == {}, f"not a permission the gateway assigns: {unknown}"


@pytest.mark.parametrize("cls", _CLIENTS, ids=lambda c: c.__name__)
@pytest.mark.parametrize("method,phrase", sorted(_OPENING.items()))
def test_edge_docstring_opens_on_its_own_method(cls, method, phrase):
    first_line = (inspect.getdoc(getattr(cls, method)) or "").splitlines()[0]
    assert phrase in first_line, f"{cls.__name__}.{method} opens with {first_line!r}"


def test_edge_gate_table_names_only_real_methods_and_permissions():
    methods = set(_public_methods(VoltnirClient))
    assert set(_GATES) <= methods
    assert set(_OPENING) <= methods
    assert set(_GATES.values()) <= _CATALOG


# The permission that widens each member-scoped read to the whole firm. Without
# it (or bypass_member_check) the method silently returns only the caller's
# members, so a docstring naming another permission sends an operator to grant
# one that does not widen the result.
_BROAD_READ = {
    "get_order": "read_orders",
    "get_contract": "read_orders",
    "list_orders": "read_orders",
    "watch_orders": "read_orders",
    "get_pnl": "read_pnl",
    "query_audit_orders": "read_orders",
    "query_audit_trades": "read_orders",
    "query_audit_events": "read_orders",
    "watch_audit_events": "read_orders",
}

# "`read_x` / `bypass_member_check`": how a member-scoped docstring names it.
_BROAD_PAIR = re.compile(r"`([a-z_0-9]+)`\s*/\s*`bypass_member_check`")


@pytest.mark.parametrize("cls", _CLIENTS, ids=lambda c: c.__name__)
def test_fail_a_member_scoped_docstring_names_its_own_broad_read(cls):
    wrong = {
        name: (stated, _BROAD_READ.get(name))
        for name, fn in _public_methods(cls).items()
        for stated in _BROAD_PAIR.findall(inspect.getdoc(fn) or "")
        if stated != _BROAD_READ.get(name)
    }
    assert wrong == {}, f"docstring names the wrong broad read (stated, actual): {wrong}"


@pytest.mark.parametrize("cls", _CLIENTS, ids=lambda c: c.__name__)
@pytest.mark.parametrize("method", sorted(_BROAD_READ))
def test_edge_every_member_scoped_read_names_its_broad_read(cls, method):
    assert _BROAD_READ[method] in _CATALOG
    stated = _BROAD_PAIR.findall(inspect.getdoc(getattr(cls, method)) or "")
    assert stated == [_BROAD_READ[method]], f"{cls.__name__}.{method} states {stated}"


@pytest.mark.parametrize("cls", _CLIENTS, ids=lambda c: c.__name__)
def test_fail_every_gated_method_states_its_gate(cls):
    """Fail: a gated method whose docstring states no requirement is reported.
    The checks above read only what a docstring states; this one fails a gated
    method that states nothing, which leaves an operator unaware the call can
    be refused."""
    silent = sorted(
        name for name, gate in _GATES.items()
        if gate not in _required_permissions(getattr(cls, name))
    )
    assert silent == [], f"{cls.__name__}: gated methods that do not state their gate: {silent}"


# Methods the gateway serves only under its desk-management license. Under a
# trader license each is refused with `LICENSE_DESK_REQUIRED` whatever the
# caller's permissions, so a docstring naming only the permission sends an
# operator to grant something that does not help.
_DESK = {
    "list_users", "create_user", "delete_user", "set_permissions",
    "get_user_members", "set_user_members",
    "list_members", "create_member", "patch_member", "delete_member",
}
_DESK_PHRASE = "desk-management license"


def _flat_doc(obj) -> str:
    """The docstring with its line breaks folded, so a wrapped phrase matches."""
    return " ".join((inspect.getdoc(obj) or "").split())


@pytest.mark.parametrize("cls", _CLIENTS, ids=lambda c: c.__name__)
def test_happy_every_desk_method_states_the_license(cls):
    silent = sorted(
        n for n in _DESK if _DESK_PHRASE not in _flat_doc(getattr(cls, n))
    )
    assert silent == [], f"{cls.__name__}: desk methods not naming the license: {silent}"


@pytest.mark.parametrize("cls", _CLIENTS, ids=lambda c: c.__name__)
def test_fail_no_other_method_claims_the_desk_license(cls):
    """Fail: `rotate_api_key` and `list_permissions` share `manage_users` but
    are not behind the license; a docstring claiming it would be refused by an
    operator who never needed it."""
    claimed = sorted(
        name for name, fn in _public_methods(cls).items()
        if name not in _DESK and _DESK_PHRASE in _flat_doc(fn)
    )
    assert claimed == []


def test_edge_the_client_docstring_names_the_refusal_and_every_desk_method():
    doc = _flat_doc(VoltnirClient)
    assert "`LICENSE_DESK_REQUIRED`" in doc and "`PermissionDenied`" in doc
    named = set(re.findall(r"`([a-z_]+)`", doc.split("desk management")[0]))
    assert _DESK <= named, sorted(_DESK - named)
    assert _DESK <= set(_public_methods(VoltnirClient))


@pytest.mark.parametrize("cls", _CLIENTS, ids=lambda c: c.__name__)
def test_edge_rotate_api_key_states_its_trader_license_limit(cls):
    """Edge: `rotate_api_key` shares `manage_users` with the desk methods but is
    not license-gated; without the license it reaches only the caller's own
    key, and another target is `NotFound`, which an operator would otherwise
    read as a missing user."""
    doc = _flat_doc(cls.rotate_api_key)
    assert "only its own key" in doc and "`NotFound`" in doc, doc


# The key-reuse rule is stated in two homes, the README and `submit_order`'s
# docstring. The gateway holds a key only while the order's record is in
# memory, so each home must name the three events that drop the record, and
# neither may promise that a retry can never double a position.
_KEY_RELEASES = ("restart", "contract sweep", "resubscription to the exchange's order feed")
_OVERSTATED = re.compile(r"(?:can never|never|cannot) double (?:your|a) position")
_README = Path(__file__).resolve().parent.parent / "README.md"


def _key_reuse_problems(text: str) -> list[str]:
    flat = " ".join(text.split())
    return [f"does not name: {e}" for e in _KEY_RELEASES if e not in flat] + [
        f"overstates: {m}" for m in _OVERSTATED.findall(flat)
    ]


def test_happy_both_homes_state_when_a_key_is_freed():
    readme = _README.read_text(encoding="utf-8")
    section = readme.split("**Reusing a `client_order_id`.**")[1].split("\n\n")[0]
    assert _key_reuse_problems(section) == []
    assert _key_reuse_problems(inspect.getdoc(VoltnirClient.submit_order)) == []
    assert _OVERSTATED.findall(" ".join(readme.split())) == []


def test_fail_a_statement_promising_no_double_position_is_reported():
    old = ("the gateway refuses a reused key for as long as it holds any record "
           "of the original order, so a retry under the same key can never "
           "double your position.")
    assert _key_reuse_problems(old) == [
        "does not name: restart",
        "does not name: contract sweep",
        "does not name: resubscription to the exchange's order feed",
        "overstates: can never double your position",
    ]


def test_edge_the_async_client_references_the_rule_rather_than_copying_it():
    doc = _flat_doc(AsyncVoltnirClient.submit_order)
    assert "`VoltnirClient.submit_order`" in doc
    assert not any(e in doc for e in _KEY_RELEASES), doc
