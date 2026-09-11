"""Signing in with a link sent by email, instead of a password.

The whole life of a link is in this file:

  issue    A random token: 32 bytes from the operating system's secure
           generator, far past anything guessable. Only its SHA-256 hash is
           stored, with an expiry MAGIC_LINK_TTL_SECONDS away (15 minutes).
           Any link the person still holds unused is retired at the same
           moment, so only the newest ever works.

  email    https://portal.alokindia.co.in/#sign-in=<token>, sent through
           the same sender and the same safety switches as order
           notifications. The token sits after the "#", which a browser
           never sends to a server, so it cannot turn up in a web server's
           access log or be passed on in a Referer header.

  redeem   One UPDATE that marks the link used ONLY IF it is still unused
           and unexpired, and hands back whose it was. Two clicks racing
           each other cannot both win: the database lets exactly one of them
           change the row. The link is spent even if the account then turns
           out to be refused.

A link is also refused if the account has been deactivated since, or its
password changed or reset since. A reset usually means "somebody should not
be signed in", and a link already sitting in an inbox must not survive it.

Nothing here knows about HTTP, and nothing here decides what to tell the
person asking. The router gives the same answer whether an address has an
account or not.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from sqlalchemy import select, update

from app.core.config import MAGIC_LINK_TTL_SECONDS, PORTAL_URL, SMTP_FROM
from app.models import MagicLink, User
from app.services import notifications

log = logging.getLogger("portal.magic_links")

# 32 bytes is 256 bits. secrets.token_urlsafe turns it into 43 characters
# that survive being put in a URL and an email untouched.
TOKEN_BYTES = 32

# A real token is 43 characters. Anything much longer is not one, and is
# refused before it is even hashed.
_LONGEST_TOKEN = 128

SUBJECT = "Your sign-in link for the Alok Ingots portal"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def minutes_valid() -> int:
    """How long a link works, in the minutes the email and the page quote."""
    return max(1, MAGIC_LINK_TTL_SECONDS // 60)


def find_account(session, email: str) -> User | None:
    """The active account an address belongs to -- customer or staff -- or None."""
    email = (email or "").strip().lower()
    if not email:
        return None
    return session.scalar(
        select(User).where(User.email == email, User.is_active.is_(True))
    )


def issue(session, user: User) -> str:
    """Create a link for somebody, retiring any they still hold.

    Returns the token, once, to be put in the email. It is not stored and
    cannot be recovered afterwards.
    """
    now = datetime.now(timezone.utc)
    session.execute(
        update(MagicLink)
        .where(MagicLink.user_id == user.id, MagicLink.used_at.is_(None))
        .values(used_at=now)
        .execution_options(synchronize_session=False)
    )
    token = secrets.token_urlsafe(TOKEN_BYTES)
    session.add(
        MagicLink(
            user_id=user.id,
            token_hash=hash_token(token),
            created_at=now,
            expires_at=now + timedelta(seconds=MAGIC_LINK_TTL_SECONDS),
        )
    )
    session.commit()
    return token


def link_for(token: str) -> str:
    """The address that goes in the email."""
    return f"{PORTAL_URL.rstrip('/')}/#sign-in={token}"


def build_message(email: str, full_name: str | None, url: str) -> EmailMessage:
    """The sign-in email. Plain text, like the order notifications."""
    greeting = (full_name or "").strip() or "Hello"
    lines = [
        f"{greeting},",
        "",
        "Somebody - hopefully you - asked to sign in to the Alok Ingots",
        f"customer portal as {email}. To sign in, open this link:",
        "",
        f"  {url}",
        "",
        f"It works once, and only for the next {minutes_valid()} minutes. After that,",
        "ask for a new one on the sign-in page, or sign in with your password.",
        "",
        "If you did not ask for this, you can ignore this email. Nobody can",
        "sign in without the link, and it stops working by itself.",
        "",
        "Alok Ingots",
        "Stainless steel bright bars, Mumbai, India",
    ]
    message = EmailMessage()
    message["Subject"] = SUBJECT
    message["From"] = SMTP_FROM
    message["To"] = email
    text = "\n".join(lines)
    try:
        # 7bit keeps the link on one unbroken line in the email as sent. Left
        # to choose, Python picks quoted-printable for any line over 78
        # characters -- which the link line always is -- and splits it with
        # a soft line break. Every real mail client joins it back together,
        # but the link is the one thing in this email that must survive
        # whatever reads it.
        message.set_content(text, cte="7bit")
    except (UnicodeError, ValueError):
        # A name with accents cannot travel as 7bit. Quoted-printable, then,
        # which mail clients decode correctly.
        message.set_content(text)
    return message


def send(email: str, full_name: str | None, url: str) -> str:
    """Email a link. Returns the outcome: "sent", "suppressed" or "failed".

    Runs after the answer has already gone back to the browser, so that an
    address with an account does not take noticeably longer to answer than
    one without -- and so it must never raise.

    The outcome is logged. The link never is: anybody able to read the
    server's logs must not be able to sign in as a customer.
    """
    outcome, detail = notifications.send(build_message(email, full_name, url))
    if outcome == "sent":
        log.info("sign-in link emailed to %s", email)
    else:
        log.warning("sign-in link for %s was not delivered (%s: %s)", email, outcome, detail)
    return outcome


def redeem(session, token: str) -> User | None:
    """Spend a link. Returns the account it signs in, or None.

    Every refusal is the same None -- unknown, already used, expired,
    replaced by a newer link, account deactivated, password changed since --
    because the person holding the link can do the same thing about all of
    them: ask for a new one.
    """
    if not token or len(token) > _LONGEST_TOKEN:
        return None

    now = datetime.now(timezone.utc)
    spent = session.execute(
        update(MagicLink)
        .where(
            MagicLink.token_hash == hash_token(token),
            MagicLink.used_at.is_(None),
            MagicLink.expires_at > now,
        )
        .values(used_at=now)
        .returning(MagicLink.user_id, MagicLink.created_at)
        .execution_options(synchronize_session=False)
    ).first()
    # Committed before anything else is checked, so the link is spent even
    # if the account is refused below.
    session.commit()

    if spent is None:
        return None

    user = session.get(User, spent.user_id)
    if user is None or not user.is_active:
        return None

    # A link sent before the password was last changed is finished, exactly
    # as a sign-in token is. Whole seconds and <=, for the reason given in
    # app/core/deps.py: password_changed_at is stored in whole seconds, and
    # comparing with < would let a link sent in the same second as a reset
    # quietly survive it.
    if (
        user.password_changed_at
        and spent.created_at.replace(microsecond=0) <= user.password_changed_at
    ):
        return None

    return user
