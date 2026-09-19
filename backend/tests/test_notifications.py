"""Notifications: what is owed, what is sent, and the sender that runs itself.

Step 33 moved sending off a person's memory and onto a timer inside the API.
These tests hold three promises:

  * nobody is ever told the same thing twice, however many times the sender
    runs, and however many senders run at once;
  * nothing that was owed is lost by a run being skipped, suppressed, or
    blowing up;
  * no customer can reach any of it.

Nothing here sends a real email. `notifications.send` is replaced with a
stand-in wherever a send has to appear to succeed, and the autouse fixture
in conftest.py keeps the automatic sender switched off for the whole suite.
"""

import pytest
from sqlalchemy import select, text

from app.core import config
from app.models import Notification
from app.services import notifications, scheduler


@pytest.fixture
def delivers(monkeypatch):
    """Make sending appear to work, and record what was handed over."""
    handed_over = []

    def fake_send(message, pilot_list=True):
        handed_over.append(message)
        return "sent", None

    monkeypatch.setattr(notifications, "send", fake_send)
    return handed_over


def notes(db):
    return list(db.scalars(select(Notification).order_by(Notification.id)))


# ------------------------------------------------------------- what is owed


def test_a_shipped_shipment_is_owed_a_message(db, order, customer_auth):
    owed = notifications.pending(db)
    assert len(owed) == 1
    shipment, sales_order, _, user = owed[0]
    assert shipment.status == "Shipped"
    assert sales_order.sales_order_no == "TEST/SO/EXP/001"
    assert user.email == "buyer@testco.example"


def test_a_customer_with_no_login_is_owed_nothing(db, order):
    # The order exists and has shipped; there is simply nobody to tell.
    assert notifications.pending(db) == []


# ---------------------------------------------------------- sending it once


def test_a_sent_message_is_never_sent_again(db, order, customer_auth, delivers):
    first = notifications.run(db)
    assert first == {"sent": 1, "suppressed": 0, "failed": 0}
    assert len(delivers) == 1

    second = notifications.run(db)
    assert second == {"sent": 0, "suppressed": 0, "failed": 0}
    assert len(delivers) == 1, "the same customer was told twice"
    assert len(notes(db)) == 1


def test_what_was_held_back_is_not_sent_later(db, order, customer_auth, monkeypatch, delivers):
    """Held back on purpose is settled, not owed (health check, 19 Sep 2026).

    It used to stay owed, so putting a customer on the pilot list -- or
    switching SEND_EMAILS on -- emailed them everything held back since
    their login was made, all at once.
    """
    monkeypatch.setattr(notifications, "send", lambda m, pilot_list=True: ("suppressed", "off"))
    assert notifications.run(db) == {"sent": 0, "suppressed": 1, "failed": 0}
    assert notes(db)[0].outcome == "suppressed"
    assert notifications.pending(db) == []

    # Sending now works (they were added to the list): the old news stays old.
    monkeypatch.setattr(notifications, "send", lambda m, pilot_list=True: ("sent", None))
    assert notifications.run(db) == {"sent": 0, "suppressed": 0, "failed": 0}


def test_a_retry_updates_the_one_record_rather_than_adding_another(
    db, order, customer_auth, monkeypatch, delivers
):
    # A failure -- the mail server refused -- is the one thing still owed.
    monkeypatch.setattr(notifications, "send", lambda m, pilot_list=True: ("failed", "refused"))
    notifications.run(db)
    first = notes(db)[0]
    first_attempt_at = first.last_attempt_at
    assert first.outcome == "failed"

    # Now sending works. The same message goes out for real.
    monkeypatch.setattr(notifications, "send", lambda m, pilot_list=True: ("sent", None))
    assert notifications.run(db) == {"sent": 1, "suppressed": 0, "failed": 0}

    records = notes(db)
    assert len(records) == 1, "a retry must not leave a second record"
    assert records[0].outcome == "sent"
    assert records[0].attempts == 2
    assert records[0].last_attempt_at >= first_attempt_at


