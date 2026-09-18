"""Sign-ins that were ended with Sign out, before they ran out by themselves.

A sign-in token is signed, not stored: the server keeps no list of them, and
until 18 Sep 2026 Sign out only made the browser forget its copy. That was
tolerable while a token lasted 12 hours. At 30 days, a copy taken from a
shared computer or by malware would have kept working for a month after its
owner pressed Sign out.

So each token carries a random id, and Sign out writes that id here. A
token whose id is in this table is refused. A row is only useful until the
token would have expired anyway, so rows past `expires_at` are deleted
whenever a new one is written, and the table stays as small as the number
of sign-outs in the last 30 days.

Only the id is kept, never the token: it signs in nobody.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SignedOutToken(Base):
    """One ended sign-in: which token, whose, and when it would have expired."""

    __tablename__ = "signed_out_tokens"

    # The token's "jti": 22 random URL-safe characters.
    token_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    signed_out_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    def __repr__(self) -> str:
        return f"<SignedOutToken {self.token_id} for user {self.user_id}>"
