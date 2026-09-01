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
    def find_by_identity(
        self, document_id: int, artifact_identity: str
    ) -> EngineeringFactSet | None:
        """
        The fact set with exactly this deterministic identity, if one
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
    ) -> EngineeringFactSet | None:
        """
        The most recently stored fact set for this document.

        ``None`` when the document has never had facts constructed. Not
        an error: most have not, and an empty set would be
        indistinguishable from a document in which nothing associated.
        """

        raise NotImplementedError
