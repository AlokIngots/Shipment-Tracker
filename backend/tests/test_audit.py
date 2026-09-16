"""The activity record: every change, who made it, and what it was before.

Three promises are tested here. Every write the admin console can make
leaves an event. An event is saved with its change or not at all, so a
refused change leaves nothing behind. And nobody -- not a customer, not
staff, not even SQL typed at the database -- can edit or remove one.
"""

from contextlib import nullcontext

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.services import accounts
from tests.conftest import png

STAFF_EMAIL = "staff@alokindia.test"

# The shipment the `order` fixture creates, so an edit can resubmit it.
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


def activity(client, staff_auth, **params) -> list[dict]:
    response = client.get("/api/staff/activity", headers=staff_auth, params=params)
    assert response.status_code == 200
    return response.json()["events"]


def latest(client, staff_auth) -> dict:
    return activity(client, staff_auth, limit=1)[0]


def fields(event) -> dict:
    """{field: (before, after)}, for comparing in one assertion."""
    return {c["field"]: (c["before"], c["after"]) for c in event["changes"] or []}


# ------------------------------------------------------------ what is kept


def test_creating_an_order_and_a_shipment_is_recorded(client, staff_auth, order):
    shipment, created = activity(client, staff_auth, limit=2)

    assert created["action"] == "order.created"
    assert created["summary"] == "Created order TEST/SO/EXP/001 for TESTCO"
    assert created["actor_email"] == STAFF_EMAIL
    assert created["source"] == "screen"
    assert fields(created)["Customer"] == (None, "TESTCO"), "named by code, not id"
    assert fields(created)["Ordered quantity"] == (None, "100.000")

    assert shipment["action"] == "shipment.created"
    assert fields(shipment)["Container number"] == (None, "CSQU3054383")


def test_an_edit_records_what_it_was_and_what_it_became(client, staff_auth, order):
    shipment_id = order["shipments"][0]["id"]
    client.put(
        f"/api/staff/shipments/{shipment_id}",
        headers=staff_auth,
        json={**SHIPMENT, "status": "In transit", "eta": "2026-10-02"},
    )
    event = latest(client, staff_auth)
    assert event["action"] == "shipment.updated"
    assert event["summary"] == "Changed shipment TEST/SHP/001-1 on order TEST/SO/EXP/001"
    assert fields(event) == {
        "Status": ("Shipped", "In transit"),
        "ETA": ("2026-09-28", "2026-10-02"),
    }, "only the two fields that changed"


def test_saving_without_changing_anything_records_nothing(client, staff_auth, order):
    """And "40" typed on the form is the same quantity as "40.000" stored."""
    before = latest(client, staff_auth)["id"]
    shipment_id = order["shipments"][0]["id"]
    assert client.put(
        f"/api/staff/shipments/{shipment_id}",
        headers=staff_auth,
        json={**SHIPMENT, "dispatched_qty": "40"},
    ).status_code == 200
    assert latest(client, staff_auth)["id"] == before


def test_a_refused_change_leaves_no_trace(client, staff_auth, order):
    before = latest(client, staff_auth)["id"]
    shipment_id = order["shipments"][0]["id"]
    refused = client.put(
        f"/api/staff/shipments/{shipment_id}",
        headers=staff_auth,
        json={**SHIPMENT, "status": "Delivered", "imo_number": "9074728"},
    )
    assert refused.status_code == 400
    assert latest(client, staff_auth)["id"] == before


def test_a_correction_backwards_says_so(client, staff_auth, order):
    shipment_id = order["shipments"][0]["id"]
    url = f"/api/staff/shipments/{shipment_id}"
    client.put(url, headers=staff_auth, json={**SHIPMENT, "status": "Delivered"})
    client.put(
        url,
        headers=staff_auth,
        json={**SHIPMENT, "status": "Packed", "allow_backwards": True},
    )
    event = latest(client, staff_auth)
    assert "correcting the status back from Delivered to Packed" in event["summary"]
    assert fields(event)["Status"] == ("Delivered", "Packed")


def test_documents_photos_and_removals_are_recorded(client, staff_auth, order):
    shipment_id = order["shipments"][0]["id"]

    def upload(name):
        client.post(
            f"/api/staff/shipments/{shipment_id}/documents",
            headers=staff_auth,
            data={"doc_type": "Packing List"},
            files={"file": (name, b"%PDF-1.4\n", "application/pdf")},
        )

    upload("first.pdf")
    assert latest(client, staff_auth)["summary"] == (
        "Added Packing List to shipment TEST/SHP/001-1"
    )
    upload("second.pdf")
    replaced = latest(client, staff_auth)
    assert replaced["action"] == "document.replaced"
    assert fields(replaced) == {"File": ("first.pdf", "second.pdf")}

    document_id = next(
        d["document_id"]
        for s in client.get("/api/staff/shipments", headers=staff_auth).json()
        if s["id"] == shipment_id
        for d in s["documents"]
        if d["document_id"]
    )
    client.delete(f"/api/staff/documents/{document_id}", headers=staff_auth)
    removed = latest(client, staff_auth)
    assert removed["summary"] == "Removed Packing List from shipment TEST/SHP/001-1"
    assert fields(removed) == {"File": ("second.pdf", None)}

    photos = client.post(
        f"/api/staff/shipments/{shipment_id}/photos",
        headers=staff_auth,
        data={"caption": "Bundle 3"},
        files=[
            ("files", ("a.png", png(), "image/png")),
            ("files", ("b.png", png(), "image/png")),
        ],
    ).json()["photos"]
    added = latest(client, staff_auth)
    assert added["summary"] == "Added 2 photo(s) to shipment TEST/SHP/001-1"
    assert [c["after"] for c in added["changes"]] == ["a.png", "b.png", "Bundle 3"]

    client.delete(f"/api/staff/photos/{photos[0]['id']}", headers=staff_auth)
    assert latest(client, staff_auth)["action"] == "photo.removed"

    client.delete(f"/api/staff/shipments/{shipment_id}", headers=staff_auth)
    gone = latest(client, staff_auth)
    assert gone["action"] == "shipment.deleted"
    assert "and 1 photo(s)" in gone["summary"]
    # What it held, so a mistaken removal can be typed back in.
    assert fields(gone)["Container number"] == ("CSQU3054383", None)

    client.delete(f"/api/staff/orders/{order['id']}", headers=staff_auth)
    deleted = latest(client, staff_auth)
    assert deleted["summary"] == "Removed order TEST/SO/EXP/001 (TESTCO)"
    assert fields(deleted)["Ordered quantity"] == ("100.000", None)


