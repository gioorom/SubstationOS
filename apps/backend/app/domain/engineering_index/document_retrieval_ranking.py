"""
Aggregation and ranking for Document Retrieval - the Engineering Index's
read side. Pure and deterministic: given the same request, the same index
entries and the same document metadata, this module always produces the
same ``DocumentRetrievalResult``, including every relevance component and
the order of every reference and mention.

The shape mirrors Structured Retrieval's own
``candidate_aggregation.py``/``candidate_ranking.py`` pair one bounded
context over: group the raw evidence by the thing being retrieved, score
it from a fixed documented weight table, then rank and limit - with the
limit applied only *after* full deduplication and ranking, so the
returned page is always the true top-N.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.engineering_index.document_metadata import DocumentMetadata
from app.domain.engineering_index.document_relevance_policy import (
    DOCUMENT_RELEVANCE_POLICY_VERSION,
    DOCUMENT_RETRIEVAL_VERSION,
    WEIGHT_ADDITIONAL_MENTION,
    WEIGHT_EXACT_IDENTIFIER_MATCH,
    WEIGHT_MULTI_TERM_SUPPORT,
    WEIGHT_PARTIAL_IDENTIFIER_MATCH,
)
from app.domain.engineering_index.document_retrieval_models import (
    DocumentMentionReference,
    DocumentReference,
    DocumentRelevance,
    DocumentRelevanceCategory,
    DocumentRelevanceComponent,
    DocumentRetrievalMetadata,
    DocumentRetrievalRequest,
    DocumentRetrievalResult,
    DocumentRetrievalStatistics,
)
from app.domain.engineering_index.engineering_index_models import IndexEntry


def build_document_retrieval_result(
    *,
    request: DocumentRetrievalRequest,
    entries: tuple[IndexEntry, ...],
    document_metadata: tuple[DocumentMetadata, ...],
    retrieved_at: datetime,
) -> DocumentRetrievalResult:
    relevant = _deduplicate(
        entry for entry in entries if entry.project_id == request.project_id
    )
    metadata_by_document = {
        metadata.document_id: metadata for metadata in document_metadata
    }

    references = tuple(
        sorted(
            (
                _build_reference(
                    request=request,
                    document_id=document_id,
                    entries=document_entries,
                    metadata=metadata_by_document.get(document_id),
                )
                for document_id, document_entries in _group_by_document(
                    relevant
                ).items()
            ),
            key=lambda reference: reference.sort_key,
        )
    )

    limited = references[: request.limit]
    truncated = len(references) > len(limited)
    missing_metadata = tuple(
        reference.document_id
        for reference in limited
        if not reference.metadata_available
    )

    return DocumentRetrievalResult(
        request=request,
        references=limited,
        statistics=DocumentRetrievalStatistics(
            matched_entry_count=len(relevant),
            matched_document_count=len(references),
            returned_document_count=len(limited),
            applied_limit=request.limit,
        ),
        metadata=DocumentRetrievalMetadata(
            document_retrieval_version=DOCUMENT_RETRIEVAL_VERSION,
            relevance_policy_version=DOCUMENT_RELEVANCE_POLICY_VERSION,
            truncated_by_limit=truncated,
            documents_missing_metadata=missing_metadata,
            warnings=_build_warnings(
                matched_document_count=len(references),
                returned_document_count=len(limited),
                truncated=truncated,
                missing_metadata=missing_metadata,
            ),
        ),
        retrieved_at=retrieved_at,
    )


# --- Deduplication and grouping -------------------------------------------


def _entry_identity(entry: IndexEntry) -> tuple[object, ...]:
    """A persisted entry is identified by its own id; an unpersisted one
    by the natural key the Engineering Index's own uniqueness constraint
    uses (document, kind, identifier, locator)."""

    if entry.id is not None:
        return ("id", entry.id)

    return (
        "natural_key",
        entry.document_id,
        entry.kind.value,
        entry.identifier,
        entry.locator.kind.value,
        entry.locator.value,
    )


def _deduplicate(entries) -> tuple[IndexEntry, ...]:
    """One lookup searches once per requested identifier, so the same
    entry legitimately arrives several times (a mention of "T2" also
    matches a search for "T"). Merged here rather than counted twice, so
    relevance never rewards the same recorded mention repeatedly."""

    unique: dict[tuple[object, ...], IndexEntry] = {}

    for entry in entries:
        unique.setdefault(_entry_identity(entry), entry)

    return tuple(unique.values())


def _group_by_document(
    entries: tuple[IndexEntry, ...],
) -> dict[int, tuple[IndexEntry, ...]]:
    grouped: dict[int, list[IndexEntry]] = {}

    for entry in entries:
        grouped.setdefault(entry.document_id, []).append(entry)

    return {
        document_id: tuple(document_entries)
        for document_id, document_entries in grouped.items()
    }


# --- Relevance ------------------------------------------------------------


def _matched_term_components(
    request: DocumentRetrievalRequest,
    entries: tuple[IndexEntry, ...],
) -> tuple[tuple[str, ...], tuple[DocumentRelevanceComponent, ...]]:
    """One component per requested identifier this document matched -
    exact when a recorded mention carries exactly that designation,
    partial when the designation only occurs inside a longer one."""

    folded = tuple(entry.identifier.casefold() for entry in entries)
    matched_terms: list[str] = []
    components: list[DocumentRelevanceComponent] = []

    for term in request.identifiers:
        needle = term.casefold()

        if any(identifier == needle for identifier in folded):
            matched_terms.append(term)
            components.append(
                DocumentRelevanceComponent(
                    category=(
                        DocumentRelevanceCategory.EXACT_IDENTIFIER_MATCH
                    ),
                    weight=WEIGHT_EXACT_IDENTIFIER_MATCH,
                    detail=term,
                )
            )
        elif any(needle in identifier for identifier in folded):
            matched_terms.append(term)
            components.append(
                DocumentRelevanceComponent(
                    category=(
                        DocumentRelevanceCategory.PARTIAL_IDENTIFIER_MATCH
                    ),
                    weight=WEIGHT_PARTIAL_IDENTIFIER_MATCH,
                    detail=term,
                )
            )

    return tuple(matched_terms), tuple(components)


def _build_relevance(
    request: DocumentRetrievalRequest,
    entries: tuple[IndexEntry, ...],
) -> tuple[tuple[str, ...], DocumentRelevance]:
    matched_terms, components = _matched_term_components(request, entries)
    scored = list(components)

    additional_mentions = len(entries) - 1
    if additional_mentions > 0:
        scored.append(
            DocumentRelevanceComponent(
                category=DocumentRelevanceCategory.ADDITIONAL_MENTION,
                weight=WEIGHT_ADDITIONAL_MENTION * additional_mentions,
                detail=f"{len(entries)} recorded mentions",
            )
        )

    additional_terms = len(matched_terms) - 1
    if additional_terms > 0:
        scored.append(
            DocumentRelevanceComponent(
                category=DocumentRelevanceCategory.MULTI_TERM_SUPPORT,
                weight=WEIGHT_MULTI_TERM_SUPPORT * additional_terms,
                detail=(
                    f"{len(matched_terms)} requested identifiers matched: "
                    f"{', '.join(matched_terms)}"
                ),
            )
        )

    return matched_terms, DocumentRelevance(
        total=sum(component.weight for component in scored),
        components=tuple(scored),
    )


# --- References -----------------------------------------------------------


def _mention_reference(entry: IndexEntry) -> DocumentMentionReference:
    return DocumentMentionReference(
        entry_id=entry.id,
        kind=entry.kind,
        identifier=entry.identifier,
        locator_kind=entry.locator.kind,
        locator_value=entry.locator.value,
        label=entry.label,
    )


def _mention_sort_key(
    mention: DocumentMentionReference,
) -> tuple[str, str, str, int]:
    return (
        mention.identifier.casefold(),
        mention.kind.value,
        mention.locator_value or "",
        mention.entry_id if mention.entry_id is not None else -1,
    )


def _build_reference(
    *,
    request: DocumentRetrievalRequest,
    document_id: int,
    entries: tuple[IndexEntry, ...],
    metadata: DocumentMetadata | None,
) -> DocumentReference:
    matched_terms, relevance = _build_relevance(request, entries)
    mentions = tuple(
        sorted(
            (_mention_reference(entry) for entry in entries),
            key=_mention_sort_key,
        )
    )
    matched_identifiers = tuple(
        sorted({entry.identifier for entry in entries}, key=str.casefold)
    )

    return DocumentReference(
        document_id=document_id,
        title=metadata.title if metadata is not None else None,
        document_format=(
            metadata.document_format if metadata is not None else None
        ),
        document_category=(
            metadata.document_category if metadata is not None else None
        ),
        revision=metadata.revision if metadata is not None else None,
        metadata_available=metadata is not None,
        relevance=relevance,
        matched_identifiers=matched_identifiers,
        matched_terms=matched_terms,
        mentions=mentions,
        mention_count=len(mentions),
        sort_key=(-relevance.total, -len(mentions), document_id),
    )


# --- Warnings -------------------------------------------------------------


def _build_warnings(
    *,
    matched_document_count: int,
    returned_document_count: int,
    truncated: bool,
    missing_metadata: tuple[int, ...],
) -> tuple[str, ...]:
    warnings: list[str] = []

    if matched_document_count == 0:
        warnings.append(
            "No document in this project's Engineering Index mentions any "
            "of the requested identifiers."
        )

    if truncated:
        warnings.append(
            f"{matched_document_count} documents matched; the "
            f"{returned_document_count} most relevant were returned."
        )

    if missing_metadata:
        warnings.append(
            "Document metadata was unavailable for document id(s) "
            f"{', '.join(str(document_id) for document_id in missing_metadata)}"
            "; only their recorded mentions are reported."
        )

    return tuple(warnings)
