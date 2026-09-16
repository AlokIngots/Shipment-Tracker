"""Photo previews: small, upright, stripped of hidden details, and private.

The gallery used to download every photo at full size to draw a tile about a
hundred pixels wide. Now each photo gets a small copy at upload. These tests
hold that copy to what it promises -- and hold the upload to refusing a file
that only pretends to be a picture, which the preview work made possible.
"""

from io import BytesIO

from PIL import Image

from app.models import Photo
from app.services import photos, storage
from tests.conftest import png


def jpeg(width=1600, height=1200, *, orientation=None, camera=None) -> bytes:
    """A real photograph-like JPEG: noisy, so it compresses like a photo does."""
    image = Image.effect_noise((width, height), 64).convert("RGB")
    exif = Image.Exif()
    if orientation:
        exif[0x0112] = orientation  # which way is up
    if camera:
        exif[0x010F] = camera  # the camera maker, one of the hidden details
    out = BytesIO()
    # No EXIF block at all unless asked for: even an empty one is a hidden
    # detail, and the upload would rightly save the photo again without it.
    image.save(out, "JPEG", quality=95, **({"exif": exif.tobytes()} if exif else {}))
    return out.getvalue()


def upload(client, staff_auth, shipment_id, name, content, content_type="image/jpeg"):
    return client.post(
        f"/api/staff/shipments/{shipment_id}/photos",
        headers=staff_auth,
        files=[("files", (name, content, content_type))],
    )


def newest_photo_id(response) -> int:
    return response.json()["photos"][-1]["id"]


def picture(response) -> Image.Image:
    return Image.open(BytesIO(response.content))


def test_an_upload_gets_a_small_preview(client, staff_auth, customer_auth, order):
    shipment_id = order["shipments"][0]["id"]
    original = jpeg(1600, 1200)
    photo_id = newest_photo_id(
        upload(client, staff_auth, shipment_id, "bundle.jpg", original)
    )

    preview = client.get(f"/api/photos/{photo_id}/thumbnail", headers=customer_auth)
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/jpeg"
    assert picture(preview).size == (400, 300), "longest side 400, shape kept"
    assert len(preview.content) < len(original) // 10

    full = client.get(f"/api/photos/{photo_id}", headers=customer_auth)
    assert full.content == original, "clicking still opens the photo as uploaded"


def test_a_sideways_phone_photo_is_turned_upright(client, staff_auth, customer_auth, order):
    """Phones store the picture sideways, with a note saying which way is up."""
    shipment_id = order["shipments"][0]["id"]
    photo_id = newest_photo_id(
        upload(client, staff_auth, shipment_id, "phone.jpg", jpeg(800, 400, orientation=6))
    )
    preview = client.get(f"/api/photos/{photo_id}/thumbnail", headers=customer_auth)
    assert picture(preview).size == (200, 400), "stored wide, shown tall"


def test_the_preview_carries_none_of_the_hidden_details(
    client, staff_auth, customer_auth, order
):
    """Camera, time, and often the GPS position of wherever it was taken."""
    shipment_id = order["shipments"][0]["id"]
    original = jpeg(camera="Alok Test Camera")
    assert b"Alok Test Camera" in original

    photo_id = newest_photo_id(upload(client, staff_auth, shipment_id, "a.jpg", original))
    preview = client.get(f"/api/photos/{photo_id}/thumbnail", headers=customer_auth)
    assert b"Alok Test Camera" not in preview.content
    assert len(picture(preview).getexif()) == 0


def test_a_transparent_png_gets_a_white_background(
    client, staff_auth, customer_auth, order
):
    """JPEG has no transparency, and Pillow's own choice would be black."""
    shipment_id = order["shipments"][0]["id"]
    out = BytesIO()
    Image.new("RGBA", (50, 50), (0, 0, 0, 0)).save(out, "PNG")
    photo_id = newest_photo_id(
        upload(client, staff_auth, shipment_id, "clear.png", out.getvalue(), "image/png")
    )
    preview = client.get(f"/api/photos/{photo_id}/thumbnail", headers=customer_auth)
    assert min(picture(preview).convert("RGB").getpixel((25, 25))) > 240


