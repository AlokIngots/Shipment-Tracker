"""Signing in, checking a remembered token, and changing a password."""

from datetime import datetime, timezone

from app.core import security
from app.core.deps import ClientAddress, CurrentUser, DbSession
from fastapi import APIRouter, HTTPException, status
from app.models import Customer, User
from app.schemas import ChangePasswordRequest, CustomerOut, LoginRequest, LoginResponse
from app.services import ratelimit
from sqlalchemy import select

router = APIRouter()


@router.get("/api/health")
def health() -> dict[str, str]:
    """Liveness probe used to confirm the API is up. Open to everyone."""
    return {"status": "ok"}


@router.post("/api/login", response_model=LoginResponse)
def login(
    credentials: LoginRequest, db: DbSession, address: ClientAddress
) -> LoginResponse:
    """Sign in against the users table and return a signed token."""
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

    customer = db.get(Customer, user.customer_id) if user.customer_id else None
    return LoginResponse(
        token=security.create_token(user.id),
        email=user.email,
        full_name=user.full_name,
        customer=CustomerOut.model_validate(customer) if customer else None,
        must_change_password=user.must_change_password,
        is_staff=user.is_staff,
    )


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
        "must_change_password": current_user.must_change_password,
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

    current_user.password_hash = security.hash_password(body.new_password)
    current_user.must_change_password = False
    # Whole seconds, because a token's "iat" is whole seconds too. Keeping
    # the microseconds would make the replacement token below look older
    # than the change that produced it, and sign the user straight out.
    current_user.password_changed_at = datetime.now(timezone.utc).replace(microsecond=0)
    db.commit()

    # Every token issued before now has just stopped working, including the
    # one used to make this request. Hand back a new one so the person who
    # changed the password stays signed in and everybody else does not.
    return {
        "detail": "Your password has been changed.",
        "token": security.create_token(current_user.id),
    }
