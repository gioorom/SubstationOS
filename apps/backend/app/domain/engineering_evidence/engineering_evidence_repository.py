"""
The persistence port for Engineering Evidence (Milestone 28.1).

**This is the boundary every future knowledge-construction milestone must
come through.** Entity resolution, equipment records, technical
properties, cross-document links and eventually Knowledge Graph
population all read evidence from here - not canonical text, not a
segmentation, and certainly not a document.

That is the point of the port existing. An entity resolver that read
canonical text directly would be re-deciding what counts as an
observation, in a second place, under no rule version - and two answers
about the same document would start to exist. There is deliberately no
method here that returns a page, a paragraph, a line, a span or a token:
provenance travels *on* each evidence item, so a consumer can audit an
observation without being able to re-derive one.

Evidence is stored independently of canonical text and of the Knowledge
Graph, and this port writes neither.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.engineering_evidence.evidence_models import (
    EngineeringEvidenceSet,
)


class EngineeringEvidenceRepository(ABC):
    """Stores and retrieves engineering evidence sets."""

    @abstractmethod
    def save(self, evidence_set: EngineeringEvidenceSet) -> None:
        """
        Store an evidence set.

        Implementations persist only ``is_persistable`` items - ``OBSERVED``
        and ``AMBIGUOUS``. ``REJECTED`` candidates are the extractor's
        diagnostics and must never reach storage, where a later reader
        could mistake them for engineering evidence.

        Implementations must not modify the canonical text, the document
        row, or any earlier evidence set. A document accumulates evidence
        sets - one per canonical source per policy version - and each
        stays readable, so a conclusion drawn under last year's rules
        remains explainable.
        """

        raise NotImplementedError

    @abstractmethod
    def find_for_source(
        self,
        document_id: int,
        content_checksum: str,
        extraction_policy_version: str,
    ) -> EngineeringEvidenceSet | None:
        """
        The set extracted from exactly this canonical source under
        exactly this policy, if one exists.

        This is what makes extraction idempotent: the same source and the
        same policy find the stored result rather than producing a
        second, equivalent one. A new checksum - the document changed -
        or a new policy version - the rules changed - is a different set,
        stored alongside.
        """

        raise NotImplementedError

    @abstractmethod
    def find_latest_for_document(
        self, document_id: int
    ) -> EngineeringEvidenceSet | None:
        """
        The most recently stored evidence set for this document - what a
        future consumer asking "what has been observed here?" gets.

        ``None`` when the document has never been extracted from. Not an
        error: most documents have not been, and an empty set would be
        indistinguishable from a document in which nothing was observed.
        """

        raise NotImplementedError
