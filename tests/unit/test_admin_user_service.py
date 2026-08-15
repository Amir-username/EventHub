"""Unit tests for AdminUserService business logic.

Tests admin CRUD, _parse_user_role edge cases, self-delete guard,
and email duplicate detection on update.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import UserRole
from app.schemas.user import AdminUserCreate, AdminUserUpdate
from app.services.admin_user_service import AdminUserService, _parse_user_role

# ── _parse_user_role helper ─────────────────────────────────────────


async def test_parse_user_role_valid_values():
    assert _parse_user_role("admin") == UserRole.ADMIN
    assert _parse_user_role("customer") == UserRole.CUSTOMER


async def test_parse_user_role_invalid_raises_with_message():
    with pytest.raises(ValueError, match="Invalid role 'superadmin'"):
        _parse_user_role("superadmin")


# ── List Users ──────────────────────────────────────────────────────


async def test_list_users_returns_all(db_session: AsyncSession, user_factory):
    await user_factory()
    await user_factory()
    await user_factory()

    svc = AdminUserService(db_session)
    _items, total = await svc.list_users()

    assert total == 3


async def test_list_users_filter_by_role(db_session: AsyncSession, user_factory):
    await user_factory(role=UserRole.ADMIN)
    await user_factory(role=UserRole.CUSTOMER)
    await user_factory(role=UserRole.CUSTOMER)

    svc = AdminUserService(db_session)
    items, total = await svc.list_users(role=UserRole.CUSTOMER)

    assert total == 2
    for u in items:
        assert u.role == UserRole.CUSTOMER


async def test_list_users_search_by_email(db_session: AsyncSession, user_factory):
    await user_factory(email="alice@example.com")
    await user_factory(email="bob@example.com")

    svc = AdminUserService(db_session)
    items, total = await svc.list_users(search="alice")

    assert total == 1
    assert items[0].email == "alice@example.com"


async def test_list_users_search_by_name(db_session: AsyncSession, user_factory):
    await user_factory(full_name="Alice Wonderland")
    await user_factory(full_name="Bob Builder")

    svc = AdminUserService(db_session)
    items, total = await svc.list_users(search="Alice")

    assert total == 1
    assert items[0].full_name == "Alice Wonderland"


# ── Get User ────────────────────────────────────────────────────────


async def test_get_user_success(db_session: AsyncSession, user_factory):
    user = await user_factory(email="target@example.com")

    svc = AdminUserService(db_session)
    result = await svc.get_user(user.id)

    assert result.email == "target@example.com"


async def test_get_user_rejects_nonexistent(db_session: AsyncSession):
    svc = AdminUserService(db_session)
    with pytest.raises(ValueError, match="User not found"):
        await svc.get_user(9999)


# ── Create User (Admin) ─────────────────────────────────────────────


async def test_create_user_success(db_session: AsyncSession):
    svc = AdminUserService(db_session)
    user = await svc.create_user(
        AdminUserCreate(
            email="newadmin@example.com",
            password="SecurePass1!",
            full_name="New Admin",
            role="admin",
        )
    )

    assert user.id is not None
    assert user.email == "newadmin@example.com"
    assert user.role == UserRole.ADMIN
    assert user.hashed_password != "SecurePass1!"


async def test_create_user_rejects_duplicate_email(
    db_session: AsyncSession, user_factory
):
    await user_factory(email="taken@example.com")

    svc = AdminUserService(db_session)
    with pytest.raises(ValueError, match="Email already exists"):
        await svc.create_user(
            AdminUserCreate(
                email="taken@example.com",
                password="AnyPass1!",
                full_name="Dup",
                role="customer",
            )
        )


async def test_create_user_rejects_invalid_role(db_session: AsyncSession):
    svc = AdminUserService(db_session)
    with pytest.raises(ValueError, match="Invalid role 'superadmin'"):
        await svc.create_user(
            AdminUserCreate(
                email="badrole@example.com",
                password="AnyPass1!",
                full_name="Bad Role",
                role="superadmin",
            )
        )


# ── Update User (Admin) ─────────────────────────────────────────────


async def test_update_user_email(db_session: AsyncSession, user_factory):
    user = await user_factory(email="old@example.com")

    svc = AdminUserService(db_session)
    updated = await svc.update_user(user.id, AdminUserUpdate(email="new@example.com"))

    assert updated.email == "new@example.com"


async def test_update_user_password(db_session: AsyncSession, user_factory):
    user = await user_factory(hashed_password="old_hash")

    svc = AdminUserService(db_session)
    updated = await svc.update_user(
        user.id, AdminUserUpdate(password="NewSecurePass1!")
    )

    assert updated.hashed_password != "old_hash"
    assert updated.hashed_password != "NewSecurePass1!"


async def test_update_user_role(db_session: AsyncSession, user_factory):
    user = await user_factory(role=UserRole.CUSTOMER)

    svc = AdminUserService(db_session)
    updated = await svc.update_user(user.id, AdminUserUpdate(role="admin"))

    assert updated.role == UserRole.ADMIN


async def test_update_user_rejects_nonexistent(db_session: AsyncSession):
    svc = AdminUserService(db_session)
    with pytest.raises(ValueError, match="User not found"):
        await svc.update_user(9999, AdminUserUpdate(email="x@y.com"))


async def test_update_user_rejects_duplicate_email_different_user(
    db_session: AsyncSession, user_factory
):
    user_a = await user_factory(email="a@example.com")
    await user_factory(email="b@example.com")

    svc = AdminUserService(db_session)
    # Trying to change user_a's email to b's email should fail
    with pytest.raises(ValueError, match="Email already exists"):
        await svc.update_user(user_a.id, AdminUserUpdate(email="b@example.com"))


async def test_update_user_same_email_is_allowed(
    db_session: AsyncSession, user_factory
):
    """Updating a user's email to its current value should NOT fail."""
    user = await user_factory(email="same@example.com")

    svc = AdminUserService(db_session)
    updated = await svc.update_user(user.id, AdminUserUpdate(email="same@example.com"))

    assert updated.email == "same@example.com"


async def test_update_user_rejects_invalid_role(db_session: AsyncSession, user_factory):
    user = await user_factory(role=UserRole.CUSTOMER)

    svc = AdminUserService(db_session)
    with pytest.raises(ValueError, match="Invalid role"):
        await svc.update_user(user.id, AdminUserUpdate(role="superadmin"))


async def test_update_user_none_fields_ignored(db_session: AsyncSession, user_factory):
    user = await user_factory(full_name="Stable", email="stable@example.com")

    svc = AdminUserService(db_session)
    updated = await svc.update_user(user.id, AdminUserUpdate())

    assert updated.full_name == "Stable"
    assert updated.email == "stable@example.com"


# ── Delete User (Admin) ─────────────────────────────────────────────


async def test_delete_user_success(db_session: AsyncSession, user_factory):
    user = await user_factory()
    admin = await user_factory()

    svc = AdminUserService(db_session)
    await svc.delete_user(user.id, current_user_id=admin.id)

    with pytest.raises(ValueError, match="User not found"):
        await svc.get_user(user.id)


async def test_delete_user_rejects_self_delete(db_session: AsyncSession, user_factory):
    user = await user_factory()

    svc = AdminUserService(db_session)
    with pytest.raises(ValueError, match="Cannot delete your own account"):
        await svc.delete_user(user.id, current_user_id=user.id)


async def test_delete_user_rejects_nonexistent(db_session: AsyncSession, user_factory):
    admin = await user_factory()

    svc = AdminUserService(db_session)
    with pytest.raises(ValueError, match="User not found"):
        await svc.delete_user(9999, current_user_id=admin.id)
