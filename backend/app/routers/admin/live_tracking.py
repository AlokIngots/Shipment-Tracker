"""Admin console: switching live container tracking on, refreshing it, stopping it.

Staff only. **Enable tracking is the one action in the whole portal that can
spend a ShipsGo credit**, so it asks for `confirm: true` as well as a press,
and spends at most one credit per B/L however often it is pressed. See
app/services/live_tracking.py and app/services/shipsgo.py.

Refresh and Stop cost nothing: a refresh is a read, and stopping only removes
our copy.
"""

from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from app.core import config
from app.core.deps import DbSession, StaffUser, bad_request, not_found
from app.models import Order, Shipment
from app.routers.admin.orders import order_response
from app.schemas import StaffTrackingResultOut
from app.services import live_tracking, scheduler, shipsgo

router = APIRouter(prefix="/api/staff")


class EnableTrackingIn(BaseModel):
    # Must be true. The screen sets it after staff agree to use a credit, so
    # a stray request with an empty body cannot spend one.
    confirm: bool = False


class TrackingSetupOut(BaseModel):
    configured: bool
    refresh_every_hours: int
    last_run_at: datetime | None = None
    last_counts: dict | None = None
    last_error: str | None = None


def _order_for(shipment_id: int, db) -> Order:
    shipment = db.get(Shipment, shipment_id)
    if shipment is None:
        raise not_found("Shipment not found.")
    return db.get(Order, shipment.order_id)


@router.get("/tracking/setup", response_model=TrackingSetupOut)
def staff_tracking_setup(staff: StaffUser) -> TrackingSetupOut:
    """Whether live tracking can be used here, and how the refresh timer is doing."""
    state = scheduler.tracking_status()
    return TrackingSetupOut(
        configured=shipsgo.configured(),
        refresh_every_hours=config.SHIPSGO_REFRESH_EVERY_HOURS,
        last_run_at=state["last_run_at"],
        last_counts=state["last_counts"],
        last_error=state["last_error"],
    )


@router.post("/shipments/{shipment_id}/tracking", response_model=StaffTrackingResultOut)
def staff_enable_tracking(
    shipment_id: int, body: EnableTrackingIn, staff: StaffUser, db: DbSession
) -> StaffTrackingResultOut:
    """Switch live tracking on. May use ONE ShipsGo credit, once per B/L."""
    if not body.confirm:
        raise bad_request(
            "Turning on live tracking can use one ShipsGo credit, so it has to be confirmed."
        )
    try:
        row, outcome = live_tracking.enable(db, shipment_id, staff)
    except LookupError as error:
        db.rollback()
        raise not_found(str(error)) from error
    except live_tracking.TrackingProblem as error:
        db.rollback()
        raise bad_request(str(error)) from error

    # The first news, straight away. A read, so it costs nothing; if it
    # fails the timer tries again later and the screen says "updating".
    if outcome != live_tracking.ALREADY_ON and row.refreshed_at is None:
        try:
            live_tracking.refresh(db, row)
        except shipsgo.CreditTripwire:
            pass  # written on the row; staff see it on the panel

    spent = outcome == live_tracking.SPENT
    if spent:
        detail = "Live tracking is on. 1 ShipsGo credit was used."
    elif outcome == live_tracking.REUSED:
        detail = "Live tracking is on. No credit was used: ShipsGo was already following this B/L."
    else:
        detail = "Live tracking was already on for this shipment. Nothing was sent to ShipsGo."
    return StaffTrackingResultOut(
        detail=detail, credit_spent=spent, order=order_response(_order_for(shipment_id, db), db)
    )


@router.post(
    "/shipments/{shipment_id}/tracking/refresh", response_model=StaffTrackingResultOut
)
def staff_refresh_tracking(
    shipment_id: int, staff: StaffUser, db: DbSession
) -> StaffTrackingResultOut:
    """Ask ShipsGo for the latest news now. Free."""
    try:
        row = live_tracking.refresh_manually(db, shipment_id)
    except live_tracking.TrackingProblem as error:
        db.rollback()
        raise bad_request(str(error)) from error
    detail = (
        f"ShipsGo could not be read: {row.last_error}"
        if row.last_error
        else "Tracking refreshed. No credit is used for this."
    )
    return StaffTrackingResultOut(
        detail=detail, credit_spent=False, order=order_response(_order_for(shipment_id, db), db)
    )


@router.delete("/shipments/{shipment_id}/tracking", response_model=StaffTrackingResultOut)
def staff_stop_tracking(
    shipment_id: int, staff: StaffUser, db: DbSession
) -> StaffTrackingResultOut:
    """Stop showing live tracking. Nothing is sent to ShipsGo."""
    order = _order_for(shipment_id, db)
    if not live_tracking.stop(db, shipment_id, staff):
        raise bad_request("Live tracking is not on for this shipment.")
    return StaffTrackingResultOut(
        detail=(
            "Live tracking is off for this shipment. It stays in ShipsGo, so "
            "turning it on again for the same B/L uses no credit."
        ),
        credit_spent=False,
        order=order_response(order, db),
    )
