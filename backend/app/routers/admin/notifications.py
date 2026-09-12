"""Admin console: what the portal has told customers, and what is waiting.

Staff only. There is one thing here that writes, and it writes nothing a
customer can see: Send now does the same pass the timer does, immediately,
for somebody standing at the screen who does not want to wait a quarter of
an hour.

The deciding and the sending are in app/services/notifications.py and
app/services/scheduler.py. This file reads the request and shapes the reply.
"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.core import config
from app.core.deps import DbSession, StaffUser
from app.schemas import (
    StaffMessageOut,
    StaffMessagesOut,
    StaffMessageWaitingOut,
    StaffSenderOut,
    StaffSendNowOut,
)
from app.services import notifications, scheduler

router = APIRouter(prefix="/api/staff")


def _sender() -> StaffSenderOut:
    state = scheduler.status()
    return StaffSenderOut(
        every_minutes=state["every_minutes"],
        running=state["running"],
        last_run_at=state["last_run_at"],
        last_counts=state["last_counts"],
        last_error=state["last_error"],
        runs=state["runs"],
        sending_enabled=config.SEND_EMAILS,
        pilot_addresses=list(config.NOTIFY_ONLY_EMAILS),
        notify_on=list(config.NOTIFIABLE_STATUSES),
    )


@router.get("/messages", response_model=StaffMessagesOut)
def staff_messages(
    staff: StaffUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    before: Annotated[int | None, Query(ge=1)] = None,
) -> StaffMessagesOut:
    """The newest messages first, what is still waiting, and how the sender is."""
    rows, more = notifications.recent(db, limit=limit, before_id=before)

    messages = [
        StaffMessageOut(
            id=note.id,
            attempted_at=note.last_attempt_at or note.created_at,
            attempts=note.attempts or 1,
            outcome=note.outcome,
            detail=note.detail,
            event=note.event,
            channel=note.channel,
            to_email=user.email,
            to_name=user.full_name,
            customer_name=customer.name,
            sales_order_no=order.sales_order_no,
            shipment_no=shipment.shipment_no,
        )
        for note, shipment, order, customer, user in rows
    ]

    # Only on the first page. "What is waiting" is one list about the whole
    # database, not a slice of it, and repeating it under every page of
    # older messages would just be noise.
    waiting: list[StaffMessageWaitingOut] = []
    if before is None:
        waiting = [
            StaffMessageWaitingOut(
                to_email=user.email,
                customer_name=customer.name,
                sales_order_no=order.sales_order_no,
                shipment_no=shipment.shipment_no,
                event=shipment.status,
                would_send=notifications.would_send_to(user.email),
            )
            for shipment, order, customer, user in notifications.pending(db)
        ]

    return StaffMessagesOut(
        sender=_sender(), waiting=waiting, messages=messages, more=more
    )


@router.post("/messages/send", response_model=StaffSendNowOut)
def staff_send_now(staff: StaffUser, db: DbSession) -> StaffSendNowOut:
    """Send whatever is waiting, now, instead of waiting for the timer.

    Safe to press twice: a customer is never told the same thing twice, and
    a press while the timer is mid-run takes no lock, so it reports skipped
    rather than sending anything a second time.

    A plain `def` and not `async`, deliberately: sending talks SMTP, which
    blocks, and FastAPI runs a sync endpoint in a worker thread where that
    is nobody's problem. Written `async` it would stall every other request
    in the container for as long as the mail server took to answer.
    """
    counts = scheduler.send_with(db)
    return StaffSendNowOut(
        sent=counts["sent"],
        suppressed=counts["suppressed"],
        failed=counts["failed"],
        skipped=counts.get("skipped", 0),
    )
