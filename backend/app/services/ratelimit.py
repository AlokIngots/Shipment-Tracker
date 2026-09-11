"""Slowing down somebody guessing passwords in bulk.

Nothing stopped it before. Passwords are long and PBKDF2 is slow, so it was
never fast going, but "slow going" is not a limit and a script does not get
bored. Step 17 made it matter more: a staff session can now create logins,
where before that needed a shell on the server.

What is counted, and why two counters
-------------------------------------

**(email, address) — 5 failures.** The ordinary attack: somebody working
through passwords for one account from one machine.

**address alone — 20 failures.** The other shape: one machine trying one
password against many accounts, which the first counter would never see
because each email is on its own budget.

There is deliberately **no counter on email alone**. It is the obvious third
one, and it is a trap: anybody who knows a customer's address could then
lock that customer out of the portal by failing five times on purpose. A
distributed attack on one account therefore still gets through, and that is
a considered trade, not an oversight — the alternative hands every passer-by
a way to shut a real customer out.

Sign-in links
-------------

Asking for a sign-in link sends an email, so there every request counts,
not only failures: at most MAGIC_LINK_MAX_PER_EMAIL links per inbox and
MAGIC_LINK_MAX_PER_ADDRESS requests per address, per window. The per-inbox
counter does not become the trap described above, because reaching it locks
nobody out of anything -- the password still works, and so do the links
already sent.

Where the counts live
---------------------

In memory, in this process. That is honest for what this is: one uvicorn
worker, in one container, in front of a handful of export customers. It
means the counts are lost when the API restarts — including on every
deploy — and that anyone who runs uvicorn with `--workers` will silently
divide the limit by the number of workers. Both are written down in
CLAUDE.md. Moving the counts to Redis is the answer if either stops being
acceptable.
"""

import threading
import time

from app.core.config import (
    LOGIN_ADDRESS_MAX_ATTEMPTS,
    LOGIN_LOCKOUT_SECONDS,
    LOGIN_MAX_ATTEMPTS,
    LOGIN_WINDOW_SECONDS,
    MAGIC_LINK_MAX_PER_ADDRESS,
    MAGIC_LINK_MAX_PER_EMAIL,
    MAGIC_LINK_WINDOW_SECONDS,
    RATE_LIMIT_MAX_KEYS,
)


class TooManyAttempts(Exception):
    """The caller must wait. `retry_after` is whole seconds, for the header."""

    def __init__(self, retry_after: int):
        super().__init__("Too many sign-in attempts.")
        self.retry_after = max(1, int(retry_after))


