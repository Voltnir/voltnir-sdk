"""Risk limits and money reads: the position limit, both cash pools, P&L, the
public-trade tape, and the permission catalogue.

The Set* tests read the current value, change it, assert, and restore it in a
``finally`` so the run leaves no net operator-state change."""

from __future__ import annotations

import pytest

from voltnir_sdk import PermissionDenied, Unauthenticated

# ── GetContractLimit / SetContractLimit (gated) ─────────────────────────────


@pytest.mark.rpc("GetContractLimit")
def test_happy_get_contract_limit(admin):
    assert admin.get_contract_limit().quantity >= 0


@pytest.mark.rpc("GetContractLimit")
def test_fail_get_contract_limit_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.get_contract_limit()


@pytest.mark.rpc("GetContractLimit")
def test_edge_get_contract_limit_is_a_plain_sub_mw_integer(admin):
    assert isinstance(admin.get_contract_limit().quantity, int)


@pytest.mark.rpc("SetContractLimit")
def test_happy_set_contract_limit_round_trips(admin):
    prior = admin.get_contract_limit().quantity
    try:
        resp = admin.set_contract_limit(quantity=4200)
        assert resp.quantity == 4200
    finally:
        admin.set_contract_limit(quantity=prior)


@pytest.mark.rpc("SetContractLimit")
def test_fail_set_contract_limit_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.set_contract_limit(quantity=1)


@pytest.mark.rpc("SetContractLimit")
def test_edge_set_contract_limit_to_current_is_idempotent(admin):
    current = admin.get_contract_limit().quantity
    assert admin.set_contract_limit(quantity=current).quantity == current


# ── GetCashLimit / SetCashLimit (gated) ─────────────────────────────────────


@pytest.mark.rpc("GetCashLimit")
def test_happy_get_cash_limit(admin):
    resp = admin.get_cash_limit()
    assert isinstance(resp.eur.breached, bool)
    assert isinstance(resp.gbp.breached, bool)


@pytest.mark.rpc("GetCashLimit")
def test_fail_get_cash_limit_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.get_cash_limit()


@pytest.mark.rpc("GetCashLimit")
def test_edge_get_cash_limit_house_is_non_negative(admin):
    assert admin.get_cash_limit().eur.house_cents >= 0


def _eur_cap(admin) -> int | None:
    pool = admin.get_cash_limit().eur
    return pool.cap_cents.value if pool.HasField("cap_cents") else None


def _restore_eur_cap(admin, prior: int | None) -> None:
    admin.set_cash_limit(cap_cents=prior, currency="eur")


@pytest.mark.rpc("SetCashLimit")
def test_happy_set_cash_limit_caps_the_eur_pool(admin):
    prior = _eur_cap(admin)
    try:
        resp = admin.set_cash_limit(cap_cents=1000, currency="eur")
        assert resp.eur.HasField("cap_cents")
        assert resp.eur.cap_cents.value == 1000
    finally:
        _restore_eur_cap(admin, prior)


@pytest.mark.rpc("SetCashLimit")
def test_fail_set_cash_limit_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.set_cash_limit(cap_cents=1000, currency="eur")


@pytest.mark.rpc("SetCashLimit")
def test_edge_set_cash_limit_zero_is_a_real_ceiling(admin):
    # A cap of 0 is a real ceiling (no trading in the pool), distinct from an
    # absent cap. The wire must carry the field set, at value 0.
    prior = _eur_cap(admin)
    try:
        resp = admin.set_cash_limit(cap_cents=0, currency="eur")
        assert resp.eur.HasField("cap_cents")
        assert resp.eur.cap_cents.value == 0
    finally:
        _restore_eur_cap(admin, prior)


# ── GetCashLimits (gated) ───────────────────────────────────────────────────


@pytest.mark.rpc("GetCashLimits")
def test_happy_get_cash_limits(admin):
    # The exchange feed; the list may be empty on a quiet sim, but the call is
    # authorised and returns its container.
    resp = admin.get_cash_limits()
    assert hasattr(resp, "limits")


@pytest.mark.rpc("GetCashLimits")
def test_fail_get_cash_limits_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.get_cash_limits()


@pytest.mark.rpc("GetCashLimits")
def test_edge_get_cash_limits_rows_carry_a_currency(admin):
    for lim in admin.get_cash_limits().limits:
        assert lim.currency


# ── GetPnl (member-scoped) ──────────────────────────────────────────────────


@pytest.mark.rpc("GetPnl")
def test_happy_get_pnl(admin):
    pnl = admin.get_pnl()
    assert pnl.compute_us >= 0


@pytest.mark.rpc("GetPnl")
async def test_happy_get_pnl_async(aadmin):
    pnl = await aadmin.get_pnl()
    assert pnl.compute_us >= 0


@pytest.mark.rpc("GetPnl")
def test_fail_get_pnl_unauthenticated(badkey):
    with pytest.raises(Unauthenticated):
        badkey.get_pnl()


@pytest.mark.rpc("GetPnl")
def test_edge_get_pnl_unknown_member_scopes_to_empty(admin):
    # A member short id the caller does not hold narrows to nothing rather than
    # erroring; the snapshot is still computed.
    pnl = admin.get_pnl(v_member_short_id="VM999999")
    assert pnl.compute_us >= 0
    assert len(pnl.per_vm) == 0


# ── ListPublicTrades (authenticated) ────────────────────────────────────────


@pytest.mark.rpc("ListPublicTrades")
def test_happy_list_public_trades(admin, area):
    resp = admin.list_public_trades(limit=10, area_id=area)
    assert len(resp.trades) <= 10


@pytest.mark.rpc("ListPublicTrades")
def test_fail_list_public_trades_unauthenticated(badkey):
    with pytest.raises(Unauthenticated):
        badkey.list_public_trades(limit=10)


@pytest.mark.rpc("ListPublicTrades")
def test_edge_list_public_trades_caps_the_page(admin):
    # limit 0 means the server default; the page is bounded either way.
    resp = admin.list_public_trades(limit=0)
    assert len(resp.trades) <= 1000


# ── ListPermissions (gated on manage_users) ─────────────────────────────────


@pytest.mark.rpc("ListPermissions")
def test_happy_list_permissions(admin):
    resp = admin.list_permissions()
    assert len(resp.permissions) >= 1


@pytest.mark.rpc("ListPermissions")
def test_fail_list_permissions_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.list_permissions()


@pytest.mark.rpc("ListPermissions")
def test_edge_list_permissions_entries_carry_a_code(admin):
    for p in admin.list_permissions().permissions:
        assert p.code
