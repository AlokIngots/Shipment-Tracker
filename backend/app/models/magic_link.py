"""A single-use sign-in link, emailed to somebody who asked for one.

Only a hash of the token is kept. The token itself exists in exactly two
places: the email, and the browser of whoever opens it. Somebody who reads
this table -- a backup, a leaked copy of the database -- gets nothing they
can sign in with.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MagicLink(Base):
    """One link: whose it is, when it stops working, and whether it has."""

    __tablename__ = "magic_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Customer or staff: a link signs in whoever the account belongs to.
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # SHA-256 of the token, in hex. A plain hash rather than the slow one a
    # password gets: the token is 256 random bits, so there is nothing to
    # guess and nothing a slow hash would add.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # Set by the application's clock, not the database's, so that it can be
    # compared with expires_at and password_changed_at, which are too.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Set the moment the link is used, or when a newer one replaces it. Once
    # set, the link never works again.
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    def __repr__(self) -> str:
        return f"<MagicLink {self.id} for user {self.user_id}>"
