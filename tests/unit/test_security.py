"""Unit tests for core/security.py — password hashing and JWT tokens.

These are pure functions with no DB dependency, so they run fast
and require no fixtures.
"""

from datetime import timedelta

import jwt
import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    needs_rehash,
    verify_password,
)

# ── Password Hashing ─────────────────────────────────────────────────


async def test_hash_password_returns_argon2_hash():
    hashed = hash_password("Secret123!")
    assert hashed != "Secret123!"
    assert hashed.startswith("$argon2")


async def test_verify_password_correct():
    hashed = hash_password("Secret123!")
    assert verify_password("Secret123!", hashed) is True


async def test_verify_password_wrong():
    hashed = hash_password("Secret123!")
    assert verify_password("WrongPass999", hashed) is False


async def test_verify_password_different_hash_always_fails():
    """A hash of password A never verifies password B."""
    hash_a = hash_password("PasswordA!")
    hash_b = hash_password("PasswordB!")
    assert verify_password("PasswordB!", hash_a) is False
    assert verify_password("PasswordA!", hash_b) is False


async def test_needs_rehash_fresh_hash_is_false():
    """A freshly hashed password should not need rehashing."""
    hashed = hash_password("Secret123!")
    assert needs_rehash(hashed) is False


# ── JWT Token Creation ────────────────────────────────────────────────


async def test_create_access_token_has_access_type():
    token = create_access_token(data={"sub": "42", "email": "a@b.com"})
    payload = decode_token(token)
    assert payload["type"] == "access"
    assert payload["sub"] == "42"
    assert payload["email"] == "a@b.com"
    assert "exp" in payload
    assert "iat" in payload


async def test_create_refresh_token_has_refresh_type():
    token = create_refresh_token(data={"sub": "42"})
    payload = decode_token(token)
    assert payload["type"] == "refresh"
    assert payload["sub"] == "42"
    assert "exp" in payload


async def test_access_and_refresh_tokens_differ():
    access = create_access_token(data={"sub": "1"})
    refresh = create_refresh_token(data={"sub": "1"})
    assert access != refresh


async def test_create_access_token_custom_expiry():
    short = timedelta(seconds=1)
    token = create_access_token(data={"sub": "1"}, expires_delta=short)
    # Should be valid now
    payload = decode_token(token)
    assert payload["sub"] == "1"


async def test_decode_expired_token_raises():
    """An expired token should raise jwt.ExpiredSignatureError."""
    past = timedelta(seconds=-1)
    token = create_access_token(data={"sub": "1"}, expires_delta=past)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_token(token)


async def test_decode_tampered_token_raises():
    """Changing a character in the payload should break the signature."""
    token = create_access_token(data={"sub": "1"})
    # Flip a character in the payload section (after the first dot)
    parts = token.split(".")
    payload_part = parts[1]
    tampered_payload = (
        "A" + payload_part[1:] if payload_part[0] != "A" else "B" + payload_part[1:]
    )
    tampered = f"{parts[0]}.{tampered_payload}.{parts[2]}"
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(tampered)


async def test_decode_token_preserves_extra_claims():
    token = create_access_token(
        data={"sub": "5", "email": "x@y.com", "role": "admin", "custom": "val"}
    )
    payload = decode_token(token)
    assert payload["email"] == "x@y.com"
    assert payload["role"] == "admin"
    assert payload["custom"] == "val"
