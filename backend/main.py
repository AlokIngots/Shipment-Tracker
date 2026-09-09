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
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    UploadFile,
    status,
)
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


MUST_CHANGE_PASSWORD_ERROR = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Please set your own password before continuing.",
)


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
    """A signed-in user who is no longer on a temporary password.

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


class StaffDocumentOut(BaseModel):
    """One document slot on a shipment, as staff see it."""

    doc_type: str
    document_id: int | None
    file_name: str | None
    uploaded: bool


class StaffShipmentOut(BaseModel):
    """A shipment on the staff page, with what is and is not attached."""

    id: int
    shipment_no: str
    status: str | None
    vessel_name: str | None
    customer_name: str
    customer_code: str
    sales_order_no: str
    documents: list[StaffDocumentOut]
    missing_count: int


class LoginResponse(BaseModel):
    """Returned on a successful sign-in."""

    token: str
    email: str
    full_name: str | None
    # Null for staff, who belong to no customer.
    customer: CustomerOut | None
    # True when the user is still on the password staff gave them. The portal
    # shows nothing else until they have chosen their own.
    must_change_password: bool = False
    is_staff: bool = False


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

    customer = db.get(Customer, user.customer_id) if user.customer_id else None
    return LoginResponse(
        token=security.create_token(user.id),
        email=user.email,
        full_name=user.full_name,
        customer=CustomerOut.model_validate(customer) if customer else None,
        must_change_password=user.must_change_password,
        is_staff=user.is_staff,
    )


@app.get("/api/me", response_model=LoginResponse | dict)
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


# --------------------------------------------------------------------- staff
#
# Everything below is the Alok Ingots side of the portal, and the only place
# in the API where a browser can write anything other than its own password.
# Every route depends on StaffUser.

# The documents a shipment is expected to have. A shipment is "complete"
# when all four are attached.
EXPECTED_DOCUMENTS = [
    "Packing List",
    "Commercial Invoice",
    "Bill of Lading",
    "Mill Test Certificate",
]


@app.get("/api/staff/shipments", response_model=list[StaffShipmentOut])
def staff_shipments(staff: StaffUser, db: DbSession) -> list[StaffShipmentOut]:
    """Every shipment, with which documents are attached and which are not.

    Ordered so the shipments needing attention come first.
    """
    rows = db.execute(
        select(Shipment, Order, Customer)
        .join(Order, Shipment.order_id == Order.id)
        .join(Customer, Order.customer_id == Customer.id)
        .options(selectinload(Shipment.documents))
        .order_by(Shipment.id.desc())
    ).all()

    out: list[StaffShipmentOut] = []
    for shipment, order, customer in rows:
        by_type = {d.doc_type: d for d in shipment.documents}

        documents: list[StaffDocumentOut] = []
        # The four expected ones first, then anything unusual somebody has
        # attached, so nothing is hidden just because it was not expected.
        for doc_type in EXPECTED_DOCUMENTS + [
            t for t in by_type if t not in EXPECTED_DOCUMENTS
        ]:
            document = by_type.get(doc_type)
            uploaded = bool(document and storage.resolve(document.stored_path or ""))
            documents.append(StaffDocumentOut(
                doc_type=doc_type,
                document_id=document.id if document else None,
                file_name=document.file_name if document else None,
                uploaded=uploaded,
            ))

        out.append(StaffShipmentOut(
            id=shipment.id,
            shipment_no=shipment.shipment_no,
            status=shipment.status,
            vessel_name=shipment.vessel_name,
            customer_name=customer.name,
            customer_code=customer.code,
            sales_order_no=order.sales_order_no,
            documents=documents,
            missing_count=sum(1 for d in documents if not d.uploaded),
        ))

    return out


@app.post("/api/staff/shipments/{shipment_id}/documents")
def staff_upload_document(
    shipment_id: int,
    staff: StaffUser,
    db: DbSession,
    doc_type: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
) -> dict[str, str]:
    """Attach a file to a shipment, replacing one of the same type.

    Does exactly what add_document.py has always done on the server, so the
    two cannot drift apart in what they produce.
    """
    shipment = db.get(Shipment, shipment_id)
    if shipment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Shipment not found."
        )

    doc_type = (doc_type or "").strip()
    if not doc_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Choose which kind of document this is.",
        )

    try:
        suffix = storage.check_upload(file.filename or "", file.content_type)
        stored_name = storage.store_upload(file.file, suffix)
    except storage.UploadRejected as rejected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(rejected)
        ) from rejected

    document = db.scalar(
        select(Document).where(
            Document.shipment_id == shipment.id, Document.doc_type == doc_type
        )
    )
    if document is None:
        document = Document(shipment_id=shipment.id, doc_type=doc_type)
        db.add(document)
        action = "added"
    else:
        # Only remove the old file once the new one is safely written.
        storage.delete(document.stored_path or "")
        action = "replaced"

    document.file_name = (file.filename or "document")[:255]
    document.stored_path = stored_name
    db.commit()

    return {"detail": f"{doc_type} {action} on {shipment.shipment_no}."}


@app.delete("/api/staff/documents/{document_id}")
def staff_delete_document(
    document_id: int, staff: StaffUser, db: DbSession
) -> dict[str, str]:
    """Remove a document, file and all.

    Worth having: attaching the wrong customer's invoice is the kind of
    mistake that must be undoable in seconds, not by asking someone with
    access to the server.
    """
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )

    doc_type = document.doc_type
    storage.delete(document.stored_path or "")
    db.delete(document)
    db.commit()

    return {"detail": f"{doc_type} removed."}


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
