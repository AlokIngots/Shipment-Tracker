"""Live container tracking: switching it on, keeping it fresh, and showing it.

Three jobs, in the order a shipment meets them.

1. **Enable** -- a member of staff presses Enable tracking on one shipment.
   This is the only thing that can spend a ShipsGo credit, and it spends at
   most one per B/L (see app/services/shipsgo.py for how). A shipment that
   already has tracking is never sent again: its row is found first and the
   call is not made. Nothing turns tracking on by itself -- not a save, not a
   customer opening a page, not the timer.

2. **Refresh** -- the timer in scheduler.py, or staff pressing Refresh, reads
   the shipment back from ShipsGo by the id stored in step 1. Reading is
   free. What comes back is stored, replacing what was there.

3. **Show** -- both halves of the portal draw the stored copy. No page view
   ever calls ShipsGo, so the page is fast and a busy day of customers
   reading their orders costs nothing.

Transshipment is shown as it is: when the box comes off one vessel and goes
onto another, the timeline says so, with both vessel names. That is the
thing the old vessel map got wrong (see tracking.py), and the reason this
follows the container's own movements rather than a ship.
"""

import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.core import config
from app.models import Shipment, ShipmentTracking
from app.services import audit, shipsgo, tracking

log = logging.getLogger("portal.tracking")

__all__ = [
    "ALREADY_ON",
    "EVENT_LABELS",
    "REUSED",
    "SPENT",
    "STATUS_LABELS",
    "TrackingProblem",
    "enable",
    "refresh",
    "refresh_due",
    "refresh_manually",
    "simplify",
    "stop",
    "timeline",
    "view",
]

STATUS_LABELS = {
    "NEW": "Tracking is updating…",
    "INPROGRESS": "Tracking is updating…",
    "BOOKED": "Booked with the shipping line",
    "LOADED": "Loaded on the vessel",
    "SAILING": "Sailing",
    "ARRIVED": "Arrived at the port of discharge",
    "DISCHARGED": "Discharged at the port of discharge",
    "UNTRACKED": "The shipping line has no tracking for this B/L",
}

EVENT_LABELS = {
    "EMSH": "Empty container sent for loading",
    "GTIN": "Container entered the port",
    "LOAD": "Loaded on vessel",
    "DEPA": "Vessel departed",
    "ARRV": "Vessel arrived",
    "DISC": "Discharged from vessel",
    "GTOT": "Container left the port",
    "EMRT": "Empty container returned",
}

# ShipsGo allows 100 requests a minute for the whole account. The timer
# stays well under it.
PAUSE_BETWEEN_READS_SECONDS = 0.7
MAX_READS_PER_RUN = 80
# A shipment that has failed this many refreshes in a row is left alone by
# the timer until staff press Refresh on it.
GIVE_UP_AFTER_FAILURES = 20
# Staff pressing Refresh again and again is harmless but pointless.
MANUAL_REFRESH_GAP = timedelta(seconds=60)


class TrackingProblem(Exception):
    """Something staff need to be told in plain words."""


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _same_bl(a: str | None, b: str | None) -> bool:
    return (a or "").strip().upper() == (b or "").strip().upper()


# ------------------------------------------------------------------ enable


ALREADY_ON = "already_on"
REUSED = "reused"
SPENT = "spent"


