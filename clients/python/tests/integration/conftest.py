"""Fixtures for the live integration suite.

These tests drive a real Voltnir gateway on the EPEX simulator, so they only
run when the runner (`cargo run --bin test_sdk`) has provided the endpoint and
an admin key through the environment. Without ``VOLTNIR_IT_API_KEY`` the whole
package is skipped, so an offline ``pytest -q`` stays hermetic and the public
mirror's users are never blocked by a suite they cannot run.

The runner passes:

- ``VOLTNIR_IT_HOST`` / ``VOLTNIR_IT_PORT`` — the gateway's gRPC endpoint.
- ``VOLTNIR_IT_API_KEY`` — the bootstrap admin key (all permissions).
- ``VOLTNIR_IT_AREA`` — a delivery area the gateway is subscribed to.
- ``VOLTNIR_IT_RESTART`` — set to ``1`` to include the gateway-restart test.
- ``VOLTNIR_IT_REST_URL`` — the gateway's REST address, for the report exports;
  defaults to ``http://<VOLTNIR_IT_HOST>:3000``, the gateway's default REST port.

Every test is marked with the RPC it proves (``@pytest.mark.rpc("SubmitOrder")``),
or, for a method the SDK serves over REST, with that method
(``@pytest.mark.rest("export_orders")``). An offline guard
(``tests/test_integration_coverage.py``) reads those markers to assert every
gRPC RPC and every REST-backed method has a happy, a fail and an edge test.
"""

from __future__ import annotations

import os
import time

import pytest
import pytest_asyncio

from voltnir_sdk import AsyncVoltnirClient, VoltnirClient
from voltnir_sdk._generated import voltnir_api_v1_pb2 as pb2

_SVC = pb2.DESCRIPTOR.services_by_name["VoltAPI"]


def _env(name: str) -> str:
    return os.environ.get(name, "")


def _have_env() -> bool:
    return bool(_env("VOLTNIR_IT_API_KEY"))


def _category(item_name: str) -> str | None:
    """happy / fail / edge, read from the test function's name prefix."""
    fn = item_name.split("[", 1)[0]
    for cat in ("happy", "fail", "edge"):
        if fn.startswith(f"test_{cat}"):
            return cat
    return None


def pytest_collection_modifyitems(config, items):
    """Record per-RPC marker coverage, and skip the package when unconfigured.

    Recording happens during collection, without running anything, so the
    offline guard can read it even though every item is skip-marked here.
    """
    cov = getattr(config, "_rpc_integration_cov", None)
    if cov is None:
        cov = {}
        config._rpc_integration_cov = cov
    rest_cov = getattr(config, "_rest_integration_cov", None)
    if rest_cov is None:
        rest_cov = {}
        config._rest_integration_cov = rest_cov
    marker = pytest.mark.skip(reason="live integration suite: VOLTNIR_IT_API_KEY unset")
    here = os.sep + "integration" + os.sep
    for item in items:
        if here not in str(item.fspath):
            continue
        cat = _category(item.name)
        for name, target in (("rpc", cov), ("rest", rest_cov)):
            mark = item.get_closest_marker(name)
            if mark and cat:
                target.setdefault(mark.args[0], set()).add(cat)
        if not _have_env():
            item.add_marker(marker)


@pytest.fixture(scope="session")
def area() -> str:
    return _env("VOLTNIR_IT_AREA") or "10YBE----------2"


def _rest_url() -> str:
    host = _env("VOLTNIR_IT_HOST") or "127.0.0.1"
    return _env("VOLTNIR_IT_REST_URL") or f"http://{host}:3000"


def _new_sync_client(api_key: str) -> VoltnirClient:
    return VoltnirClient(
        host=_env("VOLTNIR_IT_HOST") or "127.0.0.1",
        port=int(_env("VOLTNIR_IT_PORT") or "3643"),
        api_key=api_key,
        timeout=15.0,
        rest_url=_rest_url(),
    )


@pytest.fixture(scope="session")
def admin() -> VoltnirClient:
    """The bootstrap admin client: every permission, drives the happy paths."""
    client = _new_sync_client(_env("VOLTNIR_IT_API_KEY"))
    yield client
    client.close()


