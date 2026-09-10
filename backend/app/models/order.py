"""An export order, and the part-shipments that fulfil it."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base



class Order(Base):
    """An export sales order as the customer sees it in the portal."""

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    sales_order_no: Mapped[str] = mapped_column(String(140), unique=True, index=True)
    customer_po: Mapped[str | None] = mapped_column(String(140))
    grade: Mapped[str | None] = mapped_column(String(140))
    description: Mapped[str | None] = mapped_column(Text)
    ordered_qty: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    unit: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str | None] = mapped_column(String(50))

    customer: Mapped["Customer"] = relationship(back_populates="orders")
    shipments: Mapped[list["Shipment"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Order {self.sales_order_no} ({self.status})>"


class Shipment(Base):
    """A part-shipment against an order. One order can ship in several lots."""

    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), index=True
    )
    shipment_no: Mapped[str] = mapped_column(String(140), index=True)
    dispatched_qty: Mapped[Decimal | None] = mapped_column(Numeric(14, 3))
    unit: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str | None] = mapped_column(String(50))
    vessel_name: Mapped[str | None] = mapped_column(String(140))
    imo_number: Mapped[str | None] = mapped_column(String(20))
    etd: Mapped[date | None] = mapped_column(Date)
    eta: Mapped[date | None] = mapped_column(Date)

    order: Mapped["Order"] = relationship(back_populates="shipments")
    documents: Mapped[list["Document"]] = relationship(
        back_populates="shipment", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Shipment {self.shipment_no}>"
