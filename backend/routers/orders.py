"""What a customer may read: their own orders, and their own documents.

Every route here scopes on the customer taken from the sign-in token, never
from anything in the request. Asking for somebody else's order or document
answers 404 rather than 403, so the API never confirms that a row belonging
to another customer exists.
"""

from decimal import Decimal

import storage
import tracking
from deps import DbSession, SettledUser, not_found
from fastapi import APIRouter
from fastapi.responses import FileResponse
from models import Document, Order, Shipment
from schemas import DocumentOut, OrderDetailOut, OrderOut, ShipmentOut
from sqlalchemy import select
from sqlalchemy.orm import selectinload

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


@router.get("/api/documents/{document_id}/download")
def download_document(
    document_id: int, current_user: SettledUser, db: DbSession
) -> FileResponse:
    """Send a document file back to the customer it belongs to.

    Ownership is walked all the way up (document -> shipment -> order ->
    customer) and compared with the customer on the token.
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
        raise not_found("Document not found.")

    path = storage.resolve(document.stored_path or "")
    if path is None:
        # The row exists but the file has not been uploaded yet.
        raise not_found("This document has not been uploaded yet.")

    return FileResponse(
        path,
        media_type="application/pdf",
        filename=document.file_name,
    )
