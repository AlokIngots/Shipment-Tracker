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

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


SEND_EMAILS = _flag("SEND_EMAILS")
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_USE_TLS = _flag("SMTP_USE_TLS", "true")
SMTP_FROM = os.getenv("SMTP_FROM", "").strip() or "portal@alokindia.co.in"
PORTAL_URL = os.getenv("PORTAL_URL", "https://portal.alokindia.co.in").strip()

NOTIFY_ONLY_EMAILS = [
    e.strip().lower()
    for e in os.getenv("NOTIFY_ONLY_EMAILS", "").split(",")
    if e.strip()
]

# Shipment statuses worth telling a customer about.
NOTIFIABLE_STATUSES = [
    s.strip()
    for s in os.getenv("NOTIFY_ON_STATUSES", "Shipped,In transit,Delivered").split(",")
    if s.strip()
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
