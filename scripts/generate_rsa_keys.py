#!/usr/bin/env python3
import subprocess
from datetime import UTC, datetime, timedelta

import jwt
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

PRIVATE_PEM = "private_key.pem"
PUBLIC_PEM = "public_key.pem"


def generate_via_openssl_cli():
    """Generate keypair using the OpenSSL binary (must be installed)."""
    subprocess.run(["openssl", "genrsa", "-out", PRIVATE_PEM, "2048"], check=True)
    subprocess.run(
        ["openssl", "rsa", "-in", PRIVATE_PEM, "-pubout", "-out", PUBLIC_PEM],
        check=True,
    )
    print(f"Keys written: {PRIVATE_PEM}, {PUBLIC_PEM}")


def generate_via_cryptography():
    """Generate keypair using the cryptography library (OpenSSL-backed, no CLI needed)."""
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )

    with open(PRIVATE_PEM, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
        )

    with open(PUBLIC_PEM, "wb") as f:
        f.write(
            private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        )
    print(f"Keys written: {PRIVATE_PEM}, {PUBLIC_PEM}")


def load_keys():
    with open(PRIVATE_PEM, "rb") as f:
        private = f.read()
    with open(PUBLIC_PEM, "rb") as f:
        public = f.read()
    return private, public


def sign_token(private_key: bytes) -> str:
    payload = {
        "sub": "user-42",
        "email": "amir@eventhub.dev",
        "role": "admin",
        "iat": datetime.now(UTC),
        "exp": datetime.now(UTC) + timedelta(minutes=30),
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


def verify_token(token: str, public_key: bytes):
    try:
        return jwt.decode(token, public_key, algorithms=["RS256"])
    except jwt.ExpiredSignatureError:
        return "EXPIRED"
    except jwt.InvalidTokenError as e:
        return f"INVALID: {e}"


if __name__ == "__main__":
    # Pick one:
    # generate_via_openssl_cli()
    generate_via_cryptography()

    private_key, public_key = load_keys()

    token = sign_token(private_key)
    print(f"\nToken:\n{token}\n")

    decoded = verify_token(token, public_key)
    print(f"Verified payload:\n{decoded}\n")

    # Tamper test
    bad = token[:-20] + "X" * 20
    print(f"Tampered result: {verify_token(bad, public_key)}")
