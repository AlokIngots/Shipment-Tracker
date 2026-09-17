"""The only code that talks to ShipsGo (API v2, https://api.shipsgo.com/docs/v2/).

Credits
-------

ShipsGo charges one credit when a shipment is ADDED. Reading it afterwards
costs nothing. So this module has exactly one function that can spend
money, `add_shipment`, and it is written to spend at most one credit per
B/L number however it is called:

1. It first looks the B/L up in our ShipsGo account (a free read). If
   ShipsGo already has it -- added by this portal before a crash, by a
   second shipment on the same B/L, or by hand on the ShipsGo website --
   that shipment is used and nothing is spent.
2. Only then does it POST. It sends no `reference`, because ShipsGo counts
   the reference in its duplicate check and a different one would make the
   same B/L a new, charged shipment.
3. If ShipsGo answers 409 ALREADY_EXISTS, its existing shipment is used.
   ShipsGo documents that case as costing nothing.

Nobody else in the portal can POST: `_call` refuses any write except that one
path, and only when `add_shipment` asks for it.

Every answer's `X-Shipsgo-Credits-Cost` header is read. A read that ever
reports a cost raises `CreditTripwire`, which stops the refresh timer rather
than carry on spending on something that was supposed to be free.

No third-party HTTP library: the standard library is enough for two GETs and
a POST, and the API image stays as it is.
"""

import json
import logging
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from app.core import config

log = logging.getLogger("portal.shipsgo")

# ShipsGo's own rule for a booking or B/L number. Checked here so a number
# ShipsGo would refuse never leaves the building.
BOOKING_NUMBER = re.compile(r"^[A-Za-z0-9/-]+$")

_SHIPMENTS = "/ocean/shipments"


class ShipsGoError(Exception):
    """ShipsGo could not be reached, or refused. `message` is for staff."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.message = message
        self.status = status


class NotConfigured(ShipsGoError):
    """No SHIPSGO_API_KEY on this server."""


class NoCredits(ShipsGoError):
    """ShipsGo answered 402: the account has no credits left."""


class CreditTripwire(ShipsGoError):
    """A call that should have been free reported a cost."""


def configured() -> bool:
    return bool(config.SHIPSGO_API_KEY)


@dataclass(frozen=True)
class Answer:
    status: int
    body: dict
    credits_cost: int | None
    credits_remaining: int | None


def _header_int(headers, name: str) -> int | None:
    value = headers.get(name) if headers is not None else None
    try:
        return int(value) if value not in (None, "") else None
    except ValueError:
        return None


def _open(request: urllib.request.Request):
    """The one line that touches the network. Tests replace it."""
    return urllib.request.urlopen(request, timeout=config.SHIPSGO_TIMEOUT_SECONDS)


def _call(
    method: str,
    path: str,
    *,
    query: dict | None = None,
    body: dict | None = None,
    may_spend: bool = False,
) -> Answer:
    """One request to ShipsGo. Reads anything; writes only the one add."""
    if not configured():
        raise NotConfigured("Live tracking is not set up on this server (no ShipsGo key).")

    method = method.upper()
    if method != "GET" and not (method == "POST" and path == _SHIPMENTS and may_spend):
        # A guard, not a feature: nothing in the portal deletes, edits or
        # adds anything in ShipsGo except add_shipment.
        raise ShipsGoError(f"Refused {method} {path}: the portal only reads ShipsGo.")

    url = config.SHIPSGO_API_URL + path
    if query:
        url += "?" + urllib.parse.urlencode(query)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "X-Shipsgo-User-Token": config.SHIPSGO_API_KEY,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "alok-customer-portal",
        },
    )

    try:
        with _open(request) as response:
            status, headers, raw = response.status, response.headers, response.read()
    except urllib.error.HTTPError as error:
        status, headers, raw = error.code, error.headers, error.read()
    except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as error:
        raise ShipsGoError(f"ShipsGo could not be reached: {error}") from error

    try:
        parsed = json.loads(raw.decode("utf-8")) if raw else {}
    except ValueError:
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}

    answer = Answer(
        status=status,
        body=parsed,
        credits_cost=_header_int(headers, "X-Shipsgo-Credits-Cost"),
        credits_remaining=_header_int(headers, "X-Shipsgo-Credits-Remaining"),
    )

    if answer.credits_cost:
        log.warning(
            "ShipsGo %s %s cost %s credit(s); %s left",
            method, path, answer.credits_cost, answer.credits_remaining,
        )
        if method == "GET":
            raise CreditTripwire(
                f"ShipsGo charged {answer.credits_cost} credit(s) for a read "
                f"({path}). Automatic refreshing has been stopped."
            )

    if status == 401:
        raise ShipsGoError("ShipsGo refused the API key (401). Check SHIPSGO_API_KEY.", status)
    if status == 402:
        raise NoCredits("The ShipsGo account has no credits left.", status)
    if status == 403:
        raise ShipsGoError("This ShipsGo key is not allowed to do that (403).", status)
    if status == 429:
        raise ShipsGoError("ShipsGo is busy (too many requests). Try again in a minute.", status)
    if status >= 500:
        raise ShipsGoError(f"ShipsGo had a problem on its side ({status}).", status)
    return answer


def _message(answer: Answer) -> str:
    return str(answer.body.get("message") or f"HTTP {answer.status}")


# ------------------------------------------------------------------- reading


def find_by_booking(booking_number: str) -> int | None:
    """ShipsGo's id for a B/L already in our account, or None. Free."""
    answer = _call(
        "GET",
        _SHIPMENTS,
        query={"filters[booking_number]": f"eq:{booking_number}", "take": 5},
    )
    if answer.status != 200:
        raise ShipsGoError(f"ShipsGo would not list shipments: {_message(answer)}", answer.status)
    for row in answer.body.get("shipments") or []:
        if str(row.get("booking_number") or "").upper() == booking_number.upper():
            return int(row["id"])
    return None


