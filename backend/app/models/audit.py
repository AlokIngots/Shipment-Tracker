"""A record of every change made to the portal's data, and who made it.

Append-only. Nothing in the application updates or deletes a row here, and
migration 0006 puts a trigger on the table that refuses UPDATE, DELETE and
TRUNCATE from anybody, so a stolen staff session cannot tidy its own tracks
away. Somebody with a shell on the database server still could -- by
dropping the trigger first -- which is why the backups matter too.

There is deliberately no foreign key to users. The email is copied onto the
row at the moment of the change, so the record still reads correctly if the
account is later deactivated or removed with SQL -- and a foreign key's
ON DELETE SET NULL would be an UPDATE the trigger refuses.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditEvent(Base):
    """One change: when, who, how, and what it was before and after."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    happened_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Who. Both empty when the change came from a command run on the server,
    # where there is no signed-in person to name.
    actor_user_id: Mapped[int | None] = mapped_column(Integer)
    actor_email: Mapped[str | None] = mapped_column(String(255))
    # How it arrived: "screen", "command line" or "csv import".
    source: Mapped[str] = mapped_column(String(20))
    # What kind of change, for a machine: "order.updated", "photo.removed".
    action: Mapped[str] = mapped_column(String(40))
    # The same, for a person: "Changed shipment X on order Y".
    summary: Mapped[str] = mapped_column(String(300))
    # Each field that changed, as
    # [{"field": "Status", "before": "Packed", "after": "Shipped"}].
    changes: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)

    def __repr__(self) -> str:
        return f"<AuditEvent {self.id} {self.action}>"
