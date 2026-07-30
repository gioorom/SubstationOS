"""
API tests for the Canonical PDF Representation (Milestone 26.1).

They pin the status-code contract, which is the part a client depends on
and the part most easily eroded: a refusal that is an *answer about the
document* is a `200` result carrying a typed cause, never a `422`.
"""

from __future__ import annotations

import io
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.document import Document as DocumentRecord
from tests._pdf_builder import (
    corrupted_pdf,
    encrypted_pdf,
    multi_page_pdf,
    single_page_pdf,
)


def _upload(
    api_client: TestClient,
    *,
    filename: str = "montante-T2-schema.pdf",
    content: bytes | None = None,
    mime_type: str = "application/pdf",
) -> dict:
    response = api_client.post(
        "/documents/upload",
        files={
            "file": (
                filename,
                io.BytesIO(content if content is not None else single_page_pdf()),
                mime_type,
            )
        },
        data={"scope": "canonical_library"},
    )

    assert response.status_code == 200

    return response.json()["document"]


def _ingest(api_client: TestClient, document_id: int) -> None:
    response = api_client.post(
        "/documents/ingestion/jobs", json={"document_id": document_id}
    )

    assert response.status_code == 201


def _canonicalize(api_client: TestClient, document_id: int) -> httpx.Response:
    return api_client.post(
        f"/documents/{document_id}/canonical-representation"
    )


def _ready_document(api_client: TestClient, **kwargs) -> dict:
    document = _upload(api_client, **kwargs)
    _ingest(api_client, document["id"])

    return document


# --- Building -----------------------------------------------------------


def test_canonicalising_a_ready_pdf_returns_201(
    api_client: TestClient,
) -> None:
    document = _ready_document(
        api_client, content=single_page_pdf("Rated voltage 145 kV")
    )

    response = _canonicalize(api_client, document["id"])

    assert response.status_code == 201
    body = response.json()
    assert body["succeeded"] is True
    assert body["reused"] is False
    assert body["representation"]["page_count"] == 1


def test_the_result_reports_the_representations_provenance(
    api_client: TestClient,
) -> None:
    document = _ready_document(api_client)

    body = _canonicalize(api_client, document["id"]).json()
    representation = body["representation"]

    assert representation["parser_name"] == "pymupdf"
    assert representation["parser_version"]
    assert representation["representation_version"] == "1.0"
    assert representation["content_checksum"]


def test_re_canonicalising_identical_bytes_returns_200_and_reuses(
    api_client: TestClient,
) -> None:
    """Nothing was created, so nothing is reported as created. `reused`
    is the observable proof of idempotency."""

    document = _ready_document(api_client)
    _canonicalize(api_client, document["id"])

    response = _canonicalize(api_client, document["id"])

    assert response.status_code == 200
    assert response.json()["reused"] is True


# --- Reading ------------------------------------------------------------


def test_the_representation_can_be_read_back_in_full(
    api_client: TestClient,
) -> None:
    document = _ready_document(
        api_client, content=multi_page_pdf("Bay 21", "Bay 22")
    )
    _canonicalize(api_client, document["id"])

    response = api_client.get(
        f"/documents/{document['id']}/canonical-representation"
    )

    assert response.status_code == 200
    body = response.json()
    assert [page["page_number"] for page in body["pages"]] == [1, 2]
    assert body["pages"][0]["blocks"][0]["spans"][0]["text"]


def test_the_representation_exposes_geometry_and_style(
    api_client: TestClient,
) -> None:
    document = _ready_document(
        api_client, content=single_page_pdf("145 kV", font_size=17.0)
    )
    _canonicalize(api_client, document["id"])

    body = api_client.get(
        f"/documents/{document['id']}/canonical-representation"
    ).json()
    span = body["pages"][0]["blocks"][0]["spans"][0]

    assert span["bounding_box"]["x0"] == 72.0
    assert span["style"]["font_size"] == 17.0
    assert span["style"]["bold"] is False


def test_reading_a_representation_that_was_never_built_returns_404(
    api_client: TestClient,
) -> None:
    document = _ready_document(api_client)

    response = api_client.get(
        f"/documents/{document['id']}/canonical-representation"
    )

    assert response.status_code == 404


# --- Reading one page (EPIC 30.2) ---------------------------------------
#
# The Engineering Workspace renders one page at a time. These tests pin
# the two properties that make the page read safe to build a viewer on:
# it returns exactly what the full representation holds for that page,
# and it invents nothing for a page the parser never recorded.


def _page(
    api_client: TestClient, document_id: int, page_number: int
) -> httpx.Response:
    return api_client.get(
        f"/documents/{document_id}/canonical-representation"
        f"/pages/{page_number}"
    )


def test_one_page_can_be_read_on_its_own(api_client: TestClient) -> None:
    document = _ready_document(
        api_client, content=multi_page_pdf("Bay 21", "Bay 22")
    )
    _canonicalize(api_client, document["id"])

    response = _page(api_client, document["id"], 2)

    assert response.status_code == 200
    assert response.json()["page_number"] == 2


