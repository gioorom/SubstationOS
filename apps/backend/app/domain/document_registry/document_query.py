"""
The governed query vocabulary for the document registry.

Every filter and every sort field is a **closed enum member or a typed
value object**. There is no field-name string, no operator, no
expression, and no mapping from caller input to a database column. A
caller cannot name a column this module has not declared, because a
column name never travels: an enum member does, and the adapter decides
what it means.

That is the whole defence. It is structural, not a matter of escaping.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.domain.document_registry.document_models import (
    DocumentCategory,
    DocumentFormat,
)
from app.domain.project.project_document_scope import DocumentScope
from app.domain.shared_kernel.pagination import (
    PageRequest,
    SortDirection,
)


class DocumentSortField(str, Enum):
    """
    The fields a document list may be ordered by.

    Four members, each chosen because an engineer has a reason to want
    it. Adding a fifth is a deliberate act with a test behind it - not
    something a caller can do by sending a different string.
    """

    UPLOADED_AT = "uploaded_at"
    FILENAME = "filename"
    REVISION = "revision"
    DOCUMENT_FORMAT = "document_format"


#: Newest first. A registry is read to find recent work far more often
#: than to read it alphabetically.
DEFAULT_DOCUMENT_SORT = DocumentSortField.UPLOADED_AT
DEFAULT_DOCUMENT_DIRECTION = SortDirection.DESCENDING


@dataclass(frozen=True, slots=True)
class DocumentSearchTerm:
    """
    A free-text search over a **documented, closed** set of fields:
    ``filename`` and ``project_name``.

    Matching is defined once, here, so the behaviour is the same
    everywhere and can be stated in the API documentation:

    - **case-insensitive**;
    - **partial** - a substring match, not a prefix and not a whole word;
    - **whitespace-trimmed** at both ends;
    - internal whitespace preserved exactly, so ``"CP 01"`` does not
      match ``"CP01"``. Collapsing it would be a normalisation nobody
      asked for.

    A term that is empty after trimming is not a search; it is the
    absence of one, and :meth:`of` returns ``None`` rather than a filter
    that matches everything.
    """

    value: str

    @classmethod
    def of(cls, raw: str | None) -> "DocumentSearchTerm | None":
        if raw is None:
            return None

        trimmed = raw.strip()

        return cls(trimmed) if trimmed else None


@dataclass(frozen=True, slots=True)
class DocumentQuery:
    """
    One governed request for a page of the document registry.

    Every field is optional and every combination is an ``AND``. There is
    no ``OR``, no negation and no grouping: a query language is a
    liability in a public API, and the requirement in front of us is a
    registry table with four filter controls.
    """

    page: PageRequest
    project_id: int | None = None
    scope: DocumentScope | None = None
    document_format: DocumentFormat | None = None
    category: DocumentCategory | None = None
    search: DocumentSearchTerm | None = None
    sort_by: DocumentSortField = DEFAULT_DOCUMENT_SORT
    direction: SortDirection = DEFAULT_DOCUMENT_DIRECTION
