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

__all__ = ["TRACKING_PROVIDER_NAME", "TRACKING_URL_TEMPLATE", "tracking_url", "valid_imo"]


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
