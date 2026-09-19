"""The thing that sends notifications without being asked.

Until this existed, a customer heard about their shipment when somebody at
Alok Ingots remembered to run `python -m scripts.notify` on the server. That
is not a notification system; it is a reminder to a person. This runs inside
the API container and does the same job on a timer.

What it is not
--------------

It is deliberately not a job queue and not a cron daemon. There is one job,
it takes seconds, and it is safe to run twice -- the unique constraint on
`notifications` means a customer is never told the same thing twice however
often this fires. Adding Celery or APScheduler for that would be a new
dependency, a new container and a new thing to go wrong.

Only one sender at a time
-------------------------

The API can be run with more than one worker, and a server can end up
briefly running two containers during a deploy. Both would wake up and start
sending the same backlog. The database settles it: whoever takes the
PostgreSQL advisory lock sends, and anyone else skips that turn and tries
again later. Nothing is lost by skipping -- what is waiting stays waiting.

Sending is still governed by SEND_EMAILS and NOTIFY_ONLY_EMAILS, so this
running does not mean anybody is being emailed.

Live tracking has a timer of its own here too
---------------------------------------------

A second, separate loop reads ShipsGo back for every shipment staff have
switched live tracking on for, every SHIPSGO_REFRESH_EVERY_HOURS. It only
reads, and reading is free: nothing in it can add a shipment to ShipsGo or
spend a credit. It takes its own advisory lock, so two containers do not
both read. If ShipsGo ever reports a cost for a read, the loop stops itself
and says so on the staff screen, rather than carry on.
"""

import asyncio
import logging
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import text

from app.core import config
from app.core.database import SessionLocal
from app.services import live_tracking, notifications, shipsgo

log = logging.getLogger("portal.notify")

# Any constant will do; it only has to be the same number in every process
# that must not send at the same time, and different from anybody else's.
# "alok portal notifier" as an arbitrary but fixed 63-bit value.
_LOCK_KEY = 8_143_220_907_551_133

# The live-tracking reader's lock. Different from the sender's, so the two
# never wait for each other.
_TRACKING_LOCK_KEY = 8_143_220_907_551_134

_task: asyncio.Task | None = None
_tracking_task: asyncio.Task | None = None

# What the Messages screen shows about the sender. In memory on purpose: it
# describes this process's own timer, and after a restart the honest answer
# is that this process has not run yet.
_state: dict = {
    "last_run_at": None,
    "last_counts": None,
    "last_error": None,
    "runs": 0,
}


_tracking_state: dict = {
    "last_run_at": None,
    "last_counts": None,
    "last_error": None,
    "stopped": False,
}


def tracking_status() -> dict:
    """What the live-tracking reader has been doing, for the staff screen."""
    return {
        **_tracking_state,
        "running": _tracking_task is not None and not _tracking_task.done(),
    }


def status() -> dict:
    """What the sender has been doing, for the Messages screen."""
    return {
        "every_minutes": config.NOTIFY_EVERY_MINUTES,
        "running": _task is not None and not _task.done(),
        "last_run_at": _state["last_run_at"],
        "last_counts": _state["last_counts"],
        "last_error": _state["last_error"],
        "runs": _state["runs"],
    }


@contextmanager
def _only_one(session, key: int):
    """Hold a Postgres advisory lock for one pass; yield whether we got it.

    The lock belongs to a database CONNECTION. It used to be taken through
    the session and released after a rollback or commit -- by which time
    the session could be on a different pooled connection, so the unlock
    missed, the lock stayed on an idle connection, and later turns (Send
    now included) quietly said "skipped" (health check, 19 Sep 2026). So it
    is taken on a connection of its own, which this holds for the whole
    pass and releases itself. The work still uses the session; only the
    lock lives here. The same database as the session, so tests use theirs.
    """
    connection = session.get_bind().engine.connect()
    try:
        got = bool(
            connection.execute(
                text("SELECT pg_try_advisory_lock(:key)"), {"key": key}
            ).scalar()
        )
        # A session-level lock survives the commit; the commit only stops
        # this connection sitting "idle in transaction" for the whole pass.
        connection.commit()
        try:
            yield got
        finally:
            if got:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:key)"), {"key": key}
                )
                connection.commit()
    finally:
        # Closing hands the connection back to the pool; with the lock
        # released above, nothing is left behind on it.
        connection.close()


def send_with(session) -> dict[str, int]:
    """One pass on a session somebody else opened. Blocking.

    Blocking because smtplib is. Callers on the event loop must keep it off
    there -- the timer uses asyncio.to_thread, and the Send now endpoint is
    a plain `def`, which FastAPI already runs in a worker thread.
    """
    # Try, do not wait. If another worker is already sending, this turn is
    # simply skipped: the backlog is still there next time.
    with _only_one(session, _LOCK_KEY) as got_lock:
        if not got_lock:
            log.info("another sender holds the lock; skipping this turn")
            return {"sent": 0, "suppressed": 0, "failed": 0, "skipped": 1}
        try:
            counts = notifications.run(session)
        finally:
            session.rollback()

    counts["skipped"] = 0
    return counts


