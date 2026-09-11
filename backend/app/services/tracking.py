"""Where a customer goes to see a vessel live.

Today that is a public MarineTraffic page looked up by IMO number. Later it
may be a paid carrier tracking API. The portal therefore never hard-codes a
link: the server builds it from a template in .env and hands the finished
URL to the frontend. Switching provider is then a configuration change, not
a code change, and the UI does not move at all.

    TRACKING_URL_TEMPLATE=https://www.marinetraffic.com/en/ais/details/ships/imo:{imo}
    TRACKING_PROVIDER_NAME=MarineTraffic
"""

from app.core.config import TRACKING_PROVIDER_NAME, TRACKING_URL_TEMPLATE

__all__ = [
    "TRACKING_PROVIDER_NAME",
    "TRACKING_URL_TEMPLATE",
    "tidy_container_no",
    "tracking_url",
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