def test_one_bad_address_does_not_stop_the_rest(
    db, client, staff_auth, customer, other_customer, monkeypatch
):
    """A failure is written down and the run carries on to everybody else."""
    from app.services import accounts

    accounts.create_login(db, customer, "one@testco.example", "A Person")
    accounts.create_login(db, other_customer, "two@otherco.example", "B Person")

    for who, sales_order_no in ((customer, "SO/A"), (other_customer, "SO/B")):
        made = client.post(
            "/api/staff/orders",
            headers=staff_auth,
            json={
                "customer_id": who.id,
                "sales_order_no": sales_order_no,
                "ordered_qty": "10.000",
                "unit": "MT",
            },
        ).json()
        client.post(
            f"/api/staff/orders/{made['id']}/shipments",
            headers=staff_auth,
            json={
                "shipment_no": f"{sales_order_no}-1",
                "dispatched_qty": "5.000",
                "status": "Shipped",
            },
        )

    def picky(message, pilot_list=True):
        if message["To"] == "one@testco.example":
            return "failed", "SMTPRecipientsRefused: no such mailbox"
        return "sent", None

    monkeypatch.setattr(notifications, "send", picky)

    assert notifications.run(db) == {"sent": 1, "suppressed": 0, "failed": 1}
    assert {n.outcome for n in notes(db)} == {"sent", "failed"}

    # The one that failed is still owed; the one that went is not.
    assert [u.email for _, _, _, u in notifications.pending(db)] == [
        "one@testco.example"
    ]


# ------------------------------------------------ only one sender at a time


def test_a_second_sender_skips_rather_than_sending_it_twice(
    db, engine, order, customer_auth, delivers
):
    """Another worker holding the lock must make this turn do nothing."""
    other = engine.connect()
    try:
        held = other.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": scheduler._LOCK_KEY}
        ).scalar()
        assert held is True

        counts = scheduler.send_with(db)
        assert counts["skipped"] == 1
        assert counts["sent"] == 0
        assert delivers == [], "it sent while another sender held the lock"
    finally:
        other.execute(
            text("SELECT pg_advisory_unlock(:key)"), {"key": scheduler._LOCK_KEY}
        )
        other.close()

    # Nothing was lost by skipping: it is still owed, and the next turn sends it.
    assert len(notifications.pending(db)) == 1
    assert scheduler.send_with(db)["sent"] == 1


def test_the_lock_is_handed_back_so_the_next_turn_works(
    db, order, customer_auth, delivers
):
    assert scheduler.send_with(db)["sent"] == 1
    # Would say skipped if the first pass had kept the lock to itself.
    assert scheduler.send_with(db)["skipped"] == 0


def test_the_lock_is_handed_back_even_when_the_run_blows_up(
    db, order, customer_auth, monkeypatch
):
    def explode(message, pilot_list=True):
        raise RuntimeError("the mail server fell over")

    monkeypatch.setattr(notifications, "send", explode)
    with pytest.raises(RuntimeError):
        scheduler.send_with(db)

    # The lock must not be stuck, or this process never sends again.
    monkeypatch.setattr(notifications, "send", lambda m, pilot_list=True: ("sent", None))
    assert scheduler.send_with(db)["sent"] == 1


def _lock_is_free(engine, key):
    """True when nobody holds the lock: a fresh connection can take it."""
    with engine.connect() as probe:
        got = probe.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}).scalar()
        if got:
            probe.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
        probe.commit()
    return bool(got)


def test_the_lock_lives_on_its_own_connection_and_is_freed(
    db, engine, order, customer_auth, monkeypatch
):
    """Health check, 19 Sep 2026: the lock was taken through the session and
    released after it had given its connection back, so the release could
    miss and leave later turns skipping. Now it is held on a connection of
    its own for the whole pass, and nobody holds it afterwards."""
    seen = {}

    def run_and_look(session, on_result=None):
        # Mid-pass: somebody else trying the lock is refused...
        seen["held_during"] = not _lock_is_free(engine, scheduler._LOCK_KEY)
        return {"sent": 0, "suppressed": 0, "failed": 0}

    monkeypatch.setattr(notifications, "run", run_and_look)
    assert scheduler.send_with(db)["skipped"] == 0
    assert seen["held_during"] is True
    # ...and afterwards it is free, however the session's connection moved.
    assert _lock_is_free(engine, scheduler._LOCK_KEY)


