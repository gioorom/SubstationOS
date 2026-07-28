"""
The persistence port for canonical text segmentations (Milestone 27.1).

Stored **separately from the Canonical PDF Representation**, which it
never modifies. The representation stays the record of what the parser
observed; the segmentation is a derived structure over it, and keeping
the two apart means a segmentation can be rebuilt - under new rules, with
a new ``segmentation_version`` - without touching the thing it was
derived from.

This port is also the boundary every future extraction milestone comes
through. There is deliberately no method here that returns a page, a
block, a bounding box or anything else from the PDF layer: an extractor
that reached back into the representation's geometry would be re-deriving
structure this layer already settled, and two answers about the same
document would start to exist.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.canonical_text.canonical_text_models import (
    CanonicalTextDocument,
)


class CanonicalTextRepository(ABC):
    """Stores and retrieves canonical text segmentations."""

    @abstractmethod
    def save(self, segmentation: CanonicalTextDocument) -> None:
        """
        Store a segmentation.

        Implementations must not modify the canonical representation, the
        document row, or the stored PDF. A document accumulates
        segmentations - one per representation per segmentation version -
        and each stays readable, so a conclusion drawn under last year's
        rules remains explainable.
        """

        raise NotImplementedError

    @abstractmethod
    def find_for_representation(
        self,
        document_id: int,
        content_checksum: str,
        segmentation_version: str,
    ) -> CanonicalTextDocument | None:
        """
        The segmentation built from exactly this representation under
        exactly these rules, if one exists.

        This is what makes segmentation idempotent: the same
        representation and the same version find the stored result rather
        than producing a second, equivalent one. A new checksum - the
        document changed - or a new segmentation version - the rules
        changed - is a different segmentation, stored alongside.
        """

        raise NotImplementedError

    @abstractmethod
    def find_latest_for_document(
        self, document_id: int
    ) -> CanonicalTextDocument | None:
        """
        The most recently stored segmentation of this document - what a
        future extractor asking "what does this document say?" gets.

        ``None`` when the document has never been segmented. Not an
        error: most documents have not been, and an empty segmentation
        would be indistinguishable from a document that genuinely says
        nothing.
        """

        raise NotImplementedError
