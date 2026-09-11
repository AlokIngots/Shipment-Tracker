"""Signing in, staying signed in, and being slowed down."""

import pytest

from app.services import accounts


def test_health_is_open_to_everyone(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_a_wrong_password_says_nothing_useful(client, db, customer):
    """The same answer whether the email exists or not."""
    accounts.create_login(db, customer, "real@testco.example", None)

    real = client.post(
        "/api/login", json={"email": "real@testco.example", "password": "wrong"}
    )
    unknown = client.post(
        "/api/login", json={"email": "ghost@nowhere.invalid", "password": "wrong"}
    )
    assert real.status_code == unknown.status_code == 401
    assert real.json()["detail"] == unknown.json()["detail"]


def test_a_temporary_password_buys_only_the_right_to_replace_it(
    client, db, customer
):
    _, temporary = accounts.create_login(db, customer, "new@testco.example", None)
    signed_in = client.post(
        "/api/login", json={"email": "new@testco.example", "password": temporary}
    ).json()
    assert signed_in["must_change_password"] is True

    headers = {"Authorization": f"Bearer {signed_in['token']}"}
    assert client.get("/api/orders", headers=headers).status_code == 403
    assert client.get("/api/staff/orders", headers=headers).status_code == 403
    # ...but /api/me and the password change must stay reachable, or the
    # portal could not explain why everything else is refused.
    assert client.get("/api/me", headers=headers).status_code == 200

    replaced = client.post(
        "/api/change-password",
        headers=headers,
        json={"current_password": temporary, "new_password": "chosen-by-them-now"},
    )
    assert replaced.status_code == 200
    new_headers = {"Authorization": f"Bearer {replaced.json()['token']}"}
    assert client.get("/api/orders", headers=new_headers).status_code == 200


def test_changing_a_password_signs_out_everywhere_else(client, db, customer):
    """The whole point of changing it after a scare."""
    _, temporary = accounts.create_login(db, customer, "two@testco.example", None)
    first = client.post(
        "/api/login", json={"email": "two@testco.example", "password": temporary}
    ).json()["token"]
    second = client.post(
        "/api/login", json={"email": "two@testco.example", "password": temporary}
    ).json()["token"]

    changed = client.post(
        "/api/change-password",
        headers={"Authorization": f"Bearer {second}"},
        json={"current_password": temporary, "new_password": "a-brand-new-password"},
    )
    assert changed.status_code == 200

    # The other session is finished...
    assert client.get("/api/me", headers={"Authorization": f"Bearer {first}"}).status_code == 401
    # ...and the one that made the change is not, or it would sign itself out.
    kept = {"Authorization": f"Bearer {changed.json()['token']}"}
    assert client.get("/api/me", headers=kept).status_code == 200


def test_a_deactivated_account_cannot_sign_in(client, db, customer):
    user, temporary = accounts.create_login(db, customer, "gone@testco.example", None)
    accounts.set_active(db, user, False)
    refused = client.post(
        "/api/login", json={"email": "gone@testco.example", "password": temporary}
    )
    assert refused.status_code == 401


def test_a_short_password_is_refused_by_the_server(client, db, customer):
    """Not only by the screen: the rule has to hold against the API too."""
    _, temporary = accounts.create_login(db, customer, "short@testco.example", None)
    token = client.post(
        "/api/login", json={"email": "short@testco.example", "password": temporary}
    ).json()["token"]
    refused = client.post(
        "/api/change-password",
        headers={"Authorization": f"Bearer {token}"},
        json={"current_password": temporary, "new_password": "short"},
    )
    assert refused.status_code == 400


def test_eight_characters_is_exactly_enough(client, db, customer):
    """Seven is refused and eight is accepted, so the line is where we say."""
    from app.core.security import PASSWORD_MIN_LENGTH

    assert PASSWORD_MIN_LENGTH == 8
    _, temporary = accounts.create_login(db, customer, "edge@testco.example", None)
    headers = {
        "Authorization": "Bearer "
        + client.post(
            "/api/login", json={"email": "edge@testco.example", "password": temporary}
        ).json()["token"]
    }

    seven = client.post(
        "/api/change-password",
        headers=headers,
        json={"current_password": temporary, "new_password": "abcdefg"},
    )
    assert seven.status_code == 400
    assert "at least 8 characters" in seven.json()["detail"]

    eight = client.post(
        "/api/change-password",
        headers=headers,
        json={"current_password": temporary, "new_password": "abcdefgh"},
    )
    assert eight.status_code == 200


# ------------------------------------------------------------ rate limiting


def address(ip: str) -> dict:
    """Pretend to arrive from an address, the way Caddy reports one."""
    return {"X-Forwarded-For": ip}


def wrong(client, email: str, ip: str):
    return client.post(
        "/api/login", json={"email": email, "password": "wrong"}, headers=address(ip)
    )


def test_five_failures_then_locked_out(client, db, customer):
    from app.core.config import LOGIN_MAX_ATTEMPTS

    accounts.create_login(db, customer, "target@testco.example", None)
    for _ in range(LOGIN_MAX_ATTEMPTS):
        assert wrong(client, "target@testco.example", "10.0.0.1").status_code == 401

    locked = wrong(client, "target@testco.example", "10.0.0.1")
    assert locked.status_code == 429
    assert locked.headers["Retry-After"].isdigit()
    # It must not become a way to ask whether an account exists.
    assert "incorrect" not in locked.json()["detail"].lower()


def test_the_lockout_refuses_even_the_right_password(client, db, customer):
    from app.core.config import LOGIN_MAX_ATTEMPTS

    _, temporary = accounts.create_login(db, customer, "locked@testco.example", None)
    for _ in range(LOGIN_MAX_ATTEMPTS):
        wrong(client, "locked@testco.example", "10.0.0.2")

    still_locked = client.post(
        "/api/login",
        json={"email": "locked@testco.example", "password": temporary},
        headers=address("10.0.0.2"),
    )
    assert still_locked.status_code == 429


def test_a_lockout_does_not_spread(client, db, customer):
    """One pairing locked must not lock the person, or the address, out."""
    from app.core.config import LOGIN_MAX_ATTEMPTS

    _, temporary = accounts.create_login(db, customer, "a@testco.example", None)
    _, other = accounts.create_login(db, customer, "b@testco.example", None)
    for _ in range(LOGIN_MAX_ATTEMPTS + 1):
        wrong(client, "a@testco.example", "10.0.0.3")

    # Same person, different address.
    assert client.post(
        "/api/login",
        json={"email": "a@testco.example", "password": temporary},
        headers=address("10.0.0.4"),
    ).status_code == 200
    # Different person, same address.
    assert client.post(
        "/api/login",
        json={"email": "b@testco.example", "password": other},
        headers=address("10.0.0.3"),
    ).status_code == 200


def test_an_unknown_email_is_limited_identically(client):
    """Or the limiter would answer 'is this a real account?' for free."""
    from app.core.config import LOGIN_MAX_ATTEMPTS

    for _ in range(LOGIN_MAX_ATTEMPTS):
        assert wrong(client, "ghost@nowhere.invalid", "10.0.0.5").status_code == 401
    assert wrong(client, "ghost@nowhere.invalid", "10.0.0.5").status_code == 429


def test_signing_in_clears_that_pairing_but_not_the_address(client, db, customer):
    from app.core.config import LOGIN_MAX_ATTEMPTS

    _, temporary = accounts.create_login(db, customer, "clears@testco.example", None)
    for _ in range(LOGIN_MAX_ATTEMPTS - 1):
        wrong(client, "clears@testco.example", "10.0.0.6")

    assert client.post(
        "/api/login",
        json={"email": "clears@testco.example", "password": temporary},
        headers=address("10.0.0.6"),
    ).status_code == 200

    # The count restarted: a full set of failures is allowed again.
    for _ in range(LOGIN_MAX_ATTEMPTS):
        assert wrong(client, "clears@testco.example", "10.0.0.6").status_code == 401
    assert wrong(client, "clears@testco.example", "10.0.0.6").status_code == 429


def test_one_address_spraying_many_accounts_is_stopped(client):
    from app.core.config import LOGIN_ADDRESS_MAX_ATTEMPTS

    for i in range(LOGIN_ADDRESS_MAX_ATTEMPTS):
        assert wrong(client, f"user{i}@nowhere.invalid", "10.0.0.7").status_code == 401
    # A brand new email, never tried before, and still refused.
    assert wrong(client, "fresh@nowhere.invalid", "10.0.0.7").status_code == 429


def test_a_forged_forwarded_header_does_not_dodge_the_limit(client, db, customer):
    """Caddy appends the real peer, so the RIGHTMOST entry is the true one."""
    from app.core.config import LOGIN_MAX_ATTEMPTS

    accounts.create_login(db, customer, "forge@testco.example", None)
    for _ in range(LOGIN_MAX_ATTEMPTS):
        wrong(client, "forge@testco.example", "10.0.0.8")

    forged = client.post(
        "/api/login",
        json={"email": "forge@testco.example", "password": "wrong"},
        headers={"X-Forwarded-For": "1.2.3.4, 10.0.0.8"},
    )
    assert forged.status_code == 429


def test_a_real_person_is_never_throttled(client, db, customer):
    """Thirty correct sign-ins in a row must all work."""
    _, temporary = accounts.create_login(db, customer, "busy@testco.example", None)
    for _ in range(30):
        assert client.post(
            "/api/login",
            json={"email": "busy@testco.example", "password": temporary},
            headers=address("10.0.0.9"),
        ).status_code == 200
