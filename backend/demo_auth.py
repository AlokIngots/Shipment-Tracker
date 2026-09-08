"""Temporary demo authentication.

THROWAWAY CODE — replace before this portal goes anywhere near a customer.

There is exactly one demo account. Its email and password are read from
.env, which is never committed, so no credentials live in the repository.
The token is a random opaque string held in memory, so every restart
invalidates all sessions. This is deliberately kept in its own module so
that swapping in real customer accounts (hashed passwords in the database,
proper JWTs, expiry, refresh) means replacing this file rather than
untangling it from the API.
"""

import hmac
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

# .env lives at the project root, one level above backend/
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DEMO_EMAIL = os.getenv("DEMO_LOGIN_EMAIL", "").strip().lower()
DEMO_PASSWORD = os.getenv("DEMO_LOGIN_PASSWORD", "")

if not DEMO_EMAIL or not DEMO_PASSWORD:
    raise RuntimeError(
        "DEMO_LOGIN_EMAIL and DEMO_LOGIN_PASSWORD must be set. "
        "Copy .env.example to .env and fill them in."
    )

# token -> email. In-memory only; cleared on restart.
_ISSUED_TOKENS: dict[str, str] = {}


def check_credentials(email: str, password: str) -> bool:
    """Return True if the supplied credentials match the demo account."""
    email_ok = hmac.compare_digest(email.strip().lower(), DEMO_EMAIL)
    password_ok = hmac.compare_digest(password, DEMO_PASSWORD)
    # Both comparisons always run so failures take the same time either way.
    return email_ok and password_ok


def issue_token(email: str) -> str:
    """Create and remember an opaque token for the given email."""
    token = secrets.token_urlsafe(32)
    _ISSUED_TOKENS[token] = email.strip().lower()
    return token


def email_for_token(token: str) -> str | None:
    """Return the email a token was issued to, or None if it is unknown."""
    return _ISSUED_TOKENS.get(token)
