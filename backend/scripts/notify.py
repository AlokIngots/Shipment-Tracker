"""Tell customers when their shipments move.

    python -m scripts.notify --dry-run    # show exactly who would be emailed
    python -m scripts.notify              # send (subject to the safety switches)
    python -m scripts.notify --preview    # print the full text of one email

Run it after every import. Nobody is ever told the same thing twice: once a
message has actually been sent for a (shipment, status, user) it is never
sent again. An attempt that was suppressed or that failed is retried on the
next run, so nothing is silently lost.

Safety, set in .env:
    SEND_EMAILS=false        default; records and prints, sends nothing
    NOTIFY_ONLY_EMAILS=...   during a pilot, only these addresses get mail

All the deciding and sending is in app/services/notifications.py. This file
only reads the arguments and prints what happened.
"""

import argparse
import sys

from sqlalchemy.exc import IntegrityError

from app.core.config import NOTIFY_ONLY_EMAILS, SEND_EMAILS
from app.core.database import SessionLocal
from app.services import notifications


def main() -> int:
    parser = argparse.ArgumentParser(description="Send shipment notifications.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="list who would be emailed, record nothing",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="print the full text of the first email and stop",
    )
    args = parser.parse_args()

    with SessionLocal() as session:
        todo = notifications.pending(session)

        if not todo:
            print("Nothing to send. Every customer is up to date.")
            return 0

        if args.preview:
            shipment, order, customer, user = todo[0]
            message = notifications.build_message(user, customer, order, shipment)
            print(f"To: {message['To']}")
            print(f"Subject: {message['Subject']}")
            print("-" * 60)
            print(message.get_content())
            return 0

        print(f"{len(todo)} notification(s) to send")
        if not SEND_EMAILS:
            print("SEND_EMAILS is off — nothing will actually be emailed.")
        elif NOTIFY_ONLY_EMAILS:
            print(
                f"Pilot mode — only {', '.join(NOTIFY_ONLY_EMAILS)} "
                "will receive real mail."
            )
        print()

        counts = {"sent": 0, "suppressed": 0, "failed": 0}

        for shipment, order, customer, user in todo:
            message = notifications.build_message(user, customer, order, shipment)

            if args.dry_run:
                mark = (
                    "would send"
                    if notifications.would_send_to(user.email)
                    else "would suppress"
                )
                print(
                    f"  [{mark}] {user.email:<32} {order.sales_order_no} "
                    f"{shipment.shipment_no} ({shipment.status})"
                )
                continue

            outcome, detail = notifications.send(message)
            counts[outcome] += 1
            notifications.record_outcome(session, shipment, user, outcome, detail)

            try:
                session.commit()
            except IntegrityError:
                # Another run inserted the same row a moment ago; that is
                # exactly what the unique constraint is for.
                session.rollback()
                continue

            note = f" — {detail}" if detail else ""
            print(
                f"  [{outcome}] {user.email:<32} {order.sales_order_no} "
                f"{shipment.shipment_no} ({shipment.status}){note}"
            )

        if args.dry_run:
            print("\nDry run — nothing was sent and nothing was recorded.")
            return 0

        print(
            f"\nsent {counts['sent']}, suppressed {counts['suppressed']}, "
            f"failed {counts['failed']}"
        )
        return 1 if counts["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