def test_the_tracking_lock_is_freed_too(db, engine, monkeypatch):
    from app.services import live_tracking

    monkeypatch.setattr(live_tracking, "refresh_due", lambda s, **kw: {"refreshed": 0, "failed": 0})
    assert scheduler.refresh_tracking_with(db)["skipped"] == 0
    assert _lock_is_free(engine, scheduler._TRACKING_LOCK_KEY)


# ------------------------------------------------------ the Messages screen


def test_the_messages_screen_shows_what_is_waiting(
    db, client, staff_auth, order, customer_auth
):
    body = client.get("/api/staff/messages", headers=staff_auth).json()

    assert body["messages"] == []
    assert len(body["waiting"]) == 1

    waiting = body["waiting"][0]
    assert waiting["to_email"] == "buyer@testco.example"
    assert waiting["sales_order_no"] == "TEST/SO/EXP/001"
    assert waiting["event"] == "Shipped"
    assert waiting["would_send"] is config.SEND_EMAILS

    sender = body["sender"]
    assert sender["every_minutes"] == 0, "the timer must be off during tests"
    assert sender["sending_enabled"] is config.SEND_EMAILS
    assert "Shipped" in sender["notify_on"]


def test_the_messages_screen_shows_what_was_sent(
    db, client, staff_auth, order, customer_auth, delivers
):
    notifications.run(db)

    body = client.get("/api/staff/messages", headers=staff_auth).json()
    assert body["waiting"] == []
    assert len(body["messages"]) == 1

    message = body["messages"][0]
    assert message["outcome"] == "sent"
    assert message["attempts"] == 1
    assert message["to_email"] == "buyer@testco.example"
    assert message["customer_name"] == "Test Customer GmbH"
    assert message["sales_order_no"] == "TEST/SO/EXP/001"
    assert message["shipment_no"] == "TEST/SHP/001-1"
    assert message["event"] == "Shipped"
    assert message["attempted_at"] is not None


def test_send_now_sends_what_is_waiting(
    db, client, staff_auth, order, customer_auth, delivers
):
    body = client.post("/api/staff/messages/send", headers=staff_auth).json()
    assert body == {"sent": 1, "suppressed": 0, "failed": 0, "skipped": 0}
    assert len(delivers) == 1

    # Pressed twice, nobody is told twice.
    again = client.post("/api/staff/messages/send", headers=staff_auth).json()
    assert again["sent"] == 0
    assert len(delivers) == 1


# ------------------------------------------------------ customers cannot see


def test_a_customer_cannot_read_the_messages(client, customer_auth, order):
    assert client.get("/api/staff/messages", headers=customer_auth).status_code == 403


def test_a_customer_cannot_press_send(client, customer_auth, order):
    assert (
        client.post("/api/staff/messages/send", headers=customer_auth).status_code
        == 403
    )


def test_a_stranger_cannot_read_the_messages(client):
    assert client.get("/api/staff/messages").status_code == 401
    assert client.post("/api/staff/messages/send").status_code == 401


# ---------------------------------------------------------------- the timer


def test_the_timer_stays_off_when_it_is_switched_off(monkeypatch):
    monkeypatch.setattr(config, "NOTIFY_EVERY_MINUTES", 0)
    scheduler.start()
    assert scheduler.status()["running"] is False
    assert scheduler.status()["every_minutes"] == 0


def test_a_sign_in_link_that_failed_shows_on_the_messages_screen(
    client, staff_auth, monkeypatch
):
    """The person who asked for it was told to check their email, because
    the answer cannot say otherwise without telling a stranger which
    addresses have accounts. Staff have to find out somewhere."""
    from app.services import magic_links

    magic_links.RECENT_FAILURES.clear()
    monkeypatch.setattr(notifications, "SEND_EMAILS", True)
    monkeypatch.setattr(notifications, "NOTIFY_ONLY_EMAILS", [])
    monkeypatch.setattr(notifications, "SMTP_HOST", "")

    magic_links.send("buyer@testco.example", None, "https://x/#sign-in=secret")

    screen = client.get("/api/staff/messages", headers=staff_auth).json()
    failures = screen["sign_in_link_failures"]
    assert [f["email"] for f in failures] == ["buyer@testco.example"]
    assert failures[0]["outcome"] == "failed"
    assert "secret" not in str(failures)
    magic_links.RECENT_FAILURES.clear()


