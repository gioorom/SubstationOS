from __future__ import annotations

from app.domain.canonicalization.canonicalization_models import CanonicalFact
from app.domain.graph_builder.graph_builder_exceptions import (
    CrossProjectGraphOperationError,
    InvalidCanonicalFactShapeError,
    MissingEntityReferenceError,
    UnsupportedClaimTypeError,
)
from app.domain.proposed_claims.claim_type import ClaimType


class GraphBuilderValidator:
    """
    Stateless validation rules for translating Canonical Facts into
    graph operations, shared by ``GraphOperationFactory`` and
    ``GraphOperationBatchFactory``.
    """

    @staticmethod
    def validate_claim_type_supported(claim_type: ClaimType) -> None:
        if claim_type not in ClaimType:
            raise UnsupportedClaimTypeError(claim_type)

    @staticmethod
    def validate_fact_shape(fact: CanonicalFact) -> None:
        if fact.claim_type is ClaimType.RELATIONSHIP:
            if fact.object_entity is None:
                raise MissingEntityReferenceError(fact.id)

            if fact.predicate_value is None:
                raise InvalidCanonicalFactShapeError(
                    fact.id,
                    fact.claim_type,
                )
        elif fact.claim_type is ClaimType.ATTRIBUTE:
            if fact.predicate_value is None or fact.object_value is None:
                raise InvalidCanonicalFactShapeError(
                    fact.id,
                    fact.claim_type,
                )

    @staticmethod
    def validate_same_project(
        expected_project_id: int,
        fact: CanonicalFact,
    ) -> None:
        if fact.project_id != expected_project_id:
            raise CrossProjectGraphOperationError(
                expected_project_id,
                fact.project_id,
                fact.id,
            )
