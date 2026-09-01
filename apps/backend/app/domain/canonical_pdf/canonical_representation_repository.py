"""
The persistence port for canonical representations (Milestone 26.1).

**The representation is stored independently of the original PDF, and the
original is never touched.** This port offers no way to write a document,
a file or a byte of stored content - the uploaded PDF stays exactly as it
was uploaded, because it is the authoritative artefact and this system's
job is to describe it, not to edit it.

It is also the boundary every future extraction milestone must come
through. An extractor that opened the PDF itself would re-decode bytes
that were already decoded once, under whatever library version happened
to be installed that day, and would silently break the reproducibility
this whole milestone exists to establish. There is deliberately no method
here that returns a path, a handle or raw content.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.canonical_pdf.canonical_pdf_models import (
    CanonicalPdfDocument,
)


class CanonicalRepresentationRepository(ABC):
    """Stores and retrieves canonical representations."""

    @abstractmethod
    def save(self, representation: CanonicalPdfDocument) -> None:
        """
        Store a representation.

        Implementations must not modify the document row, the stored PDF,
        or any earlier representation. A document accumulates
        representations over its life - one per distinct content
        checksum - and each one stays readable so a conclusion drawn last
        year remains explainable.
        """

        raise NotImplementedError

    @abstractmethod
    def find_by_identity(
        self, document_id: int, artifact_identity: str
    ) -> CanonicalPdfDocument | None:
        """
        The canonical representation with exactly this deterministic identity, if one
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
    ) -> CanonicalPdfDocument | None:
        """
        The most recently stored representation of this document - what a
        caller asking "what does this document say?" gets.

        ``None`` when the document has never been canonicalised. That is
        not an error: most documents in the system have not been, and
        inventing an empty representation would be indistinguishable from
        a document that genuinely says nothing.
        """

        raise NotImplementedError
