"""A member's delivery areas on create and patch, on both clients.

The scope is a message field with presence: on create an absent scope means
the member starts with no areas, and on patch it means the areas are left as
they are. So the tests assert presence, not only the value: a scope dropped
on the way to the wire would silently mean "no areas" or "unchanged".
"""

from __future__ import annotations

import voltnir_sdk
from voltnir_sdk import DeliveryAreaScope
from voltnir_sdk._generated import voltnir_api_v1_pb2 as pb2

_NL = "10YNL----------L"
_BE = "10YBE----------2"


# Happy: a listed scope reaches the wire whole and reads back on the member.
def test_happy_create_member_sends_the_listed_areas(client, fake):
    member = client.create_member(
        name="desk-a", max_position=1_000, delivery_areas=DeliveryAreaScope(area_ids=[_NL, _BE])
    )
    req = fake.requests["CreateMember"]
    assert req.HasField("delivery_areas")
    assert (req.delivery_areas.all, list(req.delivery_areas.area_ids)) == (False, [_NL, _BE])
    assert list(member.delivery_areas.area_ids) == [_NL, _BE]


async def test_happy_async_create_member_sends_all(aclient, fake):
    await aclient.create_member(
        name="desk-a", max_position=1_000, delivery_areas=DeliveryAreaScope(all=True)
    )
    req = fake.requests["CreateMember"]
    assert req.HasField("delivery_areas") and req.delivery_areas.all


# Edge: no scope on create is absent on the wire, which the gateway reads as
# "no areas", never as "all".
def test_edge_create_member_without_areas_sends_none(client, fake):
    client.create_member(name="desk-b", max_position=1_000)
    assert not fake.requests["CreateMember"].HasField("delivery_areas")


# Happy: a patch replaces the scope; an empty list is sent as present, which
# takes every area away rather than leaving the scope as it was.
def test_happy_patch_member_replaces_the_areas(client, fake):
    client.patch_member(id="m-1", delivery_areas=DeliveryAreaScope(area_ids=[_NL]))
    req = fake.requests["PatchMember"]
    assert req.HasField("delivery_areas") and list(req.delivery_areas.area_ids) == [_NL]
    client.patch_member(id="m-1", delivery_areas=DeliveryAreaScope())
    req = fake.requests["PatchMember"]
    assert req.HasField("delivery_areas") and not req.delivery_areas.area_ids


async def test_happy_async_patch_member_replaces_the_areas(aclient, fake):
    await aclient.patch_member(id="m-1", delivery_areas=DeliveryAreaScope(all=True))
    req = fake.requests["PatchMember"]
    assert req.HasField("delivery_areas") and req.delivery_areas.all


# Edge: a patch of another field leaves the scope absent, so it is untouched.
def test_edge_patch_member_without_areas_leaves_them(client, fake):
    client.patch_member(id="m-1", name="desk-a")
    assert not fake.requests["PatchMember"].HasField("delivery_areas")


# Edge: the scope type is the public wire type, exported by the package.
def test_edge_delivery_area_scope_is_public():
    assert DeliveryAreaScope is pb2.DeliveryAreaScope
    assert "DeliveryAreaScope" in voltnir_sdk.__all__
