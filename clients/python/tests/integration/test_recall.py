"""RecallTrade: asking the exchange to recall a trade. These recall nothing:
a recall of a real trade asks market operations to reverse it, so the live
checks stay on the paths the gateway answers before sending anything."""

from __future__ import annotations

import pytest

from voltnir_sdk import InvalidArgument, NotFound, PermissionDenied


@pytest.mark.rpc("RecallTrade")
def test_happy_recall_trade_reaches_the_gate(admin):
    # Trade id 0 is never held: the gateway answers before the exchange is
    # asked, which proves the RPC is wired and the caller passes the gate.
    with pytest.raises(NotFound):
        admin.recall_trade("0")


@pytest.mark.rpc("RecallTrade")
async def test_happy_recall_trade_reaches_the_gate_async(aadmin):
    with pytest.raises(NotFound):
        await aadmin.recall_order_trades("00000000-0000-4000-8000-000000000000")


@pytest.mark.rpc("RecallTrade")
def test_fail_recall_trade_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.recall_trade("0")


@pytest.mark.rpc("RecallTrade")
def test_edge_recall_trade_needs_a_numeric_trade_id(admin):
    with pytest.raises(InvalidArgument):
        admin.recall_trade("not-a-number")
