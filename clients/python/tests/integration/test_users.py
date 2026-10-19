"""Users and members: identity reads, user CRUD, key rotation, member scoping.

Each user test creates and removes its own throwaway user. The suite shares
one member for the session and deletes it at teardown; the delete tests make
their own.
"""

from __future__ import annotations

import time
import uuid

import pytest

from voltnir_sdk import NotFound, PermissionDenied, Unauthenticated, VoltnirError


@pytest.fixture
def throwaway_user(admin):
    """A fresh permissionless user, deleted when the test ends."""
    username = f"sdk-it-u-{uuid.uuid4().hex[:12]}"
    created = admin.create_user(username=username, permissions=[])
    yield created
    try:
        admin.delete_user(user_id=created.user.id)
    except VoltnirError:
        pass


@pytest.fixture(scope="session")
def it_member(admin):
    """One virtual member for the session, deleted at teardown."""
    name = f"sdk-it-{int(time.time())}"
    member = admin.create_member(name=name, max_position=1000)
    yield member
    admin.patch_member(id=member.id, active=False)
    try:
        admin.delete_member(member_id=member.id)
    except VoltnirError:
        # Refused while an order, a position or consumed cash of it is left
        # (until the next booking cut); the member then stays inactive.
        pass


def _client_for(api_key: str):
    from ._common import new_sync_client

    return new_sync_client(api_key)


# ── GetMe / GetMyMembers (authenticated) ────────────────────────────────────


@pytest.mark.rpc("GetMe")
def test_happy_get_me(admin):
    me = admin.get_me()
    assert me.id
    assert me.username


@pytest.mark.rpc("GetMe")
async def test_happy_get_me_async(aadmin):
    assert (await aadmin.get_me()).id


@pytest.mark.rpc("GetMe")
def test_fail_get_me_unauthenticated(badkey):
    with pytest.raises(Unauthenticated):
        badkey.get_me()


@pytest.mark.rpc("GetMe")
def test_edge_get_me_lists_its_permissions(admin):
    # The admin key is broadly permissioned; the list is a real, non-empty set.
    assert len(admin.get_me().permissions) >= 1


@pytest.mark.rpc("GetMyMembers")
def test_happy_get_my_members(admin):
    assert hasattr(admin.get_my_members(), "members")


@pytest.mark.rpc("GetMyMembers")
def test_fail_get_my_members_unauthenticated(badkey):
    with pytest.raises(Unauthenticated):
        badkey.get_my_members()


@pytest.mark.rpc("GetMyMembers")
def test_edge_get_my_members_rows_carry_an_id(admin):
    for m in admin.get_my_members().members:
        assert m.id


# ── ListUsers / ListMembers (gated) ─────────────────────────────────────────


@pytest.mark.rpc("ListUsers")
def test_happy_list_users(admin):
    users = admin.list_users().users
    assert any(u.id for u in users)


@pytest.mark.rpc("ListUsers")
def test_fail_list_users_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.list_users()


@pytest.mark.rpc("ListUsers")
def test_edge_list_users_includes_the_caller(admin):
    me = admin.get_me().id
    assert me in {u.id for u in admin.list_users().users}


@pytest.mark.rpc("ListMembers")
def test_happy_list_members(admin, it_member):
    assert it_member.id in {m.id for m in admin.list_members().members}


@pytest.mark.rpc("ListMembers")
def test_fail_list_members_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.list_members()


@pytest.mark.rpc("ListMembers")
def test_edge_list_members_rows_carry_a_short_id(admin, it_member):
    rows = {m.id: m for m in admin.list_members().members}
    assert rows[it_member.id].short_id


# ── CreateUser / DeleteUser (gated) ─────────────────────────────────────────


@pytest.mark.rpc("CreateUser")
def test_happy_create_user(throwaway_user):
    assert throwaway_user.api_key
    assert throwaway_user.user.id


@pytest.mark.rpc("CreateUser")
def test_fail_create_user_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.create_user(username="sdk-it-nope", permissions=[])


