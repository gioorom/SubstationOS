from __future__ import annotations

from datetime import datetime

import pytest

from app.domain.canonicalization.canonicalization_models import (
    CanonicalEntityReference,
    CanonicalFact,
    CanonicalPredicate,
    CanonicalProvenance,
    CanonicalValue,
)
from app.domain.engineering_index.engineering_index_locator import (
    IndexEntryLocator,
    IndexEntryLocatorKind,
)
from app.domain.graph_builder.graph_builder_exceptions import (
    CrossProjectGraphOperationError,
    InvalidCanonicalFactShapeError,
    MissingEntityReferenceError,
)
from app.domain.graph_builder.graph_builder_validator import (
    GraphBuilderValidator,
)
from app.domain.proposed_claims.claim_type import ClaimType
from app.domain.proposed_claims.proposed_claim_models import (
    EvidenceReference,
)

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)


def _evidence() -> tuple[EvidenceReference, ...]:
    return (
        EvidenceReference(
            engineering_index_entry_id=1,
            document_id=5,
            locator=IndexEntryLocator(
                kind=IndexEntryLocatorKind.PAGE,
                value="3",
            ),
        ),
    )


def _fact(
    *,
    claim_type: ClaimType,
    predicate: CanonicalPredicate | None = None,
    object_: CanonicalEntityReference | CanonicalValue | None = None,
    project_id: int = 10,
) -> CanonicalFact:
    return CanonicalFact(
        id=1,
        project_id=project_id,
        claim_type=claim_type,
        subject=CanonicalEntityReference(
            entity_type="CABLE",
            canonical_id="C-295",
        ),
        predicate=predicate,
        object=object_,
        proposed_claim_id=1,
        review_candidate_id=1,
        evidence=_evidence(),
        provenance=CanonicalProvenance(
            reviewed_by="engineer.smith",
            reviewed_at=CREATED_AT,
        ),
        created_at=CREATED_AT,
    )


def test_validate_fact_shape_accepts_a_well_formed_relationship() -> None:
    GraphBuilderValidator.validate_fact_shape(
        _fact(
            claim_type=ClaimType.RELATIONSHIP,
            predicate=CanonicalPredicate(value="FEEDS"),
            object_=CanonicalEntityReference(
                entity_type="TRANSFORMER",
                canonical_id="TR-02",
            ),
        )
    )


def test_validate_fact_shape_rejects_a_relationship_missing_its_object() -> (
    None
):
    with pytest.raises(MissingEntityReferenceError):
        GraphBuilderValidator.validate_fact_shape(
            _fact(
                claim_type=ClaimType.RELATIONSHIP,
                predicate=CanonicalPredicate(value="FEEDS"),
                object_=None,
            )
        )


def test_validate_fact_shape_rejects_an_attribute_missing_its_value() -> (
    None
):
    with pytest.raises(InvalidCanonicalFactShapeError):
        GraphBuilderValidator.validate_fact_shape(
            _fact(
                claim_type=ClaimType.ATTRIBUTE,
                predicate=CanonicalPredicate(value="rated_voltage"),
                object_=None,
            )
        )


def test_validate_fact_shape_accepts_existence_with_no_predicate() -> None:
    GraphBuilderValidator.validate_fact_shape(
        _fact(claim_type=ClaimType.EXISTENCE)
    )


def test_validate_same_project_accepts_a_matching_fact() -> None:
    GraphBuilderValidator.validate_same_project(
        10,
        _fact(claim_type=ClaimType.EXISTENCE, project_id=10),
    )


def test_validate_same_project_rejects_a_mismatch() -> None:
    with pytest.raises(CrossProjectGraphOperationError):
        GraphBuilderValidator.validate_same_project(
            10,
            _fact(claim_type=ClaimType.EXISTENCE, project_id=20),
        )
