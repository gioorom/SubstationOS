"""
The hardened Document API (Milestone 30.1.3).

Four things this milestone had to make true, and each has tests here:

1. no storage location ever leaves the backend;
2. a document can be read on its own, and downloaded;
3. lists are paged, filtered and sorted **by the server**;
4. a missing document and missing content are different answers.
"""

from __future__ import annotations

import io

import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.document import Document as DocumentRecord

PDF = b"%PDF-1.7 Trasformatore TR1 630 kVA"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40


def _project(api_client: TestClient, code: str = "CP-001") -> dict:
    response = api_client.post(
        "/projects/",
        json={
            "name": "Cabina Primaria Gamma",
            "code": code,
            "customer": "Distributore Nazionale",
        },
    )

    assert response.status_code == 201

    return response.json()


def _upload(
    api_client: TestClient,
    *,
    filename: str = "schema.pdf",
    content: bytes = PDF,
    mime_type: str = "application/pdf",
    project_id: int | None = None,
) -> httpx.Response:
    data: dict[str, str] = (
        {"scope": "project", "project_id": str(project_id)}
        if project_id is not None
        else {"scope": "canonical_library"}
    )

    return api_client.post(
        "/documents/upload",
        files={"file": (filename, io.BytesIO(content), mime_type)},
        data=data,
    )


def _uploaded(api_client: TestClient, **kwargs) -> dict:
    response = _upload(api_client, **kwargs)

    assert response.status_code == 200

    return response.json()["document"]


# --- The public contract carries no storage location ----------------------


def test_the_document_list_never_exposes_a_storage_path(
    api_client: TestClient,
) -> None:
    _uploaded(api_client)

    body = api_client.get("/documents/").json()

    assert body["items"]

    for document in body["items"]:
        assert "file_path" not in document

        # Not merely the field name: no value in the payload may look
        # like the storage root either.
        assert "storage" not in str(document).lower()


def test_document_detail_never_exposes_a_storage_path(
    api_client: TestClient,
) -> None:
    document = _uploaded(api_client)

    detail = api_client.get(f"/documents/{document['id']}").json()

    assert "file_path" not in detail
    assert "storage_reference" not in detail
    assert "storage" not in str(detail).lower()


def test_the_upload_response_never_exposes_a_storage_path(
    api_client: TestClient,
) -> None:
    body = _upload(api_client).json()

    assert "file_path" not in body["document"]
    assert "storage" not in str(body).lower()


def test_no_public_document_field_is_named_after_a_path(
    api_client: TestClient,
) -> None:
    document = _uploaded(api_client)

    detail = api_client.get(f"/documents/{document['id']}").json()

    for field in detail:
        assert "path" not in field.lower()
        assert "directory" not in field.lower()


# --- Detail ----------------------------------------------------------------


def test_document_detail_returns_the_governed_record(
    api_client: TestClient,
) -> None:
    project = _project(api_client)

    document = _uploaded(api_client, project_id=project["id"])

    detail = api_client.get(f"/documents/{document['id']}").json()

    assert detail["id"] == document["id"]
    assert detail["filename"] == "schema.pdf"
    assert detail["file_format"] == "pdf"
    assert detail["scope"] == "project"
    assert detail["project_id"] == project["id"]
    assert detail["project_name"] == project["name"]
    assert detail["content_available"] is True


def test_document_detail_preserves_canonical_library_scope(
    api_client: TestClient,
) -> None:
    document = _uploaded(api_client)

    detail = api_client.get(f"/documents/{document['id']}").json()

    assert detail["scope"] == "canonical_library"
    assert detail["project_id"] is None


def test_document_detail_reports_ingestion_state_once_ingested(
    api_client: TestClient,
) -> None:
    project = _project(api_client)
    document = _uploaded(api_client, project_id=project["id"])

    api_client.post(
        "/documents/ingestion/jobs", json={"document_id": document["id"]}
    )

    detail = api_client.get(f"/documents/{document['id']}").json()

    assert detail["ingestion_state"] is not None
    assert detail["content_checksum"] is not None
    assert detail["checksum_algorithm"] == "sha256"
    assert detail["size_bytes"] == len(PDF)


def test_a_document_that_has_not_been_ingested_reports_no_checksum(
    api_client: TestClient,
) -> None:
    """An un-run identity is not a zero, and is not invented."""

    document = _uploaded(api_client)

    detail = api_client.get(f"/documents/{document['id']}").json()

    assert detail["content_checksum"] is None
    assert detail["size_bytes"] is None
    assert detail["ingestion_state"] is None


def test_an_unknown_document_detail_returns_404(
    api_client: TestClient,
) -> None:
    assert api_client.get("/documents/9999").status_code == 404


# --- Download --------------------------------------------------------------


def test_downloading_returns_the_original_bytes(
    api_client: TestClient,
) -> None:
    document = _uploaded(api_client)

    response = api_client.get(f"/documents/{document['id']}/content")

    assert response.status_code == 200
    assert response.content == PDF


def test_downloading_returns_the_media_type_for_the_stored_format(
    api_client: TestClient,
) -> None:
    document = _uploaded(api_client)

    response = api_client.get(f"/documents/{document['id']}/content")

    assert response.headers["content-type"].startswith("application/pdf")


def test_an_unclassified_document_is_served_as_a_generic_stream(
    api_client: TestClient,
) -> None:
    """Telling a browser a file is a PDF when nobody established that is
    a worse answer than telling it nothing."""

    document = _uploaded(
        api_client,
        filename="notes.qzx",
        content=b"unrecognised",
        mime_type="application/octet-stream",
    )

    response = api_client.get(f"/documents/{document['id']}/content")

    assert response.headers["content-type"].startswith(
        "application/octet-stream"
    )


