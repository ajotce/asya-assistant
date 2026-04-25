import io

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from app.storage.runtime import file_store


def _create_session(client: TestClient) -> str:
    response = client.post("/api/session")
    assert response.status_code == 201
    return response.json()["session_id"]


def test_upload_rejects_more_than_max_files_per_message() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    files = [("files", (f"f{i}.pdf", b"%PDF-1.7", "application/pdf")) for i in range(11)]
    response = client.post(f"/api/session/{session_id}/files", files=files)

    assert response.status_code == 400
    assert "не более 10 файлов" in response.json()["detail"]


def test_upload_rejects_unsupported_file_type() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    response = client.post(
        f"/api/session/{session_id}/files",
        files=[("files", ("notes.txt", b"hello", "text/plain"))],
    )

    assert response.status_code == 400
    assert "не поддерживается" in response.json()["detail"]


def test_upload_rejects_file_over_size_limit() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    settings = get_settings()
    old_limit = settings.max_file_size_mb
    settings.max_file_size_mb = 1
    try:
        oversized = b"x" * (1024 * 1024 + 1)
        response = client.post(
            f"/api/session/{session_id}/files",
            files=[("files", ("big.pdf", oversized, "application/pdf"))],
        )
    finally:
        settings.max_file_size_mb = old_limit

    assert response.status_code == 400
    assert "превышает лимит 1 МБ" in response.json()["detail"]


def test_extract_text_from_pdf_docx_xlsx() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    files = [
        ("files", ("sample.pdf", _make_pdf_bytes("PDF hello"), "application/pdf")),
        (
            "files",
            (
                "sample.docx",
                _make_docx_bytes("DOCX привет"),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            ),
        ),
        (
            "files",
            (
                "sample.xlsx",
                _make_xlsx_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ),
        ),
    ]
    response = client.post(f"/api/session/{session_id}/files", files=files)
    assert response.status_code == 201

    stored = file_store.get_session_files(session_id)
    by_name = {file.filename: file for file in stored}
    assert "PDF hello" in (by_name["sample.pdf"].extracted_text or "")
    assert "DOCX привет" in (by_name["sample.docx"].extracted_text or "")
    xlsx_text = by_name["sample.xlsx"].extracted_text or ""
    assert "[Лист: Sheet1]" in xlsx_text
    assert "Строка 1:" in xlsx_text
    assert "1=Имя" in xlsx_text


def test_upload_rejects_damaged_docx() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    response = client.post(
        f"/api/session/{session_id}/files",
        files=[("files", ("broken.docx", b"not-a-docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"))],
    )
    assert response.status_code == 400
    assert "может быть поврежд" in response.json()["detail"]


def test_upload_rejects_empty_xlsx() -> None:
    client = TestClient(app)
    session_id = _create_session(client)

    response = client.post(
        f"/api/session/{session_id}/files",
        files=[("files", ("empty.xlsx", _make_empty_xlsx_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))],
    )
    assert response.status_code == 400
    assert "не содержит данных" in response.json()["detail"]


def _make_pdf_bytes(text: str) -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _make_docx_bytes(text: str) -> bytes:
    from docx import Document

    doc = Document()
    doc.add_paragraph(text)
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def _make_xlsx_bytes() -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["Имя", "Значение"])
    ws.append(["A", 123])
    out = io.BytesIO()
    wb.save(out)
    wb.close()
    return out.getvalue()


def _make_empty_xlsx_bytes() -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    out = io.BytesIO()
    wb.save(out)
    wb.close()
    return out.getvalue()
