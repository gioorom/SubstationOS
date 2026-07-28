"""
Value objects for Document Retrieval - the Engineering Index's read side,
the deterministic answer to the question the architecture doc (§5) always
named as this bounded context's purpose: *"which documents mention X?"*.

Every type here is immutable and deterministic: the same index entries,
the same document metadata and the same ``DocumentRetrievalRequest``
always produce the same ``DocumentRetrievalResult``, including relevance
components and reference ordering. Nothing here performs I/O, calls an
AI provider, reads a document's contents, or interprets free text - a
request is a closed set of engineering identifiers, never a question.

A ``DocumentReference`` is a **pointer plus counted evidence**, never a
copy of a document and never a judgement about it: no summary, no
extracted facts, no classification of what the document contains.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from app.domain.engineering_index.engineering_index_entry_kind import (
    EngineeringIndexEntryKind,
)
from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocatorKind,
)


class DocumentRelevanceCategory(str, Enum):
    """One named, weighted contribution to a document's relevance - see
    ``document_relevance_policy.py`` for the fixed weight table."""

    EXACT_IDENTIFIER_MATCH = "exact_identifier_match"
    PARTIAL_IDENTIFIER_MATCH = "partial_identifier_match"
    ADDITIONAL_MENTION = "additional_mention"
    MULTI_TERM_SUPPORT = "multi_term_support"


@dataclass(frozen=True, slots=True)
class DocumentRelevanceComponent:
    """``detail`` carries the specific matched identifier or counted
    evidence, so a component explains itself without cross-referencing
    the request."""

    category: DocumentRelevanceCategory
    weight: float
    detail: str


@dataclass(frozen=True, slots=True)
class DocumentRelevance:
    """``total`` is always the sum of ``components`` - never set
    independently, and never a probability or a confidence."""

    total: float
    components: tuple[DocumentRelevanceComponent, ...]


@dataclass(frozen=True, slots=True)
class DocumentMentionReference:
    """
    One recorded mention that justified retrieving a document - a
    lightweight restatement of the ``IndexEntry`` fields a reader needs
    to navigate to it, never the entry itself (the same "each read side
    owns its own view" pattern Structured Retrieval's
    ``KnowledgeCandidateReference`` established for Graph Query's node
    view).
    """

    entry_id: int | None
    kind: EngineeringIndexEntryKind
    identifier: str
    locator_kind: IndexEntryLocatorKind
    locator_value: str | None
    label: str | None

    @property
    def page(self) -> int | None:
        """The page number for a ``PAGE`` locator, ``None`` for every
        other locator kind - the same backward-compatible view
        ``IndexEntryLocator`` itself exposes."""

        if (
            self.locator_kind is IndexEntryLocatorKind.PAGE
            and self.locator_value is not None
        ):
            return int(self.locator_value)

        return None


@dataclass(frozen=True, slots=True)
class DocumentReference:
    """
    One retrieved document, with the evidence that justified retrieving
    it.

    Every metadata field is optional because an Engineering Index entry
    is a freely rebuildable lead that may outlive the document row it
    points at (ADR-0002). When metadata is unavailable the fields are
    ``None`` and ``metadata_available`` is ``False`` - never filled in
    with a placeholder, and never inferred from the mentions.

    ``sort_key`` is precomputed by ``document_retrieval_ranking.py`` so
    ordering never has to re-derive it, and is ascending-sortable:
    ``(-relevance_total, -mention_count, document_id)``.
    """

    document_id: int
    title: str | None
    document_format: str | None
    document_category: str | None
    revision: str | None
    metadata_available: bool
    relevance: DocumentRelevance
    matched_identifiers: tuple[str, ...]
    matched_terms: tuple[str, ...]
    mentions: tuple[DocumentMentionReference, ...]
    mention_count: int
    sort_key: tuple[float, int, int]

    @property
    def page_references(self) -> tuple[int, ...]:
        """Every distinct page a mention was recorded on, ascending.
        Empty for documents whose mentions carry non-page locators (a
        spreadsheet cell range, a CAD layout) - never a fabricated page
        number."""

        pages = {
            mention.page
            for mention in self.mentions
            if mention.page is not None
        }

        return tuple(sorted(pages))


@dataclass(frozen=True, slots=True)
class DocumentRetrievalRequest:
    """
    A fully validated, canonically ordered document lookup. Never
    constructed directly - always via
    ``DocumentRetrievalRequestFactory.create``, which enforces every
    invariant (positive project id, at least one non-blank identifier,
    safe limits) at construction time.

    ``identifiers`` are engineering designations ("T2", "87T", "L3"), not
    a natural-language question: this bounded context performs no intent
    detection and no free-text interpretation.
    """

    project_id: int
    identifiers: tuple[str, ...]
    limit: int


@dataclass(frozen=True, slots=True)
class DocumentRetrievalStatistics:
    matched_entry_count: int
    matched_document_count: int
    returned_document_count: int
    applied_limit: int


@dataclass(frozen=True, slots=True)
class DocumentRetrievalMetadata:
    """Non-sensitive execution metadata. ``warnings`` records structural
    facts about this lookup (results truncated by the limit, documents
    whose metadata was unavailable) - never advice and never
    interpretation."""

    document_retrieval_version: str
    relevance_policy_version: str
    truncated_by_limit: bool
    documents_missing_metadata: tuple[int, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DocumentRetrievalResult:
    request: DocumentRetrievalRequest
    references: tuple[DocumentReference, ...]
    statistics: DocumentRetrievalStatistics
    metadata: DocumentRetrievalMetadata
    retrieved_at: datetime
