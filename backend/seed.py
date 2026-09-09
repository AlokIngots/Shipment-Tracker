"""Load development data.

    python seed.py                # bring the schema up to date, add demo data
    python seed.py --schema-only  # bring the schema up to date only, no data
    python seed.py --reset        # DROP every table first, then rebuild

The schema is no longer built here. ``migrate.py`` owns it, and this script
calls it — so there is one way the tables get made, and it is the same way on
a server holding real data as on this laptop.

--reset destroys all data, and is only for a development database. On a
server, ``python migrate.py`` changes the schema without losing anything.

All names, emails and passwords come from .env so that no credentials or
customer identities live in the repository.
"""

import os
import sys
from decimal import Decimal
from pathlib import Path

import migrate
import security
from database import Base, SessionLocal, engine
from dotenv import load_dotenv
from datetime import date

from models import Customer, Document, Order, Shipment, User
from sqlalchemy import select, text

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
        # drop_all only knows about the portal's own tables, so Alembic's
        # record of which migrations have run would survive and claim the
        # schema was still there. Clear it too, or the rebuild does nothing.
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))

    # One way to build the schema, the same one a real server uses.
    if migrate.main() != 0:
        print("! The schema is not in the state the code expects (see above).")
        return

    if schema_only:
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
                 "is_active": True,
                 # Demo logins are printed in .env, so there is nothing to
                 # change. Set it explicitly: without this, a demo account
                 # that had been through manage_users.py --reset-password
                 # would keep the lock and refuse the password seed just set.
                 "must_change_password": False},
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
