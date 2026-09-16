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
"""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import text

from app.core import config
from app.core.database import SessionLocal
from app.services import notifications

log = logging.getLogger("portal.notify")

# Any constant will do; it only has to be the same number in every process
# that must not send at the same time, and different from anybody else's.
# "alok portal notifier" as an arbitrary but fixed 63-bit value.
_LOCK_KEY = 8_143_220_907_551_133

_task: asyncio.Task | None = None

# What the Messages screen shows about the sender. In memory on purpose: it
# describes this process's own timer, and after a restart the honest answer
# is that this process has not run yet.
_state: dict = {
    "last_run_at": None,
    "last_counts": None,
    "last_error": None,
    "runs": 0,
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


def send_with(session) -> dict[str, int]:
    """One pass on a session somebody else opened. Blocking.

    Blocking because smtplib is. Callers on the event loop must keep it off
    there -- the timer uses asyncio.to_thread, and the Send now endpoint is
    a plain `def`, which FastAPI already runs in a worker thread.
    """
    # Try, do not wait. If another worker is already sending, this turn is
    # simply skipped: the backlog is still there next time.
    got_lock = session.execute(
        text("SELECT pg_try_advisory_lock(:key)"), {"key": _LOCK_KEY}
    ).scalar()
    if not got_lock:
        log.info("another sender holds the lock; skipping this turn")
        return {"sent": 0, "suppressed": 0, "failed": 0, "skipped": 1}

    try:
        counts = notifications.run(session)
    finally:
        # The lock belongs to the connection, and the connection goes back
        # to the pool rather than closing, so it must be handed back by hand
        # or the next turn in this process locks itself out.
        session.rollback()
        session.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _LOCK_KEY})
        session.commit()

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


def start() -> None:
    """Begin the timer, unless it is switched off or already going."""
    global _task

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


async def stop() -> None:
    """Stop the timer and wait for it to actually be gone."""
    global _task

    if _task is None:
        return

    _task.cancel()
    try:
        await _task
    except asyncio.CancelledError:
        pass
    finally:
        _task = None
