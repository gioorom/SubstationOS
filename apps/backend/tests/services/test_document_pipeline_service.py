"""
Tests for the consolidated document pipeline workflow (Milestone 26.2).

Against a real (in-memory) database, real adapters, the real parser and
real files, because the point of this workflow is that four services meet
correctly - a fake at any of those seams would prove nothing.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.domain.project.project_document_scope import DocumentScope
from app.infrastructure.canonical_pdf.pymupdf_parser import PyMuPdfParser
from app.infrastructure.canonical_pdf.sqlalchemy_canonical_representation_repository import (  # noqa: E501
    SqlAlchemyCanonicalRepresentationRepository,
)
from app.infrastructure.canonical_text.sqlalchemy_canonical_text_repository import (  # noqa: E501
    SqlAlchemyCanonicalTextRepository,
)
from app.infrastructure.document_identity.filesystem_document_content import (
    FilesystemDocumentContentAdapter,
)
from app.infrastructure.document_identity.sqlalchemy_document_storage_location import (  # noqa: E501
    SqlAlchemyDocumentStorageLocation,
)
from app.infrastructure.document_ingestion.sqlalchemy_ingestion_repository import (  # noqa: E501
    SqlAlchemyIngestionJobRepository,
)
from app.infrastructure.engineering_index.sqlalchemy_document_metadata import (
    SqlAlchemyDocumentMetadataRepository,
)
from app.models.canonical_pdf import CanonicalPdfRepresentation
from app.models.canonical_text import CanonicalTextDocumentRecord
from app.models.document import Document as DocumentRecord
from app.models.document import DocumentCategory, DocumentFormat
from app.services import document_pipeline_service
from app.services.document_pipeline_service import (
    PipelineFailureCode,
    PipelineStage,
)
from tests._pdf_builder import (
    build_pdf,
    corrupted_pdf,
    empty_page_only_pdf,
    encrypted_pdf,
    multi_page_pdf,
    single_page_pdf,
)

NOW = datetime(2026, 3, 1, 9, 0, 0)


def _document(
    db: Session,
    tmp_path: Path,
    *,
    content: bytes | None = None,
    filename: str = "montante-T2-schema.pdf",
    file_format: DocumentFormat = DocumentFormat.PDF,
) -> DocumentRecord:
    path = tmp_path / filename

    if content is not None:
        path.write_bytes(content)

    document = DocumentRecord(
        filename=filename,
        file_path=str(path),
        file_format=file_format,
        category=DocumentCategory.FUNCTIONAL_SCHEMATIC,
        revision="02",
        project_name="Alpha Substation",
        scope=DocumentScope.CANONICAL_LIBRARY,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def _run(db: Session, document_id: int, consumer=None):
    return document_pipeline_service.process_uploaded_document(
        document_id=document_id,
        ingestion_repository=SqlAlchemyIngestionJobRepository(db),
        document_metadata_port=SqlAlchemyDocumentMetadataRepository(db),
        content_port=FilesystemDocumentContentAdapter(),
        storage_location_port=SqlAlchemyDocumentStorageLocation(db),
        parser=PyMuPdfParser(),
        representation_repository=(
            SqlAlchemyCanonicalRepresentationRepository(db)
        ),
        text_repository=SqlAlchemyCanonicalTextRepository(db),
        now=NOW,
        consumer=consumer,
    )


# --- The consolidated path ---------------------------------------------------


def test_the_pipeline_runs_ingestion_canonicalisation_and_segmentation(
    db_session: Session, tmp_path: Path
) -> None:
    document = _document(
        db_session, tmp_path, content=single_page_pdf("Rated voltage 145 kV")
    )

    result = _run(db_session, document.id)

    assert result.succeeded
    assert result.stage_reached is PipelineStage.TEXT_ASSEMBLY
    assert (
        db_session.query(CanonicalPdfRepresentation)
        .filter(CanonicalPdfRepresentation.document_id == document.id)
        .count()
        == 1
    )
    assert (
        db_session.query(CanonicalTextDocumentRecord)
        .filter(CanonicalTextDocumentRecord.document_id == document.id)
        .count()
        == 1
    )


def test_the_consumer_receives_text_assembled_from_the_segmentation(
    db_session: Session, tmp_path: Path
) -> None:
    document = _document(
        db_session, tmp_path, content=single_page_pdf("Rated voltage 145 kV")
    )
    received: list[str] = []

    result = _run(db_session, document.id, consumer=received.append)

    assert result.succeeded
    assert result.stage_reached is PipelineStage.DOWNSTREAM_CONSUMER
    assert received == ["--- PAGINA 1 ---\nRated voltage 145 kV"]


def test_the_consumer_receives_a_string_and_nothing_else(
    db_session: Session, tmp_path: Path
) -> None:
    """No document id, no storage reference, no segmentation. A consumer
    that could reach any of those could decode the PDF itself."""

    document = _document(db_session, tmp_path, content=single_page_pdf())
    seen: list[tuple] = []

    def consumer(*args, **kwargs):
        seen.append((args, kwargs))

        return []

    _run(db_session, document.id, consumer=consumer)

    (args, kwargs) = seen[0]

    assert kwargs == {}
    assert len(args) == 1
    assert isinstance(args[0], str)


def test_the_consumers_return_value_is_carried_back(
    db_session: Session, tmp_path: Path
) -> None:
    document = _document(db_session, tmp_path, content=single_page_pdf())

    result = _run(
        db_session, document.id, consumer=lambda text: ["one", "two"]
    )

    assert result.consumer_result == ["one", "two"]


def test_a_multi_page_document_reaches_the_consumer_in_page_order(
    db_session: Session, tmp_path: Path
) -> None:
    document = _document(
        db_session,
        tmp_path,
        content=multi_page_pdf("Bay 21", "Bay 22", "Bay 23"),
    )
    received: list[str] = []

    _run(db_session, document.id, consumer=received.append)
    text = received[0]

    assert text.index("Bay 21") < text.index("Bay 22") < text.index("Bay 23")
    assert text.count("--- PAGINA") == 3


def test_the_original_pdf_is_never_modified(
    db_session: Session, tmp_path: Path
) -> None:
    content = single_page_pdf("Rated voltage 145 kV")
    document = _document(db_session, tmp_path, content=content)

    _run(db_session, document.id, consumer=lambda text: [])

    assert Path(document.file_path).read_bytes() == content


def test_the_pipeline_is_deterministic(
    db_session: Session, tmp_path: Path
) -> None:
    first = _document(
        db_session, tmp_path, content=single_page_pdf("145 kV"), filename="a.pdf"
    )
    second = _document(
        db_session, tmp_path, content=single_page_pdf("145 kV"), filename="b.pdf"
    )
    received: list[str] = []

    _run(db_session, first.id, consumer=received.append)
    _run(db_session, second.id, consumer=received.append)

    assert received[0] == received[1]


# --- Idempotency --------------------------------------------------------------


def test_re_running_reuses_the_representation_and_the_segmentation(
    db_session: Session, tmp_path: Path
) -> None:
    document = _document(db_session, tmp_path, content=single_page_pdf())

    first = _run(db_session, document.id, consumer=lambda text: [])
    second = _run(db_session, document.id, consumer=lambda text: [])

    assert first.reused_representation is False
    assert first.reused_segmentation is False
    assert second.reused_representation is True
    assert second.reused_segmentation is True


def test_re_running_creates_no_second_artefact(
    db_session: Session, tmp_path: Path
) -> None:
    document = _document(db_session, tmp_path, content=single_page_pdf())

    _run(db_session, document.id, consumer=lambda text: [])
    _run(db_session, document.id, consumer=lambda text: [])

    assert (
        db_session.query(CanonicalPdfRepresentation)
        .filter(CanonicalPdfRepresentation.document_id == document.id)
        .count()
        == 1
    )
    assert (
        db_session.query(CanonicalTextDocumentRecord)
        .filter(CanonicalTextDocumentRecord.document_id == document.id)
        .count()
        == 1
    )


def test_re_running_still_delivers_the_same_text(
    db_session: Session, tmp_path: Path
) -> None:
    """Re-use is not a shortcut past the consumer: the text is delivered
    again, identical, from the stored segmentation."""

    document = _document(
        db_session, tmp_path, content=single_page_pdf("145 kV")
    )
    received: list[str] = []

    _run(db_session, document.id, consumer=received.append)
    _run(db_session, document.id, consumer=received.append)

    assert received[0] == received[1]


# --- Honest failures -----------------------------------------------------------


def test_a_non_pdf_stops_at_canonicalisation_with_its_own_code(
    db_session: Session, tmp_path: Path
) -> None:
    document = _document(
        db_session,
        tmp_path,
        content=b"AC1027" + b"\x00" * 40,
        filename="layout.dwg",
        file_format=DocumentFormat.DWG,
    )

    result = _run(db_session, document.id, consumer=lambda text: [])

    assert result.succeeded is False
    assert result.stage_reached is PipelineStage.CANONICAL_REPRESENTATION
    assert result.failure.code == "unsupported_format"


def test_a_corrupted_pdf_stops_at_canonicalisation(
    db_session: Session, tmp_path: Path
) -> None:
    document = _document(db_session, tmp_path, content=corrupted_pdf())

    result = _run(db_session, document.id, consumer=lambda text: [])

    assert result.stage_reached is PipelineStage.CANONICAL_REPRESENTATION
    assert result.failure.code == "corrupted_document"


def test_an_encrypted_pdf_stops_at_canonicalisation(
    db_session: Session, tmp_path: Path
) -> None:
    document = _document(db_session, tmp_path, content=encrypted_pdf())

    result = _run(db_session, document.id, consumer=lambda text: [])

    assert result.failure.code == "encrypted_document"


def test_a_pdf_with_no_text_stops_before_the_consumer(
    db_session: Session, tmp_path: Path
) -> None:
    document = _document(db_session, tmp_path, content=empty_page_only_pdf())

    result = _run(db_session, document.id, consumer=lambda text: [])

    assert result.stage_reached is PipelineStage.CANONICAL_REPRESENTATION
    assert result.failure.code == "no_extractable_text"


def test_a_missing_file_stops_at_ingestion(
    db_session: Session, tmp_path: Path
) -> None:
    document = _document(db_session, tmp_path, content=None)

    result = _run(db_session, document.id, consumer=lambda text: [])

    assert result.stage_reached is PipelineStage.INGESTION
    assert result.failure.code == "content_not_found"


def test_a_failing_consumer_is_reported_as_a_downstream_failure(
    db_session: Session, tmp_path: Path
) -> None:
    """The stage is named and the cause is carried, rather than the whole
    upload being reported as one generic error."""

    def failing_consumer(text: str):
        raise RuntimeError("the graph is unavailable")

    document = _document(db_session, tmp_path, content=single_page_pdf())

    result = _run(db_session, document.id, consumer=failing_consumer)

    assert result.succeeded is False
    assert result.stage_reached is PipelineStage.DOWNSTREAM_CONSUMER
    assert result.failure.code == (
        PipelineFailureCode.DOWNSTREAM_CONSUMER_FAILURE.value
    )
    assert "the graph is unavailable" in result.failure.detail


def test_a_downstream_failure_leaves_the_artefacts_in_place(
    db_session: Session, tmp_path: Path
) -> None:
    """The representation and the segmentation are facts about the
    document. A consumer stumbling afterwards does not make them
    untrue."""

    document = _document(db_session, tmp_path, content=single_page_pdf())

    def failing_consumer(text: str):
        raise RuntimeError("boom")

    _run(db_session, document.id, consumer=failing_consumer)

    assert (
        db_session.query(CanonicalTextDocumentRecord)
        .filter(CanonicalTextDocumentRecord.document_id == document.id)
        .count()
        == 1
    )


def test_no_failure_is_collapsed_into_a_single_generic_code(
    db_session: Session, tmp_path: Path
) -> None:
    """Each condition reports the failing stage's own vocabulary."""

    cases = {
        "layout.dwg": (b"AC1027" + b"\x00" * 40, "unsupported_format"),
        "corrupt.pdf": (corrupted_pdf(), "corrupted_document"),
        "locked.pdf": (encrypted_pdf(), "encrypted_document"),
        "blank.pdf": (empty_page_only_pdf(), "no_extractable_text"),
    }
    observed = set()

    for filename, (content, _) in cases.items():
        document = _document(
            db_session,
            tmp_path,
            content=content,
            filename=filename,
            file_format=(
                DocumentFormat.DWG
                if filename.endswith(".dwg")
                else DocumentFormat.PDF
            ),
        )
        result = _run(db_session, document.id, consumer=lambda text: [])
        observed.add(result.failure.code)

    assert observed == {code for _, code in cases.values()}


