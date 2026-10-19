"""Restart: bounce the whole gateway. Destructive — every live stream drops and
the connection is reset — so it is skipped unless ``VOLTNIR_IT_RESTART=1`` and,
named to sort last, runs after every other test. Only the happy case actually
restarts; the fail and edge cases are refused before anything happens.

The coverage guard is satisfied by these markers whether or not the tests run.
"""

from __future__ import annotations

import os

import pytest

from voltnir_sdk import PermissionDenied, Unauthenticated

_ENABLED = os.environ.get("VOLTNIR_IT_RESTART") == "1"
_skip = pytest.mark.skipif(not _ENABLED, reason="restart is opt-in: set VOLTNIR_IT_RESTART=1")


@_skip
@pytest.mark.rpc("Restart")
def test_happy_restart(admin):
    # Actually restarts the gateway; every consumer must resubscribe afterwards.
    resp = admin.restart()
    assert isinstance(resp.message, str)


@_skip
@pytest.mark.rpc("Restart")
def test_fail_restart_denied(lowperm):
    # Refused before any restart happens: the gateway is untouched.
    with pytest.raises(PermissionDenied):
        lowperm.restart()


@_skip
@pytest.mark.rpc("Restart")
def test_edge_restart_unauthenticated(badkey):
    # An unknown key never reaches the restart path.
    with pytest.raises(Unauthenticated):
        badkey.restart()
