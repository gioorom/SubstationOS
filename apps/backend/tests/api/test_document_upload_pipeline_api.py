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
import time
from decimal import Decimal

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.canonical_pdf import CanonicalPdfRepresentation
from app.models.canonical_spreadsheet import (
    CanonicalCellRecord,
    CanonicalWorkbookRecord,
)
from app.models.canonical_text import CanonicalTextDocumentRecord
from app.models.document_ingestion import DocumentIngestionJob
from tests.fixtures import synthetic_workbooks
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
    document_id = response.json()["document"]["id"]

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
    knowledge_graph = response.json()["analysis"]

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
    ).json()["document"]["id"]

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

    assert response.json()["analysis"]["status"] == "skipped"
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
    ).json()["document"]
    second = _upload(
        api_client,
        content=SUBSTATION_PAGE,
        project_id=project["id"],
        filename="copy.pdf",
    ).json()["document"]

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
    ).json()["document"]["id"]

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
    knowledge_graph = response.json()["analysis"]

    assert response.status_code == 200
    assert knowledge_graph["status"] == "unsupported_file_type"
    assert knowledge_graph["entities_found"] == 0


def test_a_pdf_with_no_text_reports_no_text(api_client: TestClient) -> None:
    project = _project(api_client)

    response = _upload(
        api_client, content=empty_page_only_pdf(), project_id=project["id"]
    )

    assert response.json()["analysis"]["status"] == "no_text"


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
    knowledge_graph = response.json()["analysis"]

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
        response.json()["analysis"]["failure"]["code"]
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
    assert response.json()["document"]["id"] is not None
    assert response.json()["document"]["content_available"] is True


def test_the_response_keeps_its_long_standing_shape(
    api_client: TestClient
) -> None:
    """The governed upload contract: a document, the scope it was
    accepted under, what the analysis made of it, and any warnings."""

    project = _project(api_client)

    body = _upload(
        api_client, content=SUBSTATION_PAGE, project_id=project["id"]
    ).json()

    assert set(body) == {"document", "scope", "analysis", "warnings"}

    # Milestone 30.1.3 replaced the ad-hoc dictionary with a declared
    # model. The analysis block kept its vocabulary exactly - a client
    # reading `status` and `entities_found` still sees what it saw before
    # Milestone 26.2 - and moved under a name that says what it is.
    assert set(body["analysis"]) == {
        "status",
        "entities_found",
        "failure",
    }

    # The storage location left the contract in the same milestone.
    assert "file_path" not in body["document"]


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
    ).json()["document"]["id"]

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


# --- The spreadsheet lineage, reached through the one workflow ------------------

#: What a browser sends for a `.xlsx`, and what the classifier is given.
XLSX_MIME = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)


