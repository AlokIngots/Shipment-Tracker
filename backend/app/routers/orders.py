"""What a customer may read: their own orders.

Every route here scopes on the customer taken from the sign-in token, never
on anything in the request. Asking for somebody else's order answers 404
rather than 403, so the API never confirms that a row belonging to another
customer exists.

Read-only, and not by accident: there is no POST, PUT or DELETE anywhere in
the customer half of the API. Only the admin console writes.
"""

from decimal import Decimal

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import DbSession, SettledUser, not_found
from app.models import Order, Shipment
from app.schemas import DocumentOut, OrderDetailOut, OrderOut, ShipmentOut
from app.services import tracking

router = APIRouter()

@router.get("/api/orders", response_model=list[OrderOut])
def list_orders(current_user: SettledUser, db: DbSession) -> list[Order]:
    """Return the signed-in user's own orders, and nothing else."""
    return list(
        db.scalars(
            select(Order)
            .where(Order.customer_id == current_user.customer_id)
            .order_by(Order.id)
        )
    )


@router.get("/api/orders/{order_id}", response_model=OrderDetailOut)
def get_order(
    order_id: int, current_user: SettledUser, db: DbSession
) -> OrderDetailOut:
    """Return one order with its part-shipments and their documents."""
    order = db.scalar(
        select(Order)
        .where(Order.id == order_id, Order.customer_id == current_user.customer_id)
        .options(selectinload(Order.shipments).selectinload(Shipment.documents))
    )
    if order is None:
        raise not_found("Order not found.")

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
