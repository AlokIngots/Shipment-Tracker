"""Customers and logins, and the line the admin console must not cross.

The most important test in this file is the one asserting that no route can
create a staff account. Staff is the flag that unlocks every write in the
portal; anyone able to grant it could grant it to themselves twice over and
nobody could take it back.
"""

import pytest

from app.services import accounts


def test_the_listing_shows_who_can_sign_in_for_whom(
    client, staff_auth, db, customer, order
):
    accounts.create_login(db, customer, "buyer@testco.example", "A Buyer")

    listed = client.get("/api/staff/accounts", headers=staff_auth).json()
    entry = next(c for c in listed["customers"] if c["code"] == "TESTCO")
    assert entry["order_count"] == 1
    assert "buyer@testco.example" in [u["email"] for u in entry["logins"]]
    assert any(u["email"] == "staff@alokindia.test" for u in listed["staff"])


def test_creating_a_customer(client, staff_auth):
    created = client.post(
        "/api/staff/customers",
        headers=staff_auth,
        json={"code": "HANSA", "name": "Hansa Stahl GmbH", "country": "Germany"},
    )
    assert created.status_code == 201
    hansa = next(c for c in created.json()["customers"] if c["code"] == "HANSA")
    assert hansa["logins"] == [], "a new customer has nobody who can sign in"


def test_a_duplicate_customer_code_is_refused(client, staff_auth, customer):
    refused = client.post(
        "/api/staff/customers",
        headers=staff_auth,
        json={"code": "TESTCO", "name": "Something Else"},
    )
    assert refused.status_code == 400


def test_a_customers_code_cannot_be_edited(client, staff_auth, customer):
    """It is what import_data.py matches on. Changing it orphans every import."""
    edited = client.put(
        f"/api/staff/customers/{customer.id}",
        headers=staff_auth,
        json={"name": "Renamed GmbH", "country": "Austria", "code": "SOMETHINGELSE"},
    )
    assert edited.status_code == 200
    changed = next(c for c in edited.json()["customers"] if c["id"] == customer.id)
    assert changed["name"] == "Renamed GmbH"
    assert changed["code"] == "TESTCO", "the code survived an attempt to change it"


def test_a_new_login_works_and_is_boxed_in(client, staff_auth, customer):
    created = client.post(
        f"/api/staff/customers/{customer.id}/logins",
        headers=staff_auth,
        json={"email": "fresh@testco.example", "full_name": "Fresh Person"},
    )
    assert created.status_code == 201
    temporary = created.json()["temporary_password"]
    assert temporary

    signed_in = client.post(
        "/api/login", json={"email": "fresh@testco.example", "password": temporary}
    ).json()
    assert signed_in["must_change_password"] is True
    assert signed_in["is_staff"] is False

    headers = {"Authorization": f"Bearer {signed_in['token']}"}
    assert client.get("/api/orders", headers=headers).status_code == 403
    assert client.get("/api/staff/accounts", headers=headers).status_code == 403


def test_the_temporary_password_appears_once_and_never_again(
    client, staff_auth, customer
):
    temporary = client.post(
        f"/api/staff/customers/{customer.id}/logins",
        headers=staff_auth,
        json={"email": "once@testco.example"},
    ).json()["temporary_password"]

    listed = client.get("/api/staff/accounts", headers=staff_auth)
    assert temporary not in listed.text, "the password must not be in the listing"


def test_a_duplicate_login_is_refused(client, staff_auth, customer, db):
    accounts.create_login(db, customer, "taken@testco.example", None)
    refused = client.post(
        f"/api/staff/customers/{customer.id}/logins",
        headers=staff_auth,
        json={"email": "taken@testco.example"},
    )
    assert refused.status_code == 400


def test_resetting_a_password_ends_every_session(client, staff_auth, customer, db):
    user, temporary = accounts.create_login(db, customer, "reset@testco.example", None)
    old_token = client.post(
        "/api/login", json={"email": "reset@testco.example", "password": temporary}
    ).json()["token"]

    reset = client.post(
        f"/api/staff/logins/{user.id}/reset-password", headers=staff_auth
    )
    assert reset.status_code == 200
    assert reset.json()["temporary_password"] != temporary

    assert client.get(
        "/api/me", headers={"Authorization": f"Bearer {old_token}"}
    ).status_code == 401
    assert client.post(
        "/api/login", json={"email": "reset@testco.example", "password": temporary}
    ).status_code == 401
    assert client.post(
        "/api/login",
        json={
            "email": "reset@testco.example",
            "password": reset.json()["temporary_password"],
        },
    ).status_code == 200


