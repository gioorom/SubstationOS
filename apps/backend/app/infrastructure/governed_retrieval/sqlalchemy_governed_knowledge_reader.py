"""
SQLAlchemy adapter for ``GovernedKnowledgeReader``.

Reads the two `governed_graph_*` knowledge tables and the generation
log. It issues no ``INSERT``, ``UPDATE`` or ``DELETE``, holds no
session-level write helper, and never calls ``commit`` - an architecture
test asserts all three on the source, because "retrieval never writes"
must survive somebody adding a convenience method here.

---

## What is filtered in SQL, and what is not

Filtered in SQL: ``state``, ``kind``, ``project_id``, ``document_id``,
and identity - every one of them an exact match on an indexed column
(``ix_governed_graph_nodes_project_state`` and its edge counterpart
already cover the common shape).

Filtered in Python: **designation matching**. Deliberately, and it is
not an oversight. Folding a designation is a domain rule
(``governed_normalization``); expressing it as ``LOWER(label) = …`` or
``label ILIKE …`` would make the answer depend on the database's
collation, so the same governed graph could answer differently on
SQLite and PostgreSQL. A retrieval contract that promises determinism
cannot rest on that.

The cost is one scan of the governed nodes in scope. At present that is
a small set - the governed graph holds only what somebody has approved -
and ``performance_baseline.md`` records the measurement and the
condition under which a normalized-designation index becomes justified.

## Ordering

Every read is ordered by governed identity. That is not for
presentation - ``governed_result_assembly.order`` decides the order a
caller sees - it is so that two identical reads return the same rows in
the same sequence regardless of what the planner chose, which is what
makes determinism a property of the whole stack.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.governed_knowledge_graph.graph_generation import (
    GraphGeneration,
    GraphGenerationTrigger,
)
from app.domain.governed_knowledge_graph.graph_identity import (
    GraphEdgeId,
    GraphNodeId,
)
from app.domain.governed_knowledge_graph.graph_lifecycle import (
    GraphObjectState,
    GraphRetirement,
    GraphRetirementReason,
)
from app.domain.governed_knowledge_graph.graph_models import (
    GraphEdge,
    GraphNode,
)
from app.domain.governed_knowledge_graph.graph_provenance import (
    GraphProvenance,
)
from app.domain.governed_knowledge_graph.graph_vocabulary import (
    GraphEdgeKind,
    GraphNodeKind,
)
from app.domain.governed_retrieval.governed_knowledge_reader import (
    GovernedKnowledgeReader,
)
from app.models.governed_knowledge_graph import (
    GovernedGraphEdgeRecord,
    GovernedGraphGenerationRecord,
    GovernedGraphNodeRecord,
)

#: SQLite (and every other engine) has a bound on how many parameters
#: one statement may carry. Identity reads are chunked below it rather
#: than assuming the caller's list is short.
_IDENTITY_CHUNK = 500


class SqlAlchemyGovernedKnowledgeReader(GovernedKnowledgeReader):
    """The default ``GovernedKnowledgeReader``."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # --- Identity --------------------------------------------------------

    def find_node(self, node_id: str) -> GraphNode | None:
        record = self._session.scalar(
            select(GovernedGraphNodeRecord).where(
                GovernedGraphNodeRecord.node_id == node_id
            )
        )

        return None if record is None else _node_to_domain(record)

    def find_edge(self, edge_id: str) -> GraphEdge | None:
        record = self._session.scalar(
            select(GovernedGraphEdgeRecord).where(
                GovernedGraphEdgeRecord.edge_id == edge_id
            )
        )

        return None if record is None else _edge_to_domain(record)

    def nodes_by_identity(
        self, node_ids: tuple[str, ...]
    ) -> tuple[GraphNode, ...]:
        wanted = tuple(dict.fromkeys(node_ids))

        if not wanted:
            return ()

        records = []

        for start in range(0, len(wanted), _IDENTITY_CHUNK):
            chunk = wanted[start : start + _IDENTITY_CHUNK]
            records.extend(
                self._session.scalars(
                    select(GovernedGraphNodeRecord)
                    .where(GovernedGraphNodeRecord.node_id.in_(chunk))
                    .order_by(GovernedGraphNodeRecord.node_id.asc())
                ).all()
            )

        records.sort(key=lambda record: record.node_id)

        return tuple(_node_to_domain(record) for record in records)

    # --- Scoped reads ----------------------------------------------------

    def nodes(
        self,
        *,
        states: tuple[GraphObjectState, ...],
        kind: GraphNodeKind | None = None,
        project_id: int | None = None,
        document_id: int | None = None,
    ) -> tuple[GraphNode, ...]:
        criteria = [
            GovernedGraphNodeRecord.state.in_(
                [state.value for state in states]
            )
        ]

        if kind is not None:
            criteria.append(GovernedGraphNodeRecord.kind == kind.value)

        if project_id is not None:
            criteria.append(
                GovernedGraphNodeRecord.project_id == project_id
            )

        if document_id is not None:
            criteria.append(
                GovernedGraphNodeRecord.document_id == document_id
            )

        records = self._session.scalars(
            select(GovernedGraphNodeRecord)
            .where(*criteria)
            .order_by(GovernedGraphNodeRecord.node_id.asc())
        ).all()

        return tuple(_node_to_domain(record) for record in records)

    def edges(
        self,
        *,
        states: tuple[GraphObjectState, ...],
        kind: GraphEdgeKind | None = None,
        project_id: int | None = None,
        document_id: int | None = None,
    ) -> tuple[GraphEdge, ...]:
        criteria = [
            GovernedGraphEdgeRecord.state.in_(
                [state.value for state in states]
            )
        ]

        if kind is not None:
            criteria.append(GovernedGraphEdgeRecord.kind == kind.value)

        if project_id is not None:
            criteria.append(
                GovernedGraphEdgeRecord.project_id == project_id
            )

        if document_id is not None:
            criteria.append(
                GovernedGraphEdgeRecord.document_id == document_id
            )

        records = self._session.scalars(
            select(GovernedGraphEdgeRecord)
            .where(*criteria)
            .order_by(GovernedGraphEdgeRecord.edge_id.asc())
        ).all()

        return tuple(_edge_to_domain(record) for record in records)

    def edges_from_subjects(
        self,
        subject_node_ids: tuple[str, ...],
        *,
        states: tuple[GraphObjectState, ...],
        kind: GraphEdgeKind | None = None,
    ) -> tuple[GraphEdge, ...]:
        wanted = tuple(dict.fromkeys(subject_node_ids))

        if not wanted:
            return ()

        records = []

        for start in range(0, len(wanted), _IDENTITY_CHUNK):
            chunk = wanted[start : start + _IDENTITY_CHUNK]
            criteria = [
                GovernedGraphEdgeRecord.subject_node_id.in_(chunk),
                GovernedGraphEdgeRecord.state.in_(
                    [state.value for state in states]
                ),
            ]

            if kind is not None:
                criteria.append(GovernedGraphEdgeRecord.kind == kind.value)

            records.extend(
                self._session.scalars(
                    select(GovernedGraphEdgeRecord)
                    .where(*criteria)
                    .order_by(GovernedGraphEdgeRecord.edge_id.asc())
                ).all()
            )

        records.sort(key=lambda record: record.edge_id)

        return tuple(_edge_to_domain(record) for record in records)

    def latest_generation(self) -> GraphGeneration | None:
        record = self._session.scalar(
            select(GovernedGraphGenerationRecord)
            .order_by(
                GovernedGraphGenerationRecord.generation_number.desc()
            )
            .limit(1)
        )

        return None if record is None else _generation_to_domain(record)


