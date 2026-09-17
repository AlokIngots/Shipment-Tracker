"""Make the small preview for every material photo that does not have one.

    python -m scripts.make_thumbnails --dry-run   # count them, change nothing
    python -m scripts.make_thumbnails             # make them

Photos uploaded from now on get their preview when they are uploaded. This is
for the ones uploaded before previews existed. Until it runs, those photos
still show -- the gallery falls back to the full picture -- only slowly.

Safe to run as often as you like: a photo that already has a preview is
skipped, so a second run does nothing.
"""

import argparse
import sys

from app.core.database import SessionLocal
from app.services import photos


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Make previews for material photos that have none."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="count the photos that need one, change nothing")
    args = parser.parse_args()

    with SessionLocal() as session:
        counts = photos.backfill(session, dry_run=args.dry_run)

    if args.dry_run:
        print(f"{counts['made']} photo(s) would get a preview.")
    else:
        print(f"Made {counts['made']} preview(s).")
    if counts["file_missing"]:
        print(f"{counts['file_missing']} photo(s) skipped: the picture itself is "
              "missing from the storage directory.")
    if counts["unreadable"]:
        print(f"{counts['unreadable']} photo(s) skipped: the picture could not be "
              "read. They still show, full size.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
