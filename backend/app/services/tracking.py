"""Where a customer goes to see where their cargo actually is.

Not where the ship is. The portal used to link to a vessel's live position
and, briefly, to embed a map of it, and both were removed on 15 Sep 2026
because they answered the wrong question. Export cargo is transshipped: the
boxes come off at a hub and the first vessel sails on to a different voyage,
so a map of that hull shows a ship going somewhere the cargo is not. WAN HAI
359, carrying an Antwerp order, read Chennai to China. A customer reading
that would draw exactly the wrong conclusion, and a portal that invites the
wrong conclusion is worse than one that says less.

What is left follows the box: the carrier's own container tracking, looked
up by Bill of Lading or container number. The carrier knows about the
transshipment because the carrier arranged it.

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

The vessel name and IMO number are still stored and still shown to staff.
They are on the paperwork and identify the booking; it is only the claim to
say where they are *now* that was wrong.
"""

from dataclasses import dataclass
from urllib.parse import quote

from app.core.config import CARRIER_URL_OVERRIDES

__all__ = [
    "CARRIERS",
    "CarrierTracking",
    "ShipmentLinks",
    "carrier_key",
    "carrier_name",
    "carrier_scac",
    "container_tracking",
    "known_carriers",
    "links_for",
    "tidy_carrier",
    "tidy_container_no",
    "valid_container_no",
    "valid_imo",
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
    # The line's SCAC code, which is how ShipsGo names a carrier. Optional:
    # without it ShipsGo works the line out from the B/L number itself.
    scac: str | None = None


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
        scac="EGLV",
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


def carrier_scac(value: str | None) -> str | None:
    """The SCAC code for a typed carrier name, or None if we do not know it."""
    key = carrier_key(value)
    return CARRIERS[key].scac if key else None


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


# ------------------------------------------- everything a shipment can offer

@dataclass(frozen=True)
class ShipmentLinks:
    """Every tracking link for one shipment, built in one place.

    One link now, where there were three. It stays a dataclass and a shared
    function because both halves of the portal show it, and staff on the
    phone to a customer must not be looking at something different.
    """

    container_tracking_url: str | None
    container_tracking_carrier: str | None
    container_tracking_prefilled: bool


def links_for(shipment) -> ShipmentLinks:
    """Every tracking link for a shipment row, for either half of the portal."""
    box = container_tracking(
        getattr(shipment, "carrier", None),
        shipment.container_no,
        shipment.bl_number,
    )
    return ShipmentLinks(
        container_tracking_url=box.url if box else None,
        container_tracking_carrier=box.carrier_name if box else None,
        container_tracking_prefilled=bool(box and box.prefilled),
    )
