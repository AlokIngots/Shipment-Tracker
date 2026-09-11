"""Admin console: photographs of the material in a shipment.

Separate from admin/documents.py because the two behave differently, and
the difference is the whole reason photos got their own table. Uploading a
Packing List replaces the Packing List. Uploading a photo adds a photo:
several arrive at once, none replaces another, and each is removed on its
own.
"""

from typing import Annotated

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import DbSession, StaffUser, bad_request, not_found
from app.models import Photo, Shipment
from app.schemas import StaffPhotoOut, StaffShipmentPhotosOut
from app.services import audit, storage

router = APIRouter(prefix="/api/staff")

# One upload can carry a whole batch, because that is how photos arrive:
# somebody selects everything they took of a shipment at once. Capped so a
# single request cannot tie the server up indefinitely.
MAX_PHOTOS_PER_UPLOAD = 20


def photos_response(shipment: Shipment) -> StaffShipmentPhotosOut:
    """Every photo on a shipment, oldest first, as staff see them."""
    return StaffShipmentPhotosOut(
        shipment_id=shipment.id,
        shipment_no=shipment.shipment_no,
        photos=[
            StaffPhotoOut.model_validate(p)
            for p in sorted(shipment.photos, key=lambda p: p.id)
        ],
    )


def load_shipment(shipment_id: int, db: DbSession) -> Shipment:
    shipment = db.scalar(
        select(Shipment)
        .where(Shipment.id == shipment_id)
        .options(selectinload(Shipment.photos))
    )
    if shipment is None:
        raise not_found("Shipment not found.")
    return shipment


@router.get("/shipments/{shipment_id}/photos", response_model=StaffShipmentPhotosOut)
def staff_list_photos(
    shipment_id: int, staff: StaffUser, db: DbSession
) -> StaffShipmentPhotosOut:
    """The photos already on a shipment."""
    return photos_response(load_shipment(shipment_id, db))


@router.post(
    "/shipments/{shipment_id}/photos",
    response_model=StaffShipmentPhotosOut,
    status_code=201,
)
def staff_upload_photos(
    shipment_id: int,
    staff: StaffUser,
    db: DbSession,
    files: Annotated[list[UploadFile], File()],
    caption: Annotated[str | None, Form()] = None,
) -> StaffShipmentPhotosOut:
    """Add one or more photos to a shipment.

    All or nothing. If the fourth of five files is a PDF, none of the five
    is kept and the message says which one was wrong — better than leaving
    somebody to work out which three of five landed.
    """
    shipment = load_shipment(shipment_id, db)

    if not files:
        raise bad_request("Choose at least one photo.")
    if len(files) > MAX_PHOTOS_PER_UPLOAD:
        raise bad_request(
            f"{len(files)} photos at once is too many. "
            f"Please add up to {MAX_PHOTOS_PER_UPLOAD} at a time."
        )

    caption = (caption or "").strip() or None

    # Written to disk first, and only recorded once every one succeeded. A
    # file with no row is an orphan nobody sees; a row with no file is a
    # broken picture in front of a customer, which is worse.
    stored: list[tuple[UploadFile, str, str]] = []
    try:
        for upload in files:
            suffix, media_type = storage.check_image_upload(
                upload.filename or "", upload.content_type
            )
            stored.append(
                (upload, storage.store_upload(upload.file, suffix), media_type)
            )
    except storage.UploadRejected as rejected:
        for _, stored_name, _ in stored:
            storage.delete(stored_name)
        name = files[len(stored)].filename or "that file"
        raise bad_request(f"{name}: {rejected}") from rejected

    for upload, stored_name, media_type in stored:
        db.add(
            Photo(
                shipment_id=shipment.id,
                caption=caption,
                file_name=(upload.filename or "photo")[:255],
                stored_path=stored_name,
                content_type=media_type,
            )
        )
    audit.record(
        db,
        "photo.added",
        f"Added {len(stored)} photo(s) to shipment {shipment.shipment_no}",
        actor=staff,
        changes=[
            {"field": "Photo", "before": None, "after": (upload.filename or "photo")[:255]}
            for upload, _, _ in stored
        ]
        + ([{"field": "Caption", "before": None, "after": caption}] if caption else []),
    )
    db.commit()
    db.refresh(shipment)

    return photos_response(shipment)


@router.get("/photos/{photo_id}")
def staff_get_photo(photo_id: int, staff: StaffUser, db: DbSession) -> FileResponse:
    """The image itself, for the admin console.

    Staff need their own route to it. /api/photos/{id} is the customer's,
    and it depends on SettledUser, which refuses a staff account on purpose
    -- staff belong to no customer, so "your own photos" means nothing for
    them. Without this, staff could upload a photo and not see it.
    """
    photo = db.get(Photo, photo_id)
    if photo is None:
        raise not_found("Photo not found.")

    path = storage.resolve(photo.stored_path or "")
    if path is None:
        raise not_found("This photo is no longer available.")

    return FileResponse(
        path,
        media_type=photo.content_type or "image/jpeg",
        filename=photo.file_name,
    )


@router.delete("/photos/{photo_id}")
def staff_delete_photo(
    photo_id: int, staff: StaffUser, db: DbSession
) -> dict[str, str]:
    """Remove one photo, file and all.

    No "remove those first" rule here, unlike an order or a shipment:
    nothing hangs off a photo, and a photo of the wrong customer's material
    has to be removable in seconds.
    """
    photo = db.get(Photo, photo_id)
    if photo is None:
        raise not_found("Photo not found.")

    shipment = db.get(Shipment, photo.shipment_id)
    audit.record(
        db,
        "photo.removed",
        f"Removed a photo from shipment {shipment.shipment_no}",
        actor=staff,
        changes=[{"field": "Photo", "before": photo.file_name, "after": None}]
        + (
            [{"field": "Caption", "before": photo.caption, "after": None}]
            if photo.caption
            else []
        ),
    )

    storage.delete(photo.stored_path or "")
    db.delete(photo)
    db.commit()
    return {"detail": "Photo removed."}
