"""The shapes that cross the wire, in and out.

Nothing here touches the database or decides anything. These classes exist
so that what the API promises is written down in one place: add a column to
models.py and no customer sees it until it also appears here, which is the
point.

Read them in three groups: what everybody uses, what a customer is sent,
and what staff are sent or submit.
"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

# ------------------------------------------------------------------ shared


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


# ------------------------------------------------------- the customer's side


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
    # True once the file itself is stored and downloadable.
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


# ------------------------------------------------------------- the staff side


class StaffCustomerOut(BaseModel):
    """A customer, for the list staff pick from when creating an order."""

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
    """A shipment on the documents page, with what is and is not attached."""

    id: int
    shipment_no: str
    status: str | None
    vessel_name: str | None
    customer_name: str
    customer_code: str
    sales_order_no: str
    documents: list[StaffDocumentOut]
    missing_count: int


class StaffOrderShipmentOut(BaseModel):
    """A part-shipment as it appears under its order on the orders page."""

    id: int
    shipment_no: str
    dispatched_qty: Decimal | None
    unit: str | None
    status: str | None
    vessel_name: str | None
    imo_number: str | None
    etd: date | None
    eta: date | None
    # So the page can say why a shipment refuses to be removed.
    document_count: int


class StaffOrderOut(BaseModel):
    """An order on the staff orders page, with its shipments and balance."""

    id: int
    customer_id: int
    customer_code: str
    customer_name: str
    sales_order_no: str
    customer_po: str | None
    grade: str | None
    description: str | None
    ordered_qty: Decimal | None
    unit: str | None
    status: str | None
    dispatched_qty: Decimal
    balance_qty: Decimal
    shipments: list[StaffOrderShipmentOut]


class OrderIn(BaseModel):
    """An order as staff submit it, creating or editing."""

    customer_id: int
    sales_order_no: str
    customer_po: str | None = None
    grade: str | None = None
    description: str | None = None
    ordered_qty: Decimal
    unit: str | None = None
    status: str | None = None


class ShipmentIn(BaseModel):
    """A part-shipment as staff submit it, creating or editing."""

    shipment_no: str
    dispatched_qty: Decimal
    unit: str | None = None
    status: str | None = None
    vessel_name: str | None = None
    imo_number: str | None = None
    etd: date | None = None
    eta: date | None = None
