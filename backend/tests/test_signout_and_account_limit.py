"""Sign out ends the sign-in on the server; guessing is capped per account.

Two gaps found by the audit of 18 Sep 2026, once sign-ins lasted 30 days and
passwords were back:

  * Sign out only made the browser forget its token. A copy -- from a shared
    computer, from malware -- kept working until it expired. Now the token's
    id is recorded (migration 0014) and the token is refused everywhere,
    while the same person's other devices stay signed in.
  * Every guessing limit counted per network address, so many addresses
    meant many guesses at one account. Now an account takes at most
    LOGIN_ACCOUNT_MAX_ATTEMPTS wrong passwords per window, from anywhere.
"""

import base64
import json
import time
from datetime import datetime, timedelta, timezone

from app.core import config, security
from app.models import SignedOutToken
from app.services import accounts

PASSWORD = "harbour-steel-2026"


def sign_in(client, email, password=PASSWORD, ip="10.20.0.1"):
    return client.post(
        "/api/login",
        json={"email": email, "password": password},
        headers={"X-Forwarded-For": ip},
    )


def ready_login(db, customer, email):
    """A customer login with a password staff set, ready to sign in with."""
    user, _ = accounts.create_login(db, customer, email, None)
    accounts.set_password(db, user, PASSWORD)
    user.password_changed_at -= timedelta(seconds=5)
    db.commit()
    return user


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


# ------------------------------------------------------------------ sign out


def test_sign_out_ends_the_token_on_the_server(client, db, customer):
    ready_login(db, customer, "out@testco.example")
    token = sign_in(client, "out@testco.example").json()["token"]
    assert client.get("/api/orders", headers=bearer(token)).status_code == 200

    assert client.post("/api/logout", headers=bearer(token)).status_code == 200

    # The same token, as a copy somebody else kept, is now worth nothing.
    assert client.get("/api/orders", headers=bearer(token)).status_code == 401
    assert client.get("/api/me", headers=bearer(token)).status_code == 401


def test_only_that_device_is_signed_out(client, db, customer):
    ready_login(db, customer, "two@testco.example")
    laptop = sign_in(client, "two@testco.example").json()["token"]
    phone = sign_in(client, "two@testco.example").json()["token"]

    client.post("/api/logout", headers=bearer(laptop))

    assert client.get("/api/orders", headers=bearer(laptop)).status_code == 401
    assert client.get("/api/orders", headers=bearer(phone)).status_code == 200


def test_every_token_has_its_own_id():
    first = security.read_token(security.create_token(1))
    second = security.read_token(security.create_token(1))
    assert first["jti"] and second["jti"] and first["jti"] != second["jti"]


def test_what_is_kept_is_the_id_and_never_the_token(client, db, customer):
    user = ready_login(db, customer, "kept@testco.example")
    token = sign_in(client, "kept@testco.example").json()["token"]
    client.post("/api/logout", headers=bearer(token))

    rows = db.query(SignedOutToken).filter(SignedOutToken.user_id == user.id).all()
    assert len(rows) == 1
    assert rows[0].token_id == security.read_token(token)["jti"]
    assert token not in rows[0].token_id
    # Kept until the token would have expired by itself, and no longer.
    assert abs(
        rows[0].expires_at.timestamp() - security.read_token(token)["exp"]
    ) < 2


def test_signing_out_clears_rows_that_are_no_longer_needed(client, db, customer):
    user = ready_login(db, customer, "tidy@testco.example")
    past = datetime.now(timezone.utc) - timedelta(days=1)
    db.add(SignedOutToken(
        token_id="long-expired-token-id", user_id=user.id,
        signed_out_at=past - timedelta(days=30), expires_at=past,
    ))
    db.commit()

    token = sign_in(client, "tidy@testco.example").json()["token"]
    client.post("/api/logout", headers=bearer(token))

    assert db.get(SignedOutToken, "long-expired-token-id") is None


