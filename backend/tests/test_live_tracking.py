"""Live container tracking from ShipsGo, and above all: credits spent once.

ShipsGo charges one credit to ADD a shipment and nothing to read it. These
tests stand a fake ShipsGo in for the real one and count every call, so the
promises can be checked rather than hoped for:

  * a shipment is added at most once, and only when staff press Enable and
    confirm it;
  * a B/L ShipsGo already has is reused, never added again;
  * no customer page, no save, and no timer run adds anything;
  * the timer only reads, and stops if a read is ever charged;
  * the customer sees the stored copy, with transshipment shown.

The first block needs no database and runs anywhere. The rest go through
the API and need PostgreSQL, like the rest of the suite.
"""

import io
import json
import re
from datetime import datetime, timedelta, timezone
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlparse

import pytest

from app.core import config
from app.services import live_tracking, shipsgo

KEY = "test-key-not-real"
BL = "EGLV100650230407"
CONTAINER = "EMCU6351083"

SHIPMENT = {
    "shipment_no": "TEST/SHP/001-1",
    "dispatched_qty": "40.000",
    "status": "Shipped",
    "vessel_name": "MV Test",
    "imo_number": "9074729",
    "container_no": CONTAINER,
    "bl_number": BL,
    "carrier": "Evergreen Line",
    "etd": "2026-09-01",
    "eta": "2026-09-28",
}


def _port(code, name, country):
    return {
        "code": code,
        "name": name,
        "timezone": "UTC",
        "country": {"code": code[:2], "name": country},
    }


NHAVA = _port("INNSA", "NHAVA SHEVA", "India")
COLOMBO = _port("LKCMB", "COLOMBO", "Sri Lanka")
ANTWERP = _port("BEANR", "ANTWERP", "Belgium")


def _move(event, status, location, vessel=None, voyage=None, when="2026-09-01T10:00:00+05:30"):
    return {
        "event": event,
        "status": status,
        "location": location,
        "vessel": {"name": vessel, "imo": 9000000} if vessel else None,
        "voyage": voyage,
        "timestamp": when,
    }


# A box from Nhava Sheva to Antwerp, transshipped at Colombo onto a
# different vessel -- the case the old vessel map got wrong.
SAILING_MOVES = [
    _move("GTIN", "ACT", NHAVA, when="2026-09-01T09:00:00+05:30"),
    _move("LOAD", "ACT", NHAVA, "WAN HAI 359", "E123", "2026-09-02T10:00:00+05:30"),
    _move("DEPA", "ACT", NHAVA, "WAN HAI 359", "E123", "2026-09-02T22:00:00+05:30"),
    _move("ARRV", "ACT", COLOMBO, "WAN HAI 359", "E123", "2026-09-06T08:00:00+05:30"),
    _move("DISC", "ACT", COLOMBO, "WAN HAI 359", "E123", "2026-09-06T12:00:00+05:30"),
    _move("LOAD", "ACT", COLOMBO, "EVER GIVEN", "0977W", "2026-09-09T06:00:00+05:30"),
    _move("DEPA", "EST", COLOMBO, "EVER GIVEN", "0977W", "2026-09-09T20:00:00+05:30"),
    _move("ARRV", "EST", ANTWERP, "EVER GIVEN", "0977W", "2026-10-01T07:00:00+02:00"),
    _move("DISC", "EST", ANTWERP, "EVER GIVEN", "0977W", "2026-10-01T15:00:00+02:00"),
]


