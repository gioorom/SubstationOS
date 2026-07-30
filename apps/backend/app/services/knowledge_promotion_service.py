"""
Application service for promotion.

The one place three contexts meet, and the meeting is one-directional:

```
    Engineering Semantics ──reads──▶  │
                                      │  Promotion  ──writes──▶  Governed Graph
    Human Review          ──reads──▶  │
```

It reads statements and reviews; it writes only `governed_graph_*`. It
never calls a pipeline stage, never records a review, and has no code
path that could - an architecture test asserts all three.

The graph domain underneath knows none of this. `promotion_rules` takes a
`PromotionCandidate` - plain strings, assembled here - and returns a
decision, which is how the graph context stays free of any import of the
contexts it projects.

---

## Two operations, one rule

**`promote_statement`** is incremental: one statement, visited because
somebody just reviewed it. It computes the desired state of that
statement's knowledge and reconciles it - creating, reactivating or
retiring.

**`rebuild`** recomputes the whole projection from the pipeline and the
reviews. It exists because the graph is derived, and it is the property
that makes every other guarantee checkable: drop the graph, rebuild, and
the content is identical.

Both use `promotion_rules.evaluate`. There is no second definition of
what may be promoted, so incremental and full can never disagree about
it - which is the failure mode an incremental projection usually has.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.engineering_entities.engineering_entity_repository import (
    EngineeringEntityRepository,
)
from app.domain.engineering_semantics.engineering_semantic_repository import (
    EngineeringSemanticRepository,
)
from app.domain.governed_knowledge_graph.graph_events import (
    FAILURE_REFUSALS,
    GraphEvent,
    GraphRebuilt,
    KnowledgeHistorical,
    KnowledgePromoted,
    KnowledgeRevalidated,
    PromotionFailed,
)
from app.domain.governed_knowledge_graph.graph_exceptions import (
    GraphIntegrityError,
)
from app.domain.governed_knowledge_graph.graph_generation import (
    GraphGeneration,
)
from app.domain.governed_knowledge_graph.graph_identity import (
    edge_id_for,
    node_id_for,
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
    GraphNodeKind,
)
from app.domain.governed_knowledge_graph.promotion_rules import (
    RETIRING_REFUSALS,
    PromotionCandidate,
    PromotionDecision,
    PromotionRefusal,
    evaluate,
)
from app.domain.human_review.review_repository import ReviewRepository
from app.services import human_review_service


@dataclass(frozen=True, slots=True)
class PromotionOutcome:
    """
    What a promotion run did.

    ``events`` is the account of it, for the caller to put in the audit
    trail. Counts are convenience over the same events, never a separate
    tally that could drift from them.
    """

    events: tuple[GraphEvent, ...] = field(default_factory=tuple)

    @property
    def promoted(self) -> int:
        return sum(
            1 for event in self.events if isinstance(event, KnowledgePromoted)
        )

    @property
    def retired(self) -> int:
        return sum(
            1
            for event in self.events
            if isinstance(event, KnowledgeHistorical)
        )

    @property
    def revalidated(self) -> int:
        return sum(
            1
            for event in self.events
            if isinstance(event, KnowledgeRevalidated)
        )

    @property
    def failed(self) -> int:
        return sum(
            1 for event in self.events if isinstance(event, PromotionFailed)
        )


def promote_statement(
    graph: GovernedGraphRepository,
    semantics: EngineeringSemanticRepository,
    entities: EngineeringEntityRepository,
    reviews: ReviewRepository,
    *,
    document_id: int,
    statement_key: str,
    now: datetime,
) -> PromotionOutcome:
    """
    Reconciles one statement's knowledge with its current review.

    Called after a review is recorded, so the graph reacts to a
    judgement without recomputing everything. Four outcomes:

    | Situation | What happens |
    |---|---|
    | Promotable, no edge yet | Nodes and edge created, `ACTIVE` |
    | Promotable, edge retired | Edge reactivated - identity preserved |
    | Promotable, edge already active | Provenance refreshed; idempotent |
    | Not promotable, edge active | Edge retired `HISTORICAL` with a reason |
    | Not promotable, no edge | Nothing. Most statements, most of the time |

    **The statement is never modified**, and neither is the review. This
    function reads both.
    """

    candidate = candidate_for(
        semantics,
        entities,
        reviews,
        document_id=document_id,
        statement_key=statement_key,
    )

    if candidate is None:
        # The statement is not in the document's current interpretation.
        # Anything the graph holds for it is stale by definition.
        return _retire_for_missing_statement(graph, statement_key, now)

    decision = evaluate(candidate)
    existing = graph.find_edge_by_statement(statement_key)

    if decision.promote:
        return _apply_promotion(
            graph,
            semantics,
            entities,
            reviews,
            candidate=candidate,
            decision=decision,
            existing=existing,
            document_id=document_id,
            now=now,
        )

    return _apply_refusal(
        graph,
        statement_key=statement_key,
        refusal=decision.refusal,
        existing=existing,
        now=now,
    )


def rebuild(
    graph: GovernedGraphRepository,
    semantics: EngineeringSemanticRepository,
    entities: EngineeringEntityRepository,
    reviews: ReviewRepository,
    *,
    document_ids: tuple[int, ...],
    now: datetime,
    actor_user_id: int | None = None,
) -> tuple[PromotionOutcome, GraphGeneration]:
    """
    Recomputes the whole projection from the pipeline and the reviews.

    Drops the graph and re-promotes every statement of every document
    given. Safe **only** because the graph is derived: everything it
    discards is reproducible, which is the property this whole context is
    designed around.

    Deterministic: the same statements and the same reviews produce
    byte-identical nodes and edges, because every identity is a hash of
    governed keys and nothing is derived from a timestamp, an insertion
    order or a label. `created_at` is taken from ``now`` rather than from
    the clock inside the loop, so two rebuilds of the same sources differ
    in exactly one field and a test can compare the rest.
    """

    before = {edge.edge_id.value: edge for edge in graph.all_edges()}

    graph.clear()

    events: list[GraphEvent] = []

    for document_id in sorted(set(document_ids)):
        semantic_set = semantics.find_latest_for_document(document_id)

        if semantic_set is None:
            continue

        # Sorted, so a rebuild visits statements in a fixed order
        # regardless of what the database returned.
        for statement in sorted(
            semantic_set.statements, key=lambda item: item.statement_key
        ):
            outcome = promote_statement(
                graph,
                semantics,
                entities,
                reviews,
                document_id=document_id,
                statement_key=statement.statement_key,
                now=now,
            )

            events.extend(outcome.events)

    after = {edge.edge_id.value: edge for edge in graph.all_edges()}

    node_count, edge_count = graph.count_active()

    latest = graph.latest_generation()
    generation_number = 1 if latest is None else latest.generation_number + 1

    generation = graph.record_generation(
        GraphGeneration.of_rebuild(
            generation_number=generation_number,
            created_at=now,
            node_count=node_count,
            edge_count=edge_count,
            actor_user_id=actor_user_id,
        )
    )

    events.append(
        GraphRebuilt(
            generation_number=generation.generation_number,
            node_count=node_count,
            edge_count=edge_count,
            unchanged=_same_content(before, after),
            occurred_at=now,
        )
    )

    return (PromotionOutcome(events=tuple(events)), generation)


def promote_document(
    graph: GovernedGraphRepository,
    semantics: EngineeringSemanticRepository,
    entities: EngineeringEntityRepository,
    reviews: ReviewRepository,
    *,
    document_id: int,
    now: datetime,
) -> PromotionOutcome:
    """
    Reconciles every statement of one document.

    The incremental unit an operator reaches for after a pipeline re-run:
    cheaper than a rebuild, and it visits exactly the statements a re-run
    could have changed.
    """

    semantic_set = semantics.find_latest_for_document(document_id)
    present = (
        frozenset()
        if semantic_set is None
        else frozenset(
            statement.statement_key for statement in semantic_set.statements
        )
    )

    events: list[GraphEvent] = []

    for statement_key in sorted(present):
        outcome = promote_statement(
            graph,
            semantics,
            entities,
            reviews,
            document_id=document_id,
            statement_key=statement_key,
            now=now,
        )

        events.extend(outcome.events)

    # Reconciliation runs in **both** directions. Visiting only the
    # statements that exist would leave knowledge promoted from a
    # statement the re-run dropped sitting in the graph, current and
    # unvisited - which is precisely the "silently retain stale
    # engineering knowledge" failure this context must not have.
    for edge in graph.all_edges():
        if (
            edge.provenance.document_id != document_id
            or not edge.is_current
            or edge.statement_key in present
        ):
            continue

        events.extend(
            _retire_for_missing_statement(
                graph, edge.statement_key, now
            ).events
        )

    return PromotionOutcome(events=tuple(events))


# --- Assembling a candidate ---------------------------------------------


def candidate_for(
    semantics: EngineeringSemanticRepository,
    entities: EngineeringEntityRepository,
    reviews: ReviewRepository,
    *,
    document_id: int,
    statement_key: str,
) -> PromotionCandidate | None:
    """
    Reads the statement, its entities and its current review.

    Returns plain strings: the graph domain never sees a semantic
    statement or a review object, which is what keeps its rules testable
    without either context.
    """

    semantic_set = semantics.find_latest_for_document(document_id)

    if semantic_set is None:
        return None

    statement = semantic_set.statement(statement_key)

    if statement is None:
        return None

    entity_set = entities.find_latest_for_document(document_id)

    subject = (
        None if entity_set is None else entity_set.entity(statement.subject_entity_key)
    )
    object_entity = (
        None if entity_set is None else entity_set.entity(statement.object_entity_key)
    )

    if subject is None or object_entity is None:
        raise GraphIntegrityError(
            f"Statement '{statement_key}' references an entity that is "
            "not in the document's current entity set."
        )

    projection = human_review_service.current_review(
        reviews,
        semantics,
        document_id=document_id,
        statement_key=statement_key,
    )

    return PromotionCandidate(
        statement_key=statement_key,
        statement_type=statement.statement_type.value,
        subject_entity_key=statement.subject_entity_key,
        subject_entity_type=subject.entity_type.value,
        object_entity_key=statement.object_entity_key,
        object_entity_type=object_entity.entity_type.value,
        decision=(
            None
            if projection.current is None
            else projection.current.decision.value
        ),
        applicability=(
            None
            if projection.current is None
            else projection.applicability.value
        ),
    )


# --- Applying a decision -------------------------------------------------


def _apply_promotion(
    graph: GovernedGraphRepository,
    semantics: EngineeringSemanticRepository,
    entities: EngineeringEntityRepository,
    reviews: ReviewRepository,
    *,
    candidate: PromotionCandidate,
    decision: PromotionDecision,
    existing: GraphEdge | None,
    document_id: int,
    now: datetime,
) -> PromotionOutcome:
    semantic_set = semantics.find_latest_for_document(document_id)
    entity_set = entities.find_latest_for_document(document_id)
    statement = semantic_set.statement(candidate.statement_key)

    projection = human_review_service.current_review(
        reviews,
        semantics,
        document_id=document_id,
        statement_key=candidate.statement_key,
    )
    review = projection.current

    provenance = GraphProvenance(
        statement_key=candidate.statement_key,
        document_id=document_id,
        content_checksum=semantic_set.content_checksum,
        review_id=review.review_id,
        reviewer_user_id=review.reviewer.user_id,
        reviewer_display_name=review.reviewer.display_name,
        reviewed_at=review.recorded_at,
        semantic_rule_id=statement.semantic_rule_id,
        semantic_rule_version=statement.semantic_rule_version,
        semantic_contract_version=statement.semantic_contract_version,
        resolution_policy_version=semantic_set.resolution_policy_version,
        fact_policy_version=semantic_set.fact_policy_version,
        semantic_policy_version=semantic_set.semantic_policy_version,
        support_fingerprint=review.snapshot.support_fingerprint,
        project_id=semantic_set.project_id,
    )

    # **When the graph learned this** is a fact about the knowledge, not
    # about the run that wrote the row: it is the moment the authorising
    # review was recorded. Deriving it from the review rather than from
    # the clock is what makes the whole projection a pure function of the
    # statements and the reviews - and what lets a rebuild reproduce it
    # byte for byte rather than merely re-populate it.
    learned_at = review.recorded_at

    subject_node = _node_for(
        entity_set.entity(candidate.subject_entity_key),
        decision.subject_kind,
        provenance,
        learned_at,
    )
    object_node = _node_for(
        entity_set.entity(candidate.object_entity_key),
        decision.object_kind,
        provenance,
        learned_at,
    )

    graph.upsert_node(subject_node)
    graph.upsert_node(object_node)

    edge_id = edge_id_for(decision.edge_kind, candidate.statement_key)

    edge = GraphEdge(
        edge_id=edge_id,
        kind=decision.edge_kind,
        subject_node_id=subject_node.node_id.value,
        object_node_id=object_node.node_id.value,
        state=GraphObjectState.ACTIVE,
        provenance=provenance,
        created_at=learned_at,
        retirement=None,
    )

    graph.upsert_edge(edge)

    was_retired = existing is not None and not existing.is_current

    if was_retired:
        return PromotionOutcome(
            events=(
                KnowledgeRevalidated(
                    statement_key=candidate.statement_key,
                    edge_id=edge_id.value,
                    occurred_at=now,
                ),
            )
        )

    if existing is not None:
        # Already current: provenance refreshed, nothing became true.
        # Emitting an event here would fill the trail with re-promotions
        # that changed nothing.
        return PromotionOutcome()

    return PromotionOutcome(
        events=(
            KnowledgePromoted(
                statement_key=candidate.statement_key,
                edge_id=edge_id.value,
                occurred_at=now,
            ),
        )
    )


def _apply_refusal(
    graph: GovernedGraphRepository,
    *,
    statement_key: str,
    refusal: PromotionRefusal | None,
    existing: GraphEdge | None,
    now: datetime,
) -> PromotionOutcome:
    events: list[GraphEvent] = []

    if refusal is not None and refusal in FAILURE_REFUSALS:
        events.append(
            PromotionFailed(
                statement_key=statement_key,
                refusal=refusal,
                occurred_at=now,
            )
        )

    if existing is None or not existing.is_current:
        # Nothing in the graph to retire. Most statements, most of the
        # time - and not news.
        return PromotionOutcome(events=tuple(events))

    reason = _retirement_reason(refusal)
    retired = existing.retired(GraphRetirement(reason=reason, retired_at=now))

    graph.upsert_edge(retired)
    _retire_orphaned_nodes(graph, retired, now)

    events.append(
        KnowledgeHistorical(
            statement_key=statement_key,
            edge_id=existing.edge_id.value,
            reason=reason,
            occurred_at=now,
        )
    )

    return PromotionOutcome(events=tuple(events))


def _retire_for_missing_statement(
    graph: GovernedGraphRepository, statement_key: str, now: datetime
) -> PromotionOutcome:
    """
    The statement is not in the document's current interpretation.

    Whatever the graph holds for it was promoted from something that no
    longer exists, so it stops being current - the "never silently retain
    stale engineering knowledge" rule, at its sharpest.
    """

    existing = graph.find_edge_by_statement(statement_key)

    if existing is None or not existing.is_current:
        return PromotionOutcome()

    reason = GraphRetirementReason.REQUIRES_REVALIDATION
    retired = existing.retired(GraphRetirement(reason=reason, retired_at=now))

    graph.upsert_edge(retired)
    _retire_orphaned_nodes(graph, retired, now)

    return PromotionOutcome(
        events=(
            KnowledgeHistorical(
                statement_key=statement_key,
                edge_id=existing.edge_id.value,
                reason=reason,
                occurred_at=now,
            ),
        )
    )


def _retire_orphaned_nodes(
    graph: GovernedGraphRepository, edge: GraphEdge, now: datetime
) -> None:
    """
    Retires a node whose every relationship has been retired.

    A node exists to be an endpoint of governed relationships. One with
    none represents nothing current, and leaving it `ACTIVE` would let
    "every approved asset" return assets nothing is asserted about.
    """

    for node_id in (edge.subject_node_id, edge.object_node_id):
        remaining = graph.edges_for_node(node_id)

        if remaining:
            continue

        node = graph.find_node(node_id)

        if node is None or not node.is_current:
            continue

        graph.upsert_node(
            node.retired(
                GraphRetirement(
                    reason=(
                        GraphRetirementReason.NO_REMAINING_RELATIONSHIPS
                    ),
                    retired_at=now,
                )
            )
        )


def _node_for(
    entity,
    kind: GraphNodeKind,
    provenance: GraphProvenance,
    now: datetime,
) -> GraphNode:
    """
    The node for one governed entity.

    ``label`` and ``normalized_value`` are copied from the entity for
    readability and lookup; identity comes from the entity key alone.
    """

    node_id = node_id_for(kind, entity.entity_key)

    normalized = (
        entity.designation.normalized
        if entity.designation is not None
        else (
            str(entity.quantity.value)
            if entity.quantity is not None
            else entity.label
        )
    )

    return GraphNode(
        node_id=node_id,
        kind=kind,
        label=entity.label,
        normalized_value=normalized,
        unit=None if entity.quantity is None else entity.quantity.unit,
        state=GraphObjectState.ACTIVE,
        provenance=provenance,
        created_at=now,
        retirement=None,
    )


def _retirement_reason(
    refusal: PromotionRefusal | None,
) -> GraphRetirementReason:
    if refusal is PromotionRefusal.REVIEW_STALE:
        return GraphRetirementReason.REQUIRES_REVALIDATION

    if refusal is PromotionRefusal.REVIEW_ORPHANED:
        return GraphRetirementReason.ORPHANED

    if refusal in RETIRING_REFUSALS:
        return GraphRetirementReason.REVIEW_REVERSED

    return GraphRetirementReason.REBUILD_RECONCILIATION


def _same_content(
    before: dict[str, GraphEdge], after: dict[str, GraphEdge]
) -> bool:
    """
    Whether a rebuild changed anything that matters.

    Compares identity, state and provenance - deliberately **not**
    `created_at`, which a rebuild resets for newly created objects and
    which says when a row was written rather than what it asserts.
    """

    if set(before) != set(after):
        return False

    return all(
        before[key].state == after[key].state
        and before[key].provenance == after[key].provenance
        and before[key].subject_node_id == after[key].subject_node_id
        and before[key].object_node_id == after[key].object_node_id
        for key in before
    )
