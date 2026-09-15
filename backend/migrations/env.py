"""How Alembic connects to the database and finds the tables it manages.

Two things are deliberate here:

* The database address comes from ``database.py`` (which reads ``.env``),
  never from ``alembic.ini``. There is one source of truth, and no password
  is ever written into a file that gets committed.
* Every model is imported below so that ``--autogenerate`` can compare the
  code against the real database. A model that is not imported is invisible
  to Alembic, and its table would silently never be created.
"""

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.database import Base, DATABASE_URL

# Importing the models registers every table on Base.metadata.
from app import models  # noqa: F401

config = context.config

# Feed the address from .env to Alembic, escaping any '%' so that
# configparser does not treat it as a placeholder.
#
# Only if the caller has not already chosen one. It used to be unconditional,
# which meant every migration went to whatever DATABASE_URL said and there
# was no way to point Alembic at a different database -- not a staging copy,
# and not the throwaway database the test suite builds to prove the
# migrations actually apply. Setting it explicitly is now respected; leaving
# it unset still gets the one source of truth and no password in a committed
# file.
if not config.get_main_option("sqlalchemy.url", None):
    config.set_main_option("sqlalchemy.url", DATABASE_URL.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Print the SQL instead of running it (``alembic upgrade head --sql``)."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect to the database and apply the migrations."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # Notice a column whose type changed, not just added and
            # removed columns.
            compare_type=True,
            # Everything in one transaction: if a step fails half way, the
            # database is left exactly as it was.
            transaction_per_migration=False,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