def sailing_detail(shipment_id, booking_number):
    return {
        "id": shipment_id,
        "reference": None,
        "booking_number": booking_number,
        "container_number": CONTAINER,
        "container_count": 1,
        "carrier": {"scac": "EGLV", "name": "EVERGREEN"},
        "status": "SAILING",
        "route": {
            "port_of_loading": {"location": NHAVA, "date_of_loading": "2026-09-02T10:00:00+05:30"},
            "ts_count": 1,
            "port_of_discharge": {
                "location": ANTWERP,
                "date_of_discharge": "2026-10-01T15:00:00+02:00",
                "date_of_discharge_predicted": None,
            },
        },
        "containers": [
            {"number": CONTAINER, "status": "SAILING", "size": 20, "type": "DV", "movements": SAILING_MOVES}
        ],
        "checked_at": "2026-09-10 06:00:00",
        "discarded_at": None,
    }


# ------------------------------------------------------------ a fake ShipsGo


class _Response:
    def __init__(self, status, body, headers):
        self.status = status
        self.headers = headers
        self._raw = json.dumps(body).encode("utf-8")

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _headers(cost=None, remaining=None):
    headers = Message()
    if cost is not None:
        headers["X-Shipsgo-Credits-Cost"] = str(cost)
    if remaining is not None:
        headers["X-Shipsgo-Credits-Remaining"] = str(remaining)
    return headers


class FakeShipsGo:
    """Answers the way ShipsGo's v2 documentation says it does, and counts."""

    def __init__(self):
        self.calls = []
        self.shipments = {}
        self.next_id = 5001
        self.credits = 10
        self.read_cost = None
        self.detail = sailing_detail

    @property
    def posts(self):
        return [call for call in self.calls if call["method"] == "POST"]

    def writes(self):
        return [call for call in self.calls if call["method"] != "GET"]

    def _error(self, request, code, body, **headers):
        return HTTPError(
            request.full_url, code, "error", _headers(**headers), io.BytesIO(json.dumps(body).encode())
        )

    def __call__(self, request):
        url = urlparse(request.full_url)
        path = url.path.split("/v2", 1)[1]
        method = request.get_method()
        body = json.loads(request.data) if request.data else None
        # urllib stores header names capitalised this way.
        assert request.headers.get("X-shipsgo-user-token") == KEY
        self.calls.append({"method": method, "path": path, "query": parse_qs(url.query), "body": body})

        if method == "GET" and path == "/ocean/shipments":
            wanted = parse_qs(url.query)["filters[booking_number]"][0].split(":", 1)[1]
            rows = [
                {"id": i, "booking_number": d["booking_number"]}
                for i, d in self.shipments.items()
                if d["booking_number"] == wanted
            ]
            return _Response(200, {"message": "SUCCESS", "shipments": rows}, _headers(self.read_cost))

        if method == "GET" and path.startswith("/ocean/shipments/"):
            shipment_id = int(path.rsplit("/", 1)[1])
            if shipment_id not in self.shipments:
                raise self._error(request, 404, {"message": "NOT_FOUND"})
            return _Response(
                200, {"message": "SUCCESS", "shipment": self.shipments[shipment_id]}, _headers(self.read_cost)
            )

        if method == "POST" and path == "/ocean/shipments":
            for i, d in self.shipments.items():
                if d["booking_number"] == body.get("booking_number"):
                    raise self._error(
                        request, 409, {"message": "ALREADY_EXISTS", "shipment": {"id": i}}, cost=0
                    )
            if self.credits <= 0:
                raise self._error(request, 402, {"message": "NOT_ENOUGH_CREDITS"})
            self.credits -= 1
            shipment_id = self.next_id
            self.next_id += 1
            self.shipments[shipment_id] = self.detail(shipment_id, body["booking_number"])
            return _Response(
                200,
                {"message": "SUCCESS", "shipment": {"id": shipment_id, "booking_number": body["booking_number"]}},
                _headers(cost=1, remaining=self.credits),
            )

        raise AssertionError(f"the portal sent {method} {path}, which it never should")


@pytest.fixture
def fake(monkeypatch):
    shipsgo_fake = FakeShipsGo()
    monkeypatch.setattr(config, "SHIPSGO_API_KEY", KEY)
    monkeypatch.setattr(shipsgo, "_open", shipsgo_fake)
    return shipsgo_fake