def send_once() -> dict[str, int]:
    """One pass in a session of its own. What the timer calls."""
    with SessionLocal() as session:
        return send_with(session)


def _remember(counts: dict[str, int] | None, error: str | None) -> None:
    _state["last_run_at"] = datetime.now(timezone.utc)
    _state["last_counts"] = counts
    _state["last_error"] = error
    _state["runs"] += 1


async def _loop() -> None:
    """Send, wait, send again, for as long as the API is up."""
    await asyncio.sleep(config.NOTIFY_FIRST_RUN_DELAY_SECONDS)

    while True:
        try:
            counts = await asyncio.to_thread(send_once)
            _remember(counts, None)
            if counts["sent"] or counts["failed"]:
                log.info(
                    "notifications: sent %s, suppressed %s, failed %s",
                    counts["sent"],
                    counts["suppressed"],
                    counts["failed"],
                )
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            # A run that blows up -- the database away, say -- must not end
            # the timer. It is written down, and the next turn tries again.
            _remember(None, f"{type(exc).__name__}: {exc}")
            log.exception("notifications: this run failed")

        await asyncio.sleep(config.NOTIFY_EVERY_MINUTES * 60)


def refresh_tracking_with(session, *, pause=None) -> dict[str, int]:
    """One pass of the live-tracking reader on a session somebody else opened."""
    with _only_one(session, _TRACKING_LOCK_KEY) as got_lock:
        if not got_lock:
            return {"refreshed": 0, "failed": 0, "skipped": 1}
        try:
            kwargs = {"pause": pause} if pause is not None else {}
            counts = live_tracking.refresh_due(session, **kwargs)
        finally:
            session.rollback()
    counts["skipped"] = 0
    return counts


def refresh_tracking_once() -> dict[str, int]:
    with SessionLocal() as session:
        return refresh_tracking_with(session)


async def _tracking_loop() -> None:
    """Read ShipsGo back, wait some hours, read again. Never adds anything."""
    await asyncio.sleep(config.SHIPSGO_FIRST_REFRESH_DELAY_SECONDS)

    while True:
        try:
            counts = await asyncio.to_thread(refresh_tracking_once)
            _tracking_state.update(
                last_run_at=datetime.now(timezone.utc), last_counts=counts, last_error=None
            )
            if counts["refreshed"] or counts["failed"]:
                log.info(
                    "live tracking: refreshed %s, failed %s",
                    counts["refreshed"],
                    counts["failed"],
                )
        except asyncio.CancelledError:
            raise
        except shipsgo.CreditTripwire as exc:
            # Something that should have been free cost money. Stop, and
            # leave it stopped until a person has looked.
            _tracking_state.update(
                last_run_at=datetime.now(timezone.utc),
                last_error=exc.message,
                stopped=True,
            )
            log.error("live tracking: %s", exc.message)
            return
        except Exception as exc:  # noqa: BLE001
            _tracking_state.update(
                last_run_at=datetime.now(timezone.utc),
                last_error=f"{type(exc).__name__}: {exc}",
            )
            log.exception("live tracking: this run failed")

        await asyncio.sleep(config.SHIPSGO_REFRESH_EVERY_HOURS * 3600)


def _start_tracking() -> None:
    global _tracking_task

    if config.SHIPSGO_REFRESH_EVERY_HOURS <= 0 or not shipsgo.configured():
        log.info("live tracking refresh is off (no ShipsGo key, or interval 0)")
        return
    if _tracking_task is not None and not _tracking_task.done():
        return
    _tracking_task = asyncio.create_task(_tracking_loop(), name="portal-tracking")
    log.info(
        "live tracking refresh every %s hours", config.SHIPSGO_REFRESH_EVERY_HOURS
    )


def start() -> None:
    """Begin the timers, unless they are switched off or already going."""
    global _task

    _start_tracking()

    if config.NOTIFY_EVERY_MINUTES <= 0:
        log.info("automatic notifications are off (NOTIFY_EVERY_MINUTES=0)")
        return
    if _task is not None and not _task.done():
        return

    _task = asyncio.create_task(_loop(), name="portal-notifier")
    log.info(
        "automatic notifications every %s minutes, first run in %ss",
        config.NOTIFY_EVERY_MINUTES,
        config.NOTIFY_FIRST_RUN_DELAY_SECONDS,
    )


async def _cancel(task: asyncio.Task | None) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def stop() -> None:
    """Stop the timers and wait for them to actually be gone."""
    global _task, _tracking_task

    try:
        await _cancel(_task)
        await _cancel(_tracking_task)
    finally:
        _task = None
        _tracking_task = None
