"""What a customer may see, and — mostly — what they may not.

The recurring assertion in this file is 404, not 403. Asking for another
customer's order must look exactly like asking for one that does not exist,
or the API answers "which order numbers belong to somebody else?" for free.
"""

from tests.conftest import png


def test_a_customer_sees_only_their_own_orders(
    client, customer_auth, other_auth, order
):
    mine = client.get("/api/orders", headers=customer_auth).json()
    assert [o["sales_order_no"] for o in mine] == ["TEST/SO/EXP/001"]

    theirs = client.get("/api/orders", headers=other_auth).json()
    assert theirs == []


def test_somebody_elses_order_is_404_not_403(client, other_auth, order):
    refused = client.get(f"/api/orders/{order['id']}", headers=other_auth)
    assert refused.status_code == 404


def test_the_quantities_add_up(client, customer_auth, order, staff_auth):
    detail = client.get(f"/api/orders/{order['id']}", headers=customer_auth).json()
    assert detail["ordered_qty"] == "100.000"
    assert detail["dispatched_qty"] == "40.000"
    assert detail["balance_qty"] == "60.000"

    client.post(
        f"/api/staff/orders/{order['id']}/shipments",
        headers=staff_auth,
        json={"shipment_no": "TEST/SHP/001-2", "dispatched_qty": "35.500"},
    )
    detail = client.get(f"/api/orders/{order['id']}", headers=customer_auth).json()
    assert detail["dispatched_qty"] == "75.500"
    assert detail["balance_qty"] == "24.500"


def test_the_shipment_carries_what_the_customer_needs(client, customer_auth, order):
    shipment = client.get(
        f"/api/orders/{order['id']}", headers=customer_auth
    ).json()["shipments"][0]

    assert shipment["vessel_name"] == "MV Test"
    assert shipment["container_no"] == "CSQU3054383"
    assert shipment["bl_number"] == "MAEU-TEST-1"
    assert shipment["status"] == "Shipped"
    assert shipment["etd"] == "2026-09-01"


def test_the_tracking_link_is_built_by_the_server(client, customer_auth, order):
    """So changing provider is configuration, and never a dead link."""
    shipment = client.get(
        f"/api/orders/{order['id']}", headers=customer_auth
    ).json()["shipments"][0]
    assert shipment["tracking_url"] and "9074729" in shipment["tracking_url"]
    assert shipment["tracking_provider"]


def test_no_link_when_the_imo_is_missing(client, staff_auth, customer_auth, order):
    client.put(
        f"/api/staff/shipments/{order['shipments'][0]['id']}",
        headers=staff_auth,
        json={"shipment_no": "TEST/SHP/001-1", "dispatched_qty": "40.000"},
    )
    shipment = client.get(
        f"/api/orders/{order['id']}", headers=customer_auth
    ).json()["shipments"][0]
    assert shipment["tracking_url"] is None
    assert shipment["tracking_provider"] is None


# --------------------------------------------------------------- documents


def test_a_document_reaches_its_owner_and_nobody_else(
    client, staff_auth, customer_auth, other_auth, order
):
    shipment_id = order["shipments"][0]["id"]
    client.post(
        f"/api/staff/shipments/{shipment_id}/documents",
        headers=staff_auth,
        data={"doc_type": "Bill of Lading"},
        files={"file": ("bl.pdf", b"%PDF-1.4 bill of lading\n", "application/pdf")},
    )

    detail = client.get(f"/api/orders/{order['id']}", headers=customer_auth).json()
    document = detail["shipments"][0]["documents"][0]
    assert document["doc_type"] == "Bill of Lading"
    assert document["available"] is True

    got = client.get(f"/api/documents/{document['id']}/download", headers=customer_auth)
    assert got.status_code == 200
    assert got.content == b"%PDF-1.4 bill of lading\n"

    assert client.get(
        f"/api/documents/{document['id']}/download", headers=other_auth
    ).status_code == 404


# ------------------------------------------------------------------ photos


def test_photos_reach_their_owner_and_nobody_else(
    client, staff_auth, customer_auth, other_auth, order
):
    shipment_id = order["shipments"][0]["id"]
    image = png()
    client.post(
        f"/api/staff/shipments/{shipment_id}/photos",
        headers=staff_auth,
        data={"caption": "Bundle 12"},
        files=[("files", ("bundle.png", image, "image/png"))],
    )

    shipment = client.get(
        f"/api/orders/{order['id']}", headers=customer_auth
    ).json()["shipments"][0]
    assert len(shipment["photos"]) == 1
    assert shipment["photos"][0]["caption"] == "Bundle 12"

    photo_id = shipment["photos"][0]["id"]
    got = client.get(f"/api/photos/{photo_id}", headers=customer_auth)
    assert got.status_code == 200
    assert got.content == image, "the bytes served must be the bytes stored"
    assert got.headers["content-type"] == "image/png", "not hard-coded as a PDF"

    assert client.get(f"/api/photos/{photo_id}", headers=other_auth).status_code == 404


# ------------------------------------------------- the read-only guarantee


def test_the_customer_half_of_the_api_has_no_writes():
    """The rule, checked against the routing table rather than trusted.

    If a POST, PUT, PATCH or DELETE ever appears outside /api/staff, this
    fails -- which is the point. Changing a password is the one exception,
    because it changes nothing but the caller's own password.
    """
    import main

    allowed_writes = {"/api/login", "/api/change-password"}
    offenders = [
        f"{method} {path}"
        for path, operations in main.app.openapi()["paths"].items()
        for method in (m.upper() for m in operations)
        if not path.startswith("/api/staff")
        and method != "GET"
        and path not in allowed_writes
    ]
    assert offenders == []


def test_staff_have_no_orders_of_their_own(client, staff_auth):
    """Said plainly, rather than returning an empty list they would puzzle over."""
    refused = client.get("/api/orders", headers=staff_auth)
    assert refused.status_code == 403
    assert "staff" in refused.json()["detail"].lower()


def test_nothing_is_readable_without_signing_in(client, order):
    for path in (
        "/api/orders",
        f"/api/orders/{order['id']}",
        "/api/me",
        "/api/documents/1/download",
        "/api/photos/1",
        "/api/photos/1/thumbnail",
    ):
        assert client.get(path).status_code == 401, path
