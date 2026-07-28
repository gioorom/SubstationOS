"""
Service tests for content identity and format classification during
ingestion (Milestone 25.2).

Against a real (in-memory) database through the real SQLAlchemy adapters
and real files in ``tmp_path``, so the checksum, the classified format and
the persisted columns are proved together - a fake repository could agree
with the domain and disagree with the schema.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.domain.document_ingestion.ingestion_models import (
    IngestionFailureCode,
    IngestionOutcome,
)
from app.domain.project.project_document_scope import DocumentScope
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
from app.models.document import Document as DocumentRecord
from app.models.document import DocumentCategory, DocumentFormat
from app.models.project import Project as ProjectRecord
from app.services import document_ingestion_service

NOW = datetime(2026, 1, 1, 9, 0, 0)
PDF_CONTENT = b"%PDF-1.7 montante T2 single line diagram"


def _project(db: Session, code: str = "ALPHA-001") -> ProjectRecord:
    project = ProjectRecord(
        name="Alpha Substation", code=code, customer="Acme Utilities"
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    return project


def _stored_document(
    db: Session,
    tmp_path: Path,
    *,
    filename: str = "montante-T2-schema.pdf",
    content: bytes | None = PDF_CONTENT,
    file_format: DocumentFormat = DocumentFormat.PDF,
    project: ProjectRecord | None = None,
) -> DocumentRecord:
    """Writes real bytes and registers a document pointing at them."""

    path = tmp_path / filename

    if content is not None:
        path.write_bytes(content)

    project = project or _project(db)

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


def _ingest(db: Session, document_id: int, *, with_content: bool = True):
    kwargs = {}

    if with_content:
        kwargs = {
            "content_port": FilesystemDocumentContentAdapter(),
            "storage_location_port": SqlAlchemyDocumentStorageLocation(db),
        }

    return document_ingestion_service.ingest_document(
        SqlAlchemyIngestionJobRepository(db),
        SqlAlchemyDocumentMetadataRepository(db),
        document_id=document_id,
        now=NOW,
        **kwargs,
    )


# --- The identity a successful ingestion records ------------------------


def test_ingestion_records_the_checksum_of_the_stored_bytes(
    db_session: Session, tmp_path: Path
) -> None:
    document = _stored_document(db_session, tmp_path)

    job = _ingest(db_session, document.id)

    assert job.outcome is IngestionOutcome.READY_FOR_EXTRACTION
    assert job.document.content.checksum == hashlib.sha256(
        PDF_CONTENT
    ).hexdigest()
    assert job.document.content.checksum_algorithm == "sha256"
    assert job.document.content.size_bytes == len(PDF_CONTENT)


def test_ingestion_records_the_format_decided_by_the_bytes(
    db_session: Session, tmp_path: Path
) -> None:
    document = _stored_document(db_session, tmp_path)

    job = _ingest(db_session, document.id)

    assert job.document.format.detected_format == "pdf"
    assert job.document.format.decided_by == "content_signature"


def test_the_bytes_overrule_a_document_filed_under_the_wrong_format(
    db_session: Session, tmp_path: Path
) -> None:
    """A PDF filed as a DWG is classified from its own leading bytes, and
    the disagreement is recorded rather than resolved silently."""

    document = _stored_document(
        db_session,
        tmp_path,
        filename="montante-T2-schema.dwg",
        file_format=DocumentFormat.DWG,
    )

    job = _ingest(db_session, document.id)

    assert job.document.format.detected_format == "pdf"
    assert job.document.format.stored_format == "dwg"
    assert job.document.format.matches_stored_format is False
    assert job.document.format.disagreeing_evidence


def test_ingestion_never_rewrites_the_document_row(
    db_session: Session, tmp_path: Path
) -> None:
    """Reading a document does not modify it. Correcting the stored
    format is the backfill command's job, which a human runs
    deliberately."""

    document = _stored_document(
        db_session,
        tmp_path,
        filename="montante-T2-schema.dwg",
        file_format=DocumentFormat.DWG,
    )

    _ingest(db_session, document.id)
    db_session.refresh(document)

    assert document.file_format is DocumentFormat.DWG


def test_an_unclassified_document_ingests_and_keeps_its_stored_format(
    db_session: Session, tmp_path: Path
) -> None:
    document = _stored_document(
        db_session, tmp_path, file_format=DocumentFormat.OTHER
    )

    job = _ingest(db_session, document.id)

    assert job.outcome is IngestionOutcome.READY_FOR_EXTRACTION
    assert job.document.format.detected_format == "pdf"
    assert job.document.document_format == "other"


# --- Content failures, end to end ---------------------------------------


def test_a_document_whose_bytes_are_missing_fails_as_content_not_found(
    db_session: Session, tmp_path: Path
) -> None:
    document = _stored_document(db_session, tmp_path, content=None)

    job = _ingest(db_session, document.id)

    assert job.outcome is IngestionOutcome.FAILED
    assert job.failure.code is IngestionFailureCode.CONTENT_NOT_FOUND


def test_a_zero_byte_document_fails_as_empty_content(
    db_session: Session, tmp_path: Path
) -> None:
    document = _stored_document(db_session, tmp_path, content=b"")

    job = _ingest(db_session, document.id)

    assert job.failure.code is IngestionFailureCode.EMPTY_CONTENT


def test_an_unrecognisable_document_fails_as_unknown_format(
    db_session: Session, tmp_path: Path
) -> None:
    document = _stored_document(
        db_session,
        tmp_path,
        filename="notes.qzx",
        content=b"nothing identifiable here",
        file_format=DocumentFormat.OTHER,
    )

    job = _ingest(db_session, document.id)

    assert job.failure.code is IngestionFailureCode.UNKNOWN_FORMAT


def test_a_failed_content_job_still_records_the_document_metadata(
    db_session: Session, tmp_path: Path
) -> None:
    document = _stored_document(db_session, tmp_path, content=None)

    job = _ingest(db_session, document.id)

    assert job.document.title == "montante-T2-schema.pdf"
    assert job.document.content is None


# --- Persistence --------------------------------------------------------


def test_the_identity_survives_a_round_trip_through_the_database(
    db_session: Session, tmp_path: Path
) -> None:
    document = _stored_document(db_session, tmp_path)
    job = _ingest(db_session, document.id)

    reread = SqlAlchemyIngestionJobRepository(db_session).get_by_id(job.id)

    assert reread.document.content == job.document.content
    assert reread.document.format == job.document.format


def test_disagreeing_evidence_survives_a_round_trip(
    db_session: Session, tmp_path: Path
) -> None:
    document = _stored_document(
        db_session,
        tmp_path,
        filename="montante-T2-schema.dwg",
        file_format=DocumentFormat.DWG,
    )
    job = _ingest(db_session, document.id)

    reread = SqlAlchemyIngestionJobRepository(db_session).get_by_id(job.id)

    assert (
        reread.document.format.disagreeing_evidence
        == job.document.format.disagreeing_evidence
    )


def test_a_job_recorded_without_content_reads_back_as_carrying_none(
    db_session: Session, tmp_path: Path
) -> None:
    """The shape every job written before Milestone 25.2 has. It reads
    back as a job that examined no content - which is the truth about it,
    not a gap to be filled in."""

    document = _stored_document(db_session, tmp_path)
    job = _ingest(db_session, document.id, with_content=False)

    reread = SqlAlchemyIngestionJobRepository(db_session).get_by_id(job.id)

    assert reread.outcome is IngestionOutcome.READY_FOR_EXTRACTION
    assert reread.document.content is None
    assert reread.document.format is None
    assert reread.document.title == "montante-T2-schema.pdf"


# --- Re-ingestion after the content changed ------------------------------


def test_re_ingesting_changed_content_records_the_new_checksum(
    db_session: Session, tmp_path: Path
) -> None:
    """A new job records the new bytes. The historical job is not
    touched, so "what did we ingest in January" stays answerable."""

    document = _stored_document(db_session, tmp_path)
    first = _ingest(db_session, document.id)

    Path(document.file_path).write_bytes(b"%PDF-1.7 revision 03, redrawn")
    second = _ingest(db_session, document.id)

    assert second.id != first.id
    assert second.document.content.checksum != first.document.content.checksum

    historical = SqlAlchemyIngestionJobRepository(db_session).get_by_id(
        first.id
    )

    assert historical.document.content.checksum == hashlib.sha256(
        PDF_CONTENT
    ).hexdigest()


def test_two_documents_with_identical_bytes_both_ingest_normally(
    db_session: Session, tmp_path: Path
) -> None:
    """Identity is not deduplication: the matching checksums are recorded
    and neither ingestion is refused, skipped or linked to the other."""

    project = _project(db_session)
    first_document = _stored_document(
        db_session, tmp_path, filename="schema_a.pdf", project=project
    )
    second_document = _stored_document(
        db_session, tmp_path, filename="schema_b.pdf", project=project
    )

    first = _ingest(db_session, first_document.id)
    second = _ingest(db_session, second_document.id)

    assert first.outcome is IngestionOutcome.READY_FOR_EXTRACTION
    assert second.outcome is IngestionOutcome.READY_FOR_EXTRACTION
    assert first.document.content.checksum == second.document.content.checksum
