"""Where a customer goes to see a vessel live.

Today that is a public MarineTraffic page looked up by IMO number. Later it
may be a paid carrier tracking API. The portal therefore never hard-codes a
link: the server builds it from a template in .env and hands the finished
URL to the frontend. Switching provider is then a configuration change, not
a code change, and the UI does not move at all.

    TRACKING_URL_TEMPLATE=https://www.marinetraffic.com/en/ais/details/ships/imo:{imo}
    TRACKING_PROVIDER_NAME=MarineTraffic

Tracking the box, not the ship
------------------------------

A vessel position answers "where is the ship", which is not the question a
buyer actually asks. "Where is my container" is answered only by the carrier,
so there is a second kind of link: the carrier's own tracking page, looked up
by Bill of Lading or container number.

That cannot be one template, because every line has its own page, so there is
a small registry below -- one entry per carrier, and adding a carrier is one
entry and no code. Each entry can be overridden from .env (see
CARRIER_URL_OVERRIDES in app/core/config.py) because a carrier can change its
URL without warning and a deploy should not be the only way to keep up.

Each entry has up to three URLs, tried in this order:

    bl           the deep link by Bill of Lading number
    container    the deep link by container number
    home         the carrier's tracking page with nothing filled in

`home` is the one that is always safe. A deep link is better when it works,
but a link that lands on an error page is worse than one that lands on a
search box next to a container number the customer can paste -- so when a
carrier has no deep link, or the shipment has neither number, the button
still goes somewhere useful and `prefilled` says which it is, so the screen
can word itself honestly.

The map on the page
-------------------

A link sends somebody away from the portal to find out something the portal
could have shown them, so the vessel's position is also embedded in the page
as a small live map. `vessel_map_url` builds the frame's address from a
template, `VESSEL_MAP_URL_TEMPLATE`, exactly as the link above is built.

It is an iframe and deliberately not the provider's own <script>. The script
VesselFinder documents writes nothing but this iframe, and running it here
would put third-party JavaScript in the portal's own origin -- where the
customer's sign-in token lives. A cross-origin frame cannot reach either.

The link stays alongside the map, because a frame can be blocked, slow or
simply not what somebody wants.
"""

from dataclasses import dataclass
from urllib.parse import quote

from app.core.config import (
    CARRIER_URL_OVERRIDES,
    PORTAL_URL,
    TRACKING_PROVIDER_NAME,
    TRACKING_URL_TEMPLATE,
    VESSEL_MAP_PROVIDER_NAME,
    VESSEL_MAP_URL_TEMPLATE,
)

__all__ = [
    "CARRIERS",
    "CarrierTracking",
    "ShipmentLinks",
    "TRACKING_PROVIDER_NAME",
    "TRACKING_URL_TEMPLATE",
    "VESSEL_MAP_PROVIDER_NAME",
    "carrier_key",
    "carrier_name",
    "container_tracking",
    "known_carriers",
    "links_for",
    "tidy_carrier",
    "tidy_container_no",
    "tracking_url",
    "valid_container_no",
    "valid_imo",
    "vessel_map_url",
]


def valid_imo(value: str) -> bool:
    """An IMO number is 7 digits where the last is a checksum of the first six.

    Each of the first six digits is multiplied by 7, 6, 5, 4, 3, 2 and the
    last digit of that total must equal the seventh digit.
    """
    if not value:
        return False
    value = value.strip()
    if not (value.isdigit() and len(value) == 7):
        return False
    total = sum(int(d) * w for d, w in zip(value[:6], range(7, 1, -1)))
    return total % 10 == int(value[6])


# ISO 6346: four letters then seven digits, e.g. MSCU1234565. The first
# three letters are the owner, the fourth is the category (U for a freight
# container, J for detachable equipment, Z for a trailer or chassis), the
# next six are the serial, and the last digit is a check digit worked out
# from all ten characters before it.
#
# Letters carry a numeric value: A is 10, and it counts up, skipping every
# multiple of 11 (so there is no 11, 22, 33...). That skip is the whole
# trick of the standard and the reason this cannot be a one-liner.
_CONTAINER_LETTER_VALUES = {}
_value = 10
for _letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
    if _value % 11 == 0:
        _value += 1
    _CONTAINER_LETTER_VALUES[_letter] = _value
    _value += 1


def valid_container_no(value: str) -> bool:
    """An ISO 6346 container number, check digit and all.

    Each of the first ten characters is weighted by 1, 2, 4, 8 ... 512, the
    total is taken modulo 11, and a result of 10 counts as 0. That has to
    equal the eleventh character.

    The point is the same as valid_imo: catch a typo here, at the one screen
    where somebody types it, rather than in front of a customer trying to
    trace a box that does not exist.
    """
    if not value:
        return False
    value = value.strip().upper().replace(" ", "").replace("-", "")
    if len(value) != 11:
        return False
    if not value[:4].isalpha() or not value[4:].isdigit():
        return False
    if value[3] not in "UJZ":
        return False

    total = 0
    for position, character in enumerate(value[:10]):
        digit = (
            _CONTAINER_LETTER_VALUES[character]
            if character.isalpha()
            else int(character)
        )
        total += digit * (2 ** position)

    return (total % 11) % 10 == int(value[10])