def test_every_failure_names_its_stage_and_carries_a_message(
    db_session: Session, tmp_path: Path
) -> None:
    document = _document(db_session, tmp_path, content=corrupted_pdf())

    result = _run(db_session, document.id, consumer=lambda text: [])

    assert result.failure.stage is result.stage_reached
    assert result.failure.message


# --- Engineering symbols survive the whole pipeline ---------------------------


def test_engineering_symbols_reach_the_consumer_unchanged(
    db_session: Session, tmp_path: Path
) -> None:
    """
    The regression that matters most in this milestone: the canonical
    pipeline must not silently degrade the engineering text the previous
    decoder delivered. ``mm²`` must not arrive as ``mm2``.
    """

    source = "Cavo 240 mm2 - vedere anche 240 mm² e 3 m³"
    document = _document(
        db_session,
        tmp_path,
        content=build_pdf([[(source, (72.0, 100.0), 11.0)]]),
    )
    received: list[str] = []

    _run(db_session, document.id, consumer=received.append)

    assert "mm²" in received[0]
    assert "m³" in received[0]


def test_the_consumer_never_receives_normalized_text(
    db_session: Session, tmp_path: Path
) -> None:
    document = _document(
        db_session,
        tmp_path,
        content=build_pdf(
            [[("Tolleranza ±5 °C a 20 kV", (72.0, 100.0), 11.0)]]
        ),
    )
    received: list[str] = []

    _run(db_session, document.id, consumer=received.append)

    assert "±5" in received[0]
    assert "°C" in received[0]
    assert "kV" in received[0]
