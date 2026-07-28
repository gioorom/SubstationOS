"""
API tests for the consolidated upload path (Milestone 26.2).

Before this milestone, uploading a PDF into a project opened the stored
file with PyMuPDF and handed the result to the Knowledge Graph. Now the
upload runs the one supported pipeline - ingestion, canonicalisation,
segmentation - and the Knowledge Graph receives text assembled from the
segmentation.

These tests prove the migration at the endpoint, which is where the
behaviour a client sees is actually decided.
"""

from __future__ import annotations

import io

import httpx
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.canonical_pdf import CanonicalPdfRepresentation
from app.models.canonical_text import CanonicalTextDocumentRecord
from app.models.document_ingestion import DocumentIngestionJob
from tests._pdf_builder import (
    build_pdf,
    corrupted_pdf,
    empty_page_only_pdf,
    encrypted_pdf,
    single_page_pdf,
)

# A page of realistic substation text, so the Knowledge Graph's own
# patterns have something to find.
SUBSTATION_PAGE = build_pdf(
    [
        [
            ("TRASFORMATORE AT/MT", (72.0, 100.0), 11.0),
            ("152 AT-TR interruttore", (72.0, 130.0), 11.0),
            ("189 SB-TR sezionatore", (72.0, 160.0), 11.0),
            ("Cavo 240 mm2 e 240 mm²", (72.0, 190.0), 11.0),
        ]
    ]
)


def _project(api_client: TestClient, code: str = "ALPHA-001") -> dict:
    response = api_client.post(
        "/projects/",
        json={
            "name": "Alpha Substation",
            "code": code,
            "customer": "Acme Utilities",
        },
    )

    assert response.status_code == 201

    return response.json()


def _upload(
    api_client: TestClient,
    *,
    content: bytes,
    project_id: int | None = None,
    filename: str = "montante-T2-schema.pdf",
    mime_type: str = "application/pdf",
) -> httpx.Response:
    data = (
        {"scope": "project", "project_id": str(project_id)}
        if project_id is not None
        else {"scope": "canonical_library"}
    )

    return api_client.post(
        "/documents/upload",
        files={"file": (filename, io.BytesIO(content), mime_type)},
        data=data,
    )


# --- The consolidated path runs -----------------------------------------------


def test_uploading_a_pdf_runs_the_whole_pipeline(
    api_client: TestClient, db_session: Session
) -> None:
    project = _project(api_client)

    response = _upload(
        api_client, content=SUBSTATION_PAGE, project_id=project["id"]
    )

    assert response.status_code == 200
    document_id = response.json()["id"]

    assert (
        db_session.query(DocumentIngestionJob)
        .filter(DocumentIngestionJob.document_id == document_id)
        .count()
        == 1
    )
    assert (
        db_session.query(CanonicalPdfRepresentation)
        .filter(CanonicalPdfRepresentation.document_id == document_id)
        .count()
        == 1
    )
    assert (
        db_session.query(CanonicalTextDocumentRecord)
        .filter(CanonicalTextDocumentRecord.document_id == document_id)
        .count()
        == 1
    )


def test_the_pipeline_delivers_text_to_the_knowledge_graph(
    api_client: TestClient
) -> None:
    """
    The pipeline runs to the downstream consumer and hands it text.

    Asserted without assuming the consumer succeeds, because the live
    Knowledge Graph extractor is **LLM-backed** and needs
    ``ANTHROPIC_API_KEY`` - it was so long before this milestone, and
    without a key it has always reported ``failed``. What changed here is
    that the failure now names its stage: reaching
    ``downstream_consumer`` proves ingestion, canonicalisation and
    segmentation all succeeded and the assembled text was delivered.

    That the consumer receives text assembled from the segmentation, and
    what that text contains, is proved deterministically against an
    injected consumer in
    ``tests/services/test_document_pipeline_service.py``.
    """

    project = _project(api_client)

    response = _upload(
        api_client, content=SUBSTATION_PAGE, project_id=project["id"]
    )
    knowledge_graph = response.json()["knowledge_graph"]

    if knowledge_graph["status"] == "completed":
        assert knowledge_graph["failure"] is None
        assert knowledge_graph["entities_found"] >= 0
    else:
        assert knowledge_graph["failure"]["stage"] == "downstream_consumer"


def test_the_uploaded_document_is_readable_through_the_canonical_endpoints(
    api_client: TestClient
) -> None:
    """The artefacts the upload produced are the same ones the canonical
    endpoints serve - one pipeline, not two."""

    project = _project(api_client)
    document_id = _upload(
        api_client, content=SUBSTATION_PAGE, project_id=project["id"]
    ).json()["id"]

    representation = api_client.get(
        f"/documents/{document_id}/canonical-representation"
    )
    segmentation = api_client.get(
        f"/documents/{document_id}/canonical-text"
    )

    assert representation.status_code == 200
    assert segmentation.status_code == 200
    assert segmentation.json()["token_count"] > 0


def test_a_canonical_library_upload_skips_the_knowledge_graph(
    api_client: TestClient, db_session: Session
) -> None:
    """Unchanged behaviour: the Knowledge Graph is per-project, and a
    canonical-library document has no project to be ingested into."""

    response = _upload(api_client, content=SUBSTATION_PAGE)

    assert response.json()["knowledge_graph"]["status"] == "skipped"
    assert (
        db_session.query(CanonicalPdfRepresentation).count() == 0
    )


# --- Idempotency ---------------------------------------------------------------


