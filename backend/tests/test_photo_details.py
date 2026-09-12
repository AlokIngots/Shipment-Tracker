"""Hidden details: gone from the full-size photo, not only from the preview.

A phone photo carries the camera, the time, and often the GPS position where
it was taken -- for these photos, the factory. The preview never carried
them; since step 29 the full-size photo a customer downloads does not
either. These tests hold both the upload and the command for older photos to
that, and hold the picture itself to looking the same.
"""

from io import BytesIO

from PIL import ExifTags, Image, ImageChops, ImageStat, PngImagePlugin

from app.models import Photo
from app.services import photos, storage
from tests.test_photo_previews import jpeg, newest_photo_id, picture, upload

CAMERA = "Alok Test Camera"
XMP = b"<x:xmpmeta>test-xmp-note</x:xmpmeta>"
COMMENT = b"test comment"


def detailed_jpeg(width=1200, height=900, *, orientation=None) -> bytes:
    """A photo carrying every kind of hidden detail a phone or an editor adds."""
    image = Image.effect_noise((width, height), 64).convert("RGB")
    exif = Image.Exif()
    exif[ExifTags.Base.Make] = CAMERA
    if orientation:
        exif[ExifTags.Base.Orientation] = orientation
    gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
    gps[ExifTags.GPS.GPSLatitudeRef] = "N"
    gps[ExifTags.GPS.GPSLatitude] = (19.0, 4.0, 30.0)
    out = BytesIO()
    image.save(out, "JPEG", quality=95, exif=exif.tobytes(), xmp=XMP, comment=COMMENT)
    return out.getvalue()


def assert_no_details(content: bytes) -> None:
    for secret in (CAMERA.encode(), XMP, COMMENT):
        assert secret not in content, f"{secret!r} survived"
    served = Image.open(BytesIO(content))
    assert len(served.getexif()) == 0
    assert not served.getexif().get_ifd(ExifTags.IFD.GPSInfo)
    assert not photos._carries_details(served), "no EXIF, XMP, comment or second picture"


def test_the_full_size_photo_loses_its_hidden_details(
    client, staff_auth, customer_auth, order
):
    original = detailed_jpeg()
    assert CAMERA.encode() in original and XMP in original and COMMENT in original
    assert Image.open(BytesIO(original)).getexif().get_ifd(ExifTags.IFD.GPSInfo), "the test photo has a GPS position"

    shipment_id = order["shipments"][0]["id"]
    photo_id = newest_photo_id(upload(client, staff_auth, shipment_id, "bars.jpg", original))

    full = client.get(f"/api/photos/{photo_id}", headers=customer_auth)
    assert full.status_code == 200
    assert full.headers["content-type"] == "image/jpeg"
    assert_no_details(full.content)
    assert_no_details(client.get(f"/api/staff/photos/{photo_id}", headers=staff_auth).content)

    # The same picture: same size, and no pixel moved more than a hair.
    before, after = Image.open(BytesIO(original)), picture(full)
    assert after.size == before.size
    difference = ImageChops.difference(before.convert("RGB"), after.convert("RGB"))
    assert max(ImageStat.Stat(difference).mean) < 2


def test_a_photo_with_nothing_hidden_is_kept_byte_for_byte(
    client, staff_auth, customer_auth, order
):
    shipment_id = order["shipments"][0]["id"]
    original = jpeg(800, 600)
    photo_id = newest_photo_id(upload(client, staff_auth, shipment_id, "plain.jpg", original))
    assert client.get(f"/api/photos/{photo_id}", headers=customer_auth).content == original


def test_a_sideways_photo_is_stored_upright_once_the_note_saying_so_has_gone(
    client, staff_auth, customer_auth, order
):
    """Removing the details removes the note that says which way is up, so
    the picture itself has to be turned, or it would show sideways."""
    shipment_id = order["shipments"][0]["id"]
    photo_id = newest_photo_id(
        upload(client, staff_auth, shipment_id, "phone.jpg", detailed_jpeg(800, 400, orientation=6))
    )
    full = client.get(f"/api/photos/{photo_id}", headers=customer_auth)
    assert picture(full).size == (400, 800), "stored wide, now stored tall"
    assert_no_details(full.content)

    preview = client.get(f"/api/photos/{photo_id}/thumbnail", headers=customer_auth)
    assert picture(preview).size == (200, 400), "and the preview is still upright"


