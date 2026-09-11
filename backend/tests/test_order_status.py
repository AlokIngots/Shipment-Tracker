"""An order's status, worked out from its shipments.

Nobody types an order's status. It follows the shipments, and two things are
still set by hand: a shipment ticked as the last one, and an order marked
cancelled. The rule itself is tested on its own in test_validation.py; this
file tests that both halves of the portal, the activity record and the CSV
importer all use it.
"""

from contextlib import nullcontext

import pytest
from sqlalchemy import select

from app.models import Order, Shipment

# The order and shipment the `order` fixture makes -- 40 of 100 MT, Shipped
# -- so an edit can resubmit them unchanged apart from what a test changes.
ORDER = {
    "sales_order_no": "TEST/SO/EXP/001",
    "ordered_qty": "100.000",
    "unit": "MT",
    "grade": "431 / 1.4057",
}
SHIPMENT = {
    "shipment_no": "TEST/SHP/001-1",
    "dispatched_qty": "40.000",
    "status": "Shipped",
    "vessel_name": "MV Test",
    "imo_number": "9074729",
    "container_no": "CSQU3054383",
    "bl_number": "MAEU-TEST-1",
    "etd": "2026-09-01",
    "eta": "2026-09-28",
}


def seen_by_everybody(client, order_id, staff_auth, customer_auth) -> set[str]:
    """The order's status on the staff page, the customer list and the detail."""
    staff = next(
        o for o in client.get("/api/staff/orders", headers=staff_auth).json()
        if o["id"] == order_id
    )
    listed = next(
        o for o in client.get("/api/orders", headers=customer_auth).json()
        if o["id"] == order_id
    )
    detail = client.get(f"/api/orders/{order_id}", headers=customer_auth).json()
    return {staff["status"], listed["status"], detail["status"]}


def latest_event(client, staff_auth) -> dict:
    return client.get(
        "/api/staff/activity", headers=staff_auth, params={"limit": 1}
    ).json()["events"][0]


# ------------------------------------------------------------ both halves


def test_a_new_order_with_nothing_against_it_is_in_production(client, staff_auth, customer):
    created = client.post(
        "/api/staff/orders",
        headers=staff_auth,
        json={"customer_id": customer.id, "sales_order_no": "TEST/SO/NEW", "ordered_qty": "5"},
    ).json()
    assert created["status"] == "In production"
    assert created["cancelled"] is False


def test_both_halves_follow_the_shipments(client, staff_auth, customer_auth, order):
    url = f"/api/staff/shipments/{order['shipments'][0]['id']}"

    def seen():
        return seen_by_everybody(client, order["id"], staff_auth, customer_auth)

    assert seen() == {"Part shipped"}, "40 MT has left and no last shipment is ticked"

    client.put(url, headers=staff_auth, json={**SHIPMENT, "is_final": True})
    assert seen() == {"Shipped"}

    client.put(url, headers=staff_auth, json={**SHIPMENT, "status": "Delivered", "is_final": True})
    assert seen() == {"Delivered"}

    client.post(
        f"/api/staff/orders/{order['id']}/shipments",
        headers=staff_auth,
        json={"shipment_no": "TEST/SHP/001-2", "dispatched_qty": "60", "status": "Packed"},
    )
    assert seen() == {"Part shipped"}, "a second lot still at the factory"


def test_a_status_sent_for_an_order_is_ignored(client, staff_auth, customer, order):
    """An old form, or a request typed by hand, has nothing to set."""
    edited = client.put(
        f"/api/staff/orders/{order['id']}",
        headers=staff_auth,
        json={"customer_id": customer.id, **ORDER, "status": "Delivered"},
    )
    assert edited.status_code == 200
    assert edited.json()["status"] == "Part shipped"


def test_cancelling_and_the_correction_that_undoes_it(
    client, staff_auth, customer, customer_auth, order
):
    url = f"/api/staff/orders/{order['id']}"
    body = {"customer_id": customer.id, **ORDER}

    cancelled = client.put(url, headers=staff_auth, json={**body, "cancelled": True})
    assert cancelled.json()["status"] == "Cancelled"
    assert seen_by_everybody(client, order["id"], staff_auth, customer_auth) == {"Cancelled"}

    refused = client.put(url, headers=staff_auth, json=body)
    assert refused.status_code == 400, "a form that forgets the box must not un-cancel"
    assert "correction" in refused.json()["detail"].lower()

    restored = client.put(url, headers=staff_auth, json={**body, "allow_backwards": True})
    assert restored.status_code == 200
    assert restored.json()["status"] == "Part shipped", "back to what the shipments say"


