"""The Alok Ingots side: attaching documents to shipments.

Uploading is the only way a browser can write a file into the portal, and
everything it is allowed to write is decided in storage.py, not here.
"""

import storage
from deps import DbSession, StaffUser, bad_request, not_found
from fastapi import APIRouter, File, Form, UploadFile
from models import Customer, Document, Order, Shipment
from schemas import StaffDocumentOut, StaffShipmentOut
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Annotated

router = APIRouter(prefix="/api/staff")

# The documents a shipment is expected to have. A shipment is "complete"
# when all four are attached.
EXPECTED_DOCUMENTS = [
    "Packing List",
    "Commercial Invoice",
    "Bill of Lading",
    "Mill Test Certificate",
]


@router.get("/shipments", response_model=list[StaffShipmentOut])
def staff_shipments(staff: StaffUser, db: DbSession) -> list[StaffShipmentOut]:
    """Every shipment, with which documents are attached and which are not."""
    rows = db.execute(
        select(Shipment, Order, Customer)
        .join(Order, Shipment.order_id == Order.id)
        .join(Customer, Order.customer_id == Customer.id)
        .options(selectinload(Shipment.documents))
        .order_by(Shipment.id.desc())
    ).all()

    out: list[StaffShipmentOut] = []
    for shipment, order, customer in rows:
        by_type = {d.doc_type: d for d in shipment.documents}

        documents: list[StaffDocumentOut] = []
        # The four expected ones first, then anything unusual somebody has
        # attached, so nothing is hidden just because it was not expected.
        for doc_type in EXPECTED_DOCUMENTS + [
            t for t in by_type if t not in EXPECTED_DOCUMENTS
        ]:
            document = by_type.get(doc_type)
            uploaded = bool(document and storage.resolve(document.stored_path or ""))
            documents.append(
                StaffDocumentOut(
                    doc_type=doc_type,
                    document_id=document.id if document else None,
                    file_name=document.file_name if document else None,
                    uploaded=uploaded,
                )
            )

        out.append(
            StaffShipmentOut(
                id=shipment.id,
                shipment_no=shipment.shipment_no,
                status=shipment.status,
                vessel_name=shipment.vessel_name,
                customer_name=customer.name,
                customer_code=customer.code,
                sales_order_no=order.sales_order_no,
                documents=documents,
                missing_count=sum(1 for d in documents if not d.uploaded),
            )
        )

    return out


@router.post("/shipments/{shipment_id}/documents")
def staff_upload_document(
    shipment_id: int,
    staff: StaffUser,
    db: DbSession,
    doc_type: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
) -> dict[str, str]:
    """Attach a file to a shipment, replacing one of the same type.

    Does exactly what add_document.py has always done on the server, so the
    two cannot drift apart in what they produce.
    """
    shipment = db.get(Shipment, shipment_id)
    if shipment is None:
        raise not_found("Shipment not found.")

    doc_type = (doc_type or "").strip()
    if not doc_type:
        raise bad_request("Choose which kind of document this is.")

    try:
        suffix = storage.check_upload(file.filename or "", file.content_type)
        stored_name = storage.store_upload(file.file, suffix)
    except storage.UploadRejected as rejected:
        raise bad_request(str(rejected)) from rejected

    document = db.scalar(
        select(Document).where(
            Document.shipment_id == shipment.id, Document.doc_type == doc_type
        )
    )
    if document is None:
        document = Document(shipment_id=shipment.id, doc_type=doc_type)
        db.add(document)
        action = "added"
    else:
        # Only remove the old file once the new one is safely written.
        storage.delete(document.stored_path or "")
        action = "replaced"

    document.file_name = (file.filename or "document")[:255]
    document.stored_path = stored_name
    db.commit()

    return {"detail": f"{doc_type} {action} on {shipment.shipment_no}."}


@router.delete("/documents/{document_id}")
def staff_delete_document(
    document_id: int, staff: StaffUser, db: DbSession
) -> dict[str, str]:
    """Remove a document, file and all.

    Worth having: attaching the wrong customer's invoice is the kind of
    mistake that must be undoable in seconds, not by asking someone with
    access to the server.
    """
    document = db.get(Document, document_id)
    if document is None:
        raise not_found("Document not found.")

    doc_type = document.doc_type
    storage.delete(document.stored_path or "")
    db.delete(document)
    db.commit()

    return {"detail": f"{doc_type} removed."}
