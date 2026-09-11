"""The rules, tested on their own: IMO, container, status, rate limiting.

No database and no HTTP. These are the functions that both the admin screen
and the CSV importer call, so a change that breaks one breaks both, and this
is where that shows up first and most cheaply.
"""

import importlib.util
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services import ratelimit, statuses, tracking

# ------------------------------------------------------------------- IMO


@pytest.mark.parametrize(
    "value, valid, why",
    [
        ("9074729", True, "a real IMO number"),
        ("9633082", True, "another real one"),
        ("9074728", False, "check digit off by one"),
        ("907472", False, "six digits"),
        ("90747299", False, "eight digits"),
        ("907472A", False, "a letter in it"),
        ("", False, "empty"),
    ],
)
def test_valid_imo(value, valid, why):
    assert tracking.valid_imo(value) is valid, why


def test_tracking_url_only_for_a_usable_imo():
    """A dead link is worse than no link, so a bad IMO produces neither."""
    assert tracking.tracking_url("9074729")
    assert "9074729" in tracking.tracking_url("9074729")
    assert tracking.tracking_url("9074728") is None
    assert tracking.tracking_url(None) is None
    assert tracking.tracking_url("") is None


# ------------------------------------------------------------- container


@pytest.mark.parametrize(
    "value, valid, why",
    [
        ("CSQU3054383", True, "the example in the ISO 6346 standard"),
        ("MSCU1234566", True, "check digit computed by hand: 5528 % 11 = 6"),
        ("MSCU1234565", False, "same number, check digit off by one"),
        ("MSUC1234566", False, "two letters transposed"),
        ("MSCA1234566", False, "category letter must be U, J or Z"),
        ("MSCU123456", False, "ten characters"),
        ("MSCU12345AB", False, "letters where the serial belongs"),
        ("mscu1234566", True, "lower case is accepted"),
        ("MSCU 123456 6", True, "spaces are accepted"),
        ("MSCU-123456-6", True, "hyphens are accepted"),
        ("", False, "empty"),
    ],
)
def test_valid_container_no(value, valid, why):
    assert tracking.valid_container_no(value) is valid, why


def test_container_numbers_are_stored_one_way():
    """However it is typed, one container is one string in the database."""
    forms = ["MSCU1234566", "mscu1234566", "MSCU 123456 6", " mscu-123456-6 "]
    assert {tracking.tidy_container_no(f) for f in forms} == {"MSCU1234566"}
    assert tracking.tidy_container_no("") is None
    assert tracking.tidy_container_no(None) is None


# ---------------------------------------------------------------- status


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("shipped", "Shipped"),
        ("  IN TRANSIT ", "In transit"),
        ("in-transit", "In transit"),
        ("In production", "In production"),
        ("canceled", "Cancelled"),
        ("", None),
        (None, None),
    ],
)
def test_status_is_normalised(raw, expected):
    assert statuses.canonical(raw) == expected


def test_an_invented_status_is_refused_and_says_what_is_allowed():
    with pytest.raises(statuses.StatusProblem) as refused:
        statuses.canonical("Nearly there")
    message = str(refused.value)
    assert "Nearly there" in message
    for name in statuses.ALL_STATUSES:
        assert name in message


@pytest.mark.parametrize(
    "current, new, allowed, why",
    [
        ("In production", "Packed", True, "one step forward"),
        ("Packed", "Delivered", True, "several steps forward"),
        ("Shipped", "Packed", False, "backwards"),
        ("Delivered", "In production", False, "all the way back"),
        ("Shipped", "Shipped", True, "no change at all"),
        (None, "Delivered", True, "nothing to move back from"),
        ("Shipped", "Cancelled", True, "anything can be cancelled"),
        ("Cancelled", "Shipped", False, "un-cancelling is a correction"),
    ],
)
def test_moving_through_the_sequence(current, new, allowed, why):
    if allowed:
        statuses.check_move(current, new, allow_backwards=False)
    else:
        with pytest.raises(statuses.StatusProblem):
            statuses.check_move(current, new, allow_backwards=False)