@pytest.mark.rpc("CreateUser")
def test_edge_create_user_grants_the_requested_permissions(admin):
    username = f"sdk-it-u-{uuid.uuid4().hex[:12]}"
    created = admin.create_user(username=username, permissions=["read_state"])
    try:
        assert "read_state" in created.user.permissions
    finally:
        admin.delete_user(user_id=created.user.id)


@pytest.mark.rpc("DeleteUser")
def test_happy_delete_user(admin):
    username = f"sdk-it-u-{uuid.uuid4().hex[:12]}"
    created = admin.create_user(username=username, permissions=[])
    admin.delete_user(user_id=created.user.id)
    assert created.user.id not in {u.id for u in admin.list_users().users}


@pytest.mark.rpc("DeleteUser")
def test_fail_delete_user_denied(lowperm, throwaway_user):
    with pytest.raises(PermissionDenied):
        lowperm.delete_user(user_id=throwaway_user.user.id)


@pytest.mark.rpc("DeleteUser")
def test_edge_delete_unknown_user_is_a_translated_error(admin):
    with pytest.raises(VoltnirError) as exc:
        admin.delete_user(user_id="00000000-0000-4000-8000-000000000000")
    assert exc.value.rpc == "DeleteUser"


# ── SetPermissions / RotateApiKey (gated) ───────────────────────────────────


@pytest.mark.rpc("SetPermissions")
def test_happy_set_permissions(admin, throwaway_user):
    uid = throwaway_user.user.id
    admin.set_permissions(user_id=uid, permissions=["read_state", "read_status"])
    granted = {u.id: u for u in admin.list_users().users}[uid].permissions
    assert set(granted) >= {"read_state", "read_status"}


@pytest.mark.rpc("SetPermissions")
def test_fail_set_permissions_denied(lowperm, throwaway_user):
    with pytest.raises(PermissionDenied):
        lowperm.set_permissions(user_id=throwaway_user.user.id, permissions=["read_state"])


@pytest.mark.rpc("SetPermissions")
def test_edge_set_permissions_empty_strips_them_all(admin, throwaway_user):
    uid = throwaway_user.user.id
    admin.set_permissions(user_id=uid, permissions=["read_state"])
    admin.set_permissions(user_id=uid, permissions=[])
    granted = {u.id: u for u in admin.list_users().users}[uid].permissions
    assert list(granted) == []


@pytest.mark.rpc("RotateApiKey")
def test_happy_rotate_api_key(admin, throwaway_user):
    rotated = admin.rotate_api_key(user_id=throwaway_user.user.id)
    assert rotated.api_key
    assert rotated.api_key != throwaway_user.api_key


@pytest.mark.rpc("RotateApiKey")
def test_fail_rotate_api_key_denied(lowperm, throwaway_user):
    with pytest.raises(PermissionDenied):
        lowperm.rotate_api_key(user_id=throwaway_user.user.id)


@pytest.mark.rpc("RotateApiKey")
def test_edge_rotated_key_authenticates(admin, throwaway_user):
    # The rotated key is live: it authenticates where the old one is now void.
    rotated = admin.rotate_api_key(user_id=throwaway_user.user.id)
    client = _client_for(rotated.api_key)
    try:
        assert client.get_me().id == throwaway_user.user.id
    finally:
        client.close()


# ── GetUserMembers / SetUserMembers (gated) ─────────────────────────────────


@pytest.mark.rpc("SetUserMembers")
def test_happy_set_user_members(admin, throwaway_user, it_member):
    admin.set_user_members(user_id=throwaway_user.user.id, member_ids=[it_member.id])
    got = admin.get_user_members(user_id=throwaway_user.user.id).member_ids
    assert it_member.id in got


@pytest.mark.rpc("SetUserMembers")
def test_fail_set_user_members_denied(lowperm, throwaway_user, it_member):
    with pytest.raises(PermissionDenied):
        lowperm.set_user_members(user_id=throwaway_user.user.id, member_ids=[it_member.id])


@pytest.mark.rpc("SetUserMembers")
def test_edge_set_user_members_empty_clears_the_set(admin, throwaway_user, it_member):
    admin.set_user_members(user_id=throwaway_user.user.id, member_ids=[it_member.id])
    admin.set_user_members(user_id=throwaway_user.user.id, member_ids=[])
    assert list(admin.get_user_members(user_id=throwaway_user.user.id).member_ids) == []


