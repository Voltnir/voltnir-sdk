"""Report exports over the gateway's REST API: order history, trade history and
the audit trail as bytes. On a quiet sim the export may be empty; the assertions pin that the file
downloads whole in the format asked for and that the gate holds, not a row
count."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from voltnir_sdk import InvalidArgument, PermissionDenied

_FROM = "2026-01-01T00:00:00Z"
_TO = "2026-01-31T00:00:00Z"


def _drain(stream) -> bytes:
    return b"".join(stream)


# ── export_orders (gated on export_reports) ─────────────────────────────────


@pytest.mark.rest("export_orders")
def test_happy_export_orders(admin):
    data = _drain(admin.export_orders(format="json", from_=_FROM, to=_TO))
    assert isinstance(json.loads(data), list)


@pytest.mark.rest("export_orders")
async def test_happy_export_orders_async(aadmin):
    data = b""
    async for chunk in aadmin.export_orders(format="json", from_=_FROM, to=_TO):
        data += chunk
    assert isinstance(json.loads(data), list)


@pytest.mark.rest("export_orders")
def test_fail_export_orders_denied(lowperm):
    with pytest.raises(PermissionDenied):
        list(lowperm.export_orders(format="json", from_=_FROM, to=_TO))


@pytest.mark.rest("export_orders")
def test_fail_export_orders_unknown_format_is_invalid_argument(admin):
    with pytest.raises(InvalidArgument, match="format"):
        list(admin.export_orders(format="xml", from_=_FROM, to=_TO))


@pytest.mark.rest("export_orders")
def test_edge_export_orders_narrow_window_is_an_empty_array(admin):
    # A one-second window in the distant past has nothing to export; the file
    # is still served, as the empty JSON array.
    data = _drain(
        admin.export_orders(
            format="json",
            from_="2020-01-01T00:00:00Z",
            to="2020-01-01T00:00:01Z",
        )
    )
    assert json.loads(data) == []


# ── export_trades (gated on export_reports) ─────────────────────────────────


@pytest.mark.rest("export_trades")
def test_happy_export_trades(admin):
    data = _drain(admin.export_trades(format="json", from_=_FROM, to=_TO))
    assert isinstance(json.loads(data), list)


@pytest.mark.rest("export_trades")
def test_fail_export_trades_denied(lowperm):
    with pytest.raises(PermissionDenied):
        list(lowperm.export_trades(format="json", from_=_FROM, to=_TO))


@pytest.mark.rest("export_trades")
def test_edge_export_trades_csv_of_an_empty_window_is_zero_bytes(admin):
    data = _drain(
        admin.export_trades(
            format="csv",
            from_="2020-01-01T00:00:00Z",
            to="2020-01-01T00:00:01Z",
        )
    )
    assert data == b""


# ── history filters (export_orders and export_trades) ──────────────────────


def _recent_window() -> tuple[str, str]:
    """The last seven days, where a desk trading on the sim has rows."""
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return (now - timedelta(days=7)).isoformat(), now.isoformat()


@pytest.mark.rest("export_trades")
def test_happy_export_trades_on_the_execution_basis(admin):
    data = _drain(
        admin.export_trades(format="json", from_=_FROM, to=_TO, time_basis="execution")
    )
    assert isinstance(json.loads(data), list)


@pytest.mark.rest("export_orders")
def test_happy_export_orders_filtered_by_status(admin):
    data = _drain(admin.export_orders(format="json", from_=_FROM, to=_TO, status="inactive"))
    assert isinstance(json.loads(data), list)


@pytest.mark.rest("export_trades")
def test_fail_export_trades_unknown_time_basis_is_invalid_argument(admin):
    with pytest.raises(InvalidArgument, match="time_basis 'settlement'"):
        list(admin.export_trades(format="json", from_=_FROM, to=_TO, time_basis="settlement"))


@pytest.mark.rest("export_orders")
def test_fail_export_orders_rejected_status_is_invalid_argument(admin):
    with pytest.raises(InvalidArgument, match="REJECTED is not an M7 order state"):
        list(admin.export_orders(format="json", from_=_FROM, to=_TO, status="REJECTED"))


@pytest.mark.rest("export_orders")
@pytest.mark.rest("export_trades")
@pytest.mark.parametrize("method", ["export_orders", "export_trades"])
def test_edge_a_user_code_no_row_carries_exports_nothing(admin, method):
    # Compared with the same window unfiltered, so an empty report proves the
    # filter was applied rather than that the window was quiet.
    from_, to = _recent_window()
    export = getattr(admin, method)
    unfiltered = json.loads(_drain(export(format="json", from_=from_, to=to)))
    if not unfiltered:
        pytest.skip("no rows in the last seven days to filter out")
    filtered = _drain(export(format="json", from_=from_, to=to, user_code="NO_SUCH_TRADER"))
    assert json.loads(filtered) == []


# ── export_audit (gated on export_reports and read_audit) ──────────────────


@pytest.mark.rest("export_audit")
def test_happy_export_audit(admin):
    data = _drain(admin.export_audit(format="json", from_=_FROM, to=_TO))
    rows = json.loads(data)
    assert isinstance(rows, list)
    stamps = [(r["ts_ms"], r["id"]) for r in rows]
    assert stamps == sorted(stamps), "oldest first"


@pytest.mark.rest("export_audit")
def test_fail_export_audit_denied(lowperm):
    with pytest.raises(PermissionDenied):
        list(lowperm.export_audit(format="json", from_=_FROM, to=_TO))


@pytest.mark.rest("export_audit")
def test_edge_export_audit_unknown_action_is_an_empty_array(admin):
    # An action no row carries filters to nothing, as it does on
    # query_audit_events: the file is the empty JSON array, not an error.
    data = _drain(
        admin.export_audit(format="json", from_=_FROM, to=_TO, action="no_such_action")
    )
    assert json.loads(data) == []
