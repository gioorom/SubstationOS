"""
Application service for Document Retrieval - the Engineering Index's read
side, and the retrieval capability the Engineering Engine's
DOCUMENT_LOOKUP workflow depends on (Milestone 23B.1).

One use case: given a project and a set of engineering identifiers,
return the documents whose recorded mentions match them, ranked by
counted evidence. Orchestrates the domain through the two existing ports
(``EngineeringIndexRepository`` for mentions, ``DocumentMetadataPort`` for
presentable document metadata) - never a raw database session, never a
document's contents, and never an AI provider. **No LLM is involved at
any point.**

The service performs no ranking, no scoring and no aggregation of its
own: those are pure domain concerns
(``document_retrieval_ranking.py``). It only reads through ports and
hands the results to the domain.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.engineering_index.document_metadata import (
    DocumentMetadataPort,
)
from app.domain.engineering_index.document_retrieval_models import (
    DocumentRetrievalRequest,
    DocumentRetrievalResult,
)
from app.domain.engineering_index.document_retrieval_ranking import (
    build_document_retrieval_result,
)
from app.domain.engineering_index.engineering_index_models import IndexEntry
from app.domain.engineering_index.engineering_index_repository import (
    EngineeringIndexRepository,
)


def retrieve_documents(
    index_repository: EngineeringIndexRepository,
    document_metadata_port: DocumentMetadataPort,
    request: DocumentRetrievalRequest,
    *,
    now: datetime,
) -> DocumentRetrievalResult:
    """
    Reads once per requested identifier through the existing
    ``search_by_identifier`` capability, resolves every matched document's
    metadata in a single batch read, and delegates deduplication, scoring
    and ranking to the domain.

    ``now`` is always supplied by the caller rather than read from the
    wall clock here, so the whole lookup stays reproducible (CLAUDE.md
    §16).
    """

    entries = _search_entries(index_repository, request)
    document_ids = tuple(sorted({entry.document_id for entry in entries}))
    document_metadata = document_metadata_port.find_many(document_ids)

    return build_document_retrieval_result(
        request=request,
        entries=entries,
        document_metadata=document_metadata,
        retrieved_at=now,
    )


def _search_entries(
    index_repository: EngineeringIndexRepository,
    request: DocumentRetrievalRequest,
) -> tuple[IndexEntry, ...]:
    """Searched one identifier at a time because that is the capability
    the Engineering Index port already exposes. Overlapping results are
    expected and are merged by the domain, never counted twice."""

    found: list[IndexEntry] = []

    for identifier in request.identifiers:
        found.extend(
            index_repository.search_by_identifier(
                request.project_id, identifier
            )
        )

    return tuple(found)
