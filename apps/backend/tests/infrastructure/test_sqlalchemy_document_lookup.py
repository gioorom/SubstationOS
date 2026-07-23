from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.project.project_document_scope import DocumentScope
from app.domain.project.project_lifecycle import ProjectLifecycleState
from app.infrastructure.engineering_index.sqlalchemy_document_lookup import (
    SqlAlchemyDocumentLookup,
)
from app.models.document import Document as DocumentRecord
from app.models.project import Project as ProjectRecord


def test_find_returns_none_for_a_missing_document(
    db_session: Session,
) -> None:
    lookup = SqlAlchemyDocumentLookup(db_session)

    assert lookup.find(999) is None


def test_find_returns_the_owning_projects_scope_and_lifecycle_state(
    db_session: Session,
) -> None:
    project = ProjectRecord(
        name="Alpha Substation",
        code="ALPHA-001",
        customer="Acme Utilities",
    )
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    document = DocumentRecord(
        filename="functional-schematic.pdf",
        file_path="/tmp/functional-schematic.pdf",
        project_id=project.id,
        project_name=project.name,
        scope=DocumentScope.PROJECT,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    context = SqlAlchemyDocumentLookup(db_session).find(document.id)

    assert context is not None
    assert context.project_id == project.id
    assert context.scope is DocumentScope.PROJECT
    assert context.project_lifecycle_state is ProjectLifecycleState.DRAFT


def test_find_returns_a_none_project_for_a_canonical_library_document(
    db_session: Session,
) -> None:
    document = DocumentRecord(
        filename="vendor-manual.pdf",
        file_path="/tmp/vendor-manual.pdf",
        project_id=None,
        scope=DocumentScope.CANONICAL_LIBRARY,
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    context = SqlAlchemyDocumentLookup(db_session).find(document.id)

    assert context is not None
    assert context.project_id is None
    assert context.scope is DocumentScope.CANONICAL_LIBRARY
    assert context.project_lifecycle_state is None
