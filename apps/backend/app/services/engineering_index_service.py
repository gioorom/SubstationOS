"""
Application services for the Engineering Index, per Architecture Freeze
v1.0 (docs/architecture/project_intelligence_architecture.md §5,
ADR-0002). Each function is a single use case, orchestrating the domain
(``app.domain.engineering_index``) through the
``EngineeringIndexRepository`` and ``DocumentLookupPort`` ports - never a
raw database session. This is the landing zone future Document
Classification and Knowledge Extraction milestones will write into; it
deliberately does not itself classify, extract, review, or reason about
anything it stores.
"""

from __future__ import annotations

from datetime import datetime

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
    ProjectNotIndexableError,
)
from app.domain.engineering_index.engineering_index_factory import (
    EngineeringIndexEntryFactory,
)
from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocator,
)
from app.domain.engineering_index.engineering_index_models import IndexEntry
from app.domain.engineering_index.engineering_index_repository import (
    EngineeringIndexRepository,
)
from app.domain.project.project_document_scope import DocumentScope
from app.domain.project.project_lifecycle import MUTABLE_STATES


def _require_indexable_document(
    document_lookup: DocumentLookupPort,
    document_id: int,
) -> DocumentIndexContext:
    context = document_lookup.find(document_id)

    if context is None:
        raise IndexedDocumentNotFoundError(document_id)

    if context.scope is not DocumentScope.PROJECT:
        raise DocumentNotIndexableError(document_id, context.scope)

    if context.project_lifecycle_state not in MUTABLE_STATES:
        raise ProjectNotIndexableError(
            context.project_id,
            context.project_lifecycle_state,
        )

    return context


def _locator_from_mention(
    mention: dict[str, object],
) -> IndexEntryLocator | None:
    locator_kind = mention.get("locator_kind")

    if locator_kind is None:
        return None

    return IndexEntryLocator(
        kind=locator_kind,  # type: ignore[arg-type]
        value=mention.get("locator_value"),  # type: ignore[arg-type]
    )


def _entry_from_mention(
    mention: dict[str, object],
    *,
    project_id: int,
    document_id: int,
    now: datetime,
) -> IndexEntry:
    return EngineeringIndexEntryFactory.create(
        project_id=project_id,
        document_id=document_id,
        kind=mention["kind"],  # type: ignore[arg-type]
        identifier=mention["identifier"],  # type: ignore[arg-type]
        created_at=now,
        page=mention.get("page"),  # type: ignore[arg-type]
        locator=_locator_from_mention(mention),
        label=mention.get("label"),  # type: ignore[arg-type]
    )


def register_index_entry(
    repository: EngineeringIndexRepository,
    document_lookup: DocumentLookupPort,
    *,
    document_id: int,
    kind: EngineeringIndexEntryKind,
    identifier: str,
    now: datetime,
    page: int | None = None,
    locator: IndexEntryLocator | None = None,
    label: str | None = None,
) -> IndexEntry:
    """
    Registers one candidate mention against a document. Raises
    ``IndexedDocumentNotFoundError`` if the document does not exist,
    ``DocumentNotIndexableError`` if it is not PROJECT-scoped (ADR-0005),
    and ``ProjectNotIndexableError`` if its Project is Archived or
    Deleted.
    """

    context = _require_indexable_document(document_lookup, document_id)

    entry = EngineeringIndexEntryFactory.create(
        project_id=context.project_id,
        document_id=document_id,
        kind=kind,
        identifier=identifier,
        created_at=now,
        page=page,
        locator=locator,
        label=label,
    )

    return repository.save(entry)


def register_index_entries(
    repository: EngineeringIndexRepository,
    document_lookup: DocumentLookupPort,
    *,
    document_id: int,
    mentions: list[dict[str, object]],
    now: datetime,
) -> list[IndexEntry]:
    """
    Registers many candidate mentions against one document in a single
    call - the shape future automated Document Indexing will use, which
    typically produces several mentions per document at once. Each item
    of ``mentions`` supplies ``kind``, ``identifier``, and optionally
    ``page``/``locator_kind``/``locator_value``/``label``. The document
    is validated once, before any entry is built or persisted.

    This is the additive path: repeated calls with overlapping mentions
    append rather than replace. ``replace_document_index`` is the
    idempotent rebuild path.
    """

    context = _require_indexable_document(document_lookup, document_id)

    entries = [
        _entry_from_mention(
            mention,
            project_id=context.project_id,
            document_id=document_id,
            now=now,
        )
        for mention in mentions
    ]

    return [repository.save(entry) for entry in entries]


def replace_document_index(
    repository: EngineeringIndexRepository,
    document_lookup: DocumentLookupPort,
    *,
    document_id: int,
    mentions: list[dict[str, object]],
    now: datetime,
) -> list[IndexEntry]:
    """
    Rebuilds a document's Engineering Index from scratch: every existing
    entry for ``document_id`` is atomically replaced by the entries
    built from ``mentions``, per ADR-0002's "freely rebuildable"
    requirement.

    This is the idempotent rebuild path: calling it twice with the same
    ``mentions`` leaves the index in the same state rather than
    accumulating duplicates, because the previous entries are always
    fully replaced rather than appended to (unlike
    ``register_index_entries``).

    The document is validated once, and every entry is built - enforcing
    every domain invariant - before anything is removed or written; an
    invalid mention leaves the existing index completely untouched.
    Raises the same document/project guard errors as
    ``register_index_entry``.
    """

    context = _require_indexable_document(document_lookup, document_id)

    entries = [
        _entry_from_mention(
            mention,
            project_id=context.project_id,
            document_id=document_id,
            now=now,
        )
        for mention in mentions
    ]

    return repository.replace_for_document(
        document_id,
        context.project_id,
        entries,
    )


def clear_document_index(
    repository: EngineeringIndexRepository,
    document_lookup: DocumentLookupPort,
    *,
    document_id: int,
) -> None:
    """
    Removes every Engineering Index entry recorded for ``document_id``,
    without touching the document itself. Obeys the same lifecycle and
    scope guards as writing does: raises ``IndexedDocumentNotFoundError``,
    ``DocumentNotIndexableError``, or ``ProjectNotIndexableError`` under
    the same conditions as ``register_index_entry``.
    """

    _require_indexable_document(document_lookup, document_id)

    repository.delete_by_document(document_id)


def get_index_entry(
    repository: EngineeringIndexRepository,
    entry_id: int,
) -> IndexEntry:
    entry = repository.get_by_id(entry_id)

    if entry is None:
        raise IndexEntryNotFoundError(entry_id)

    return entry


def list_index_entries_for_document(
    repository: EngineeringIndexRepository,
    document_id: int,
) -> list[IndexEntry]:
    return repository.list_by_document(document_id)


def list_index_entries_for_project(
    repository: EngineeringIndexRepository,
    project_id: int,
    *,
    kind: EngineeringIndexEntryKind | None = None,
) -> list[IndexEntry]:
    return repository.list_by_project(project_id, kind=kind)


def search_index_by_identifier(
    repository: EngineeringIndexRepository,
    project_id: int,
    identifier: str,
) -> list[IndexEntry]:
    return repository.search_by_identifier(project_id, identifier)
