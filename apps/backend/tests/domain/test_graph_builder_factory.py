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
    ConflictingAttributeOperationError,
    CrossProjectGraphOperationError,
)
from app.domain.graph_builder.graph_builder_factory import (
    GraphOperationBatchFactory,
    GraphOperationFactory,
)
from app.domain.graph_builder.graph_builder_models import (
    GraphNodeOperation,
    GraphNodeOperationKind,
    GraphOperationBatchScope,
    GraphOperationBatchSource,
    GraphRelationshipOperation,
    GraphRelationshipOperationKind,
)
from app.domain.proposed_claims.claim_type import ClaimType
from app.domain.proposed_claims.proposed_claim_models import (
    EvidenceReference,
)

CREATED_AT = datetime(2026, 1, 1, 10, 0, 0)
REVIEWED_AT = datetime(2026, 1, 2, 9, 0, 0)

_SOURCE = GraphOperationBatchSource(
    scope=GraphOperationBatchScope.PROJECT,
    scope_id=10,
)


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
    fact_id: int,
    project_id: int = 10,
    claim_type: ClaimType = ClaimType.EXISTENCE,
    subject: CanonicalEntityReference | None = None,
    predicate: CanonicalPredicate | None = None,
    object_: CanonicalEntityReference | CanonicalValue | None = None,
) -> CanonicalFact:
    return CanonicalFact(
        id=fact_id,
        project_id=project_id,
        claim_type=claim_type,
        subject=subject
        or CanonicalEntityReference(
            entity_type="CABLE",
            canonical_id="C-295",
        ),
        predicate=predicate,
        object=object_,
        proposed_claim_id=fact_id,
        review_candidate_id=fact_id,
        evidence=_evidence(),
        provenance=CanonicalProvenance(
            reviewed_by="engineer.smith",
            reviewed_at=REVIEWED_AT,
        ),
        created_at=CREATED_AT,
    )


def _transformer() -> CanonicalEntityReference:
    return CanonicalEntityReference(
        entity_type="TRANSFORMER",
        canonical_id="TR-02",
    )


# --- GraphOperationFactory --------------------------------------------


def test_existence_fact_produces_one_create_node_operation() -> None:
    operations = GraphOperationFactory.from_canonical_fact(
        _fact(fact_id=1, claim_type=ClaimType.EXISTENCE)
    )

    assert len(operations) == 1
    operation = operations[0]
    assert isinstance(operation, GraphNodeOperation)
    assert operation.kind is GraphNodeOperationKind.CREATE_NODE
    assert operation.entity_id.value == "10:CABLE:C-295"
    assert operation.attribute is None
    assert operation.value is None


def test_attribute_fact_produces_one_update_node_operation() -> None:
    operations = GraphOperationFactory.from_canonical_fact(
        _fact(
            fact_id=1,
            claim_type=ClaimType.ATTRIBUTE,
            predicate=CanonicalPredicate(value="rated_voltage"),
            object_=CanonicalValue(value="132kV"),
        )
    )

    assert len(operations) == 1
    operation = operations[0]
    assert isinstance(operation, GraphNodeOperation)
    assert operation.kind is GraphNodeOperationKind.UPDATE_NODE
    assert operation.attribute == "rated_voltage"
    assert operation.value == "132kV"


def test_relationship_fact_produces_two_creates_and_one_relationship() -> (
    None
):
    operations = GraphOperationFactory.from_canonical_fact(
        _fact(
            fact_id=1,
            claim_type=ClaimType.RELATIONSHIP,
            predicate=CanonicalPredicate(value="FEEDS"),
            object_=_transformer(),
        )
    )

    assert len(operations) == 3
    node_ops = [op for op in operations if isinstance(op, GraphNodeOperation)]
    relationship_ops = [
        op for op in operations if isinstance(op, GraphRelationshipOperation)
    ]
    assert len(node_ops) == 2
    assert all(
        op.kind is GraphNodeOperationKind.CREATE_NODE for op in node_ops
    )
    assert len(relationship_ops) == 1
    relationship = relationship_ops[0]
    assert relationship.kind is GraphRelationshipOperationKind.CREATE_RELATIONSHIP
    assert relationship.subject_id.value == "10:CABLE:C-295"
    assert relationship.object_id.value == "10:TRANSFORMER:TR-02"
    assert relationship.relationship_type.value == "FEEDS"


# --- GraphOperationBatchFactory ----------------------------------------


def test_build_suppresses_duplicate_create_node_operations() -> None:
    fact_a = _fact(fact_id=1, claim_type=ClaimType.EXISTENCE)
    fact_b = _fact(fact_id=2, claim_type=ClaimType.EXISTENCE)

    batch, results = GraphOperationBatchFactory.build(
        source=_SOURCE,
        facts=[fact_a, fact_b],
        now=CREATED_AT,
    )

    assert len(batch.operations) == 1
    suppressed = [result for result in results if not result.included]
    assert len(suppressed) == 1
    assert "duplicate" in suppressed[0].reason


