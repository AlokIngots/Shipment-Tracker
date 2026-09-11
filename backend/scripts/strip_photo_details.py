"""Remove the hidden details from material photos uploaded before that was done.

    python -m scripts.strip_photo_details --dry-run   # count them, change nothing
    python -m scripts.strip_photo_details             # clean them

Photos uploaded from now on lose their hidden details -- camera, time, GPS
position -- when they are uploaded. This is for the ones uploaded before.
Until it runs, a customer who opens one of those full size downloads the
details with it.

Safe to run as often as you like: a photo with nothing hidden in it is left
exactly as it is, so a second run does nothing.
"""

import argparse
import sys

from app.core.database import SessionLocal
from app.services import photos


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Remove hidden details from material photos that still have them."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="count the photos that still have them, change nothing")
    args = parser.parse_args()

    with SessionLocal() as session:
        counts = photos.clean_existing(session, dry_run=args.dry_run)

    if args.dry_run:
        print(f"{counts['cleaned']} photo(s) would have their hidden details removed.")
    else:
        print(f"Removed the hidden details from {counts['cleaned']} photo(s).")
    print(f"{counts['already_clean']} photo(s) had none.")
    if counts["file_missing"]:
        print(f"{counts['file_missing']} photo(s) skipped: the picture itself is "
              "missing from the storage directory.")
    if counts["unreadable"]:
        print(f"{counts['unreadable']} photo(s) skipped: the picture could not be "
              "read to its end, so it still has its details. Remove it on the "
              "staff screen and upload it again.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