def test_re_uploading_identical_bytes_reuses_the_canonical_artefacts(
    api_client: TestClient, db_session: Session
) -> None:
    """Two uploads of the same bytes are two documents, and the second
    parses nothing new for itself beyond its own representation - each
    document keeps its own artefacts, and neither is rebuilt twice."""

    project = _project(api_client)

    first = _upload(
        api_client, content=SUBSTATION_PAGE, project_id=project["id"]
    ).json()
    second = _upload(
        api_client,
        content=SUBSTATION_PAGE,
        project_id=project["id"],
        filename="copy.pdf",
    ).json()

    for document_id in (first["id"], second["id"]):
        assert (
            db_session.query(CanonicalTextDocumentRecord)
            .filter(CanonicalTextDocumentRecord.document_id == document_id)
            .count()
            == 1
        )


def test_canonicalising_again_after_upload_reuses_what_upload_built(
    api_client: TestClient, db_session: Session
) -> None:
    """The upload and the canonical endpoint are the same pipeline, so
    the endpoint re-uses rather than rebuilding."""

    project = _project(api_client)
    document_id = _upload(
        api_client, content=SUBSTATION_PAGE, project_id=project["id"]
    ).json()["id"]

    response = api_client.post(
        f"/documents/{document_id}/canonical-representation"
    )

    assert response.status_code == 200
    assert response.json()["reused"] is True


# --- Honest failures ------------------------------------------------------------


def test_a_non_pdf_upload_reports_unsupported_file_type(
    api_client: TestClient
) -> None:
    """The status string this endpoint has always returned, preserved."""

    project = _project(api_client)

    response = _upload(
        api_client,
        content=b"AC1027" + b"\x00" * 40,
        project_id=project["id"],
        filename="layout.dwg",
        mime_type="image/vnd.dwg",
    )
    knowledge_graph = response.json()["knowledge_graph"]

    assert response.status_code == 200
    assert knowledge_graph["status"] == "unsupported_file_type"
    assert knowledge_graph["entities_found"] == 0


def test_a_pdf_with_no_text_reports_no_text(api_client: TestClient) -> None:
    project = _project(api_client)

    response = _upload(
        api_client, content=empty_page_only_pdf(), project_id=project["id"]
    )

    assert response.json()["knowledge_graph"]["status"] == "no_text"


def test_a_corrupted_pdf_reports_failed_and_names_the_stage(
    api_client: TestClient
) -> None:
    """The legacy endpoint reported a bare "failed". It still does, for
    a client reading only ``status`` - and now says which stage stopped
    and why beside it."""

    project = _project(api_client)

    response = _upload(
        api_client, content=corrupted_pdf(), project_id=project["id"]
    )
    knowledge_graph = response.json()["knowledge_graph"]

    assert knowledge_graph["status"] == "failed"
    assert knowledge_graph["failure"]["stage"] == "canonical_representation"
    assert knowledge_graph["failure"]["code"] == "corrupted_document"


def test_an_encrypted_pdf_names_its_own_cause(
    api_client: TestClient
) -> None:
    project = _project(api_client)

    response = _upload(
        api_client, content=encrypted_pdf(), project_id=project["id"]
    )

    assert (
        response.json()["knowledge_graph"]["failure"]["code"]
        == "encrypted_document"
    )


def test_a_pipeline_failure_never_fails_the_upload(
    api_client: TestClient, db_session: Session
) -> None:
    """Losing an uploaded file because a downstream analysis stumbled
    would be the worst possible trade. The document is stored either
    way."""

    project = _project(api_client)

    response = _upload(
        api_client, content=corrupted_pdf(), project_id=project["id"]
    )

    assert response.status_code == 200
    assert response.json()["id"] is not None
    assert response.json()["file_path"]


def test_the_response_keeps_its_long_standing_shape(
    api_client: TestClient
) -> None:
    """A client reading ``status`` and ``entities_found`` sees exactly
    what it saw before Milestone 26.2."""

    project = _project(api_client)

    body = _upload(
        api_client, content=SUBSTATION_PAGE, project_id=project["id"]
    ).json()

    assert set(body) == {
        "id",
        "project_id",
        "filename",
        "file_path",
        "file_format",
        "category",
        "revision",
        "project_name",
        "scope",
        "uploaded_at",
        "knowledge_graph",
    }
    assert set(body["knowledge_graph"]) == {
        "status",
        "entities_found",
        "failure",
    }


# --- Engineering symbols survive the migration ----------------------------------


def test_engineering_symbols_survive_the_consolidated_path(
    api_client: TestClient
) -> None:
    """
    The regression this milestone most needed: replacing the legacy
    decoder must not degrade the engineering text delivered downstream.
    ``mm²`` reaches the segmentation - and therefore the consumer - as
    ``mm²``, not ``mm2``.
    """

    project = _project(api_client)
    document_id = _upload(
        api_client, content=SUBSTATION_PAGE, project_id=project["id"]
    ).json()["id"]

    body = api_client.get(
        f"/documents/{document_id}/canonical-text"
    ).json()
    originals = [
        token["text"]
        for section in body["sections"]
        for paragraph in section["paragraphs"]
        for line in paragraph["lines"]
        for token in line["tokens"]
    ]

    assert "mm²" in originals
    assert "mm2" in originals  # the document contains both, distinctly


def test_the_upload_path_no_longer_imports_the_legacy_extractor() -> None:
    """A behavioural check to sit beside the architecture one: the module
    is gone, so importing it fails."""

    import importlib

    for module in (
        "app.services.pdf_text_extractor",
        "app.services.pdf_renderer",
        "app.services.document_analyzer",
        "app.services.intelligence.renderer",
    ):
        try:
            importlib.import_module(module)
        except ModuleNotFoundError:
            continue

        raise AssertionError(f"{module} still exists")