class AttemptLimiter:
    """Counts recent failures against a key, and locks it out past a limit."""

    def __init__(self, max_attempts: int, window_seconds: int, lockout_seconds: int):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        # key -> list of the times it failed, oldest first
        self._failures: dict[str, list[float]] = {}
        self._last_prune = time.monotonic()
        # Often enough that stale keys do not linger, rarely enough that the
        # walk is nowhere near the hot path.
        self._prune_every = max(30, window_seconds // 10)
        # Headroom, so a prune is followed by many cheap inserts.
        self._prune_down_to = max(1, (RATE_LIMIT_MAX_KEYS * 9) // 10)
        # A lock, because uvicorn runs sync endpoints in a thread pool and
        # two attempts really can land at the same moment.
        self._lock = threading.Lock()

    def _recent(self, key: str, now: float) -> list[float]:
        cutoff = now - self.window_seconds
        return [t for t in self._failures.get(key, []) if t > cutoff]

    def _prune(self, now: float) -> None:
        """Forget keys with nothing recent, and cap how many are held.

        Without this, somebody inventing a new email on every attempt would
        grow the dictionary until the container ran out of memory — turning
        a defence against one attack into an invitation to another.
        """
        cutoff = now - self.window_seconds
        self._failures = {
            key: times
            for key, times in self._failures.items()
            if times and times[-1] > cutoff
        }
        if len(self._failures) > RATE_LIMIT_MAX_KEYS:
            # Keep the most recently active. An attacker spraying fresh keys
            # evicts their own older ones rather than anybody else's.
            #
            # Trimmed to well UNDER the cap, not to it. Trimming exactly to
            # the cap leaves the next insertion over it again, so every
            # single attempt would trigger another full walk and the whole
            # point of pruning rarely would be lost.
            keep = sorted(
                self._failures.items(), key=lambda kv: kv[1][-1], reverse=True
            )[: self._prune_down_to]
            self._failures = dict(keep)
        self._last_prune = now

    def check(self, key: str) -> None:
        """Raise TooManyAttempts if this key is locked out right now."""
        now = time.monotonic()
        with self._lock:
            recent = self._recent(key, now)
            if len(recent) < self.max_attempts:
                return
            # Locked from the moment of the failure that hit the limit.
            unlock_at = recent[self.max_attempts - 1] + self.lockout_seconds
            if now < unlock_at:
                raise TooManyAttempts(unlock_at - now)

    def record_failure(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            recent = self._recent(key, now)

            # Once a key is at the limit it is already locked, and a longer
            # list would change nothing except how much memory one key can
            # occupy. Somebody hammering a single address would otherwise
            # append a timestamp per request for the whole window.
            if len(recent) < self.max_attempts:
                recent.append(now)
            self._failures[key] = recent

            # Pruning walks every key, so it must NOT run on every attempt.
            # It used to, and that made each failed login cost one operation
            # per key held — so the busier the attack, the slower the API
            # got, which is a denial of service built into the thing meant
            # to prevent one. Now it runs when the dictionary is actually
            # over its cap, or occasionally to clear out stale keys.
            if (
                len(self._failures) > RATE_LIMIT_MAX_KEYS
                or now - self._last_prune > self._prune_every
            ):
                self._prune(now)

    def record_attempt(self, key: str) -> None:
        """Count an attempt that is limited whether it worked or not.

        The same bookkeeping as a failure. Used where every request costs
        something -- a sign-in link is an email -- so a successful one must
        count too.
        """
        self.record_failure(key)

    def clear(self, key: str) -> None:
        """Forget a key's failures. Called when it finally signs in."""
        with self._lock:
            self._failures.pop(key, None)

    def failures(self, key: str) -> int:
        """How many recent failures are on this key. For tests and logging."""
        with self._lock:
            return len(self._recent(key, time.monotonic()))


# One machine working through passwords for one account.
by_email_and_address = AttemptLimiter(
    max_attempts=LOGIN_MAX_ATTEMPTS,
    window_seconds=LOGIN_WINDOW_SECONDS,
    lockout_seconds=LOGIN_LOCKOUT_SECONDS,
)

# One machine trying many accounts.
by_address = AttemptLimiter(
    max_attempts=LOGIN_ADDRESS_MAX_ATTEMPTS,
    window_seconds=LOGIN_WINDOW_SECONDS,
    lockout_seconds=LOGIN_LOCKOUT_SECONDS,
)


# Sign-in links asked for one inbox, from anywhere.
magic_link_by_email = AttemptLimiter(
    max_attempts=MAGIC_LINK_MAX_PER_EMAIL,
    window_seconds=MAGIC_LINK_WINDOW_SECONDS,
    lockout_seconds=MAGIC_LINK_WINDOW_SECONDS,
)

# Sign-in links asked for from one address, for any inboxes.
magic_link_by_address = AttemptLimiter(
    max_attempts=MAGIC_LINK_MAX_PER_ADDRESS,
    window_seconds=MAGIC_LINK_WINDOW_SECONDS,
    lockout_seconds=MAGIC_LINK_WINDOW_SECONDS,
)


def reset_all() -> None:
    """Forget everything. Only for tests."""
    for limiter in (
        by_email_and_address, by_address, magic_link_by_email, magic_link_by_address
    ):
        with limiter._lock:  # noqa: SLF001 - the module owns these objects
            limiter._failures.clear()
