"""Writing down who changed what, and reading it back.

Every change to the portal's data is recorded through ``record``, in the
same transaction as the change: the event is added to the session before
the caller commits, so the change and its event are saved together or not
at all. A change that is refused leaves no event, and no event describes a
change that did not happen.

Nothing here knows about HTTP. The admin console passes the signed-in staff
member as the actor; a command run on the server passes nobody, and the
event says where it came from instead. That is the only difference between
them, and it is why the screen, manage_users.py, add_document.py and the CSV
importer all record through this one module.
"""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select

from app.models import AuditEvent, Customer, Order, User
from app.services import statuses

# Where a change came from.
SCREEN = "screen"
COMMAND_LINE = "command line"
CSV_IMPORT = "csv import"

# The fields the record keeps, and what a person calls each one. A field not
# listed here is never written into an event -- which is how a password hash
# stays out: not by remembering to leave it out, but by never being asked
# for in the first place.
ORDER_FIELDS = {
    "sales_order_no": "Sales order",
    "customer_po": "Customer PO",
    "grade": "Grade",
    "description": "Description",
    "ordered_qty": "Ordered quantity",
    "unit": "Unit",
    # Not the status: that is worked out from the shipments, and the change
    # to a shipment that moved it is what gets recorded.
    "cancelled": "Cancelled",
}
# An order's customer is shown by its code, not its id. See order_state.
ORDER_LABELS = {"customer": "Customer", **ORDER_FIELDS}

SHIPMENT_FIELDS = {
    "shipment_no": "Shipment",
    "dispatched_qty": "Dispatched quantity",
    "unit": "Unit",
    "status": "Status",
    "is_final": "Last shipment",
    "vessel_name": "Vessel",
    "imo_number": "IMO number",
    "container_no": "Container number",
    "bl_number": "B/L number",
    "etd": "ETD",
    "eta": "ETA",
}

CUSTOMER_FIELDS = {"code": "Code", "name": "Name", "country": "Country"}

LOGIN_FIELDS = {"email": "Email", "full_name": "Name"}


# ------------------------------------------------------------ what changed


def shown(value) -> str | None:
    """A value as the record stores it: text, or None for "not set".

    Quantities are written to three places, the precision the database
    keeps. Otherwise "40" typed on a form and "40.000" read back from the
    table would look like a change when nothing had changed.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, Decimal):
        return format(value.quantize(Decimal("0.001")), "f")
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    text = str(value).strip()
    return text or None


def snapshot(row, fields: dict[str, str]) -> dict[str, str | None]:
    """The recorded fields of a row, as they are right now."""
    return {name: shown(getattr(row, name)) for name in fields}


def order_state(session, order: Order) -> dict[str, str | None]:
    """An order's recorded fields, with its customer named by code.

    "Customer: 3 → 7" would tell nobody anything.
    """
    customer = (
        session.get(Customer, order.customer_id)
        if order.customer_id is not None
        else None
    )
    return {
        "customer": customer.code if customer else None,
        **snapshot(order, ORDER_FIELDS),
    }


def diff(before: dict, after: dict, labels: dict[str, str]) -> list[dict]:
    """Each field whose value differs, with what it was and what it became.

    Pass ``{}`` as ``before`` for something being created, and every field
    that has a value is listed as set from nothing. Pass ``{}`` as ``after``
    for something being removed, and the record keeps what it held -- so a
    mistaken removal can be typed back in.
    """
    return [
        {"field": label, "before": before.get(name), "after": after.get(name)}
        for name, label in labels.items()
        if before.get(name) != after.get(name)
    ]


def correction_note(before: str | None, after: str | None) -> str:
    """Words to add to a summary when a status was moved backwards.

    The screen only lets that through once somebody has confirmed it is a
    correction, and a correction is exactly the kind of change somebody
    will later want to find.
    """
    try:
        statuses.check_move(before, after, allow_backwards=False)
    except statuses.StatusProblem:
        return f", correcting the status back from {before} to {after}"
    return ""


# ------------------------------------------------------------ writing


def record(
    session,
    action: str,
    summary: str,
    *,
    actor: User | None = None,
    source: str | None = None,
    changes: list[dict] | None = None,
) -> AuditEvent:
    """Add one event to the session. The caller's commit saves it.

    Never commits by itself: an event committed ahead of its change would
    survive the change failing, and describe something that never happened.
    """
    event = AuditEvent(
        action=action,
        summary=summary[:300],
        actor_user_id=actor.id if actor else None,
        actor_email=actor.email if actor else None,
        source=source or (SCREEN if actor else COMMAND_LINE),
        changes=changes or None,
    )
    session.add(event)
    return event


# ------------------------------------------------------------ reading


def recent(
    session, *, limit: int = 100, before_id: int | None = None
) -> tuple[list[AuditEvent], bool]:
    """The newest events first, one page at a time.

    Returns the page, and whether there are older events beyond it. Ordered
    by id rather than by time: every event written in one transaction shares
    the same timestamp, and the id is the order they were written in.
    """
    query = select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit + 1)
    if before_id is not None:
        query = query.where(AuditEvent.id < before_id)
    rows = list(session.scalars(query))
    return rows[:limit], len(rows) > limit
