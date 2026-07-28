from __future__ import annotations

from app.domain.engineering_index.engineering_index_entry_kind import (
    EngineeringIndexEntryKind,
)
from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocatorKind,
)
from app.domain.project.project_document_scope import DocumentScope
from app.domain.project.project_lifecycle import ProjectLifecycleState


class EngineeringIndexError(Exception):
    """
    Base class for every exception raised by the Engineering Index
    bounded context.
    """


class InvalidIndexEntryIdentifierError(EngineeringIndexError):
    def __init__(self, identifier: str) -> None:
        self.identifier = identifier

        super().__init__(
            f"Invalid engineering index identifier: '{identifier}'. "
            "An identifier is required."
        )


class InvalidIndexEntryPageError(EngineeringIndexError):
    def __init__(self, page: int) -> None:
        self.page = page

        super().__init__(
            f"Invalid engineering index page: {page}. "
            "A page reference, when given, must be 1 or greater."
        )


class InvalidIndexEntryLocatorError(EngineeringIndexError):
    """
    A source locator whose ``value`` does not obey the shape its
    ``kind`` requires (e.g. a non-numeric ``PAGE`` value, or a blank
    value for a non-``PAGE`` kind).
    """

    def __init__(
        self,
        kind: IndexEntryLocatorKind,
        value: str | None,
    ) -> None:
        self.locator_kind = kind
        self.locator_value = value

        super().__init__(
            f"Invalid engineering index locator: kind='{kind.value}', "
            f"value={value!r}."
        )


class DuplicateIndexEntryError(EngineeringIndexError):
    """
    An Engineering Index entry with the same document, kind, identifier
    and source locator already exists. Raised when the persistence
    layer's uniqueness constraint rejects an insert - the backstop for
    idempotency alongside the replace-semantics rebuild path.
    """

    def __init__(
        self,
        document_id: int,
        kind: EngineeringIndexEntryKind,
        identifier: str,
    ) -> None:
        self.document_id = document_id
        self.kind = kind
        self.identifier = identifier

        super().__init__(
            f"An Engineering Index entry already exists for document "
            f"'{document_id}', kind '{kind.value}', identifier "
            f"'{identifier}' at this source location."
        )


class IndexEntryNotFoundError(EngineeringIndexError):
    def __init__(self, entry_id: int) -> None:
        self.entry_id = entry_id

        super().__init__(
            f"Engineering index entry '{entry_id}' not found."
        )


class IndexedDocumentNotFoundError(EngineeringIndexError):
    """
    The document an index entry was to be registered against does not
    exist.
    """

    def __init__(self, document_id: int) -> None:
        self.document_id = document_id

        super().__init__(f"Document '{document_id}' not found.")


class DocumentNotIndexableError(EngineeringIndexError):
    """
    Only PROJECT-scoped documents feed a Project's Engineering Index
    (ADR-0005; architecture doc §3). A CANONICAL_LIBRARY document is
    never a source for any Project's Index.
    """

    def __init__(self, document_id: int, scope: DocumentScope) -> None:
        self.document_id = document_id
        self.scope = scope

        super().__init__(
            f"Document '{document_id}' has scope '{scope.value}' and "
            "cannot feed a Project's Engineering Index. Only "
            "PROJECT-scoped documents are indexable."
        )


class ProjectNotIndexableError(EngineeringIndexError):
    """
    A Project's Engineering Index accepts new entries only while the
    Project itself is mutable (Draft or Active) - Archived and Deleted
    projects are read-only, per the Project Lifecycle.
    """

    def __init__(
        self,
        project_id: int,
        lifecycle_state: ProjectLifecycleState,
    ) -> None:
        self.project_id = project_id
        self.lifecycle_state = lifecycle_state

        super().__init__(
            f"Project '{project_id}' is '{lifecycle_state.value}' and "
            "is read-only; its Engineering Index cannot be written to."
        )


class BlankDocumentRetrievalRequestError(EngineeringIndexError):
    """
    A document lookup that names no engineering identifier at all. This
    bounded context answers "which documents mention X?" - with no X
    there is nothing to look up, and returning every document in the
    project instead would silently answer a different question.
    """

    def __init__(self) -> None:
        super().__init__(
            "A document retrieval request must name at least one "
            "engineering identifier."
        )


class InvalidDocumentRetrievalLimitError(EngineeringIndexError):
    def __init__(self, limit: int, minimum: int, maximum: int) -> None:
        self.limit = limit
        self.minimum = minimum
        self.maximum = maximum

        super().__init__(
            f"Invalid document retrieval limit: {limit}. It must be "
            f"between {minimum} and {maximum}."
        )


class ExcessiveDocumentRetrievalIdentifierCountError(EngineeringIndexError):
    def __init__(self, count: int, maximum: int) -> None:
        self.count = count
        self.maximum = maximum

        super().__init__(
            f"A document retrieval request names {count} identifiers; at "
            f"most {maximum} are accepted."
        )


class DocumentRetrievalIdentifierTooLongError(EngineeringIndexError):
    def __init__(self, identifier: str, maximum: int) -> None:
        self.identifier = identifier
        self.maximum = maximum

        super().__init__(
            f"Document retrieval identifier '{identifier}' exceeds the "
            f"maximum length of {maximum} characters."
        )


class InvalidDocumentRetrievalProjectError(EngineeringIndexError):
    def __init__(self, project_id: int) -> None:
        self.project_id = project_id

        super().__init__(
            f"Invalid project id for a document retrieval request: "
            f"{project_id}. It must be positive."
        )


class UnsupportedIndexEntryKindError(EngineeringIndexError):
    def __init__(self, kind: str) -> None:
        self.kind = kind

        super().__init__(
            f"'{kind}' is not a supported Engineering Index entry kind. "
            f"Supported kinds: "
            f"{', '.join(k.value for k in EngineeringIndexEntryKind)}."
        )