@pytest_asyncio.fixture
async def aadmin() -> AsyncVoltnirClient:
    """A per-test async admin client, built inside the test's event loop.

    Function-scoped on purpose: the async client binds to the loop it is built
    in and refuses cross-loop use, and pytest-asyncio gives each test its own.
    """
    client = AsyncVoltnirClient(
        host=_env("VOLTNIR_IT_HOST") or "127.0.0.1",
        port=int(_env("VOLTNIR_IT_PORT") or "3643"),
        api_key=_env("VOLTNIR_IT_API_KEY"),
        timeout=15.0,
        rest_url=_rest_url(),
    )
    yield client
    await client.close()


@pytest.fixture(scope="session")
def badkey() -> VoltnirClient:
    """A client holding a syntactically valid but unknown key.

    Every RPC authenticates before it does anything else, so this drives the
    unauthenticated fail path uniformly, for reads that carry no permission gate
    and for the streams.
    """
    client = _new_sync_client("sdk-it-not-a-real-key")
    yield client
    client.close()


@pytest.fixture(scope="session")
def lowperm(admin) -> VoltnirClient:
    """A throwaway user with no permissions, assigned the admin's members.

    Its key drives the permission-denied fail path for the gated operations: it
    authenticates but holds none of the gates, so a hard-gated call refuses it.
    Deleted at session end; it created no orders or state of its own.
    """
    username = f"sdk-it-lp-{int(time.time())}"
    created = admin.create_user(username=username, permissions=[])
    user_id = created.user.id
    try:
        members = [m.id for m in admin.get_my_members().members]
        if members:
            admin.set_user_members(user_id=user_id, member_ids=members)
    except Exception:  # noqa: BLE001 (member assignment is best-effort setup)
        pass
    client = _new_sync_client(created.api_key)
    yield client
    client.close()
    admin.delete_user(user_id=user_id)


@pytest.fixture(scope="session", autouse=True)
def _gateway_operational(admin):
    """Wait for the gateway to reach operational before the suite runs.

    The runner returns as soon as the port opens; the M7 login and first
    snapshots land a little later. Poll rather than sleep a fixed time. If it
    never reaches operational the read tests still run, and the order tests fail
    loudly with the gateway's own state rather than being skipped.
    """
    if not _have_env():
        return
    deadline = time.monotonic() + 60.0
    while time.monotonic() < deadline:
        try:
            if admin.get_state().operational:
                return
        except Exception:  # noqa: BLE001 (still starting up)
            pass
        time.sleep(1.0)


@pytest.fixture(scope="session")
def trading_env(admin):
    """Enable trading and relax the risk limits for the order lifecycle, then
    restore every value at session end so the run leaves no net state change.

    A fresh gateway seeds the safe production defaults (trading off, a tiny
    position limit, a fail-closed cash posture), which reject even a hibernated
    order. Raising them is the real operator setup verify.py performs.
    """
    prior_allowed = admin.get_trading_allowed().allowed
    prior_limit = admin.get_contract_limit().quantity
    pool = admin.get_cash_limit().eur
    prior_cap = pool.cap_cents.value if pool.HasField("cap_cents") else None

    admin.set_trading_allowed(allowed=True)
    admin.set_contract_limit(quantity=1_000_000_000)
    admin.set_cash_limit(cap_cents=None, currency="eur")  # lift any Voltnir cap
    yield
    if prior_cap is not None:
        admin.set_cash_limit(cap_cents=prior_cap, currency="eur")
    admin.set_contract_limit(quantity=prior_limit)
    admin.set_trading_allowed(allowed=prior_allowed)


@pytest.fixture(scope="session")
def a_contract(admin, area) -> str:
    """A contract_id in `area` that is safe to rest a test order on."""
    from ._common import find_orderable_contract

    contract_id = find_orderable_contract(admin, area)
    if not contract_id:
        listed = len(admin.list_contracts(area_id=area).contracts)
        raise RuntimeError(
            f"no ACTI non-block contract found in area {area} "
            f"({listed} contracts listed); the sim may have no tradable book"
        )
    return contract_id


@pytest.fixture
def resting_order(admin, area, a_contract, trading_env) -> str:
    """A hibernated, confirmed order for the test that requests it.

    Function-scoped so each test gets its own and no test's cancel-all disturbs
    another's. Never exposed to the market; cancelled at teardown.
    """
    from ._common import cancel_quietly, open_hibernated_order, wait_confirmed

    coid, _cid = open_hibernated_order(admin, area)
    wait_confirmed(admin, coid)
    yield coid
    cancel_quietly(admin, coid)
