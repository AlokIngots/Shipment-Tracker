"""Attach a document file to a shipment.

For Alok Ingots staff, run on the server. Customers never upload anything,
so there is deliberately no upload endpoint on the API.

    python add_document.py --shipment AIMPL/SHP/163-1 \
                           --type "Packing List" \
                           --file /path/to/packing-list.pdf

If a document of that type already exists on the shipment it is replaced
and the old file is deleted.

    python add_document.py --list                 # show every document
    python add_document.py --list AIMPL/SHP/163-1 # just one shipment
"""

import argparse
import sys
from pathlib import Path

from app.services import audit, storage
from app.core.database import SessionLocal
from app.models import Document, Order, Shipment
from sqlalchemy import select

DOC_TYPES = [
    "Packing List",
    "Commercial Invoice",
    "Bill of Lading",
    "Mill Test Certificate",
]


def list_documents(shipment_no: str | None) -> None:
    with SessionLocal() as session:
        stmt = (
            select(Document, Shipment, Order)
            .join(Shipment, Document.shipment_id == Shipment.id)
            .join(Order, Shipment.order_id == Order.id)
            .order_by(Shipment.shipment_no, Document.id)
        )
        if shipment_no:
            stmt = stmt.where(Shipment.shipment_no == shipment_no)

        rows = session.execute(stmt).all()
        if not rows:
            print("No documents found.")
            return

        current = None
        for document, shipment, order in rows:
            if shipment.shipment_no != current:
                current = shipment.shipment_no
                print(f"\n{order.sales_order_no}  /  {shipment.shipment_no}")
            state = "uploaded" if storage.resolve(document.stored_path or "") else "MISSING"
            print(f"  [{document.id:>3}] {document.doc_type:<24} {state:<9} {document.file_name}")


def add(shipment_no: str, doc_type: str, file_path: Path) -> int:
    if not file_path.is_file():
        print(f"Error: no such file: {file_path}")
        return 1

    with SessionLocal() as session:
        shipment = session.scalar(
            select(Shipment).where(Shipment.shipment_no == shipment_no)
        )
        if shipment is None:
            print(f"Error: no shipment called {shipment_no!r}")
            return 1

        stored_name = storage.store_file(file_path)

        document = session.scalar(
            select(Document).where(
                Document.shipment_id == shipment.id, Document.doc_type == doc_type
            )
        )
        if document is None:
            document = Document(shipment_id=shipment.id, doc_type=doc_type)
            session.add(document)
            action = "Added"
            old_file_name = None
        else:
            old = storage.resolve(document.stored_path or "")
            if old:
                old.unlink()
            action = "Replaced"
            old_file_name = document.file_name

        document.file_name = file_path.name
        document.stored_path = stored_name
        # Worded exactly as the staff page words it, so the activity record
        # reads the same whichever way the document arrived.
        audit.record(
            session,
            f"document.{action.lower()}",
            f"Added {doc_type} to shipment {shipment_no}"
            if action == "Added"
            else f"Replaced {doc_type} on shipment {shipment_no}",
            changes=[{"field": "File", "before": old_file_name, "after": file_path.name}],
        )
        session.commit()

        print(f"{action}: {doc_type} on {shipment_no} ({file_path.name})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", nargs="?", const="", metavar="SHIPMENT_NO",
                        help="list documents, optionally for one shipment")
    parser.add_argument("--shipment", help="shipment number, e.g. AIMPL/SHP/163-1")
    parser.add_argument("--type", help=f"document type, one of: {', '.join(DOC_TYPES)}")
    parser.add_argument("--file", type=Path, help="path to the file to attach")
    args = parser.parse_args()

    if args.list is not None:
        list_documents(args.list or None)
        return 0

    if not (args.shipment and args.type and args.file):
        parser.print_help()
        return 1

    if args.type not in DOC_TYPES:
        print(f"Warning: {args.type!r} is not one of the usual types "
              f"({', '.join(DOC_TYPES)}). Adding it anyway.")

    return add(args.shipment, args.type, args.file)


if __name__ == "__main__":
    sys.exit(main())
