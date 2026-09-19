"""Step 51: the customer is told which documents are still to come.

From the pre-pilot audit: a buyer saw only what had been attached, and had
to guess whether a Bill of Lading was late or simply not coming. The order
page now lists the expected documents not attached yet. The wording changes
in the same step (Partly shipped, the contact line) are screen-only.
"""

from app.models.document import EXPECTED_DOCUMENTS


def shipment_seen(client, customer_auth, order):
    seen = client.get(f"/api/orders/{order['id']}", headers=customer_auth).json()
    return seen["shipments"][0]


def test_a_new_shipment_has_every_document_to_come(client, customer_auth, order):
    assert shipment_seen(client, customer_auth, order)["documents_to_come"] == EXPECTED_DOCUMENTS


def test_an_attached_document_is_no_longer_to_come(client, staff_auth, customer_auth, order):
    uploaded = client.post(
        f"/api/staff/shipments/{order['shipments'][0]['id']}/documents",
        headers=staff_auth,
        data={"doc_type": "Packing List"},
        files={"file": ("pl.pdf", b"%PDF-1.4\n", "application/pdf")},
    )
    assert uploaded.status_code in (200, 201), uploaded.text

    to_come = shipment_seen(client, customer_auth, order)["documents_to_come"]
    assert "Packing List" not in to_come
    assert to_come == [d for d in EXPECTED_DOCUMENTS if d != "Packing List"]


def test_a_cancelled_shipment_has_nothing_to_come(client, staff_auth, customer_auth, order):
    shipment = order["shipments"][0]
    cancelled = client.put(
        f"/api/staff/shipments/{shipment['id']}",
        headers=staff_auth,
        json={
            "shipment_no": shipment["shipment_no"],
            "dispatched_qty": shipment["dispatched_qty"],
            "status": "Cancelled",
        },
    )
    assert cancelled.status_code == 200, cancelled.text
    assert shipment_seen(client, customer_auth, order)["documents_to_come"] == []


def test_the_staff_documents_page_still_expects_the_same_four():
    """The list moved beside the model; the staff page must still use it."""
    from app.routers.admin import documents

    assert documents.EXPECTED_DOCUMENTS is EXPECTED_DOCUMENTS