def test_uploading_a_workbook_runs_the_spreadsheet_lineage(
    api_client: TestClient, db_session: Session
) -> None:
    """
    The milestone's whole claim, at the endpoint a user actually reaches.

    Before this, an uploaded workbook was stored and classified `xlsx`
    and then refused at canonicalisation with `unsupported_file_type`:
    the capability existed and nothing in the running application could
    reach it.
    """

    project = _project(api_client)

    response = _upload(
        api_client,
        content=synthetic_workbooks.simple_register(),
        project_id=project["id"],
        filename="elenco-cavi.xlsx",
        mime_type=XLSX_MIME,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["analysis"]["status"] == "completed"
    assert body["analysis"]["failure"] is None
    assert body["document"]["file_format"] == "xlsx"

    stored = db_session.query(CanonicalWorkbookRecord).one()
    assert stored.document_id == body["document"]["id"]
    assert stored.worksheet_count == 1


def test_a_workbook_upload_builds_no_pdf_artefact(
    api_client: TestClient, db_session: Session
) -> None:
    """
    The two source families fork at the root and never meet (ADR-0034
    §1). A workbook produces a workbook - not a representation, not a
    segmentation, and no text for a consumer that has none to read.
    """

    project = _project(api_client)

    _upload(
        api_client,
        content=synthetic_workbooks.multiple_sheets(),
        project_id=project["id"],
        filename="quadri.xlsx",
        mime_type=XLSX_MIME,
    )

    assert db_session.query(CanonicalWorkbookRecord).count() == 1
    assert db_session.query(CanonicalPdfRepresentation).count() == 0
    assert db_session.query(CanonicalTextDocumentRecord).count() == 0


def test_a_workbook_upload_is_still_ingested(
    api_client: TestClient, db_session: Session
) -> None:
    """Ingestion is the stage both lineages share, and the spreadsheet
    lineage runs it rather than skipping past it - a representation is
    trustworthy because the checks before it happened."""

    project = _project(api_client)

    _upload(
        api_client,
        content=synthetic_workbooks.simple_register(),
        project_id=project["id"],
        filename="elenco-cavi.xlsx",
        mime_type=XLSX_MIME,
    )

    job = db_session.query(DocumentIngestionJob).one()
    assert job.outcome.value == "ready_for_extraction"


def test_an_empty_workbook_reports_no_text_like_an_empty_pdf(
    api_client: TestClient
) -> None:
    """
    One observation, one answer, whichever lineage made it.

    A PDF with pages and no text span reports `no_text`. A workbook that
    opened and holds no populated cell is the same observation, and
    reporting it as the generic `failed` would give a client two answers
    to one question.
    """

    project = _project(api_client)

    response = _upload(
        api_client,
        content=synthetic_workbooks.empty_workbook(),
        project_id=project["id"],
        filename="vuoto.xlsx",
        mime_type=XLSX_MIME,
    )

    assert response.status_code == 200
    assert response.json()["analysis"]["status"] == "no_text"


def test_an_unreadable_workbook_never_fails_the_upload(
    api_client: TestClient, db_session: Session
) -> None:
    """The promise this endpoint makes, on the newly reachable lineage:
    the document is stored and recorded whatever the reader made of
    it."""

    project = _project(api_client)

    response = _upload(
        api_client,
        content=synthetic_workbooks.corrupted_package(),
        project_id=project["id"],
        filename="rotto.xlsx",
        mime_type=XLSX_MIME,
    )
    body = response.json()

    assert response.status_code == 200
    assert body["analysis"]["status"] == "failed"
    assert body["analysis"]["failure"]["stage"] == "canonical_workbook"
    assert body["document"]["id"] is not None
    assert db_session.query(CanonicalWorkbookRecord).count() == 0


def test_a_workbook_with_no_worksheet_reports_failed_not_no_text(
    api_client: TestClient
) -> None:
    """
    Two different observations, reported differently.

    A workbook whose worksheets hold no cell is the analogue of a PDF
    with pages and no text: `no_text`. A container with no worksheet at
    all is the analogue of a PDF with no pages, and `empty_document`
    reports `failed`. Collapsing the two would tell a client that a
    structurally broken file merely had nothing to say.
    """

    project = _project(api_client)

    response = _upload(
        api_client,
        content=synthetic_workbooks.workbook_without_worksheets(),
        project_id=project["id"],
        filename="senza-fogli.xlsx",
        mime_type=XLSX_MIME,
    )
    analysis = response.json()["analysis"]

    assert response.status_code == 200
    assert analysis["status"] == "failed"
    assert analysis["failure"]["code"] == "empty_workbook"


def test_an_ooxml_package_that_is_not_a_workbook_never_fails_the_upload(
    api_client: TestClient
) -> None:
    """
    A `.docx` renamed `.xlsx` is a mistake a user makes, not an attack.

    The library signals it with a bare `OSError`, which the reader's
    closed fault lists did not name - so it escaped the port's "never
    raises" contract and reached the request as a 500, for a document
    already stored and committed.
    """

    project = _project(api_client)

    response = _upload(
        api_client,
        content=synthetic_workbooks.ooxml_without_workbook_part(),
        project_id=project["id"],
        filename="relazione.xlsx",
        mime_type=XLSX_MIME,
    )
    analysis = response.json()["analysis"]

    assert response.status_code == 200
    assert analysis["status"] == "failed"
    assert analysis["failure"]["code"] == "malformed_package"


def test_a_workbook_claiming_an_enormous_row_is_refused_quickly(
    api_client: TestClient
) -> None:
    """
    A small upload must not be able to buy a large amount of work.

    The upload path is synchronous, so the cost of reading is paid
    inside the request. A file declaring one row far below the format's
    grid makes the reader walk every index in between - work no bound
    on *populated* rows can see, because nothing is populated there.
    """

    project = _project(api_client)

    started = time.perf_counter()
    response = _upload(
        api_client,
        content=synthetic_workbooks.row_far_beyond_the_grid(),
        project_id=project["id"],
        filename="lontano.xlsx",
        mime_type=XLSX_MIME,
    )
    elapsed = time.perf_counter() - started
    analysis = response.json()["analysis"]

    assert response.status_code == 200
    assert analysis["status"] == "failed"
    assert analysis["failure"]["code"] == "workbook_too_large"

    # Generous on purpose: this asserts a bound exists, not a speed.
    # Unbounded, the same upload took minutes.
    assert elapsed < 20.0


@pytest.mark.parametrize(
    "fixture", ["positive_infinity_number", "negative_infinity_number"]
)
def test_a_non_finite_number_is_refused_and_nothing_is_stored(
    api_client: TestClient, db_session: Session, fixture: str
) -> None:
    """
    A magnitude no finite number can hold must never become a stored
    representation.

    Persisting one is worse than refusing it: the write succeeds and
    every later read of that artefact raises, so the workbook becomes a
    row that exists and can never be read back.
    """

    project = _project(api_client)

    response = _upload(
        api_client,
        content=getattr(synthetic_workbooks, fixture)(),
        project_id=project["id"],
        filename="portate.xlsx",
        mime_type=XLSX_MIME,
    )
    analysis = response.json()["analysis"]

    assert response.status_code == 200
    assert analysis["status"] == "failed"
    assert analysis["failure"]["code"] == "unrepresentable_number"
    assert db_session.query(CanonicalWorkbookRecord).count() == 0


def test_a_large_recordable_number_is_still_canonicalised(
    api_client: TestClient, db_session: Session
) -> None:
    """The control. The rule above rejects a magnitude the column
    cannot hold; a large number inside it is recorded normally."""

    project = _project(api_client)

    response = _upload(
        api_client,
        content=synthetic_workbooks.large_finite_number(),
        project_id=project["id"],
        filename="grande.xlsx",
        mime_type=XLSX_MIME,
    )

    assert response.json()["analysis"]["status"] == "completed"

    cell = (
        db_session.query(CanonicalCellRecord)
        .filter(CanonicalCellRecord.literal_number.isnot(None))
        .one()
    )

    # The number that was written, not merely a number. Asserting only
    # that the upload completed would pass with the value corrupted.
    assert cell.literal_number == Decimal("1E+12")


def test_a_magnitude_beyond_the_column_is_refused_not_stored(
    api_client: TestClient, db_session: Session
) -> None:
    """
    Finite is not the same as recordable.

    A payload with no decimal point is parsed as a Python integer, which
    has no width - so a four-hundred-digit literal is perfectly finite
    and passes a finiteness check. The column then holds it as an
    infinity, the upload reports success, and the row can never be read
    again: an artefact that exists and is unreadable, which is worse
    than a refusal.
    """

    project = _project(api_client)

    response = _upload(
        api_client,
        content=synthetic_workbooks.magnitude_beyond_the_column(),
        project_id=project["id"],
        filename="enorme.xlsx",
        mime_type=XLSX_MIME,
    )
    analysis = response.json()["analysis"]

    assert response.status_code == 200
    assert analysis["status"] == "failed"
    assert analysis["failure"]["code"] == "unrepresentable_number"
    assert db_session.query(CanonicalWorkbookRecord).count() == 0


def test_a_missing_canonical_table_does_not_return_a_raw_500(
    api_client: TestClient, db_session: Session
) -> None:
    """
    Code deployed ahead of its migration.

    A realistic operational state, and one the upload endpoint must
    survive: it promises that a pipeline failure never fails the upload,
    and a schema that has not caught up is a pipeline failure like any
    other. The document is stored and committed before the pipeline
    runs, so a raw 500 here loses the caller's answer for a file the
    system has in fact kept.
    """

    project = _project(api_client)

    for table in (
        "canonical_cells",
        "canonical_rows",
        "canonical_worksheets",
        "canonical_workbooks",
    ):
        db_session.execute(text(f"DROP TABLE {table}"))

    db_session.commit()

    response = _upload(
        api_client,
        content=synthetic_workbooks.simple_register(),
        project_id=project["id"],
        filename="elenco-cavi.xlsx",
        mime_type=XLSX_MIME,
    )

    analysis = response.json()["analysis"]

    assert response.status_code == 200
    assert analysis["status"] == "failed"
    # The code and the stage, not merely "failed" - which
    # `representation_persistence_failure` would satisfy identically.
    assert analysis["failure"]["code"] == "storage_unavailable"
    assert analysis["failure"]["stage"] == "canonical_workbook"
    assert response.json()["document"]["id"] is not None


def test_a_missing_pdf_table_reports_the_pdf_lineages_stage(
    api_client: TestClient, db_session: Session
) -> None:
    """The same mapping on the other lineage.

    Without this the PDF entry of the lineage-to-stage table is never
    executed, and a wrong entry there would report a spreadsheet stage
    for a PDF."""

    project = _project(api_client)

    for table in ("canonical_pdf_spans", "canonical_pdf_blocks",
                  "canonical_pdf_pages", "canonical_pdf_representations"):
        db_session.execute(text(f"DROP TABLE {table}"))

    db_session.commit()

    response = _upload(
        api_client,
        content=single_page_pdf("Rated voltage 145 kV"),
        project_id=project["id"],
    )
    analysis = response.json()["analysis"]

    assert response.status_code == 200
    assert analysis["status"] == "failed"
    assert analysis["failure"]["code"] == "storage_unavailable"
    assert analysis["failure"]["stage"] == "canonical_representation"


def test_the_public_upload_failure_vocabulary_is_pinned() -> None:
    """
    Every code the *spreadsheet* lineage can put in
    `analysis.failure.code`, plus the endpoint's own.

    Not every code this endpoint can emit: the PDF lineage's
    canonicalisation, segmentation and ingestion vocabularies reach the
    same field and are pinned by their own contexts.

    `status` is a published contract with its own pin; `code` is not,
    because it carries each failing stage's own vocabulary and OpenAPI
    describes it only as a string. So a code added to a context enum
    reaches clients with nothing failing anywhere - which is how the
    frontend's transcription fell nine values behind.

    This does not prevent adding one. It makes adding one a deliberate
    act with a visible diff, next to the comment saying what else to
    update.
    """

    from app.domain.canonical_spreadsheet.canonical_spreadsheet_failures import (  # noqa: E501
        WorkbookCanonicalizationFailureCode,
    )
    from app.routers.documents import _STORAGE_UNAVAILABLE_CODE

    # Mirrored in apps/frontend/lib/contracts/pipeline.ts as
    # WORKBOOK_CANONICALIZATION_FAILURE_CODES and
    # STORAGE_UNAVAILABLE_CODE. Update both together.
    assert {code.value for code in WorkbookCanonicalizationFailureCode} == {
        "document_not_found",
        "unsupported_format",
        "content_not_found",
        "content_inaccessible",
        "empty_content",
        "not_ready_for_extraction",
        "encrypted_workbook",
        "malformed_package",
        "decompression_limit_exceeded",
        "workbook_too_large",
        "unrepresentable_number",
        "reader_failure",
        "empty_workbook",
        "no_populated_cell",
        "representation_persistence_failure",
    }
    assert _STORAGE_UNAVAILABLE_CODE == "storage_unavailable"


def test_a_shared_string_index_past_the_table_never_fails_the_upload(
    api_client: TestClient
) -> None:
    """
    The sibling of the OOXML-without-a-workbook case, and found the same
    way: by asking which faults the reader's closed lists do *not* name.

    A shared-string index is resolved as a list subscript, so this fails
    with `IndexError` - which neither fault list named, so it crossed the
    port's "never raises" contract and reached the request as a 500 for a
    document already stored and committed.
    """

    project = _project(api_client)

    response = _upload(
        api_client,
        content=synthetic_workbooks.shared_string_index_beyond_the_table(),
        project_id=project["id"],
        filename="troncato.xlsx",
        mime_type=XLSX_MIME,
    )
    analysis = response.json()["analysis"]

    assert response.status_code == 200
    assert analysis["status"] == "failed"
    assert analysis["failure"]["code"] == "malformed_package"
