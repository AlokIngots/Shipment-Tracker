"""What the admin console is sent, and what it submits back."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


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
    container_no: str | None
    bl_number: str | None
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
    # Moving a status back down the sequence is refused unless this says it
    # is deliberate. The screen sets it after asking; a CSV never does.
    allow_backwards: bool = False


class ShipmentIn(BaseModel):
    """A part-shipment as staff submit it, creating or editing."""

    shipment_no: str
    dispatched_qty: Decimal
    unit: str | None = None
    status: str | None = None
    vessel_name: str | None = None
    imo_number: str | None = None
    container_no: str | None = None
    bl_number: str | None = None
    etd: date | None = None
    eta: date | None = None
    # Moving a status back down the sequence is refused unless this says it
    # is deliberate. The screen sets it after asking; a CSV never does.
    allow_backwards: bool = False


class StaffPhotoOut(BaseModel):
    """One material photo, as staff see it."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    caption: str | None
    file_name: str


class StaffShipmentPhotosOut(BaseModel):
    """Every photo on one shipment, newest last."""

    shipment_id: int
    shipment_no: str
    photos: list[StaffPhotoOut]


class StaffLoginOut(BaseModel):
    """One person who can sign in, as the admin console lists them."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    full_name: str | None
    is_active: bool
    is_staff: bool
    # True while they are still on the temporary password staff gave them.
    must_change_password: bool


class StaffCustomerAccountOut(BaseModel):
    """A customer company, who signs in for it, and how much work it has."""

    id: int
    code: str
    name: str
    country: str | None
    order_count: int
    logins: list[StaffLoginOut]


class StaffAccountsOut(BaseModel):
    """The whole Customers & logins screen in one response."""

    customers: list[StaffCustomerAccountOut]
    staff: list[StaffLoginOut]


class CustomerIn(BaseModel):
    """A customer company as staff submit it."""

    code: str
    name: str
    country: str | None = None


class CustomerEditIn(BaseModel):
    """Editing a customer. The code is not here: it is the join to SAP/PMS."""

    name: str
    country: str | None = None


class LoginIn(BaseModel):
    """A new login for a customer."""

    email: str
    full_name: str | None = None


class ActiveIn(BaseModel):
    """Letting somebody in, or locking them out."""

    active: bool


class TemporaryPasswordOut(BaseModel):
    """A new login or a reset, with the one-time password.

    The password is in this response and nowhere else, ever again: only its
    hash is stored, so nobody, including the server, can read it back.
    """

    detail: str
    email: str
    temporary_password: str


class StaffActivityChangeOut(BaseModel):
    """One field of one change: what it was, and what it became."""

    field: str
    before: str | None
    after: str | None


class StaffActivityEventOut(BaseModel):
    """One change on the Activity page."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    happened_at: datetime
    # None when the change came from a command run on the server.
    actor_email: str | None
    source: str
    action: str
    summary: str
    changes: list[StaffActivityChangeOut] | None


class StaffActivityOut(BaseModel):
    """A page of the activity record, newest first."""

    events: list[StaffActivityEventOut]
    # True when there are older events than the last one on this page.
    more: bool
