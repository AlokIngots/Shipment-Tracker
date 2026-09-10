"""Sending notifications to customers.

Email only for now. WhatsApp needs a WhatsApp Business account and an
approved template through a provider such as Twilio or Meta's Cloud API;
the shape below (build a message, hand it to a channel, record the outcome)
is what a WhatsApp channel would slot into.

Two safety switches exist because the cost of a mistake here is emailing a
real customer something wrong:

    SEND_EMAILS=false        nothing is actually sent; every message is
                             recorded as "suppressed" and printed instead.
                             This is the default.

    NOTIFY_ONLY_EMAILS=a@b   during a pilot, only these addresses receive
                             real mail. Everyone else is suppressed. Leave
                             blank once you genuinely want to mail everyone.
"""

import smtplib
from email.message import EmailMessage

from sqlalchemy import select

from app.core.config import (
    NOTIFIABLE_STATUSES,
    NOTIFY_ONLY_EMAILS,
    PORTAL_URL,
    SEND_EMAILS,
    SMTP_FROM,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USE_TLS,
    SMTP_USER,
)
from app.models import Customer, Notification, Order, Shipment, User

__all__ = [
    "NOTIFIABLE_STATUSES",
    "build_message",
    "pending",
    "record_outcome",
    "send",
    "subject_for",
    "would_send_to",
]

SUBJECTS = {
    "shipped": "Your order {sales_order_no} has shipped",
    "in transit": "Your order {sales_order_no} is on its way",
    "delivered": "Your order {sales_order_no} has arrived",
}


def subject_for(event: str, sales_order_no: str) -> str:
    template = SUBJECTS.get(
        event.lower(), "Update on your order {sales_order_no}"
    )
    return template.format(sales_order_no=sales_order_no)


def build_message(user, customer, order, shipment) -> EmailMessage:
    """Compose the email for one shipment update."""
    event = shipment.status or "Updated"
    greeting = (user.full_name or "").strip() or "Hello"

    lines = [
        f"{greeting},",
        "",
        f"There is an update on your order {order.sales_order_no}.",
        "",
        f"  Shipment      {shipment.shipment_no}",
        f"  Status        {event}",
    ]
    if shipment.dispatched_qty is not None:
        lines.append(f"  Quantity      {shipment.dispatched_qty} {shipment.unit or ''}".rstrip())
    if shipment.vessel_name:
        lines.append(f"  Vessel        {shipment.vessel_name}")
    if shipment.imo_number:
        lines.append(f"  IMO           {shipment.imo_number}")
    if shipment.etd:
        lines.append(f"  Departed      {shipment.etd:%d %b %Y}")
    if shipment.eta:
        lines.append(f"  Expected      {shipment.eta:%d %b %Y}")
    if order.customer_po:
        lines.append(f"  Your PO       {order.customer_po}")

    lines += [
        "",
        f"You can see the full order, part-shipments and documents here:",
        f"  {PORTAL_URL}",
        "",
        "This is an automated message from the Alok Ingots customer portal.",
        "Please reply to your usual contact if anything looks wrong.",
        "",
        "Alok Ingots",
        "Stainless steel bright bars, Mumbai, India",
    ]

    message = EmailMessage()
    message["Subject"] = subject_for(event, order.sales_order_no)
    message["From"] = SMTP_FROM
    message["To"] = user.email
    message.set_content("\n".join(lines))
    return message


def would_send_to(email: str) -> bool:
    """Whether a real email may go to this address right now."""
    if not SEND_EMAILS:
        return False
    if NOTIFY_ONLY_EMAILS and email.strip().lower() not in NOTIFY_ONLY_EMAILS:
        return False
    return True


def send(message: EmailMessage) -> tuple[str, str | None]:
    """Deliver a message. Returns (outcome, detail).

    Outcomes: "sent", "suppressed" or "failed". Nothing raises, so one bad
    address cannot stop the rest of a run.
    """
    recipient = message["To"]

    if not SEND_EMAILS:
        return "suppressed", "SEND_EMAILS is off"
    if NOTIFY_ONLY_EMAILS and recipient.strip().lower() not in NOTIFY_ONLY_EMAILS:
        return "suppressed", "not on the NOTIFY_ONLY_EMAILS pilot list"
    if not SMTP_HOST:
        return "failed", "SMTP_HOST is not set"

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as smtp:
            if SMTP_USE_TLS:
                smtp.starttls()
            if SMTP_USER:
                smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(message)
    except Exception as exc:  # noqa: BLE001 - one failure must not stop the run
        return "failed", f"{type(exc).__name__}: {exc}"

    return "sent", None


# --------------------------------------------------------- what is still owed
#
# These two used to live in notify.py. They are logic, not command-line
# plumbing: a scheduled job or an API endpoint that sends notifications needs
# them just as much as the script does, and neither should have to import a
# script to get them.


def pending(session):
    """Every (shipment, order, customer, user) still owed a notification."""
    rows = session.execute(
        select(Shipment, Order, Customer, User)
        .join(Order, Shipment.order_id == Order.id)
        .join(Customer, Order.customer_id == Customer.id)
        .join(User, User.customer_id == Customer.id)
        .where(
            Shipment.status.in_(NOTIFIABLE_STATUSES),
            User.is_active.is_(True),
        )
        .order_by(Shipment.id, User.id)
    ).all()

    # Only a message that genuinely went out counts as done. An attempt that
    # was suppressed (SEND_EMAILS off, or not on the pilot list) or that
    # failed must be tried again on the next run - otherwise switching
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


def record_outcome(session, shipment, user, outcome: str, detail: str | None):
    """Write down what happened to one message, replacing any earlier attempt.

    An earlier attempt may already have left a row here, recorded as
    suppressed or failed. Updating that row rather than inserting a second
    one is what lets the unique constraint keep its promise: one record per
    (shipment, status, user), so nobody is ever told the same thing twice.
    """
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
    return record
