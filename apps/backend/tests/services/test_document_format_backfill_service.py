"""
Tests for the deterministic format backfill (Milestone 25.2).

The backfill exists because every document uploaded before this milestone
was stored as ``other``. These tests specify the two properties that make
it safe to run against production: it decides without writing, and it
never invents a format.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from app.infrastructure.document_identity.filesystem_document_content import (
    FilesystemDocumentContentAdapter,
)
from app.infrastructure.document_identity.sqlalchemy_document_format_registry import (  # noqa: E501
    SqlAlchemyDocumentFormatRegistry,
)
from app.models.document import Document as DocumentRecord
from app.models.document import DocumentCategory, DocumentFormat
from app.services.document_format_backfill_service import (
    BackfillAction,
    apply_format_backfill,
    plan_format_backfill,
)

PDF_CONTENT = b"%PDF-1.7 montante T2 single line diagram"
PNG_CONTENT = b"\x89PNG\r\n\x1a\n" + b"\x00" * 40


def _document(
    db: Session,
    tmp_path: Path,
    *,
    filename: str,
    content: bytes | None,
    file_format: DocumentFormat = DocumentFormat.OTHER,
) -> DocumentRecord:
    path = tmp_path / filename

    if content is not None:
        path.write_bytes(content)

    document = DocumentRecord(
        filename=filename,
        file_path=str(path),
        file_format=file_format,
        category=DocumentCategory.GENERAL_TECHNICAL,
        revision="00",
        project_name="Unknown",
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    return document


def _plan(db: Session):
    return plan_format_backfill(
        SqlAlchemyDocumentFormatRegistry(db),
        FilesystemDocumentContentAdapter(),
    )


# --- Planning writes nothing --------------------------------------------


def test_planning_reports_what_it_would_record_without_writing(
    db_session: Session, tmp_path: Path
) -> None:
    document = _document(
        db_session, tmp_path, filename="schema.pdf", content=PDF_CONTENT
    )

    plan = _plan(db_session)
    db_session.refresh(document)

    assert [decision.detected_format for decision in plan.actionable] == [
        "pdf"
    ]
    assert document.file_format is DocumentFormat.OTHER


def test_applying_records_the_classified_format(
    db_session: Session, tmp_path: Path
) -> None:
    document = _document(
        db_session, tmp_path, filename="schema.pdf", content=PDF_CONTENT
    )
    registry = SqlAlchemyDocumentFormatRegistry(db_session)

    applied = apply_format_backfill(registry, _plan(db_session))
    db_session.refresh(document)

    assert len(applied) == 1
    assert document.file_format is DocumentFormat.PDF


def test_applying_writes_only_the_format(
    db_session: Session, tmp_path: Path
) -> None:
    document = _document(
        db_session, tmp_path, filename="schema.pdf", content=PDF_CONTENT
    )
    uploaded_at = document.uploaded_at

    apply_format_backfill(
        SqlAlchemyDocumentFormatRegistry(db_session), _plan(db_session)
    )
    db_session.refresh(document)

    assert document.filename == "schema.pdf"
    assert document.category is DocumentCategory.GENERAL_TECHNICAL
    assert document.revision == "00"
    assert document.uploaded_at == uploaded_at


# --- It never invents a format ------------------------------------------


def test_a_document_whose_bytes_are_missing_is_left_alone(
    db_session: Session, tmp_path: Path
) -> None:
    """Its filename says ``.pdf``, but nobody can open it. Recording a
    format for a file that may no longer be there would be a guess."""

    document = _document(
        db_session, tmp_path, filename="vanished.pdf", content=None
    )

    plan = _plan(db_session)
    apply_format_backfill(SqlAlchemyDocumentFormatRegistry(db_session), plan)
    db_session.refresh(document)

    assert plan.decisions[0].action is BackfillAction.CONTENT_UNAVAILABLE
    assert document.file_format is DocumentFormat.OTHER


def test_an_empty_document_is_left_alone(
    db_session: Session, tmp_path: Path
) -> None:
    document = _document(
        db_session, tmp_path, filename="empty.pdf", content=b""
    )

    plan = _plan(db_session)

    assert plan.decisions[0].action is BackfillAction.CONTENT_UNAVAILABLE
    assert plan.actionable == ()


def test_an_unrecognisable_document_stays_unclassified(
    db_session: Session, tmp_path: Path
) -> None:
    document = _document(
        db_session,
        tmp_path,
        filename="notes.qzx",
        content=b"nothing identifiable",
    )

    plan = _plan(db_session)
    apply_format_backfill(SqlAlchemyDocumentFormatRegistry(db_session), plan)
    db_session.refresh(document)

    assert plan.decisions[0].action is BackfillAction.LEFT_UNCLASSIFIED
    assert document.file_format is DocumentFormat.OTHER


def test_an_unsigned_document_is_classified_by_its_extension(
    db_session: Session, tmp_path: Path
) -> None:
    """DWG files whose header this system does not recognise still carry
    an extension, and with nothing contradicting it that is enough. The
    provenance is recorded, so the weaker basis is visible."""

    document = _document(
        db_session,
        tmp_path,
        filename="drawing.dwg",
        content=b"unsigned bytes with no known header",
    )

    plan = _plan(db_session)
    apply_format_backfill(SqlAlchemyDocumentFormatRegistry(db_session), plan)
    db_session.refresh(document)

    assert plan.decisions[0].action is BackfillAction.RECLASSIFIED
    assert plan.decisions[0].decided_by == "filename_extension"
    assert document.file_format is DocumentFormat.DWG


def test_documents_already_classified_are_not_examined(
    db_session: Session, tmp_path: Path
) -> None:
    """Overwriting a format somebody may have set deliberately is not
    this command's job."""

    _document(
        db_session,
        tmp_path,
        filename="already.pdf",
        content=PNG_CONTENT,
        file_format=DocumentFormat.PDF,
    )

    plan = _plan(db_session)

    assert plan.decisions == ()


