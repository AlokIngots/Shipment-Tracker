"""Tracking the box rather than the ship: the carrier registry and the link.

Two halves, as the feature has two. The first needs neither a database nor
HTTP -- it is the registry and the URL building, which the customer endpoint
and the CSV importer both lean on. The second proves the link actually
reaches a customer and that staff can set the carrier that produces it.
"""

import pytest

from app.services import tracking

# The real shipment this was built for, so the numbers in these tests are
# the ones that will be in the database.
BL = "EGLV100650230407"
CONTAINER = "EMCU6351083"

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


# ------------------------------------------------------------- the registry


@pytest.mark.parametrize(
    "typed",
    [
        "Evergreen Line",
        "evergreen line",
        "EVERGREEN-LINE",
        "  Evergreen   Line  ",
        "Evergreen",
        "EGLV",
        "Evergreen Marine",
    ],
)
def test_a_carrier_is_recognised_however_it_is_written(typed):
    """Staff copy the line off a Bill of Lading; they will not type a code."""
    assert tracking.carrier_key(typed) == "EVERGREEN"


@pytest.mark.parametrize("typed", ["Maersk", "MSC", "", None, "Evergreens"])
def test_an_unknown_carrier_is_not_guessed_at(typed):
    assert tracking.carrier_key(typed) is None


def test_the_stored_carrier_stays_the_human_one():
    """Matching uses a normalised copy; the database keeps what was typed."""
    assert tracking.tidy_carrier("  Evergreen   Line ") == "Evergreen Line"
    assert tracking.tidy_carrier("") is None
    assert tracking.tidy_carrier(None) is None


def test_a_known_carrier_is_named_properly_and_an_unknown_one_as_given():
    assert tracking.carrier_name("eglv") == "Evergreen Line"
    assert tracking.carrier_name("Hapag-Lloyd") == "Hapag-Lloyd"
    assert tracking.carrier_name(None) is None


def test_every_carrier_has_a_page_that_always_works():
    """`home` is the fallback the whole design rests on, so none may lack it."""
    for carrier in tracking.CARRIERS.values():
        assert carrier.home.startswith("https://"), carrier.key
    assert tracking.known_carriers() == ["Evergreen Line"]


# ------------------------------------------------------------ the link built


def test_the_bill_of_lading_is_preferred_over_the_container():
    """Both identify the shipment; the B/L is the carrier's own reference."""
    box = tracking.container_tracking("Evergreen Line", CONTAINER, BL)
    assert box.by == "bl"
    assert box.prefilled is True
    assert BL in box.url
    assert box.carrier_name == "Evergreen Line"


def test_the_container_is_used_when_there_is_no_bill_of_lading():
    box = tracking.container_tracking("Evergreen Line", CONTAINER, None)
    assert box.by == "container"
    assert box.prefilled is True
    assert CONTAINER in box.url


def test_a_container_that_fails_its_check_digit_is_never_linked():
    """The same rule as the form: never send a customer after a box that
    cannot exist. The carrier's own page is offered instead."""
    box = tracking.container_tracking("Evergreen Line", "EMCU6351084", None)
    assert box.by == "home"
    assert "6351084" not in box.url


def test_a_known_carrier_with_no_numbers_still_goes_somewhere_useful():
    """A search box beside a number to paste beats a link that errors."""
    box = tracking.container_tracking("Evergreen Line", None, None)
    assert box.by == "home"
    assert box.prefilled is False
    assert box.url.startswith("https://")


@pytest.mark.parametrize("carrier", [None, "", "Maersk"])
def test_no_link_at_all_for_a_carrier_we_cannot_track(carrier):
    """Rather than a button labelled with a line that leads nowhere."""
    assert tracking.container_tracking(carrier, CONTAINER, BL) is None


def test_a_bill_of_lading_number_is_escaped_into_the_url():
    """No line uses a space or an ampersand today, but a URL is a URL."""
    box = tracking.container_tracking("Evergreen Line", None, "EGLV 100&650")
    assert " " not in box.url
    assert "EGLV%20100%26650" in box.url


