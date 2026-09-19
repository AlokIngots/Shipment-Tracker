"""What a customer is sent: their orders, shipments and documents."""

from datetime import date, datetime
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
    order_date: date | None = None
    # Worked out from the shipments on every read; see statuses.order_status.
    status: str


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


class TrackingMoveOut(BaseModel):
    """One step in the container's journey: where, what, when, on which ship."""

    event: str | None
    label: str
    # False while it is the shipping line's estimate rather than a fact.
    actual: bool
    location: str | None
    country: str | None
    vessel: str | None
    voyage: str | None
    # YYYY-MM-DD as the port wrote it -- not moved into anybody's time zone.
    date: str | None
    timestamp: str | None
    # The box changed vessel here. `from_vessel` is the ship it came off.
    transshipment: bool = False
    from_vessel: str | None = None
    # The most recent thing that has actually happened.
    latest: bool = False


class LiveTrackingOut(BaseModel):
    """What ShipsGo last told the portal about this shipment's container.

    Always the stored copy: opening a page never calls ShipsGo.
    """

    # "updating" until ShipsGo has news, then "ready". ("unavailable" is
    # only ever sent to staff; a customer is shown nothing instead.)
    state: str
    status: str | None
    status_label: str
    carrier: str | None
    port_of_loading: str | None
    port_of_discharge: str | None
    loaded_on: str | None
    eta: str | None
    transshipments: int = 0
    container_number: str | None
    container_count: int = 0
    other_containers: list[str] = []
    movements: list[TrackingMoveOut] = []
    updated_at: datetime | None


class ShipmentOut(BaseModel):
    """One part-shipment against an order."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    shipment_no: str
    dispatched_qty: Decimal | None
    unit: str | None
    status: str | None
    # The last shipment against the order. Shown to the customer, because it
    # explains an order that says Delivered with a few tonnes of balance.
    is_final: bool = False
    vessel_name: str | None
    imo_number: str | None
    container_no: str | None
    bl_number: str | None
    carrier: str | None
    etd: date | None
    eta: date | None
    # The route and the box, from the Bill of Lading. gross_weight is in the
    # shipment's unit, beside dispatched_qty, which is the net.
    port_of_loading: str | None = None
    port_of_discharge: str | None = None
    voyage_no: str | None = None
    seal_no: str | None = None
    container_size: str | None = None
    gross_weight: Decimal | None = None
    # The carrier's own tracking page -- where the box is, not the ship.
    # None when the carrier is unknown or unset, so no dead button is drawn.
    # There is no vessel link or map: a named ship's current position is a
    # different voyage once cargo is transshipped. See services/tracking.py.
    container_tracking_url: str | None = None
    container_tracking_carrier: str | None = None
    # False when the carrier's page opens empty, so the screen can tell the
    # customer to paste the number rather than implying it is already there.
    container_tracking_prefilled: bool = False
    # Live tracking from ShipsGo, or None when it is not switched on.
    live_tracking: LiveTrackingOut | None = None
    documents: list[DocumentOut] = []
    # The expected documents not attached yet, so the customer knows what is
    # coming rather than guessing from what is there. Empty on a cancelled
    # shipment, which will get none.
    documents_to_come: list[str] = []
    photos: list[PhotoOut] = []


class OrderDetailOut(OrderOut):
    """An order plus its quantity breakdown and part-shipments."""

    dispatched_qty: Decimal
    balance_qty: Decimal
    shipments: list[ShipmentOut] = []


# ------------------------------------------------------------- the staff side