def test_a_token_from_before_this_change_still_works(client, db, customer):
    """Tokens issued before the deploy have no id to record. They keep
    working until they run out -- at most the 12 hours they were issued
    with -- and Sign out still clears them from the browser."""
    user = ready_login(db, customer, "old@testco.example")
    now = int(time.time())
    body = {"uid": user.id, "iat": now, "exp": now + 3600}
    payload = base64.urlsafe_b64encode(
        json.dumps(body, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    old = f"{payload}.{security._sign(payload)}"

    assert security.read_token(old)["jti"] is None
    assert client.get("/api/orders", headers=bearer(old)).status_code == 200
    assert client.post("/api/logout", headers=bearer(old)).status_code == 200


def test_signing_out_needs_a_sign_in(client):
    assert client.post("/api/logout").status_code == 401


# --------------------------------------------------- the per-account limit


def test_many_addresses_cannot_share_out_the_guessing(client, db, customer):
    """Each address makes one wrong guess -- no per-address limit is near
    -- and the account still closes after LOGIN_ACCOUNT_MAX_ATTEMPTS."""
    ready_login(db, customer, "target@testco.example")
    for i in range(config.LOGIN_ACCOUNT_MAX_ATTEMPTS):
        assert sign_in(
            client, "target@testco.example", "wrong-guess-1", ip=f"10.30.0.{i + 1}"
        ).status_code == 401

    refused = sign_in(client, "target@testco.example", "wrong-guess-1", ip="10.30.1.1")
    assert refused.status_code == 429
    # Even the right password, from an address that never failed.
    right = sign_in(client, "target@testco.example", ip="10.30.1.2")
    assert right.status_code == 429
    assert "email link" in right.json()["detail"]
    assert int(right.headers["Retry-After"]) > 0


def test_an_unknown_email_is_capped_the_same_way(client):
    """Or the per-account limit would say which emails have accounts."""
    for i in range(config.LOGIN_ACCOUNT_MAX_ATTEMPTS):
        assert sign_in(
            client, "nobody@nowhere.invalid", "wrong-guess-1", ip=f"10.31.0.{i + 1}"
        ).status_code == 401
    assert sign_in(
        client, "nobody@nowhere.invalid", "wrong-guess-1", ip="10.31.1.1"
    ).status_code == 429


def test_the_email_link_still_works_while_passwords_are_locked(client, db, customer, monkeypatch):
    """What a customer locked out by a stranger falls back on."""
    from app.services import notifications

    sent = []
    monkeypatch.setattr(notifications, "send", lambda message, pilot_list=True: (sent.append(message), ("sent", None))[1])
    ready_login(db, customer, "fallback@testco.example")
    for i in range(config.LOGIN_ACCOUNT_MAX_ATTEMPTS):
        sign_in(client, "fallback@testco.example", "wrong-guess-1", ip=f"10.32.0.{i + 1}")
    assert sign_in(client, "fallback@testco.example", ip="10.32.1.1").status_code == 429

    asked = client.post(
        "/api/magic-link",
        json={"email": "fallback@testco.example"},
        headers={"X-Forwarded-For": "10.32.1.1"},
    )
    assert asked.status_code == 202
    assert len(sent) == 1


def test_a_successful_sign_in_does_not_reset_the_account_count(client, db, customer):
    """Otherwise whoever is guessing gets a fresh allowance every time the
    real owner signs in."""
    ready_login(db, customer, "owner@testco.example")
    for i in range(config.LOGIN_ACCOUNT_MAX_ATTEMPTS - 1):
        sign_in(client, "owner@testco.example", "wrong-guess-1", ip=f"10.33.0.{i + 1}")
    assert sign_in(client, "owner@testco.example", ip="10.33.1.1").status_code == 200

    sign_in(client, "owner@testco.example", "wrong-guess-1", ip="10.33.1.2")
    assert sign_in(client, "owner@testco.example", ip="10.33.1.3").status_code == 429


def test_a_persons_own_typos_hit_the_address_limit_first():
    """Somebody mistyping at their own desk is stopped by the gentler
    per-address limit long before the account-wide one closes the door."""
    assert config.LOGIN_MAX_ATTEMPTS < config.LOGIN_ACCOUNT_MAX_ATTEMPTS