def test_build_suppresses_an_identical_repeated_attribute_assertion() -> (
    None
):
    fact_a = _fact(
        fact_id=1,
        claim_type=ClaimType.ATTRIBUTE,
        predicate=CanonicalPredicate(value="rated_voltage"),
        object_=CanonicalValue(value="132kV"),
    )
    fact_b = _fact(
        fact_id=2,
        claim_type=ClaimType.ATTRIBUTE,
        predicate=CanonicalPredicate(value="rated_voltage"),
        object_=CanonicalValue(value="132kV"),
    )

    batch, results = GraphOperationBatchFactory.build(
        source=_SOURCE,
        facts=[fact_a, fact_b],
        now=CREATED_AT,
    )

    assert len(batch.operations) == 1
    assert sum(1 for result in results if not result.included) == 1


def test_build_rejects_conflicting_attribute_assertions() -> None:
    fact_a = _fact(
        fact_id=1,
        claim_type=ClaimType.ATTRIBUTE,
        predicate=CanonicalPredicate(value="rated_voltage"),
        object_=CanonicalValue(value="132kV"),
    )
    fact_b = _fact(
        fact_id=2,
        claim_type=ClaimType.ATTRIBUTE,
        predicate=CanonicalPredicate(value="rated_voltage"),
        object_=CanonicalValue(value="150kV"),
    )

    with pytest.raises(ConflictingAttributeOperationError):
        GraphOperationBatchFactory.build(
            source=_SOURCE,
            facts=[fact_a, fact_b],
            now=CREATED_AT,
        )


def test_build_suppresses_duplicate_relationships() -> None:
    fact_a = _fact(
        fact_id=1,
        claim_type=ClaimType.RELATIONSHIP,
        predicate=CanonicalPredicate(value="FEEDS"),
        object_=_transformer(),
    )
    fact_b = _fact(
        fact_id=2,
        claim_type=ClaimType.RELATIONSHIP,
        predicate=CanonicalPredicate(value="FEEDS"),
        object_=_transformer(),
    )

    batch, _results = GraphOperationBatchFactory.build(
        source=_SOURCE,
        facts=[fact_a, fact_b],
        now=CREATED_AT,
    )

    relationship_ops = [
        op
        for op in batch.operations
        if isinstance(op, GraphRelationshipOperation)
    ]
    assert len(relationship_ops) == 1


def test_build_orders_creates_before_updates_before_relationships() -> (
    None
):
    relationship_fact = _fact(
        fact_id=1,
        claim_type=ClaimType.RELATIONSHIP,
        predicate=CanonicalPredicate(value="FEEDS"),
        object_=_transformer(),
    )
    attribute_fact = _fact(
        fact_id=2,
        subject=_transformer(),
        claim_type=ClaimType.ATTRIBUTE,
        predicate=CanonicalPredicate(value="rated_voltage"),
        object_=CanonicalValue(value="132kV"),
    )

    batch, _results = GraphOperationBatchFactory.build(
        source=_SOURCE,
        # Relationship fact processed first on purpose - ordering must
        # not depend on input order.
        facts=[relationship_fact, attribute_fact],
        now=CREATED_AT,
    )

    kinds = [
        (
            "node:" + op.kind.value
            if isinstance(op, GraphNodeOperation)
            else "relationship:" + op.kind.value
        )
        for op in batch.operations
    ]

    create_indexes = [
        i for i, k in enumerate(kinds) if k == "node:create_node"
    ]
    update_indexes = [
        i for i, k in enumerate(kinds) if k == "node:update_node"
    ]
    relationship_indexes = [
        i for i, k in enumerate(kinds) if k.startswith("relationship:")
    ]

    assert max(create_indexes) < min(update_indexes)
    assert max(update_indexes) < min(relationship_indexes)


def test_build_is_deterministic_across_repeated_calls() -> None:
    facts = [
        _fact(fact_id=1, claim_type=ClaimType.EXISTENCE),
        _fact(
            fact_id=2,
            subject=_transformer(),
            claim_type=ClaimType.EXISTENCE,
        ),
        _fact(
            fact_id=3,
            claim_type=ClaimType.RELATIONSHIP,
            predicate=CanonicalPredicate(value="FEEDS"),
            object_=_transformer(),
        ),
    ]

    first, _ = GraphOperationBatchFactory.build(
        source=_SOURCE,
        facts=facts,
        now=CREATED_AT,
    )
    second, _ = GraphOperationBatchFactory.build(
        source=_SOURCE,
        facts=facts,
        now=CREATED_AT,
    )

    assert first.operations == second.operations


def test_build_rejects_a_cross_project_fact() -> None:
    fact_a = _fact(fact_id=1, project_id=10, claim_type=ClaimType.EXISTENCE)
    fact_b = _fact(fact_id=2, project_id=20, claim_type=ClaimType.EXISTENCE)

    with pytest.raises(CrossProjectGraphOperationError):
        GraphOperationBatchFactory.build(
            source=_SOURCE,
            facts=[fact_a, fact_b],
            now=CREATED_AT,
        )


def test_build_with_no_facts_produces_an_empty_batch_with_no_project() -> (
    None
):
    batch, results = GraphOperationBatchFactory.build(
        source=GraphOperationBatchSource(
            scope=GraphOperationBatchScope.DOCUMENT,
            scope_id=99,
        ),
        facts=[],
        now=CREATED_AT,
    )

    assert batch.operations == ()
    assert batch.project_id is None
    assert results == ()
