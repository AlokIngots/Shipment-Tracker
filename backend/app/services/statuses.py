"""The lifecycle a shipment moves through, and the rules about moving.

Until now `status` was a free-text column. Anything could be typed into it,
nothing checked the spelling, and a shipment could go from Delivered back to
Packed without a murmur. "Packed" had never once been used, because nothing
offered it.

The sequence
------------

    1  In production
    2  Packed
    3  Shipped
    4  In transit
    5  Delivered

    -  Cancelled       outside the numbering: reachable from anywhere,
                       and leaving it counts as a correction

Four of those are the steps the business asked for. **"In transit" is the
fifth and it was already in the data** — the demo orders use it, the
notification defaults name it, and the vessel-tracking feature is built
around it. Rewriting those rows to "Shipped" would have thrown away a real
distinction (loaded, versus actually at sea) to make the list shorter, so it
was kept and placed where it belongs, between Shipped and Delivered.

Moving backwards
----------------

Refused by default: Delivered to Packed is almost always a misclick, and a
customer who has been told their goods arrived should not silently see them
un-arrive. It is allowed when the caller says explicitly that it is a
correction, because the alternative — no way back from a fat-fingered
Delivered — is worse than the misclick.
"""

# In order. The position in this list is the step number.
SEQUENCE = [
    "In production",
    "Packed",
    "Shipped",
    "In transit",
    "Delivered",
]

# Reachable from any step, and not part of the progression.
CANCELLED = "Cancelled"

ALL_STATUSES = SEQUENCE + [CANCELLED]

# Matched case-insensitively, and with the odd spelling somebody will use.
# The value stored is always the canonical one on the right.
_CANONICAL = {s.lower(): s for s in ALL_STATUSES}
_CANONICAL.update({
    "in-transit": "In transit",
    "intransit": "In transit",
    "in production": "In production",
    "in-production": "In production",
    "inproduction": "In production",
    "canceled": "Cancelled",   # American spelling, one L
})


class StatusProblem(Exception):
    """A status that will not be accepted, with a reason a person can read."""


def canonical(value: str | None) -> str | None:
    """The stored form of a status, or None for "not set yet".

    Raises StatusProblem for anything not in the list, naming what is.
    """
    if value is None:
        return None
    cleaned = " ".join(value.split())
    if not cleaned:
        return None

    resolved = _CANONICAL.get(cleaned.lower())
    if resolved is None:
        raise StatusProblem(
            f"{cleaned!r} is not a status this portal knows. "
            f"Use one of: {', '.join(ALL_STATUSES)}."
        )
    return resolved


def step(value: str | None) -> int | None:
    """Which step a status is, 1-based. None for unset or Cancelled."""
    if not value or value == CANCELLED:
        return None
    try:
        return SEQUENCE.index(value) + 1
    except ValueError:
        return None


def check_move(current: str | None, new: str | None, *, allow_backwards: bool) -> None:
    """Refuse a move back down the sequence unless it is a stated correction."""
    if allow_backwards or current is None or new is None:
        return
    if current == new:
        return

    # Leaving Cancelled is a correction: something was cancelled and is not.
    if current == CANCELLED:
        raise StatusProblem(
            f"{current} is not a step in the sequence, so moving to {new} "
            "counts as a correction. Confirm it and it will be saved."
        )

    # Moving to Cancelled is always allowed. Things do get cancelled.
    if new == CANCELLED:
        return

    here, there = step(current), step(new)
    if here is None or there is None:
        return
    if there < here:
        raise StatusProblem(
            f"That moves this back from {current} (step {here}) to {new} "
            f"(step {there}). If the earlier status was wrong, confirm the "
            "correction and it will be saved."
        )


# ------------------------------------------------------------------ an order
#
# Nobody types an order's status. It is worked out from the order's shipments
# every time it is read, so it cannot go out of step with them -- which a
# typed one did: "In production" on an order whose every shipment said
# Delivered. Two things are still decided by hand, because only a person
# knows them: which shipment is the last one, and whether the order has been
# cancelled.

# Only an order ever says this. Some of it has left the factory, and either
# the rest has not or nobody has ticked a shipment as the last one yet.
PART_SHIPPED = "Part shipped"

# A shipment at this step or beyond has left the factory.
_LEFT_THE_FACTORY = SEQUENCE.index("Shipped") + 1


def order_status(cancelled: bool, shipments) -> str:
    """What an order says, worked out from its shipments.

    ``shipments`` is anything carrying ``status`` and ``is_final``. The rules,
    in the order they are tried:

    - an order marked cancelled says Cancelled, whatever has shipped
    - a cancelled shipment is left out, as though it were never there
    - no shipments: In production
    - the last shipment is ticked and every shipment has left the factory:
      the step of the one furthest behind (Shipped, In transit, Delivered)
    - anything has left the factory: Part shipped
    - the last shipment is ticked but nothing has left: the step of the one
      furthest behind (In production, Packed)
    - otherwise In production, because more of the order is still to make

    The last shipment is ticked by staff rather than worked out from the
    quantities, because steel orders finish a few tonnes over or under and
    only staff know which lot is the last.
    """
    if cancelled:
        return CANCELLED

    live = [s for s in shipments if s.status != CANCELLED]
    if not live:
        return SEQUENCE[0]

    # A shipment with no status yet -- or one written before step 18 that
    # the sequence does not know -- has not started.
    steps = [step(s.status) or 1 for s in live]
    behind, ahead = min(steps), max(steps)
    finished = any(s.is_final for s in live)

    if finished and behind >= _LEFT_THE_FACTORY:
        return SEQUENCE[behind - 1]
    if ahead >= _LEFT_THE_FACTORY:
        return PART_SHIPPED
    if finished:
        return SEQUENCE[behind - 1]
    return SEQUENCE[0]
