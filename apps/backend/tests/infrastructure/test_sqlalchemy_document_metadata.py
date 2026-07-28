"""Adapter tests for ``SqlAlchemyDocumentMetadataRepository`` (Milestone
23B.1), against a real (in-memory) database."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.project.project_document_scope import DocumentScope
from app.infrastructure.engineering_index.sqlalchemy_document_metadata import (
    SqlAlchemyDocumentMetadataRepository,
)
from app.models.document import (
    Document as DocumentRecord,
)
from app.models.document import (
    DocumentCategory,
    DocumentFormat,
)
from app.models.project import Project as ProjectRecord


def _project(db_session: Session) -> ProjectRecord:
    project = ProjectRecord(
        name="Alpha Substation",
        code="ALPHA-001",
        customer="Acme Utilities",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    return project


def _document(db_session: Session, project: ProjectRecord, **overrides):
    defaults = dict(
        filename="montante-T2-schema-funzionale.pdf",
        file_path="/tmp/montante-T2-schema-funzionale.pdf",
        project_id=project.id,
        project_name=project.name,
        file_format=DocumentFormat.PDF,
        category=DocumentCategory.FUNCTIONAL_SCHEMATIC,
        revision="02",
        scope=DocumentScope.PROJECT,
    )
    defaults.update(overrides)

    document = DocumentRecord(**defaults)
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    return document


def test_no_document_ids_reads_nothing(db_session: Session) -> None:
    repository = SqlAlchemyDocumentMetadataRepository(db_session)

    assert repository.find_many(()) == ()


def test_the_persisted_metadata_is_mapped_to_the_domain(
    db_session: Session,
) -> None:
    project = _project(db_session)
    document = _document(db_session, project)

    metadata = SqlAlchemyDocumentMetadataRepository(db_session).find_many(
        (document.id,)
    )

    assert len(metadata) == 1
    record = metadata[0]
    assert record.document_id == document.id
    assert record.project_id == project.id
    assert record.title == "montante-T2-schema-funzionale.pdf"
    assert record.document_format == "pdf"
    assert record.document_category == "functional_schematic"
    assert record.revision == "02"
    assert record.scope is DocumentScope.PROJECT


def test_several_documents_are_read_in_one_call(db_session: Session) -> None:
    project = _project(db_session)
    first = _document(db_session, project, filename="a.pdf")
    second = _document(db_session, project, filename="b.dwg")

    metadata = SqlAlchemyDocumentMetadataRepository(db_session).find_many(
        (second.id, first.id)
    )

    assert [record.document_id for record in metadata] == [
        first.id,
        second.id,
    ]


def test_a_missing_document_is_simply_absent(db_session: Session) -> None:
    """Never an error and never a placeholder: an Engineering Index entry
    may outlive the document row it points at (ADR-0002)."""

    project = _project(db_session)
    document = _document(db_session, project)

    metadata = SqlAlchemyDocumentMetadataRepository(db_session).find_many(
        (document.id, 9999)
    )

    assert [record.document_id for record in metadata] == [document.id]


def test_results_are_ordered_by_document_id(db_session: Session) -> None:
    project = _project(db_session)
    documents = [
        _document(db_session, project, filename=f"doc-{index}.pdf")
        for index in range(3)
    ]

    metadata = SqlAlchemyDocumentMetadataRepository(db_session).find_many(
        tuple(reversed([document.id for document in documents]))
    )

    ids = [record.document_id for record in metadata]
    assert ids == sorted(ids)
