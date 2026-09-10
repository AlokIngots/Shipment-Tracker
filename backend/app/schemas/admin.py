"""What the admin console is sent, and what it submits back."""

from datetime import date
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
