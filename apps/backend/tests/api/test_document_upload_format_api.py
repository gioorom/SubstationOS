"""
API tests for format classification on upload (Milestone 25.2).

Before this milestone the upload endpoint never set a format, so every
document in the system was stored as ``other``. These tests specify what
it stores now - and that a document it cannot classify is still accepted.
"""

from __future__ import annotations

import io

import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.document import Document as DocumentRecord
from app.models.document import DocumentFormat

PDF_CONTENT = b"%PDF-1.7 montante T2 single line diagram"
PNG_CONTENT = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40
DWG_CONTENT = b"AC1027" + b"\x00" * 40


def _upload(
    api_client: TestClient,
    *,
    filename: str,
    content: bytes,
    mime_type: str,
) -> httpx.Response:
    return api_client.post(
        "/documents/upload",
        files={"file": (filename, io.BytesIO(content), mime_type)},
        data={"scope": "canonical_library"},
    )


def test_an_uploaded_pdf_is_stored_as_a_pdf(api_client: TestClient) -> None:
    response = _upload(
        api_client,
        filename="schema.pdf",
        content=PDF_CONTENT,
        mime_type="application/pdf",
    )

    assert response.status_code == 200
    assert response.json()["file_format"] == DocumentFormat.PDF


def test_an_uploaded_drawing_is_stored_as_a_drawing(
    api_client: TestClient,
) -> None:
    response = _upload(
        api_client,
        filename="layout.dwg",
        content=DWG_CONTENT,
        mime_type="application/octet-stream",
    )

    assert response.json()["file_format"] == DocumentFormat.DWG


def test_an_uploaded_photo_is_stored_as_an_image(
    api_client: TestClient,
) -> None:
    response = _upload(
        api_client,
        filename="site_photo.png",
        content=PNG_CONTENT,
        mime_type="image/png",
    )

    assert response.json()["file_format"] == DocumentFormat.IMAGE


def test_the_bytes_overrule_the_declared_type_and_the_extension(
    api_client: TestClient,
) -> None:
    """A PDF uploaded under a ``.dwg`` name is a PDF. The name is a label
    somebody typed; the bytes are the document."""

    response = _upload(
        api_client,
        filename="single_line_diagram.dwg",
        content=PDF_CONTENT,
        mime_type="image/vnd.dwg",
    )

    assert response.json()["file_format"] == DocumentFormat.PDF


def test_an_unclassifiable_upload_is_accepted_and_stored_as_other(
    api_client: TestClient,
) -> None:
    """``other`` means *unclassified*, not rejected. Refusing the file
    over an unrecognised extension would lose a document to protect a
    column."""

    response = _upload(
        api_client,
        filename="site_notes.qzx",
        content=b"nothing identifiable here",
        mime_type="application/octet-stream",
    )

    assert response.status_code == 200
    assert response.json()["file_format"] == DocumentFormat.OTHER


def test_contradictory_evidence_stores_other_rather_than_a_guess(
    api_client: TestClient,
) -> None:
    """No signature, a MIME type saying one thing and an extension saying
    another. Neither can arbitrate the other, so nothing is recorded."""

    response = _upload(
        api_client,
        filename="drawing.dwg",
        content=b"unsigned bytes with no known header",
        mime_type="application/pdf",
    )

    assert response.json()["file_format"] == DocumentFormat.OTHER


def test_the_classified_format_is_persisted_not_merely_reported(
    api_client: TestClient, db_session: Session
) -> None:
    response = _upload(
        api_client,
        filename="schema.pdf",
        content=PDF_CONTENT,
        mime_type="application/pdf",
    )

    stored = db_session.get(DocumentRecord, response.json()["id"])

    assert stored.file_format is DocumentFormat.PDF


def test_documents_stored_as_other_remain_readable(
    api_client: TestClient,
) -> None:
    """Every document uploaded before this milestone is recorded as
    ``other``. Listing must keep working for them exactly as before."""

    _upload(
        api_client,
        filename="legacy_notes.qzx",
        content=b"unrecognised",
        mime_type="application/octet-stream",
    )

    listed = api_client.get("/documents/")

    assert listed.status_code == 200
    assert [document["file_format"] for document in listed.json()] == [
        DocumentFormat.OTHER
    ]
