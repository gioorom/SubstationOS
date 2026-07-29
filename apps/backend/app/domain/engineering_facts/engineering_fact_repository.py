"""
The persistence port for Engineering Facts (Milestone 29.2).

**This is the boundary the Knowledge Graph must come through.** A later
milestone will generate graph edges from governed facts - from these, and
from nothing else. A graph builder that reconstructed relationships from
document text would be re-deciding what counts as an association, in a
second place, under no rule version, and two answers about the same
document would exist.

Facts are stored independently of evidence, entities and the graph, and
this port writes none of them. There is no method returning canonical
text, a token or a document: a fact's support is reachable by evidence
key, and the evidence record remains the authoritative account of where
an observation came from.

**Insert-only.** There is no ``update`` and no ``delete``: a new rule
version produces a new fact set, and overwriting one would destroy the
history that makes a historical fact explainable.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.engineering_facts.fact_models import EngineeringFactSet


class EngineeringFactRepository(ABC):
    """Stores and retrieves engineering fact sets."""

    @abstractmethod
    def save(self, fact_set: EngineeringFactSet) -> None:
        """
        Store a fact set.

        Implementations must not modify the entities it was constructed
        from, the evidence beneath them, the document row, or any earlier
        fact set.
        """

        raise NotImplementedError

    @abstractmethod
    def find_for_source(
        self,
        document_id: int,
        content_checksum: str,
        resolution_policy_version: str,
        fact_policy_version: str,
    ) -> EngineeringFactSet | None:
        """
        The set constructed from exactly this entity source under exactly
        these rules, if one exists.

        This is what makes construction idempotent. The key includes the
        **entity source identity** as well as the fact policy, because a
        re-resolution under new entity rules is a different source even
        when the document has not changed.
        """

        raise NotImplementedError

    @abstractmethod
    def find_latest_for_document(
        self, document_id: int
    ) -> EngineeringFactSet | None:
        """
        The most recently stored fact set for this document.

        ``None`` when the document has never had facts constructed. Not
        an error: most have not, and an empty set would be
        indistinguishable from a document in which nothing associated.
        """

        raise NotImplementedError
