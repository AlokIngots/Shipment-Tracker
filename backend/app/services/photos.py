"""Material photos: making sure an upload is a picture, and making its preview.

The gallery used to download every photo at full size to draw a tile about a
hundred pixels wide. Twenty photos from a phone are easily 80 MB, and an
export customer is often on a slow connection. Each photo now gets a small
JPEG copy when it is uploaded, and the tiles load that; clicking a tile still
opens the photo exactly as it was uploaded.

The preview is also:

  * upright. Phones store a picture sideways plus a note saying which way is
    up; a browser drawing the raw file sometimes ignores the note.
  * stripped. Phone photos carry hidden details -- the camera, the time, and
    often the GPS position where they were taken. The preview carries none.
    The full-size original still does; see "Known issues" in CLAUDE.md.

Nothing here knows about HTTP. The routers decide what to answer; this module
only works out which file that is.
"""

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select

from app.models import Photo
from app.services import storage

# The longest side of a preview, in pixels. A tile is about 116 pixels wide;
# 400 keeps it sharp on a phone or laptop screen that packs three pixels
# into each one, and is still a small fraction of the original.
PREVIEW_LONG_EDGE = 400
PREVIEW_QUALITY = 80

# What Pillow calls a format, and the media type it is served as.
_MEDIA_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png"}

NOT_A_PICTURE = (
    "that file is not a picture this portal can read. A photo must be a real "
    "JPG or PNG; an iPhone HEIC photo renamed to .jpg, for example, is not one."
)


def inspect_picture(path: Path | None) -> str:
    """The media type a stored upload really is. Raises UploadRejected if it
    is not a JPG or PNG picture at all.

    The name and the browser's claim are both checked before this, in
    storage.check_image_upload, and both are easy to get wrong or to fake:
    a PDF renamed to .jpg passes the pair of them. Opening the file is the
    only check that knows. And the type returned is what the file is, not
    what it is called, so a PNG saved as .jpg is still served as a PNG.
    """
    if path is None:
        raise storage.UploadRejected(NOT_A_PICTURE)
    try:
        with Image.open(path) as image:
            media_type = _MEDIA_TYPES.get(image.format)
            image.verify()
    except Image.DecompressionBombError as error:
        raise storage.UploadRejected(
            "that picture has too many pixels to be processed safely."
        ) from error
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as error:
        raise storage.UploadRejected(NOT_A_PICTURE) from error

    if media_type is None:
        raise storage.UploadRejected(NOT_A_PICTURE)
    return media_type


def make_preview(path: Path | None) -> str | None:
    """Store a small, upright JPEG copy of a picture. Returns its stored name.

    Returns None rather than raising if it cannot be made: a photo with no
    preview still shows, full size, and that is better than refusing an
    upload over a thumbnail.
    """
    if path is None:
        return None
    try:
        with Image.open(path) as original:
            image = ImageOps.exif_transpose(original)
            image.thumbnail((PREVIEW_LONG_EDGE, PREVIEW_LONG_EDGE))
            if image.mode != "RGB":
                # JPEG has no transparency. Laid onto white, because the
                # alternative Pillow picks is black.
                with_alpha = image.convert("RGBA")
                image = Image.new("RGB", with_alpha.size, "white")
                image.paste(with_alpha, mask=with_alpha.getchannel("A"))
            buffer = BytesIO()
            # No exif= argument, so none of the original's hidden details
            # are written into the copy.
            image.save(buffer, "JPEG", quality=PREVIEW_QUALITY, optimize=True)
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        return None

    buffer.seek(0)
    return storage.store_upload(buffer, ".jpg")


def file_to_serve(photo: Photo, *, preview: bool) -> tuple[Path, str] | None:
    """Which file to send for a photo, and as what type. None if neither exists.

    A preview falls back to the full picture when the photo has none --
    uploaded before previews existed, or one that could not be shrunk -- so
    a missing preview makes a tile slower, never broken.
    """
    if preview:
        path = storage.resolve(photo.thumb_path or "")
        if path is not None:
            return path, "image/jpeg"

    path = storage.resolve(photo.stored_path or "")
    if path is None:
        return None
    return path, photo.content_type or "image/jpeg"


def delete_files(photo: Photo) -> None:
    """Remove a photo's picture and its preview from disk.

    The database removes the row; nothing on disk knows about that, so both
    files have to be removed by hand or they pile up unseen.
    """
    storage.delete(photo.stored_path or "")
    storage.delete(photo.thumb_path or "")


def backfill(session, *, dry_run: bool = False) -> dict[str, int]:
    """Make a preview for every photo that has none. Safe to run again.

    Not recorded in the activity record: a preview is a copy made from a
    photo, and making one changes nothing anybody decided.
    """
    counts = {"made": 0, "file_missing": 0, "unreadable": 0}
    waiting = list(
        session.scalars(select(Photo).where(Photo.thumb_path.is_(None)).order_by(Photo.id))
    )
    for photo in waiting:
        path = storage.resolve(photo.stored_path or "")
        if path is None:
            counts["file_missing"] += 1
            continue
        if dry_run:
            counts["made"] += 1
            continue
        stored_name = make_preview(path)
        if stored_name is None:
            counts["unreadable"] += 1
            continue
        photo.thumb_path = stored_name
        counts["made"] += 1

    if not dry_run:
        session.commit()
    return counts
