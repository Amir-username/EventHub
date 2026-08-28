import logging
import os
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

logger = logging.getLogger(__name__)

ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


# Module-level cache so keys are loaded/generated once per process
_private_key: bytes | None = None
_public_key: bytes | None = None


def hash_password(plain: str) -> str:
    return ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        ph.verify(hashed, plain)
        return True
    except VerifyMismatchError:
        return False


def needs_rehash(hashed: str) -> bool:
    return ph.check_needs_rehash(hashed)


def _generate_keypair() -> tuple[bytes, bytes]:
    """Generate an RSA-2048 key pair and return (private_pem, public_pem)."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem


def _ensure_keys_dir(path: str) -> None:
    """Create the parent directory of *path* if it does not exist."""
    os.makedirs(os.path.dirname(path), exist_ok=True)


def _load_private_key() -> bytes:
    global _private_key
    if _private_key is not None:
        return _private_key

    # 1. Try env var (e.g. Docker secrets)
    from app.config import get_settings

    settings = get_settings()
    if settings.rsa_private_key:
        _private_key = settings.rsa_private_key.encode()
        return _private_key

    # 2. Try file path from settings
    path = settings.rsa_private_key_path
    if os.path.isfile(path):
        with open(path, "rb") as f:
            _private_key = f.read()
        return _private_key

    # 3. Auto-generate and persist (useful for local dev & tests)
    _ensure_keys_dir(path)
    private_pem, public_pem = _generate_keypair()
    with open(path, "wb") as f:
        f.write(private_pem)
    public_path = settings.rsa_public_key_path
    _ensure_keys_dir(public_path)
    with open(public_path, "wb") as f:
        f.write(public_pem)
    logger.warning(
        "RSA key pair auto-generated and saved to %s / %s", path, public_path
    )
    _private_key = private_pem
    return _private_key


def _load_public_key() -> bytes:
    global _public_key
    if _public_key is not None:
        return _public_key

    from app.config import get_settings

    settings = get_settings()
    if settings.rsa_public_key:
        _public_key = settings.rsa_public_key.encode()
        return _public_key

    path = settings.rsa_public_key_path
    if os.path.isfile(path):
        with open(path, "rb") as f:
            _public_key = f.read()
        return _public_key

    # Private-key loader may have auto-generated both files; try again
    # after triggering it.
    _load_private_key()
    if os.path.isfile(path):
        with open(path, "rb") as f:
            _public_key = f.read()
        return _public_key

    raise RuntimeError(
        f"RSA public key not found and could not be auto-generated. Expected at: {path}"
    )


def create_access_token(
    data: dict[str, Any], expires_delta: timedelta | None = None
) -> str:
    to_encode = data.copy()
    to_encode["type"] = "access"
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=30))
    to_encode.update({"exp": expire, "iat": datetime.now(UTC)})
    return jwt.encode(to_encode, _load_private_key(), algorithm="RS256")


def create_refresh_token(
    data: dict[str, Any], expires_delta: timedelta | None = None
) -> str:
    to_encode = data.copy()
    to_encode["type"] = "refresh"
    expire = datetime.now(UTC) + (expires_delta or timedelta(days=4))
    to_encode.update({"exp": expire, "iat": datetime.now(UTC)})
    return jwt.encode(to_encode, _load_private_key(), algorithm="RS256")


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, _load_public_key(), algorithms=["RS256"])
