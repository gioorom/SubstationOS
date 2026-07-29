"""
The document registry service, against in-memory ports.

What these prove that the API tests cannot easily: the three content
failure modes stay distinguishable, and the download never touches
anything but the two ports.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime

import pytest

from app.domain.document_identity.document_content_port import (
    DocumentContentDescriptor,
    DocumentContentPort,
)
from app.domain.document_identity.document_storage_location import (
    DocumentStorageLocationPort,
)
from app.domain.document_registry.document_failures import (
    DocumentContentAccessError,
    DocumentContentNotFoundError,
    DocumentNotFoundError,
)
from app.domain.document_registry.document_models import (
    DocumentCategory,
    DocumentDetail,
    DocumentFormat,
    DocumentSummary,
)
from app.domain.document_registry.document_query import DocumentQuery
from app.domain.document_registry.document_repository import (
    DocumentRegistryRepository,
)
from app.domain.project.project_document_scope import DocumentScope
from app.domain.shared_kernel.pagination import Page, PageRequest
from app.services import document_registry_service

CONTENT = b"%PDF-1.7 Trasformatore TR1 630 kVA"


def _detail(document_id: int = 1) -> DocumentDetail:
    return DocumentDetail(
        document_id=document_id,
        project_id=2,
        project_name="Cabina Gamma",
        filename="schema.pdf",
        document_format=DocumentFormat.PDF,
        category=DocumentCategory.FUNCTIONAL_SCHEMATIC,
        revision="00",
        scope=DocumentScope.PROJECT,
        uploaded_at=datetime(2026, 7, 1, 9, 0),
        content_checksum="a" * 64,
        checksum_algorithm="sha256",
        size_bytes=len(CONTENT),
        content_available=False,
        ingestion_state="processed",
        ingestion_outcome="ready_for_extraction",
    )


class FakeRegistry(DocumentRegistryRepository):
    def __init__(self, details: dict[int, DocumentDetail]) -> None:
        self._details = details

    def list_page(self, query: DocumentQuery) -> Page[DocumentSummary]:
        summaries = tuple(
            detail.summary for detail in self._details.values()
        )

        start = query.page.offset

        return Page.of(
            summaries[start : start + query.page.limit],
            total=len(summaries),
            request=query.page,
        )

    def find_detail(self, document_id: int) -> DocumentDetail | None:
        return self._details.get(document_id)


class FakeStorageLocation(DocumentStorageLocationPort):
    def __init__(self, references: dict[int, str]) -> None:
        self._references = references

    def find_storage_reference(self, document_id: int) -> str | None:
        return self._references.get(document_id)


class FakeContent(DocumentContentPort):
    """
    Keyed by opaque reference. It has no notion of a path, which is the
    point: the service must work identically against a filesystem and an
    object store.
    """

    def __init__(
        self,
        stored: dict[str, bytes],
        *,
        unreadable: set[str] | None = None,
    ) -> None:
        self._stored = stored
        self._unreadable = unreadable or set()
        self.chunk_sizes: list[int] = []

    def describe(
        self, storage_reference: str
    ) -> DocumentContentDescriptor | None:
        if storage_reference in self._unreadable:
            return DocumentContentDescriptor(
                storage_reference=storage_reference,
                size_bytes=0,
                readable=False,
            )

        if storage_reference not in self._stored:
            return None

        return DocumentContentDescriptor(
            storage_reference=storage_reference,
            size_bytes=len(self._stored[storage_reference]),
            readable=True,
        )

    def read_prefix(self, storage_reference: str, length: int) -> bytes:
        return self._stored[storage_reference][:length]

    def iter_chunks(
        self, storage_reference: str, chunk_size: int
    ) -> Iterator[bytes]:
        self.chunk_sizes.append(chunk_size)

        data = self._stored[storage_reference]

        for start in range(0, len(data), chunk_size):
            yield data[start : start + chunk_size]


def _ports(
    *,
    details: dict[int, DocumentDetail] | None = None,
    references: dict[int, str] | None = None,
    stored: dict[str, bytes] | None = None,
    unreadable: set[str] | None = None,
):
    registry = FakeRegistry(details if details is not None else {1: _detail()})
    locations = FakeStorageLocation(
        references if references is not None else {1: "opaque-ref"}
    )
    content = FakeContent(
        stored if stored is not None else {"opaque-ref": CONTENT},
        unreadable=unreadable,
    )

    return registry, content, locations


# --- Detail ---------------------------------------------------------------


def test_detail_reports_content_as_available_when_it_is() -> None:
    registry, content, locations = _ports()

    detail = document_registry_service.get_document_detail(
        registry, content, locations, document_id=1
    )

    assert detail.content_available is True


def test_detail_reports_content_as_unavailable_when_it_is_gone() -> None:
    """A registry row can outlive its file. Saying "yes, download it"
    would be a lie the download would then have to break."""

    registry, content, locations = _ports(stored={})

    detail = document_registry_service.get_document_detail(
        registry, content, locations, document_id=1
    )

    assert detail.content_available is False


def test_detail_reports_content_as_unavailable_with_no_reference() -> None:
    registry, content, locations = _ports(references={})

    detail = document_registry_service.get_document_detail(
        registry, content, locations, document_id=1
    )

    assert detail.content_available is False


def test_detail_raises_for_an_unknown_document() -> None:
    registry, content, locations = _ports()

    with pytest.raises(DocumentNotFoundError) as failure:
        document_registry_service.get_document_detail(
            registry, content, locations, document_id=999
        )

    assert failure.value.document_id == 999


# --- Download -------------------------------------------------------------


def test_download_resolves_through_both_ports() -> None:
    registry, content, locations = _ports()

    download = document_registry_service.resolve_download(
        registry, content, locations, document_id=1
    )

    assert download.storage_reference == "opaque-ref"
    assert download.download_filename == "schema.pdf"
    assert download.media_type == "application/pdf"
    assert download.size_bytes == len(CONTENT)


def test_download_streams_rather_than_reading_the_whole_file() -> None:
    """A 200 MB drawing must be served without being held in memory."""

    registry, content, locations = _ports()

    download = document_registry_service.resolve_download(
        registry, content, locations, document_id=1
    )

    streamed = b"".join(
        document_registry_service.stream_download(content, download)
    )

    assert streamed == CONTENT
    assert content.chunk_sizes == [
        document_registry_service.DOWNLOAD_CHUNK_SIZE
    ]


def test_download_raises_for_an_unknown_document() -> None:
    registry, content, locations = _ports()

    with pytest.raises(DocumentNotFoundError):
        document_registry_service.resolve_download(
            registry, content, locations, document_id=999
        )


def test_a_document_with_no_recorded_reference_is_a_content_failure() -> (
    None
):
    """Not a missing document - the registry has one and cannot say where
    its bytes are. Different problem, different remedy."""

    registry, content, locations = _ports(references={})

    with pytest.raises(DocumentContentNotFoundError) as failure:
        document_registry_service.resolve_download(
            registry, content, locations, document_id=1
        )

    assert "no storage reference" in str(failure.value)


def test_content_that_no_longer_exists_is_not_found() -> None:
    registry, content, locations = _ports(stored={})

    with pytest.raises(DocumentContentNotFoundError) as failure:
        document_registry_service.resolve_download(
            registry, content, locations, document_id=1
        )

    assert "no longer exists" in str(failure.value)


def test_content_that_cannot_be_read_is_an_access_failure() -> None:
    """"It is not there" and "it is there and I cannot read it" are
    different facts, and conflating them sends an engineer to the wrong
    place."""

    registry, content, locations = _ports(unreadable={"opaque-ref"})

    with pytest.raises(DocumentContentAccessError):
        document_registry_service.resolve_download(
            registry, content, locations, document_id=1
        )


def test_no_failure_message_names_a_path_or_an_adapter() -> None:
    registry, content, locations = _ports(
        stored={}, references={1: "/var/substationos/storage/secret.pdf"}
    )

    with pytest.raises(DocumentContentNotFoundError) as failure:
        document_registry_service.resolve_download(
            registry, content, locations, document_id=1
        )

    message = str(failure.value)

    assert "/var" not in message
    assert "storage" not in message
    assert "secret" not in message


# --- Listing --------------------------------------------------------------


def test_listing_asks_the_repository_for_one_page() -> None:
    details = {index: _detail(index) for index in range(1, 8)}
    registry, _, _ = _ports(details=details)

    page = document_registry_service.list_documents(
        registry,
        DocumentQuery(page=PageRequest(page=1, page_size=3)),
    )

    assert len(page.items) == 3
    assert page.total == 7
    assert page.has_next is True
