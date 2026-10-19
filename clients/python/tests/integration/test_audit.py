"""History and log reads: the audit trails, the M7 error log, the exchange
message log, and the gateway's diagnostic log. On a quiet sim a page may be
empty; the assertions pin the page bound and the gate, not row counts."""

from __future__ import annotations

import pytest

from voltnir_sdk import PermissionDenied, Unauthenticated

# ── QueryAuditOrders (member-scoped) ────────────────────────────────────────


@pytest.mark.rpc("QueryAuditOrders")
def test_happy_query_audit_orders(admin):
    resp = admin.query_audit_orders(limit=5)
    assert len(resp.items) <= 5


@pytest.mark.rpc("QueryAuditOrders")
async def test_happy_query_audit_orders_async(aadmin):
    resp = await aadmin.query_audit_orders(limit=3)
    assert len(resp.items) <= 3


@pytest.mark.rpc("QueryAuditOrders")
def test_fail_query_audit_orders_unauthenticated(badkey):
    with pytest.raises(Unauthenticated):
        badkey.query_audit_orders(limit=5)


@pytest.mark.rpc("QueryAuditOrders")
def test_edge_query_audit_orders_caps_the_page_at_200(admin):
    # limit above the ceiling is capped, not honoured verbatim.
    assert len(admin.query_audit_orders(limit=500).items) <= 200


# ── QueryAuditTrades (member-scoped) ────────────────────────────────────────


@pytest.mark.rpc("QueryAuditTrades")
def test_happy_query_audit_trades(admin):
    assert len(admin.query_audit_trades(limit=5).items) <= 5


@pytest.mark.rpc("QueryAuditTrades")
def test_fail_query_audit_trades_unauthenticated(badkey):
    with pytest.raises(Unauthenticated):
        badkey.query_audit_trades(limit=5)


@pytest.mark.rpc("QueryAuditTrades")
def test_edge_query_audit_trades_ascending_page_is_accepted(admin):
    # The oldest-first page direction is a valid request, not an error.
    resp = admin.query_audit_trades(limit=5, sort_order="ASC")
    assert len(resp.items) <= 5


# ── QueryAuditPublicTrades (gated on read_audit) ────────────────────────────


@pytest.mark.rpc("QueryAuditPublicTrades")
def test_happy_query_audit_public_trades(admin):
    assert len(admin.query_audit_public_trades(limit=5).items) <= 5


@pytest.mark.rpc("QueryAuditPublicTrades")
def test_fail_query_audit_public_trades_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.query_audit_public_trades(limit=5)


@pytest.mark.rpc("QueryAuditPublicTrades")
def test_edge_query_audit_public_trades_caps_the_page(admin):
    assert len(admin.query_audit_public_trades(limit=500).items) <= 200


# ── QueryAuditEvents (gated on read_audit) ──────────────────────────────────


@pytest.mark.rpc("QueryAuditEvents")
def test_happy_query_audit_events(admin):
    assert len(admin.query_audit_events(limit=5).items) <= 5


@pytest.mark.rpc("QueryAuditEvents")
def test_fail_query_audit_events_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.query_audit_events(limit=5)


@pytest.mark.rpc("QueryAuditEvents")
def test_edge_query_audit_events_unmatched_filter_is_empty(admin):
    # A filter nothing matches yields an empty page, not an error.
    resp = admin.query_audit_events(limit=5, action="no_such_action_xyz")
    assert list(resp.items) == []


# ── QueryM7Errors (gated on read_m7_errors) ─────────────────────────────────


@pytest.mark.rpc("QueryM7Errors")
def test_happy_query_m7_errors(admin):
    assert len(admin.query_m7_errors(limit=5).items) <= 5


@pytest.mark.rpc("QueryM7Errors")
def test_fail_query_m7_errors_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.query_m7_errors(limit=5)


@pytest.mark.rpc("QueryM7Errors")
def test_edge_query_m7_errors_caps_the_page(admin):
    assert len(admin.query_m7_errors(limit=500).items) <= 200


# ── ListExchangeMessages (gated on read_m7_errors) ──────────────────────────


@pytest.mark.rpc("ListExchangeMessages")
def test_happy_list_exchange_messages(admin):
    assert len(admin.list_exchange_messages(limit=5).items) <= 5


@pytest.mark.rpc("ListExchangeMessages")
def test_fail_list_exchange_messages_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.list_exchange_messages(limit=5)


@pytest.mark.rpc("ListExchangeMessages")
def test_edge_list_exchange_messages_caps_the_page(admin):
    assert len(admin.list_exchange_messages(limit=500).items) <= 200


# ── ListSystemLog (gated on read_logs) ──────────────────────────────────────


@pytest.mark.rpc("ListSystemLog")
def test_happy_list_system_log(admin):
    resp = admin.list_system_log(limit=5)
    assert len(resp.items) <= 5
    assert resp.HasField("buffer")


@pytest.mark.rpc("ListSystemLog")
def test_fail_list_system_log_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.list_system_log(limit=5)


@pytest.mark.rpc("ListSystemLog")
def test_edge_list_system_log_reports_its_buffer_capacity(admin):
    # The buffer block is always present so a panel can tell how much history it
    # is not seeing; capacity is a positive bound.
    assert admin.list_system_log().buffer.capacity >= 1
