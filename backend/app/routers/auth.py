"""Signing in, checking a remembered token, and changing a password.

The portal signs people in with a link sent by email: POST /api/magic-link
to ask for one and POST /api/magic-link/redeem to spend it.

An email and a password, POST /api/login, is the older way in. It is kept
but dormant: while PASSWORD_SIGN_IN is off, which is how the portal ships,
it refuses everybody before looking anything up. Switched on, it works
exactly as it did, and both ways end in the same place.

None of these change a customer's data. What they write is sign-in
bookkeeping -- a link issued, a link spent -- which is why they may sit
outside /api/staff without breaking the read-only rule.
"""

from datetime import datetime, timezone

from app.core import config, security
from app.core.deps import ClientAddress, CurrentUser, DbSession, must_choose_password
from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from app.models import Customer, User
from app.schemas import (
    ChangePasswordRequest,
    CustomerOut,
    LoginRequest,
    LoginResponse,
    MagicLinkRedeem,
    MagicLinkRequest,
)
from app.services import audit, magic_links, ratelimit
from sqlalchemy import select

router = APIRouter()

LINK_EXPIRED = "This link has expired, please request a new one."

PASSWORD_SIGN_IN_OFF = (
    "Signing in with a password is switched off. Enter your email address "
    "and press Sign in with email link."
)


def signed_in(user: User, db) -> LoginResponse:
    """What a successful sign-in returns, however the person proved who they are."""
    customer = db.get(Customer, user.customer_id) if user.customer_id else None
    return LoginResponse(
        token=security.create_token(user.id),
        email=user.email,
        full_name=user.full_name,
        customer=CustomerOut.model_validate(customer) if customer else None,
        must_change_password=must_choose_password(user),
        is_staff=user.is_staff,
    )


@router.get("/api/health")
def health() -> dict[str, str]:
    """Liveness probe used to confirm the API is up. Open to everyone."""
    return {"status": "ok"}


@router.post("/api/login", response_model=LoginResponse)
def login(
    credentials: LoginRequest, db: DbSession, address: ClientAddress
) -> LoginResponse:
    """Sign in against the users table and return a signed token.

    Dormant while PASSWORD_SIGN_IN is off: refused before the rate limiter,
    the users table or the password is looked at, so the answer is the same
    for every email and every password and says nothing about either.
    """
    if not config.PASSWORD_SIGN_IN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=PASSWORD_SIGN_IN_OFF
        )

    email = credentials.email.strip().lower()

    # Checked before the password is even looked at, and checked the same
    # way for an email that exists and one that does not -- otherwise the
    # limiter itself would answer the question "is this a real account?".
    for limiter, key in ((ratelimit.by_email_and_address, f"{email}|{address}"),
                         (ratelimit.by_address, address)):
        try:
            limiter.check(key)
        except ratelimit.TooManyAttempts as blocked:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "Too many sign-in attempts. Please wait a few minutes and "
                    "try again. If you have forgotten your password, ask Alok "
                    "Ingots to reset it."
                ),
                headers={"Retry-After": str(blocked.retry_after)},
            ) from blocked

    user = db.scalar(select(User).where(User.email == email))

    # Always run a hash comparison, even when the email is unknown, so a
    # wrong email and a wrong password take the same time to answer.
    stored = user.password_hash if user else security.hash_password("dummy")
    password_ok = security.verify_password(credentials.password, stored)

    if not user or not password_ok or not user.is_active:
        # A deactivated account counts too: it is still a wrong answer, and
        # not counting it would leave a way to guess without limit.
        ratelimit.by_email_and_address.record_failure(f"{email}|{address}")
        ratelimit.by_address.record_failure(address)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect.",
        )

    # Signed in, so this pairing starts again. The address keeps its own
    # count: one good password does not excuse nineteen bad ones.
    ratelimit.by_email_and_address.clear(f"{email}|{address}")

    return signed_in(user, db)


