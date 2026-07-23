from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domain.project.project_document_scope import DocumentScope
from app.domain.project.project_lifecycle import ProjectLifecycleState


@dataclass(frozen=True, slots=True)
class DocumentIndexContext:
    """
    The minimal snapshot of a Document, and its owning Project, that the
    Engineering Index needs to decide whether an entry may be registered
    against it: is the document PROJECT-scoped (ADR-0005), and is its
    Project currently mutable (Project Lifecycle, Milestone 8)?

    Deliberately not a full Document domain model - no such bounded
    context exists yet (see
    app.domain.project.project_document_scope.DocumentScope's placement
    note); this is the narrow read this bounded context requires.
    """

    document_id: int
    project_id: int | None
    scope: DocumentScope
    project_lifecycle_state: ProjectLifecycleState | None


class DocumentLookupPort(ABC):
    """
    Port for reading the indexing-relevant context of a Document. An
    infrastructure adapter implements this against the existing
    ``app.models.document.Document`` / ``app.models.project.Project``
    persistence models.
    """

    @abstractmethod
    def find(self, document_id: int) -> DocumentIndexContext | None:
        """Return the indexing context for this document, or ``None``
        if no document with this id exists."""

        raise NotImplementedError
