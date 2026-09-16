"""Demo and sample data must not reach a database that holds real work.

Two ways it could: `python -m scripts.seed` on the server, and
deploy/sample-data/sample-data.sql run with mode=load against the live
database. Four sample orders had to be removed from the live portal by hand
on 16 Sep 2026; these tests are the part of the fix that can be tested.
"""

from pathlib import Path

from scripts import seed


def test_a_real_customer_stops_the_demo_data(db, customer):
    """The fixture customer is TESTCO: not a demo code, not SAMPLE-."""
    assert seed.customers_that_are_not_demo(db) == ["TESTCO"]


def test_sample_and_demo_customers_do_not_count_as_real(db):
    """Sample data is removable by its own file, and demo data is this
    script's own. Neither should stop it running on a development database."""
    from app.services import accounts

    accounts.create_customer(db, "SAMPLE-001", "Sample Buyer GmbH", "Germany")
    for code in seed.demo_codes():
        accounts.create_customer(db, code, f"Demo {code}", None)

    assert seed.customers_that_are_not_demo(db) == []


def test_an_empty_database_is_fine(db):
    assert seed.customers_that_are_not_demo(db) == []


# ------------------------------------------------- the sample-data SQL itself
#
# It runs against the database container, not through the app, so there is
# nothing here to import and call. What can be held to account is that the
# guards are in the file and say what they are meant to say.


def _sample_sql() -> str:
    return (
        Path(__file__).resolve().parents[2] / "deploy" / "sample-data" / "sample-data.sql"
    ).read_text(encoding="utf-8")


def test_the_sample_loader_refuses_a_database_with_real_orders():
    sql = _sample_sql()
    assert "Refusing to load sample data" in sql
    assert "allow_beside_real_data" in sql


def test_removing_sample_data_is_by_customer_code_only():
    """The delete must be reachable only from SAMPLE- customers, so it can
    never take a real order with it."""
    sql = _sample_sql()
    assert "DELETE FROM customers WHERE code LIKE 'SAMPLE-%';" in sql
    # One delete, and nothing that deletes orders directly.
    assert sql.count("DELETE FROM") == 1


def test_the_removal_says_how_much_it_removed():
    sql = _sample_sql()
    assert "before_counts" in sql
    assert "found_before_this_run" in sql
