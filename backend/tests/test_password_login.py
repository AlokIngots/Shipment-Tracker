"""Signing in with a password, beside the email link (18 Sep 2026).

Sign-in depended on email alone, and when the mail service refused its
credentials nobody could get in. Held to account here: password sign-in is
on by default; staff set a customer's password from the admin console and
the customer signs in with it, not made to change it; only the hash is
stored and the password is in no response and no activity record; the
server command does the same from a terminal; somebody who signs in by link
is never held back by a temporary password they never saw; and a session
lasts SESSION_TTL_DAYS, 30 by default.
"""

import time
from datetime import timedelta
from pathlib import Path

import pytest

import json
import re

from app.core import config, security
from app.models import AuditEvent, User
from app.services import accounts, notifications
from scripts import set_password as set_password_script

CHOSEN = "harbour-steel-2026"
LINK = re.compile(r"#sign-in=([A-Za-z0-9_\-]+)")


@pytest.fixture
def outbox(monkeypatch):
    """Every email the portal tries to send, caught instead of sent."""
    caught = []

    def catch(message, pilot_list=True):
        caught.append(message)
        return "sent", None

    monkeypatch.setattr(notifications, "send", catch)
    return caught


def sign_in_by_link(client, outbox, email, ip="10.9.1.1"):
    """Ask for a link, take it out of the caught email, and spend it."""
    headers = {"X-Forwarded-For": ip}
    assert client.post("/api/magic-link", json={"email": email}, headers=headers).status_code == 202
    token = LINK.search(outbox[-1].get_content()).group(1)
    redeemed = client.post("/api/magic-link/redeem", json={"token": token}, headers=headers)
    assert redeemed.status_code == 200
    body = redeemed.json()
    return body, {"Authorization": f"Bearer {body['token']}"}


def backdate(db, user):
    """A token issued in the same second as a password change is refused on
    purpose; move the change a few seconds back, as other tests do."""
    user.password_changed_at -= timedelta(seconds=5)
    db.commit()


def login(client, email, password, ip="10.9.0.1"):
    return client.post(
        "/api/login",
        json={"email": email, "password": password},
        headers={"X-Forwarded-For": ip},
    )


# ------------------------------------------------------------- the defaults


def test_password_sign_in_is_on_unless_the_server_says_otherwise():
    source = (Path(config.__file__)).read_text(encoding="utf-8")
    assert '_flag("PASSWORD_SIGN_IN", "true")' in source
    example = Path(__file__).resolve().parents[2] / ".env.example"
    assert "PASSWORD_SIGN_IN=true" in example.read_text(encoding="utf-8")


def test_a_session_lasts_thirty_days_by_default():
    example = Path(__file__).resolve().parents[2] / ".env.example"
    assert "SESSION_TTL_DAYS=30" in example.read_text(encoding="utf-8")
    assert config.TOKEN_TTL_SECONDS == config.SESSION_TTL_DAYS * 86400

    before = time.time()
    token = security.create_token(1)
    expires = json.loads(security._b64decode(token.split(".")[0]))["exp"]
    assert expires - before >= config.SESSION_TTL_DAYS * 86400 - 2


def test_the_sign_in_screen_offers_the_password_box(client):
    assert client.get("/api/sign-in-options").json()["password_sign_in"] is True


# ------------------------------------------------- staff set the password


def test_staff_set_a_password_and_the_customer_signs_in_with_it(
    client, db, customer, staff_auth
):
    user, _ = accounts.create_login(db, customer, "ops@testco.example", None)

    answer = client.post(
        f"/api/staff/logins/{user.id}/set-password",
        headers=staff_auth,
        json={"password": CHOSEN},
    )
    assert answer.status_code == 200
    # Never sent back, in any shape.
    assert CHOSEN not in answer.text

    db.refresh(user)
    assert user.password_hash.startswith("pbkdf2_sha256$")
    assert CHOSEN not in user.password_hash
    assert user.must_change_password is False
    backdate(db, user)

    signed = login(client, "ops@testco.example", CHOSEN)
    assert signed.status_code == 200
    body = signed.json()
    # Staff chose it on purpose: the customer goes straight to their orders.
    assert body["must_change_password"] is False
    auth = {"Authorization": f"Bearer {body['token']}"}
    assert client.get("/api/orders", headers=auth).status_code == 200


def test_the_activity_record_says_it_happened_and_never_what_it_was(
    client, db, customer, staff_auth
):
    user, _ = accounts.create_login(db, customer, "audit@testco.example", None)
    client.post(
        f"/api/staff/logins/{user.id}/set-password",
        headers=staff_auth,
        json={"password": CHOSEN},
    )
    events = db.query(AuditEvent).filter(AuditEvent.action == "login.password_set").all()
    assert len(events) == 1
    assert "audit@testco.example" in events[0].summary
    assert all(CHOSEN not in str(value) for value in vars(events[0]).values())


def test_setting_a_password_signs_them_out_everywhere(client, db, customer_auth, staff_auth):
    user = db.query(User).filter(User.email == "buyer@testco.example").one()
    assert client.get("/api/orders", headers=customer_auth).status_code == 200

    client.post(
        f"/api/staff/logins/{user.id}/set-password",
        headers=staff_auth,
        json={"password": CHOSEN},
    )
    assert client.get("/api/orders", headers=customer_auth).status_code == 401


