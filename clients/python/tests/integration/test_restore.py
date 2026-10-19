"""RestoreTradeHistory: backfilling the persistent trade store from the
exchange's history. Isolated from the cash-exposure gate; leaves no orders."""

from __future__ import annotations

import pytest

from voltnir_sdk import PermissionDenied


@pytest.mark.rpc("RestoreTradeHistory")
def test_happy_restore_trade_history(admin):
    resp = admin.restore_trade_history(days=1)
    assert resp.chunk_count >= 0
    assert resp.effective_days >= 0


@pytest.mark.rpc("RestoreTradeHistory")
async def test_happy_restore_trade_history_async(aadmin):
    resp = await aadmin.restore_trade_history(days=1)
    assert resp.chunk_count >= 0


@pytest.mark.rpc("RestoreTradeHistory")
def test_fail_restore_trade_history_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.restore_trade_history(days=1)


@pytest.mark.rpc("RestoreTradeHistory")
def test_edge_restore_trade_history_zero_days_is_an_empty_window(admin):
    # days=0 is an explicit empty window: nothing to restore, distinct from an
    # absent days (which restores the exchange's whole reach).
    resp = admin.restore_trade_history(days=0)
    assert resp.chunk_count == 0
    assert resp.effective_days == 0