def tidy_container_no(value: str | None) -> str | None:
    """The form a container number is stored in: upper case, no spaces."""
    if not value:
        return None
    cleaned = value.strip().upper().replace(" ", "").replace("-", "")
    return cleaned or None


def tracking_url(imo_number: str | None) -> str | None:
    """Build the live-tracking URL for a vessel, or None if we cannot.

    Returns None for a missing, malformed or checksum-failing IMO number, so
    the portal never shows a customer a link that leads nowhere.
    """
    if not imo_number or not valid_imo(imo_number):
        return None
    if not TRACKING_URL_TEMPLATE or "{imo}" not in TRACKING_URL_TEMPLATE:
        return None
    return TRACKING_URL_TEMPLATE.format(imo=imo_number.strip())


# --------------------------------------------------- tracking the box itself

@dataclass(frozen=True)
class Carrier:
    """One shipping line, and where its own tracking page lives.

    `bl` and `container` are templates taking `{bl}` and `{container}`.
    Either may be None when the line offers no link of that kind; `home` is
    required, because it is the fallback that is always safe.
    """

    key: str
    name: str
    home: str
    bl: str | None = None
    container: str | None = None
    # Spellings a person might actually type, normalised the same way as the
    # stored value. The key itself is always matched and need not be here.
    aliases: tuple[str, ...] = ()


# One entry per carrier. Adding a line is an entry here and nothing else.
#
# Evergreen has NO deep link, and that is a finding rather than an omission.
# Both candidate GET URLs were tried against the real Bill of Lading on
# 15 Sep 2026 and both landed on ShipmentLink's blank Quick Tracking form,
# which is what a POST-only tracking form does with a GET. A button that
# opens a blank form having promised the shipment is worse than one that
# says so, so `bl` and `container` are None and the search page stands on
# its own -- with the two numbers shown beside it to copy.
#
# If Evergreen ever offers a real GET deep link, it needs no release:
# set CARRIER_URL_EVERGREEN_BL (or _CONTAINER) in .env and it is used from
# the next restart. Note that .env can only ADD or REPLACE a template, never
# remove one -- an empty value is ignored on purpose, so that a half-written
# line cannot silently delete a working link. Switching a carrier back to
# the search page is therefore a change here, as this one was.
_CARRIER_LIST = (
    Carrier(
        key="EVERGREEN",
        name="Evergreen Line",
        home="https://www.shipmentlink.com/servlet/TDB1_CargoTracking.do",
        aliases=("EVERGREENLINE", "EVERGREENMARINE", "EGLV"),
    ),
)

CARRIERS = {carrier.key: carrier for carrier in _CARRIER_LIST}

# Every spelling that resolves to a carrier, normalised.
_CARRIER_BY_ALIAS = {}
for _carrier in _CARRIER_LIST:
    for _alias in (_carrier.key, *_carrier.aliases):
        _CARRIER_BY_ALIAS[_alias] = _carrier


def tidy_carrier(value: str | None) -> str | None:
    """The form a carrier name is stored in: as typed, with the edges off.

    Deliberately not upper-cased or mapped to a key. "Evergreen Line" is what
    the Bill of Lading says and what staff should see back on the form; the
    matching is done on a normalised copy instead, so the stored value stays
    the human one.
    """
    if not value:
        return None
    return " ".join(value.split()) or None


def _normalise(value: str) -> str:
    """A carrier name reduced to letters and digits, upper case.

    "Evergreen Line", "evergreen line" and "EVERGREEN-LINE" all have to find
    the same entry, because all three will be typed.
    """
    return "".join(c for c in value.upper() if c.isalnum())


def carrier_key(value: str | None) -> str | None:
    """The registry key a typed carrier name means, or None if unknown."""
    if not value:
        return None
    carrier = _CARRIER_BY_ALIAS.get(_normalise(value))
    return carrier.key if carrier else None


def carrier_name(value: str | None) -> str | None:
    """The carrier's proper name if we know it, else the name as given."""
    key = carrier_key(value)
    return CARRIERS[key].name if key else tidy_carrier(value)


def known_carriers() -> list[str]:
    """The proper names of every carrier with a tracking page, for a form."""
    return [carrier.name for carrier in _CARRIER_LIST]


