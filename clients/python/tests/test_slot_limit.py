"""The slot position limit wrappers: what each one puts on the wire, what is
refused before anything is sent, and how a mode reads back. Both clients.

The slot limit caps the net MW per quarter-hour per delivery area, summing
every contract that covers the quarter-hour; every figure is sub-MW. A member
slot limit of 0 is flat-only and must reach the gateway as 0, not as "no
limit", so the member tests assert presence, not only the value.
"""

from __future__ import annotations

import pytest

from voltnir_sdk import OrderValidationError, SlotLimitMode, slot_limit_mode_name

_AREA = "10YBE----------2"
_FROM = 1_790_000_000_000
_TO = _FROM + 2 * 3_600_000


# Happy: the mode name is sent as its enum, in any case, with the limit.
@pytest.mark.parametrize(
    "mode,wire",
    [
        ("off", SlotLimitMode.SLOT_LIMIT_MODE_OFF),
        ("Observe", SlotLimitMode.SLOT_LIMIT_MODE_OBSERVE),
        ("REJECT", SlotLimitMode.SLOT_LIMIT_MODE_REJECT),
    ],
)
def test_happy_set_slot_limit_sends_the_mode_and_the_limit(client, fake, mode, wire):
    client.set_slot_limit(mode=mode, house_limit=20_000)
    req = fake.requests["SetSlotLimit"]
    assert (req.mode, req.house_limit) == (wire, 20_000)


# Fail: an unknown mode is refused locally and nothing is sent.
@pytest.mark.parametrize("bad", ["", "strict", "on", "unspecified"])
def test_fail_set_slot_limit_refuses_an_unknown_mode_locally(client, fake, bad):
    with pytest.raises(OrderValidationError, match="mode must be 'off', 'observe' or 'reject'"):
        client.set_slot_limit(mode=bad, house_limit=0)
    assert "SetSlotLimit" not in fake.requests


async def test_fail_async_set_slot_limit_refuses_an_unknown_mode_locally(aclient, fake):
    with pytest.raises(OrderValidationError):
        await aclient.set_slot_limit(mode="strict", house_limit=0)
    assert "SetSlotLimit" not in fake.requests


# Edge: OFF is sent explicitly, never left to how an unset mode reads.
def test_edge_off_is_sent_as_off_not_unspecified(client, fake):
    client.set_slot_limit(mode="off", house_limit=0)
    assert fake.requests["SetSlotLimit"].mode == SlotLimitMode.SLOT_LIMIT_MODE_OFF


# Edge: a House limit of 0 (flat-only) is sent as set, never as absent: the
# gateway refuses a set without one.
def test_edge_a_zero_house_limit_is_sent_as_set(client, fake):
    client.set_slot_limit(mode="observe", house_limit=0)
    req = fake.requests["SetSlotLimit"]
    assert req.HasField("house_limit") and req.house_limit == 0


# Edge: UNSPECIFIED reads as "off", the default, and each mode by its name.
def test_edge_an_unspecified_mode_reads_as_off():
    assert slot_limit_mode_name(SlotLimitMode.SLOT_LIMIT_MODE_UNSPECIFIED) == "off"
    assert slot_limit_mode_name(SlotLimitMode.SLOT_LIMIT_MODE_OFF) == "off"
    assert slot_limit_mode_name(SlotLimitMode.SLOT_LIMIT_MODE_OBSERVE) == "observe"
    assert slot_limit_mode_name(SlotLimitMode.SLOT_LIMIT_MODE_REJECT) == "reject"


# Happy: the usage read and the stream forward the area, the range and the
# member; an omitted member is unset on the wire, not "".
def test_happy_slot_positions_forward_every_field(client, fake):
    client.get_slot_positions(delivery_area=_AREA, from_ms=_FROM, to_ms=_TO, v_member_short_id="VM001")
    req = fake.requests["GetSlotPositions"]
    assert (req.delivery_area, req.from_ms, req.to_ms, req.v_member_short_id) == (_AREA, _FROM, _TO, "VM001")
    client.get_slot_positions(delivery_area=_AREA, from_ms=_FROM, to_ms=_TO)
    assert not fake.requests["GetSlotPositions"].HasField("v_member_short_id")
    frames = list(client.watch_slot_positions(delivery_area=_AREA, from_ms=_FROM, to_ms=_TO, timeout=5.0))
    assert len(frames) == fake.stream_count
    req = fake.requests["WatchSlotPositions"]
    assert (req.delivery_area, req.from_ms, req.to_ms) == (_AREA, _FROM, _TO)
    assert not req.HasField("v_member_short_id")


async def test_happy_async_slot_positions_forward_every_field(aclient, fake):
    await aclient.get_slot_positions(delivery_area=_AREA, from_ms=_FROM, to_ms=_TO, v_member_short_id="VM001")
    assert fake.requests["GetSlotPositions"].v_member_short_id == "VM001"
    frames = [f async for f in aclient.watch_slot_positions(delivery_area=_AREA, from_ms=_FROM, to_ms=_TO)]
    assert len(frames) == fake.stream_count
    assert fake.requests["WatchSlotPositions"].to_ms == _TO


# Edge: a member slot limit of 0 is sent as 0, present; none is absent.
def test_edge_create_member_sends_zero_as_zero_and_none_as_absent(client, fake):
    client.create_member(name="desk-a", max_position=1_000, max_slot_position=0)
    req = fake.requests["CreateMember"]
    assert req.HasField("max_slot_position") and req.max_slot_position == 0
    client.create_member(name="desk-b", max_position=1_000)
    assert not fake.requests["CreateMember"].HasField("max_slot_position")


# Happy: a patch sets the member slot limit, or clears it, and leaves it
# untouched when neither is passed.
def test_happy_patch_member_sets_clears_or_leaves_the_slot_limit(client, fake):
    client.patch_member(id="m-1", max_slot_position=2_500)
    req = fake.requests["PatchMember"]
    assert (req.max_slot_position, req.clear_max_slot_position) == (2_500, False)
    client.patch_member(id="m-1", clear_max_slot_position=True)
    req = fake.requests["PatchMember"]
    assert not req.HasField("max_slot_position") and req.clear_max_slot_position
    client.patch_member(id="m-1", name="desk-a")
    req = fake.requests["PatchMember"]
    assert not req.HasField("max_slot_position") and not req.clear_max_slot_position


# Fail: setting and clearing at once is refused locally, on both clients.
def test_fail_patch_member_refuses_set_and_clear_together(client, fake):
    with pytest.raises(OrderValidationError, match="exclusive"):
        client.patch_member(id="m-1", max_slot_position=1, clear_max_slot_position=True)
    assert "PatchMember" not in fake.requests


async def test_fail_async_patch_member_refuses_set_and_clear_together(aclient, fake):
    with pytest.raises(OrderValidationError, match="exclusive"):
        await aclient.patch_member(id="m-1", max_slot_position=1, clear_max_slot_position=True)
    assert "PatchMember" not in fake.requests
