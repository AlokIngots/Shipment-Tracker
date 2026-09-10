"""Password hashing and sign-in tokens.

Standard library only, on purpose: no extra packages to install, nothing to
break on a Python upgrade.

Passwords  : PBKDF2-HMAC-SHA256, 240,000 iterations, 16-byte random salt per
             user. Stored as "pbkdf2_sha256$<iterations>$<salt>$<hash>".
Tokens     : "<payload>.<signature>" where payload is base64 JSON holding the
             user id, when it was issued and when it expires, signed with
             HMAC-SHA256 using SECRET_KEY.
             Nothing secret is inside the token and it cannot be altered
             without invalidating the signature. Stateless, so the server
             keeps no session table.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time

from app.core.config import SECRET_KEY, TOKEN_TTL_SECONDS

_ALGORITHM = "pbkdf2_sha256"
_ITERATIONS = 240_000

# The shortest password the portal will accept. Length is what protects a
# password, which is why there are no rules about punctuation below.
PASSWORD_MIN_LENGTH = 8

# No 0/O, no 1/l/I. A customer being read their password down a bad line
# should not have to ask which character it was.
_UNAMBIGUOUS = "abcdefghjkmnpqrstuvwxyz23456789"


# ---------------------------------------------------------------- passwords


def hash_password(password: str) -> str:
    """Hash a plain password for storage."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"{_ALGORITHM}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def temporary_password() -> str:
    """A one-off password for a new account, e.g. "kfrn-8mqx-2wtd".

    Grouped in fours because that is how a person reads a code aloud without
    losing their place.
    """
    raw = "".join(secrets.choice(_UNAMBIGUOUS) for _ in range(12))
    return "-".join(raw[i:i + 4] for i in range(0, 12, 4))


def password_problem(password: str) -> str | None:
    """Say what is wrong with a chosen password, in words a customer reads.

    Returns None if it is acceptable. Deliberately short: length is what
    actually protects a password, and rules about punctuation mostly teach
    people to write Password1! and reuse it everywhere.
    """
    if password != password.strip():
        return "Your password cannot start or end with a space."
    if len(password) < PASSWORD_MIN_LENGTH:
        return (
            f"Your password must be at least {PASSWORD_MIN_LENGTH} characters "
            "long."
        )
    if len(set(password)) < 5:
        return "Your password repeats too few different characters."
    return None


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


def create_token(user_id: int, issued_at: int | None = None) -> str:
    """Issue a signed token for a user.

    "iat" is when it was issued. Because a token cannot be taken back once
    handed out, that timestamp is how changing a password retires the tokens
    that existed before it: see get_current_user in app/core/deps.py.

    `issued_at` overrides the clock. Exactly one caller needs it: the
    password change, which must hand back a token that is unambiguously
    NEWER than the change it just made. Both timestamps are whole seconds,
    so a replacement stamped from the clock could land on the very same
    second as the change and be indistinguishable from a token issued a
    moment before it.
    """
    issued = int(time.time()) if issued_at is None else int(issued_at)
    body = {"uid": user_id, "iat": issued, "exp": issued + TOKEN_TTL_SECONDS}
    payload = _b64encode(json.dumps(body, separators=(",", ":")).encode())
    return f"{payload}.{_sign(payload)}"


def read_token(token: str) -> dict | None:
    """Return the contents of a valid, unexpired token, else None.

    The caller gets {"uid": ..., "iat": ...}. Nothing in here is trusted
    until the signature has been checked, which is the first thing done.
    """
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

    # Tokens issued before "iat" existed have no business being accepted
    # now: treat a missing one as the beginning of time, which every
    # password change is later than.
    return {"uid": body["uid"], "iat": int(body.get("iat", 0))}