# --- Mapping -------------------------------------------------------------


def _provenance_of(record) -> GraphProvenance:
    return GraphProvenance(
        statement_key=record.statement_key,
        document_id=record.document_id,
        content_checksum=record.content_checksum,
        review_id=record.review_id,
        reviewer_user_id=record.reviewer_user_id,
        reviewer_display_name=record.reviewer_display_name,
        reviewed_at=record.reviewed_at,
        semantic_rule_id=record.semantic_rule_id,
        semantic_rule_version=record.semantic_rule_version,
        semantic_contract_version=record.semantic_contract_version,
        resolution_policy_version=record.resolution_policy_version,
        fact_policy_version=record.fact_policy_version,
        semantic_policy_version=record.semantic_policy_version,
        support_fingerprint=record.support_fingerprint,
        project_id=record.project_id,
    )


def _retirement_of(record) -> GraphRetirement | None:
    if record.retirement_reason is None or record.retired_at is None:
        return None

    return GraphRetirement(
        reason=GraphRetirementReason(record.retirement_reason),
        retired_at=record.retired_at,
    )


def _node_to_domain(record: GovernedGraphNodeRecord) -> GraphNode:
    kind = GraphNodeKind(record.kind)

    return GraphNode(
        node_id=GraphNodeId(
            value=record.node_id, kind=kind, entity_key=record.entity_key
        ),
        kind=kind,
        label=record.label,
        normalized_value=record.normalized_value,
        unit=record.unit,
        state=GraphObjectState(record.state),
        provenance=_provenance_of(record),
        created_at=record.created_at,
        retirement=_retirement_of(record),
    )


def _edge_to_domain(record: GovernedGraphEdgeRecord) -> GraphEdge:
    kind = GraphEdgeKind(record.kind)

    return GraphEdge(
        edge_id=GraphEdgeId(
            value=record.edge_id,
            kind=kind,
            statement_key=record.statement_key,
        ),
        kind=kind,
        subject_node_id=record.subject_node_id,
        object_node_id=record.object_node_id,
        state=GraphObjectState(record.state),
        provenance=_provenance_of(record),
        created_at=record.created_at,
        retirement=_retirement_of(record),
    )


def _generation_to_domain(
    record: GovernedGraphGenerationRecord,
) -> GraphGeneration:
    return GraphGeneration(
        generation_id=record.id,
        generation_number=record.generation_number,
        trigger=GraphGenerationTrigger(record.trigger),
        promotion_contract_version=record.promotion_contract_version,
        created_at=record.created_at,
        node_count=record.node_count,
        edge_count=record.edge_count,
        actor_user_id=record.actor_user_id,
    )
