"""Alok Ingots Customer Portal — FastAPI backend.

Every order endpoint requires a valid sign-in token and only ever returns
data belonging to that user's own customer.
"""

from decimal import Decimal
from typing import Annotated, Iterator

import security
from database import SessionLocal
from fastapi import Depends, FastAPI, Header, HTTPException, status
from models import Customer, Order, User
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

app = FastAPI(
    title="Alok Ingots Customer Portal API",
    description="Backend API for the Alok Ingots export customer portal.",
    version="0.2.0",
)


# ------------------------------------------------------------- dependencies


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

    user_id = security.read_token(authorization.split(" ", 1)[1].strip())
    if user_id is None:
        raise CREDENTIALS_ERROR

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise CREDENTIALS_ERROR

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


# ----------------------------------------------------------------- schemas


class LoginRequest(BaseModel):
    """Credentials submitted by the login form."""

    email: str
    password: str


class CustomerOut(BaseModel):
    """The customer a signed-in user belongs to."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    country: str | None


class LoginResponse(BaseModel):
    """Returned on a successful sign-in."""

    token: str
    email: str
    full_name: str | None
    customer: CustomerOut


class OrderOut(BaseModel):
    """An order as returned to the portal frontend."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    sales_order_no: str
    customer_po: str | None
    grade: str | None
    description: str | None
    ordered_qty: Decimal | None
    unit: str | None
    status: str | None


# ------------------------------------------------------------------ routes


@app.get("/api/health")
def health() -> dict[str, str]:
    """Liveness probe used to confirm the API is up. Open to everyone."""
    return {"status": "ok"}


@app.post("/api/login", response_model=LoginResponse)
def login(credentials: LoginRequest, db: DbSession) -> LoginResponse:
    """Sign in against the users table and return a signed token."""
    email = credentials.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email))

    # Always run a hash comparison, even when the email is unknown, so a
    # wrong email and a wrong password take the same time to answer.
    stored = user.password_hash if user else security.hash_password("dummy")
    password_ok = security.verify_password(credentials.password, stored)

    if not user or not password_ok or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect.",
        )

    customer = db.get(Customer, user.customer_id)
    return LoginResponse(
        token=security.create_token(user.id),
        email=user.email,
        full_name=user.full_name,
        customer=CustomerOut.model_validate(customer),
    )


@app.get("/api/me", response_model=LoginResponse | dict)
def me(current_user: CurrentUser, db: DbSession) -> dict:
    """Who am I? Used by the frontend to confirm a stored token is still good."""
    customer = db.get(Customer, current_user.customer_id)
    return {
        "email": current_user.email,
        "full_name": current_user.full_name,
        "customer": CustomerOut.model_validate(customer).model_dump(),
    }


@app.get("/api/orders", response_model=list[OrderOut])
def list_orders(current_user: CurrentUser, db: DbSession) -> list[Order]:
    """Return the signed-in user's own orders, and nothing else.

    The customer filter comes from the token, never from the request, so a
    user cannot ask for another customer's orders.
    """
    return list(
        db.scalars(
            select(Order)
            .where(Order.customer_id == current_user.customer_id)
            .order_by(Order.id)
        )
    )
