"""Who is asking, and may they.

Every route in the portal depends on one of the four types at the bottom of
this file, and the difference between them is the whole access-control story:

    DbSession    — a database session, and nothing about the caller
    CurrentUser  — signed in; may still be on a temporary password
    SettledUser  — signed in, has chosen their own password, is a customer
    StaffUser    — signed in, has chosen their own password, is Alok Ingots

Keeping them in one small file means the rules can be read in one sitting,
rather than being inferred from whichever route happens to be on screen.
"""

from typing import Annotated, Iterator

from app.core import security
from app.core.database import SessionLocal
from fastapi import Depends, Header, HTTPException, status
from app.models import User
from sqlalchemy.orm import Session


def get_db() -> Iterator[Session]:
    """Yield a database session and always close it afterwards."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


DbSession = Annotated[Session, Depends(get_db)]

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not signed in.",
    headers={"WWW-Authenticate": "Bearer"},
)

MUST_CHANGE_PASSWORD_ERROR = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Please set your own password before continuing.",
)


def get_current_user(
    db: DbSession,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Resolve the signed-in user from the Authorization header.

    Raises 401 if the header is missing, malformed, expired, or points at a
    user who no longer exists or has been deactivated.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise CREDENTIALS_ERROR

    token = security.read_token(authorization.split(" ", 1)[1].strip())
    if token is None:
        raise CREDENTIALS_ERROR

    user = db.get(User, token["uid"])
    if user is None or not user.is_active:
        raise CREDENTIALS_ERROR

    # A token handed out before the password was last changed is finished.
    # This is what makes changing a password mean something: whoever else
    # was signed in with the old one is signed out by it, including on a
    # computer nobody has access to any more.
    if user.password_changed_at and token["iat"] < user.password_changed_at.timestamp():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your password was changed. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_staff_user(current_user: CurrentUser) -> User:
    """An Alok Ingots staff member. Everything under /api/staff needs this.

    Staff are told apart from customers by a flag on their account, which
    only manage_users.py on the server can set. There is no way to become
    staff through the portal.
    """
    if not current_user.is_staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This is only for Alok Ingots staff.",
        )
    if current_user.must_change_password:
        raise MUST_CHANGE_PASSWORD_ERROR
    return current_user


StaffUser = Annotated[User, Depends(get_staff_user)]


def get_settled_user(current_user: CurrentUser) -> User:
    """A signed-in customer who is no longer on a temporary password.

    Everything that shows a customer their data depends on this rather than
    on get_current_user, so the change cannot be skipped by talking to the
    API directly instead of using the website.
    """
    if current_user.must_change_password:
        raise MUST_CHANGE_PASSWORD_ERROR
    if current_user.is_staff or current_user.customer_id is None:
        # Staff belong to no customer, so there are no orders that are
        # "theirs". Saying so plainly beats returning an empty list and
        # letting them wonder where the orders went.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Staff accounts do not have their own orders.",
        )
    return current_user


SettledUser = Annotated[User, Depends(get_settled_user)]


def bad_request(message: str) -> HTTPException:
    """A refusal written for the person filling in the form, not for a log."""
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


def not_found(message: str) -> HTTPException:
    """Not there — or not yours, which the caller is never told apart."""
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)
