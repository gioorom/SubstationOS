from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.proposed_claims.claim_type import ClaimType
from app.domain.proposed_claims.proposed_claim_models import (
    ClaimObject,
    ClaimPredicate,
    ClaimSubject,
    EvidenceReference,
    ProposedClaim,
)


class ProposedClaimRepository(ABC):
    """
    Port for persisting and querying Proposed Claims. The domain
    depends only on this contract; an infrastructure adapter (e.g.
    ``SqlAlchemyProposedClaimRepository``) provides the implementation.
    """

    @abstractmethod
    def create(self, claim: ProposedClaim) -> ProposedClaim:
        """Insert a new claim (``id`` must be ``None``), together with
        its evidence, and return it with ``id`` populated."""

        raise NotImplementedError

    @abstractmethod
    def get_by_id(self, claim_id: int) -> ProposedClaim | None:
        """Return the claim with this id, or ``None`` if none exists."""

        raise NotImplementedError

    @abstractmethod
    def find_duplicate(
        self,
        project_id: int,
        claim_type: ClaimType,
        subject: ClaimSubject,
        predicate: ClaimPredicate | None,
        object_: ClaimObject | None,
    ) -> ProposedClaim | None:
        """
        Return the existing claim in this project asserting the same
        type/subject/predicate/object, if one exists - used to enforce
        "no duplicate claims".
        """

        raise NotImplementedError

    @abstractmethod
    def list_by_project(self, project_id: int) -> list[ProposedClaim]:
        """Return every claim proposed in this project."""

        raise NotImplementedError

    @abstractmethod
    def list_by_document(self, document_id: int) -> list[ProposedClaim]:
        """Return every claim citing at least one evidence entry from
        this document."""

        raise NotImplementedError

    @abstractmethod
    def replace_evidence(
        self,
        claim_id: int,
        evidence: list[EvidenceReference],
    ) -> ProposedClaim:
        """
        Atomically replace every evidence reference for this claim: the
        previous references are removed and the new ones inserted as a
        single transaction.
        """

        raise NotImplementedError

    @abstractmethod
    def delete(self, claim_id: int) -> None:
        """Remove this claim and its evidence references."""

        raise NotImplementedError