# ======================================================= no database needed


def test_add_spends_one_credit_and_sends_no_reference(fake):
    added = shipsgo.add_shipment(BL, "EGLV")
    assert added.spent is True
    assert fake.credits == 9
    # Looked up first (free), then added once.
    assert [c["method"] for c in fake.calls] == ["GET", "POST"]
    # No reference: ShipsGo counts it in its duplicate check, and a different
    # one would make the same B/L a second, charged shipment.
    assert fake.posts[0]["body"] == {"booking_number": BL, "carrier": "EGLV"}


def test_a_bl_shipsgo_already_has_is_reused_without_asking_to_add_it(fake):
    first = shipsgo.add_shipment(BL)
    fake.calls.clear()
    again = shipsgo.add_shipment(BL)
    assert again.external_id == first.external_id
    assert again.spent is False
    assert fake.posts == []
    assert fake.credits == 9


def test_a_409_already_exists_is_used_and_costs_nothing(fake, monkeypatch):
    shipsgo.add_shipment(BL)
    # Pretend the free lookup missed it (say ShipsGo's list was slow to catch up).
    monkeypatch.setattr(shipsgo, "find_by_booking", lambda bl: None)
    again = shipsgo.add_shipment(BL)
    assert again.spent is False
    assert fake.credits == 9


def test_no_credits_left_is_said_plainly(fake):
    fake.credits = 0
    with pytest.raises(shipsgo.NoCredits):
        shipsgo.add_shipment(BL)
    assert fake.shipments == {}


def test_a_read_that_is_charged_trips_the_wire(fake):
    added = shipsgo.add_shipment(BL)
    fake.read_cost = 1
    with pytest.raises(shipsgo.CreditTripwire):
        shipsgo.get_shipment(added.external_id)


def test_a_bl_shipsgo_would_refuse_never_leaves_the_building(fake):
    with pytest.raises(shipsgo.ShipsGoError):
        shipsgo.add_shipment("EGLV 1006 50230407")
    with pytest.raises(shipsgo.ShipsGoError):
        shipsgo.add_shipment("")
    assert fake.calls == []


def test_nothing_but_reads_and_the_one_add_can_be_sent(fake):
    for method, path in [
        ("DELETE", "/ocean/shipments/1"),
        ("PATCH", "/ocean/shipments/1"),
        ("POST", "/ocean/shipments/1/followers"),
        ("POST", "/ocean/shipments"),  # without may_spend
    ]:
        with pytest.raises(shipsgo.ShipsGoError):
            shipsgo._call(method, path, body={})
    assert fake.calls == []


def test_without_a_key_nothing_is_sent():
    assert shipsgo.configured() is False
    with pytest.raises(shipsgo.NotConfigured):
        shipsgo.get_shipment(1)


def test_transshipment_is_marked_with_both_vessels():
    moves = live_tracking.simplify(sailing_detail(1, BL))[0]["movements"]
    steps = live_tracking.timeline(moves)

    colombo_off = steps[4]
    assert colombo_off["location"] == "COLOMBO"
    assert colombo_off["transshipment"] is True
    assert colombo_off["label"] == "Discharged for transshipment"

    colombo_on = steps[5]
    assert colombo_on["transshipment"] is True
    assert colombo_on["vessel"] == "EVER GIVEN"
    assert colombo_on["from_vessel"] == "WAN HAI 359"

    # The final discharge at Antwerp is not a transshipment.
    assert steps[-1]["transshipment"] is False
    # The latest thing that has actually happened is the Colombo loading.
    assert [s["latest"] for s in steps].index(True) == 5
    # Dates stay as the port wrote them.
    assert steps[-1]["date"] == "2026-10-01"
    assert steps[-1]["actual"] is False