def test_the_last_shipment_tick_reaches_the_customer(client, staff_auth, customer_auth, order):
    client.put(
        f"/api/staff/shipments/{order['shipments'][0]['id']}",
        headers=staff_auth,
        json={**SHIPMENT, "is_final": True},
    )
    shipment = client.get(
        f"/api/orders/{order['id']}", headers=customer_auth
    ).json()["shipments"][0]
    assert shipment["is_final"] is True


# ------------------------------------------------------- the activity record


def test_the_tick_and_the_cancellation_are_recorded(client, staff_auth, customer, order):
    client.put(
        f"/api/staff/shipments/{order['shipments'][0]['id']}",
        headers=staff_auth,
        json={**SHIPMENT, "is_final": True},
    )
    ticked = latest_event(client, staff_auth)
    assert {c["field"]: (c["before"], c["after"]) for c in ticked["changes"]} == {
        "Last shipment": ("no", "yes")
    }

    url = f"/api/staff/orders/{order['id']}"
    body = {"customer_id": customer.id, **ORDER}
    client.put(url, headers=staff_auth, json={**body, "cancelled": True})
    cancelled = latest_event(client, staff_auth)
    assert {c["field"]: (c["before"], c["after"]) for c in cancelled["changes"]} == {
        "Cancelled": ("no", "yes")
    }

    client.put(url, headers=staff_auth, json={**body, "allow_backwards": True})
    assert "taking it back out of Cancelled" in latest_event(client, staff_auth)["summary"]


# ------------------------------------------------------------ the importer


@pytest.fixture
def run_import(db, customer, monkeypatch):
    """Check and import one row; the problems found, or [] once it is in."""
    from scripts import import_data

    # The importer opens a session of its own; hand it the test's instead.
    monkeypatch.setattr(import_data, "SessionLocal", lambda: nullcontext(db))

    def run(**row):
        data, errors = import_data.check_row(
            {"customer_code": "TESTCO", "sales_order_no": "TEST/SO/CSV",
             "ordered_qty": "10", **row},
            2,
        )
        if not errors:
            import_data.apply_rows([data], dry_run=False, file_name="orders.csv")
        return errors

    return run


def imported_order(db) -> Order:
    db.expire_all()
    return db.scalar(select(Order).where(Order.sales_order_no == "TEST/SO/CSV"))


def test_a_file_can_cancel_an_order_but_not_type_its_status(run_import, db):
    problems = run_import(order_status="In transit")
    assert problems and "worked out from the shipments" in problems[0]

    assert run_import(order_status="Cancelled") == []
    assert imported_order(db).status == "Cancelled"

    assert run_import(order_status="") == []
    assert imported_order(db).cancelled is True, "a blank never un-cancels"


def test_last_shipment_from_a_file(run_import, db):
    lot = {"shipment_no": "TEST/SHP/CSV-1", "dispatched_qty": "10", "shipment_status": "Shipped"}

    assert run_import(**lot) == []
    assert imported_order(db).status == "Part shipped"

    assert run_import(**lot, last_shipment="yes") == []
    assert imported_order(db).status == "Shipped"

    assert run_import(**lot) == []
    assert imported_order(db).status == "Shipped", (
        "a blank leaves the tick alone, so one made on the screen survives"
    )

    assert run_import(**lot, last_shipment="no") == []
    assert imported_order(db).status == "Part shipped"

    problems = run_import(**lot, last_shipment="maybe")
    assert problems and "not yes or no" in problems[0]


def test_a_file_cannot_move_a_shipment_backwards(run_import, db):
    """The docs promised this since step 18; until step 28 nothing did it."""
    lot = {"shipment_no": "TEST/SHP/CSV-1", "dispatched_qty": "10"}
    assert run_import(**lot, shipment_status="Delivered") == []

    with pytest.raises(ValueError, match="never makes a correction"):
        run_import(**lot, shipment_status="Packed")

    shipment = db.scalar(select(Shipment).where(Shipment.shipment_no == "TEST/SHP/CSV-1"))
    assert shipment.status == "Delivered"
