"""Password hashing and sign-in tokens.

Standard library only, on purpose: no extra packages to install, nothing to
break on a Python upgrade.

Passwords  : PBKDF2-HMAC-SHA256, 240,000 iterations, 16-byte random salt per
             user. Stored as "pbkdf2_sha256$<iterations>$<salt>$<hash>".
Tokens     : "<payload>.<signature>" where payload is base64 JSON holding the
             user id and an expiry, signed with HMAC-SHA256 using SECRET_KEY.
             Nothing secret is inside the token and it cannot be altered
             without invalidating the signature. Stateless, so the server
             keeps no session table.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY or len(SECRET_KEY) < 32:
    raise RuntimeError(
        "SECRET_KEY must be set in .env and at least 32 characters long. "
        "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
    )

TOKEN_TTL_SECONDS = int(os.getenv("TOKEN_TTL_SECONDS", "43200"))  # 12 hours

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 240_000


# ---------------------------------------------------------------- passwords


def hash_password(password: str) -> str:
    """Hash a plain password for storage."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"{_ALGORITHM}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Check a plain password against a stored hash."""
    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$")
        if algorithm != _ALGORITHM:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations)
        )
    except (ValueError, AttributeError):
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


# ------------------------------------------------------------------- tokens


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload: str) -> str:
    signature = hmac.new(
        SECRET_KEY.encode(), payload.encode(), hashlib.sha256
    ).digest()
    return _b64encode(signature)


def create_token(user_id: int) -> str:
    """Issue a signed token for a user."""
    body = {"uid": user_id, "exp": int(time.time()) + TOKEN_TTL_SECONDS}
    payload = _b64encode(json.dumps(body, separators=(",", ":")).encode())
    return f"{payload}.{_sign(payload)}"


def read_token(token: str) -> int | None:
    """Return the user id inside a valid, unexpired token, else None."""
    try:
        payload, signature = token.split(".", 1)
    except (ValueError, AttributeError):
        return None

    if not hmac.compare_digest(signature, _sign(payload)):
        return None

    try:
        body = json.loads(_b64decode(payload))
    except (ValueError, json.JSONDecodeError):
        return None

    if not isinstance(body.get("uid"), int):
        return None
    if body.get("exp", 0) < time.time():
        return None

    return body["uid"]
