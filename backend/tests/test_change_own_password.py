"""Changing your own password, from both halves.

The change-password screen existed from step 11 but, since step 31, nothing
led to it except a temporary password. Step 49 puts a Change password button
beside Sign out on the customer and staff screens. With it on every screen,
the endpoint behind it must not be a way round the per-account limit: a
wrong current password counts against LOGIN_ACCOUNT_MAX_ATTEMPTS exactly as
a wrong password at sign-in does.
"""

from app.core import config

CUSTOMER_PASSWORD = "a-password-they-chose-in-2026"  # conftest._settled_login
STAFF_PASSWORD = "staff-password-chosen-7"  # conftest.staff_auth


def change(client, headers, current, new="fresh-choice-2026"):
    return client.post(
        "/api/change-password",
        headers=headers,
        json={"current_password": current, "new_password": new},
    )


def test_a_customer_can_change_their_password_by_choice(client, customer_auth):
    changed = change(client, customer_auth, CUSTOMER_PASSWORD)
    assert changed.status_code == 200
    headers = {"Authorization": f"Bearer {changed.json()['token']}"}
    # Still signed in with the replacement, and the orders are still there.
    assert client.get("/api/orders", headers=headers).status_code == 200

    signed_in = client.post(
        "/api/login",
        json={"email": "buyer@testco.example", "password": "fresh-choice-2026"},
    )
    assert signed_in.status_code == 200


def test_staff_can_change_their_password_by_choice(client, staff_auth):
    changed = change(client, staff_auth, STAFF_PASSWORD)
    assert changed.status_code == 200
    headers = {"Authorization": f"Bearer {changed.json()['token']}"}
    assert client.get("/api/staff/orders", headers=headers).status_code == 200


def test_wrong_current_passwords_are_capped_per_account(client, customer_auth):
    for _ in range(config.LOGIN_ACCOUNT_MAX_ATTEMPTS):
        assert change(client, customer_auth, "wrong-guess-1").status_code == 401

    # Even the right one is refused now, and says how long to wait.
    refused = change(client, customer_auth, CUSTOMER_PASSWORD)
    assert refused.status_code == 429
    assert "wait" in refused.json()["detail"]
    assert int(refused.headers["Retry-After"]) > 0


def test_guesses_here_and_at_sign_in_share_one_count(client, customer_auth):
    """Or a token holder gets ten guesses here and ten more at sign-in."""
    for _ in range(config.LOGIN_ACCOUNT_MAX_ATTEMPTS):
        change(client, customer_auth, "wrong-guess-1")

    at_sign_in = client.post(
        "/api/login",
        json={"email": "buyer@testco.example", "password": CUSTOMER_PASSWORD},
        headers={"X-Forwarded-For": "10.49.0.1"},
    )
    assert at_sign_in.status_code == 429


def test_a_right_change_does_not_count_against_the_account(client, customer_auth):
    changed = change(client, customer_auth, CUSTOMER_PASSWORD)
    assert changed.status_code == 200
    from app.services import ratelimit

    assert ratelimit.by_account.failures("buyer@testco.example") == 0
