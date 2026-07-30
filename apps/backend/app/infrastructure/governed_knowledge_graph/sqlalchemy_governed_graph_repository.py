"""
SQLAlchemy adapter for the ``GovernedGraphRepository`` port.

Writes the three `governed_graph_*` tables and nothing else. It touches
no semantic table, no review table and no document table: the promotion
service reads those and hands this adapter finished projections.

Every read is ordered deterministically. Two reads of the same graph
return the same list in the same order - which is what lets a query
result be attached to an engineering query, and what makes comparing two
rebuilds a meaningful test rather than a flaky one.
"""

from __future__ import annotations

from sqlalchemy import delete, func, or_, select
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
from app.domain.governed_knowledge_graph.graph_repository import (
    GovernedGraphRepository,
)
from app.domain.governed_knowledge_graph.graph_vocabulary import (
    GraphEdgeKind,
    GraphNodeKind,
)
from app.domain.shared_kernel.pagination import Page, PageRequest
from app.models.governed_knowledge_graph import (
    GovernedGraphEdgeRecord,
    GovernedGraphGenerationRecord,
    GovernedGraphNodeRecord,
)


class SqlAlchemyGovernedGraphRepository(GovernedGraphRepository):
    """The default ``GovernedGraphRepository``."""

    def __init__(self, session: Session) -> None:
        self._session = session

    # --- Writing ---------------------------------------------------------

    def upsert_node(self, node: GraphNode) -> GraphNode:
        record = self._session.scalar(
            select(GovernedGraphNodeRecord).where(
                GovernedGraphNodeRecord.node_id == node.node_id.value
            )
        )

        if record is None:
            record = GovernedGraphNodeRecord(node_id=node.node_id.value)
            self._session.add(record)

        _apply_node(record, node)
        self._session.commit()

        return _node_to_domain(record)

    def upsert_edge(self, edge: GraphEdge) -> GraphEdge:
        record = self._session.scalar(
            select(GovernedGraphEdgeRecord).where(
                GovernedGraphEdgeRecord.edge_id == edge.edge_id.value
            )
        )

        if record is None:
            record = GovernedGraphEdgeRecord(edge_id=edge.edge_id.value)
            self._session.add(record)

        _apply_edge(record, edge)
        self._session.commit()

        return _edge_to_domain(record)

    def record_generation(
        self, generation: GraphGeneration
    ) -> GraphGeneration:
        record = GovernedGraphGenerationRecord(
            generation_number=generation.generation_number,
            trigger=generation.trigger.value,
            promotion_contract_version=(
                generation.promotion_contract_version
            ),
            created_at=generation.created_at,
            node_count=generation.node_count,
            edge_count=generation.edge_count,
            actor_user_id=generation.actor_user_id,
        )

        self._session.add(record)
        self._session.commit()

        return _generation_to_domain(record)

    def clear(self) -> None:
        """
        Drops every node and edge. Generations are kept.

        The generation log is the record of *when the projection was
        recomputed*, and a rebuild that erased its own history would make
        "when did this graph last change shape?" unanswerable.
        """

        self._session.execute(delete(GovernedGraphEdgeRecord))
        self._session.execute(delete(GovernedGraphNodeRecord))
        self._session.commit()

    # --- Reading ---------------------------------------------------------

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

    def find_edge_by_statement(
        self, statement_key: str
    ) -> GraphEdge | None:
        record = self._session.scalar(
            select(GovernedGraphEdgeRecord).where(
                GovernedGraphEdgeRecord.statement_key == statement_key
            )
        )

        return None if record is None else _edge_to_domain(record)

    def list_nodes(
        self,
        *,
        page: PageRequest,
        kind: str | None = None,
        project_id: int | None = None,
        document_id: int | None = None,
        label_search: str | None = None,
        include_historical: bool = False,
    ) -> Page[GraphNode]:
        criteria = []

        if not include_historical:
            criteria.append(
                GovernedGraphNodeRecord.state
                == GraphObjectState.ACTIVE.value
            )

        if kind is not None:
            criteria.append(GovernedGraphNodeRecord.kind == kind)

        if project_id is not None:
            criteria.append(
                GovernedGraphNodeRecord.project_id == project_id
            )

        if document_id is not None:
            criteria.append(
                GovernedGraphNodeRecord.document_id == document_id
            )

        if label_search:
            term = f"%{label_search}%"
            criteria.append(
                or_(
                    GovernedGraphNodeRecord.label.ilike(term),
                    GovernedGraphNodeRecord.normalized_value.ilike(term),
                )
            )

        total = int(
            self._session.scalar(
                select(func.count())
                .select_from(GovernedGraphNodeRecord)
                .where(*criteria)
            )
            or 0
        )

        records = self._session.scalars(
            select(GovernedGraphNodeRecord)
            .where(*criteria)
            # `node_id` breaks the tie, so paging over a non-unique sort
            # key cannot show one row twice and skip another.
            .order_by(
                GovernedGraphNodeRecord.label.asc(),
                GovernedGraphNodeRecord.node_id.asc(),
            )
            .offset(page.offset)
            .limit(page.limit)
        ).all()

        return Page.of(
            items=tuple(_node_to_domain(record) for record in records),
            total=total,
            request=page,
        )

    def list_edges(
        self,
        *,
        page: PageRequest,
        kind: str | None = None,
        project_id: int | None = None,
        document_id: int | None = None,
        include_historical: bool = False,
    ) -> Page[GraphEdge]:
        criteria = []

        if not include_historical:
            criteria.append(
                GovernedGraphEdgeRecord.state
                == GraphObjectState.ACTIVE.value
            )

        if kind is not None:
            criteria.append(GovernedGraphEdgeRecord.kind == kind)

        if project_id is not None:
            criteria.append(
                GovernedGraphEdgeRecord.project_id == project_id
            )

        if document_id is not None:
            criteria.append(
                GovernedGraphEdgeRecord.document_id == document_id
            )

        total = int(
            self._session.scalar(
                select(func.count())
                .select_from(GovernedGraphEdgeRecord)
                .where(*criteria)
            )
            or 0
        )

        records = self._session.scalars(
            select(GovernedGraphEdgeRecord)
            .where(*criteria)
            .order_by(GovernedGraphEdgeRecord.edge_id.asc())
            .offset(page.offset)
            .limit(page.limit)
        ).all()

        return Page.of(
            items=tuple(_edge_to_domain(record) for record in records),
            total=total,
            request=page,
        )

    def edges_for_node(
        self, node_id: str, *, include_historical: bool = False
    ) -> tuple[GraphEdge, ...]:
        criteria = [
            or_(
                GovernedGraphEdgeRecord.subject_node_id == node_id,
                GovernedGraphEdgeRecord.object_node_id == node_id,
            )
        ]

        if not include_historical:
            criteria.append(
                GovernedGraphEdgeRecord.state
                == GraphObjectState.ACTIVE.value
            )

        records = self._session.scalars(
            select(GovernedGraphEdgeRecord)
            .where(*criteria)
            .order_by(GovernedGraphEdgeRecord.edge_id.asc())
        ).all()

        return tuple(_edge_to_domain(record) for record in records)

    def all_edges(self) -> tuple[GraphEdge, ...]:
        records = self._session.scalars(
            select(GovernedGraphEdgeRecord).order_by(
                GovernedGraphEdgeRecord.edge_id.asc()
            )
        ).all()

        return tuple(_edge_to_domain(record) for record in records)

    def all_nodes(self) -> tuple[GraphNode, ...]:
        records = self._session.scalars(
            select(GovernedGraphNodeRecord).order_by(
                GovernedGraphNodeRecord.node_id.asc()
            )
        ).all()

        return tuple(_node_to_domain(record) for record in records)

    def latest_generation(self) -> GraphGeneration | None:
        record = self._session.scalar(
            select(GovernedGraphGenerationRecord)
            .order_by(
                GovernedGraphGenerationRecord.generation_number.desc()
            )
            .limit(1)
        )

        return None if record is None else _generation_to_domain(record)

    def count_active(self) -> tuple[int, int]:
        nodes = int(
            self._session.scalar(
                select(func.count())
                .select_from(GovernedGraphNodeRecord)
                .where(
                    GovernedGraphNodeRecord.state
                    == GraphObjectState.ACTIVE.value
                )
            )
            or 0
        )

        edges = int(
            self._session.scalar(
                select(func.count())
                .select_from(GovernedGraphEdgeRecord)
                .where(
                    GovernedGraphEdgeRecord.state
                    == GraphObjectState.ACTIVE.value
                )
            )
            or 0
        )

        return (nodes, edges)