@router.post("/api/magic-link", status_code=status.HTTP_202_ACCEPTED)
def request_magic_link(
    body: MagicLinkRequest,
    db: DbSession,
    address: ClientAddress,
    background: BackgroundTasks,
) -> dict[str, str]:
    """Email a sign-in link, if the address has an account.

    The answer is identical whether it does or not, word for word and status
    for status. Every request is counted twice -- per address and per inbox,
    see MAGIC_LINK_* in app/core/config.py.
    """
    email = (body.email or "").strip().lower()
    if "@" not in email:
        # Says nothing about any account: it is not an address at all.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please enter your email address.",
        )

    # One network asking for links to many inboxes: refused outright.
    try:
        ratelimit.magic_link_by_address.check(address)
    except ratelimit.TooManyAttempts as blocked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Too many sign-in links have been asked for from your network. "
                "Please wait a few minutes and try again."
            ),
            headers={"Retry-After": str(blocked.retry_after)},
        ) from blocked
    ratelimit.magic_link_by_address.record_attempt(address)

    answer = {
        "detail": (
            "Check your email. If that address has an account with the portal, "
            "a sign-in link is on its way. It works once, within "
            f"{magic_links.minutes_valid()} minutes."
        )
    }

    # One inbox already sent as many links as it is allowed: the same
    # answer, and nothing sent. A 429 here would tell a stranger that this
    # address is being asked about -- and the links already sent still work.
    try:
        ratelimit.magic_link_by_email.check(email)
    except ratelimit.TooManyAttempts:
        return answer
    ratelimit.magic_link_by_email.record_attempt(email)

    user = magic_links.find_account(db, email)
    if user is not None:
        token = magic_links.issue(db, user)
        # Sent after the answer has gone, so an address with an account does
        # not take visibly longer to answer than one without.
        background.add_task(
            magic_links.send, user.email, user.full_name, magic_links.link_for(token)
        )

    return answer


@router.post("/api/magic-link/redeem", response_model=LoginResponse)
def redeem_magic_link(
    body: MagicLinkRedeem, db: DbSession, address: ClientAddress
) -> LoginResponse:
    """Spend a sign-in link and sign its owner in. It never works a second time.

    Bad links count against the same per-address budget as bad passwords, so
    trying tokens at random is slowed to a stop -- not that 256 random bits
    leave anything to find.
    """
    try:
        ratelimit.by_address.check(address)
    except ratelimit.TooManyAttempts as blocked:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many sign-in attempts. Please wait a few minutes and try again.",
            headers={"Retry-After": str(blocked.retry_after)},
        ) from blocked

    user = magic_links.redeem(db, body.token)
    if user is None:
        ratelimit.by_address.record_failure(address)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=LINK_EXPIRED)

    return signed_in(user, db)


@router.get("/api/me", response_model=LoginResponse | dict)
def me(current_user: CurrentUser, db: DbSession) -> dict:
    """Who am I? Used by the frontend to confirm a stored token is still good."""
    customer = (
        db.get(Customer, current_user.customer_id)
        if current_user.customer_id
        else None
    )
    return {
        "email": current_user.email,
        "full_name": current_user.full_name,
        "customer": (
            CustomerOut.model_validate(customer).model_dump() if customer else None
        ),
        "must_change_password": must_choose_password(current_user),
        "is_staff": current_user.is_staff,
    }


@router.post("/api/change-password")
def change_password(
    body: ChangePasswordRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> dict[str, str]:
    """Let a signed-in user replace their own password.

    Deliberately depends on CurrentUser and not SettledUser: someone on a
    temporary password has to be able to reach this one endpoint, and only
    this one.
    """
    if not security.verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your current password is not correct.",
        )

    if body.new_password == body.current_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your new password must be different from the current one.",
        )

    problem = security.password_problem(body.new_password)
    if problem:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=problem)

    was_temporary = current_user.must_change_password
    current_user.password_hash = security.hash_password(body.new_password)
    current_user.must_change_password = False
    # Whole seconds, because a token's "iat" is whole seconds too. Keeping
    # the microseconds would make the replacement token below look older
    # than the change that produced it, and sign the user straight out.
    current_user.password_changed_at = datetime.now(timezone.utc).replace(microsecond=0)
    # That it happened, and never what it was changed to.
    audit.record(
        db,
        "password.changed",
        f"{current_user.email} replaced their temporary password"
        if was_temporary
        else f"{current_user.email} changed their password",
        actor=current_user,
    )
    db.commit()

    # Every token issued before now has just stopped working, including the
    # one used to make this request. Hand back a new one so the person who
    # changed the password stays signed in and everybody else does not.
    return {
        "detail": "Your password has been changed.",
        # One second after the change, so it survives the check that retires
        # every other token. Anything stamped at or before the change is now
        # refused, and without this the replacement would be too.
        "token": security.create_token(
            current_user.id,
            issued_at=int(current_user.password_changed_at.timestamp()) + 1,
        ),
    }
