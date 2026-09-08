"""ORM models for the customer portal."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    UniqueConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Customer(Base):
    """An export customer. Everything a portal user sees hangs off this."""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    country: Mapped[str | None] = mapped_column(String(100))

    users: Mapped[list["User"]] = relationship(back_populates="customer")
    orders: Mapped[list["Order"]] = relationship(back_populates="customer")

    def __repr__(self) -> str:
        return f"<Customer {self.code}>"


class User(Base):
    """A person who can sign in to the portal, always tied to one customer."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # PBKDF2-HMAC-SHA256, salted per user. Never a plain password.
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    customer: Mapped["Customer"] = relationship(back_populates="users")

    def __repr__(self) -> str:
        return f"<User {self.email}>"


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


class Document(Base):
    """A document attached to a shipment (Packing List, Invoice, BL, MTC...)."""

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shipment_id: Mapped[int] = mapped_column(
        ForeignKey("shipments.id", ondelete="CASCADE"), index=True
    )
    doc_type: Mapped[str] = mapped_column(String(60))
    file_name: Mapped[str] = mapped_column(String(255))
    # Path on the server. Files themselves are never committed to git.
    stored_path: Mapped[str | None] = mapped_column(String(500))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    shipment: Mapped["Shipment"] = relationship(back_populates="documents")

    def __repr__(self) -> str:
        return f"<Document {self.doc_type} {self.file_name}>"


class Notification(Base):
    """A record of one message sent to one customer about one shipment.

    The unique constraint on (shipment_id, event, user_id) is what stops a
    customer being told twice that the same shipment shipped, however many
    times the notifier runs.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint(
            "shipment_id", "event", "user_id", name="uq_notification_once"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shipment_id: Mapped[int] = mapped_column(
        ForeignKey("shipments.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # The shipment status that triggered this, e.g. "Shipped" or "Delivered".
    event: Mapped[str] = mapped_column(String(50))
    channel: Mapped[str] = mapped_column(String(20), default="email")
    # "sent", "suppressed" (dry run or not on the pilot allow-list), or "failed"
    outcome: Mapped[str] = mapped_column(String(20))
    detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Notification {self.event} -> user {self.user_id} ({self.outcome})>"
