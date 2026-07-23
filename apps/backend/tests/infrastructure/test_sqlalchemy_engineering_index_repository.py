from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy.orm import Session

from app.domain.engineering_index.engineering_index_entry_kind import (
    EngineeringIndexEntryKind,
)
from app.domain.engineering_index.engineering_index_exceptions import (
    DuplicateIndexEntryError,
)
from app.domain.engineering_index.engineering_index_factory import (
    EngineeringIndexEntryFactory,
)
from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocator,
    IndexEntryLocatorKind,
)
from app.infrastructure.engineering_index.sqlalchemy_engineering_index_repository import (
    SqlAlchemyEngineeringIndexRepository,
)
from app.models.document import Document as DocumentRecord
from app.models.project import Project as ProjectRecord

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)


def _persist_project_and_document(
    db_session: Session,
) -> tuple[ProjectRecord, DocumentRecord]:
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
    )
    db_session.add(document)
    db_session.commit()
    db_session.refresh(document)

    return project, document


def test_save_persists_a_new_entry_and_assigns_an_id(
    db_session: Session,
) -> None:
    _, document = _persist_project_and_document(db_session)
    repository = SqlAlchemyEngineeringIndexRepository(db_session)
    entry = EngineeringIndexEntryFactory.create(
        project_id=document.project_id,
        document_id=document.id,
        kind=EngineeringIndexEntryKind.EQUIPMENT,
        identifier="T1",
        created_at=CREATED_AT,
    )

    saved = repository.save(entry)

    assert saved.id is not None
    assert saved.identifier == "T1"


def test_get_by_id_returns_none_for_a_missing_entry(
    db_session: Session,
) -> None:
    repository = SqlAlchemyEngineeringIndexRepository(db_session)

    assert repository.get_by_id(999) is None


def test_list_by_document_returns_only_that_documents_entries(
    db_session: Session,
) -> None:
    _, document = _persist_project_and_document(db_session)
    repository = SqlAlchemyEngineeringIndexRepository(db_session)

    repository.save(
        EngineeringIndexEntryFactory.create(
            project_id=document.project_id,
            document_id=document.id,
            kind=EngineeringIndexEntryKind.EQUIPMENT,
            identifier="T1",
            created_at=CREATED_AT,
        )
    )
    repository.save(
        EngineeringIndexEntryFactory.create(
            project_id=document.project_id,
            document_id=document.id,
            kind=EngineeringIndexEntryKind.CABLE,
            identifier="W-152",
            created_at=CREATED_AT,
        )
    )

    entries = repository.list_by_document(document.id)

    assert {entry.identifier for entry in entries} == {"T1", "W-152"}


def test_list_by_project_filters_by_kind(
    db_session: Session,
) -> None:
    _, document = _persist_project_and_document(db_session)
    repository = SqlAlchemyEngineeringIndexRepository(db_session)

    repository.save(
        EngineeringIndexEntryFactory.create(
            project_id=document.project_id,
            document_id=document.id,
            kind=EngineeringIndexEntryKind.EQUIPMENT,
            identifier="T1",
            created_at=CREATED_AT,
        )
    )
    repository.save(
        EngineeringIndexEntryFactory.create(
            project_id=document.project_id,
            document_id=document.id,
            kind=EngineeringIndexEntryKind.CABLE,
            identifier="W-152",
            created_at=CREATED_AT,
        )
    )

    equipment_entries = repository.list_by_project(
        document.project_id,
        kind=EngineeringIndexEntryKind.EQUIPMENT,
    )

    assert [entry.identifier for entry in equipment_entries] == ["T1"]


def test_search_by_identifier_matches_case_insensitively_and_partially(
    db_session: Session,
) -> None:
    _, document = _persist_project_and_document(db_session)
    repository = SqlAlchemyEngineeringIndexRepository(db_session)

    repository.save(
        EngineeringIndexEntryFactory.create(
            project_id=document.project_id,
            document_id=document.id,
            kind=EngineeringIndexEntryKind.PROTECTION,
            identifier="52-T1",
            created_at=CREATED_AT,
        )
    )

    results = repository.search_by_identifier(document.project_id, "t1")

    assert len(results) == 1
    assert results[0].identifier == "52-T1"