def enable(session: Session, shipment_id: int, actor) -> tuple[ShipmentTracking, str]:
    """Switch live tracking on for one shipment.

    Returns the row and what it took: ALREADY_ON (nothing was sent to
    ShipsGo), REUSED (ShipsGo already had the B/L; no credit) or SPENT (one
    credit).

    Commits as soon as ShipsGo has answered, so ShipsGo's id is never held
    only in memory. The shipment row is locked while this runs, so two
    presses at once end with one row and at most one credit.
    """
    shipment = session.scalar(
        select(Shipment).where(Shipment.id == shipment_id).with_for_update()
    )
    if shipment is None:
        raise LookupError("Shipment not found.")

    existing = session.scalar(
        select(ShipmentTracking).where(ShipmentTracking.shipment_id == shipment.id)
    )
    if existing is not None:
        if _same_bl(existing.booking_number, shipment.bl_number):
            # Already on. Nothing is sent to ShipsGo.
            session.rollback()
            return existing, ALREADY_ON
        raise TrackingProblem(
            f"Tracking is on for the old B/L number {existing.booking_number}. "
            "Stop tracking first, then enable it for the new number."
        )

    bl = (shipment.bl_number or "").strip()
    if not bl:
        raise TrackingProblem("Add the Bill of Lading number to this shipment first.")
    if not shipsgo.configured():
        raise TrackingProblem(
            "Live tracking is not set up on this server yet (SHIPSGO_API_KEY is empty)."
        )

    # A second shipment on the same B/L can share the first one's ShipsGo
    # record without even asking ShipsGo.
    sibling = session.scalar(
        select(ShipmentTracking).where(
            ShipmentTracking.booking_number == bl.upper()
        ).limit(1)
    )
    if sibling is not None:
        external_id, spent = sibling.external_id, False
    else:
        try:
            added = shipsgo.add_shipment(bl.upper(), tracking.carrier_scac(shipment.carrier))
        except shipsgo.ShipsGoError as error:
            raise TrackingProblem(error.message) from error
        external_id, spent = added.external_id, added.spent

    row = ShipmentTracking(
        shipment_id=shipment.id,
        provider="shipsgo",
        external_id=external_id,
        booking_number=bl.upper(),
        enabled_by=getattr(actor, "email", None),
        reused=not spent,
        status="NEW",
    )
    session.add(row)
    order = shipment.order
    audit.record(
        session,
        "shipment.tracking_enabled",
        f"Turned on live tracking for shipment {shipment.shipment_no} "
        f"(B/L {bl.upper()}) on order {order.sales_order_no}"
        + (" -- 1 ShipsGo credit used" if spent else " -- no credit used, ShipsGo already had it"),
        actor=actor,
    )
    session.commit()
    return row, (SPENT if spent else REUSED)


def stop(session: Session, shipment_id: int, actor) -> bool:
    """Stop showing live tracking for a shipment. Nothing is sent to ShipsGo.

    The shipment stays in the ShipsGo account -- deleting it would refund
    nothing -- so enabling again for the same B/L finds it and costs nothing.
    """
    row = session.scalar(
        select(ShipmentTracking)
        .where(ShipmentTracking.shipment_id == shipment_id)
        .options(selectinload(ShipmentTracking.shipment).selectinload(Shipment.order))
    )
    if row is None:
        return False
    shipment = row.shipment
    audit.record(
        session,
        "shipment.tracking_stopped",
        f"Turned off live tracking for shipment {shipment.shipment_no} "
        f"(B/L {row.booking_number}) on order {shipment.order.sales_order_no}",
        actor=actor,
    )
    session.delete(row)
    session.commit()
    return True


# ----------------------------------------------------------------- refresh


def simplify(detail: dict) -> list[dict]:
    """Each container and its movements, keeping only what the portal shows.

    Movements stay in ShipsGo's order, which is the order they happen in.
    Their timestamps are kept as sent, with the port's own UTC offset.
    """
    containers = []
    for container in detail.get("containers") or []:
        moves = []
        for move in container.get("movements") or []:
            location = move.get("location") or {}
            vessel = move.get("vessel") or {}
            country = location.get("country") or {}
            moves.append(
                {
                    "event": move.get("event"),
                    "actual": move.get("status") == "ACT",
                    "location": location.get("name"),
                    "location_code": location.get("code"),
                    "country": country.get("name"),
                    "vessel": vessel.get("name") if isinstance(vessel, dict) else None,
                    "imo": vessel.get("imo") if isinstance(vessel, dict) else None,
                    "voyage": move.get("voyage"),
                    "timestamp": move.get("timestamp"),
                }
            )
        containers.append(
            {
                "number": container.get("number"),
                "status": container.get("status"),
                "size": container.get("size"),
                "type": container.get("type"),
                "movements": moves,
            }
        )
    return containers


def _port(side: dict | None) -> str | None:
    location = (side or {}).get("location") or {}
    name = location.get("name")
    country = (location.get("country") or {}).get("name")
    if name and country:
        return f"{name}, {country}"
    return name or None


