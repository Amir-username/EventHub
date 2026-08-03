from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.config import Settings, get_settings

ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(plain: str) -> str:
    """Hash a plain-text password. Returns the encoded hash string."""
    return ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plain-text password against a stored Argon2 hash."""
    try:
        ph.verify(hashed, plain)
        return True
    except VerifyMismatchError:
        return False


def needs_rehash(hashed: str) -> bool:
    """Check if the hash parameters have been upgraded."""
    return ph.check_needs_rehash(hashed)


def create_access_token(
    data: dict[str, Any],
    settings: Settings | None = None,
) -> str:
    """Create a JWT access token (RS256)."""
    if settings is None:
        settings = get_settings()

    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    to_encode.update({"exp": expire, "iat": datetime.now(UTC)})

    # Load private key from settings or file
    private_key = settings.rsa_private_key or _load_private_key_from_file()
    return jwt.encode(to_encode, private_key, algorithm="RS256")


def decode_access_token(
    token: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Decode and verify a JWT access token."""
    if settings is None:
        settings = get_settings()

    public_key = settings.rsa_public_key or _load_public_key_from_file()
    return jwt.decode(token, public_key, algorithms=["RS256"])


def _load_private_key_from_file() -> bytes:
    with open("private_key.pem", "rb") as f:
        return f.read()


def _load_public_key_from_file() -> bytes:
    with open("public_key.pem", "rb") as f:
        return f.read()
