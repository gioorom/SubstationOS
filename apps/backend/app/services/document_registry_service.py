"""
Application services for the document registry.

The router calls these and nothing else: it builds no query, opens no
session and touches no storage. Everything that decides *what* a caller
may see happens here, over the ports.
"""

from __future__ import annotations

from dataclasses import replace

from app.domain.document_identity.document_content_port import (
    DocumentContentPort,
)
from app.domain.document_identity.document_storage_location import (
    DocumentStorageLocationPort,
)
from app.domain.document_registry.document_download import DocumentDownload
from app.domain.document_registry.document_failures import (
    DocumentContentAccessError,
    DocumentContentNotFoundError,
    DocumentNotFoundError,
)
from app.domain.document_registry.document_models import (
    DocumentDetail,
    DocumentSummary,
)
from app.domain.document_registry.document_query import DocumentQuery
from app.domain.document_registry.document_repository import (
    DocumentRegistryRepository,
)
from app.domain.shared_kernel.pagination import Page

#: Streamed in 64 KiB chunks. A 200 MB drawing is served without ever
#: being held in memory, which is the whole reason the content port
#: exposes ``iter_chunks`` rather than a read-it-all method.
DOWNLOAD_CHUNK_SIZE = 64 * 1024


def list_documents(
    repository: DocumentRegistryRepository,
    query: DocumentQuery,
) -> Page[DocumentSummary]:
    """One page of the registry. The query is already validated - an
    invalid page could not have been constructed."""

    return repository.list_page(query)


def get_document_detail(
    repository: DocumentRegistryRepository,
    content_port: DocumentContentPort,
    storage_location_port: DocumentStorageLocationPort,
    *,
    document_id: int,
) -> DocumentDetail:
    """
    One document's full public record.

    ``content_available`` is resolved here, by asking the two ports in
    turn, because it is the only honest answer to "can I download this?"
    - and the registry alone cannot give it.

    :raises DocumentNotFoundError: no such document
    """

    detail = repository.find_detail(document_id)

    if detail is None:
        raise DocumentNotFoundError(document_id)

    return replace(
        detail,
        content_available=_content_is_available(
            content_port,
            storage_location_port,
            document_id=document_id,
        ),
    )


def _content_is_available(
    content_port: DocumentContentPort,
    storage_location_port: DocumentStorageLocationPort,
    *,
    document_id: int,
) -> bool:
    reference = storage_location_port.find_storage_reference(document_id)

    if reference is None:
        return False

    descriptor = content_port.describe(reference)

    return descriptor is not None and descriptor.readable


def resolve_download(
    repository: DocumentRegistryRepository,
    content_port: DocumentContentPort,
    storage_location_port: DocumentStorageLocationPort,
    *,
    document_id: int,
) -> DocumentDownload:
    """
    Resolve everything needed to serve a document's original bytes.

    The chain is: id -> registry -> storage reference -> descriptor. **At
    no point does a caller-supplied value reach storage**; the only input
    is an integer id, and the reference is whatever the registry recorded
    for it. There is no parameter through which a path could be
    expressed, which is why traversal is not merely blocked here but
    unrepresentable.

    :raises DocumentNotFoundError: no such document
    :raises DocumentContentNotFoundError: no reference recorded, or
        nothing at that reference
    :raises DocumentContentAccessError: found, and unreadable
    """

    detail = repository.find_detail(document_id)

    if detail is None:
        raise DocumentNotFoundError(document_id)

    reference = storage_location_port.find_storage_reference(document_id)

    if reference is None:
        raise DocumentContentNotFoundError(
            document_id,
            "the registry holds no storage reference for it",
        )

    descriptor = content_port.describe(reference)

    if descriptor is None:
        raise DocumentContentNotFoundError(
            document_id,
            "the stored content no longer exists",
        )

    if not descriptor.readable:
        raise DocumentContentAccessError(
            document_id,
            "the stored content exists but could not be read",
        )

    return DocumentDownload.of(
        document_id=document_id,
        storage_reference=reference,
        filename=detail.filename,
        document_format=detail.document_format,
        size_bytes=descriptor.size_bytes,
    )


def stream_download(
    content_port: DocumentContentPort,
    download: DocumentDownload,
):
    """
    The byte stream for a resolved download.

    Separate from :func:`resolve_download` so every failure is raised
    *before* a response begins: once the first chunk has been written,
    the status code is already sent and a failure can no longer be
    reported as one.
    """

    return content_port.iter_chunks(
        download.storage_reference, DOWNLOAD_CHUNK_SIZE
    )
