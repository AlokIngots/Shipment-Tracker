"""A record of what each customer has already been told."""

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
    # When it was last TRIED, which is not when the row was made: a message
    # suppressed this morning and sent this afternoon keeps one row, and the
    # afternoon is the answer a person wants on the Messages screen.
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    # How many times it has been tried. Above 1 means an earlier attempt was
    # suppressed or failed and this one is a retry.
    attempts: Mapped[int] = mapped_column(Integer, default=1, server_default="1")

    def __repr__(self) -> str:
        return f"<Notification {self.event} -> user {self.user_id} ({self.outcome})>"