@pytest.mark.rpc("GetUserMembers")
def test_happy_get_user_members(admin, throwaway_user, it_member):
    admin.set_user_members(user_id=throwaway_user.user.id, member_ids=[it_member.id])
    assert it_member.id in admin.get_user_members(user_id=throwaway_user.user.id).member_ids


@pytest.mark.rpc("GetUserMembers")
def test_fail_get_user_members_denied(lowperm, throwaway_user):
    with pytest.raises(PermissionDenied):
        lowperm.get_user_members(user_id=throwaway_user.user.id)


@pytest.mark.rpc("GetUserMembers")
def test_edge_get_user_members_defaults_to_empty(admin, throwaway_user):
    # A fresh user is assigned no members until one is set.
    assert list(admin.get_user_members(user_id=throwaway_user.user.id).member_ids) == []


# ── CreateMember / PatchMember (gated) ──────────────────────────────────────


@pytest.mark.rpc("CreateMember")
def test_happy_create_member(it_member):
    assert it_member.id
    assert it_member.short_id


@pytest.mark.rpc("CreateMember")
def test_fail_create_member_denied(lowperm):
    with pytest.raises(PermissionDenied):
        lowperm.create_member(name="sdk-it-nope", max_position=1)


@pytest.mark.rpc("CreateMember")
def test_edge_create_member_starts_active(admin, it_member):
    row = {m.id: m for m in admin.list_members().members}[it_member.id]
    assert row.active is True


@pytest.mark.rpc("PatchMember")
def test_happy_patch_member_updates_max_position(admin, it_member):
    before = {m.id: m for m in admin.list_members().members}[it_member.id].max_position
    try:
        admin.patch_member(id=it_member.id, max_position=5000)
        after = {m.id: m for m in admin.list_members().members}[it_member.id].max_position
        assert after == 5000
    finally:
        admin.patch_member(id=it_member.id, max_position=before)


@pytest.mark.rpc("PatchMember")
def test_fail_patch_member_denied(lowperm, it_member):
    with pytest.raises(PermissionDenied):
        lowperm.patch_member(id=it_member.id, max_position=1)


@pytest.mark.rpc("PatchMember")
def test_edge_patch_member_rename_only_leaves_other_fields(admin, it_member):
    before = {m.id: m for m in admin.list_members().members}[it_member.id]
    prior_name, prior_max = before.name, before.max_position
    try:
        admin.patch_member(id=it_member.id, name="sdk-it-renamed")
        row = {m.id: m for m in admin.list_members().members}[it_member.id]
        assert row.name == "sdk-it-renamed"
        assert row.max_position == prior_max
    finally:
        admin.patch_member(id=it_member.id, name=prior_name)


# ── DeleteMember (gated) ────────────────────────────────────────────────────


@pytest.fixture
def doomed_member(admin):
    """A fresh member with no orders, for a test to delete."""
    return admin.create_member(name=f"sdk-it-d-{uuid.uuid4().hex[:12]}", max_position=1)


@pytest.mark.rpc("DeleteMember")
def test_happy_delete_member_leaves_the_listing(admin, doomed_member):
    admin.delete_member(member_id=doomed_member.id)
    assert doomed_member.id not in {m.id for m in admin.list_members().members}


@pytest.mark.rpc("DeleteMember")
def test_fail_delete_member_denied(lowperm, admin, doomed_member):
    try:
        with pytest.raises(PermissionDenied):
            lowperm.delete_member(member_id=doomed_member.id)
        assert doomed_member.id in {m.id for m in admin.list_members().members}
    finally:
        admin.delete_member(member_id=doomed_member.id)


@pytest.mark.rpc("DeleteMember")
def test_edge_delete_member_twice_is_not_found(admin, doomed_member):
    admin.delete_member(member_id=doomed_member.id)
    with pytest.raises(NotFound) as exc:
        admin.delete_member(member_id=doomed_member.id)
    assert exc.value.message == "member not found"
