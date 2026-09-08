"""Create the schema and load development data.

    python seed.py            # create missing tables, add/update the demo data
    python seed.py --reset    # DROP every table first, then recreate

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
from models import Customer, Order, User
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

    if reset:
        print("Dropping all tables...")
        Base.metadata.drop_all(engine)

    Base.metadata.create_all(engine)
    print("Schema ready (customers, users, orders, shipments, documents)")

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

            for order in block["orders"]:
                match = {"sales_order_no": order["sales_order_no"]}
                values = {k: v for k, v in order.items() if k != "sales_order_no"}
                upsert(session, Order, match,
                       {**values, "customer_id": customer.id})

            print(f"  {customer.code} — {customer.name}: "
                  f"1 user, {len(block['orders'])} order(s)")

        session.commit()

    print("Done.")


if __name__ == "__main__":
    main()
