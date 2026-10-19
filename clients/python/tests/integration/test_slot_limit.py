"""The slot position limit against a live gateway: the mode and House limit,
the per-quarter-hour usage read, and its stream.

The Set test reads the current setting, writes the same mode with another
limit, asserts, and restores it in a ``finally``, so the run never changes the
mode the operator configured."""

from __future__ import annotations

import time

import pytest

from voltnir_sdk import InvalidArgument, PermissionDenied, Unauthenticated, slot_limit_mode_name

_HOUR_MS = 3_600_000


def _window(hours: int) -> tuple[int, int]:
    start = int(time.time() * 1000)
    return start, start + hours * _HOUR_MS


# ── GetSlotLimit / SetSlotLimit (gated) ─────────────────────────────────────


@pytest.mark.rpc("GetSlotLimit")
def test_happy_get_slot_limit(admin):
    resp = admin.get_slot_limit()
    assert slot_limit_mode_name(resp.mode) in ("off", "observe", "reject")
    assert resp.house_limit >= 0


@pytest.mark.rpc("GetSlotLimit")
def test_fail_get_slot_limit_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.get_slot_limit()


@pytest.mark.rpc("GetSlotLimit")
def test_edge_get_slot_limit_is_a_plain_sub_mw_integer(admin):
    assert isinstance(admin.get_slot_limit().house_limit, int)


@pytest.mark.rpc("SetSlotLimit")
def test_happy_set_slot_limit_round_trips(admin):
    prior = admin.get_slot_limit()
    mode = slot_limit_mode_name(prior.mode)
    try:
        resp = admin.set_slot_limit(mode=mode, house_limit=prior.house_limit + 1_000)
        assert (resp.mode, resp.house_limit) == (prior.mode, prior.house_limit + 1_000)
        assert admin.get_slot_limit().house_limit == prior.house_limit + 1_000
    finally:
        admin.set_slot_limit(mode=mode, house_limit=prior.house_limit)


@pytest.mark.rpc("SetSlotLimit")
def test_fail_set_slot_limit_refuses_a_negative_limit(admin):
    prior = admin.get_slot_limit()
    with pytest.raises(InvalidArgument):
        admin.set_slot_limit(mode=slot_limit_mode_name(prior.mode), house_limit=-1)
    assert admin.get_slot_limit() == prior


@pytest.mark.rpc("SetSlotLimit")
def test_edge_set_slot_limit_denied_without_set_position_limit(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.set_slot_limit(mode="off", house_limit=0)


# ── GetSlotPositions (authenticated, member-scoped) ─────────────────────────


@pytest.mark.rpc("GetSlotPositions")
def test_happy_get_slot_positions(admin, area):
    start, end = _window(24)
    resp = admin.get_slot_positions(delivery_area=area, from_ms=start, to_ms=end)
    assert resp.delivery_area == area
    assert resp.HasField("house_limit"), "the admin sees the House scope"
    for slot in resp.slots:
        assert slot.slot_end_ms - slot.slot_start_ms == 15 * 60 * 1000


@pytest.mark.rpc("GetSlotPositions")
def test_fail_get_slot_positions_refuses_a_range_over_48_hours(admin, area):
    start, end = _window(49)
    with pytest.raises(InvalidArgument):
        admin.get_slot_positions(delivery_area=area, from_ms=start, to_ms=end)


@pytest.mark.rpc("GetSlotPositions")
def test_edge_get_slot_positions_without_read_status_has_no_house(lowperm, area):
    start, end = _window(24)
    resp = lowperm.get_slot_positions(delivery_area=area, from_ms=start, to_ms=end)
    assert not resp.HasField("house_limit")
    assert all(s.scope != "house" for slot in resp.slots for s in slot.scopes)


# ── WatchSlotPositions (stream) ─────────────────────────────────────────────


@pytest.mark.rpc("WatchSlotPositions")
def test_happy_watch_slot_positions_sends_the_full_set_first(admin, area):
    start, end = _window(24)
    stream = admin.watch_slot_positions(delivery_area=area, from_ms=start, to_ms=end, timeout=4.0)
    first = next(iter(stream))
    assert first.seq >= 1
    assert first.delivery_area == area


@pytest.mark.rpc("WatchSlotPositions")
def test_fail_watch_slot_positions_unauthenticated(badkey, area):
    start, end = _window(24)
    with pytest.raises(Unauthenticated):
        next(iter(badkey.watch_slot_positions(delivery_area=area, from_ms=start, to_ms=end, timeout=4.0)))


@pytest.mark.rpc("WatchSlotPositions")
def test_edge_watch_slot_positions_another_member_is_refused(lowperm, area):
    start, end = _window(24)
    with pytest.raises(PermissionDenied):
        next(
            iter(
                lowperm.watch_slot_positions(
                    delivery_area=area, from_ms=start, to_ms=end, v_member_short_id="VM999", timeout=4.0
                )
            )
        )
