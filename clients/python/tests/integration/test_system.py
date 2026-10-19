"""System reads: state, status, throttling, info, area table, kill switch,
self-trade policy. Reads only; nothing here changes gateway state."""

from __future__ import annotations

import pytest

from voltnir_sdk import PermissionDenied, SelfTradePolicy, Unauthenticated

# ── GetState (gated on read_state) ──────────────────────────────────────────


@pytest.mark.rpc("GetState")
def test_happy_get_state(admin):
    s = admin.get_state()
    assert isinstance(s.uptime, str) and s.uptime  # formatted, e.g. "2h 14m 03s"
    assert isinstance(s.operational, bool)


@pytest.mark.rpc("GetState")
async def test_happy_get_state_async(aadmin):
    s = await aadmin.get_state()
    assert isinstance(s.operational, bool)


@pytest.mark.rpc("GetState")
def test_fail_get_state_denied_without_read_state(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.get_state()


@pytest.mark.rpc("GetState")
def test_edge_get_state_health_flags_are_present_booleans(admin):
    # The health flags are always populated, even before the M7 login lands, so
    # a consumer can render them without guarding for absence.
    s = admin.get_state()
    assert isinstance(s.amqp_connected, bool)
    assert isinstance(s.ws_order_book_stream_connected, bool)


# ── GetStatus (authenticated) ───────────────────────────────────────────────


@pytest.mark.rpc("GetStatus")
def test_happy_get_status(admin):
    st = admin.get_status()
    assert isinstance(st.trading_enabled, bool)
    assert st.order_pos_limit >= 0


@pytest.mark.rpc("GetStatus")
def test_fail_get_status_unauthenticated(badkey):
    with pytest.raises(Unauthenticated):
        badkey.get_status()


@pytest.mark.rpc("GetStatus")
def test_edge_get_status_carries_the_throttling_block(admin):
    # order_pos_limit and the throttling sub-message are always present; a panel
    # reads them without a presence check.
    st = admin.get_status()
    assert st.HasField("throttling")


# ── GetThrottling (authenticated) ───────────────────────────────────────────


@pytest.mark.rpc("GetThrottling")
def test_happy_get_throttling(admin):
    th = admin.get_throttling()
    assert th.short_omt_limit_l1 >= 0


@pytest.mark.rpc("GetThrottling")
def test_fail_get_throttling_unauthenticated(badkey):
    with pytest.raises(Unauthenticated):
        badkey.get_throttling()


@pytest.mark.rpc("GetThrottling")
def test_edge_get_throttling_counts_are_non_negative(admin):
    th = admin.get_throttling()
    assert th.short_current_omt_count >= 0
    assert th.long_current_omt_count >= 0


# ── GetSystemInfo (authenticated) ───────────────────────────────────────────


@pytest.mark.rpc("GetSystemInfo")
def test_happy_get_system_info(admin):
    info = admin.get_system_info()
    assert info.voltnir_version
    assert info.contract_store_time_in_days >= 0


@pytest.mark.rpc("GetSystemInfo")
def test_fail_get_system_info_unauthenticated(badkey):
    with pytest.raises(Unauthenticated):
        badkey.get_system_info()


@pytest.mark.rpc("GetSystemInfo")
def test_edge_get_system_info_lists_the_configured_products(admin):
    # The gateway is configured for a product set; it is reported back non-empty.
    info = admin.get_system_info()
    assert len(info.products) >= 1


# ── GetAreaTable (authenticated) ────────────────────────────────────────────


@pytest.mark.rpc("GetAreaTable")
def test_happy_get_area_table(admin):
    at = admin.get_area_table()
    assert len(at.areas) >= 1


@pytest.mark.rpc("GetAreaTable")
def test_fail_get_area_table_unauthenticated(badkey):
    with pytest.raises(Unauthenticated):
        badkey.get_area_table()


@pytest.mark.rpc("GetAreaTable")
def test_edge_get_area_table_area_rows_carry_an_eic(admin):
    # The embedded reference table always names an EIC per area row.
    at = admin.get_area_table()
    assert all(getattr(a, "eic", "") for a in at.areas[:5])


# ── GetTradingAllowed (authenticated) ───────────────────────────────────────


@pytest.mark.rpc("GetTradingAllowed")
def test_happy_get_trading_allowed(admin):
    ta = admin.get_trading_allowed()
    assert isinstance(ta.allowed, bool)


@pytest.mark.rpc("GetTradingAllowed")
def test_fail_get_trading_allowed_unauthenticated(badkey):
    with pytest.raises(Unauthenticated):
        badkey.get_trading_allowed()


@pytest.mark.rpc("GetTradingAllowed")
def test_edge_get_trading_allowed_agrees_with_status(admin):
    # The kill switch and the base slice of get_status read the same flag.
    assert admin.get_trading_allowed().allowed == admin.get_status().trading_enabled


# ── GetSelfTradePolicy (authenticated) ──────────────────────────────────────


@pytest.mark.rpc("GetSelfTradePolicy")
def test_happy_get_self_trade_policy(admin):
    pol = admin.get_self_trade_policy()
    assert pol.policy in SelfTradePolicy.values()


@pytest.mark.rpc("GetSelfTradePolicy")
def test_fail_get_self_trade_policy_unauthenticated(badkey):
    with pytest.raises(Unauthenticated):
        badkey.get_self_trade_policy()


@pytest.mark.rpc("GetSelfTradePolicy")
def test_edge_get_self_trade_policy_name_resolves(admin):
    # The returned enum is a real member, so its name always resolves.
    pol = admin.get_self_trade_policy()
    assert SelfTradePolicy.Name(pol.policy)