# --- Determinism and reporting ------------------------------------------


def test_the_plan_is_identical_across_runs(
    db_session: Session, tmp_path: Path
) -> None:
    _document(
        db_session, tmp_path, filename="schema.pdf", content=PDF_CONTENT
    )
    _document(db_session, tmp_path, filename="photo.png", content=PNG_CONTENT)
    _document(db_session, tmp_path, filename="gone.pdf", content=None)

    assert _plan(db_session) == _plan(db_session)


def test_documents_are_examined_in_ascending_id_order(
    db_session: Session, tmp_path: Path
) -> None:
    """Part of the contract, not an implementation detail: the report must
    read the same way twice over the same data."""

    first = _document(
        db_session, tmp_path, filename="a.pdf", content=PDF_CONTENT
    )
    second = _document(
        db_session, tmp_path, filename="b.png", content=PNG_CONTENT
    )

    plan = _plan(db_session)

    assert [decision.document_id for decision in plan.decisions] == [
        first.id,
        second.id,
    ]


def test_the_report_counts_every_action(
    db_session: Session, tmp_path: Path
) -> None:
    _document(
        db_session, tmp_path, filename="schema.pdf", content=PDF_CONTENT
    )
    _document(db_session, tmp_path, filename="gone.pdf", content=None)
    _document(
        db_session, tmp_path, filename="notes.qzx", content=b"unrecognised"
    )

    counts = _plan(db_session).count_by_action()

    assert counts["reclassified"] == 1
    assert counts["content_unavailable"] == 1
    assert counts["left_unclassified"] == 1


def test_applying_an_empty_plan_changes_nothing(
    db_session: Session, tmp_path: Path
) -> None:
    applied = apply_format_backfill(
        SqlAlchemyDocumentFormatRegistry(db_session), _plan(db_session)
    )

    assert applied == ()


def test_a_second_apply_finds_nothing_left_to_do(
    db_session: Session, tmp_path: Path
) -> None:
    """Idempotent: once a document is classified it is no longer among
    the unclassified rows the backfill examines."""

    _document(
        db_session, tmp_path, filename="schema.pdf", content=PDF_CONTENT
    )
    registry = SqlAlchemyDocumentFormatRegistry(db_session)

    apply_format_backfill(registry, _plan(db_session))

    assert _plan(db_session).decisions == ()


def test_an_image_is_classified_from_its_signature(
    db_session: Session, tmp_path: Path
) -> None:
    document = _document(
        db_session, tmp_path, filename="site_photo.png", content=PNG_CONTENT
    )

    apply_format_backfill(
        SqlAlchemyDocumentFormatRegistry(db_session), _plan(db_session)
    )
    db_session.refresh(document)

    assert document.file_format is DocumentFormat.IMAGE
