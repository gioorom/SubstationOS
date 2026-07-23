from __future__ import annotations

from dataclasses import replace
from datetime import datetime

import pytest

from app.domain.engineering_index.document_lookup import (
    DocumentIndexContext,
    DocumentLookupPort,
)
from app.domain.engineering_index.engineering_index_entry_kind import (
    EngineeringIndexEntryKind,
)
from app.domain.engineering_index.engineering_index_exceptions import (
    DocumentNotIndexableError,
    IndexedDocumentNotFoundError,
    IndexEntryNotFoundError,
    InvalidIndexEntryIdentifierError,
    ProjectNotIndexableError,
)
from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocator,
    IndexEntryLocatorKind,
)
from app.domain.engineering_index.engineering_index_models import IndexEntry
from app.domain.engineering_index.engineering_index_repository import (
    EngineeringIndexRepository,
)
from app.domain.project.project_document_scope import DocumentScope
from app.domain.project.project_lifecycle import ProjectLifecycleState
from app.services import engineering_index_service

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)


class FakeEngineeringIndexRepository(EngineeringIndexRepository):
    def __init__(self) -> None:
        self._entries: dict[int, IndexEntry] = {}
        self._next_id = 1

    def save(self, entry: IndexEntry) -> IndexEntry:
        if entry.id is None:
            entry = replace(entry, id=self._next_id)
            self._next_id += 1

        self._entries[entry.id] = entry  # type: ignore[index]

        return entry

    def get_by_id(self, entry_id: int) -> IndexEntry | None:
        return self._entries.get(entry_id)

    def list_by_document(self, document_id: int) -> list[IndexEntry]:
        return [
            entry
            for entry in self._entries.values()
            if entry.document_id == document_id
        ]

    def list_by_project(
        self,
        project_id: int,
        *,
        kind: EngineeringIndexEntryKind | None = None,
    ) -> list[IndexEntry]:
        return [
            entry
            for entry in self._entries.values()
            if entry.project_id == project_id
            and (kind is None or entry.kind is kind)
        ]

    def search_by_identifier(
        self,
        project_id: int,
        identifier: str,
    ) -> list[IndexEntry]:
        return [
            entry
            for entry in self._entries.values()
            if entry.project_id == project_id
            and identifier.lower() in entry.identifier.lower()
        ]

    def replace_for_document(
        self,
        document_id: int,
        project_id: int,
        entries: list[IndexEntry],
    ) -> list[IndexEntry]:
        for entry_id, entry in list(self._entries.items()):
            if entry.document_id == document_id:
                del self._entries[entry_id]

        return [self.save(entry) for entry in entries]

    def delete_by_document(self, document_id: int) -> None:
        for entry_id, entry in list(self._entries.items()):
            if entry.document_id == document_id:
                del self._entries[entry_id]


class FakeDocumentLookup(DocumentLookupPort):
    def __init__(self) -> None:
        self._documents: dict[int, DocumentIndexContext] = {}

    def register(self, context: DocumentIndexContext) -> None:
        self._documents[context.document_id] = context

    def find(self, document_id: int) -> DocumentIndexContext | None:
        return self._documents.get(document_id)


@pytest.fixture()
def repository() -> FakeEngineeringIndexRepository:
    return FakeEngineeringIndexRepository()


@pytest.fixture()
def document_lookup() -> FakeDocumentLookup:
    lookup = FakeDocumentLookup()
    lookup.register(
        DocumentIndexContext(
            document_id=1,
            project_id=10,
            scope=DocumentScope.PROJECT,
            project_lifecycle_state=ProjectLifecycleState.ACTIVE,
        )
    )
    lookup.register(
        DocumentIndexContext(
            document_id=2,
            project_id=None,
            scope=DocumentScope.CANONICAL_LIBRARY,
            project_lifecycle_state=None,
        )
    )
    lookup.register(
        DocumentIndexContext(
            document_id=3,
            project_id=20,
            scope=DocumentScope.PROJECT,
            project_lifecycle_state=ProjectLifecycleState.ARCHIVED,
        )
    )
    lookup.register(
        DocumentIndexContext(
            document_id=4,
            project_id=20,
            scope=DocumentScope.PROJECT,
            project_lifecycle_state=ProjectLifecycleState.ACTIVE,
        )
    )
    lookup.register(
        DocumentIndexContext(
            document_id=5,
            project_id=10,
            scope=DocumentScope.PROJECT,
            project_lifecycle_state=ProjectLifecycleState.ACTIVE,
        )
    )

    return lookup


