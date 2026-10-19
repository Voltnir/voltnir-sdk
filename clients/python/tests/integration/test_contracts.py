"""Market data: contract listing and lookups, and the hub-to-hub matrix."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from voltnir_sdk import Unauthenticated, VoltnirError


def _window_24h() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return now.strftime(fmt), (now + timedelta(hours=24)).strftime(fmt)


# ── ListContracts (authenticated) ───────────────────────────────────────────


@pytest.mark.rpc("ListContracts")
def test_happy_list_contracts(admin, area):
    resp = admin.list_contracts(area_id=area)
    assert len(resp.contracts) >= 1
    assert all(c.area_id == area for c in resp.contracts[:5])


@pytest.mark.rpc("ListContracts")
async def test_happy_list_contracts_async(aadmin, area):
    resp = await aadmin.list_contracts(area_id=area)
    assert len(resp.contracts) >= 1


@pytest.mark.rpc("ListContracts")
def test_fail_list_contracts_unauthenticated(badkey, area):
    with pytest.raises(Unauthenticated):
        badkey.list_contracts(area_id=area)


@pytest.mark.rpc("ListContracts")
def test_edge_list_contracts_rows_carry_an_id_and_state(admin, area):
    # Every listed contract is fully identified: an id and a defined state, so a
    # consumer can key and filter on them without guarding for blanks.
    for c in admin.list_contracts(area_id=area).contracts[:10]:
        assert c.contract_id
        assert c.state is not None


# ── GetContract (member-scoped) ─────────────────────────────────────────────


@pytest.mark.rpc("GetContract")
def test_happy_get_contract(admin, area, a_contract):
    detail = admin.get_contract(area_id=area, contract_id=a_contract)
    assert detail.contract.contract_id == a_contract


@pytest.mark.rpc("GetContract")
def test_fail_get_contract_unauthenticated(badkey, area, a_contract):
    with pytest.raises(Unauthenticated):
        badkey.get_contract(area_id=area, contract_id=a_contract)


@pytest.mark.rpc("GetContract")
def test_edge_get_contract_unknown_id_is_a_translated_error(admin, area):
    # A contract id that does not exist surfaces as a typed, translated error
    # naming the RPC, not a raw gRPC status.
    with pytest.raises(VoltnirError) as exc:
        admin.get_contract(area_id=area, contract_id="999999999")
    assert exc.value.rpc == "GetContract"


# ── GetContractByDelivery (member-scoped) ───────────────────────────────────


def _a_contract_with_delivery(admin, area):
    for c in admin.list_contracts(area_id=area).contracts:
        if c.prod and c.dlvry_start:
            return c
    return None


@pytest.mark.rpc("GetContractByDelivery")
def test_happy_get_contract_by_delivery(admin, area):
    c = _a_contract_with_delivery(admin, area)
    assert c is not None, "no contract carried both a product and a delivery start"
    detail = admin.get_contract_by_delivery(
        area_id=area, prod=c.prod, dlvry_start=c.dlvry_start
    )
    assert detail.contract.contract_id == c.contract_id


@pytest.mark.rpc("GetContractByDelivery")
def test_fail_get_contract_by_delivery_unauthenticated(badkey, area):
    with pytest.raises(Unauthenticated):
        badkey.get_contract_by_delivery(
            area_id=area, prod="XX", dlvry_start="2099-01-01T00:00:00Z"
        )


@pytest.mark.rpc("GetContractByDelivery")
def test_edge_get_contract_by_delivery_far_future_is_a_translated_error(admin, area):
    # No contract delivers in 2099; the lookup surfaces a typed, translated
    # error naming the RPC rather than a raw gRPC status.
    with pytest.raises(VoltnirError) as exc:
        admin.get_contract_by_delivery(
            area_id=area, prod="H", dlvry_start="2099-01-01T00:00:00Z"
        )
    assert exc.value.rpc == "GetContractByDelivery"


# ── GetHub2Hub (authenticated) ──────────────────────────────────────────────


@pytest.mark.rpc("GetHub2Hub")
def test_happy_get_hub2hub(admin, area):
    win_from, win_to = _window_24h()
    resp = admin.get_hub2hub(
        delivery_area_from=area, delivery_from=win_from, delivery_to=win_to
    )
    assert isinstance(resp.enabled, bool)


@pytest.mark.rpc("GetHub2Hub")
def test_fail_get_hub2hub_unauthenticated(badkey, area):
    win_from, win_to = _window_24h()
    with pytest.raises(Unauthenticated):
        badkey.get_hub2hub(
            delivery_area_from=area, delivery_from=win_from, delivery_to=win_to
        )


@pytest.mark.rpc("GetHub2Hub")
def test_edge_get_hub2hub_reports_capacity_connectivity(admin, area):
    # Alongside enablement the matrix reports whether the capacity feed is
    # connected, so a caller can tell "disabled" from "enabled but no data".
    win_from, win_to = _window_24h()
    resp = admin.get_hub2hub(
        delivery_area_from=area, delivery_from=win_from, delivery_to=win_to
    )
    assert isinstance(resp.capacity_connected, bool)
