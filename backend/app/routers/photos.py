"""A customer viewing photographs of their own material.

Read-only, like the rest of the customer half. Ownership is walked all the
way up (photo -> shipment -> order -> customer) and compared with the
customer on the token, exactly as documents are. Anything that is not the
caller's own photo answers 404, so the endpoint never reveals that another
customer's photo exists. The preview is checked in exactly the same way as
the full picture, by the same function.
"""

from fastapi import APIRouter
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.core.deps import DbSession, SettledUser, not_found
from app.models import Order, Photo, Shipment
from app.services import photos, storage

router = APIRouter()


def own_photo(photo_id: int, current_user, db) -> Photo:
    """The caller's own photo, or the 404 that anything else gets."""
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
    return photo


@router.get("/api/photos/{photo_id}")
def get_photo(photo_id: int, current_user: SettledUser, db: DbSession) -> FileResponse:
    """Send back one photo image.

    Served with the type worked out from the file itself when it was
    uploaded, not with whatever the uploading browser claimed and not
    hard-coded — the gallery has to render JPGs and PNGs alike.
    """
    photo = own_photo(photo_id, current_user, db)

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


@router.get("/api/photos/{photo_id}/thumbnail")
def get_photo_preview(
    photo_id: int, current_user: SettledUser, db: DbSession
) -> FileResponse:
    """The small preview a gallery tile shows. The full picture if it has none."""
    photo = own_photo(photo_id, current_user, db)

    found = photos.file_to_serve(photo, preview=True)
    if found is None:
        raise not_found("This photo is no longer available.")
    path, media_type = found
    return FileResponse(path, media_type=media_type)
