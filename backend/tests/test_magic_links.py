"""Signing in with a link sent by email.

What is held to account here: the same answer whether an address has an
account or not; a token that is random, stored only as a hash, works once
and only for fifteen minutes; refusal after a newer link, a password reset
or a deactivation; both rate limits; and the password sign-in still there.
"""

import hashlib
import re
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select, update

from app.models import MagicLink
from app.services import accounts, notifications

LINK = re.compile(r"https://portal\.alokindia\.co\.in/#sign-in=([A-Za-z0-9_\-]+)")
EXPIRED = "This link has expired, please request a new one."


@pytest.fixture
def outbox(monkeypatch):
    """Every email the portal tries to send, caught instead of sent."""
    caught = []

    def catch(message):
        caught.append(message)
        return "sent", None

    monkeypatch.setattr(notifications, "send", catch)
    return caught


@pytest.fixture
def buyer(db, customer):
    """A customer login that has already chosen its own password."""
    user, _ = accounts.create_login(db, customer, "buyer@testco.example", "Petra Baumann")
    user.must_change_password = False
    db.commit()
    return user


def ask(client, email, ip="10.1.0.1"):
    return client.post(
        "/api/magic-link", json={"email": email}, headers={"X-Forwarded-For": ip}
    )


def redeem(client, token, ip="10.1.0.1"):
    return client.post(
        "/api/magic-link/redeem", json={"token": token}, headers={"X-Forwarded-For": ip}
    )


def token_from(message) -> str:
    match = LINK.search(message.get_content())
    assert match, "the link must point at https://portal.alokindia.co.in"
    return match.group(1)


def bearer(body) -> dict:
    return {"Authorization": f"Bearer {body['token']}"}


# ------------------------------------------------------------ it works


def test_a_link_signs_a_customer_in(client, outbox, buyer):
    asked = ask(client, "  Buyer@TestCo.example ")
    assert asked.status_code == 202
    assert asked.json()["detail"].startswith("Check your email.")

    assert len(outbox) == 1
    assert outbox[0]["To"] == "buyer@testco.example"

    signed_in = redeem(client, token_from(outbox[0]))
    assert signed_in.status_code == 200
    body = signed_in.json()
    assert (body["email"], body["is_staff"]) == ("buyer@testco.example", False)
    assert client.get("/api/orders", headers=bearer(body)).status_code == 200


def test_staff_can_sign_in_by_link_too(client, db, outbox, staff_auth):
    # The fixture changed this password a moment ago; a link sent in that
    # same second is refused on purpose (see the password-reset test), so
    # the change is moved a few seconds into the past.
    staff = accounts.find_user(db, "staff@alokindia.test")
    staff.password_changed_at -= timedelta(seconds=5)
    db.commit()

    ask(client, "staff@alokindia.test")
    body = redeem(client, token_from(outbox[0])).json()
    assert body["is_staff"] is True
    assert client.get("/api/staff/orders", headers=bearer(body)).status_code == 200


def test_the_password_sign_in_still_works(client, db, customer):
    _, temporary = accounts.create_login(db, customer, "both@testco.example", None)
    assert client.post(
        "/api/login", json={"email": "both@testco.example", "password": temporary}
    ).status_code == 200


def test_the_email_says_what_it_is(client, outbox, buyer):
    ask(client, buyer.email)
    message = outbox[0]
    text = message.get_content()
    assert message["Subject"] == "Your sign-in link for the Alok Ingots portal"
    assert "Petra Baumann" in text
    assert "15 minutes" in text
    assert "did not ask for this" in text


def test_the_link_is_unbroken_in_the_email_as_sent(client, outbox, buyer):
    """Not split by a quoted-printable soft line break, for whatever reads it."""
    ask(client, buyer.email)
    raw = outbox[0].as_string()
    assert f"#sign-in={token_from(outbox[0])}" in raw


def test_a_name_with_accents_still_gets_a_working_link(client, db, outbox, customer):
    accounts.create_login(db, customer, "mueller@testco.example", "Jürgen Müller")
    ask(client, "mueller@testco.example")
    assert "Jürgen Müller" in outbox[0].get_content()
    assert len(token_from(outbox[0])) == 43


def test_with_sending_switched_off_the_answer_is_unchanged(client, db, buyer):
    """No outbox here: the real sender, with SEND_EMAILS off, suppresses it."""
    assert ask(client, buyer.email).status_code == 202
    assert db.scalar(select(func.count(MagicLink.id))) == 1


# ------------------------------------------------------------ it tells nobody anything


def test_an_unknown_address_gets_exactly_the_same_answer(client, db, outbox, buyer):
    known = ask(client, buyer.email, ip="10.1.0.2")
    unknown = ask(client, "nobody@testco.example", ip="10.1.0.3")

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json(), "word for word"
    assert len(outbox) == 1, "only the real account was emailed"
    assert db.scalar(select(func.count(MagicLink.id))) == 1


