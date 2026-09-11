"""The admin console: everything that writes, and everything it refuses.

Two themes run through this file. First, the screen and the CSV importer
must agree — both go through the same services, and a rule tested here is
the rule the importer applies. Second, nothing here may be reachable by a
customer, which is asserted route by route at the bottom.
"""

import pytest

from tests.conftest import png


def test_creating_an_order(client, staff_auth, customer):
    created = client.post(
        "/api/staff/orders",
        headers=staff_auth,
        json={
            "customer_id": customer.id,
            "sales_order_no": "TEST/SO/NEW",
            "ordered_qty": "12.500",
            "grade": "316L",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["ordered_qty"] == "12.500", "the decimal is kept exactly"
    assert body["balance_qty"] == "12.500", "nothing shipped, so all outstanding"
    assert body["unit"] == "MT", "the default unit"
    assert body["customer_code"] == "TESTCO"


@pytest.mark.parametrize(
    "changes, why",
    [
        ({"sales_order_no": "TEST/SO/EXP/001"}, "a duplicate sales order number"),
        ({"sales_order_no": "   "}, "a blank sales order number"),
        ({"ordered_qty": "-1"}, "a negative quantity"),
        ({"customer_id": 999999}, "a customer that does not exist"),
    ],
)
def test_an_order_that_should_be_refused(client, staff_auth, customer, order, changes, why):
    body = {
        "customer_id": customer.id,
        "sales_order_no": "TEST/SO/OTHER",
        "ordered_qty": "5",
        **changes,
    }
    assert client.post(
        "/api/staff/orders", headers=staff_auth, json=body
    ).status_code == 400, why


def test_a_blank_box_is_stored_as_absent_not_empty(client, staff_auth, customer, order):
    """Or the portal shows a customer an order whose grade is ''."""
    edited = client.put(
        f"/api/staff/orders/{order['id']}",
        headers=staff_auth,
        json={
            "customer_id": customer.id,
            "sales_order_no": "TEST/SO/EXP/001",
            "ordered_qty": "100.000",
            "grade": "",
        },
    ).json()
    assert edited["grade"] is None


def test_a_sales_order_number_does_not_clash_with_itself(client, staff_auth, customer, order):
    """Editing an order without changing its number must not be refused."""
    assert client.put(
        f"/api/staff/orders/{order['id']}",
        headers=staff_auth,
        json={
            "customer_id": customer.id,
            "sales_order_no": "TEST/SO/EXP/001",
            "ordered_qty": "150.000",
        },
    ).status_code == 200


# --------------------------------------------------------------- shipments


@pytest.mark.parametrize(
    "changes, why",
    [
        ({"imo_number": "9074728"}, "an IMO whose check digit is wrong"),
        ({"container_no": "MSCU1234565"}, "a container check digit off by one"),
        ({"container_no": "MSUC1234566"}, "two container letters transposed"),
        ({"etd": "2026-09-28", "eta": "2026-09-01"}, "arriving before departing"),
        ({"dispatched_qty": "-5"}, "a negative dispatched quantity"),
        ({"shipment_no": "TEST/SHP/001-1"}, "a duplicate shipment number"),
        ({"shipment_no": " "}, "a blank shipment number"),
        ({"status": "Nearly there"}, "a status the portal does not know"),
    ],
)
def test_a_shipment_that_should_be_refused(client, staff_auth, order, changes, why):
    body = {"shipment_no": "TEST/SHP/NEW", "dispatched_qty": "1", **changes}
    assert client.post(
        f"/api/staff/orders/{order['id']}/shipments", headers=staff_auth, json=body
    ).status_code == 400, why


def test_a_container_number_is_stored_one_way(client, staff_auth, order):
    created = client.post(
        f"/api/staff/orders/{order['id']}/shipments",
        headers=staff_auth,
        json={
            "shipment_no": "TEST/SHP/TIDY",
            "dispatched_qty": "1",
            "container_no": "  mscu 123456-6 ",
        },
    ).json()
    tidied = [s for s in created["shipments"] if s["shipment_no"] == "TEST/SHP/TIDY"]
    assert tidied[0]["container_no"] == "MSCU1234566"


def test_a_bl_number_has_no_format_imposed_on_it(client, staff_auth, order):
    """Every carrier numbers its own way; a format check only refuses real ones."""
    created = client.post(
        f"/api/staff/orders/{order['id']}/shipments",
        headers=staff_auth,
        json={
            "shipment_no": "TEST/SHP/BL",
            "dispatched_qty": "1",
            "bl_number": "anything/the-carrier/likes 123",
        },
    )
    assert created.status_code == 201


def test_the_status_sequence_only_goes_forward(client, staff_auth, order):
    shipment_id = order["shipments"][0]["id"]
    body = {"shipment_no": "TEST/SHP/001-1", "dispatched_qty": "40.000"}

    assert client.put(
        f"/api/staff/shipments/{shipment_id}",
        headers=staff_auth,
        json={**body, "status": "Delivered"},
    ).status_code == 200

    backwards = client.put(
        f"/api/staff/shipments/{shipment_id}",
        headers=staff_auth,
        json={**body, "status": "Packed"},
    )
    assert backwards.status_code == 400
    assert "correction" in backwards.json()["detail"].lower()

    assert client.put(
        f"/api/staff/shipments/{shipment_id}",
        headers=staff_auth,
        json={**body, "status": "Packed", "allow_backwards": True},
    ).status_code == 200


# ---------------------------------------------------------------- deleting


def test_nothing_is_deleted_while_something_hangs_off_it(client, staff_auth, order):
    shipment_id = order["shipments"][0]["id"]

    refused = client.delete(f"/api/staff/orders/{order['id']}", headers=staff_auth)
    assert refused.status_code == 400, "an order with a shipment"
    assert "shipment" in refused.json()["detail"].lower()

    client.post(
        f"/api/staff/shipments/{shipment_id}/documents",
        headers=staff_auth,
        data={"doc_type": "Packing List"},
        files={"file": ("pl.pdf", b"%PDF-1.4\n", "application/pdf")},
    )
    refused = client.delete(f"/api/staff/shipments/{shipment_id}", headers=staff_auth)
    assert refused.status_code == 400, "a shipment with a document"

    documents = client.get("/api/staff/shipments", headers=staff_auth).json()
    document_id = next(
        d["document_id"]
        for s in documents
        if s["id"] == shipment_id
        for d in s["documents"]
        if d["document_id"]
    )
    assert client.delete(
        f"/api/staff/documents/{document_id}", headers=staff_auth
    ).status_code == 200
    assert client.delete(
        f"/api/staff/shipments/{shipment_id}", headers=staff_auth
    ).status_code == 200
    assert client.delete(
        f"/api/staff/orders/{order['id']}", headers=staff_auth
    ).status_code == 200


def test_photos_do_not_block_a_shipment_from_being_removed(client, staff_auth, order):
    """A snapshot of a bundle is not filed paperwork. It goes with it."""
    shipment_id = order["shipments"][0]["id"]
    client.post(
        f"/api/staff/shipments/{shipment_id}/photos",
        headers=staff_auth,
        files=[("files", ("a.png", png(), "image/png"))],
    )
    removed = client.delete(f"/api/staff/shipments/{shipment_id}", headers=staff_auth)
    assert removed.status_code == 200
    assert "photo" in removed.json()["detail"].lower()


# ------------------------------------------------------------------ photos


def test_several_photos_in_one_upload(client, staff_auth, order):
    shipment_id = order["shipments"][0]["id"]
    added = client.post(
        f"/api/staff/shipments/{shipment_id}/photos",
        headers=staff_auth,
        data={"caption": "Before wrapping"},
        files=[
            ("files", ("one.png", png(), "image/png")),
            ("files", ("two.png", png(), "image/png")),
        ],
    )
    assert added.status_code == 201
    assert len(added.json()["photos"]) == 2
    assert all(p["caption"] == "Before wrapping" for p in added.json()["photos"])


def test_a_later_upload_adds_rather_than_replaces(client, staff_auth, order):
    """The whole reason photos are not a kind of document."""
    shipment_id = order["shipments"][0]["id"]
    client.post(
        f"/api/staff/shipments/{shipment_id}/photos",
        headers=staff_auth,
        files=[("files", ("one.png", png(), "image/png"))],
    )
    second = client.post(
        f"/api/staff/shipments/{shipment_id}/photos",
        headers=staff_auth,
        files=[("files", ("two.png", png(), "image/png"))],
    )
    assert len(second.json()["photos"]) == 2


def test_one_bad_file_keeps_none_of_the_batch(client, staff_auth, order):
    """Better than leaving somebody to work out which three of five landed."""
    shipment_id = order["shipments"][0]["id"]
    refused = client.post(
        f"/api/staff/shipments/{shipment_id}/photos",
        headers=staff_auth,
        files=[
            ("files", ("ok1.png", png(), "image/png")),
            ("files", ("ok2.png", png(), "image/png")),
            ("files", ("invoice.pdf", b"%PDF-1.4\n", "application/pdf")),
        ],
    )
    assert refused.status_code == 400
    assert "invoice.pdf" in refused.json()["detail"], "it names the file that was wrong"

    left = client.get(
        f"/api/staff/shipments/{shipment_id}/photos", headers=staff_auth
    ).json()
    assert left["photos"] == []


def test_staff_can_see_the_photo_they_uploaded(client, staff_auth, order):
    """/api/photos is the customer's route and refuses staff by design."""
    shipment_id = order["shipments"][0]["id"]
    added = client.post(
        f"/api/staff/shipments/{shipment_id}/photos",
        headers=staff_auth,
        files=[("files", ("a.png", png(), "image/png"))],
    ).json()
    photo_id = added["photos"][0]["id"]

    assert client.get(f"/api/staff/photos/{photo_id}", headers=staff_auth).status_code == 200
    assert client.get(f"/api/photos/{photo_id}", headers=staff_auth).status_code == 403


def test_a_document_of_the_same_type_replaces_the_previous_one(client, staff_auth, order):
    shipment_id = order["shipments"][0]["id"]
    for body in (b"%PDF-1.4 first\n", b"%PDF-1.4 second\n"):
        client.post(
            f"/api/staff/shipments/{shipment_id}/documents",
            headers=staff_auth,
            data={"doc_type": "Commercial Invoice"},
            files={"file": ("ci.pdf", body, "application/pdf")},
        )
    listed = client.get("/api/staff/shipments", headers=staff_auth).json()
    invoices = [
        d
        for s in listed
        if s["id"] == shipment_id
        for d in s["documents"]
        if d["doc_type"] == "Commercial Invoice"
    ]
    assert len(invoices) == 1, "one Commercial Invoice, not two"


# --------------------------------------------------------- who may do this


ADMIN_CALLS = [
    ("get", "/api/staff/orders", {}),
    ("post", "/api/staff/orders", {"json": {}}),
    ("get", "/api/staff/shipments", {}),
    ("get", "/api/staff/accounts", {}),
    ("post", "/api/staff/customers", {"json": {"code": "X", "name": "X"}}),
    ("get", "/api/staff/customers", {}),
]


@pytest.mark.parametrize("method, path, kwargs", ADMIN_CALLS)
def test_a_customer_cannot_reach_the_admin_console(
    client, customer_auth, method, path, kwargs
):
    response = getattr(client, method)(path, headers=customer_auth, **kwargs)
    assert response.status_code == 403


@pytest.mark.parametrize("method, path, kwargs", ADMIN_CALLS)
def test_nobody_signed_in_cannot_reach_it_either(client, method, path, kwargs):
    response = getattr(client, method)(path, **kwargs)
    assert response.status_code == 401