def test_register_index_entry_succeeds_for_a_project_scoped_document(
    repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    entry = engineering_index_service.register_index_entry(
        repository,
        document_lookup,
        document_id=1,
        kind=EngineeringIndexEntryKind.EQUIPMENT,
        identifier="T1",
        now=CREATED_AT,
    )

    assert entry.id is not None
    assert entry.project_id == 10


def test_register_index_entry_raises_for_an_unknown_document(
    repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    with pytest.raises(IndexedDocumentNotFoundError):
        engineering_index_service.register_index_entry(
            repository,
            document_lookup,
            document_id=999,
            kind=EngineeringIndexEntryKind.EQUIPMENT,
            identifier="T1",
            now=CREATED_AT,
        )


def test_register_index_entry_raises_for_a_canonical_library_document(
    repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    with pytest.raises(DocumentNotIndexableError):
        engineering_index_service.register_index_entry(
            repository,
            document_lookup,
            document_id=2,
            kind=EngineeringIndexEntryKind.EQUIPMENT,
            identifier="T1",
            now=CREATED_AT,
        )


def test_register_index_entry_raises_for_an_archived_project(
    repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    with pytest.raises(ProjectNotIndexableError):
        engineering_index_service.register_index_entry(
            repository,
            document_lookup,
            document_id=3,
            kind=EngineeringIndexEntryKind.EQUIPMENT,
            identifier="T1",
            now=CREATED_AT,
        )


def test_register_index_entries_registers_all_mentions_for_a_document(
    repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    entries = engineering_index_service.register_index_entries(
        repository,
        document_lookup,
        document_id=1,
        mentions=[
            {"kind": EngineeringIndexEntryKind.EQUIPMENT, "identifier": "T1"},
            {"kind": EngineeringIndexEntryKind.CABLE, "identifier": "W-152"},
        ],
        now=CREATED_AT,
    )

    assert [entry.identifier for entry in entries] == ["T1", "W-152"]
    assert all(entry.project_id == 10 for entry in entries)


def test_register_index_entries_raises_before_persisting_any_entry(
    repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    with pytest.raises(DocumentNotIndexableError):
        engineering_index_service.register_index_entries(
            repository,
            document_lookup,
            document_id=2,
            mentions=[
                {
                    "kind": EngineeringIndexEntryKind.EQUIPMENT,
                    "identifier": "T1",
                },
            ],
            now=CREATED_AT,
        )

    assert repository.list_by_document(2) == []


def test_get_index_entry_raises_for_an_unknown_entry(
    repository: FakeEngineeringIndexRepository,
) -> None:
    with pytest.raises(IndexEntryNotFoundError):
        engineering_index_service.get_index_entry(repository, 999)


def test_list_index_entries_for_document(
    repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    engineering_index_service.register_index_entry(
        repository,
        document_lookup,
        document_id=1,
        kind=EngineeringIndexEntryKind.EQUIPMENT,
        identifier="T1",
        now=CREATED_AT,
    )

    entries = engineering_index_service.list_index_entries_for_document(
        repository,
        1,
    )

    assert len(entries) == 1


def test_search_index_by_identifier(
    repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    engineering_index_service.register_index_entry(
        repository,
        document_lookup,
        document_id=1,
        kind=EngineeringIndexEntryKind.PROTECTION,
        identifier="52-T1",
        now=CREATED_AT,
    )

    results = engineering_index_service.search_index_by_identifier(
        repository,
        10,
        "t1",
    )

    assert len(results) == 1


def test_replace_document_index_is_idempotent_for_identical_input(
    repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    mentions = [
        {"kind": EngineeringIndexEntryKind.EQUIPMENT, "identifier": "T1"},
        {"kind": EngineeringIndexEntryKind.CABLE, "identifier": "W-152"},
    ]

    engineering_index_service.replace_document_index(
        repository,
        document_lookup,
        document_id=1,
        mentions=mentions,
        now=CREATED_AT,
    )
    engineering_index_service.replace_document_index(
        repository,
        document_lookup,
        document_id=1,
        mentions=mentions,
        now=CREATED_AT,
    )

    entries = repository.list_by_document(1)

    assert sorted(entry.identifier for entry in entries) == [
        "T1",
        "W-152",
    ]


def test_replace_document_index_swaps_in_changed_data(
    repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    engineering_index_service.replace_document_index(
        repository,
        document_lookup,
        document_id=1,
        mentions=[
            {"kind": EngineeringIndexEntryKind.EQUIPMENT, "identifier": "T1"},
        ],
        now=CREATED_AT,
    )

    engineering_index_service.replace_document_index(
        repository,
        document_lookup,
        document_id=1,
        mentions=[
            {"kind": EngineeringIndexEntryKind.EQUIPMENT, "identifier": "T2"},
        ],
        now=CREATED_AT,
    )

    entries = repository.list_by_document(1)

    assert [entry.identifier for entry in entries] == ["T2"]


def test_replace_document_index_rolls_back_on_one_invalid_entry(
    repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    engineering_index_service.replace_document_index(
        repository,
        document_lookup,
        document_id=1,
        mentions=[
            {"kind": EngineeringIndexEntryKind.EQUIPMENT, "identifier": "T1"},
        ],
        now=CREATED_AT,
    )

    with pytest.raises(InvalidIndexEntryIdentifierError):
        engineering_index_service.replace_document_index(
            repository,
            document_lookup,
            document_id=1,
            mentions=[
                {
                    "kind": EngineeringIndexEntryKind.EQUIPMENT,
                    "identifier": "T2",
                },
                {
                    "kind": EngineeringIndexEntryKind.CABLE,
                    "identifier": "   ",
                },
            ],
            now=CREATED_AT,
        )

    entries = repository.list_by_document(1)

    assert [entry.identifier for entry in entries] == ["T1"]


def test_replace_document_index_rejects_a_canonical_library_document(
    repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    with pytest.raises(DocumentNotIndexableError):
        engineering_index_service.replace_document_index(
            repository,
            document_lookup,
            document_id=2,
            mentions=[
                {
                    "kind": EngineeringIndexEntryKind.EQUIPMENT,
                    "identifier": "T1",
                },
            ],
            now=CREATED_AT,
        )


def test_replace_document_index_rejects_an_archived_project(
    repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    with pytest.raises(ProjectNotIndexableError):
        engineering_index_service.replace_document_index(
            repository,
            document_lookup,
            document_id=3,
            mentions=[
                {
                    "kind": EngineeringIndexEntryKind.EQUIPMENT,
                    "identifier": "T1",
                },
            ],
            now=CREATED_AT,
        )


def test_replace_document_index_does_not_affect_a_different_document_in_the_same_project(
    repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    engineering_index_service.register_index_entry(
        repository,
        document_lookup,
        document_id=5,
        kind=EngineeringIndexEntryKind.EQUIPMENT,
        identifier="T9",
        now=CREATED_AT,
    )

    engineering_index_service.replace_document_index(
        repository,
        document_lookup,
        document_id=1,
        mentions=[
            {"kind": EngineeringIndexEntryKind.EQUIPMENT, "identifier": "T1"},
        ],
        now=CREATED_AT,
    )

    assert [
        entry.identifier for entry in repository.list_by_document(5)
    ] == ["T9"]


def test_clear_document_index_removes_every_entry_for_the_document(
    repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    engineering_index_service.register_index_entries(
        repository,
        document_lookup,
        document_id=1,
        mentions=[
            {"kind": EngineeringIndexEntryKind.EQUIPMENT, "identifier": "T1"},
            {"kind": EngineeringIndexEntryKind.CABLE, "identifier": "W-152"},
        ],
        now=CREATED_AT,
    )

    engineering_index_service.clear_document_index(
        repository,
        document_lookup,
        document_id=1,
    )

    assert repository.list_by_document(1) == []


def test_clear_document_index_does_not_affect_a_different_project(
    repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    engineering_index_service.register_index_entry(
        repository,
        document_lookup,
        document_id=1,
        kind=EngineeringIndexEntryKind.EQUIPMENT,
        identifier="T1",
        now=CREATED_AT,
    )
    engineering_index_service.register_index_entry(
        repository,
        document_lookup,
        document_id=4,
        kind=EngineeringIndexEntryKind.EQUIPMENT,
        identifier="T2",
        now=CREATED_AT,
    )

    engineering_index_service.clear_document_index(
        repository,
        document_lookup,
        document_id=1,
    )

    assert repository.list_by_document(1) == []
    assert [
        entry.identifier for entry in repository.list_by_project(20)
    ] == ["T2"]


def test_clear_document_index_rejects_a_canonical_library_document(
    repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    with pytest.raises(DocumentNotIndexableError):
        engineering_index_service.clear_document_index(
            repository,
            document_lookup,
            document_id=2,
        )


def test_clear_document_index_rejects_an_archived_project(
    repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    with pytest.raises(ProjectNotIndexableError):
        engineering_index_service.clear_document_index(
            repository,
            document_lookup,
            document_id=3,
        )


def test_register_index_entry_accepts_a_non_page_locator(
    repository: FakeEngineeringIndexRepository,
    document_lookup: FakeDocumentLookup,
) -> None:
    entry = engineering_index_service.register_index_entry(
        repository,
        document_lookup,
        document_id=1,
        kind=EngineeringIndexEntryKind.CABLE,
        identifier="W-152",
        now=CREATED_AT,
        locator=IndexEntryLocator(
            kind=IndexEntryLocatorKind.CELL_RANGE,
            value="B12:C15",
        ),
    )

    assert entry.locator_kind is IndexEntryLocatorKind.CELL_RANGE
    assert entry.locator_value == "B12:C15"
    assert entry.page is None