def _template(key: str, kind: str, built_in: str | None) -> str | None:
    """A carrier's URL template, letting .env win over the built-in one."""
    override = CARRIER_URL_OVERRIDES.get(f"{key}_{kind.upper()}")
    return override or built_in


@dataclass(frozen=True)
class CarrierTracking:
    """Where to send a customer who wants to know where their box is."""

    url: str
    carrier_name: str
    # False when the carrier's page opens with nothing filled in, so the
    # screen can say "paste the container number" instead of pretending.
    prefilled: bool
    # "bl", "container" or "home" -- which of the three was used.
    by: str


def container_tracking(
    carrier: str | None,
    container_no: str | None = None,
    bl_number: str | None = None,
) -> CarrierTracking | None:
    """The carrier's own tracking link for this shipment, or None.

    None when there is no carrier, or the carrier is not one the portal
    knows: a button labelled with a line we cannot link to would be a dead
    end. Never None for a known carrier, because `home` always exists.

    A Bill of Lading number is preferred over a container number. Both
    identify the shipment, but the B/L is the carrier's own reference for
    this exact consignment, while a box is reused and its number alone can
    be ambiguous on some lines.
    """
    key = carrier_key(carrier)
    if key is None:
        return None
    entry = CARRIERS[key]

    bl = (bl_number or "").strip()
    bl_template = _template(key, "bl", entry.bl)
    if bl and bl_template and "{bl}" in bl_template:
        return CarrierTracking(
            url=bl_template.format(bl=quote(bl, safe="")),
            carrier_name=entry.name,
            prefilled=True,
            by="bl",
        )

    container = tidy_container_no(container_no)
    container_template = _template(key, "container", entry.container)
    if (
        container
        and valid_container_no(container)
        and container_template
        and "{container}" in container_template
    ):
        return CarrierTracking(
            url=container_template.format(container=quote(container, safe="")),
            carrier_name=entry.name,
            prefilled=True,
            by="container",
        )

    return CarrierTracking(
        url=_template(key, "home", entry.home) or entry.home,
        carrier_name=entry.name,
        prefilled=False,
        by="home",
    )


# ------------------------------------------------- the map on the page itself

def vessel_map_url(imo_number: str | None) -> str | None:
    """The embeddable live map for this vessel, or None if we cannot build one.

    None for a missing or checksum-failing IMO number, on the same principle
    as `tracking_url`: an empty map frame explains nothing, so the screen is
    better off not drawing one.

    VesselFinder resolves the IMO to the vessel itself, so no MMSI is needed
    and none is stored -- checked against WAN HAI 359 (IMO 9554092), which
    the embed answered with MMSI 563182400 and no configuration error.
    """
    if not imo_number or not valid_imo(imo_number):
        return None
    if not VESSEL_MAP_URL_TEMPLATE or "{imo}" not in VESSEL_MAP_URL_TEMPLATE:
        return None
    return VESSEL_MAP_URL_TEMPLATE.format(
        imo=quote(imo_number.strip(), safe=""),
        # The portal's own address, not the page the customer happens to be
        # on: the embed wants a referring URL, and the base one tells
        # VesselFinder nothing about which order is being looked at.
        ra=quote(PORTAL_URL, safe=""),
    )


# ------------------------------------------- everything a shipment can offer

@dataclass(frozen=True)
class ShipmentLinks:
    """Every tracking link for one shipment, built in one place.

    Both halves of the portal show the same three things, and they must not
    drift: a customer and the member of staff on the phone to them need to
    be looking at the same position. So neither router works any of this out
    for itself -- they both ask here.
    """

    # The vessel's live position, embedded in the page.
    vessel_map_url: str | None
    vessel_map_provider: str | None
    # The same vessel on the provider's own site, kept as the fallback for
    # when an embedded frame is blocked, slow, or simply not what is wanted.
    tracking_url: str | None
    tracking_provider: str | None
    # The carrier's own page: where the box is, not where the ship is.
    container_tracking_url: str | None
    container_tracking_carrier: str | None
    container_tracking_prefilled: bool


def links_for(shipment) -> ShipmentLinks:
    """Every tracking link for a shipment row, for either half of the portal."""
    vessel_map = vessel_map_url(shipment.imo_number)
    vessel_link = tracking_url(shipment.imo_number)
    box = container_tracking(
        getattr(shipment, "carrier", None),
        shipment.container_no,
        shipment.bl_number,
    )
    return ShipmentLinks(
        vessel_map_url=vessel_map,
        vessel_map_provider=VESSEL_MAP_PROVIDER_NAME if vessel_map else None,
        tracking_url=vessel_link,
        tracking_provider=TRACKING_PROVIDER_NAME if vessel_link else None,
        container_tracking_url=box.url if box else None,
        container_tracking_carrier=box.carrier_name if box else None,
        container_tracking_prefilled=bool(box and box.prefilled),
    )
