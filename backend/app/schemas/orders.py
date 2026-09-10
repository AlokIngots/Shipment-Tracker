"""What a customer is sent: their orders, shipments and documents."""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


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


class PhotoOut(BaseModel):
    """One material photo, as a customer sees it listed.

    Only what is needed to draw the gallery. The image itself comes from
    /api/photos/{id}, which checks ownership the same way a document does.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    caption: str | None
    file_name: str


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
    container_no: str | None
    bl_number: str | None
    etd: date | None
    eta: date | None
    # Built by the server so the provider can change without touching the UI.
    # None when there is no usable IMO number, so the UI shows no dead link.
    tracking_url: str | None = None
    tracking_provider: str | None = None
    documents: list[DocumentOut] = []
    photos: list[PhotoOut] = []


class OrderDetailOut(OrderOut):
    """An order plus its quantity breakdown and part-shipments."""

    dispatched_qty: Decimal
    balance_qty: Decimal
    shipments: list[ShipmentOut] = []


# ------------------------------------------------------------- the staff side
