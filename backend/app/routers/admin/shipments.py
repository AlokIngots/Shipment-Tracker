"""Admin console: the part-shipments under an order.

Split from admin/orders.py only for length; the checking rules live there,
because an order and its shipments are validated against each other and
against what import_data.py accepts.
"""

from fastapi import APIRouter

from app.core.deps import DbSession, StaffUser, bad_request, not_found
from app.models import Order, Shipment
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

    apply_shipment(shipment, body, db)
    db.commit()
    return order_response(db.get(Order, shipment.order_id), db)


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

    shipment_no = shipment.shipment_no
    db.delete(shipment)
    db.commit()
    return {"detail": f"{shipment_no} removed."}
