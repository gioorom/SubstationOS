"""
The persistence port for canonical workbooks (ADR-0034).

**The representation is stored independently of the original workbook,
and the original is never touched.** This port offers no way to write a
document, a file or a byte of stored content - the uploaded workbook
stays exactly as it was uploaded, because it is the authoritative
artefact and this system's job is to describe it, not to edit it.

It is also the boundary every future consumer of a workbook must come
through. A consumer that opened the file itself would re-decode bytes
that were already decoded once, under whatever library version happened
to be installed that day, and would silently break the reproducibility
this context exists to establish. There is deliberately no method here
that returns a path, a handle or raw content.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.canonical_spreadsheet.canonical_spreadsheet_models import (
    CanonicalWorkbook,
)


class CanonicalWorkbookRepository(ABC):
    """Stores and retrieves canonical workbooks."""

    @abstractmethod
    def save(self, representation: CanonicalWorkbook) -> None:
        """
        Store a representation.

        Implementations must not modify the document row, the stored
        workbook, or any earlier representation. A document accumulates
        representations over its life - one per distinct content
        checksum - and each one stays readable so a conclusion drawn last
        year remains explainable.
        """

        raise NotImplementedError

    @abstractmethod
    def find_by_identity(
        self, document_id: int, artifact_identity: str
    ) -> CanonicalWorkbook | None:
        """
        The canonical workbook with exactly this deterministic identity, if one
        exists.

        **This is the reuse decision.** The identity already carries
        everything that could make a stored artifact incompatible: the
        identity of the artifact it was derived from, and every version
        this stage owns. Matching it is therefore a proof of equivalence
        rather than a guess, and no caller has to know - or copy - the
        version constants of the stages above.

        A legacy artifact stored before the identity chain existed has
        no identity and can never match here. That is deliberate: unknown
        provenance is not compatible provenance.
        """

        raise NotImplementedError

    @abstractmethod
    def find_latest_for_document(
        self, document_id: int
    ) -> CanonicalWorkbook | None:
        """
        The most recently stored representation of this document - what a
        caller asking "what does this workbook say?" gets.

        ``None`` when the document has never been read. That is not an
        error: most documents in the system have not been, and inventing
        an empty representation would be indistinguishable from a
        register that genuinely says nothing.
        """

        raise NotImplementedError