def test_deactivating_takes_effect_at_once(client, staff_auth, customer, db):
    user, temporary = accounts.create_login(db, customer, "out@testco.example", None)
    client.post(
        f"/api/staff/logins/{user.id}/active", headers=staff_auth, json={"active": False}
    )
    assert client.post(
        "/api/login", json={"email": "out@testco.example", "password": temporary}
    ).status_code == 401

    client.post(
        f"/api/staff/logins/{user.id}/active", headers=staff_auth, json={"active": True}
    )
    assert client.post(
        "/api/login", json={"email": "out@testco.example", "password": temporary}
    ).status_code == 200


# ------------------------------------------- the line that must not be crossed


def test_no_route_can_create_a_staff_account(client, staff_auth, customer):
    """The single most important assertion in the suite.

    Staff unlocks every write in the portal. If a route ever grants it,
    somebody who steals one staff session can mint more and never be
    removed. Granting it requires a shell on the server, on purpose.
    """
    for body in (
        {"email": "sneak1@x.test", "is_staff": True},
        {"email": "sneak2@x.test", "is_staff": 1, "full_name": "x"},
    ):
        created = client.post(
            f"/api/staff/customers/{customer.id}/logins", headers=staff_auth, json=body
        )
        if created.status_code == 201:
            signed_in = client.post(
                "/api/login",
                json={
                    "email": body["email"],
                    "password": created.json()["temporary_password"],
                },
            ).json()
            assert signed_in["is_staff"] is False, f"{body} produced a staff account"

    listed = client.get("/api/staff/accounts", headers=staff_auth).json()
    assert [u["email"] for u in listed["staff"]] == ["staff@alokindia.test"]


def test_no_route_at_all_mentions_creating_staff():
    """Belt and braces: check the routing table, not just the behaviour."""
    import main

    paths = main.app.openapi()["paths"]
    assert not [p for p in paths if "add-staff" in p or "staff-login" in p]


def test_you_cannot_deactivate_the_account_you_are_signed_in_with(client, staff_auth):
    listed = client.get("/api/staff/accounts", headers=staff_auth).json()
    me = next(u for u in listed["staff"] if u["email"] == "staff@alokindia.test")
    refused = client.post(
        f"/api/staff/logins/{me['id']}/active", headers=staff_auth, json={"active": False}
    )
    assert refused.status_code == 400
    assert "signed in with" in refused.json()["detail"]


def test_the_last_active_staff_account_cannot_be_deactivated(db, client, staff_auth):
    """Otherwise the admin console locks against everybody, undoable only
    by somebody with access to the server."""
    other, _ = accounts.create_staff_login(db, "second@alokindia.test", None)
    signed_in_as = accounts.find_user(db, "staff@alokindia.test")

    # Only `other` is left once the signed-in one is discounted; deactivate
    # it and there is exactly one active staff account remaining.
    accounts.set_active(db, other, False)
    assert accounts.active_staff_count(db) == 1

    with pytest.raises(accounts.AccountProblem, match="last active staff"):
        accounts.set_active(
            db,
            signed_in_as,
            False,
            acting_user=accounts.find_user(db, "second@alokindia.test"),
        )


@pytest.mark.parametrize(
    "method, path, kwargs",
    [
        ("get", "/api/staff/accounts", {}),
        ("post", "/api/staff/customers", {"json": {"code": "X", "name": "X"}}),
        ("post", "/api/staff/logins/1/reset-password", {}),
        ("post", "/api/staff/logins/1/active", {"json": {"active": False}}),
    ],
)
def test_a_customer_cannot_manage_accounts(client, customer_auth, method, path, kwargs):
    assert getattr(client, method)(
        path, headers=customer_auth, **kwargs
    ).status_code == 403
