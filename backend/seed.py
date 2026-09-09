"""Create the schema and load development data.

    python seed.py                # create missing tables, add/update demo data
    python seed.py --schema-only  # create missing tables only, no demo data
    python seed.py --reset        # DROP every table first, then recreate

--reset destroys all data. It exists because this is a development database
with no real customer data in it yet. Once real data lands, schema changes
must go through proper migrations instead.

All names, emails and passwords come from .env so that no credentials or
customer identities live in the repository.
"""

import os
import sys
from decimal import Decimal
from pathlib import Path

import security
from database import Base, SessionLocal, engine
from dotenv import load_dotenv
from datetime import date

from models import Customer, Document, Order, Shipment, User
from sqlalchemy import select

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


# Two customers, so that customer isolation can actually be tested.
DEMO_DATA = [
    {
        "customer": {
            "code": env("DEMO_CUSTOMER_CODE", "CUST-001"),
            "name": env("DEMO_CUSTOMER_NAME", "Demo Customer"),
            "country": env("DEMO_CUSTOMER_COUNTRY") or None,
        },
        "user": {
            "email": env("DEMO_LOGIN_EMAIL"),
            "password": env("DEMO_LOGIN_PASSWORD"),
            "full_name": "Procurement",
        },
        "orders": [
            {
                "sales_order_no": "AIMPL/SO/EXP/163/2025-26",
                "customer_po": "PO-4500781123",
                "grade": "431 / 1.4057",
                "description": "Bright bar rounds 20-40 mm, h9",
                "ordered_qty": Decimal("583.00"),
                "unit": "MT",
                "status": "In transit",
                "shipments": [
                    {
                        "shipment_no": "AIMPL/SHP/163-1",
                        "dispatched_qty": Decimal("200.000"),
                        "unit": "MT",
                        "status": "Delivered",
                        "vessel_name": "MV NORDIC STAR",
                        "imo_number": "9312341",
                        "etd": date(2025, 6, 12),
                        "eta": date(2025, 7, 8),
                        "documents": [
                            "Packing List", "Commercial Invoice",
                            "Bill of Lading", "Mill Test Certificate",
                        ],
                    },
                    {
                        "shipment_no": "AIMPL/SHP/163-2",
                        "dispatched_qty": Decimal("183.000"),
                        "unit": "MT",
                        "status": "In transit",
                        "vessel_name": "MV BALTIC TRADER",
                        "imo_number": "9487627",
                        "etd": date(2025, 8, 21),
                        "eta": date(2025, 9, 17),
                        "documents": [
                            "Packing List", "Commercial Invoice", "Bill of Lading",
                        ],
                    },
                ],
            }
        ],
    },
    {
        "customer": {
            "code": env("DEMO2_CUSTOMER_CODE", "CUST-002"),
            "name": env("DEMO2_CUSTOMER_NAME", "Second Demo Customer"),
            "country": env("DEMO2_CUSTOMER_COUNTRY") or None,
        },
        "user": {
            "email": env("DEMO2_LOGIN_EMAIL"),
            "password": env("DEMO2_LOGIN_PASSWORD"),
            "full_name": "Buyer",
        },
        "orders": [
            {
                "sales_order_no": "AIMPL/SO/EXP/164/2025-26",
                "customer_po": "PO-9900112233",
                "grade": "304 / 1.4301",
                "description": "Bright bar rounds 10-25 mm, h9",
                "ordered_qty": Decimal("120.500"),
                "unit": "MT",
                "status": "In production",
                "shipments": [
                    {
                        "shipment_no": "AIMPL/SHP/164-1",
                        "dispatched_qty": Decimal("40.000"),
                        "unit": "MT",
                        "status": "Shipped",
                        "vessel_name": "MV ADRIATIC WAVE",
                        "imo_number": "9601235",
                        "etd": date(2025, 9, 2),
                        "eta": date(2025, 9, 29),
                        "documents": ["Packing List", "Commercial Invoice"],
                    },
                ],
            }
        ],
    },
]


def upsert(session, model, match: dict, values: dict):
    """Insert a row, or update it in place if it already exists."""
    stmt = select(model)
    for field, value in match.items():
        stmt = stmt.where(getattr(model, field) == value)
    row = session.scalar(stmt)
    if row is None:
        row = model(**match, **values)
        session.add(row)
    else:
        for field, value in values.items():
            setattr(row, field, value)
    session.flush()
    return row


def main() -> None:
    reset = "--reset" in sys.argv
    schema_only = "--schema-only" in sys.argv

    if reset:
        print("Dropping all tables...")
        Base.metadata.drop_all(engine)

    Base.metadata.create_all(engine)
    print("Schema ready (customers, users, orders, shipments, documents)")

    if schema_only:
        # What a real server runs: create any missing tables and stop.
        # Demo customers must never be created on a production database.
        print("Schema only — no demo data was created.")
        return

    with SessionLocal() as session:
        for block in DEMO_DATA:
            spec = block["user"]
            if not spec["email"] or not spec["password"]:
                print(f"  ! skipped {block['customer']['code']}: login not set in .env")
                continue

            customer = upsert(
                session, Customer,
                {"code": block["customer"]["code"]},
                {"name": block["customer"]["name"],
                 "country": block["customer"]["country"]},
            )

            upsert(
                session, User,
                {"email": spec["email"].lower()},
                {"customer_id": customer.id,
                 "password_hash": security.hash_password(spec["password"]),
                 "full_name": spec["full_name"],
                 "is_active": True},
            )

            shipment_count = 0
            for order in block["orders"]:
                shipments = order.get("shipments", [])
                values = {
                    k: v for k, v in order.items()
                    if k not in ("sales_order_no", "shipments")
                }
                order_row = upsert(
                    session, Order,
                    {"sales_order_no": order["sales_order_no"]},
                    {**values, "customer_id": customer.id},
                )

                for shipment in shipments:
                    doc_types = shipment.get("documents", [])
                    ship_values = {
                        k: v for k, v in shipment.items()
                        if k not in ("shipment_no", "documents")
                    }
                    ship_row = upsert(
                        session, Shipment,
                        {"shipment_no": shipment["shipment_no"]},
                        {**ship_values, "order_id": order_row.id},
                    )
                    shipment_count += 1

                    for doc_type in doc_types:
                        # Metadata only for now. The files themselves arrive
                        # in Step 4, which is when stored_path gets filled in.
                        upsert(
                            session, Document,
                            {"shipment_id": ship_row.id, "doc_type": doc_type},
                            {"file_name": (
                                f"{ship_row.shipment_no.replace('/', '-')}"
                                f"-{doc_type.replace(' ', '-')}.pdf"
                            )},
                        )

            print(f"  {customer.code} — {customer.name}: 1 user, "
                  f"{len(block['orders'])} order(s), {shipment_count} shipment(s)")

        session.commit()

    print("Done.")


if __name__ == "__main__":
    main()
