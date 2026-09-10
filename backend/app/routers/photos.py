"""A customer viewing photographs of their own material.

Read-only, like the rest of the customer half. Ownership is walked all the
way up (photo -> shipment -> order -> customer) and compared with the
customer on the token, exactly as documents are. Anything that is not the
caller's own photo answers 404, so the endpoint never reveals that another
customer's photo exists.
"""

from fastapi import APIRouter
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.core.deps import DbSession, SettledUser, not_found
from app.models import Order, Photo, Shipment
from app.services import storage

router = APIRouter()


@router.get("/api/photos/{photo_id}")
def get_photo(photo_id: int, current_user: SettledUser, db: DbSession) -> FileResponse:
    """Send back one photo image.

    Served with the type worked out from the file's suffix when it was
    uploaded, not with whatever the uploading browser claimed and not
    hard-coded — the gallery has to render JPGs and PNGs alike.
    """
    photo = db.scalar(
        select(Photo)
        .join(Shipment, Photo.shipment_id == Shipment.id)
        .join(Order, Shipment.order_id == Order.id)
        .where(
            Photo.id == photo_id,
            Order.customer_id == current_user.customer_id,
        )
    )
    if photo is None:
        raise not_found("Photo not found.")

    path = storage.resolve(photo.stored_path or "")
    if path is None:
        # The row is there but the file is not. An orphaned row rather than
        # an orphaned file: rare, and worth saying plainly.
        raise not_found("This photo is no longer available.")

    return FileResponse(
        path,
        media_type=photo.content_type or "image/jpeg",
        filename=photo.file_name,
    )
