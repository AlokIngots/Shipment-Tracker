"""Tracking the box rather than the ship: the carrier registry and the link.

Two halves, as the feature has two. The first needs neither a database nor
HTTP -- it is the registry and the URL building, which the customer endpoint
and the CSV importer both lean on. The second proves the link actually
reaches a customer and that staff can set the carrier that produces it.
"""

from types import SimpleNamespace

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


# Evergreen offers no working deep link, so the rules about choosing one are
# proved through a configured template. That is not a contrivance: .env is
# exactly how a real deep link would arrive if Evergreen ever offered one.
DEEP_LINKS = {
    "EVERGREEN_BL": "https://example.test/track?bl={bl}",
    "EVERGREEN_CONTAINER": "https://example.test/track?ct={container}",
}


@pytest.fixture
def deep_links(monkeypatch):
    monkeypatch.setattr(tracking, "CARRIER_URL_OVERRIDES", DEEP_LINKS)


def test_evergreen_falls_back_to_its_search_page_today(monkeypatch):
    """Both candidate deep links were tried against the real B/L on 15 Sep
    2026 and both landed on ShipmentLink's blank Quick Tracking form. A
    button that opens a blank form having promised the shipment is worse
    than one that says so."""
    monkeypatch.setattr(tracking, "CARRIER_URL_OVERRIDES", {})
    box = tracking.container_tracking("Evergreen Line", CONTAINER, BL)
    assert box.by == "home"
    assert box.prefilled is False
    assert BL not in box.url
    assert CONTAINER not in box.url


def test_the_bill_of_lading_is_preferred_over_the_container(deep_links):
    """Both identify the shipment; the B/L is the carrier's own reference."""
    box = tracking.container_tracking("Evergreen Line", CONTAINER, BL)
    assert box.by == "bl"
    assert box.prefilled is True
    assert BL in box.url
    assert box.carrier_name == "Evergreen Line"


def test_the_container_is_used_when_there_is_no_bill_of_lading(deep_links):
    box = tracking.container_tracking("Evergreen Line", CONTAINER, None)
    assert box.by == "container"
    assert box.prefilled is True
    assert CONTAINER in box.url


def test_a_container_that_fails_its_check_digit_is_never_linked(deep_links):
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


def test_a_bill_of_lading_number_is_escaped_into_the_url(deep_links):
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


def test_an_empty_override_is_ignored_rather_than_obeyed(monkeypatch):
    """A half-written .env line must not create a link to nowhere, nor
    silently delete a working one where there is one to delete."""
    monkeypatch.setattr(tracking, "CARRIER_URL_OVERRIDES", {"EVERGREEN_BL": ""})
    box = tracking.container_tracking("Evergreen Line", CONTAINER, BL)
    assert box.by == "home"
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
    # Evergreen's search page, so the screen shows the numbers to paste.
    assert shipment["container_tracking_prefilled"] is False
    assert shipment["container_tracking_url"].startswith("https://")


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


# ------------------------------------------------ the map on the page itself


def test_the_map_is_built_from_the_imo_alone():
    """No MMSI is stored and none is needed: VesselFinder resolves the IMO
    itself. Checked against WAN HAI 359 (IMO 9554092), whose embed came back
    with MMSI 563182400 and no configuration error."""
    url = tracking.vessel_map_url("9554092")
    assert url and url.startswith("https://")
    assert "imo=9554092" in url


@pytest.mark.parametrize("imo", [None, "", "9554091", "955409", "abcdefg"])
def test_no_map_without_a_usable_imo(imo):
    """An empty map frame explains nothing, so none is drawn."""
    assert tracking.vessel_map_url(imo) is None


def test_the_map_says_nothing_about_which_order_is_being_looked_at():
    """The embed wants a referring URL. It gets the portal's own address,
    not the page the customer happens to be on."""
    url = tracking.vessel_map_url("9554092")
    assert "ra=https%3A%2F%2F" in url
    assert "/orders/" not in url


def test_the_map_url_comes_from_a_template_like_every_other_link(monkeypatch):
    monkeypatch.setattr(
        tracking, "VESSEL_MAP_URL_TEMPLATE", "https://example.test/m?i={imo}&r={ra}"
    )
    assert tracking.vessel_map_url("9554092").startswith(
        "https://example.test/m?i=9554092&r="
    )


def test_a_template_that_cannot_take_an_imo_yields_no_map(monkeypatch):
    """Rather than a frame pointed at the wrong thing."""
    monkeypatch.setattr(tracking, "VESSEL_MAP_URL_TEMPLATE", "https://example.test/m")
    assert tracking.vessel_map_url("9554092") is None
    monkeypatch.setattr(tracking, "VESSEL_MAP_URL_TEMPLATE", "")
    assert tracking.vessel_map_url("9554092") is None


# ------------------------------------------- one function, both halves alike


def test_links_for_gathers_everything_a_shipment_offers():
    row = SimpleNamespace(
        imo_number="9554092",
        container_no=CONTAINER,
        bl_number=BL,
        carrier="Evergreen Line",
    )
    links = tracking.links_for(row)
    assert "imo=9554092" in links.vessel_map_url
    assert links.vessel_map_provider == "VesselFinder"
    assert "9554092" in links.tracking_url
    assert links.tracking_provider
    assert links.container_tracking_carrier == "Evergreen Line"
    assert links.container_tracking_prefilled is False


def test_links_for_names_no_provider_it_cannot_link_to():
    """A provider name beside a missing link would read as a broken feature."""
    row = SimpleNamespace(
        imo_number=None, container_no=None, bl_number=None, carrier=None
    )
    links = tracking.links_for(row)
    assert links.vessel_map_url is None and links.vessel_map_provider is None
    assert links.tracking_url is None and links.tracking_provider is None
    assert links.container_tracking_url is None
    assert links.container_tracking_carrier is None
    assert links.container_tracking_prefilled is False


def test_a_shipment_with_no_carrier_attribute_at_all_is_survivable():
    """links_for is called with model rows today, but it is the one place
    both routers depend on, so it must not fall over on a bare object."""
    row = SimpleNamespace(imo_number="9554092", container_no=None, bl_number=None)
    assert tracking.links_for(row).container_tracking_url is None


def test_staff_and_customer_are_shown_the_same_tracking(
    client, staff_auth, customer_auth, order
):
    """The whole point of one shared function: staff on the phone to a
    customer must not be looking at a different position."""
    set_carrier(client, staff_auth, order, "Evergreen Line")

    theirs = customer_shipment(client, customer_auth, order)
    ours = client.get(f"/api/staff/orders/{order['id']}", headers=staff_auth)
    assert ours.status_code == 200, ours.text
    ours = ours.json()["shipments"][0]

    for field in (
        "vessel_map_url",
        "vessel_map_provider",
        "tracking_url",
        "tracking_provider",
        "container_tracking_url",
        "container_tracking_carrier",
        "container_tracking_prefilled",
    ):
        assert theirs[field] == ours[field], field
    assert ours["vessel_map_url"]


def test_the_customer_gets_the_map_on_the_page(client, customer_auth, order):
    shipment = customer_shipment(client, customer_auth, order)
    assert "imo=9074729" in shipment["vessel_map_url"]
    assert shipment["vessel_map_provider"] == "VesselFinder"
    # The link stays as the fallback; the map does not replace it.
    assert shipment["tracking_url"]
