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

Since step 33 the API also sends on a timer by itself (NOTIFY_EVERY_MINUTES)
and staff can press Send now on the Messages screen, so this is no longer the
only way anything goes out. It stays because a command that can be run over
SSH, with --dry-run, is the right tool when something looks wrong.
"""

import argparse
import sys

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

        if args.dry_run:
            for shipment, order, customer, user in todo:
                mark = (
                    "would send"
                    if notifications.would_send_to(user.email)
                    else "would suppress"
                )
                print(
                    f"  [{mark}] {user.email:<32} {order.sales_order_no} "
                    f"{shipment.shipment_no} ({shipment.status})"
                )
            print("\nDry run — nothing was sent and nothing was recorded.")
            return 0

        def show(shipment, order, customer, user, outcome, detail):
            note = f" — {detail}" if detail else ""
            print(
                f"  [{outcome}] {user.email:<32} {order.sales_order_no} "
                f"{shipment.shipment_no} ({shipment.status}){note}"
            )

        # The sending loop itself lives in the service, because the timer in
        # the API and the Send now button need exactly the same loop and
        # neither can import a script to get it.
        counts = notifications.run(session, on_result=show)

        print(
            f"\nsent {counts['sent']}, suppressed {counts['suppressed']}, "
            f"failed {counts['failed']}"
        )
        return 1 if counts["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
