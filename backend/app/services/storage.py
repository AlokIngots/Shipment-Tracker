"""Where customer documents live on disk.

Files are stored outside the repository, under a directory named by
DOCUMENT_STORAGE_DIR in .env (default: <project>/storage/documents).

Every stored file is given a random name. The customer's own file name is
kept in the database and only used to name the download, so nothing a user
supplies is ever used to build a path. That removes any chance of a crafted
name reaching outside the storage directory.
"""

import secrets
import shutil
from pathlib import Path

from app.core.config import STORAGE_DIR


def ensure_storage() -> Path:
    """Create the storage directory if it is not there yet."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    return STORAGE_DIR


def store_file(source: Path) -> str:
    """Copy a document into storage under a random name.

    Returns the stored name, which is what goes in Document.stored_path.
    The file must really be a PDF, JPG or PNG, whatever its name says, and
    is stored under the suffix of what it really is; see document_suffix.
    """
    with open(source, "rb") as fh:
        suffix = document_suffix(fh.read(len(_PNG_MAGIC)))
    if suffix is None:
        raise UploadRejected(NOT_A_DOCUMENT)
    ensure_storage()
    stored_name = f"{secrets.token_hex(16)}{suffix}"
    shutil.copyfile(source, STORAGE_DIR / stored_name)
    return stored_name


# What a staff upload may be. Documents are PDFs; a mill test certificate is
# sometimes a scan, so images are allowed too. Anything else is refused -
# this is the only route by which a browser can put a file on the server.
ALLOWED_SUFFIXES = {".pdf", ".jpg", ".jpeg", ".png"}
ALLOWED_TYPES = {"application/pdf", "image/jpeg", "image/png"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB


class UploadRejected(Exception):
    """An upload that will not be stored, with a reason a person can read."""


# What the first bytes of each kind of document are. The name and the
# browser's stated type are both only claims; these bytes are the file.
# A photo gets a stricter check still (it is opened and re-saved, see
# services/photos.py); a document is stored as it came, so this is its check.
_PDF_MAGIC = b"%PDF-"
_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

NOT_A_DOCUMENT = (
    "That file is not really a PDF, JPG or PNG, whatever its name says. "
    "Save or export it as a PDF and upload that."
)


def document_suffix(head: bytes) -> str | None:
    """The suffix a document should be stored under, from its first bytes.

    None when it is none of the three. A PNG named .jpg comes back as .png,
    so it is later served as what it is rather than as what it was called.
    """
    if head.startswith(_PDF_MAGIC):
        return ".pdf"
    if head.startswith(_PNG_MAGIC):
        return ".png"
    if head.startswith(_JPEG_MAGIC):
        return ".jpg"
    return None


def check_upload(file_name: str, content_type: str | None) -> str:
    """Check a file may be uploaded. Returns its suffix, or raises."""
    suffix = Path(file_name or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise UploadRejected(
            "Only PDF, JPG and PNG files can be uploaded."
        )
    # The browser's stated type is a hint, not proof, so it is checked as
    # well as the suffix rather than instead of it.
    if content_type and content_type.split(";")[0].strip() not in ALLOWED_TYPES:
        raise UploadRejected("That file does not look like a PDF or an image.")
    return suffix


# A material photo is a photograph, not a document. Allowing a PDF here
# would let one arrive in the customer's photo gallery, where the browser
# would try to render it as an image and show a broken picture instead.
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
IMAGE_TYPES = {"image/jpeg", "image/png"}

# The media type to serve a stored file back as, worked out from the suffix
# rather than trusted from the browser that uploaded it. A stored name is
# random plus the original suffix, so the suffix here is one this module
# accepted at upload and not anything a person typed.
_TYPE_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".pdf": "application/pdf",
}


def media_type_for(stored_path: str) -> str:
    """What a stored document really is.

    Documents were served as application/pdf whatever they were, so a Mill
    Test Certificate scanned as a JPG arrived labelled as a PDF and would
    not open. Anything unrecognised is sent as a plain download rather than
    guessed at.
    """
    return _TYPE_BY_SUFFIX.get(Path(stored_path or "").suffix.lower(), "application/octet-stream")


def check_image_upload(file_name: str, content_type: str | None) -> tuple[str, str]:
    """Check a file may be uploaded as a photo. Returns (suffix, media type).

    The media type comes back from the suffix, not from what the browser
    claimed, because it is stored and later used to serve the file. A
    browser's word is good enough to refuse an upload on and not good enough
    to repeat back to somebody else's browser.
    """
    suffix = Path(file_name or "").suffix.lower()
    if suffix not in IMAGE_SUFFIXES:
        raise UploadRejected("A photo must be a JPG or a PNG file.")
    if content_type and content_type.split(";")[0].strip() not in IMAGE_TYPES:
        raise UploadRejected("That file does not look like a photograph.")
    return suffix, _TYPE_BY_SUFFIX[suffix]


def store_upload(stream, suffix: str) -> str:
    """Write an uploaded file into storage under a random name.

    Copied in chunks and abandoned the moment it goes over the size limit,
    so an enormous upload cannot fill the disk before anyone notices.
    """
    ensure_storage()
    stored_name = f"{secrets.token_hex(16)}{suffix}"
    target = STORAGE_DIR / stored_name

    written = 0
    try:
        with open(target, "wb") as out:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    raise UploadRejected(
                        f"That file is larger than "
                        f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
                    )
                out.write(chunk)
    except Exception:
        target.unlink(missing_ok=True)
        raise

    if written == 0:
        target.unlink(missing_ok=True)
        raise UploadRejected("That file is empty.")

    return stored_name


def store_document(stream, claimed_suffix: str) -> str:
    """Store an uploaded document, refusing one that is not what it claims.

    Written first (with the size limit and the empty-file check of
    store_upload), then its first bytes are read back. Something that is
    not a PDF, JPG or PNG is deleted and refused; one whose name says the
    wrong kind -- a PNG called .jpg -- is kept under its real suffix.
    """
    stored_name = store_upload(stream, claimed_suffix)
    target = STORAGE_DIR / stored_name
    with open(target, "rb") as fh:
        real = document_suffix(fh.read(len(_PNG_MAGIC)))
    if real is None:
        target.unlink(missing_ok=True)
        raise UploadRejected(NOT_A_DOCUMENT)
    if real != claimed_suffix and not (real == ".jpg" and claimed_suffix == ".jpeg"):
        renamed = f"{Path(stored_name).stem}{real}"
        target.rename(STORAGE_DIR / renamed)
        stored_name = renamed
    return stored_name


def delete(stored_name: str) -> bool:
    """Remove a stored file. True if there was one to remove."""
    path = resolve(stored_name)
    if path is None:
        return False
    path.unlink()
    return True


def resolve(stored_name: str) -> Path | None:
    """Return the full path of a stored file, or None if it is not there.

    Refuses anything that does not resolve to a direct child of the storage
    directory, so a bad value in the database cannot read arbitrary files.
    """
    if not stored_name:
        return None

    candidate = (STORAGE_DIR / stored_name).resolve()
    if candidate.parent != STORAGE_DIR or not candidate.is_file():
        return None
    return candidate