def test_a_reset_in_the_same_second_as_a_password_change_still_signs_out(
    client, db, customer
):
    """Changing your own password hands back a token stamped one second
    after the change. A reset or Set password in that same second used to be
    stamped earlier than that token and leave it signed in -- CI run #108
    caught it by chance. Forced here, so it does not depend on timing."""
    from datetime import datetime, timezone

    user, _ = accounts.create_login(db, customer, "quick@testco.example", None)
    changed = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(seconds=30)
    user.password_changed_at = changed
    db.commit()
    # Exactly what change-password hands back: one second after the change.
    token = security.create_token(user.id, issued_at=int(changed.timestamp()) + 1)
    auth = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/me", headers=auth).status_code == 200

    accounts.set_password(db, user, CHOSEN)
    assert client.get("/api/me", headers=auth).status_code == 401

    accounts.reset_password(db, user)
    assert user.password_changed_at > changed + timedelta(seconds=1)


def test_a_weak_password_is_refused_in_plain_words(client, db, customer, staff_auth):
    user, _ = accounts.create_login(db, customer, "weak@testco.example", None)
    answer = client.post(
        f"/api/staff/logins/{user.id}/set-password",
        headers=staff_auth,
        json={"password": "short"},
    )
    assert answer.status_code == 400
    assert "at least 8 characters, including a letter and a number" in answer.json()["detail"]


def test_staff_cannot_set_their_own_password_from_the_console(client, db, staff_auth):
    me = db.query(User).filter(User.email == "staff@alokindia.test").one()
    answer = client.post(
        f"/api/staff/logins/{me.id}/set-password",
        headers=staff_auth,
        json={"password": CHOSEN},
    )
    assert answer.status_code == 400
    assert "scripts.set_password" in answer.json()["detail"]


def test_a_customer_cannot_set_anybodys_password(client, db, customer_auth, other_customer):
    victim, _ = accounts.create_login(db, other_customer, "victim@otherco.example", None)
    answer = client.post(
        f"/api/staff/logins/{victim.id}/set-password",
        headers=customer_auth,
        json={"password": CHOSEN},
    )
    assert answer.status_code == 403


def test_wrong_passwords_are_still_rate_limited(client, db, customer, staff_auth):
    user, _ = accounts.create_login(db, customer, "slow@testco.example", None)
    accounts.set_password(db, user, CHOSEN)
    backdate(db, user)
    statuses = [
        login(client, "slow@testco.example", "not-the-password", ip="10.9.9.9").status_code
        for _ in range(config.LOGIN_MAX_ATTEMPTS + 1)
    ]
    assert statuses[-1] == 429


# ------------------------------------ the link is still there, and unblocked


def test_link_sign_in_is_not_held_back_by_a_temporary_password(
    client, db, customer, outbox
):
    """Every login made before today still carries the temporary password
    the server made for it, which nobody was sent. Signing in by link must
    not ask them to replace it -- the change screen wants the old one."""
    accounts.create_login(db, customer, "link@testco.example", None)
    body, auth = sign_in_by_link(client, outbox, "link@testco.example")
    assert body["must_change_password"] is False
    assert client.get("/api/me", headers=auth).json()["must_change_password"] is False
    assert client.get("/api/orders", headers=auth).status_code == 200


def test_a_temporary_password_still_has_to_be_replaced_when_used(client, db, customer):
    _, temporary = accounts.create_login(db, customer, "temp@testco.example", None)
    body = login(client, "temp@testco.example", temporary).json()
    assert body["must_change_password"] is True
    auth = {"Authorization": f"Bearer {body['token']}"}
    assert client.get("/api/orders", headers=auth).status_code == 403


# ------------------------------------------------------- the server command


@pytest.fixture
def terminal(monkeypatch, db):
    """The script run as if typed into a terminal, on the test's database."""

    class Tty:
        def isatty(self):
            return True

    monkeypatch.setattr(set_password_script.sys, "stdin", Tty())

    class Borrowed:
        def __enter__(self):
            return db

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(set_password_script, "SessionLocal", Borrowed)

    def typed(*answers):
        queue = list(answers)
        monkeypatch.setattr(set_password_script.getpass, "getpass", lambda prompt="": queue.pop(0))

    return typed


def test_the_server_command_sets_a_staff_password(db, client, terminal, capsys):
    staff, _ = accounts.create_staff_login(db, "alok@alokindia.test", None)
    terminal(CHOSEN, CHOSEN)

    assert set_password_script.main(["--email", "alok@alokindia.test"]) == 0
    out = capsys.readouterr().out
    assert CHOSEN not in out
    assert "Done" in out

    db.refresh(staff)
    assert staff.must_change_password is False
    backdate(db, staff)
    body = login(client, "alok@alokindia.test", CHOSEN).json()
    assert body["is_staff"] is True and body["must_change_password"] is False
    auth = {"Authorization": f"Bearer {body['token']}"}
    assert client.get("/api/staff/accounts", headers=auth).status_code == 200


def test_the_server_command_refuses_a_mismatch_and_changes_nothing(db, terminal, capsys):
    staff, _ = accounts.create_staff_login(db, "typo@alokindia.test", None)
    before = staff.password_hash
    terminal(*[CHOSEN, "something-else-entirely"] * set_password_script.TRIES)

    assert set_password_script.main(["--email", "typo@alokindia.test"]) == 1
    assert "did not match" in capsys.readouterr().out
    db.refresh(staff)
    assert staff.password_hash == before


def test_the_server_command_says_so_when_nobody_has_that_email(db, terminal, capsys):
    assert set_password_script.main(["--email", "nobody@nowhere.test"]) == 1
    assert "manage_users --list" in capsys.readouterr().out


def test_the_server_command_prints_usage_without_an_email(capsys):
    with pytest.raises(SystemExit) as stopped:
        set_password_script.main([])
    assert stopped.value.code == 2
    err = capsys.readouterr().err
    assert "--email" in err
