"""The rules for the shipping details added in step 50, in one place.

The staff screens and the CSV importer both call these, so a value one of
them refuses cannot arrive through the other. Each check returns a sentence
for a person, or None when the value is fine.

Most of these fields are deliberately not checked at all. Ports, voyage and
seal numbers and container sizes are written a dozen ways by a dozen lines,
and a portal that refused one would only be refusing a real one.
"""

import re
from decimal import Decimal

# Two letters for the country, then up to 15 letters or digits. "DE" plus a
# number for Germany, "GB" plus twelve digits for the UK, "XI" for Northern
# Ireland. Nothing checks it against the EU's register: that would mean the
# portal calling somebody else's service every time staff pressed Save.
_EORI = re.compile(r"^[A-Z]{2}[A-Z0-9]{1,15}$")

# Units in which a net quantity and a gross weight can be compared.
WEIGHT_UNITS = {"MT", "KG", "T", "TON", "TONS", "TONNE", "TONNES", "KGS"}


def tidy_eori(value: str | None) -> str | None:
    """Upper case, spaces and dashes taken out; blank becomes None."""
    if value is None:
        return None
    value = re.sub(r"[\s-]", "", value).upper()
    return value or None


def eori_problem(value: str | None) -> str | None:
    if value and not _EORI.match(value):
        return (
            f"{value} is not an EORI number. It starts with two letters for "
            "the country, like DE or GB, followed by up to 15 letters or digits."
        )
    return None


def email_problem(value: str | None) -> str | None:
    # Only enough to catch a name typed into the wrong box. Whether an
    # address is real is something only sending to it can tell.
    if value and not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", value):
        return f"{value} does not look like an email address."
    return None


def gross_weight_problem(
    gross: Decimal | None, net: Decimal | None, unit: str | None
) -> str | None:
    if gross is None:
        return None
    if gross < 0:
        return "The gross weight cannot be negative."
    # Packing only ever adds weight. Compared only where both figures are a
    # weight: a shipment counted in pieces has nothing to compare.
    if (
        net is not None
        and (unit or "MT").strip().upper() in WEIGHT_UNITS
        and gross < net
    ):
        return (
            f"The gross weight ({gross}) is less than the net quantity "
            f"({net}). Gross includes the packing, so it is never less."
        )
    return None
