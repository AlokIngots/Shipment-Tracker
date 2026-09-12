"""The portal as it ships: signed in by email link only.

PASSWORD_SIGN_IN is off unless the server's .env says otherwise. Held to
account here: an email and a password open nothing, and the refusal is the
same whether either was right; a brand-new login -- still carrying the
temporary password the server made for it -- signs in by link and sees its
orders without being asked for a password nobody sent it; a staff login does
the same, and every quick action still works; and the sign-in email offers
no password.

The password code is dormant, not gone. Every other test file runs with it
switched on (the password_sign_in fixture in conftest.py), which is the
proof it still works if it is ever switched back. The last two tests hold
the way back in to account: the sign-in screen is told when to show the
password box, and a staff member locked out by an email failure gets back
in with a password once the switch is on.
"""

import re
from datetime import timedelta
from pathlib import Path

import pytest

from app.core import config
from app.services import accounts, notifications

LINK = re.compile(r"#sign-in=([A-Za-z0-9_\-]+)")


@pytest.fixture
def link_only(monkeypatch):
    """The switch as the portal ships it, over conftest's password_sign_in."""
    monkeypatch.setattr(config, "PASSWORD_SIGN_IN", False)


@pytest.fixture
def outbox(monkeypatch):
    """Every email the portal tries to send, caught instead of sent."""
    caught = []

    def catch(message):
        caught.append(message)
        return "sent", None

    monkeypatch.setattr(notifications, "send", catch)
    return caught


def sign_in_by_link(client, outbox, email, ip="10.7.0.1"):
    """Ask for a link, take it out of the caught email, and spend it."""
    asked = client.post(
        "/api/magic-link", json={"email": email}, headers={"X-Forwarded-For": ip}
    )
    assert asked.status_code == 202
    token = LINK.search(outbox[-1].get_content()).group(1)
    redeemed = client.post(
        "/api/magic-link/redeem", json={"token": token}, headers={"X-Forwarded-For": ip}
    )
    assert redeemed.status_code == 200
    body = redeemed.json()
    return body, {"Authorization": f"Bearer {body['token']}"}


def test_password_sign_in_is_off_unless_the_server_says_otherwise(monkeypatch):
    monkeypatch.delenv("PASSWORD_SIGN_IN", raising=False)
    assert config._flag("PASSWORD_SIGN_IN") is False

    example = Path(__file__).resolve().parents[2] / ".env.example"
    assert "PASSWORD_SIGN_IN=false" in example.read_text(encoding="utf-8")


def test_a_right_password_opens_nothing_and_says_nothing(client, db, customer, link_only):
    _, temporary = accounts.create_login(db, customer, "pw@testco.example", None)

    def attempt(email, password):
        response = client.post("/api/login", json={"email": email, "password": password})
        return response.status_code, response.json()

    right = attempt("pw@testco.example", temporary)
    assert right[0] == 403
    assert "token" not in right[1]
    assert "email link" in right[1]["detail"]
    # The same answer for a wrong password and for an address with no account.
    assert attempt("pw@testco.example", "not-the-password") == right
    assert attempt("ghost@nowhere.invalid", "not-the-password") == right


def test_a_new_customer_login_signs_in_by_link_and_sees_its_orders(
    client, db, customer, outbox, link_only
):
    user, _ = accounts.create_login(db, customer, "new@testco.example", "Petra Baumann")
    # Made exactly as before: the server still marks it as on a temporary password.
    assert user.must_change_password is True

    body, auth = sign_in_by_link(client, outbox, "new@testco.example")

    assert body["must_change_password"] is False
    assert client.get("/api/me", headers=auth).json()["must_change_password"] is False
    assert client.get("/api/orders", headers=auth).status_code == 200


