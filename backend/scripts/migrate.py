"""Bring the database schema up to date, without ever wiping it.

    python migrate.py             bring the database up to date
    python migrate.py --status    show where the database is, change nothing
    python migrate.py --check     exit with an error if it is not up to date
    python migrate.py --sql       print the SQL that would run, change nothing
    python migrate.py --revision  print just the step the database is at

``--revision`` exists for ``safe-deploy.sh``: it notes the answer before
migrating, so that a deploy which fails afterwards can put the schema back
exactly where it was.

Until now the schema was built by ``seed.py``, which can only ever create
tables that are missing — it cannot add a column to a table that already
exists, so the only way to change anything was to drop the database. That is
fine while the data is invented; it is not fine once a real customer's orders
are in there.

Every change is now a numbered step in ``migrations/versions/``. Running this
applies whichever steps the database has not had yet, and nothing else.

Adopting the database that already exists
-----------------------------------------
The development database already has all six tables, built the old way, with
no record of any migration. Deleting and rebuilding it would work, but it is
exactly the habit this file exists to break — so instead, a database that
already has the portal's tables is *marked* as being at step 0001 rather than
having 0001 run against it. Nothing is created, nothing is dropped, and the
next real migration then applies to it normally.
"""

import sys
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from app.core.database import Base, engine

# Importing the models registers every table, so the drift check below can
# compare the code against the database.
from app import models  # noqa: F401

# alembic.ini and migrations/ stay at the backend root, beside the
# Dockerfile, because that is where alembic expects to be run from.
# This script lives one level down in scripts/.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
BASELINE = "0001"

# A table that only the portal creates. If this exists, the database is the
# portal's and predates migrations; if it does not, the database is empty.
MARKER_TABLE = "customers"


def config() -> Config:
    """Alembic's settings, with paths that work from any directory."""
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    return cfg


def current_revision() -> str | None:
    """Which migration the database says it is at, or None if it has none."""
    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def head_revision(cfg: Config) -> str | None:
    """The newest migration that exists in the code."""
    return ScriptDirectory.from_config(cfg).get_current_head()


def has_portal_tables() -> bool:
    return MARKER_TABLE in inspect(engine).get_table_names()


def model_drift() -> list:
    """Differences between the models in the code and the real database.

    A non-empty list means somebody changed a model and did not write a
    migration for it, so the code and the database disagree about what the
    tables look like.
    """
    with engine.connect() as connection:
        context = MigrationContext.configure(
            connection, opts={"compare_type": True}
        )
        return compare_metadata(context, Base.metadata)


def describe(item) -> str:
    """Turn one raw difference into a sentence a person can read.

    Alembic reports what the *database* would need in order to match the
    code, so "add" means the database is missing it and "remove" means the
    database has something the code no longer knows about.
    """
    # A table difference is a plain (action, Table) pair; a column difference
    # is (action, schema, table_name, Column); an altered column is a list.
    if isinstance(item, list):
        return "; ".join(describe(each) for each in item)

    action = item[0]

    if action == "add_table":
        return f"table '{item[1].name}' is in the code but missing from the database"
    if action == "remove_table":
        return f"table '{item[1].name}' is in the database but gone from the code"
    if action == "add_column":
        return (f"column '{item[3].name}' on table '{item[2]}' is in the code "
                f"but missing from the database")
    if action == "remove_column":
        return (f"column '{item[3].name}' on table '{item[2]}' is in the database "
                f"but gone from the code")
    if action.startswith("modify_"):
        what = action.replace("modify_", "")
        return (f"column '{item[3]}' on table '{item[2]}': {what} is "
                f"{item[5]!r} in the database but {item[6]!r} in the code")
    if action in ("add_index", "add_constraint"):
        return f"{action.split('_')[1]} on '{item[1].table.name}' is missing from the database"
    if action in ("remove_index", "remove_constraint"):
        return f"{action.split('_')[1]} on '{item[1].table.name}' is not in the code"

    return str(item)


def adopt_if_needed(cfg: Config) -> bool:
    """Mark a pre-migration database as being at the baseline. Returns True if
    that happened."""
    if current_revision() is not None:
        return False
    if not has_portal_tables():
        return False

    print("This database already has the portal's tables but no migration")
    print(f"history. Marking it as being at {BASELINE} — nothing is created")
    print("or dropped.")
    command.stamp(cfg, BASELINE)
    return True


def show_status(cfg: Config) -> int:
    """Print where things stand. Returns 0 if up to date, 1 if not."""
    head = head_revision(cfg)
    current = current_revision()

    print(f"Newest migration in the code: {head}")

    if current is None:
        if has_portal_tables():
            print("Database:                    has tables, no migration history")
            print("                             (run 'python migrate.py' to adopt it)")
        else:
            print("Database:                    empty — no tables yet")
        return 1

    print(f"Database is at:              {current}")

    if current != head:
        pending = [
            s.revision
            for s in ScriptDirectory.from_config(cfg).iterate_revisions(head, current)
            if s.revision != current
        ]
        print(f"Behind by {len(pending)} migration(s): {', '.join(reversed(pending))}")
        return 1

    print("Up to date.")

    drift = model_drift()
    if drift:
        print()
        print("WARNING: the code and the database do not match. Somebody changed")
        print("a model without writing a migration for it:")
        for item in drift:
            print(f"  - {describe(item)}")
        print()
        print("Write one with:")
        print('  python -m alembic revision --autogenerate -m "what changed"')
        return 1

    print("The models and the database agree.")
    return 0


def main() -> int:
    cfg = config()

    if "--revision" in sys.argv:
        # One line, nothing else, so a script can read it.
        print(current_revision() or "")
        return 0

    if "--status" in sys.argv:
        show_status(cfg)
        return 0

    if "--check" in sys.argv:
        return show_status(cfg)

    if "--sql" in sys.argv:
        # Print the SQL rather than running it. Only meaningful for a database
        # that has a history to work forward from.
        start = current_revision()
        print(f"-- SQL to move from {start or 'nothing'} to head, NOT executed:")
        command.upgrade(cfg, f"{start}:head" if start else "head", sql=True)
        return 0

    adopted = adopt_if_needed(cfg)
    if adopted:
        print()

    before = current_revision()
    command.upgrade(cfg, "head")
    after = current_revision()

    if before == after:
        print(f"Already up to date at {after}. Nothing to do.")
    else:
        print(f"Database moved from {before or 'nothing'} to {after}.")

    drift = model_drift()
    if drift:
        print()
        print("WARNING: the code and the database do not match.")
        print("Run 'python migrate.py --status' for the details.")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
