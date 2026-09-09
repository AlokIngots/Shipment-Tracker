"""Alok Ingots Customer Portal — FastAPI backend.

Every order endpoint requires a valid sign-in token and only ever returns
data belonging to that user's own customer.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Annotated, Iterator

import security
import storage
import tracking
from database import SessionLocal
from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import FileResponse
from models import Customer, Document, Order, Shipment, User
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import selectinload
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


MUST_CHANGE_PASSWORD_ERROR = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Please set your own password before continuing.",
)


def get_settled_user(current_user: CurrentUser) -> User:
    """A signed-in user who is no longer on a temporary password.

    Everything that shows a customer their data depends on this rather than
    on get_current_user, so the change cannot be skipped by talking to the
    API directly instead of using the website.
    """
    if current_user.must_change_password:
        raise MUST_CHANGE_PASSWORD_ERROR
    return current_user


SettledUser = Annotated[User, Depends(get_settled_user)]


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
    # True when the user is still on the password staff gave them. The portal
    # shows nothing else until they have chosen their own.
    must_change_password: bool = False


class ChangePasswordRequest(BaseModel):
    """A user setting their own password."""

    current_password: str
    new_password: str


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


class DocumentOut(BaseModel):
    """A document attached to a shipment."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    doc_type: str
    file_name: str
    # True once the file itself is stored and downloadable (Step 4).
    available: bool = False


class ShipmentOut(BaseModel):
    """One part-shipment against an order."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    shipment_no: str
    dispatched_qty: Decimal | None
    unit: str | None
    status: str | None
    vessel_name: str | None
    imo_number: str | None
    etd: date | None
    eta: date | None
    # Built by the server so the provider can change without touching the UI.
    # None when there is no usable IMO number, so the UI shows no dead link.
    tracking_url: str | None = None
    tracking_provider: str | None = None
    documents: list[DocumentOut] = []


class OrderDetailOut(OrderOut):
    """An order plus its quantity breakdown and part-shipments."""

    dispatched_qty: Decimal
    balance_qty: Decimal
    shipments: list[ShipmentOut] = []


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
        must_change_password=user.must_change_password,
    )


@app.get("/api/me", response_model=LoginResponse | dict)
def me(current_user: CurrentUser, db: DbSession) -> dict:
    """Who am I? Used by the frontend to confirm a stored token is still good."""
    customer = db.get(Customer, current_user.customer_id)
    return {
        "email": current_user.email,
        "full_name": current_user.full_name,
        "customer": CustomerOut.model_validate(customer).model_dump(),
        "must_change_password": current_user.must_change_password,
    }


@app.post("/api/change-password")
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=problem
        )

    current_user.password_hash = security.hash_password(body.new_password)
    current_user.must_change_password = False
    current_user.password_changed_at = datetime.now(timezone.utc)
    db.commit()

    # The old token still works, and should: the person holding it is the
    # one who just proved they know the password. Tokens cannot be revoked
    # today, which is written down as a known limit.
    return {"detail": "Your password has been changed."}


@app.get("/api/orders", response_model=list[OrderOut])
def list_orders(current_user: SettledUser, db: DbSession) -> list[Order]:
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


@app.get("/api/orders/{order_id}", response_model=OrderDetailOut)
def get_order(order_id: int, current_user: SettledUser, db: DbSession) -> OrderDetailOut:
    """Return one order with its part-shipments and their documents.

    Scoped to the caller's own customer. Asking for someone else's order
    returns 404, exactly as if it did not exist, so the endpoint never
    reveals which order numbers belong to other customers.
    """
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.customer_id == current_user.customer_id)
        .options(selectinload(Order.shipments).selectinload(Shipment.documents))
    )
    if order is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

    ordered = order.ordered_qty or Decimal("0")
    dispatched = sum(
        (s.dispatched_qty or Decimal("0") for s in order.shipments), Decimal("0")
    )

    shipments = []
    for s in sorted(order.shipments, key=lambda s: s.id):
        ship = ShipmentOut.model_validate(s)
        ship.tracking_url = tracking.tracking_url(s.imo_number)
        ship.tracking_provider = (
            tracking.TRACKING_PROVIDER_NAME if ship.tracking_url else None
        )
        ship.documents = [
            DocumentOut(
                id=d.id,
                doc_type=d.doc_type,
                file_name=d.file_name,
                available=bool(d.stored_path),
            )
            for d in sorted(s.documents, key=lambda d: d.id)
        ]
        shipments.append(ship)

    return OrderDetailOut(
        **OrderOut.model_validate(order).model_dump(),
        dispatched_qty=dispatched,
        balance_qty=ordered - dispatched,
        shipments=shipments,
    )


@app.get("/api/documents/{document_id}/download")
def download_document(
    document_id: int, current_user: SettledUser, db: DbSession
) -> FileResponse:
    """Send a document file back to the customer it belongs to.

    Ownership is walked all the way up (document -> shipment -> order ->
    customer) and compared with the customer on the token. Anything that is
    not the caller's own document answers 404, so the endpoint never reveals
    that another customer's document exists.
    """
    document = db.scalar(
        select(Document)
        .join(Shipment, Document.shipment_id == Shipment.id)
        .join(Order, Shipment.order_id == Order.id)
        .where(
            Document.id == document_id,
            Order.customer_id == current_user.customer_id,
        )
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )

    path = storage.resolve(document.stored_path or "")
    if path is None:
        # The row exists but the file has not been uploaded yet.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This document has not been uploaded yet.",
        )

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=document.file_name,
    )
