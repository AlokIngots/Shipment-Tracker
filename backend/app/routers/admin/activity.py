"""Admin console: what has been changed, by whom, and when.

Read-only, and staff only. There is no route that edits or removes an event,
and there must never be one: a record the people it records can tidy is not
a record. The table refuses it as well -- see migration 0006.

Customers see none of this. Who at Alok Ingots changed a shipment is
internal, and nothing in the customer half of the API reads this table.
"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import DbSession, StaffUser
from app.schemas import StaffActivityEventOut, StaffActivityOut
from app.services import audit

router = APIRouter(prefix="/api/staff")


@router.get("/activity", response_model=StaffActivityOut)
def staff_activity(
    staff: StaffUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    before: Annotated[int | None, Query(ge=1)] = None,
) -> StaffActivityOut:
    """The newest changes first. Pass ``before`` (an event id) for older ones."""
    events, more = audit.recent(db, limit=limit, before_id=before)
    return StaffActivityOut(
        events=[StaffActivityEventOut.model_validate(e) for e in events],
        more=more,
    )
