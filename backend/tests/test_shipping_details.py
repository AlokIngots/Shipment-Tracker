"""Step 50: shipping details that had nowhere to go.

What the Bill of Lading and the export paperwork carry, stored at last:
customer address, EORI and a contact who need not have a login; order date
and Shipping Bill number; ports, voyage, seal, container size and gross
weight on each shipment. Staff enter them on the screens or through the CSV
importer, which apply the same rules. The customer sees the route, the dates
and the box, and never the customer details or the Shipping Bill.
"""

from contextlib import nullcontext
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models import Customer, Order, Shipment
from app.services import shipping_details

SHIPMENT_DETAILS = {
    "port_of_loading": "Nhava Sheva",
    "port_of_discharge": "Hamburg",
    "voyage_no": "0FL4RW1MA",
    "seal_no": "SEAL123456",
    "container_size": "20ft standard",
    "gross_weight": "41.250",
}


# ------------------------------------------------------ the rules, no database


def test_eori_is_tidied_and_checked():
    assert shipping_details.tidy_eori(" de 1234-5678 ") == "DE12345678"
    assert shipping_details.tidy_eori("   ") is None
    assert shipping_details.eori_problem("DE123456789012345") is None
    assert shipping_details.eori_problem("GB123456789000") is None
    assert shipping_details.eori_problem("12345") is not None
    assert shipping_details.eori_problem("DE" + "1" * 16) is not None


def test_a_contact_email_must_look_like_one():
    assert shipping_details.email_problem("anna@hansa.de") is None
    assert shipping_details.email_problem(None) is None
    assert shipping_details.email_problem("Anna Schmidt") is not None


def test_gross_weight_is_never_less_than_the_net():
    check = shipping_details.gross_weight_problem
    assert check(Decimal("41.2"), Decimal("40"), "MT") is None
    assert check(Decimal("39.9"), Decimal("40"), "MT") is not None
    assert check(Decimal("-1"), None, "MT") is not None
    # Counted in pieces, so there is nothing to compare it with.
    assert check(Decimal("2"), Decimal("40"), "PCS") is None


# ------------------------------------------------------------ the staff side


def save_shipment(client, staff_auth, order, **changes):
    shipment = order["shipments"][0]
    body = {
        "shipment_no": shipment["shipment_no"],
        "dispatched_qty": shipment["dispatched_qty"],
        "status": shipment["status"],
        **changes,
    }
    return client.put(
        f"/api/staff/shipments/{shipment['id']}", headers=staff_auth, json=body
    )


def test_staff_save_and_read_back_the_shipment_details(client, staff_auth, order):
    saved = save_shipment(client, staff_auth, order, **SHIPMENT_DETAILS)
    assert saved.status_code == 200, saved.text

    listed = client.get("/api/staff/orders", headers=staff_auth).json()
    shipment = listed[0]["shipments"][0]
    for field, value in SHIPMENT_DETAILS.items():
        assert shipment[field] == value, field


def test_a_gross_weight_below_the_net_is_refused(client, staff_auth, order):
    refused = save_shipment(client, staff_auth, order, gross_weight="39.000")
    assert refused.status_code == 400
    assert "gross weight" in refused.json()["detail"].lower()


