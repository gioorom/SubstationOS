"""
The persistence port for Engineering Entities (Milestone 29.1).

**This is the boundary the Knowledge Graph will come through.** A later
milestone generates graph nodes from entities - from these, and from
nothing else. A graph builder that read evidence, canonical text or a
document directly would be re-deciding what counts as an engineering
object, in a second place, under no rule version.

Entities are stored independently of engineering evidence and of the
graph, and this port writes neither. There is no method here that returns
canonical text, a token or a document: an entity's contributing evidence
is reachable by key, and the evidence record remains the authoritative
account of where an observation came from.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.engineering_entities.entity_models import (
    EngineeringEntitySet,
)


class EngineeringEntityRepository(ABC):
    """Stores and retrieves engineering entity sets."""

    @abstractmethod
    def save(self, entity_set: EngineeringEntitySet) -> None:
        """
        Store an entity set.

        Implementations must not modify the evidence it was resolved
        from, the document row, or any earlier entity set. A document
        accumulates entity sets - one per evidence source per resolution
        policy - and each stays readable, so a hypothesis drawn under
        last year's rules remains explainable.
        """

        raise NotImplementedError

    @abstractmethod
    def find_by_identity(
        self, document_id: int, artifact_identity: str
    ) -> EngineeringEntitySet | None:
        """
        The entity set with exactly this deterministic identity, if one
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
    ) -> EngineeringEntitySet | None:
        """
        The most recently stored entity set for this document.

        ``None`` when the document has never been resolved. Not an
        error: most documents have not been, and an empty set would be
        indistinguishable from a document in which nothing was found.
        """

        raise NotImplementedError
