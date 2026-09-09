"""Where customer documents live on disk.

Files are stored outside the repository, under a directory named by
DOCUMENT_STORAGE_DIR in .env (default: <project>/storage/documents).

Every stored file is given a random name. The customer's own file name is
kept in the database and only used to name the download, so nothing a user
supplies is ever used to build a path. That removes any chance of a crafted
name reaching outside the storage directory.
"""

import os
import secrets
import shutil
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

STORAGE_DIR = Path(
    os.getenv("DOCUMENT_STORAGE_DIR") or (PROJECT_ROOT / "storage" / "documents")
).resolve()


def ensure_storage() -> Path:
    """Create the storage directory if it is not there yet."""
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    return STORAGE_DIR


def store_file(source: Path) -> str:
    """Copy a file into storage under a random name.

    Returns the stored name, which is what goes in Document.stored_path.
    """
    ensure_storage()
    suffix = source.suffix.lower()[:10]
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
