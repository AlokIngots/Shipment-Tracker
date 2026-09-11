"""A photograph of the material itself, taken before or during loading.

A separate table from Document on purpose. A document is one file per kind
per shipment — there is one Packing List, and uploading another replaces it.
Photos are the opposite: a shipment has as many as somebody took, none of
them replaces another, and the useful thing about each one is its caption,
not its type. Squeezing them into `documents` would have meant inventing
doc_type values like "Photo 3", and the replace-on-same-type rule would then
have quietly destroyed photos.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Photo(Base):
    """One image of the bars or bundles in a shipment."""

    __tablename__ = "photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    shipment_id: Mapped[int] = mapped_column(
        ForeignKey("shipments.id", ondelete="CASCADE"), index=True
    )
    # What the photo shows, in a few words: "Bundle 12, before wrapping".
    # Optional, because making it required would only produce "photo".
    caption: Mapped[str | None] = mapped_column(String(200))
    # The name the file had on the uploader's machine. Used to label a
    # download and nothing else — never to build a path.
    file_name: Mapped[str] = mapped_column(String(255))
    # The random name it was stored under, inside the storage directory.
    stored_path: Mapped[str] = mapped_column(String(500))
    # Kept so the image can be served back with the right type. Documents
    # were always assumed to be PDFs; a photo cannot be.
    content_type: Mapped[str] = mapped_column(String(100), default="image/jpeg")
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    shipment: Mapped["Shipment"] = relationship(back_populates="photos")

    def __repr__(self) -> str:
        return f"<Photo {self.id} on shipment {self.shipment_id}>"
