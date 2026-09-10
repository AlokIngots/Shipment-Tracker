"""The Alok Ingots side: creating and editing orders and part-shipments.

Until this existed, an order or a shipment could only reach the portal by
running import_data.py on the server. This is the same job done from a
screen, and it deliberately applies the importer's rules, so the two cannot
disagree about what a valid order looks like.
"""

from decimal import Decimal

from app.services import tracking
from app.core.deps import DbSession, StaffUser, bad_request, not_found
from fastapi import APIRouter
from app.models import Customer, Order, Shipment
from app.schemas import (
    OrderIn,
    ShipmentIn,
    StaffCustomerOut,
    StaffOrderOut,
    StaffOrderShipmentOut,
)
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

router = APIRouter(prefix="/api/staff")


# ------------------------------------------------------- checking and shaping


def tidy(value: str | None) -> str | None:
    """Trim a submitted field, treating a blank one as not given at all."""
    if value is None:
        return None
    value = value.strip()
    return value or None


def staff_order_out(order: Order, customer: Customer) -> StaffOrderOut:
    """One order, its shipments, and how much of it is still to ship."""
    dispatched = sum(
        (s.dispatched_qty or Decimal("0") for s in order.shipments), Decimal("0")
    )
    return StaffOrderOut(
        id=order.id,
        customer_id=customer.id,
        customer_code=customer.code,
        customer_name=customer.name,
        sales_order_no=order.sales_order_no,
        customer_po=order.customer_po,
        grade=order.grade,
        description=order.description,
        ordered_qty=order.ordered_qty,
        unit=order.unit,
        status=order.status,
        dispatched_qty=dispatched,
        balance_qty=(order.ordered_qty or Decimal("0")) - dispatched,
        shipments=[
            StaffOrderShipmentOut(
                id=s.id,
                shipment_no=s.shipment_no,
                dispatched_qty=s.dispatched_qty,
                unit=s.unit,
                status=s.status,
                vessel_name=s.vessel_name,
                imo_number=s.imo_number,
                container_no=s.container_no,
                bl_number=s.bl_number,
                etd=s.etd,
                eta=s.eta,
                document_count=len(s.documents),
            )
            for s in sorted(order.shipments, key=lambda s: s.id)
        ],
    )


def apply_order(order: Order, body: OrderIn, db: Session) -> None:
    """Check a submitted order and copy it onto the row, or refuse it."""
    customer = db.get(Customer, body.customer_id)
    if customer is None:
        raise bad_request("Choose which customer this order is for.")

    sales_order_no = tidy(body.sales_order_no)
    if not sales_order_no:
        raise bad_request("A sales order number is required.")

    # Unique across the whole portal, not just per customer, because
    # import_data.py finds an order by its sales order number alone. Two
    # orders sharing a number would make the next import overwrite whichever
    # one it happened to find first.
    clash = db.scalar(select(Order.id).where(Order.sales_order_no == sales_order_no))
    if clash is not None and clash != order.id:
        raise bad_request(f"Sales order {sales_order_no} already exists.")

    if body.ordered_qty < 0:
        raise bad_request("The ordered quantity cannot be negative.")

    order.customer_id = customer.id
    order.sales_order_no = sales_order_no
    order.customer_po = tidy(body.customer_po)
    order.grade = tidy(body.grade)
    order.description = tidy(body.description)
    order.ordered_qty = body.ordered_qty
    order.unit = tidy(body.unit) or "MT"
    order.status = tidy(body.status)