def get_shipment(external_id: int) -> dict:
    """Everything ShipsGo knows about one shipment. Free."""
    answer = _call("GET", f"{_SHIPMENTS}/{int(external_id)}")
    if answer.status == 404:
        raise ShipsGoError("ShipsGo no longer has this shipment (404).", 404)
    if answer.status != 200 or not isinstance(answer.body.get("shipment"), dict):
        raise ShipsGoError(f"ShipsGo would not return the shipment: {_message(answer)}", answer.status)
    return answer.body["shipment"]


# --------------------------------------------------- adding: the one cost


@dataclass(frozen=True)
class Added:
    external_id: int
    # True only when this call spent a credit.
    spent: bool
    credits_remaining: int | None


def add_shipment(booking_number: str, scac: str | None = None) -> Added:
    """Make sure ShipsGo is following this B/L. Spends at most one credit.

    Call it only from the staff Enable tracking action. See the module note.
    """
    booking_number = (booking_number or "").strip()
    if not booking_number or not BOOKING_NUMBER.match(booking_number):
        raise ShipsGoError(
            "This B/L number cannot be tracked: ShipsGo accepts only letters, "
            "digits, '/' and '-'."
        )

    existing = find_by_booking(booking_number)
    if existing is not None:
        log.info("ShipsGo already follows %s (#%s); no credit spent", booking_number, existing)
        return Added(external_id=existing, spent=False, credits_remaining=None)

    body = {"booking_number": booking_number}
    if scac:
        body["carrier"] = scac
    answer = _call("POST", _SHIPMENTS, body=body, may_spend=True)

    shipment = answer.body.get("shipment") if isinstance(answer.body, dict) else None
    shipment_id = shipment.get("id") if isinstance(shipment, dict) else None

    if answer.status == 409 and shipment_id:
        log.info("ShipsGo already had %s (#%s); no credit spent", booking_number, shipment_id)
        return Added(int(shipment_id), spent=False, credits_remaining=answer.credits_remaining)
    if answer.status in (200, 201) and shipment_id:
        spent = answer.credits_cost is None or answer.credits_cost > 0
        log.info(
            "Added %s to ShipsGo (#%s); cost %s, %s credit(s) left",
            booking_number, shipment_id, answer.credits_cost, answer.credits_remaining,
        )
        return Added(int(shipment_id), spent=spent, credits_remaining=answer.credits_remaining)
    if answer.status == 422:
        raise ShipsGoError(f"ShipsGo refused this B/L number: {_message(answer)}", 422)
    raise ShipsGoError(f"ShipsGo did not add the shipment: {_message(answer)}", answer.status)