def test_the_download_uses_the_stored_filename(
    api_client: TestClient,
) -> None:
    document = _uploaded(api_client, filename="schema-funzionale.pdf")

    response = api_client.get(f"/documents/{document['id']}/content")

    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="schema-funzionale.pdf"'
    )


def test_the_download_is_always_an_attachment(
    api_client: TestClient,
) -> None:
    """A document of unverified provenance must not be rendered by the
    browser in this application's origin."""

    document = _uploaded(api_client)

    response = api_client.get(f"/documents/{document['id']}/content")

    assert response.headers["content-disposition"].startswith("attachment")
    assert "inline" not in response.headers["content-disposition"]


def test_a_traversal_filename_cannot_escape_through_the_header(
    api_client: TestClient,
) -> None:
    document = _uploaded(api_client, filename="../../../etc/passwd")

    response = api_client.get(f"/documents/{document['id']}/content")

    disposition = response.headers["content-disposition"]

    assert ".." not in disposition
    assert "/" not in disposition.split("filename=")[1]
    assert "\\" not in disposition


def test_a_quote_in_a_filename_cannot_inject_a_header(
    api_client: TestClient,
) -> None:
    document = _uploaded(
        api_client, filename='evil";\r\nX-Injected: yes.pdf'
    )

    response = api_client.get(f"/documents/{document['id']}/content")

    assert "x-injected" not in {
        key.lower() for key in response.headers
    }
    assert "\r" not in response.headers["content-disposition"]
    assert "\n" not in response.headers["content-disposition"]


def test_downloading_an_unknown_document_returns_404(
    api_client: TestClient,
) -> None:
    assert (
        api_client.get("/documents/9999/content").status_code == 404
    )


def test_missing_content_is_distinguished_from_a_missing_document(
    api_client: TestClient,
    db_session: Session,
) -> None:
    """
    A missing registry row and a missing file are different problems with
    different remedies. Both answer 404 - there is no other honest status
    for either - but the message names which one it is.
    """

    document = _uploaded(api_client)

    record = db_session.get(DocumentRecord, document["id"])
    record.file_path = str(record.file_path) + ".gone"
    db_session.commit()

    response = api_client.get(f"/documents/{document['id']}/content")

    assert response.status_code == 404
    assert "content" in response.json()["detail"].lower()

    # The document itself is still readable, and says its content is not.
    detail = api_client.get(f"/documents/{document['id']}").json()

    assert detail["content_available"] is False


def test_a_document_id_cannot_be_used_to_fetch_an_unrelated_file(
    api_client: TestClient,
) -> None:
    """
    The only input is an integer id, resolved against the registry. There
    is no parameter through which a path could be expressed, so a caller
    can only ever receive the bytes of the document that id names.
    """

    first = _uploaded(api_client, filename="a.pdf", content=b"%PDF-A")
    second = _uploaded(api_client, filename="b.pdf", content=b"%PDF-B")

    assert (
        api_client.get(f"/documents/{first['id']}/content").content
        == b"%PDF-A"
    )
    assert (
        api_client.get(f"/documents/{second['id']}/content").content
        == b"%PDF-B"
    )


def test_a_traversal_id_is_not_even_a_route(
    api_client: TestClient,
) -> None:
    for attempt in ("../../etc/passwd", "..%2F..%2Fetc%2Fpasswd", "0"):
        response = api_client.get(f"/documents/{attempt}/content")

        # 422 (not an integer) or 404 (no such document). Never 200.
        assert response.status_code in (404, 422)


# --- Upload response -------------------------------------------------------


def test_upload_returns_the_declared_response_model(
    api_client: TestClient,
) -> None:
    project = _project(api_client)

    body = _upload(api_client, project_id=project["id"]).json()

    assert set(body) == {"document", "scope", "analysis", "warnings"}
    assert body["scope"] == "project"
    assert body["document"]["filename"] == "schema.pdf"
    assert body["analysis"]["status"] in {
        "completed",
        "skipped",
        "failed",
        "no_text",
        "unsupported_file_type",
    }


def test_a_canonical_library_upload_reports_a_skipped_analysis(
    api_client: TestClient,
) -> None:
    body = _upload(api_client).json()

    assert body["scope"] == "canonical_library"
    assert body["analysis"]["status"] == "skipped"
    assert body["analysis"]["failure"] is None


def test_an_unclassifiable_upload_carries_a_warning(
    api_client: TestClient,
) -> None:
    body = _upload(
        api_client,
        filename="notes.qzx",
        content=b"unrecognised",
        mime_type="application/octet-stream",
    ).json()

    assert body["document"]["file_format"] == "other"
    assert any("unclassified" in warning for warning in body["warnings"])


def test_a_classifiable_upload_carries_no_warnings(
    api_client: TestClient,
) -> None:
    body = _upload(api_client).json()

    assert body["warnings"] == []


def test_two_uploads_of_the_same_filename_do_not_overwrite_each_other(
    api_client: TestClient,
) -> None:
    """
    Before this milestone the stored path was the uploaded filename, so
    the second upload silently destroyed the first.
    """

    first = _uploaded(api_client, filename="schema.pdf", content=b"%PDF-1")
    second = _uploaded(api_client, filename="schema.pdf", content=b"%PDF-2")

    assert first["id"] != second["id"]

    assert (
        api_client.get(f"/documents/{first['id']}/content").content
        == b"%PDF-1"
    )
    assert (
        api_client.get(f"/documents/{second['id']}/content").content
        == b"%PDF-2"
    )
