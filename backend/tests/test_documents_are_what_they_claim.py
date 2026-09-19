"""Step 52: a document must really be a PDF, JPG or PNG.

The audit (N4) found documents were checked by name and by the browser's
stated type only -- both claims -- so a renamed file would be stored and
handed to a customer. Now the first bytes decide: anything else is refused,
and a picture named as the wrong kind is stored as what it is.
"""

import io

import pytest

from app.services import storage

PDF = b"%PDF-1.4\n%fake but well-formed enough to be recognised\n"
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture
def store_here(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "STORAGE_DIR", tmp_path)
    return tmp_path


# ------------------------------------------------------------ no database


def test_the_first_bytes_decide_what_a_document_is():
    assert storage.document_suffix(PDF) == ".pdf"
    assert storage.document_suffix(JPEG) == ".jpg"
    assert storage.document_suffix(PNG) == ".png"
    assert storage.document_suffix(b"MZ\x90\x00 a Windows program") is None
    assert storage.document_suffix(b"<html>") is None
    assert storage.document_suffix(b"") is None


def test_a_renamed_file_is_refused_and_not_kept(store_here):
    with pytest.raises(storage.UploadRejected):
        storage.store_document(io.BytesIO(b"<html>not a pdf</html>"), ".pdf")
    assert list(store_here.iterdir()) == []


def test_a_picture_named_as_the_wrong_kind_is_stored_as_what_it_is(store_here):
    stored = storage.store_document(io.BytesIO(PNG), ".jpg")
    assert stored.endswith(".png")
    assert (store_here / stored).read_bytes() == PNG
    assert storage.media_type_for(stored) == "image/png"


def test_jpeg_and_jpg_are_the_same_kind(store_here):
    stored = storage.store_document(io.BytesIO(JPEG), ".jpeg")
    assert stored.endswith(".jpeg")


def test_a_real_pdf_goes_through_unchanged(store_here):
    stored = storage.store_document(io.BytesIO(PDF), ".pdf")
    assert (store_here / stored).read_bytes() == PDF


def test_the_command_line_is_held_to_the_same_rule(store_here, tmp_path_factory):
    source = tmp_path_factory.mktemp("in") / "invoice.pdf"
    source.write_bytes(b"just some text")
    with pytest.raises(storage.UploadRejected):
        storage.store_file(source)
    assert list(store_here.iterdir()) == []


# ------------------------------------------------------------- the screen


def test_the_staff_screen_refuses_a_renamed_file(client, staff_auth, order):
    refused = client.post(
        f"/api/staff/shipments/{order['shipments'][0]['id']}/documents",
        headers=staff_auth,
        data={"doc_type": "Packing List"},
        files={"file": ("pl.pdf", b"<html>not a pdf</html>", "application/pdf")},
    )
    assert refused.status_code == 400
    assert "not really a PDF" in refused.json()["detail"]

    listed = client.get("/api/staff/shipments", headers=staff_auth).json()
    packing = next(d for d in listed[0]["documents"] if d["doc_type"] == "Packing List")
    assert packing["uploaded"] is False