def test_a_png_loses_its_notes_but_keeps_its_transparency(
    client, staff_auth, customer_auth, order
):
    image = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    notes = PngImagePlugin.PngInfo()
    notes.add_text("Comment", "test comment")
    notes.add_itxt("XML:com.adobe.xmp", XMP.decode())
    out = BytesIO()
    image.save(out, "PNG", pnginfo=notes)

    shipment_id = order["shipments"][0]["id"]
    photo_id = newest_photo_id(
        upload(client, staff_auth, shipment_id, "drawing.png", out.getvalue(), "image/png")
    )
    full = client.get(f"/api/photos/{photo_id}", headers=customer_auth)
    assert full.headers["content-type"] == "image/png"
    assert b"test comment" not in full.content and XMP not in full.content
    served = picture(full)
    served.load()
    assert served.text == {}
    assert served.convert("RGBA").getpixel((20, 20))[3] == 0, "still transparent"


def test_a_phone_photo_with_a_second_picture_inside_is_accepted(
    client, staff_auth, customer_auth, order
):
    """Many iPhones and Samsungs save a JPEG with a second picture after the
    first. Pillow calls that MPO, and until step 29 the upload refused it as
    "not a picture". The second picture is a hidden detail too, and goes."""
    first = Image.effect_noise((600, 400), 64).convert("RGB")
    second = Image.effect_noise((300, 200), 64).convert("RGB")
    out = BytesIO()
    first.save(out, "MPO", save_all=True, append_images=[second])
    assert Image.open(BytesIO(out.getvalue())).format == "MPO"

    shipment_id = order["shipments"][0]["id"]
    response = upload(client, staff_auth, shipment_id, "iphone.jpg", out.getvalue())
    assert response.status_code == 201, response.text

    full = client.get(f"/api/photos/{newest_photo_id(response)}", headers=customer_auth)
    assert full.headers["content-type"] == "image/jpeg"
    served = picture(full)
    assert served.format == "JPEG" and getattr(served, "n_frames", 1) == 1
    assert served.size == (600, 400)


def test_a_photo_cut_short_is_refused_and_nothing_is_left(client, staff_auth, order):
    """It passes the check that it is a picture, and cannot be drawn."""
    shipment_id = order["shipments"][0]["id"]
    whole = detailed_jpeg()
    on_disk = set(storage.ensure_storage().iterdir())

    refused = upload(client, staff_auth, shipment_id, "copied.jpg", whole[: len(whole) // 2])
    assert refused.status_code == 400
    assert "copied.jpg" in refused.json()["detail"]
    assert "cut short" in refused.json()["detail"]

    left = client.get(f"/api/staff/shipments/{shipment_id}/photos", headers=staff_auth)
    assert left.json()["photos"] == []
    assert set(storage.ensure_storage().iterdir()) == on_disk, "nothing left on disk"


def test_the_command_cleans_older_photos_and_is_safe_to_run_again(
    client, db, staff_auth, customer_auth, order
):
    shipment_id = order["shipments"][0]["id"]
    photo_id = newest_photo_id(upload(client, staff_auth, shipment_id, "old.jpg", jpeg(600, 400)))

    # Made to look like a photo uploaded before details were removed.
    row = db.get(Photo, photo_id)
    clean_name = row.stored_path
    row.stored_path = storage.store_upload(BytesIO(detailed_jpeg(600, 400)), ".jpg")
    storage.delete(clean_name)
    db.commit()
    detailed_name = row.stored_path

    assert CAMERA.encode() in client.get(f"/api/photos/{photo_id}", headers=customer_auth).content

    assert photos.clean_existing(db, dry_run=True)["cleaned"] == 1
    assert db.get(Photo, photo_id).stored_path == detailed_name, "a dry run changes nothing"

    counts = photos.clean_existing(db)
    assert counts["cleaned"] == 1
    assert storage.resolve(detailed_name) is None, "the file with the details is gone"
    assert_no_details(client.get(f"/api/photos/{photo_id}", headers=customer_auth).content)

    again = photos.clean_existing(db)
    assert again["cleaned"] == 0 and again["already_clean"] == 1, "running it again does nothing"