def test_account_changes_are_recorded_and_no_password_ever_is(client, staff_auth):
    created = client.post(
        "/api/staff/customers",
        headers=staff_auth,
        json={"code": "HANSA", "name": "Hansa Stahl", "country": "Germany"},
    ).json()
    customer_id = next(c["id"] for c in created["customers"] if c["code"] == "HANSA")
    client.put(
        f"/api/staff/customers/{customer_id}",
        headers=staff_auth,
        json={"name": "Hansa Stahl GmbH", "country": "Germany"},
    )
    assert fields(latest(client, staff_auth)) == {
        "Name": ("Hansa Stahl", "Hansa Stahl GmbH")
    }

    login = client.post(
        f"/api/staff/customers/{customer_id}/logins",
        headers=staff_auth,
        json={"email": "einkauf@hansa.example"},
    ).json()
    login_id = next(
        u["id"]
        for c in client.get("/api/staff/accounts", headers=staff_auth).json()["customers"]
        if c["code"] == "HANSA"
        for u in c["logins"]
    )
    reset = client.post(
        f"/api/staff/logins/{login_id}/reset-password", headers=staff_auth
    ).json()
    client.post(
        f"/api/staff/logins/{login_id}/active", headers=staff_auth, json={"active": False}
    )

    assert [e["action"] for e in activity(client, staff_auth, limit=5)] == [
        "login.deactivated",
        "login.password_reset",
        "login.created",
        "customer.updated",
        "customer.created",
    ]

    everything = client.get(
        "/api/staff/activity", headers=staff_auth, params={"limit": 500}
    ).text
    for secret in (
        login["temporary_password"],
        reset["temporary_password"],
        "staff-password-chosen",
        "pbkdf2",
    ):
        assert secret not in everything


def test_a_command_run_on_the_server_is_named_as_one(client, db, staff_auth):
    """manage_users.py calls the same service, and passes nobody as the actor."""
    accounts.create_customer(db, "SHELLCO", "Made From A Shell", None)
    event = latest(client, staff_auth)
    assert event["action"] == "customer.created"
    assert event["actor_email"] is None
    assert event["source"] == "command line"


def test_a_csv_import_records_only_what_it_changed(
    client, db, staff_auth, customer, monkeypatch
):
    from scripts import import_data

    # The importer opens a session of its own; hand it the test's instead,
    # and leave it open when the importer's `with` block ends.
    monkeypatch.setattr(import_data, "SessionLocal", lambda: nullcontext(db))

    row = {
        "customer_code": "TESTCO",
        "sales_order_no": "TEST/SO/CSV",
        "ordered_qty": "10",
        "shipment_no": "TEST/SHP/CSV-1",
        "dispatched_qty": "4",
        "shipment_status": "Packed",
    }

    def run(**changes):
        data, errors = import_data.check_row({**row, **changes}, 2)
        assert not errors
        import_data.apply_rows([data], dry_run=False, file_name="orders.csv")

    run()
    shipment, order = activity(client, staff_auth, limit=2)
    assert (order["action"], shipment["action"]) == ("order.created", "shipment.created")
    assert all(e["source"] == "csv import" for e in (order, shipment))
    assert all(e["actor_email"] is None for e in (order, shipment))
    assert "orders.csv" in order["summary"]

    run()
    assert latest(client, staff_auth)["id"] == shipment["id"], (
        "the same export again is not a change"
    )

    run(shipment_status="Shipped")
    event = latest(client, staff_auth)
    assert event["action"] == "shipment.updated"
    assert fields(event) == {"Status": ("Packed", "Shipped")}


# ------------------------------------------------------------ what is not


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE audit_events SET summary = 'tidied away'",
        "DELETE FROM audit_events",
        "TRUNCATE audit_events",
    ],
)
def test_not_even_sql_can_edit_or_remove_an_event(db, customer, statement):
    """A stolen staff session cannot tidy its tracks, and neither can a typo."""
    # The `customer` fixture was made through the service, so a row exists.
    count = db.scalar(text("SELECT count(*) FROM audit_events"))
    assert count > 0

    with pytest.raises(DBAPIError, match="append-only"):
        with db.begin_nested():
            db.execute(text(statement))

    assert db.scalar(text("SELECT count(*) FROM audit_events")) == count


def test_older_events_come_a_page_at_a_time(client, staff_auth, order):
    first = client.get(
        "/api/staff/activity", headers=staff_auth, params={"limit": 2}
    ).json()
    ids = [e["id"] for e in first["events"]]
    assert len(ids) == 2 and first["more"] is True
    assert ids == sorted(ids, reverse=True), "newest first"

    older = client.get(
        "/api/staff/activity",
        headers=staff_auth,
        params={"limit": 500, "before": ids[-1]},
    ).json()
    assert older["events"]
    assert all(e["id"] < ids[-1] for e in older["events"])
    assert older["more"] is False
