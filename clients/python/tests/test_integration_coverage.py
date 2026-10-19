"""Offline guard: the live integration suite covers every RPC three ways.

`tests/integration/` proves each RPC against a real gateway, but only when the
runner has set its environment. This guard runs in the ordinary offline suite:
it reads the ``rpc`` markers recorded while the integration package is
collected (collection happens with no gateway and no run) and fails naming any
RPC in the service descriptor that lacks a happy, a fail or an edge test.

That is what keeps the SDK honest when the next RPC lands: a wrapper with no
live coverage trips this before review, not in production.

The client methods served over REST (`REST_METHODS`, the report exports, which
are not RPCs) are held to the same rule through their own ``rest`` marker,
naming the method.
"""

from __future__ import annotations

import pytest

from voltnir_sdk._generated import voltnir_api_v1_pb2 as pb2

from conftest import REST_METHODS

_SVC = pb2.DESCRIPTOR.services_by_name["VoltAPI"]
_REQUIRED = frozenset({"happy", "fail", "edge"})


def _coverage(config) -> dict[str, set[str]]:
    return getattr(config, "_rpc_integration_cov", {})


def _rest_coverage(config) -> dict[str, set[str]]:
    return getattr(config, "_rest_integration_cov", {})


def _gaps(cov: dict[str, set[str]], names) -> dict[str, list[str]]:
    missing = {n: sorted(_REQUIRED - cov.get(n, set())) for n in names}
    return {n: cats for n, cats in missing.items() if cats}


def _grpc_rpcs() -> list[str]:
    return [m.name for m in _SVC.methods]


def test_every_rpc_has_a_happy_fail_and_edge_integration_test(request):
    """Every VoltAPI RPC carries a happy, a fail and an edge live test."""
    cov = _coverage(request.config)
    if not cov:
        pytest.skip(
            "no integration items were collected in this session; run the full "
            "suite (this guard reads collection-time markers)"
        )

    gaps = _gaps(cov, _grpc_rpcs())

    assert not gaps, (
        f"integration coverage gaps ({len(gaps)} RPC(s)); each needs a happy, a "
        f"fail and an edge test marked with @pytest.mark.rpc(<RpcName>): {gaps}"
    )


def test_every_rest_method_has_a_happy_fail_and_edge_integration_test(request):
    """Every REST-served method carries a happy, a fail and an edge live test."""
    cov = _rest_coverage(request.config)
    if not _coverage(request.config):
        pytest.skip("integration package not collected in this session")
    gaps = _gaps(cov, REST_METHODS)
    assert not gaps, (
        f"REST integration coverage gaps; each needs a happy, a fail and an edge "
        f"test marked with @pytest.mark.rest(<method>): {gaps}"
    )


def test_fail_detector_notices_a_missing_category(request):
    """The gap check actually fires when a category is absent.

    A guard that cannot fail is worthless, so run its logic against a coverage
    map with one RPC missing its edge test and assert that RPC is named.
    """
    cov = dict(_coverage(request.config))
    cov["GetState"] = {"happy", "fail"}  # edge removed
    assert _gaps(cov, _grpc_rpcs()).get("GetState") == ["edge"]

    rest_cov = dict(_rest_coverage(request.config))
    rest_cov["export_trades"] = {"happy", "edge"}  # fail removed
    assert _gaps(rest_cov, REST_METHODS).get("export_trades") == ["fail"]


def test_edge_coverage_map_is_populated_from_the_integration_package(request):
    """The recorder saw a substantial slice of the package, not nothing.

    A silently empty map would make the happy guard skip forever and hide a
    real regression, so pin that collection actually populated it.
    """
    cov = _coverage(request.config)
    if not cov:
        pytest.skip("integration package not collected in this session")
    assert len(cov) >= len(_grpc_rpcs()), (
        f"only {len(cov)} RPCs carry integration markers; expected every one"
    )
