"""ORM models for the customer portal."""

from decimal import Decimal

from sqlalchemy import Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Order(Base):
    """An export sales order as the customer sees it in the portal."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sales_order_no: Mapped[str] = mapped_column(String(140), unique=True, index=True)
    customer_po: Mapped[str | None] = mapped_column(String(140))
    grade: Mapped[str | None] = mapped_column(String(140))
    description: Mapped[str | None] = mapped_column(Text)
    ordered_qty: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    unit: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str | None] = mapped_column(String(50))

    def __repr__(self) -> str:
        return f"<Order {self.sales_order_no} ({self.status})>"