def test_staff_save_the_order_date_and_shipping_bill(client, staff_auth, order, customer):
    saved = client.put(
        f"/api/staff/orders/{order['id']}",
        headers=staff_auth,
        json={
            "customer_id": customer.id,
            "sales_order_no": order["sales_order_no"],
            "ordered_qty": order["ordered_qty"],
            "order_date": "2026-08-14",
            "shipping_bill_no": " 1234567 ",
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["order_date"] == "2026-08-14"
    assert saved.json()["shipping_bill_no"] == "1234567"


def test_staff_save_the_customer_details(client, staff_auth, customer):
    saved = client.put(
        f"/api/staff/customers/{customer.id}",
        headers=staff_auth,
        json={
            "name": customer.name,
            "country": customer.country,
            "address": "Hafenstrasse 1\n20095 Hamburg",
            "eori_number": "de 123456789",
            "contact_name": "Anna Schmidt",
            "contact_email": "Anna@TestCo.example",
        },
    )
    assert saved.status_code == 200, saved.text
    mine = next(c for c in saved.json()["customers"] if c["id"] == customer.id)
    assert mine["eori_number"] == "DE123456789"
    assert mine["contact_email"] == "anna@testco.example"
    assert mine["address"] == "Hafenstrasse 1\n20095 Hamburg"
    # A contact is somebody to write to, never a login.
    assert mine["logins"] == []


def test_a_bad_eori_is_refused_and_nothing_is_changed(client, staff_auth, customer, db):
    refused = client.put(
        f"/api/staff/customers/{customer.id}",
        headers=staff_auth,
        json={"name": "A New Name", "eori_number": "12345"},
    )
    assert refused.status_code == 400
    assert "EORI" in refused.json()["detail"]
    db.expire_all()
    assert db.get(Customer, customer.id).name != "A New Name"


def test_the_changes_are_recorded(client, staff_auth, order):
    save_shipment(client, staff_auth, order, port_of_discharge="Rotterdam")
    events = client.get("/api/staff/activity", headers=staff_auth).json()["events"]
    fields = [c["field"] for e in events for c in (e["changes"] or [])]
    assert "Port of discharge" in fields


# --------------------------------------------------------- the customer side


def test_the_customer_sees_the_route_and_the_box(
    client, staff_auth, customer_auth, order, customer
):
    save_shipment(client, staff_auth, order, **SHIPMENT_DETAILS)
    client.put(
        f"/api/staff/orders/{order['id']}",
        headers=staff_auth,
        json={
            "customer_id": customer.id,
            "sales_order_no": order["sales_order_no"],
            "ordered_qty": order["ordered_qty"],
            "order_date": "2026-08-14",
            "shipping_bill_no": "1234567",
        },
    )

    seen = client.get(f"/api/orders/{order['id']}", headers=customer_auth).json()
    assert seen["order_date"] == "2026-08-14"
    shipment = seen["shipments"][0]
    for field, value in SHIPMENT_DETAILS.items():
        assert shipment[field] == value, field


def test_the_customer_never_sees_the_staff_only_details(
    client, staff_auth, customer_auth, order, customer
):
    client.put(
        f"/api/staff/customers/{customer.id}",
        headers=staff_auth,
        json={"name": customer.name, "eori_number": "DE123456789",
              "contact_email": "anna@testco.example", "address": "Hafenstrasse 1"},
    )
    client.put(
        f"/api/staff/orders/{order['id']}",
        headers=staff_auth,
        json={"customer_id": customer.id, "sales_order_no": order["sales_order_no"],
              "ordered_qty": order["ordered_qty"], "shipping_bill_no": "1234567"},
    )

    replies = [
        client.get("/api/orders", headers=customer_auth).text,
        client.get(f"/api/orders/{order['id']}", headers=customer_auth).text,
        client.get("/api/me", headers=customer_auth).text,
    ]
    for reply in replies:
        for secret in ("1234567", "DE123456789", "Hafenstrasse", "anna@testco"):
            assert secret not in reply


# ------------------------------------------------------------- the importer


@pytest.fixture
def run_import(db, customer, monkeypatch):
    from scripts import import_data

    monkeypatch.setattr(import_data, "SessionLocal", lambda: nullcontext(db))

    def run(**row):
        full = {column: "" for column in import_data.ALL_COLUMNS}
        full.update(customer_code="TESTCO", sales_order_no="TEST/SO/CSV",
                    ordered_qty="100", shipment_no="TEST/SHP/CSV",
                    dispatched_qty="40")
        full.update(row)
        data, errors = import_data.check_row(full, 2)
        if not errors:
            import_data.apply_rows([data], dry_run=False, file_name="orders.csv")
        db.expire_all()
        return errors

    return run


def test_a_file_brings_the_details_in(run_import, db, customer):
    assert run_import(
        customer_eori="de 99887766", customer_contact_name="Anna Schmidt",
        order_date="2026-08-14", shipping_bill_no="7654321",
        **SHIPMENT_DETAILS,
    ) == []

    shipment = db.scalar(select(Shipment).where(Shipment.shipment_no == "TEST/SHP/CSV"))
    assert shipment.port_of_loading == "Nhava Sheva"
    assert shipment.gross_weight == Decimal("41.250")
    order = db.scalar(select(Order).where(Order.sales_order_no == "TEST/SO/CSV"))
    assert order.shipping_bill_no == "7654321"
    assert str(order.order_date) == "2026-08-14"
    assert db.get(Customer, customer.id).eori_number == "DE99887766"


def test_a_blank_column_leaves_what_staff_typed(run_import, db, customer):
    """An export made before these columns existed must not wipe them."""
    assert run_import(customer_eori="DE99887766", shipping_bill_no="7654321",
                      **SHIPMENT_DETAILS) == []
    # The same row again, every new column blank.
    assert run_import() == []

    shipment = db.scalar(select(Shipment).where(Shipment.shipment_no == "TEST/SHP/CSV"))
    assert shipment.seal_no == "SEAL123456"
    assert shipment.gross_weight == Decimal("41.250")
    order = db.scalar(select(Order).where(Order.sales_order_no == "TEST/SO/CSV"))
    assert order.shipping_bill_no == "7654321"
    assert db.get(Customer, customer.id).eori_number == "DE99887766"


def test_a_file_is_held_to_the_same_rules(run_import):
    assert run_import(gross_weight="39") != []
    assert run_import(customer_eori="12345") != []
    assert run_import(customer_contact_email="not an address") != []
    assert run_import(order_date="14/08/2026") != []
