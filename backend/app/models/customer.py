"""Who the portal is for, and who may sign in to it."""

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
    # Null for Alok Ingots staff, who belong to no customer. Every other
    # user must have one: that link is what keeps one customer's orders
    # away from another's.
    customer_id: Mapped[int | None] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # Alok Ingots staff. Sees the staff pages, never a customer's portal.
    is_staff: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    # PBKDF2-HMAC-SHA256, salted per user. Never a plain password.
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(200))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # True while the user is still on the temporary password staff gave them.
    # The API refuses to show any order until they have set their own.
    must_change_password: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    customer: Mapped["Customer"] = relationship(back_populates="users")

    def __repr__(self) -> str:
        return f"<User {self.email}>"