def test_a_deactivated_account_is_answered_the_same_and_sent_nothing(
    client, db, outbox, buyer
):
    accounts.set_active(db, buyer, False)
    assert ask(client, buyer.email).status_code == 202
    assert outbox == []


# ------------------------------------------------------------ the token


def test_only_a_hash_of_the_token_is_stored(client, db, outbox, buyer):
    ask(client, buyer.email)
    token = token_from(outbox[0])
    row = db.scalar(select(MagicLink))
    assert row.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token not in row.token_hash
    assert len(token) == 43, "32 random bytes"


def test_a_link_expires_fifteen_minutes_after_it_is_sent(client, db, outbox, buyer):
    ask(client, buyer.email)
    row = db.scalar(select(MagicLink))
    assert row.expires_at - row.created_at == timedelta(minutes=15)


def test_a_link_works_once(client, outbox, buyer):
    ask(client, buyer.email)
    token = token_from(outbox[0])
    assert redeem(client, token).status_code == 200

    again = redeem(client, token)
    assert again.status_code == 400
    assert again.json()["detail"] == EXPIRED


def test_an_expired_link_is_refused(client, db, outbox, buyer):
    ask(client, buyer.email)
    token = token_from(outbox[0])
    db.execute(
        update(MagicLink).values(expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    )
    db.commit()

    refused = redeem(client, token)
    assert refused.status_code == 400
    assert refused.json()["detail"] == EXPIRED


def test_asking_again_retires_the_earlier_link(client, outbox, buyer):
    ask(client, buyer.email)
    ask(client, buyer.email)
    first, second = (token_from(m) for m in outbox)
    assert redeem(client, first).status_code == 400, "only the newest works"
    assert redeem(client, second).status_code == 200


def test_a_password_reset_retires_a_link_already_sent(client, db, outbox, buyer):
    """A reset usually means somebody should not be signed in."""
    ask(client, buyer.email)
    token = token_from(outbox[0])
    accounts.reset_password(db, buyer)
    assert redeem(client, token).status_code == 400


def test_deactivating_an_account_stops_its_link(client, db, outbox, buyer):
    ask(client, buyer.email)
    token = token_from(outbox[0])
    accounts.set_active(db, buyer, False)
    assert redeem(client, token).status_code == 400


def test_a_temporary_password_must_still_be_replaced(client, db, outbox, customer):
    """A link proves the inbox; the rule about temporary passwords stays."""
    accounts.create_login(db, customer, "new@testco.example", None)
    ask(client, "new@testco.example")
    body = redeem(client, token_from(outbox[0])).json()
    assert body["must_change_password"] is True
    assert client.get("/api/orders", headers=bearer(body)).status_code == 403


def test_nonsense_is_refused_the_same_way(client):
    for token in ("", "x", "not-a-real-token-at-all-really", "a" * 5000):
        refused = redeem(client, token, ip="10.1.0.9")
        assert refused.status_code == 400
        assert refused.json()["detail"] == EXPIRED


# ------------------------------------------------------------ rate limits


def test_one_inbox_gets_no_more_than_its_share_however_it_is_asked(
    client, outbox, buyer
):
    from app.core.config import MAGIC_LINK_MAX_PER_EMAIL

    answers = [
        ask(client, buyer.email, ip=f"10.2.0.{i}")
        for i in range(MAGIC_LINK_MAX_PER_EMAIL + 3)
    ]
    assert {a.status_code for a in answers} == {202}
    assert len({a.text for a in answers}) == 1, "the same answer every time"
    assert len(outbox) == MAGIC_LINK_MAX_PER_EMAIL


def test_one_address_asking_for_many_inboxes_is_stopped(client, outbox):
    from app.core.config import MAGIC_LINK_MAX_PER_ADDRESS

    for i in range(MAGIC_LINK_MAX_PER_ADDRESS):
        assert ask(client, f"person{i}@nowhere.invalid", ip="10.3.0.1").status_code == 202

    blocked = ask(client, "one.more@nowhere.invalid", ip="10.3.0.1")
    assert blocked.status_code == 429
    assert blocked.headers["Retry-After"].isdigit()
    assert ask(client, "one.more@nowhere.invalid", ip="10.3.0.2").status_code == 202, (
        "only that address is stopped"
    )


def test_guessing_tokens_is_slowed_to_a_stop(client, outbox, buyer):
    from app.core.config import LOGIN_ADDRESS_MAX_ATTEMPTS

    ask(client, buyer.email, ip="10.4.0.1")
    token = token_from(outbox[0])

    for _ in range(LOGIN_ADDRESS_MAX_ATTEMPTS):
        assert redeem(client, "a-guess", ip="10.4.0.2").status_code == 400
    assert redeem(client, token, ip="10.4.0.2").status_code == 429, (
        "even a real link, from the address that was guessing"
    )
    assert redeem(client, token, ip="10.4.0.3").status_code == 200, (
        "and being refused did not spend the real link"
    )
