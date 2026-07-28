"""
Service tests for Document Retrieval (Milestone 23B.1). Both ports are
in-memory fakes: no database, no network, and no AI provider - the service
only reads through ports and delegates scoring to the domain.
"""

from __future__ import annotations

import pytest

from app.domain.engineering_index.document_retrieval_factory import (
    DocumentRetrievalRequestFactory,
)
from app.domain.engineering_index.engineering_index_exceptions import (
    EngineeringIndexError,
)
from app.services import document_retrieval_service
from tests.domain._document_retrieval_support import NOW, entry, metadata


class FakeIndexRepository:
    """Answers ``search_by_identifier`` with the same case-insensitive
    substring match the real SQLAlchemy adapter performs."""

    def __init__(self, entries=(), *, raises: Exception | None = None) -> None:
        self._entries = tuple(entries)
        self._raises = raises
        self.searched_identifiers: list[str] = []

    def search_by_identifier(self, project_id: int, identifier: str):
        self.searched_identifiers.append(identifier)

        if self._raises is not None:
            raise self._raises

        needle = identifier.casefold()

        return [
            candidate
            for candidate in self._entries
            if candidate.project_id == project_id
            and needle in candidate.identifier.casefold()
        ]


class FakeDocumentMetadataPort:
    def __init__(self, records=()) -> None:
        self._records = tuple(records)
        self.requested_document_ids: list[tuple[int, ...]] = []

    def find_many(self, document_ids: tuple[int, ...]):
        self.requested_document_ids.append(document_ids)

        return tuple(
            record
            for record in self._records
            if record.document_id in document_ids
        )


def _request(identifiers=("T2",), limit=20, project_id=1):
    return DocumentRetrievalRequestFactory.create(
        project_id=project_id, identifiers=identifiers, limit=limit
    )


def test_a_matching_document_is_retrieved_with_its_metadata() -> None:
    repository = FakeIndexRepository([entry()])
    metadata_port = FakeDocumentMetadataPort([metadata()])

    result = document_retrieval_service.retrieve_documents(
        repository, metadata_port, _request(), now=NOW
    )

    assert len(result.references) == 1
    assert result.references[0].title == "montante-T2-schema-funzionale.pdf"
    assert result.retrieved_at == NOW


def test_every_requested_identifier_is_searched() -> None:
    repository = FakeIndexRepository([entry()])

    document_retrieval_service.retrieve_documents(
        repository,
        FakeDocumentMetadataPort([metadata()]),
        _request(("T2", "87T")),
        now=NOW,
    )

    assert sorted(repository.searched_identifiers) == ["87T", "T2"]


def test_metadata_is_resolved_in_a_single_batch_read() -> None:
    """One read for every matched document - never one query per document
    inside a loop."""

    repository = FakeIndexRepository(
        [
            entry(entry_id=1, document_id=10),
            entry(entry_id=2, document_id=11),
            entry(entry_id=3, document_id=12),
        ]
    )
    metadata_port = FakeDocumentMetadataPort([metadata(document_id=10)])

    document_retrieval_service.retrieve_documents(
        repository, metadata_port, _request(), now=NOW
    )

    assert metadata_port.requested_document_ids == [(10, 11, 12)]


def test_overlapping_matches_across_terms_are_not_counted_twice() -> None:
    repository = FakeIndexRepository([entry(identifier="T2")])

    result = document_retrieval_service.retrieve_documents(
        repository,
        FakeDocumentMetadataPort([metadata()]),
        _request(("T2", "T")),
        now=NOW,
    )

    assert result.references[0].mention_count == 1


def test_no_match_yields_an_empty_result_and_no_metadata_read() -> None:
    repository = FakeIndexRepository([entry(identifier="T2")])
    metadata_port = FakeDocumentMetadataPort([metadata()])

    result = document_retrieval_service.retrieve_documents(
        repository, metadata_port, _request(("99Z",)), now=NOW
    )

    assert result.references == ()
    assert metadata_port.requested_document_ids == [()]


def test_a_repository_failure_propagates_as_a_typed_domain_error() -> None:
    """The service does not swallow a repository failure - the caller
    decides how to report it (the engine's step handler maps it to a typed
    RETRIEVAL_FAILURE)."""

    repository = FakeIndexRepository(
        raises=EngineeringIndexError("index unavailable")
    )

    with pytest.raises(EngineeringIndexError):
        document_retrieval_service.retrieve_documents(
            repository, FakeDocumentMetadataPort(), _request(), now=NOW
        )


def test_the_lookup_is_reproducible() -> None:
    entries = [
        entry(entry_id=1, document_id=10, identifier="T2"),
        entry(entry_id=2, document_id=11, identifier="T21"),
    ]
    records = [metadata(document_id=10), metadata(document_id=11)]

    first = document_retrieval_service.retrieve_documents(
        FakeIndexRepository(entries),
        FakeDocumentMetadataPort(records),
        _request(),
        now=NOW,
    )
    second = document_retrieval_service.retrieve_documents(
        FakeIndexRepository(entries),
        FakeDocumentMetadataPort(records),
        _request(),
        now=NOW,
    )

    assert first == second