# ------------------------------------------------- documents announce themselves
#
# Alok's rules, 16 Sep 2026: the fewest emails that still keep the customer
# informed. Several documents uploaded together make ONE email; a replaced
# document makes none; each type is announced once per shipment per person.


def upload(client, staff_auth, shipment_id, doc_type, name="doc.pdf"):
    return client.post(
        f"/api/staff/shipments/{shipment_id}/documents",
        headers=staff_auth,
        data={"doc_type": doc_type},
        files={"file": (name, b"%PDF-1.4", "application/pdf")},
    )


def events_for(db):
    return sorted(n.event for n in db.scalars(select(Notification)))


def flush(db):
    """Send whatever is already owed -- the fixture's shipment is Shipped, so
    a status email is waiting -- and leave the documents to the test."""
    notifications.run(db)


def test_a_document_is_announced_once(
    db, client, staff_auth, order, customer_auth, delivers
):
    shipment_id = order["shipments"][0]["id"]
    upload(client, staff_auth, shipment_id, "Bill of Lading")

    notifications.run(db)
    assert "Document: Bill of Lading" in events_for(db)
    sent_first = len(delivers)
    assert sent_first >= 1

    # A second run tells nobody anything again.
    notifications.run(db)
    assert len(delivers) == sent_first


def test_replacing_a_document_says_nothing(
    db, client, staff_auth, order, customer_auth, delivers
):
    shipment_id = order["shipments"][0]["id"]
    upload(client, staff_auth, shipment_id, "Commercial Invoice")
    notifications.run(db)
    after_first = len(delivers)

    upload(client, staff_auth, shipment_id, "Commercial Invoice", name="corrected.pdf")
    notifications.run(db)
    assert len(delivers) == after_first, "a correction must not be announced"


def test_documents_uploaded_together_make_one_email(
    db, client, staff_auth, order, customer_auth, delivers
):
    flush(db)
    shipment_id = order["shipments"][0]["id"]
    for kind in ["Packing List", "Commercial Invoice", "Bill of Lading"]:
        upload(client, staff_auth, shipment_id, kind)

    before = len(delivers)
    notifications.run(db)
    new_mail = delivers[before:]

    assert len(new_mail) == 1, "three documents, one email"
    body = new_mail[0].get_content()
    for kind in ["Packing List", "Commercial Invoice", "Bill of Lading"]:
        assert kind in body
    # Still recorded one by one, so each is announced only once ever.
    assert events_for(db).count("Document: Packing List") == 1


def test_documents_on_two_shipments_of_one_order_still_make_one_email(
    db, client, staff_auth, order, customer_auth, delivers
):
    flush(db)
    first = order["shipments"][0]["id"]
    second = client.post(
        f"/api/staff/orders/{order['id']}/shipments",
        headers=staff_auth,
        json={"shipment_no": "TEST/SHP/001-2", "dispatched_qty": "10.000"},
    ).json()["shipments"][-1]["id"]

    upload(client, staff_auth, first, "Packing List")
    upload(client, staff_auth, second, "Packing List")

    before = len(delivers)
    notifications.run(db)
    new_mail = delivers[before:]
    assert len(new_mail) == 1, "one order, one email, however many shipments"
    body = new_mail[0].get_content()
    assert "TEST/SHP/001-1" in body and "TEST/SHP/001-2" in body


def test_a_document_type_switched_off_says_nothing(
    db, client, staff_auth, order, customer_auth, delivers, monkeypatch
):
    flush(db)
    monkeypatch.setattr(notifications, "NOTIFIABLE_DOCUMENTS", ["Bill of Lading"])
    shipment_id = order["shipments"][0]["id"]
    upload(client, staff_auth, shipment_id, "Mill Test Certificate")

    before = len(delivers)
    notifications.run(db)
    assert len(delivers) == before
    assert "Document: Mill Test Certificate" not in events_for(db)


