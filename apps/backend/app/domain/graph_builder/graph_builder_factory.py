from __future__ import annotations

from datetime import datetime

from app.domain.canonicalization.canonicalization_models import (
    CanonicalEntityReference,
    CanonicalFact,
    CanonicalPredicate,
)
from app.domain.graph_builder.graph_builder_exceptions import (
    ConflictingAttributeOperationError,
)
from app.domain.graph_builder.graph_builder_models import (
    GraphEntityId,
    GraphNodeOperation,
    GraphNodeOperationKind,
    GraphOperation,
    GraphOperationBatch,
    GraphOperationResult,
    GraphOperationBatchSource,
    GraphRelationshipOperation,
    GraphRelationshipOperationKind,
    GraphRelationshipType,
)
from app.domain.graph_builder.graph_builder_validator import (
    GraphBuilderValidator,
)
from app.domain.proposed_claims.claim_type import ClaimType


class GraphEntityIdFactory:
    @staticmethod
    def from_canonical_reference(
        project_id: int,
        reference: CanonicalEntityReference,
    ) -> GraphEntityId:
        return GraphEntityId(
            project_id=project_id,
            entity_type=reference.entity_type,
            canonical_id=reference.canonical_id,
        )


class GraphRelationshipTypeFactory:
    @staticmethod
    def from_canonical_predicate(
        predicate: CanonicalPredicate,
    ) -> GraphRelationshipType:
        return GraphRelationshipType(value=predicate.value)


class GraphOperationFactory:
    """
    Translates one ``CanonicalFact`` into the ``GraphOperation``s it
    implies. Pure translation: it never deduplicates across facts (that
    is ``GraphOperationBatchFactory``'s job) and never touches
    persistence.
    """

    @staticmethod
    def from_canonical_fact(fact: CanonicalFact) -> tuple[GraphOperation, ...]:
        GraphBuilderValidator.validate_claim_type_supported(fact.claim_type)
        GraphBuilderValidator.validate_fact_shape(fact)

        subject_id = GraphEntityIdFactory.from_canonical_reference(
            fact.project_id,
            fact.subject,
        )

        if fact.claim_type is ClaimType.EXISTENCE:
            return (
                GraphNodeOperation(
                    kind=GraphNodeOperationKind.CREATE_NODE,
                    entity_id=subject_id,
                    attribute=None,
                    value=None,
                    source_fact_id=fact.id,  # type: ignore[arg-type]
                ),
            )

        if fact.claim_type is ClaimType.ATTRIBUTE:
            return (
                GraphNodeOperation(
                    kind=GraphNodeOperationKind.UPDATE_NODE,
                    entity_id=subject_id,
                    attribute=fact.predicate_value,
                    value=fact.object_value,
                    source_fact_id=fact.id,  # type: ignore[arg-type]
                ),
            )

        # RELATIONSHIP - validated above to have a predicate and an
        # object_entity.
        object_id = GraphEntityIdFactory.from_canonical_reference(
            fact.project_id,
            fact.object_entity,  # type: ignore[arg-type]
        )
        relationship_type = GraphRelationshipTypeFactory.from_canonical_predicate(
            fact.predicate  # type: ignore[arg-type]
        )

        return (
            GraphNodeOperation(
                kind=GraphNodeOperationKind.CREATE_NODE,
                entity_id=subject_id,
                attribute=None,
                value=None,
                source_fact_id=fact.id,  # type: ignore[arg-type]
            ),
            GraphNodeOperation(
                kind=GraphNodeOperationKind.CREATE_NODE,
                entity_id=object_id,
                attribute=None,
                value=None,
                source_fact_id=fact.id,  # type: ignore[arg-type]
            ),
            GraphRelationshipOperation(
                kind=GraphRelationshipOperationKind.CREATE_RELATIONSHIP,
                subject_id=subject_id,
                relationship_type=relationship_type,
                object_id=object_id,
                source_fact_id=fact.id,  # type: ignore[arg-type]
            ),
        )


class GraphOperationBatchFactory:
    """
    Assembles a ``GraphOperationBatch`` from a set of Canonical Facts:
    translates each fact (``GraphOperationFactory``), suppresses exact
    duplicates, rejects genuine conflicts
    (``ConflictingAttributeOperationError``), and orders the result
    deterministically - every ``CREATE_NODE``, then every
    ``UPDATE_NODE``, then every relationship operation, each group in
    the order its facts were supplied.
    """

    @staticmethod
    def build(
        *,
        source: GraphOperationBatchSource,
        facts: list[CanonicalFact],
        now: datetime,
    ) -> tuple[GraphOperationBatch, tuple[GraphOperationResult, ...]]:
        project_id = facts[0].project_id if facts else None

        create_node_ops: dict[str, GraphNodeOperation] = {}
        update_node_ops: dict[tuple[str, str], GraphNodeOperation] = {}
        relationship_ops: dict[
            tuple[str, str, str, str], GraphRelationshipOperation
        ] = {}
        results: list[GraphOperationResult] = []

        for fact in facts:
            GraphBuilderValidator.validate_same_project(
                project_id,  # type: ignore[arg-type]
                fact,
            )

            for operation in GraphOperationFactory.from_canonical_fact(fact):
                if isinstance(operation, GraphNodeOperation):
                    if operation.kind is GraphNodeOperationKind.CREATE_NODE:
                        key = operation.entity_id.value

                        if key in create_node_ops:
                            results.append(
                                GraphOperationResult(
                                    operation=operation,
                                    included=False,
                                    reason=(
                                        "duplicate node creation for "
                                        f"'{key}'"
                                    ),
                                )
                            )
                            continue

                        create_node_ops[key] = operation
                    else:
                        update_key = (
                            operation.entity_id.value,
                            operation.attribute,  # type: ignore[arg-type]
                        )
                        existing = update_node_ops.get(update_key)

                        if existing is not None:
                            if existing.value == operation.value:
                                results.append(
                                    GraphOperationResult(
                                        operation=operation,
                                        included=False,
                                        reason=(
                                            "duplicate attribute "
                                            f"assertion for "
                                            f"'{update_key[0]}"
                                            f".{update_key[1]}'"
                                        ),
                                    )
                                )
                                continue

                            raise ConflictingAttributeOperationError(
                                update_key[0],
                                update_key[1],
                                existing.value,  # type: ignore[arg-type]
                                operation.value,  # type: ignore[arg-type]
                            )

                        update_node_ops[update_key] = operation
                else:
                    relationship_key = (
                        operation.subject_id.value,
                        operation.relationship_type.value,
                        operation.object_id.value,
                        operation.kind.value,
                    )

                    if relationship_key in relationship_ops:
                        results.append(
                            GraphOperationResult(
                                operation=operation,
                                included=False,
                                reason=(
                                    "duplicate relationship "
                                    f"'{relationship_key}'"
                                ),
                            )
                        )
                        continue

                    relationship_ops[relationship_key] = operation

                results.append(
                    GraphOperationResult(
                        operation=operation,
                        included=True,
                        reason=None,
                    )
                )

        operations: tuple[GraphOperation, ...] = (
            tuple(create_node_ops.values())
            + tuple(update_node_ops.values())
            + tuple(relationship_ops.values())
        )

        batch = GraphOperationBatch(
            id=None,
            project_id=project_id,
            source=source,
            operations=operations,
            created_at=now,
        )

        return batch, tuple(results)
