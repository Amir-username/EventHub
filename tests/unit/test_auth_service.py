"""Unit tests for AuthService business logic.

These tests hit a real (in-memory SQLite) database through the repository
layer, which makes them integration-light. Pure unit tests that mock
the repository can be added later as needed.
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import UserRole
from app.schemas.auth import UserLogin, UserRegister
from app.services.auth_service import AuthService

# ── Register ─────────────────────────────────────────────────────────


async def test_register_creates_user(db_session: AsyncSession, user_factory):
    svc = AuthService(db_session)
    data = UserRegister(
        email="new@example.com",
        password="SecurePass123!",
        confirm_pass="SecurePass123!",
        full_name="New User",
    )
    user = await svc.register(data)

    assert user.id is not None
    assert user.email == "new@example.com"
    assert user.full_name == "New User"
    assert user.role == UserRole.CUSTOMER


async def test_register_rejects_duplicate_email(db_session: AsyncSession, user_factory):
    await user_factory(email="taken@example.com")

    svc = AuthService(db_session)
    data = UserRegister(
        email="taken@example.com",
        password="SecurePass123!",
        confirm_pass="SecurePass123!",
    )

    with pytest.raises(ValueError, match="email already exists"):
        await svc.register(data)


async def test_register_hashes_password(db_session: AsyncSession):
    svc = AuthService(db_session)
    data = UserRegister(
        email="hash@example.com",
        password="MyPassword1!",
        confirm_pass="MyPassword1!",
        full_name="Hash Test",
    )
    user = await svc.register(data)

    assert user.hashed_password != "MyPassword1!"
    # Verify it's a valid argon2 hash
    assert user.hashed_password.startswith("$argon2")


# ── Login ────────────────────────────────────────────────────────────


async def test_login_returns_token_pair(db_session: AsyncSession, user_factory):
    password = "CorrectPass1!"
    await user_factory(
        email="login@example.com", hashed_password=hash_password(password)
    )

    svc = AuthService(db_session)
    tokens = await svc.login(UserLogin(email="login@example.com", password=password))

    assert tokens.access_token
    assert tokens.refresh_token
    assert tokens.access_token != tokens.refresh_token


async def test_login_rejects_wrong_password(db_session: AsyncSession, user_factory):
    await user_factory(
        email="wrong@example.com", hashed_password=hash_password("RealPass1!")
    )

    svc = AuthService(db_session)
    with pytest.raises(ValueError, match="Invalid email or password"):
        await svc.login(UserLogin(email="wrong@example.com", password="WrongPass1!"))


async def test_login_rejects_nonexistent_email(db_session: AsyncSession):
    svc = AuthService(db_session)
    with pytest.raises(ValueError, match="Invalid email or password"):
        await svc.login(UserLogin(email="nobody@example.com", password="Whatever1!"))


# ── Refresh ──────────────────────────────────────────────────────────


async def test_refresh_returns_new_tokens(db_session: AsyncSession, user_factory):
    user = await user_factory(email="refresh@example.com")

    svc = AuthService(db_session)
    # Login first to get a valid refresh token
    from app.core.security import create_refresh_token

    refresh_token = create_refresh_token(data={"sub": str(user.id)})

    tokens = await svc.refresh(refresh_token)

    assert tokens.access_token
    assert tokens.refresh_token


async def test_refresh_rejects_access_token_used_as_refresh(
    db_session: AsyncSession, user_factory
):
    await user_factory(email="badtype@example.com")

    svc = AuthService(db_session)
    from app.core.security import create_access_token

    # Pass an access token as refresh token
    access_token = create_access_token(
        data={"sub": "1", "email": "badtype@example.com", "role": "customer"}
    )

    with pytest.raises(ValueError, match="Invalid refresh token"):
        await svc.refresh(access_token)


async def test_refresh_rejects_expired_token(db_session: AsyncSession):
    """An expired refresh token should be caught as Invalid refresh token."""
    from datetime import timedelta

    from app.core.security import create_refresh_token

    # Create a token that's already expired
    expired = create_refresh_token(
        data={"sub": "1"}, expires_delta=timedelta(seconds=-1)
    )

    svc = AuthService(db_session)
    with pytest.raises(ValueError, match="Invalid refresh token"):
        await svc.refresh(expired)


async def test_refresh_rejects_deleted_user(db_session: AsyncSession, user_factory):
    """If the user was deleted after the token was issued, refresh should fail."""
    user = await user_factory(email="gone@example.com")

    from app.core.security import create_refresh_token

    token = create_refresh_token(data={"sub": str(user.id)})

    # Delete the user using the repository (proper async delete)
    from app.repositories.user_repository import UserRepository

    repo = UserRepository(db_session)
    await repo.delete(user)

    svc = AuthService(db_session)
    with pytest.raises(ValueError, match="User not found"):
        await svc.refresh(token)


async def test_refresh_rejects_token_missing_sub(db_session: AsyncSession):
    """A token without 'sub' claim should cause ValueError."""
    from app.core.security import create_refresh_token

    token = create_refresh_token(data={"email": "no-sub@test.com"})

    svc = AuthService(db_session)
    with pytest.raises(ValueError, match="Invalid refresh token"):
        await svc.refresh(token)


async def test_refresh_returns_valid_token_pair(db_session: AsyncSession, user_factory):
    """Refreshed tokens are valid and correctly typed."""
    user = await user_factory(email="rotate@example.com")

    from app.core.security import create_refresh_token, decode_token

    token1 = create_refresh_token(data={"sub": str(user.id)})

    svc = AuthService(db_session)
    pair = await svc.refresh(token1)

    # Decode and verify the tokens
    access_payload = decode_token(pair.access_token)
    refresh_payload = decode_token(pair.refresh_token)

    assert access_payload["type"] == "access"
    assert refresh_payload["type"] == "refresh"
    assert access_payload["sub"] == str(user.id)
    assert refresh_payload["sub"] == str(user.id)
    assert access_payload["email"] == "rotate@example.com"
