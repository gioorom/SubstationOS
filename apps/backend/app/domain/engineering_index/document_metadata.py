"""
The document-metadata read the Engineering Index needs when it *answers*
a document lookup, as opposed to when it *records* a mention
(``document_lookup.py``).

Deliberately still not a full Document domain bounded context - no such
context exists (see
``app.domain.project.project_document_scope.DocumentScope``'s placement
note). ``DocumentMetadata`` restates exactly the already-persisted
fields a document reference exposes to an engineer, and nothing more: no
relevance, no classification, no interpretation of the document's
contents. Anything an engineer sees here is a field a repository already
holds.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domain.project.project_document_scope import DocumentScope


@dataclass(frozen=True, slots=True)
class DocumentMetadata:
    """
    The persisted, human-meaningful identity of one document.

    ``title`` is the document's stored filename - today the only
    human-readable name the persistence layer holds. It is exposed under
    the domain name an engineer uses ("which document is this?") rather
    than under the storage name, but no title is ever invented or
    derived from the file's contents.

    ``document_format``/``document_category`` are plain strings carrying
    the values the persistence layer already stores (``pdf``, ``dwg``,
    ``functional_schematic``, ...). They are deliberately not restated as
    domain enums here: no bounded context owns that vocabulary yet, and
    duplicating the persistence enums would create two definitions of the
    same closed set that could silently drift apart.
    """

    document_id: int
    project_id: int | None
    title: str
    document_format: str
    document_category: str
    revision: str
    scope: DocumentScope


class DocumentMetadataPort(ABC):
    """
    Port for reading the presentable metadata of already-identified
    documents. An infrastructure adapter implements it against the
    existing ``app.models.document.Document`` persistence model.

    The lookup is deliberately *batch-shaped*: a document lookup resolves
    the metadata of every document its index entries point at in one
    read, never one query per document inside a loop.
    """

    @abstractmethod
    def find_many(
        self, document_ids: tuple[int, ...]
    ) -> tuple[DocumentMetadata, ...]:
        """
        Return the metadata of every requested document that exists, in
        ascending ``document_id`` order. A document id with no
        corresponding record is simply absent from the result - it is
        never reported as an error and never filled in with placeholder
        values, because an Engineering Index entry is a freely rebuildable
        lead that may outlive the document row it points at (ADR-0002).
        """

        raise NotImplementedError
