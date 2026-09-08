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