def _apply(row: ShipmentTracking, detail: dict) -> None:
    route = detail.get("route") or {}
    pol = route.get("port_of_loading") or {}
    pod = route.get("port_of_discharge") or {}
    carrier = detail.get("carrier") or {}

    row.status = detail.get("status")
    row.carrier_name = carrier.get("name") if isinstance(carrier, dict) else None
    row.port_of_loading = _port(pol)
    row.port_of_discharge = _port(pod)
    row.loaded_at = pol.get("date_of_loading")
    row.eta = pod.get("date_of_discharge") or pod.get("date_of_discharge_predicted")
    row.transshipments = route.get("ts_count")
    row.container_count = detail.get("container_count")
    row.containers = simplify(detail)
    row.checked_at = detail.get("checked_at")
    row.discarded_at = detail.get("discarded_at")


def refresh(session: Session, row: ShipmentTracking) -> None:
    """Read one shipment back from ShipsGo and store what it says. Free.

    A failure is written on the row and the old news kept, so a customer
    goes on seeing the last good copy. Commits either way. A CreditTripwire
    is recorded and then raised, so whoever called this stops.
    """
    try:
        detail = shipsgo.get_shipment(row.external_id)
    except shipsgo.CreditTripwire as error:
        row.last_error = error.message
        row.failures = (row.failures or 0) + 1
        session.commit()
        raise
    except shipsgo.ShipsGoError as error:
        row.last_error = error.message
        row.failures = (row.failures or 0) + 1
        row.refreshed_at = _now()
        session.commit()
        log.warning("tracking refresh failed for #%s: %s", row.external_id, error.message)
        return

    _apply(row, detail)
    row.refreshed_at = _now()
    row.last_error = None
    row.failures = 0
    session.commit()


def refresh_manually(session: Session, shipment_id: int) -> ShipmentTracking:
    """Staff pressed Refresh. Free, and at most once a minute per shipment."""
    row = session.scalar(
        select(ShipmentTracking).where(ShipmentTracking.shipment_id == shipment_id)
    )
    if row is None:
        raise TrackingProblem("Live tracking is not on for this shipment.")
    if not shipsgo.configured():
        raise TrackingProblem(
            "Live tracking is not set up on this server yet (SHIPSGO_API_KEY is empty)."
        )
    if row.refreshed_at and _now() - row.refreshed_at < MANUAL_REFRESH_GAP and not row.last_error:
        return row
    try:
        refresh(session, row)
    except shipsgo.CreditTripwire as error:
        raise TrackingProblem(error.message) from error
    return row


def refresh_due(session: Session, *, pause=time.sleep) -> dict[str, int]:
    """Every tracked shipment that has not been read for a while. The timer's job.

    Skips shipments ShipsGo has stopped following, and ones that keep
    failing. Reads only: nothing here can add a shipment to ShipsGo.
    """
    counts = {"refreshed": 0, "failed": 0}
    if not shipsgo.configured() or config.SHIPSGO_REFRESH_EVERY_HOURS <= 0:
        return counts

    # A little under the interval, so a timer that wakes a few seconds early
    # does not skip everything until the turn after.
    stale_before = _now() - timedelta(hours=config.SHIPSGO_REFRESH_EVERY_HOURS) * 0.9
    rows = list(
        session.scalars(
            select(ShipmentTracking)
            .where(
                ShipmentTracking.discarded_at.is_(None),
                ShipmentTracking.failures < GIVE_UP_AFTER_FAILURES,
                or_(
                    ShipmentTracking.refreshed_at.is_(None),
                    ShipmentTracking.refreshed_at < stale_before,
                ),
            )
            .order_by(ShipmentTracking.refreshed_at.asc().nulls_first())
            .limit(MAX_READS_PER_RUN)
        )
    )

    for index, row in enumerate(rows):
        if index:
            pause(PAUSE_BETWEEN_READS_SECONDS)
        failures_before = row.failures or 0
        refresh(session, row)  # a CreditTripwire goes straight up and stops the run
        if (row.failures or 0) > failures_before:
            counts["failed"] += 1
        else:
            counts["refreshed"] += 1
    return counts


