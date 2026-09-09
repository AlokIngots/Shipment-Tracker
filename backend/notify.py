"""Tell customers when their shipments move.

Looks for shipments whose status is one worth reporting and which the
customer has not already been told about, then emails the users of that
customer.

    python notify.py --dry-run    # show exactly who would be emailed
    python notify.py              # send (subject to the safety switches)
    python notify.py --preview    # print the full text of one email

Run it after every import. Nobody is ever told the same thing twice: once a
message has actually been sent for a (shipment, status, user) it is never
sent again. An attempt that was suppressed or that failed is retried on the
next run, so nothing is silently lost.

Safety, set in .env:
    SEND_EMAILS=false        default; records and prints, sends nothing
    NOTIFY_ONLY_EMAILS=...   during a pilot, only these addresses get mail
"""

import argparse
import sys

import notifier
from database import SessionLocal
from models import Customer, Notification, Order, Shipment, User
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError


def pending(session):
    """Every (shipment, order, customer, user) still owed a notification."""
    rows = session.execute(
        select(Shipment, Order, Customer, User)
        .join(Order, Shipment.order_id == Order.id)
        .join(Customer, Order.customer_id == Customer.id)
        .join(User, User.customer_id == Customer.id)
        .where(
            Shipment.status.in_(notifier.NOTIFIABLE_STATUSES),
            User.is_active.is_(True),
        )
        .order_by(Shipment.id, User.id)
    ).all()

    # Only a message that genuinely went out counts as done. An attempt that
    # was suppressed (SEND_EMAILS off, or not on the pilot list) or that
    # failed must be tried again on the next run — otherwise switching
    # SEND_EMAILS on would silently skip every shipment recorded while it
    # was off, and a bounced email would never be retried.
    already = {
        (n.shipment_id, n.event, n.user_id)
        for n in session.scalars(
            select(Notification).where(Notification.outcome == "sent")
        )
    }

    return [
        (shipment, order, customer, user)
        for shipment, order, customer, user in rows
        if (shipment.id, shipment.status, user.id) not in already
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Send shipment notifications.")
    parser.add_argument("--dry-run", action="store_true",
                        help="list who would be emailed, record nothing")
    parser.add_argument("--preview", action="store_true",
                        help="print the full text of the first email and stop")
    args = parser.parse_args()

    with SessionLocal() as session:
        todo = pending(session)

        if not todo:
            print("Nothing to send. Every customer is up to date.")
            return 0

        if args.preview:
            shipment, order, customer, user = todo[0]
            message = notifier.build_message(user, customer, order, shipment)
            print(f"To: {message['To']}")
            print(f"Subject: {message['Subject']}")
            print("-" * 60)
            print(message.get_content())
            return 0

        print(f"{len(todo)} notification(s) to send")
        if not notifier.SEND_EMAILS:
            print("SEND_EMAILS is off — nothing will actually be emailed.")
        elif notifier.NOTIFY_ONLY_EMAILS:
            print(f"Pilot mode — only {', '.join(notifier.NOTIFY_ONLY_EMAILS)} "
                  "will receive real mail.")
        print()

        counts = {"sent": 0, "suppressed": 0, "failed": 0}

        for shipment, order, customer, user in todo:
            message = notifier.build_message(user, customer, order, shipment)

            if args.dry_run:
                mark = "would send" if notifier.would_send_to(user.email) else "would suppress"
                print(f"  [{mark}] {user.email:<32} {order.sales_order_no} "
                      f"{shipment.shipment_no} ({shipment.status})")
                continue

            outcome, detail = notifier.send(message)
            counts[outcome] += 1

            # An earlier attempt may already have left a row here, recorded
            # as suppressed or failed. Update that row instead of inserting
            # a second one, so the unique constraint still guarantees one
            # record per (shipment, status, user) and nobody is told twice.
            record = session.scalar(
                select(Notification).where(
                    Notification.shipment_id == shipment.id,
                    Notification.event == shipment.status,
                    Notification.user_id == user.id,
                )
            )
            if record is None:
                record = Notification(
                    shipment_id=shipment.id,
                    user_id=user.id,
                    event=shipment.status,
                    channel="email",
                )
                session.add(record)
            record.outcome = outcome
            record.detail = detail

            try:
                session.commit()
            except IntegrityError:
                # Another run inserted the same row a moment ago; that is
                # exactly what the unique constraint is for.
                session.rollback()
                continue

            note = f" — {detail}" if detail else ""
            print(f"  [{outcome}] {user.email:<32} {order.sales_order_no} "
                  f"{shipment.shipment_no} ({shipment.status}){note}")

        if args.dry_run:
            print("\nDry run — nothing was sent and nothing was recorded.")
            return 0

        print(f"\nsent {counts['sent']}, suppressed {counts['suppressed']}, "
              f"failed {counts['failed']}")
        return 1 if counts["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
