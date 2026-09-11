"""Material photos: making sure an upload is a picture, removing its hidden
details, and making its preview.

The gallery used to download every photo at full size to draw a tile about a
hundred pixels wide. Twenty photos from a phone are easily 80 MB, and an
export customer is often on a slow connection. Each photo now gets a small
JPEG copy when it is uploaded, and the tiles load that; clicking a tile opens
the full-size photo.

Phone photos carry hidden details -- the camera, the time, and often the GPS
position where they were taken, which for these photos is the factory.
Neither the full-size photo nor the preview a customer can download carries
any of them: both are stored without them from the moment of upload.

The preview is also upright. Phones store a picture sideways plus a note
saying which way is up; a browser drawing the raw file sometimes ignores the
note.

Nothing here knows about HTTP. The routers decide what to answer; this module
only works out which file that is.
"""

from io import BytesIO
from pathlib import Path

from PIL import ExifTags, Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select

from app.models import Photo
from app.services import storage

# The longest side of a preview, in pixels. A tile is about 116 pixels wide;
# 400 keeps it sharp on a phone or laptop screen that packs three pixels
# into each one, and is still a small fraction of the original.
PREVIEW_LONG_EDGE = 400
PREVIEW_QUALITY = 80

# What Pillow calls a format, and the media type it is served as. MPO is a
# JPEG with a second picture tucked in after the first -- many iPhones and
# Samsungs save photos that way -- and a browser shows it as a plain JPEG.
_MEDIA_TYPES = {"JPEG": "image/jpeg", "MPO": "image/jpeg", "PNG": "image/png"}

# What Pillow cannot read a picture with, whichever way it fails.
_UNREADABLE = (
    UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError
)

NOT_A_PICTURE = (
    "that file is not a picture this portal can read. A photo must be a real "
    "JPG or PNG; an iPhone HEIC photo renamed to .jpg, for example, is not one."
)

CUT_SHORT = (
    "that picture stops before its end, so it cannot be shown. It was probably "
    "cut short while being copied; copy it from the phone again."
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


# ------------------------------------------------------------ hidden details

# The parts of a JPEG that say how to draw it and nothing else: the JFIF
# header, the colour profile, and Adobe's colour note, which a CMYK file
# needs. Anything else -- EXIF, XMP, IPTC, a comment, a second picture --
# counts as a hidden detail. A list of what may stay, not of what must go,
# so a kind of detail nobody thought of goes too.
_PLAIN_JPEG_SEGMENTS = (
    ("APP0", b"JFIF"),
    ("APP2", b"ICC_PROFILE"),
    ("APP14", b"Adobe"),
)

# A JPEG that is already upright is saved again with its own compression
# settings, which changes nothing a person can see. One that has to be
# turned cannot keep them -- turning makes a new picture, not the original
# JPEG -- and is saved at this quality instead.
UPRIGHT_QUALITY = 95


def _carries_details(image: Image.Image) -> bool:
    if image.getexif():
        return True
    if image.format in ("JPEG", "MPO"):
        if getattr(image, "n_frames", 1) > 1:
            return True
        return not all(
            any(marker == name and data.startswith(start) for name, start in _PLAIN_JPEG_SEGMENTS)
            for marker, data in image.applist
        )
    # A PNG keeps its notes, XMP among them, as text. EXIF is covered above.
    return bool(getattr(image, "text", None))


def has_hidden_details(path: Path | None) -> bool | None:
    """Whether a stored picture still carries hidden details. None if unreadable."""
    if path is None:
        return None
    try:
        with Image.open(path) as image:
            return _carries_details(image)
    except _UNREADABLE:
        return None


def remove_hidden_details(path: Path) -> str | None:
    """Store a copy of a picture without its hidden details. Returns its stored name.

    Returns None when there is nothing to remove: a clean picture is left
    exactly as it is, byte for byte, rather than saved again for nothing.
    The copy is upright, so turning it no longer depends on a detail that
    has gone. The colour profile stays, because it changes how the colours
    look and says nothing about where the photo was taken.

    Raises UploadRejected if the picture cannot be read to its end. It is
    not kept with its details instead: the point is that none reach a
    customer.

    The caller removes the old file, once nothing points at it any more.
    """
    try:
        with Image.open(path) as original:
            if not _carries_details(original):
                return None

            keep = {}
            if icc_profile := original.info.get("icc_profile"):
                keep["icc_profile"] = icc_profile
            orientation = original.getexif().get(ExifTags.Base.Orientation, 1)
            buffer = BytesIO()

            if original.format == "PNG":
                # Text notes and EXIF are written only when asked for, and
                # nothing asks. Transparency is kept.
                ImageOps.exif_transpose(original).save(buffer, "PNG", **keep)
            elif original.format == "JPEG" and orientation not in range(2, 9):
                # Saving copies a comment across unless it has gone first.
                original.info.pop("comment", None)
                original.save(buffer, "JPEG", quality="keep", **keep)
            else:
                # Sideways, or an MPO, whose second picture is left behind.
                image = ImageOps.exif_transpose(original)
                image.info.pop("comment", None)
                image.save(buffer, "JPEG", quality=UPRIGHT_QUALITY, **keep)
    except _UNREADABLE as error:
        raise storage.UploadRejected(CUT_SHORT) from error

    buffer.seek(0)
    return storage.store_upload(buffer, path.suffix.lower())


def clean_existing(session, *, dry_run: bool = False) -> dict[str, int]:
    """Remove the hidden details from every stored photo that still has them.

    For photos uploaded before details were removed at upload. Safe to run
    again: a clean photo is left alone. Each photo is saved as soon as it is
    done, and its old file removed only once the photo points at the clean
    copy, so a run stopped halfway leaves every photo showing.

    Not recorded in the activity record: the picture is the same picture,
    and nothing anybody decided has changed.
    """
    counts = {"cleaned": 0, "already_clean": 0, "file_missing": 0, "unreadable": 0}
    for photo in list(session.scalars(select(Photo).order_by(Photo.id))):
        path = storage.resolve(photo.stored_path or "")
        if path is None:
            counts["file_missing"] += 1
            continue

        if dry_run:
            found = has_hidden_details(path)
            counts[{True: "cleaned", False: "already_clean", None: "unreadable"}[found]] += 1
            continue

        try:
            cleaned = remove_hidden_details(path)
        except storage.UploadRejected:
            counts["unreadable"] += 1
            continue
        if cleaned is None:
            counts["already_clean"] += 1
            continue

        old_name = photo.stored_path
        photo.stored_path = cleaned
        session.commit()
        storage.delete(old_name)
        counts["cleaned"] += 1

    return counts


# ------------------------------------------------------------------ previews


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
    except _UNREADABLE:
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
