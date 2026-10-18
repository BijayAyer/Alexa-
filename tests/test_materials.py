import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from cram import db
from cram.web import app, extract_pdf_text, obvious_tool


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "materials.db")
    db.init_db()
    return TestClient(app)


def sample_pdf() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 20 200 Td (Photosynthesis uses light energy to make glucose.) Tj ET")
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    fonts = DictionaryObject({NameObject("/F1"): writer._add_object(font)})
    page[NameObject("/Contents")] = writer._add_object(stream)
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): fonts})
    from io import BytesIO

    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_save_notes_material(client):
    response = client.post("/api/materials/text", data={
        "topic": "biology", "text": "Plants use sunlight to make glucose."
    })

    assert response.status_code == 200
    assert db.get_notes("Biology") == ["Plants use sunlight to make glucose."]


def test_upload_pdf_extracts_text_and_saves_it(client):
    response = client.post(
        "/api/materials/pdf",
        data={"topic": "biology"},
        files={"file": ("lesson.pdf", sample_pdf(), "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["filename"] == "lesson.pdf"
    assert "Photosynthesis uses light energy" in db.get_notes("biology")[0]


def test_upload_rejects_non_pdf_and_image_only_pdf(client):
    non_pdf = client.post(
        "/api/materials/pdf",
        data={"topic": "biology"},
        files={"file": ("notes.txt", b"plain text", "text/plain")},
    )
    empty_pdf = PdfWriter()
    from io import BytesIO

    output = BytesIO()
    empty_pdf.write(output)
    no_text = client.post(
        "/api/materials/pdf",
        data={"topic": "biology"},
        files={"file": ("scan.pdf", output.getvalue(), "application/pdf")},
    )

    assert non_pdf.status_code == 415
    assert no_text.status_code == 422
    assert "ocr" in no_text.json()["detail"].lower()


def test_study_question_routes_to_grounded_tool():
    assert obvious_tool("What do plants make?") == "answer_from_notes"