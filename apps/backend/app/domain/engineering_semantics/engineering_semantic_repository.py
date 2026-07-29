"""
The persistence port for Engineering Semantic Statements
(Milestone 30.1).

**This is the boundary the Knowledge Graph will be built from.**
Semantic Interpretation assigns engineering meaning; the Knowledge Graph
stores interpreted knowledge; reasoning consumes it. Each of those is a
distinct responsibility, and this port is where the first hands over to
the second.

A graph builder that read facts, entities or document text directly would
be assigning meaning in a second place, under no rule version - and two
accounts of what a document means would exist.

Statements are stored independently of facts, entities, evidence and the
graph, and this port writes none of them. There is no method returning a
fact payload, an entity or a token: a statement's support is reachable by
fact key, and the fact remains the authoritative account of why two
entities are related at all.

**Insert-only.** There is no ``update`` and no ``delete``: a new rule
version produces a new semantic set, and overwriting one would destroy
the history that makes a historical interpretation explainable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.engineering_semantics.semantic_models import (
    EngineeringSemanticSet,
)


class EngineeringSemanticRepository(ABC):
    """Stores and retrieves engineering semantic sets."""

    @abstractmethod
    def save(self, semantic_set: EngineeringSemanticSet) -> None:
        """
        Store a semantic set.

        Implementations must not modify the facts it was interpreted
        from, the layers beneath them, the document row, or any earlier
        semantic set.
        """

        raise NotImplementedError

    @abstractmethod
    def find_for_source(
        self,
        document_id: int,
        content_checksum: str,
        resolution_policy_version: str,
        fact_policy_version: str,
        semantic_policy_version: str,
    ) -> EngineeringSemanticSet | None:
        """
        The set interpreted from exactly this fact source under exactly
        these rules, if one exists.

        This is what makes interpretation idempotent. The key includes
        the **whole upstream source identity**, because a re-resolution
        or a re-construction is a different source even when the document
        has not changed.
        """

        raise NotImplementedError

    @abstractmethod
    def find_latest_for_document(
        self, document_id: int
    ) -> EngineeringSemanticSet | None:
        """
        The most recently stored semantic set for this document.

        ``None`` when the document has never been interpreted. Not an
        error: most have not, and an empty set would be
        indistinguishable from a document in which nothing meant
        anything.
        """

        raise NotImplementedError