def test_a_document_row_with_no_file_is_not_announced(db, order, customer_auth):
    """A Document row can exist before its file does. Announcing that as
    ready would send a customer to an empty download."""
    from app.models import Document

    db.add(
        Document(
            shipment_id=order["shipments"][0]["id"],
            doc_type="Packing List",
            file_name="packing-list.pdf",
        )
    )
    db.commit()
    assert notifications.pending_documents(db) == []


def test_the_status_emails_are_untouched(
    db, client, staff_auth, order, customer_auth, delivers
):
    """Round 1 adds the document half and changes nothing about the other."""
    before = len(delivers)
    notifications.run(db)
    statuses = [m for m in delivers[before:] if "has shipped" in (m["Subject"] or "")]
    assert statuses, "the shipment in the fixture is Shipped and still says so"


def test_the_default_document_list_matches_the_staff_screen():
    """A fifth kind of document added to the staff screen must not quietly
    stay silent, so the two lists are held equal here."""
    from app.routers.admin.documents import EXPECTED_DOCUMENTS

    assert sorted(config.NOTIFIABLE_DOCUMENTS) == sorted(EXPECTED_DOCUMENTS)


# ------------------------------- no backlog for new logins (19 Sep 2026)
#
# A login made, or let back in, is told what happens from then on -- not
# the company's history, and not what happened while it was switched off.


def _owed_to(db, email):
    statuses = [u.email for _, _, _, u in notifications.pending(db)]
    documents = [u.email for *_, u in notifications.pending_documents(db)]
    return statuses.count(email) + documents.count(email)


def test_a_new_login_is_not_sent_the_history(db, client, staff_auth, order, customer):
    shipment_id = order["shipments"][0]["id"]  # already Shipped
    upload(client, staff_auth, shipment_id, "Bill of Lading")

    made = client.post(
        f"/api/staff/customers/{customer.id}/logins",
        headers=staff_auth,
        json={"email": "newbuyer@testco.example", "full_name": "New Buyer"},
    )
    assert made.status_code in (200, 201), made.text
    assert _owed_to(db, "newbuyer@testco.example") == 0

    # What happens next is news, and is owed.
    moved = client.put(
        f"/api/staff/shipments/{shipment_id}",
        headers=staff_auth,
        json={"shipment_no": order["shipments"][0]["shipment_no"],
              "dispatched_qty": order["shipments"][0]["dispatched_qty"],
              "status": "In transit"},
    )
    assert moved.status_code == 200, moved.text
    upload(client, staff_auth, shipment_id, "Packing List")
    assert _owed_to(db, "newbuyer@testco.example") == 2


def test_a_login_let_back_in_is_not_sent_what_it_missed(
    db, client, staff_auth, order, customer, customer_auth
):
    from app.models import User

    buyer = db.scalar(select(User).where(User.email == "buyer@testco.example"))
    assert client.post(
        f"/api/staff/logins/{buyer.id}/active", headers=staff_auth, json={"active": False}
    ).status_code == 200

    shipment_id = order["shipments"][0]["id"]
    upload(client, staff_auth, shipment_id, "Commercial Invoice")

    assert client.post(
        f"/api/staff/logins/{buyer.id}/active", headers=staff_auth, json={"active": True}
    ).status_code == 200
    assert _owed_to(db, "buyer@testco.example") == 0


def test_already_known_is_not_listed_on_the_messages_screen(
    db, client, staff_auth, order, customer
):
    client.post(
        f"/api/staff/customers/{customer.id}/logins",
        headers=staff_auth,
        json={"email": "quiet@testco.example", "full_name": None},
    )
    assert any(n.outcome == "known" for n in notes(db))
    body = client.get("/api/staff/messages", headers=staff_auth).json()
    assert body["messages"] == []
    assert body["waiting"] == []


def test_a_failure_is_still_tried_again(db, order, customer_auth, monkeypatch):
    monkeypatch.setattr(notifications, "send", lambda m, pilot_list=True: ("failed", "no route"))
    notifications.run(db)
    assert len(notifications.pending(db)) == 1