def test_staff_sign_in_by_link_and_every_quick_action_still_works(
    client, db, outbox, link_only
):
    """Add customer, Add customer login, New order, Upload document -- and the
    customer login that came out of them signs in by link and sees it all."""
    accounts.create_staff_login(db, "team@alokindia.test", "Team Member")
    staff_body, staff = sign_in_by_link(client, outbox, "team@alokindia.test")
    assert (staff_body["is_staff"], staff_body["must_change_password"]) == (True, False)

    added = client.post(
        "/api/staff/customers",
        headers=staff,
        json={"code": "LINKCO", "name": "Link Only GmbH", "country": "Germany"},
    )
    assert added.status_code == 201
    customer_id = next(c["id"] for c in added.json()["customers"] if c["code"] == "LINKCO")

    login = client.post(
        f"/api/staff/customers/{customer_id}/logins",
        headers=staff,
        json={"email": "buyer@linkco.example", "full_name": "Link Buyer"},
    )
    assert login.status_code == 201

    order = client.post(
        "/api/staff/orders",
        headers=staff,
        json={
            "customer_id": customer_id,
            "sales_order_no": "LINK/SO/001",
            "ordered_qty": "50.000",
            "unit": "MT",
            "grade": "304 / 1.4301",
        },
    )
    assert order.is_success
    shipment = client.post(
        f"/api/staff/orders/{order.json()['id']}/shipments",
        headers=staff,
        json={"shipment_no": "LINK/SHP/001-1", "dispatched_qty": "20.000", "status": "Shipped"},
    )
    assert shipment.is_success
    shipment_id = shipment.json()["shipments"][0]["id"]

    uploaded = client.post(
        f"/api/staff/shipments/{shipment_id}/documents",
        headers=staff,
        data={"doc_type": "Packing List"},
        files={"file": ("pl.pdf", b"%PDF-1.4 packing list\n", "application/pdf")},
    )
    assert uploaded.is_success

    _, buyer = sign_in_by_link(client, outbox, "buyer@linkco.example", ip="10.7.0.2")
    orders = client.get("/api/orders", headers=buyer).json()
    assert [o["sales_order_no"] for o in orders] == ["LINK/SO/001"]
    detail = client.get(f"/api/orders/{orders[0]['id']}", headers=buyer).json()
    documents = detail["shipments"][0]["documents"]
    assert any(d["doc_type"] == "Packing List" and d["available"] for d in documents)


def test_the_sign_in_email_offers_no_password(client, db, customer, outbox, link_only):
    accounts.create_login(db, customer, "mail@testco.example", None)
    sign_in_by_link(client, outbox, "mail@testco.example")
    assert "password" not in outbox[0].get_content().lower()


def test_switched_back_on_the_temporary_password_rule_returns(client, db, customer, outbox):
    """No link_only here: conftest has password sign-in on, as a server with
    PASSWORD_SIGN_IN=true would. The rule the switch put to sleep is awake."""
    accounts.create_login(db, customer, "back@testco.example", None)
    body, auth = sign_in_by_link(client, outbox, "back@testco.example")
    assert body["must_change_password"] is True
    assert client.get("/api/orders", headers=auth).status_code == 403


# ------------------------------------------------- the way back in


def test_the_sign_in_screen_is_told_whether_to_show_the_password_box(client, monkeypatch):
    """No sign-in needed to ask, and the answer follows the switch as it is now."""
    monkeypatch.setattr(config, "PASSWORD_SIGN_IN", False)
    off = client.get("/api/sign-in-options")
    assert off.status_code == 200
    assert off.json()["password_sign_in"] is False

    monkeypatch.setattr(config, "PASSWORD_SIGN_IN", True)
    assert client.get("/api/sign-in-options").json()["password_sign_in"] is True


def test_if_email_fails_staff_get_back_in_with_the_switch_on(client, db):
    """The recovery path, written down in CLAUDE.md: switch on, reset the
    password on the server, sign in with the temporary one, choose a real one.
    (conftest has the switch on here.)"""
    staff, _ = accounts.create_staff_login(db, "rescue@alokindia.test", None)
    temporary = accounts.reset_password(db, staff, actor=None)
    # A token issued in the same second as a reset is refused on purpose;
    # move the reset a few seconds into the past, as other tests do.
    staff.password_changed_at -= timedelta(seconds=5)
    db.commit()

    signed = client.post(
        "/api/login", json={"email": "rescue@alokindia.test", "password": temporary}
    )
    assert signed.status_code == 200
    body = signed.json()
    assert body["must_change_password"] is True
    auth = {"Authorization": f"Bearer {body['token']}"}
    # The temporary password buys only the right to choose a real one.
    assert client.get("/api/staff/orders", headers=auth).status_code == 403

    changed = client.post(
        "/api/change-password",
        headers=auth,
        json={"current_password": temporary, "new_password": "a-real-password-after-rescue"},
    )
    assert changed.status_code == 200
    settled = {"Authorization": f"Bearer {changed.json()['token']}"}
    assert client.get("/api/staff/orders", headers=settled).status_code == 200