def apply_shipment(shipment: Shipment, body: ShipmentIn, db: Session) -> None:
    """Check a submitted shipment and copy it onto the row, or refuse it."""
    shipment_no = tidy(body.shipment_no)
    if not shipment_no:
        raise bad_request("A shipment number is required.")

    # Unique portal-wide for the same reason a sales order number is: the
    # importer matches a shipment on its number alone.
    clash = db.scalar(select(Shipment.id).where(Shipment.shipment_no == shipment_no))
    if clash is not None and clash != shipment.id:
        raise bad_request(f"Shipment {shipment_no} already exists.")

    if body.dispatched_qty < 0:
        raise bad_request("The dispatched quantity cannot be negative.")

    imo_number = tidy(body.imo_number)
    if imo_number and not tracking.valid_imo(imo_number):
        raise bad_request(
            f"{imo_number} is not a valid IMO number. An IMO number is seven "
            "digits, and the last one is a check digit worked out from the "
            "first six, so a typo is caught here rather than by a customer "
            "following a link to the wrong ship."
        )

    # A container number carries its own check digit, exactly as an IMO
    # number does, so a transposed pair of characters is caught here rather
    # than by a customer trying to trace a box that does not exist.
    container_no = tracking.tidy_container_no(body.container_no)
    if container_no and not tracking.valid_container_no(container_no):
        raise bad_request(
            f"{container_no} is not a valid container number. It is four "
            "letters then seven digits (like MSCU1234566), and the last "
            "digit is a check digit worked out from the rest — so a typo "
            "or two characters the wrong way round is refused here."
        )

    if body.etd and body.eta and body.eta < body.etd:
        raise bad_request("The arrival date cannot be before the departure date.")

    shipment.shipment_no = shipment_no
    shipment.dispatched_qty = body.dispatched_qty
    shipment.unit = tidy(body.unit) or "MT"
    shipment.status = tidy(body.status)
    shipment.vessel_name = tidy(body.vessel_name)
    shipment.imo_number = imo_number
    shipment.container_no = container_no
    # No format to check: every carrier numbers its Bills of Lading its own
    # way, so refusing anything here would only refuse real ones.
    shipment.bl_number = tidy(body.bl_number)
    shipment.etd = body.etd
    shipment.eta = body.eta


def load_order(order_id: int, db: Session) -> Order:
    """Fetch an order for editing, or raise the 404 every route here wants."""
    order = db.get(Order, order_id)
    if order is None:
        raise not_found("Order not found.")
    return order


def order_response(order: Order, db: Session) -> StaffOrderOut:
    """The saved order, reloaded, so the page never guesses what the row became."""
    db.refresh(order)
    return staff_order_out(order, db.get(Customer, order.customer_id))


# ----------------------------------------------------------------- the routes


@router.get("/customers", response_model=list[StaffCustomerOut])
def staff_customers(staff: StaffUser, db: DbSession) -> list[Customer]:
    """Every customer, for the dropdown on the new-order form.

    Creating a customer is still manage_users.py --add-customer on the
    server, deliberately: a customer is created once, and mistyping its code
    breaks the link to SAP/PMS, so it is not a two-second job on a screen.
    """
    return list(db.scalars(select(Customer).order_by(Customer.name)))


@router.get("/orders", response_model=list[StaffOrderOut])
def staff_orders(staff: StaffUser, db: DbSession) -> list[StaffOrderOut]:
    """Every order in the portal, newest first, with its part-shipments."""
    rows = db.execute(
        select(Order, Customer)
        .join(Customer, Order.customer_id == Customer.id)
        .options(selectinload(Order.shipments).selectinload(Shipment.documents))
        .order_by(Order.id.desc())
    ).all()
    return [staff_order_out(order, customer) for order, customer in rows]


@router.post("/orders", response_model=StaffOrderOut, status_code=201)
def staff_create_order(body: OrderIn, staff: StaffUser, db: DbSession) -> StaffOrderOut:
    """Create an order.

    Safe alongside the importer: a later CSV carrying the same sales order
    number updates this row rather than adding a second one.
    """
    order = Order()
    apply_order(order, body, db)
    db.add(order)
    db.commit()
    return order_response(order, db)


@router.put("/orders/{order_id}", response_model=StaffOrderOut)
def staff_update_order(
    order_id: int, body: OrderIn, staff: StaffUser, db: DbSession
) -> StaffOrderOut:
    """Edit an order. The form sends every field, so every field is replaced."""
    order = load_order(order_id, db)
    apply_order(order, body, db)
    db.commit()
    return order_response(order, db)


@router.delete("/orders/{order_id}")
def staff_delete_order(
    order_id: int, staff: StaffUser, db: DbSession
) -> dict[str, str]:
    """Remove an order, but only while it has nothing hanging off it.

    Deleting would cascade to its shipments and their documents. Refusing
    until the order is empty means the mistake being undone is always the one
    just made, and never somebody's filed paperwork.
    """
    order = load_order(order_id, db)
    if order.shipments:
        raise bad_request(
            f"{order.sales_order_no} still has {len(order.shipments)} "
            "shipment(s). Remove those first."
        )

    sales_order_no = order.sales_order_no
    db.delete(order)
    db.commit()
    return {"detail": f"{sales_order_no} removed."}
