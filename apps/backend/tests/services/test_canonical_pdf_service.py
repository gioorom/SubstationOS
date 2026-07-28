"""
Service tests for the Canonical PDF Representation (Milestone 26.1).

The whole governed flow, against a real (in-memory) database, the real
SQLAlchemy adapters, the real PyMuPDF parser and real files in
``tmp_path``. A fake repository could agree with the domain and disagree
with the schema; a fake parser could agree with both and disagree with
PDFs.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.domain.canonical_pdf.canonical_pdf_failures import (
    CanonicalizationFailureCode,
)
from app.domain.canonical_pdf.canonical_representation_repository import (
    CanonicalRepresentationRepository,
)
from app.domain.project.project_document_scope import DocumentScope
from app.infrastructure.canonical_pdf.pymupdf_parser import PyMuPdfParser
from app.infrastructure.canonical_pdf.sqlalchemy_canonical_representation_repository import (  # noqa: E501
    SqlAlchemyCanonicalRepresentationRepository,
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
from app.models.document import Document as DocumentRecord
from app.models.document import DocumentCategory, DocumentFormat
from app.models.project import Project as ProjectRecord
from app.services import canonical_pdf_service, document_ingestion_service
from tests._pdf_builder import (
    corrupted_pdf,
    empty_page_only_pdf,
    encrypted_pdf,
    multi_page_pdf,
    single_page_pdf,
)

NOW = datetime(2026, 2, 1, 9, 0, 0)


def _project(db: Session) -> ProjectRecord:
    """One project per test, reused - a test that registers two documents
    is about the documents, not about a second project."""

    existing = (
        db.query(ProjectRecord)
        .filter(ProjectRecord.code == "ALPHA-001")
        .first()
    )

    if existing is not None:
        return existing

    project = ProjectRecord(
        name="Alpha Substation", code="ALPHA-001", customer="Acme Utilities"
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    return project


def _document(
    db: Session,
    tmp_path: Path,
    *,
    content: bytes | None = None,
    filename: str = "montante-T2-schema.pdf",
    file_format: DocumentFormat = DocumentFormat.PDF,
) -> DocumentRecord:
    """Writes real bytes and registers a document pointing at them."""

    path = tmp_path / filename

    if content is not None:
        path.write_bytes(content)

    project = _project(db)

    document = DocumentRecord(
        filename=filename,
        file_path=str(path),
        project_id=project.id,
        project_name=project.name,
        file_format=file_format,
        category=DocumentCategory.FUNCTIONAL_SCHEMATIC,
        revision="02",
        scope=DocumentScope.PROJECT,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def _ingest(db: Session, document_id: int) -> None:
    """The governed predecessor: canonicalisation starts at
    READY_FOR_EXTRACTION."""

    document_ingestion_service.ingest_document(
        SqlAlchemyIngestionJobRepository(db),
        SqlAlchemyDocumentMetadataRepository(db),
        document_id=document_id,
        now=NOW,
        content_port=FilesystemDocumentContentAdapter(),
        storage_location_port=SqlAlchemyDocumentStorageLocation(db),
    )


def _canonicalize(
    db: Session,
    document_id: int,
    *,
    repository: CanonicalRepresentationRepository | None = None,
):
    return canonical_pdf_service.canonicalize_document(
        PyMuPdfParser(),
        repository or SqlAlchemyCanonicalRepresentationRepository(db),
        FilesystemDocumentContentAdapter(),
        SqlAlchemyDocumentStorageLocation(db),
        SqlAlchemyDocumentMetadataRepository(db),
        SqlAlchemyIngestionJobRepository(db),
        document_id=document_id,
    )


def _ready_document(
    db: Session, tmp_path: Path, content: bytes | None = None, **kwargs
) -> DocumentRecord:
    document = _document(
        db, tmp_path, content=content or single_page_pdf(), **kwargs
    )
    _ingest(db, document.id)

    return document


# --- The happy path -----------------------------------------------------


def test_a_ready_pdf_is_canonicalised(
    db_session: Session, tmp_path: Path
) -> None:
    document = _ready_document(
        db_session, tmp_path, single_page_pdf("Rated voltage 145 kV")
    )

    result = _canonicalize(db_session, document.id)

    assert result.succeeded
    assert result.reused is False
    assert result.representation.page_count == 1
    assert "Rated voltage 145 kV" in result.representation.pages[0].text


def test_the_representation_is_bound_to_the_bytes_it_came_from(
    db_session: Session, tmp_path: Path
) -> None:
    """The checksum ingestion established, carried onto the
    representation - which is what makes it explainable years later."""

    document = _ready_document(db_session, tmp_path)

    representation = _canonicalize(db_session, document.id).representation
    job = SqlAlchemyIngestionJobRepository(db_session).list_by_document(
        document.id
    )[0]

    assert representation.content_checksum == job.document.content.checksum
    assert representation.checksum_algorithm == "sha256"


def test_a_multi_page_pdf_persists_every_page(
    db_session: Session, tmp_path: Path
) -> None:
    document = _ready_document(
        db_session, tmp_path, multi_page_pdf("Bay 21", "Bay 22", "Bay 23")
    )

    _canonicalize(db_session, document.id)
    stored = canonical_pdf_service.get_representation(
        SqlAlchemyCanonicalRepresentationRepository(db_session), document.id
    )

    assert stored.page_count == 3
    assert [page.page_number for page in stored.pages] == [1, 2, 3]


# --- Persistence through the port ---------------------------------------


def test_the_representation_survives_a_round_trip_through_the_database(
    db_session: Session, tmp_path: Path
) -> None:
    """Rebuilt through the domain factory on the way out, so the stored
    value equals the parsed one exactly - text, geometry and style."""

    document = _ready_document(
        db_session, tmp_path, multi_page_pdf("Bay 21", "Bay 22")
    )

    built = _canonicalize(db_session, document.id).representation
    stored = SqlAlchemyCanonicalRepresentationRepository(
        db_session
    ).find_latest_for_document(document.id)

    assert stored == built


def test_bounding_boxes_and_style_survive_persistence(
    db_session: Session, tmp_path: Path
) -> None:
    document = _ready_document(
        db_session, tmp_path, single_page_pdf("145 kV", font_size=17.0)
    )

    _canonicalize(db_session, document.id)
    stored = canonical_pdf_service.get_representation(
        SqlAlchemyCanonicalRepresentationRepository(db_session), document.id
    )
    span = stored.pages[0].blocks[0].spans[0]

    assert span.style.font_size == 17.0
    assert span.bounding_box.x0 == 72.0
    assert span.bounding_box.width > 0


def test_a_document_never_canonicalised_has_no_representation(
    db_session: Session, tmp_path: Path
) -> None:
    """``None``, not an empty representation: most documents have not
    been canonicalised, and an empty one would be indistinguishable from
    a document that genuinely says nothing."""

    document = _ready_document(db_session, tmp_path)

    assert (
        canonical_pdf_service.get_representation(
            SqlAlchemyCanonicalRepresentationRepository(db_session),
            document.id,
        )
        is None
    )


# --- The original document is never touched ------------------------------


def test_the_original_pdf_is_never_modified(
    db_session: Session, tmp_path: Path
) -> None:
    """The uploaded PDF is authoritative. This system describes it; it
    does not edit it."""

    content = single_page_pdf("Rated voltage 145 kV")
    document = _ready_document(db_session, tmp_path, content)
    path = Path(document.file_path)
    before = path.read_bytes()

    _canonicalize(db_session, document.id)

    assert path.read_bytes() == before
    assert path.read_bytes() == content


def test_the_document_row_is_never_modified(
    db_session: Session, tmp_path: Path
) -> None:
    document = _ready_document(db_session, tmp_path)
    filename, file_path = document.filename, document.file_path
    file_format, uploaded_at = document.file_format, document.uploaded_at

    _canonicalize(db_session, document.id)
    db_session.refresh(document)

    assert document.filename == filename
    assert document.file_path == file_path
    assert document.file_format is file_format
    assert document.uploaded_at == uploaded_at


# --- Idempotency ---------------------------------------------------------


def test_re_running_over_identical_bytes_reuses_the_representation(
    db_session: Session, tmp_path: Path
) -> None:
    document = _ready_document(db_session, tmp_path)

    first = _canonicalize(db_session, document.id)
    second = _canonicalize(db_session, document.id)

    assert first.reused is False
    assert second.reused is True
    assert second.representation == first.representation


def test_re_running_creates_no_second_row(
    db_session: Session, tmp_path: Path
) -> None:
    document = _ready_document(db_session, tmp_path)

    _canonicalize(db_session, document.id)
    _canonicalize(db_session, document.id)
    _canonicalize(db_session, document.id)

    stored = (
        db_session.query(CanonicalPdfRepresentation)
        .filter(CanonicalPdfRepresentation.document_id == document.id)
        .all()
    )

    assert len(stored) == 1


def test_changed_bytes_produce_a_new_representation(
    db_session: Session, tmp_path: Path
) -> None:
    document = _ready_document(
        db_session, tmp_path, single_page_pdf("Revision 02")
    )
    first = _canonicalize(db_session, document.id).representation

    Path(document.file_path).write_bytes(single_page_pdf("Revision 03"))
    _ingest(db_session, document.id)
    second = _canonicalize(db_session, document.id)

    assert second.reused is False
    assert second.representation.content_checksum != first.content_checksum
    assert "Revision 03" in second.representation.pages[0].text


def test_the_historical_representation_stays_readable(
    db_session: Session, tmp_path: Path
) -> None:
    """A conclusion drawn from last year's revision must remain
    explainable, so the old representation is kept beside the new one -
    never overwritten."""

    document = _ready_document(
        db_session, tmp_path, single_page_pdf("Revision 02")
    )
    first = _canonicalize(db_session, document.id).representation

    Path(document.file_path).write_bytes(single_page_pdf("Revision 03"))
    _ingest(db_session, document.id)
    _canonicalize(db_session, document.id)

    repository = SqlAlchemyCanonicalRepresentationRepository(db_session)
    historical = repository.find_for_content(
        document.id, first.content_checksum
    )

    assert historical == first
    assert "Revision 02" in historical.pages[0].text


def test_the_latest_representation_is_the_one_callers_read(
    db_session: Session, tmp_path: Path
) -> None:
    document = _ready_document(
        db_session, tmp_path, single_page_pdf("Revision 02")
    )
    _canonicalize(db_session, document.id)

    Path(document.file_path).write_bytes(single_page_pdf("Revision 03"))
    _ingest(db_session, document.id)
    _canonicalize(db_session, document.id)

    current = canonical_pdf_service.get_representation(
        SqlAlchemyCanonicalRepresentationRepository(db_session), document.id
    )

    assert "Revision 03" in current.pages[0].text


# --- Typed failures ------------------------------------------------------


def test_a_missing_document_fails_with_document_not_found(
    db_session: Session,
) -> None:
    result = _canonicalize(db_session, 4321)

    assert result.succeeded is False
    assert result.failure.code is (
        CanonicalizationFailureCode.DOCUMENT_NOT_FOUND
    )


def test_a_non_pdf_document_fails_with_unsupported_format(
    db_session: Session, tmp_path: Path
) -> None:
    """A drawing is not badly-formed text. Representing it as text would
    put nonsense into the artefact every future extraction trusts."""

    document = _document(
        db_session,
        tmp_path,
        content=b"AC1027" + b"\x00" * 40,
        filename="layout.dwg",
        file_format=DocumentFormat.DWG,
    )
    _ingest(db_session, document.id)

    result = _canonicalize(db_session, document.id)

    assert result.failure.code is (
        CanonicalizationFailureCode.UNSUPPORTED_FORMAT
    )


def test_a_document_no_ingestion_accepted_is_refused(
    db_session: Session, tmp_path: Path
) -> None:
    """Canonicalisation is the step after ingestion. Parsing without it
    would be a second, quieter path to the same artefact."""

    document = _document(db_session, tmp_path, content=single_page_pdf())

    result = _canonicalize(db_session, document.id)

    assert result.failure.code is (
        CanonicalizationFailureCode.NOT_READY_FOR_EXTRACTION
    )


def test_a_document_whose_bytes_vanished_fails_with_content_not_found(
    db_session: Session, tmp_path: Path
) -> None:
    document = _ready_document(db_session, tmp_path)
    Path(document.file_path).unlink()

    result = _canonicalize(db_session, document.id)

    assert result.failure.code is (
        CanonicalizationFailureCode.CONTENT_NOT_FOUND
    )


def test_an_encrypted_pdf_fails_with_encrypted_document(
    db_session: Session, tmp_path: Path
) -> None:
    document = _ready_document(db_session, tmp_path, encrypted_pdf())

    result = _canonicalize(db_session, document.id)

    assert result.failure.code is (
        CanonicalizationFailureCode.ENCRYPTED_DOCUMENT
    )


def test_a_corrupted_pdf_fails_with_corrupted_document(
    db_session: Session, tmp_path: Path
) -> None:
    document = _ready_document(db_session, tmp_path, corrupted_pdf())

    result = _canonicalize(db_session, document.id)

    assert result.failure.code is (
        CanonicalizationFailureCode.CORRUPTED_DOCUMENT
    )


def test_a_pdf_with_no_extractable_text_is_not_persisted(
    db_session: Session, tmp_path: Path
) -> None:
    """Persisting it would give every future extractor a document that
    appears to say nothing - indistinguishable from one that genuinely
    does. It names the observation and stops; it does not claim the
    document is scanned."""

    document = _ready_document(db_session, tmp_path, empty_page_only_pdf())

    result = _canonicalize(db_session, document.id)

    assert result.failure.code is (
        CanonicalizationFailureCode.NO_EXTRACTABLE_TEXT
    )
    assert (
        db_session.query(CanonicalPdfRepresentation)
        .filter(CanonicalPdfRepresentation.document_id == document.id)
        .count()
        == 0
    )


def test_no_failure_persists_a_partial_representation(
    db_session: Session, tmp_path: Path
) -> None:
    """A half-written representation would be trusted as a whole one."""

    for content in (encrypted_pdf(), corrupted_pdf(), empty_page_only_pdf()):
        document = _ready_document(db_session, tmp_path, content)

        _canonicalize(db_session, document.id)

        assert (
            db_session.query(CanonicalPdfRepresentation)
            .filter(CanonicalPdfRepresentation.document_id == document.id)
            .count()
            == 0
        )


def test_a_storage_failure_is_reported_as_a_persistence_failure(
    db_session: Session, tmp_path: Path
) -> None:
    """The representation was built and could not be stored - one honest
    answer, rather than an adapter exception crossing the boundary."""

    class FailingRepository(CanonicalRepresentationRepository):
        def save(self, representation):
            raise RuntimeError("the disk is full")

        def find_for_content(self, document_id, content_checksum):
            return None

        def find_latest_for_document(self, document_id):
            return None

    document = _ready_document(db_session, tmp_path)

    result = _canonicalize(
        db_session, document.id, repository=FailingRepository()
    )

    assert result.failure.code is (
        CanonicalizationFailureCode.REPRESENTATION_PERSISTENCE_FAILURE
    )
    assert "the disk is full" in result.failure.detail


def test_every_failure_carries_a_message(
    db_session: Session, tmp_path: Path
) -> None:
    document = _ready_document(db_session, tmp_path, corrupted_pdf())

    result = _canonicalize(db_session, document.id)

    assert result.failure.message
    assert result.representation is None


# --- Determinism end to end ----------------------------------------------


def test_canonicalising_two_documents_with_identical_bytes_agrees(
    db_session: Session, tmp_path: Path
) -> None:
    """Two separate documents, the same bytes: the representations differ
    only by which document they belong to. Nothing about the parse
    depends on the filing."""

    content = single_page_pdf("Rated voltage 145 kV")
    first = _ready_document(db_session, tmp_path, content, filename="a.pdf")
    second = _ready_document(db_session, tmp_path, content, filename="b.pdf")

    first_result = _canonicalize(db_session, first.id)
    second_result = _canonicalize(db_session, second.id)

    assert (
        first_result.representation.content_checksum
        == second_result.representation.content_checksum
    )
    assert (
        first_result.representation.pages
        == second_result.representation.pages
    )


@pytest.mark.parametrize("run", [1, 2, 3])
def test_the_flow_is_reproducible_across_runs(
    db_session: Session, tmp_path: Path, run: int
) -> None:
    document = _ready_document(
        db_session, tmp_path, single_page_pdf("Rated voltage 145 kV")
    )

    representation = _canonicalize(db_session, document.id).representation

    assert representation.page_count == 1
    assert representation.pages[0].blocks[0].spans[0].text == (
        "Rated voltage 145 kV"
    )