# -------------------------------------------------------------------- show


def _date(timestamp: str | None) -> str | None:
    """The date part as the port wrote it, not converted to anybody's zone."""
    return timestamp[:10] if timestamp and len(timestamp) >= 10 else None


def _pick_container(containers: list[dict], container_no: str | None) -> dict | None:
    if not containers:
        return None
    wanted = tracking.tidy_container_no(container_no)
    for container in containers:
        if wanted and (container.get("number") or "").upper() == wanted:
            return container
    return containers[0]


def timeline(movements: list[dict]) -> list[dict]:
    """The movements as the screens draw them, with transshipment marked.

    A box that is discharged and then loaded again before its last port has
    been transshipped. The discharge is labelled as the transshipment, and
    the loading onto a different vessel names both ships -- so nobody reads
    the first vessel's next voyage as their cargo's route.
    """
    events = [m.get("event") for m in movements]
    latest_actual = max(
        (i for i, m in enumerate(movements) if m.get("actual")), default=None
    )

    out = []
    vessel_so_far = None
    for index, move in enumerate(movements):
        event = move.get("event")
        vessel = move.get("vessel")
        label = EVENT_LABELS.get(event, event or "Update")
        transshipment = False
        from_vessel = None

        if event == "DISC" and "LOAD" in events[index + 1 :]:
            transshipment = True
            label = "Discharged for transshipment"
        if event in ("LOAD", "DEPA") and vessel and vessel_so_far and vessel != vessel_so_far:
            transshipment = True
            from_vessel = vessel_so_far
            if event == "LOAD":
                label = "Transshipped: loaded on the next vessel"
        if vessel and event in ("LOAD", "DEPA", "ARRV", "DISC"):
            vessel_so_far = vessel

        out.append(
            {
                "event": event,
                "label": label,
                "actual": bool(move.get("actual")),
                "location": move.get("location"),
                "country": move.get("country"),
                "vessel": vessel,
                "voyage": move.get("voyage"),
                "date": _date(move.get("timestamp")),
                "timestamp": move.get("timestamp"),
                "transshipment": transshipment,
                "from_vessel": from_vessel,
                "latest": index == latest_actual,
            }
        )
    return out


def view(shipment, *, for_staff: bool) -> dict | None:
    """The tracking panel for one shipment, from the stored copy only.

    None when there is nothing a customer should see: tracking off, the B/L
    changed since it was switched on, or the line has no tracking for it.
    Staff are shown those cases too, with the reason.
    """
    row = getattr(shipment, "tracking", None)
    if row is None:
        return None

    stale = not _same_bl(row.booking_number, shipment.bl_number)
    status = row.status
    if not for_staff and (stale or status == "UNTRACKED"):
        return None

    if status == "UNTRACKED":
        state = "unavailable"
    elif row.refreshed_at is None or status in (None, "NEW", "INPROGRESS"):
        state = "updating"
    else:
        state = "ready"

    containers = row.containers or []
    chosen = _pick_container(containers, shipment.container_no)
    panel = {
        "state": state,
        "status": status,
        "status_label": STATUS_LABELS.get(status or "", "Tracking is updating…"),
        "carrier": row.carrier_name,
        "port_of_loading": row.port_of_loading,
        "port_of_discharge": row.port_of_discharge,
        "loaded_on": _date(row.loaded_at),
        "eta": _date(row.eta),
        "transshipments": row.transshipments or 0,
        "container_number": chosen.get("number") if chosen else None,
        "container_count": row.container_count or len(containers),
        "other_containers": [
            c.get("number") for c in containers if c is not chosen and c.get("number")
        ],
        "movements": timeline(chosen.get("movements") or []) if chosen else [],
        "updated_at": row.refreshed_at,
    }
    if for_staff:
        panel.update(
            {
                "booking_number": row.booking_number,
                "external_id": row.external_id,
                "stale": stale,
                "last_error": row.last_error,
                "failures": row.failures or 0,
                "reused": row.reused,
                "enabled_at": row.enabled_at,
                "enabled_by": row.enabled_by,
                "finished": row.discarded_at is not None,
            }
        )
    return panel
