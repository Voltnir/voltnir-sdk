"""AckTradeIngestFault: acknowledging a raised `trade_report refused` fault.

The fault comes from a trade report the gateway could not read, which a test
cannot provoke, so the live checks stay on the answers a healthy gateway gives:
with no fault raised there is nothing to acknowledge."""

from __future__ import annotations

import pytest

from voltnir_sdk import Aborted, InvalidArgument, PermissionDenied


@pytest.mark.rpc("AckTradeIngestFault")
def test_happy_ack_trade_ingest_fault_reaches_the_fault_check(admin):
    # Past the permission gate and the reason check, the gateway finds no fault
    # raised and answers Aborted: the RPC is wired and the caller passes the gate.
    with pytest.raises(Aborted):
        admin.ack_trade_ingest_fault("sdk integration: no fault raised")


@pytest.mark.rpc("AckTradeIngestFault")
def test_fail_ack_trade_ingest_fault_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.ack_trade_ingest_fault("sdk integration")


@pytest.mark.rpc("AckTradeIngestFault")
def test_edge_ack_trade_ingest_fault_needs_a_reason(admin):
    with pytest.raises(InvalidArgument):
        admin.ack_trade_ingest_fault("   ")