def test_save_persists_and_reloads_a_non_page_locator(
    db_session: Session,
) -> None:
    _, document = _persist_project_and_document(db_session)
    repository = SqlAlchemyEngineeringIndexRepository(db_session)

    saved = repository.save(
        EngineeringIndexEntryFactory.create(
            project_id=document.project_id,
            document_id=document.id,
            kind=EngineeringIndexEntryKind.CABLE,
            identifier="W-152",
            created_at=CREATED_AT,
            locator=IndexEntryLocator(
                kind=IndexEntryLocatorKind.CELL_RANGE,
                value="B12:C15",
            ),
        )
    )

    reloaded = repository.get_by_id(saved.id)  # type: ignore[arg-type]

    assert reloaded is not None
    assert reloaded.locator_kind is IndexEntryLocatorKind.CELL_RANGE
    assert reloaded.locator_value == "B12:C15"
    assert reloaded.page is None


def test_save_rejects_a_duplicate_natural_key(
    db_session: Session,
) -> None:
    _, document = _persist_project_and_document(db_session)
    repository = SqlAlchemyEngineeringIndexRepository(db_session)

    repository.save(
        EngineeringIndexEntryFactory.create(
            project_id=document.project_id,
            document_id=document.id,
            kind=EngineeringIndexEntryKind.EQUIPMENT,
            identifier="T1",
            created_at=CREATED_AT,
            page=3,
        )
    )

    with pytest.raises(DuplicateIndexEntryError):
        repository.save(
            EngineeringIndexEntryFactory.create(
                project_id=document.project_id,
                document_id=document.id,
                kind=EngineeringIndexEntryKind.EQUIPMENT,
                identifier="T1",
                created_at=CREATED_AT,
                page=3,
            )
        )

    assert len(repository.list_by_document(document.id)) == 1


def test_replace_for_document_removes_previous_entries_and_inserts_new_ones(
    db_session: Session,
) -> None:
    _, document = _persist_project_and_document(db_session)
    repository = SqlAlchemyEngineeringIndexRepository(db_session)

    repository.save(
        EngineeringIndexEntryFactory.create(
            project_id=document.project_id,
            document_id=document.id,
            kind=EngineeringIndexEntryKind.EQUIPMENT,
            identifier="T1",
            created_at=CREATED_AT,
        )
    )

    replaced = repository.replace_for_document(
        document.id,
        document.project_id,
        [
            EngineeringIndexEntryFactory.create(
                project_id=document.project_id,
                document_id=document.id,
                kind=EngineeringIndexEntryKind.EQUIPMENT,
                identifier="T2",
                created_at=CREATED_AT,
            )
        ],
    )

    entries = repository.list_by_document(document.id)

    assert [entry.identifier for entry in replaced] == ["T2"]
    assert [entry.identifier for entry in entries] == ["T2"]


def test_replace_for_document_rolls_back_on_a_duplicate_within_the_batch(
    db_session: Session,
) -> None:
    _, document = _persist_project_and_document(db_session)
    repository = SqlAlchemyEngineeringIndexRepository(db_session)

    repository.save(
        EngineeringIndexEntryFactory.create(
            project_id=document.project_id,
            document_id=document.id,
            kind=EngineeringIndexEntryKind.EQUIPMENT,
            identifier="T1",
            created_at=CREATED_AT,
        )
    )

    # ``page`` (not ``None``) so the natural-key uniqueness constraint
    # can actually observe a collision - two NULL ``locator_value``s are
    # not equal under SQL uniqueness semantics, so an unlocated
    # duplicate would silently pass; a shared page number is a genuine
    # collision.
    duplicate_entries = [
        EngineeringIndexEntryFactory.create(
            project_id=document.project_id,
            document_id=document.id,
            kind=EngineeringIndexEntryKind.EQUIPMENT,
            identifier="T2",
            created_at=CREATED_AT,
            page=5,
        ),
        EngineeringIndexEntryFactory.create(
            project_id=document.project_id,
            document_id=document.id,
            kind=EngineeringIndexEntryKind.EQUIPMENT,
            identifier="T2",
            created_at=CREATED_AT,
            page=5,
        ),
    ]

    with pytest.raises(DuplicateIndexEntryError):
        repository.replace_for_document(
            document.id,
            document.project_id,
            duplicate_entries,
        )

    entries = repository.list_by_document(document.id)

    assert [entry.identifier for entry in entries] == ["T1"]


def test_delete_by_document_removes_every_entry(
    db_session: Session,
) -> None:
    _, document = _persist_project_and_document(db_session)
    repository = SqlAlchemyEngineeringIndexRepository(db_session)

    repository.save(
        EngineeringIndexEntryFactory.create(
            project_id=document.project_id,
            document_id=document.id,
            kind=EngineeringIndexEntryKind.EQUIPMENT,
            identifier="T1",
            created_at=CREATED_AT,
        )
    )

    repository.delete_by_document(document.id)

    assert repository.list_by_document(document.id) == []