def test_a_stated_correction_may_go_backwards():
    """Otherwise a fat-fingered Delivered could never be undone."""
    statuses.check_move("Delivered", "Packed", allow_backwards=True)
    statuses.check_move("Cancelled", "Shipped", allow_backwards=True)


def test_the_steps_are_numbered_in_order():
    numbers = [statuses.step(s) for s in statuses.SEQUENCE]
    assert numbers == list(range(1, len(statuses.SEQUENCE) + 1))
    assert statuses.step(statuses.CANCELLED) is None, "Cancelled is not a step"
    assert statuses.step(None) is None


# --------------------------------------------------------- an order's status


def lot(status, final=False):
    """A shipment, as far as its order's status is concerned."""
    return SimpleNamespace(status=status, is_final=final)


ORDER_CASES = [
    (False, [], "In production", "nothing against it yet"),
    (False, [lot(None)], "In production", "a shipment with no status has not started"),
    (False, [lot("Packed")], "In production", "a lot packed, and more of the order still to make"),
    (False, [lot("Packed", final=True)], "Packed", "the only lot, packed and not yet gone"),
    (False, [lot("Shipped")], "Part shipped", "one lot gone, none ticked as the last"),
    (False, [lot("Delivered"), lot("Delivered")], "Part shipped", "all arrived, but nobody said it was the last"),
    (False, [lot("Delivered"), lot("Packed", final=True)], "Part shipped", "the last lot is still at the factory"),
    (False, [lot("Delivered"), lot("In transit", final=True)], "In transit", "finished: the lot furthest behind"),
    (False, [lot("Delivered"), lot("Delivered", final=True)], "Delivered", "finished, and all of it arrived"),
    (False, [lot("Shipped", final=True), lot("Cancelled")], "Shipped", "a cancelled lot is left out"),
    (False, [lot("Cancelled")], "In production", "only a cancelled lot: as though there were none"),
    (False, [lot("Nearly there", final=True)], "In production", "a status the sequence does not know has not started"),
    (True, [lot("Delivered", final=True)], "Cancelled", "a cancelled order says so, whatever shipped"),
]


@pytest.mark.parametrize("cancelled, shipments, expected, why", ORDER_CASES)
def test_an_orders_status_is_worked_out_from_its_shipments(cancelled, shipments, expected, why):
    assert statuses.order_status(cancelled, shipments) == expected, why


