"""The rules, tested on their own: IMO, container, status, rate limiting.

No database and no HTTP. These are the functions that both the admin screen
and the CSV importer call, so a change that breaks one breaks both, and this
is where that shows up first and most cheaply.
"""

import time

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