# --- Mapping -------------------------------------------------------------


def _apply_provenance(record, provenance: GraphProvenance) -> None:
    record.statement_key = provenance.statement_key
    record.document_id = provenance.document_id
    record.project_id = provenance.project_id
    record.content_checksum = provenance.content_checksum
    record.review_id = provenance.review_id
    record.reviewer_user_id = provenance.reviewer_user_id
    record.reviewer_display_name = provenance.reviewer_display_name
    record.reviewed_at = provenance.reviewed_at
    record.semantic_rule_id = provenance.semantic_rule_id
    record.semantic_rule_version = provenance.semantic_rule_version
    record.semantic_contract_version = provenance.semantic_contract_version
    record.resolution_policy_version = provenance.resolution_policy_version
    record.fact_policy_version = provenance.fact_policy_version
    record.semantic_policy_version = provenance.semantic_policy_version
    record.support_fingerprint = provenance.support_fingerprint


def _apply_node(record: GovernedGraphNodeRecord, node: GraphNode) -> None:
    record.kind = node.kind.value
    record.entity_key = node.node_id.entity_key
    record.label = node.label
    record.normalized_value = node.normalized_value
    record.unit = node.unit
    record.state = node.state.value
    record.retirement_reason = (
        None if node.retirement is None else node.retirement.reason.value
    )
    record.retired_at = (
        None if node.retirement is None else node.retirement.retired_at
    )
    record.created_at = node.created_at
    _apply_provenance(record, node.provenance)


def _apply_edge(record: GovernedGraphEdgeRecord, edge: GraphEdge) -> None:
    record.kind = edge.kind.value
    record.subject_node_id = edge.subject_node_id
    record.object_node_id = edge.object_node_id
    record.state = edge.state.value
    record.retirement_reason = (
        None if edge.retirement is None else edge.retirement.reason.value
    )
    record.retired_at = (
        None if edge.retirement is None else edge.retirement.retired_at
    )
    record.created_at = edge.created_at
    _apply_provenance(record, edge.provenance)


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