def test_the_0009_downgrade_works_it_out_the_same_way():
    """Migration 0009 carries its own copy of the rule, as a migration must.

    The copy writes Shipped where the rule says Part shipped, because the
    older code does not know that word. Otherwise they must agree, or taking
    the database back would give orders a status they never showed.
    """
    path = Path(__file__).parents[1] / "migrations" / "versions" / "0009_order_status_from_shipments.py"
    spec = importlib.util.spec_from_file_location("migration_0009", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    for cancelled, shipments, expected, why in ORDER_CASES:
        older = migration._older_status(cancelled, [(s.status, s.is_final) for s in shipments])
        assert older == ("Shipped" if expected == statuses.PART_SHIPPED else expected), why


# ----------------------------------------------------------- rate limiting


def test_the_limit_is_the_number_of_failures_not_attempts():
    limiter = ratelimit.AttemptLimiter(
        max_attempts=3, window_seconds=60, lockout_seconds=60
    )
    for _ in range(3):
        limiter.check("k")          # allowed
        limiter.record_failure("k")
    with pytest.raises(ratelimit.TooManyAttempts):
        limiter.check("k")


def test_a_lockout_expires_on_its_own():
    limiter = ratelimit.AttemptLimiter(
        max_attempts=1, window_seconds=1, lockout_seconds=1
    )
    limiter.record_failure("k")
    with pytest.raises(ratelimit.TooManyAttempts):
        limiter.check("k")
    time.sleep(1.1)
    limiter.check("k")


def test_signing_in_clears_only_that_key():
    limiter = ratelimit.AttemptLimiter(2, 60, 60)
    limiter.record_failure("a")
    limiter.record_failure("b")
    limiter.clear("a")
    assert limiter.failures("a") == 0
    assert limiter.failures("b") == 1


def test_one_key_cannot_grow_without_bound():
    """A key at its limit is already locked; more timestamps only cost memory."""
    limiter = ratelimit.AttemptLimiter(5, 900, 900)
    for _ in range(10_000):
        limiter.record_failure("one.key")
    assert limiter.failures("one.key") == 5


def test_inventing_keys_cannot_exhaust_memory():
    """Otherwise the defence against guessing becomes a way to fell the API."""
    from app.core.config import RATE_LIMIT_MAX_KEYS

    limiter = ratelimit.AttemptLimiter(5, 900, 900)
    for i in range(RATE_LIMIT_MAX_KEYS * 3):
        limiter.record_failure(f"invented{i}")
    assert len(limiter._failures) <= RATE_LIMIT_MAX_KEYS


def test_recording_a_failure_stays_fast_when_the_table_is_full():
    """Pruning once ran on every failure, so the API slowed as an attack grew.

    The number here is deliberately loose. It is not measuring performance,
    it is catching the return of an O(keys)-per-attempt prune, which was
    thousands of times slower than this bound.
    """
    from app.core.config import RATE_LIMIT_MAX_KEYS

    limiter = ratelimit.AttemptLimiter(5, 900, 900)
    for i in range(RATE_LIMIT_MAX_KEYS):
        limiter.record_failure(f"fill{i}")

    started = time.perf_counter()
    for i in range(2_000):
        limiter.record_failure(f"more{i}")
    elapsed = time.perf_counter() - started
    assert elapsed < 5.0, f"2000 failures took {elapsed:.1f}s with a full table"


# ------------------------------------------------- which address is the client


def _request(header: str | None, peer: str = "10.9.9.9"):
    """A real Starlette Request, built from a scope, with no server needed."""
    from starlette.requests import Request

    headers = [(b"x-forwarded-for", header.encode())] if header else []
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": headers,
            "client": (peer, 12345),
        }
    )


@pytest.mark.parametrize(
    "header, hops, expected, why",
    [
        ("203.0.113.9", 1, "203.0.113.9", "Caddy alone: it appended the client"),
        ("203.0.113.9, 10.0.0.2", 2, "203.0.113.9", "nginx wrote it, Caddy appended nginx"),
        ("1.2.3.4, 203.0.113.9", 1, "203.0.113.9", "a forged leftmost is stepped over"),
        ("1.2.3.4, 203.0.113.9, 10.0.0.2", 2, "203.0.113.9", "forged leftmost, two real hops"),
        ("203.0.113.9", 2, "203.0.113.9", "fewer hops than configured: take the leftmost"),
        (None, 1, "10.9.9.9", "no header at all: fall back to the peer"),
    ],
)
def test_which_entry_of_forwarded_for_is_the_client(monkeypatch, header, hops, expected, why):
    """The rate limiter is only as good as this.

    Get it wrong and every visitor looks like one address: one shared proxy
    absorbs everybody's budget, and a single attacker locks out every
    customer at once.
    """
    from app.core import deps

    monkeypatch.setattr(deps, "TRUSTED_PROXY_HOPS", hops)
    assert deps.client_address(_request(header)) == expected, why


def test_the_header_is_ignored_when_it_is_not_to_be_trusted():
    """For a deployment where the API is reachable directly, a caller could
    otherwise put any address it liked in the header."""
    from app.core import deps

    original = deps.TRUST_PROXY_HEADER
    try:
        deps.TRUST_PROXY_HEADER = False
        assert deps.client_address(_request("203.0.113.9")) == "10.9.9.9"
    finally:
        deps.TRUST_PROXY_HEADER = original
