"""
The port through which a document's *recorded* format is read and, in one
narrow case, corrected (Milestone 25.2).

Separate from ``DocumentContentPort`` for the same reason
``DocumentStorageLocationPort`` is: that port serves the byte store, this
one serves the document registry. It is also the only write this
milestone introduces, and it is deliberately shaped so that it can do
exactly one thing - record a classified format against a document that
had none.

**Nothing calls ``record_format`` during a read.** It exists for the
backfill command, which a human runs deliberately. An ingestion that
rewrote a document row as a side effect of examining it would change
history without anyone asking.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RegisteredDocumentFormat:
    """One document as the registry holds it, for format purposes only.

    ``storage_reference`` may be ``None``: a document row can exist with
    no usable pointer to its bytes, and the backfill reports that rather
    than guessing a path."""

    document_id: int
    filename: str
    storage_reference: str | None
    stored_format: str


class DocumentFormatRegistryPort(ABC):
    """Reads documents by their recorded format, and records a format
    against one."""

    @abstractmethod
    def list_by_stored_format(
        self, stored_format: str
    ) -> tuple[RegisteredDocumentFormat, ...]:
        """
        Every document currently recorded under this format value, in
        ascending document id order.

        Ascending order is part of the contract, not an implementation
        detail: the backfill's report must read the same way twice over
        the same data.
        """

        raise NotImplementedError

    @abstractmethod
    def record_format(self, document_id: int, classified_format: str) -> None:
        """
        Record ``classified_format`` as this document's format.

        Implementations write exactly this one field. A document that no
        longer exists is left alone rather than raising - a backfill that
        crashed on a row deleted since it planned its work would abandon
        every remaining correction.
        """

        raise NotImplementedError