def test_a_file_that_only_pretends_to_be_a_picture_is_refused(client, staff_auth, order):
    """A PDF renamed to .jpg passes the name check and the browser's claim."""
    shipment_id = order["shipments"][0]["id"]
    on_disk = set(storage.ensure_storage().iterdir())

    refused = client.post(
        f"/api/staff/shipments/{shipment_id}/photos",
        headers=staff_auth,
        files=[
            ("files", ("good.jpg", jpeg(), "image/jpeg")),
            ("files", ("invoice.jpg", b"%PDF-1.4 not a picture\n", "image/jpeg")),
        ],
    )
    assert refused.status_code == 400
    assert "invoice.jpg" in refused.json()["detail"], "it names the file that was wrong"

    left = client.get(f"/api/staff/shipments/{shipment_id}/photos", headers=staff_auth)
    assert left.json()["photos"] == [], "all or nothing, as before"
    assert set(storage.ensure_storage().iterdir()) == on_disk, "nothing left on disk"


def test_a_picture_is_served_as_what_it_is_not_what_it_is_called(
    client, staff_auth, customer_auth, order
):
    shipment_id = order["shipments"][0]["id"]
    photo_id = newest_photo_id(
        upload(client, staff_auth, shipment_id, "misnamed.jpg", png(), "image/jpeg")
    )
    full = client.get(f"/api/photos/{photo_id}", headers=customer_auth)
    assert full.headers["content-type"] == "image/png"


def test_a_preview_reaches_its_owner_and_nobody_else(
    client, staff_auth, customer_auth, other_auth, order
):
    shipment_id = order["shipments"][0]["id"]
    photo_id = newest_photo_id(upload(client, staff_auth, shipment_id, "a.jpg", jpeg()))

    customer_route = f"/api/photos/{photo_id}/thumbnail"
    staff_route = f"/api/staff/photos/{photo_id}/thumbnail"
    assert client.get(customer_route, headers=customer_auth).status_code == 200
    assert client.get(customer_route, headers=other_auth).status_code == 404
    assert client.get(customer_route, headers=staff_auth).status_code == 403
    assert client.get(staff_route, headers=staff_auth).status_code == 200
    assert client.get(staff_route, headers=customer_auth).status_code == 403


def test_an_older_photo_falls_back_then_gets_a_preview_from_the_command(
    client, db, staff_auth, customer_auth, order
):
    shipment_id = order["shipments"][0]["id"]
    original = jpeg(1200, 900)
    photo_id = newest_photo_id(upload(client, staff_auth, shipment_id, "old.jpg", original))

    # Made to look like a photo uploaded before previews existed.
    row = db.get(Photo, photo_id)
    storage.delete(row.thumb_path)
    row.thumb_path = None
    db.commit()

    slow = client.get(f"/api/photos/{photo_id}/thumbnail", headers=customer_auth)
    assert slow.status_code == 200
    assert slow.content == original, "the full picture, rather than a broken tile"

    assert photos.backfill(db, dry_run=True)["made"] == 1
    assert db.get(Photo, photo_id).thumb_path is None, "a dry run changes nothing"
    assert photos.backfill(db)["made"] == 1
    assert photos.backfill(db)["made"] == 0, "running it again does nothing"

    fast = client.get(f"/api/photos/{photo_id}/thumbnail", headers=customer_auth)
    assert picture(fast).size == (400, 300)


def test_removing_a_photo_or_its_shipment_removes_the_preview_too(
    client, db, staff_auth, order
):
    shipment_id = order["shipments"][0]["id"]
    first = newest_photo_id(upload(client, staff_auth, shipment_id, "a.jpg", jpeg(600, 400)))
    second = newest_photo_id(upload(client, staff_auth, shipment_id, "b.jpg", jpeg(600, 400)))
    previews = {pid: db.get(Photo, pid).thumb_path for pid in (first, second)}
    assert all(storage.resolve(name) for name in previews.values())

    client.delete(f"/api/staff/photos/{first}", headers=staff_auth)
    assert storage.resolve(previews[first]) is None

    client.delete(f"/api/staff/shipments/{shipment_id}", headers=staff_auth)
    assert storage.resolve(previews[second]) is None
