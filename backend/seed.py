"""Create the schema and insert one example order.

Safe to run more than once: the order is matched on sales_order_no and
updated in place rather than duplicated.

    python seed.py
"""

from decimal import Decimal

from sqlalchemy import select

from database import Base, SessionLocal, engine
from models import Order

EXAMPLE_ORDER = {
    "sales_order_no": "AIMPL/SO/EXP/163/2025-26",
    "customer_po": "PO-4500781123",
    "grade": "431 / 1.4057",
    "description": "Bright bar rounds 20-40 mm, h9",
    "ordered_qty": Decimal("583.00"),
    "unit": "MT",
    "status": "In transit",
}


def main() -> None:
    Base.metadata.create_all(engine)
    print("Schema ready (table: orders)")

    with SessionLocal() as session:
        order = session.scalar(
            select(Order).where(
                Order.sales_order_no == EXAMPLE_ORDER["sales_order_no"]
            )
        )
        if order is None:
            order = Order(**EXAMPLE_ORDER)
            session.add(order)
            action = "Inserted"
        else:
            for field, value in EXAMPLE_ORDER.items():
                setattr(order, field, value)
            action = "Updated existing"

        session.commit()
        print(f"{action} order: {order.sales_order_no} (id={order.id})")


if __name__ == "__main__":
    main()
