"""Signing in with a link sent by email, instead of a password.

The whole life of a link is in this file:

  issue    A random token: 32 bytes from the operating system's secure
           generator, far past anything guessable. Only its SHA-256 hash is
           stored, with an expiry MAGIC_LINK_TTL_SECONDS away (24 hours).
           Any link the person still holds is retired at the same moment, so
           only the newest ever works.

  email    https://portal.alokindia.co.in/#sign-in=<token>, sent through
           the same sender and the same safety switches as order
           notifications. The token sits after the "#", which a browser
           never sends to a server, so it cannot turn up in a web server's
           access log or be passed on in a Referer header.

  redeem   Two behaviours, chosen by MAGIC_LINK_SINGLE_USE.

           Reusable, the default since 12 Sep 2026: a plain lookup. The link
           keeps working until it expires, however many times it is opened.
           Alok asked for this so a link cannot be used up before the
           customer gets to it, and accepted that it means a 24-hour
           reusable credential sitting in an inbox.

           Single use, MAGIC_LINK_SINGLE_USE=true: one UPDATE that marks the
           link used ONLY IF it is still unused and unexpired. Two clicks
           racing each other cannot both win, because the database lets
           exactly one of them change the row, and the link is spent even if
           the account then turns out to be refused.

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

from app.core import config
from app.core.config import PORTAL_URL, SMTP_FROM
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
    """How long a link works, in whole minutes."""
    return max(1, config.MAGIC_LINK_TTL_SECONDS // 60)


def validity_in_words() -> str:
    """How long a link works, written the way the email should say it.

    "1440 minutes" is a true answer and a useless one. Hours once there are
    hours of it, a day once there is a day.
    """
    minutes = minutes_valid()
    if minutes < 60:
        return "1 minute" if minutes == 1 else f"{minutes} minutes"
    hours, spare_minutes = divmod(minutes, 60)
    if hours < 24 or spare_minutes:
        return "1 hour" if hours == 1 else f"{hours} hours"
    days, spare_hours = divmod(hours, 24)
    if days == 1 and not spare_hours:
        return "24 hours"
    return f"{days} days"


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
            expires_at=now + timedelta(seconds=config.MAGIC_LINK_TTL_SECONDS),
        )
    )
    session.commit()
    return token


def link_for(token: str) -> str:
    """The address that goes in the email."""
    return f"{PORTAL_URL.rstrip('/')}/#sign-in={token}"


def _how_long_it_lasts() -> list[str]:
    """The lines of the email that say how long the link works, and how often.

    Two settings, two honest descriptions. Telling somebody a link "works
    once" when it no longer does would train them to ask for a new one they
    do not need; the reverse would be worse.
    """
    lasts = validity_in_words()
    if config.MAGIC_LINK_SINGLE_USE:
        return [
            f"It works once, and only for the next {lasts}. After that,",
            "ask for a new one on the sign-in page.",
        ]
    return [
        f"It works for the next {lasts}, and you can use it more than once in",
        "that time. After that, ask for a new one on the sign-in page.",
        "",
        "Until then, please keep this email to yourself: anybody who can read",
        "it can sign in as you. Asking for a new link stops this one working.",
    ]


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
        *_how_long_it_lasts(),
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

    if config.MAGIC_LINK_SINGLE_USE:
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
        # Committed before anything else is checked, so the link is spent
        # even if the account is refused below.
        session.commit()
    else:
        # Reusable: look, do not spend. `used_at` still means "this link is
        # finished", and issue() still sets it on every older link, so asking
        # for a new link retires the one before it exactly as it always did.
        # The only thing that has changed is that redeeming no longer sets it.
        spent = session.execute(
            select(MagicLink.user_id, MagicLink.created_at).where(
                MagicLink.token_hash == hash_token(token),
                MagicLink.used_at.is_(None),
                MagicLink.expires_at > now,
            )
        ).first()

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
