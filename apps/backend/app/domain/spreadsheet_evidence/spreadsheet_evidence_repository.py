"""
The persistence port for spreadsheet evidence (ADR-0034).

Evidence is stored independently of the canonical workbook and of the
Knowledge Graph, and this port writes neither. It offers no method
returning a worksheet, a row, a cell or a byte of stored content:
provenance travels *on* each evidence item, so a consumer can audit an
observation without being able to re-derive one.

**Nothing downstream consumes this store yet, and that is deliberate.**
Entity resolution reads the PDF family's evidence repository and will
not see a spreadsheet observation. Resolving entities over cell-scoped
evidence is a semantic question with its own review obligations, and
ADR-0034 records the gap as debt rather than closing it here by
guessing. This port exists so the milestone that does close it has one
boundary to come through.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.spreadsheet_evidence.spreadsheet_evidence_models import (
    SpreadsheetEvidenceSet,
)


class SpreadsheetEvidenceRepository(ABC):
    """Stores and retrieves spreadsheet evidence sets."""

    @abstractmethod
    def save(self, evidence_set: SpreadsheetEvidenceSet) -> None:
        """
        Store an evidence set.

        Implementations persist only ``is_persistable`` items -
        ``OBSERVED`` and ``AMBIGUOUS``. ``REJECTED`` candidates are the
        extractor's diagnostics and must never reach storage, where a
        later reader could mistake them for engineering evidence.

        Implementations must not modify the canonical workbook, the
        document row, or any earlier evidence set. A document
        accumulates evidence sets - one per workbook recording per policy
        version - and each stays readable, so a conclusion drawn under
        last year's rules remains explainable.
        """

        raise NotImplementedError

    @abstractmethod
    def find_by_identity(
        self, document_id: int, artifact_identity: str
    ) -> SpreadsheetEvidenceSet | None:
        """
        The evidence set with exactly this deterministic identity, if one
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
    ) -> SpreadsheetEvidenceSet | None:
        """
        The most recently stored evidence set for this document - what a
        future consumer asking "what has been observed in this workbook?"
        gets.

        ``None`` when the document has never been extracted from. Not an
        error: most documents have not been, and an empty set would be
        indistinguishable from a workbook in which nothing was observed.
        """

        raise NotImplementedError