def test_a_direct_voyage_shows_no_transshipment():
    moves = live_tracking.simplify(sailing_detail(1, BL))[0]["movements"]
    direct = [m for m in moves if m["location"] != "COLOMBO"]
    for m in direct:
        if m["vessel"]:
            m["vessel"] = "WAN HAI 359"
    assert not any(s["transshipment"] for s in live_tracking.timeline(direct))


def _row(**kw):
    base = dict(
        booking_number=BL,
        status="SAILING",
        refreshed_at=datetime.now(timezone.utc),
        containers=live_tracking.simplify(sailing_detail(1, BL)),
        carrier_name="EVERGREEN",
        port_of_loading="NHAVA SHEVA, India",
        port_of_discharge="ANTWERP, Belgium",
        loaded_at="2026-09-02T10:00:00+05:30",
        eta="2026-10-01T15:00:00+02:00",
        transshipments=1,
        container_count=1,
        external_id=1,
        last_error=None,
        failures=0,
        reused=False,
        enabled_at=None,
        enabled_by=None,
        discarded_at=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _shipment(row, bl=BL):
    return SimpleNamespace(tracking=row, bl_number=bl, container_no=CONTAINER)


def test_the_customer_panel_is_the_stored_copy():
    panel = live_tracking.view(_shipment(_row()), for_staff=False)
    assert panel["state"] == "ready"
    assert panel["eta"] == "2026-10-01"
    assert panel["port_of_discharge"] == "ANTWERP, Belgium"
    assert panel["transshipments"] == 1
    assert len(panel["movements"]) == len(SAILING_MOVES)
    # Housekeeping is for staff only.
    assert "external_id" not in panel and "last_error" not in panel


def test_before_shipsgo_has_news_the_panel_says_updating():
    panel = live_tracking.view(_shipment(_row(status="NEW", refreshed_at=None, containers=[])), for_staff=False)
    assert panel["state"] == "updating"
    assert panel["status_label"] == "Tracking is updating…"
    assert panel["movements"] == []


def test_a_changed_bl_or_an_untracked_one_is_hidden_from_customers_only():
    stale = _shipment(_row(), bl="SOMETHING-ELSE")
    assert live_tracking.view(stale, for_staff=False) is None
    assert live_tracking.view(stale, for_staff=True)["stale"] is True

    untracked = _shipment(_row(status="UNTRACKED"))
    assert live_tracking.view(untracked, for_staff=False) is None
    assert live_tracking.view(untracked, for_staff=True)["state"] == "unavailable"


def test_no_tracking_means_no_panel():
    assert live_tracking.view(SimpleNamespace(tracking=None), for_staff=True) is None


# ------------------------------------------------ the rules, read off the code

BACKEND = Path(__file__).resolve().parents[1]
FRONTEND = BACKEND.parent / "frontend" / "src"


def _python_files():
    return [p for p in (BACKEND / "app").rglob("*.py")] + [BACKEND / "main.py"]


def test_only_enable_can_add_a_shipment_to_shipsgo():
    """add_shipment is called from one place, and enable from one route."""
    callers = {
        p.relative_to(BACKEND).as_posix()
        for p in _python_files()
        if re.search(r"\badd_shipment\(", p.read_text(encoding="utf-8"))
    }
    assert callers == {"app/services/shipsgo.py", "app/services/live_tracking.py"}

    enablers = {
        p.relative_to(BACKEND).as_posix()
        for p in _python_files()
        if re.search(r"live_tracking\.enable\(", p.read_text(encoding="utf-8"))
    }
    assert enablers == {"app/routers/admin/live_tracking.py"}


def test_the_customer_half_never_talks_to_shipsgo():
    for name in ("auth.py", "orders.py", "documents.py", "photos.py"):
        text = (BACKEND / "app" / "routers" / name).read_text(encoding="utf-8")
        assert "shipsgo" not in text
        assert "refresh" not in text


def test_the_key_never_reaches_the_website():
    for path in FRONTEND.rglob("*"):
        if path.suffix in {".js", ".jsx", ".css", ".html"}:
            text = path.read_text(encoding="utf-8").lower()
            assert "shipsgo_api_key" not in text, path
            assert "x-shipsgo" not in text, path
            assert "api.shipsgo.com" not in text, path


# ================================================= through the API (database)


def put_shipment(client, staff_auth, order, **changes):
    shipment_id = order["shipments"][0]["id"]
    response = client.put(
        f"/api/staff/shipments/{shipment_id}", headers=staff_auth, json={**SHIPMENT, **changes}
    )
    assert response.status_code == 200, response.text
    return shipment_id


def enable(client, staff_auth, shipment_id, confirm=True):
    return client.post(
        f"/api/staff/shipments/{shipment_id}/tracking",
        headers=staff_auth,
        json={"confirm": confirm},
    )


def customer_shipment(client, customer_auth, order):
    response = client.get(f"/api/orders/{order['id']}", headers=customer_auth)
    assert response.status_code == 200, response.text
    return response.json()["shipments"][0]


def test_tracking_starts_off_and_saving_a_shipment_sends_nothing(
    client, staff_auth, customer_auth, order, fake
):
    put_shipment(client, staff_auth, order)
    put_shipment(client, staff_auth, order, vessel_name="MV Other")
    assert customer_shipment(client, customer_auth, order)["live_tracking"] is None
    assert fake.calls == []


def test_enable_needs_confirming(client, staff_auth, order, fake):
    shipment_id = put_shipment(client, staff_auth, order)
    response = enable(client, staff_auth, shipment_id, confirm=False)
    assert response.status_code == 400
    assert "credit" in response.json()["detail"]
    assert fake.calls == []


def test_enable_spends_one_credit_and_pressing_again_spends_none(
    client, staff_auth, order, fake
):
    shipment_id = put_shipment(client, staff_auth, order)

    first = enable(client, staff_auth, shipment_id)
    assert first.status_code == 200, first.text
    assert first.json()["credit_spent"] is True
    assert len(fake.posts) == 1
    assert fake.credits == 9

    fake.calls.clear()
    for _ in range(3):
        again = enable(client, staff_auth, shipment_id)
        assert again.status_code == 200
        assert again.json()["credit_spent"] is False
    # Not a lookup, not an add: the row was found and ShipsGo was left alone.
    assert fake.calls == []
    assert fake.credits == 9

    panel = first.json()["order"]["shipments"][0]["live_tracking"]
    assert panel["state"] == "ready"
    assert panel["booking_number"] == BL
    assert panel["reused"] is False


def test_the_customer_sees_the_stored_timeline_and_opening_it_costs_nothing(
    client, staff_auth, customer_auth, order, fake
):
    shipment_id = put_shipment(client, staff_auth, order)
    enable(client, staff_auth, shipment_id)
    fake.calls.clear()

    for _ in range(5):
        panel = customer_shipment(client, customer_auth, order)["live_tracking"]
    assert fake.calls == []

    assert panel["state"] == "ready"
    assert panel["status"] == "SAILING"
    assert panel["port_of_discharge"] == "ANTWERP, Belgium"
    assert panel["eta"] == "2026-10-01"
    moves = panel["movements"]
    assert any(m["transshipment"] and m["from_vessel"] == "WAN HAI 359" for m in moves)
    assert "external_id" not in panel


def test_stopping_and_enabling_again_reuses_the_shipsgo_shipment(
    client, staff_auth, order, fake
):
    shipment_id = put_shipment(client, staff_auth, order)
    enable(client, staff_auth, shipment_id)

    stopped = client.delete(f"/api/staff/shipments/{shipment_id}/tracking", headers=staff_auth)
    assert stopped.status_code == 200
    assert stopped.json()["order"]["shipments"][0]["live_tracking"] is None

    again = enable(client, staff_auth, shipment_id)
    assert again.status_code == 200
    assert again.json()["credit_spent"] is False
    assert len(fake.posts) == 1
    assert fake.credits == 9


def test_a_second_shipment_on_the_same_bl_asks_shipsgo_nothing(
    client, staff_auth, order, fake
):
    shipment_id = put_shipment(client, staff_auth, order)
    enable(client, staff_auth, shipment_id)
    created = client.post(
        f"/api/staff/orders/{order['id']}/shipments",
        headers=staff_auth,
        json={**SHIPMENT, "shipment_no": "TEST/SHP/001-2"},
    ).json()
    second_id = [s for s in created["shipments"] if s["shipment_no"] == "TEST/SHP/001-2"][0]["id"]

    fake.calls.clear()
    response = enable(client, staff_auth, second_id)
    assert response.status_code == 200
    assert response.json()["credit_spent"] is False
    assert fake.writes() == []
    assert fake.credits == 9


def test_a_changed_bl_hides_the_panel_and_will_not_quietly_add_the_new_one(
    client, staff_auth, customer_auth, order, fake
):
    shipment_id = put_shipment(client, staff_auth, order)
    enable(client, staff_auth, shipment_id)
    # Enabling read the box as sailing, which moved the shipment on to In
    # transit (step 53). Saving it as Shipped now would be a move backwards.
    put_shipment(
        client, staff_auth, order, bl_number="EGLV999999999999", status="In transit"
    )

    assert customer_shipment(client, customer_auth, order)["live_tracking"] is None
    response = enable(client, staff_auth, shipment_id)
    assert response.status_code == 400
    assert "old B/L" in response.json()["detail"]
    assert len(fake.posts) == 1


def test_enable_is_refused_without_a_key_or_a_bl(client, staff_auth, order, monkeypatch, fake):
    shipment_id = put_shipment(client, staff_auth, order, bl_number=None)
    response = enable(client, staff_auth, shipment_id)
    assert response.status_code == 400
    assert "Bill of Lading" in response.json()["detail"]

    put_shipment(client, staff_auth, order)
    monkeypatch.setattr(config, "SHIPSGO_API_KEY", "")
    response = enable(client, staff_auth, shipment_id)
    assert response.status_code == 400
    assert "not set up" in response.json()["detail"]
    assert fake.calls == []


def test_no_credits_left_leaves_tracking_off(client, staff_auth, order, fake):
    fake.credits = 0
    shipment_id = put_shipment(client, staff_auth, order)
    response = enable(client, staff_auth, shipment_id)
    assert response.status_code == 400
    assert "no credits" in response.json()["detail"]


def test_customers_cannot_touch_tracking(client, customer_auth, order, fake):
    shipment_id = order["shipments"][0]["id"]
    assert enable(client, customer_auth, shipment_id).status_code == 403
    assert client.post(
        f"/api/staff/shipments/{shipment_id}/tracking/refresh", headers=customer_auth
    ).status_code == 403
    assert client.delete(
        f"/api/staff/shipments/{shipment_id}/tracking", headers=customer_auth
    ).status_code == 403
    assert fake.calls == []


def test_the_timer_only_reads_and_skips_what_is_fresh_or_finished(
    client, db, staff_auth, order, fake, monkeypatch
):
    from app.models import ShipmentTracking
    from app.services import scheduler

    monkeypatch.setattr(config, "SHIPSGO_REFRESH_EVERY_HOURS", 6)
    shipment_id = put_shipment(client, staff_auth, order)
    enable(client, staff_auth, shipment_id)
    fake.calls.clear()

    # Just refreshed by Enable: nothing to do.
    assert scheduler.refresh_tracking_with(db, pause=lambda s: None)["refreshed"] == 0
    assert fake.calls == []

    row = db.query(ShipmentTracking).filter_by(shipment_id=shipment_id).one()
    row.refreshed_at = datetime.now(timezone.utc) - timedelta(hours=7)
    fake.shipments[row.external_id]["status"] = "ARRIVED"
    db.commit()

    counts = scheduler.refresh_tracking_with(db, pause=lambda s: None)
    assert counts["refreshed"] == 1
    assert [c["method"] for c in fake.calls] == ["GET"]
    db.refresh(row)
    assert row.status == "ARRIVED"

    # Finished journeys are left alone.
    row.refreshed_at = datetime.now(timezone.utc) - timedelta(hours=7)
    row.discarded_at = "2026-10-05 00:00:00"
    db.commit()
    fake.calls.clear()
    assert scheduler.refresh_tracking_with(db, pause=lambda s: None)["refreshed"] == 0
    assert fake.calls == []


def test_the_timer_stops_if_a_read_is_ever_charged(
    client, db, staff_auth, order, fake, monkeypatch
):
    from app.models import ShipmentTracking
    from app.services import scheduler

    monkeypatch.setattr(config, "SHIPSGO_REFRESH_EVERY_HOURS", 6)
    shipment_id = put_shipment(client, staff_auth, order)
    enable(client, staff_auth, shipment_id)
    row = db.query(ShipmentTracking).filter_by(shipment_id=shipment_id).one()
    row.refreshed_at = datetime.now(timezone.utc) - timedelta(hours=7)
    db.commit()

    fake.read_cost = 1
    with pytest.raises(shipsgo.CreditTripwire):
        scheduler.refresh_tracking_with(db, pause=lambda s: None)
    db.refresh(row)
    assert "charged" in row.last_error
    assert fake.posts[1:] == []


def test_a_failed_read_keeps_the_last_good_copy(
    client, db, staff_auth, customer_auth, order, fake, monkeypatch
):
    from app.models import ShipmentTracking
    from app.services import scheduler

    monkeypatch.setattr(config, "SHIPSGO_REFRESH_EVERY_HOURS", 6)
    shipment_id = put_shipment(client, staff_auth, order)
    enable(client, staff_auth, shipment_id)
    row = db.query(ShipmentTracking).filter_by(shipment_id=shipment_id).one()
    row.refreshed_at = datetime.now(timezone.utc) - timedelta(hours=7)
    db.commit()
    fake.shipments.clear()  # ShipsGo now answers 404

    counts = scheduler.refresh_tracking_with(db, pause=lambda s: None)
    assert counts["failed"] == 1
    db.refresh(row)
    assert row.failures == 1
    assert "404" in row.last_error

    # The customer still sees the last good news, not an error.
    panel = customer_shipment(client, customer_auth, order)["live_tracking"]
    assert panel["status"] == "SAILING"
    assert "last_error" not in panel

    # Staff see why, and pressing Refresh after a failure does try again.
    refreshed = client.post(
        f"/api/staff/shipments/{shipment_id}/tracking/refresh", headers=staff_auth
    )
    assert refreshed.status_code == 200
    assert "could not be read" in refreshed.json()["detail"]
    assert fake.posts[1:] == []


def test_turning_tracking_on_and_off_is_in_the_activity_record(
    client, staff_auth, order, fake
):
    shipment_id = put_shipment(client, staff_auth, order)
    enable(client, staff_auth, shipment_id)
    client.delete(f"/api/staff/shipments/{shipment_id}/tracking", headers=staff_auth)
    events = client.get("/api/staff/activity", headers=staff_auth).json()["events"]
    actions = [e["action"] for e in events]
    assert "shipment.tracking_enabled" in actions
    assert "shipment.tracking_stopped" in actions
    enabled = next(e for e in events if e["action"] == "shipment.tracking_enabled")
    assert "1 ShipsGo credit used" in enabled["summary"]


# ------------------------------------- step 53: the status moves by itself


def _row_for(db, shipment_id):
    from app.models import ShipmentTracking

    return db.query(ShipmentTracking).filter_by(shipment_id=shipment_id).one()


def _now_says(db, fake, shipment_id, stage):
    """ShipsGo now reports `stage`; read it back as the timer would."""
    row = _row_for(db, shipment_id)
    fake.shipments[row.external_id]["status"] = stage
    live_tracking.refresh(db, row)
    db.expire_all()


def _status(db, shipment_id):
    from app.models import Shipment

    return db.get(Shipment, shipment_id).status


def test_a_sailing_box_moves_a_shipped_shipment_to_in_transit(
    client, db, staff_auth, customer_auth, order, fake
):
    shipment_id = put_shipment(client, staff_auth, order)  # Shipped
    enable(client, staff_auth, shipment_id)  # reads SAILING
    assert _status(db, shipment_id) == "In transit"
    assert customer_shipment(client, customer_auth, order)["status"] == "In transit"

    events = client.get("/api/staff/activity", headers=staff_auth).json()["events"]
    moved = [e for e in events if e["source"] == "live tracking"]
    assert len(moved) == 1
    assert "In transit" in moved[0]["summary"]
    assert {"field": "Status", "before": "Shipped", "after": "In transit"} in moved[0]["changes"]


def test_discharged_at_the_port_means_delivered(
    client, db, staff_auth, customer_auth, order, fake
):
    shipment_id = put_shipment(client, staff_auth, order)
    enable(client, staff_auth, shipment_id)
    _now_says(db, fake, shipment_id, "ARRIVED")
    assert _status(db, shipment_id) == "In transit"
    _now_says(db, fake, shipment_id, "DISCHARGED")
    assert _status(db, shipment_id) == "Delivered"
    assert customer_shipment(client, customer_auth, order)["status"] == "Delivered"


def test_tracking_never_takes_a_status_backwards(client, db, staff_auth, order, fake):
    shipment_id = put_shipment(client, staff_auth, order, status="Delivered")
    enable(client, staff_auth, shipment_id)  # reads SAILING
    assert _status(db, shipment_id) == "Delivered"
    _now_says(db, fake, shipment_id, "LOADED")
    assert _status(db, shipment_id) == "Delivered"


def test_a_cancelled_shipment_is_left_alone(client, db, staff_auth, order, fake):
    shipment_id = put_shipment(client, staff_auth, order, status="Cancelled")
    enable(client, staff_auth, shipment_id)
    _now_says(db, fake, shipment_id, "DISCHARGED")
    assert _status(db, shipment_id) == "Cancelled"


def test_news_about_an_old_bl_moves_nothing(client, db, staff_auth, order, fake):
    shipment_id = put_shipment(client, staff_auth, order)  # Shipped
    enable(client, staff_auth, shipment_id)  # SAILING -> In transit
    put_shipment(client, staff_auth, order, bl_number="EGLV999999999999", status="In transit")
    _now_says(db, fake, shipment_id, "DISCHARGED")
    # The tracked box is no longer this shipment's, so its news is not either.
    assert _status(db, shipment_id) == "In transit"


def test_the_switch_turns_it_off(client, db, staff_auth, order, fake, monkeypatch):
    monkeypatch.setattr(config, "AUTO_STATUS_FROM_TRACKING", False)
    shipment_id = put_shipment(client, staff_auth, order)
    enable(client, staff_auth, shipment_id)
    _now_says(db, fake, shipment_id, "DISCHARGED")
    assert _status(db, shipment_id) == "Shipped"


def test_only_forward_stages_are_mapped():
    """No ShipsGo stage maps to anything before Shipped or to Cancelled."""
    from app.services import statuses

    for stage, status in live_tracking.STATUS_FROM_TRACKING.items():
        assert statuses.step(status) >= statuses.step("Shipped"), stage
    assert "BOOKED" not in live_tracking.STATUS_FROM_TRACKING
    assert "UNTRACKED" not in live_tracking.STATUS_FROM_TRACKING
