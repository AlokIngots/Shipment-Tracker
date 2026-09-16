"""Admin console: the part-shipments under an order.

Split from admin/orders.py only for length; the checking rules live there,
because an order and its shipments are validated against each other and
against what import_data.py accepts.
"""

from fastapi import APIRouter

from app.core.deps import DbSession, StaffUser, bad_request, not_found
from app.models import Order, Shipment
from app.services import audit, photos
from app.routers.admin.orders import apply_shipment, load_order, order_response
from app.schemas import ShipmentIn, StaffOrderOut

router = APIRouter(prefix="/api/staff")


@router.post("/orders/{order_id}/shipments", response_model=StaffOrderOut, status_code=201)
def staff_create_shipment(
    order_id: int, body: ShipmentIn, staff: StaffUser, db: DbSession
) -> StaffOrderOut:
    """Add a part-shipment to an order."""
    order = load_order(order_id, db)
    shipment = Shipment(order_id=order.id)
    apply_shipment(shipment, body, db)
    db.add(shipment)
    audit.record(
        db,
        "shipment.created",
        f"Added shipment {shipment.shipment_no} to order {order.sales_order_no}",
        actor=staff,
        changes=audit.diff(
            {}, audit.snapshot(shipment, audit.SHIPMENT_FIELDS), audit.SHIPMENT_FIELDS
        ),
    )
    db.commit()
    return order_response(order, db)


@router.put("/shipments/{shipment_id}", response_model=StaffOrderOut)
def staff_update_shipment(
    shipment_id: int, body: ShipmentIn, staff: StaffUser, db: DbSession
) -> StaffOrderOut:
    """Edit a part-shipment, and return the order it belongs to."""
    shipment = db.get(Shipment, shipment_id)
    if shipment is None:
        raise not_found("Shipment not found.")

    before = audit.snapshot(shipment, audit.SHIPMENT_FIELDS)
    apply_shipment(shipment, body, db)
    changes = audit.diff(
        before, audit.snapshot(shipment, audit.SHIPMENT_FIELDS), audit.SHIPMENT_FIELDS
    )

    order = db.get(Order, shipment.order_id)
    # Same as an order: a save that changed nothing is not recorded.
    if changes:
        audit.record(
            db,
            "shipment.updated",
            f"Changed shipment {shipment.shipment_no} on order {order.sales_order_no}"
            + audit.correction_note(before["status"], shipment.status),
            actor=staff,
            changes=changes,
        )
    db.commit()
    return order_response(order, db)


@router.delete("/shipments/{shipment_id}")
def staff_delete_shipment(
    shipment_id: int, staff: StaffUser, db: DbSession
) -> dict[str, str]:
    """Remove a part-shipment, but only while nothing is attached to it.

    Same reasoning as an order: removing it would take its documents with
    it, so the documents have to go first, one at a time and on purpose.
    """
    shipment = db.get(Shipment, shipment_id)
    if shipment is None:
        raise not_found("Shipment not found.")

    if shipment.documents:
        raise bad_request(
            f"{shipment.shipment_no} still has {len(shipment.documents)} "
            "document(s) attached. Remove those first."
        )

    # Photos do not block the delete the way documents do -- a snapshot of
    # a bundle is not filed paperwork -- but their files have to go with
    # them by hand, previews included. The database cascade removes the
    # rows; nothing on disk knows about it, and orphaned images would pile
    # up silently.
    for photo in shipment.photos:
        photos.delete_files(photo)

    shipment_no = shipment.shipment_no
    photo_count = len(shipment.photos)
    note = f" and {photo_count} photo(s)" if photo_count else ""

    order = db.get(Order, shipment.order_id)
    audit.record(
        db,
        "shipment.deleted",
        f"Removed shipment {shipment_no}{note} from order {order.sales_order_no}",
        actor=staff,
        changes=audit.diff(
            audit.snapshot(shipment, audit.SHIPMENT_FIELDS), {}, audit.SHIPMENT_FIELDS
        ),
    )

    db.delete(shipment)
    db.commit()

    return {"detail": f"{shipment_no}{note} removed."}