def test_env_can_correct_a_carrier_url_without_a_deploy(monkeypatch):
    """A carrier can change its tracking URL without warning, and waiting for
    a release to follow it would leave every customer on a dead link."""
    monkeypatch.setattr(
        tracking,
        "CARRIER_URL_OVERRIDES",
        {"EVERGREEN_BL": "https://example.test/track?bl={bl}"},
    )
    box = tracking.container_tracking("Evergreen Line", CONTAINER, BL)
    assert box.url == f"https://example.test/track?bl={BL}"
    assert box.prefilled is True


def test_an_empty_override_does_not_remove_the_built_in_link(monkeypatch):
    """A half-written .env line must not silently delete a working button."""
    monkeypatch.setattr(tracking, "CARRIER_URL_OVERRIDES", {"EVERGREEN_BL": ""})
    box = tracking.container_tracking("Evergreen Line", CONTAINER, BL)
    assert box.by == "bl"
    assert "shipmentlink" in box.url


# --------------------------------------------------- what a customer is sent


def set_carrier(client, staff_auth, order, carrier):
    """Put a carrier on the fixture's shipment, as the staff screen would."""
    shipment_id = order["shipments"][0]["id"]
    response = client.put(
        f"/api/staff/shipments/{shipment_id}",
        headers=staff_auth,
        json={
            **SHIPMENT,
            "carrier": carrier,
            "bl_number": BL,
            "container_no": CONTAINER,
        },
    )
    assert response.status_code == 200, response.text
    return response


def customer_shipment(client, customer_auth, order):
    response = client.get(f"/api/orders/{order['id']}", headers=customer_auth)
    assert response.status_code == 200, response.text
    return response.json()["shipments"][0]


def test_the_customer_gets_a_container_link_built_by_the_server(
    client, staff_auth, customer_auth, order
):
    set_carrier(client, staff_auth, order, "Evergreen Line")
    shipment = customer_shipment(client, customer_auth, order)

    assert shipment["carrier"] == "Evergreen Line"
    assert shipment["container_tracking_carrier"] == "Evergreen Line"
    assert shipment["container_tracking_prefilled"] is True
    assert BL in shipment["container_tracking_url"]


def test_no_carrier_means_no_container_button(client, customer_auth, order):
    """The fixture has none, which is the state every existing row is in."""
    shipment = customer_shipment(client, customer_auth, order)
    assert shipment["carrier"] is None
    assert shipment["container_tracking_url"] is None
    assert shipment["container_tracking_carrier"] is None
    assert shipment["container_tracking_prefilled"] is False


def test_an_unrecognised_carrier_is_kept_but_gets_no_button(
    client, staff_auth, customer_auth, order
):
    """It is still true, and refusing it would mean knowing every line alive."""
    set_carrier(client, staff_auth, order, "Some Feeder Line")
    shipment = customer_shipment(client, customer_auth, order)
    assert shipment["carrier"] == "Some Feeder Line"
    assert shipment["container_tracking_url"] is None


def test_the_vessel_link_is_untouched_by_any_of_this(
    client, staff_auth, customer_auth, order
):
    """Two questions, two links; the older one must not have moved."""
    set_carrier(client, staff_auth, order, "Evergreen Line")
    shipment = customer_shipment(client, customer_auth, order)
    assert "9074729" in shipment["tracking_url"]
    assert shipment["tracking_provider"]


def test_the_customer_side_is_still_read_only(client, customer_auth, order):
    """A customer cannot set a carrier, or anything else on a shipment."""
    shipment_id = order["shipments"][0]["id"]
    response = client.put(
        f"/api/staff/shipments/{shipment_id}",
        headers=customer_auth,
        json={**SHIPMENT, "carrier": "Evergreen Line"},
    )
    assert response.status_code == 403


def test_setting_the_carrier_is_in_the_activity_record(client, staff_auth, order):
    set_carrier(client, staff_auth, order, "Evergreen Line")
    event = client.get(
        "/api/staff/activity", headers=staff_auth, params={"limit": 1}
    ).json()["events"][0]
    changes = {c["field"]: (c["before"], c["after"]) for c in event["changes"] or []}
    assert changes["Carrier"] == (None, "Evergreen Line")
