"""Downloading a document a customer owns.

Ownership is walked all the way up (document -> shipment -> order ->
customer) and compared with the customer on the token. Anything that is not
the caller's own document answers 404, so the endpoint never reveals that
another customer's document exists.
"""

from fastapi import APIRouter
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.core.deps import DbSession, SettledUser, not_found
from app.models import Document, Order, Shipment
from app.services import storage

router = APIRouter()


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
        # What the file actually is, not what documents are usually. A JPG
        # or PNG scan is a real case: a mill test certificate often arrives
        # as a photograph of a sheet of paper.
        media_type=storage.media_type_for(document.stored_path or ""),
        filename=document.file_name,
    )
