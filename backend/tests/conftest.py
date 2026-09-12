"""Shared setup for every test.

How the database is handled
---------------------------

Tests run against a **separate PostgreSQL database** on the same server the
development one uses — never against the development database itself, and
never against SQLite. SQLite would be faster and would also quietly disagree
with production about `Numeric`, about `ON DELETE CASCADE`, and about what a
unique constraint does, which is exactly the class of bug a test suite
exists to catch.

The test database is created once per run and built by running the real
Alembic migrations, so the migrations are tested too: a migration that does
not apply cleanly fails the whole suite before a single assertion runs.

Each test then gets a connection inside a transaction that is rolled back
afterwards. The endpoints call `db.commit()` themselves, so the session is
joined to that outer transaction with a savepoint — a commit inside an
endpoint releases the savepoint, and the rollback at the end still undoes
everything. Tests therefore cannot see each other's rows, and the database
is the same at the end of the run as at the start.
"""

import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# The tests live one level below the backend root, and import `app.*` and
# `main` the same way the running API does.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _test_database_url() -> tuple[str, str, str]:
    """(url of the server, url of the test database, its name).

    Derived from DATABASE_URL so there is one place to configure a database
    and no second password to keep in step.
    """
    from app.core.config import DATABASE_URL

    base, _, name = DATABASE_URL.rpartition("/")
    test_name = os.getenv("TEST_DATABASE_NAME", f"{name}_test")
    if test_name == name:
        raise RuntimeError(
            "The test database must not be the development one. "
            "Set TEST_DATABASE_NAME to something else."
        )
    # 'postgres' always exists, and is where CREATE DATABASE is issued from.
    return f"{base}/postgres", f"{base}/{test_name}", test_name


@pytest.fixture(scope="session")
def engine():
    """A built, migrated, empty test database that lasts the whole run."""
    server_url, test_url, test_name = _test_database_url()

    # CREATE DATABASE cannot run inside a transaction.
    admin = create_engine(server_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": test_name}
        ).scalar()
        if exists:
            connection.execute(text(f'DROP DATABASE "{test_name}" WITH (FORCE)'))
        connection.execute(text(f'CREATE DATABASE "{test_name}"'))
    admin.dispose()

    # Build the schema with the real migrations, so a migration that does not
    # apply is a test failure rather than a surprise on a server.
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", test_url.replace("%", "%%"))
    command.upgrade(cfg, "head")

    test_engine = create_engine(test_url, pool_pre_ping=True, future=True)
    yield test_engine
    test_engine.dispose()

    admin = create_engine(server_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{test_name}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture
def db(engine):
    """A session whose every change is undone when the test ends."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture(autouse=True)
def password_sign_in(monkeypatch):
    """Password sign-in switched ON for every test, unless a test turns it off.

    The portal ships with it off (PASSWORD_SIGN_IN) and signs people in by
    email link only. The password code is kept, dormant, so that it can be
    switched back on -- and the tests written before that decision are what
    prove it still works if it is. The fixtures below also sign in with a
    password, as the shortest way to a token. test_link_only.py switches it
    off and tests the portal as it ships.
    """
    from app.core import config

    monkeypatch.setattr(config, "PASSWORD_SIGN_IN", True)


@pytest.fixture(autouse=True)
def no_automatic_sender(monkeypatch):
    """The automatic notification sender is OFF for every test.

    The `client` fixture starts the app properly, lifespan and all, which is
    what makes it worth having. The timer started in that lifespan opens its
    own database session -- the real one, not the rolled-back test session --
    and would send real email on a machine with SEND_EMAILS on. Nothing in
    the test suite should be able to mail a customer, so the timer is
    switched off before the app is built. Tests that want a run call
    scheduler.send_with(db) directly, on the session that gets rolled back.

    Autouse, and therefore set up before `client`, which is what makes this
    reliable rather than a hope.
    """
    from app.core import config

    monkeypatch.setattr(config, "NOTIFY_EVERY_MINUTES", 0)


@pytest.fixture
def client(db):
    """The API, talking to the rolled-back session instead of the real one."""
    from fastapi.testclient import TestClient

    import main
    from app.core.deps import get_db
    from app.services import ratelimit

    # Every test starts with the rate limiter empty, or the order tests run
    # in would decide whether the auth tests pass.
    ratelimit.reset_all()

    main.app.dependency_overrides[get_db] = lambda: db
    with TestClient(main.app) as test_client:
        yield test_client
    main.app.dependency_overrides.clear()


# ------------------------------------------------------------------ people
#
# Made through the same service the admin console and manage_users.py use,
# so a test is never set up by a route the application does not have.


@pytest.fixture
def customer(db):
    from app.services import accounts

    return accounts.create_customer(db, "TESTCO", "Test Customer GmbH", "Germany")


@pytest.fixture
def other_customer(db):
    from app.services import accounts

    return accounts.create_customer(db, "OTHERCO", "Other Customer Srl", "Italy")


def _settled_login(db, client, customer, email):
    """A customer login that has already chosen its own password."""
    from app.services import accounts

    user, temporary = accounts.create_login(db, customer, email, "Test Person")
    password = "a-password-they-chose-themselves"
    token = client.post(
        "/api/login", json={"email": email, "password": temporary}
    ).json()["token"]
    replaced = client.post(
        "/api/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": temporary, "new_password": password},
    ).json()["token"]
    return user, password, {"Authorization": f"Bearer {replaced}"}


@pytest.fixture
def customer_auth(db, client, customer):
    _, _, headers = _settled_login(db, client, customer, "buyer@testco.example")
    return headers


@pytest.fixture
def other_auth(db, client, other_customer):
    _, _, headers = _settled_login(db, client, other_customer, "buyer@otherco.example")
    return headers


@pytest.fixture
def staff_auth(db, client):
    """A staff login that has chosen its own password.

    Created through accounts.create_staff_login, which is the only thing in
    the codebase that can make one -- there is deliberately no route.
    """
    from app.services import accounts

    email = "staff@alokindia.test"
    _, temporary = accounts.create_staff_login(db, email, "Test Staff")
    token = client.post(
        "/api/login", json={"email": email, "password": temporary}
    ).json()["token"]
    replaced = client.post(
        "/api/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "current_password": temporary,
            "new_password": "staff-password-chosen",
        },
    ).json()["token"]
    return {"Authorization": f"Bearer {replaced}"}


@pytest.fixture
def order(db, client, staff_auth, customer):
    """One order with one shipment, the shape most tests need."""
    created = client.post(
        "/api/staff/orders",
        headers=staff_auth,
        json={
            "customer_id": customer.id,
            "sales_order_no": "TEST/SO/EXP/001",
            "ordered_qty": "100.000",
            "unit": "MT",
            "grade": "431 / 1.4057",
        },
    ).json()
    with_shipment = client.post(
        f"/api/staff/orders/{created['id']}/shipments",
        headers=staff_auth,
        json={
            "shipment_no": "TEST/SHP/001-1",
            "dispatched_qty": "40.000",
            "status": "Shipped",
            "vessel_name": "MV Test",
            "imo_number": "9074729",
            "container_no": "CSQU3054383",
            "bl_number": "MAEU-TEST-1",
            "etd": "2026-09-01",
            "eta": "2026-09-28",
        },
    ).json()
    return with_shipment


def png(width: int = 6, height: int = 6) -> bytes:
    """A real, valid PNG, so a round trip can be compared byte for byte."""
    import struct
    import zlib

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + kind
            + data
            + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        )

    raw = b"".join(b"\x00" + bytes((40, 90, 160)) * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