def test_a_page_read_is_identical_to_that_page_of_the_whole(
    api_client: TestClient,
) -> None:
    """The point of the projection: fewer bytes, never different ones.

    A viewer that highlights a span at these coordinates must be looking
    at the same artefact the full read describes, or the highlight is
    drawn somewhere the parser never said anything was.
    """

    document = _ready_document(
        api_client, content=multi_page_pdf("Bay 21", "Bay 22")
    )
    _canonicalize(api_client, document["id"])

    whole = api_client.get(
        f"/documents/{document['id']}/canonical-representation"
    ).json()

    for page in whole["pages"]:
        assert (
            _page(api_client, document["id"], page["page_number"]).json()
            == page
        )


def test_the_page_read_carries_the_parsers_own_geometry(
    api_client: TestClient,
) -> None:
    document = _ready_document(
        api_client, content=single_page_pdf("145 kV", font_size=17.0)
    )
    _canonicalize(api_client, document["id"])

    span = _page(api_client, document["id"], 1).json()["blocks"][0][
        "spans"
    ][0]

    assert span["bounding_box"]["x0"] == 72.0
    # `reading_order` is the key evidence provenance joins on: an
    # observation names the span it read, and this is that span.
    assert span["reading_order"] == 0
    assert span["style"]["font_size"] == 17.0


def test_a_page_the_representation_does_not_record_returns_404(
    api_client: TestClient,
) -> None:
    document = _ready_document(api_client, content=single_page_pdf())
    _canonicalize(api_client, document["id"])

    assert _page(api_client, document["id"], 2).status_code == 404
    assert _page(api_client, document["id"], 0).status_code == 404


def test_reading_a_page_before_canonicalisation_returns_404(
    api_client: TestClient,
) -> None:
    document = _ready_document(api_client)

    assert _page(api_client, document["id"], 1).status_code == 404


def test_a_page_of_an_unknown_document_returns_404(
    api_client: TestClient,
) -> None:
    assert _page(api_client, 4321, 1).status_code == 404


def test_one_documents_page_cannot_be_read_through_another(
    api_client: TestClient,
) -> None:
    """Page numbers are not identities. Asking document B for a page
    only document A was canonicalised into must not answer with A's."""

    canonicalised = _ready_document(
        api_client, content=multi_page_pdf("Bay 21", "Bay 22")
    )
    _canonicalize(api_client, canonicalised["id"])

    other = _ready_document(
        api_client, filename="altro-schema.pdf", content=single_page_pdf()
    )

    assert _page(api_client, other["id"], 2).status_code == 404


def test_a_page_read_discloses_no_storage_location(
    api_client: TestClient, db_session: Session
) -> None:
    document = _ready_document(api_client, content=single_page_pdf())
    _canonicalize(api_client, document["id"])

    stored = db_session.get(DocumentRecord, document["id"])
    body = _page(api_client, document["id"], 1).text

    assert stored.file_path not in body
    assert "file_path" not in body
    assert "storage_reference" not in body


def test_the_page_read_is_described_by_openapi(
    api_client: TestClient,
) -> None:
    schema = api_client.get("/openapi.json").json()
    path = schema["paths"][
        "/documents/{document_id}/canonical-representation"
        "/pages/{page_number}"
    ]

    assert "get" in path
    assert (
        path["get"]["responses"]["200"]["content"]["application/json"][
            "schema"
        ]["$ref"]
        == "#/components/schemas/CanonicalPdfPageRead"
    )


# --- Refusals -----------------------------------------------------------


def test_an_unknown_document_returns_404(api_client: TestClient) -> None:
    assert _canonicalize(api_client, 4321).status_code == 404


def test_a_document_no_ingestion_accepted_returns_409(
    api_client: TestClient,
) -> None:
    """A state conflict, not a malformed request: the document exists and
    the caller asked for something legitimate at the wrong time."""

    document = _upload(api_client)

    assert _canonicalize(api_client, document["id"]).status_code == 409


def test_an_unsupported_format_is_an_answer_not_an_error(
    api_client: TestClient,
) -> None:
    """`200` with a typed cause. The request was well-formed and
    canonicalisation answered it correctly - `422` keeps meaning exactly
    one thing across this codebase."""

    document = _ready_document(
        api_client,
        filename="layout.dwg",
        content=b"AC1027" + b"\x00" * 40,
        mime_type="image/vnd.dwg",
    )

    response = _canonicalize(api_client, document["id"])

    assert response.status_code == 200
    body = response.json()
    assert body["succeeded"] is False
    assert body["failure"]["code"] == "unsupported_format"
    assert body["representation"] is None


def test_an_encrypted_pdf_is_answered_with_its_typed_cause(
    api_client: TestClient,
) -> None:
    document = _ready_document(api_client, content=encrypted_pdf())

    response = _canonicalize(api_client, document["id"])

    assert response.status_code == 200
    assert response.json()["failure"]["code"] == "encrypted_document"


def test_a_corrupted_pdf_is_answered_with_its_typed_cause(
    api_client: TestClient,
) -> None:
    document = _ready_document(api_client, content=corrupted_pdf())

    response = _canonicalize(api_client, document["id"])

    assert response.status_code == 200
    assert response.json()["failure"]["code"] == "corrupted_document"


# --- The original document ------------------------------------------------


def test_canonicalising_never_touches_the_uploaded_file(
    api_client: TestClient, db_session: Session
) -> None:
    content = single_page_pdf("Rated voltage 145 kV")
    document = _ready_document(api_client, content=content)

    stored = db_session.get(DocumentRecord, document["id"])
    before = Path(stored.file_path).read_bytes()

    _canonicalize(api_client, document["id"])

    assert Path(stored.file_path).read_bytes() == before == content
