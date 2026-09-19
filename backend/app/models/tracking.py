"""What ShipsGo last told us about a shipment's container."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ShipmentTracking(Base):
    """Live tracking for one shipment: ShipsGo's reference and its latest news.

    A row exists only once the shipment has been added to ShipsGo, which is
    the one step that costs a credit. `shipment_id` is unique, so a shipment
    can never hold two, and `external_id` is ShipsGo's own number for it --
    every refresh after that is a free read of that number.

    Customers are shown what is stored here, never a live call. The timer in
    app/services/scheduler.py keeps it fresh.
    """

    __tablename__ = "shipment_tracking"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shipment_id: Mapped[int] = mapped_column(
        ForeignKey("shipments.id", ondelete="CASCADE"), unique=True, index=True
    )
    provider: Mapped[str] = mapped_column(String(20), default="shipsgo")
    # ShipsGo's shipment id. Not unique: if two of our shipments travel on one
    # B/L, both read the same ShipsGo shipment, and reading is free.
    external_id: Mapped[int] = mapped_column(Integer, index=True)
    # The B/L number that was added. If staff later change the shipment's
    # B/L, this no longer describes it, and customers stop seeing it.
    booking_number: Mapped[str] = mapped_column(String(60))

    # ------------------------------------------ the latest news, replaced whole
    status: Mapped[str | None] = mapped_column(String(20))
    carrier_name: Mapped[str | None] = mapped_column(String(80))
    port_of_loading: Mapped[str | None] = mapped_column(String(120))
    port_of_discharge: Mapped[str | None] = mapped_column(String(120))
    # Kept as ShipsGo sent them, with the port's own UTC offset, so the date
    # a customer reads is the date at that port rather than in their browser.
    loaded_at: Mapped[str | None] = mapped_column(String(40))
    eta: Mapped[str | None] = mapped_column(String(40))
    transshipments: Mapped[int | None] = mapped_column(Integer)
    container_count: Mapped[int | None] = mapped_column(Integer)
    # Each container's movements, simplified. See live_tracking.simplify().
    containers: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)
    # ShipsGo's own clocks: when it last looked at the carrier, and when it
    # stopped following the shipment for good (after it finished).
    checked_at: Mapped[str | None] = mapped_column(String(40))
    discarded_at: Mapped[str | None] = mapped_column(String(40))

    # ----------------------------------------------------------- our own clocks
    enabled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    enabled_by: Mapped[str | None] = mapped_column(String(255))
    # True when enabling found the shipment already in ShipsGo, so no credit
    # was spent; False when a credit was.
    reused: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )
    refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    failures: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    shipment: Mapped["Shipment"] = relationship(back_populates="tracking")

    def __repr__(self) -> str:
        return f"<ShipmentTracking {self.booking_number} #{self.external_id}>"
