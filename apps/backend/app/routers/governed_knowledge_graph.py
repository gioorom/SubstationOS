"""
The Governed Knowledge Graph API (EPIC 31).

```
GET  /knowledge-graph/vocabulary                     what may be in the graph
GET  /knowledge-graph/status                         counts and latest generation
GET  /knowledge-graph/nodes                          find assets and quantities
GET  /knowledge-graph/nodes/{node_id}                one node, and everything asserted about it
GET  /knowledge-graph/edges                          governed relationships
GET  /knowledge-graph/edges/{edge_id}                one relationship, with provenance
GET  /documents/{id}/engineering-semantics/{key}/promotion   is this statement in the graph?
POST /knowledge-graph/promotions                     promote one statement or one document
POST /knowledge-graph/rebuilds                       recompute the whole projection
```

**Resource-oriented, and no graph query language.** No Cypher, no
GraphQL, no SPARQL - a governed graph whose whole value is that every
answer is explainable should not first ship a way to ask questions whose
answers nobody planned. The queries above are the ones an engineer asks;
more are added as resources when there are more.

`promotions` and `rebuilds` are **collections of runs**, not verbs: a
promotion is a thing that happened, `POST` records one, and `201` says a
run was created. That keeps the API from acquiring `/promote` and
`/rebuild`, which would be RPC wearing a REST hat.

**Nothing here modifies a semantic statement or a review.** These routes
read both and write only the `governed_graph_*` tables; an architecture
test asserts it.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database.database import SessionLocal
from app.domain.audit.audit_models import (
    AuditAction,
    AuditOutcome,
    AuditResource,
)
from app.domain.governed_knowledge_graph.graph_events import (
    GraphEvent,
    GraphRebuilt,
    KnowledgeHistorical,
    KnowledgePromoted,
    KnowledgeRemoved,
    KnowledgeRevalidated,
    PromotionFailed,
)
from app.domain.governed_knowledge_graph.graph_exceptions import (
    GraphIntegrityError,
)
from app.domain.governed_knowledge_graph.graph_vocabulary import (
    EDGE_KIND_FOR_STATEMENT_TYPE,
    NODE_KIND_FOR_ENTITY_TYPE,
    GraphEdgeKind,
    GraphNodeKind,
)
from app.domain.governed_knowledge_graph.promotion_rules import (
    PROMOTION_CONTRACT_VERSION,
    evaluate,
)
from app.domain.identity.audit_identity import AuditIdentity
from app.domain.identity.identity_roles import Capability
from app.domain.shared_kernel.pagination import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    PageRequest,
)
from app.domain.shared_kernel.pagination_exceptions import PaginationError
from app.infrastructure.audit.sqlalchemy_audit_repository import (
    SqlAlchemyAuditRepository,
)
from app.infrastructure.engineering_entities.sqlalchemy_engineering_entity_repository import (  # noqa: E501
    SqlAlchemyEngineeringEntityRepository,
)
from app.infrastructure.engineering_semantics.sqlalchemy_engineering_semantic_repository import (  # noqa: E501
    SqlAlchemyEngineeringSemanticRepository,
)
from app.infrastructure.governed_knowledge_graph.sqlalchemy_governed_graph_repository import (  # noqa: E501
    SqlAlchemyGovernedGraphRepository,
)
from app.infrastructure.human_review.sqlalchemy_review_repository import (
    SqlAlchemyReviewRepository,
)
from app.routers.security import require_capability
from app.schemas.governed_knowledge_graph import (
    GraphEdgeListResponse,
    GraphEdgeRead,
    GraphGenerationRead,
    GraphNodeDetailResponse,
    GraphNodeListResponse,
    GraphNodeRead,
    GraphStatusResponse,
    GraphVocabularyResponse,
    PromotionEventRead,
    PromotionResultResponse,
    RebuildResultResponse,
    RelatedNodeRead,
    StatementPromotionRead,
)
from app.schemas.pagination import PageMetadata
from app.services import audit_service, knowledge_promotion_service
from app.services.knowledge_promotion_service import PromotionOutcome

router = APIRouter(tags=["Governed Knowledge Graph"])


def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def _graph(db: Session) -> SqlAlchemyGovernedGraphRepository:
    return SqlAlchemyGovernedGraphRepository(db)


def _semantics(db: Session):
    """Read-only. Nothing in this router writes a semantic set."""

    return SqlAlchemyEngineeringSemanticRepository(db)


def _entities(db: Session):
    return SqlAlchemyEngineeringEntityRepository(db)


def _reviews(db: Session):
    return SqlAlchemyReviewRepository(db)


#: Reading the graph needs no more than using the platform. Promoting is
#: a governed write and needs its own capability.
_READ = Depends(require_capability(Capability.USE_ENGINEERING_PLATFORM))

_PROMOTE = require_capability(Capability.PROMOTE_ENGINEERING_KNOWLEDGE)


# --- What the graph is ---------------------------------------------------


@router.get(
    "/knowledge-graph/vocabulary",
    response_model=GraphVocabularyResponse,
    summary="The node and edge kinds the graph may contain",
)
def read_vocabulary(_: AuditIdentity = _READ) -> GraphVocabularyResponse:
    return GraphVocabularyResponse(
        node_kinds=tuple(GraphNodeKind),
        edge_kinds=tuple(GraphEdgeKind),
        node_kind_for_entity_type=dict(NODE_KIND_FOR_ENTITY_TYPE),
        edge_kind_for_statement_type=dict(EDGE_KIND_FOR_STATEMENT_TYPE),
        promotion_contract_version=PROMOTION_CONTRACT_VERSION,
    )


@router.get(
    "/knowledge-graph/status",
    response_model=GraphStatusResponse,
    summary="What the graph currently holds",
)
def read_status(
    db: Session = Depends(get_db), _: AuditIdentity = _READ
) -> GraphStatusResponse:
    graph = _graph(db)
    nodes, edges = graph.count_active()
    generation = graph.latest_generation()

    return GraphStatusResponse(
        active_nodes=nodes,
        active_edges=edges,
        latest_generation=(
            None
            if generation is None
            else GraphGenerationRead.model_validate(generation)
        ),
        promotion_contract_version=PROMOTION_CONTRACT_VERSION,
    )


# --- Querying ------------------------------------------------------------


@router.get(
    "/knowledge-graph/nodes",
    response_model=GraphNodeListResponse,
    summary="Find governed assets and quantities",
)
def list_nodes(
    kind: GraphNodeKind | None = Query(default=None),
    project_id: int | None = Query(default=None),
    document_id: int | None = Query(default=None),
    search: str | None = Query(
        default=None,
        max_length=120,
        description=(
            "Matches the governed label or normalized value. A "
            "substring match over stored pipeline output - never a "
            "similarity search, and it never decides two nodes are the "
            "same thing."
        ),
    ),
    include_historical: bool = Query(
        default=False,
        description=(
            "By default only current governed knowledge is returned. "
            "Set to read what the graph used to assert."
        ),
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    _: AuditIdentity = _READ,
) -> GraphNodeListResponse:
    """
    "Find transformer by designation" is this endpoint with
    `kind=engineering_asset&search=TR1`.

    It finds what the documents *designate* `TR1`. It does not find
    transformers: no governed rule classifies equipment, and this API
    will not imply one that does.
    """

    try:
        found = _graph(db).list_nodes(
            page=PageRequest(page=page, page_size=page_size),
            kind=None if kind is None else kind.value,
            project_id=project_id,
            document_id=document_id,
            label_search=search,
            include_historical=include_historical,
        )
    except PaginationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    return GraphNodeListResponse(
        items=tuple(GraphNodeRead.of(node) for node in found.items),
        pagination=PageMetadata.of(found),
    )


@router.get(
    "/knowledge-graph/nodes/{node_id}",
    response_model=GraphNodeDetailResponse,
    responses={404: {"description": "No such node."}},
    summary="One node, and every governed relationship it participates in",
)
def read_node(
    node_id: str,
    include_historical: bool = Query(default=False),
    db: Session = Depends(get_db),
    _: AuditIdentity = _READ,
) -> GraphNodeDetailResponse:
    """
    "Find rated power", "find upstream equipment" and "find downstream
    equipment" are all this endpoint.

    Rather than one endpoint per question, a node answers with the
    relationships it participates in and which end it is on. `direction`
    is `outgoing` when this node is the subject - which is what
    "downstream" means for the relationships that exist today - and
    `incoming` when it is the object.

    Every relationship carries its own provenance, so the explanation of
    an answer arrives with the answer.
    """

    graph = _graph(db)
    node = graph.find_node(node_id)

    if node is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No such node in the governed knowledge graph.",
        )

    edges = graph.edges_for_node(
        node_id, include_historical=include_historical
    )

    relationships = tuple(
        RelatedNodeRead(
            edge=GraphEdgeRead.of(edge),
            direction=(
                "outgoing" if edge.subject_node_id == node_id else "incoming"
            ),
            other_node=_other_node(graph, edge, node_id),
        )
        for edge in edges
    )

    return GraphNodeDetailResponse(
        node=GraphNodeRead.of(node), relationships=relationships
    )


@router.get(
    "/knowledge-graph/edges",
    response_model=GraphEdgeListResponse,
    summary="Governed engineering relationships",
)
def list_edges(
    kind: GraphEdgeKind | None = Query(default=None),
    project_id: int | None = Query(default=None),
    document_id: int | None = Query(default=None),
    include_historical: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    db: Session = Depends(get_db),
    _: AuditIdentity = _READ,
) -> GraphEdgeListResponse:
    try:
        found = _graph(db).list_edges(
            page=PageRequest(page=page, page_size=page_size),
            kind=None if kind is None else kind.value,
            project_id=project_id,
            document_id=document_id,
            include_historical=include_historical,
        )
    except PaginationError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    return GraphEdgeListResponse(
        items=tuple(GraphEdgeRead.of(edge) for edge in found.items),
        pagination=PageMetadata.of(found),
    )


@router.get(
    "/knowledge-graph/edges/{edge_id}",
    response_model=GraphEdgeRead,
    responses={404: {"description": "No such edge."}},
    summary="One governed relationship, with its full provenance",
)
def read_edge(
    edge_id: str,
    db: Session = Depends(get_db),
    _: AuditIdentity = _READ,
) -> GraphEdgeRead:
    """
    "Find provenance" and "find review" are this endpoint: both are on
    the edge, because an edge that could not explain itself would not
    have been storable in the first place.
    """

    edge = _graph(db).find_edge(edge_id)

    if edge is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No such edge in the governed knowledge graph.",
        )

    return GraphEdgeRead.of(edge)


@router.get(
    "/documents/{document_id}/engineering-semantics/{statement_key}"
    "/promotion",
    response_model=StatementPromotionRead,
    summary="Whether one statement is in the graph, and why or why not",
)
def read_statement_promotion(
    document_id: int,
    statement_key: str,
    db: Session = Depends(get_db),
    _: AuditIdentity = _READ,
) -> StatementPromotionRead:
    """
    What the Workspace asks per statement.

    Answers with the **reason** when a statement is not promoted, not
    merely with its absence: "not promoted" and "not promoted because
    nobody has approved it" are different things to an engineer looking
    at the screen.
    """

    graph = _graph(db)
    edge = graph.find_edge_by_statement(statement_key)

    if edge is not None and edge.is_current:
        return StatementPromotionRead(
            statement_key=statement_key,
            promoted=True,
            refusal=None,
            edge=GraphEdgeRead.of(edge),
        )

    candidate = knowledge_promotion_service.candidate_for(
        _semantics(db),
        _entities(db),
        _reviews(db),
        document_id=document_id,
        statement_key=statement_key,
    )

    refusal = None if candidate is None else evaluate(candidate).refusal

    return StatementPromotionRead(
        statement_key=statement_key,
        promoted=False,
        refusal=refusal,
        edge=None if edge is None else GraphEdgeRead.of(edge),
    )


# --- Promotion -----------------------------------------------------------


@router.post(
    "/knowledge-graph/promotions",
    response_model=PromotionResultResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "The caller may not promote knowledge."},
        422: {"description": "Neither a statement nor a document was named."},
    },
    summary="Reconcile one statement's, or one document's, knowledge",
)
def create_promotion(
    document_id: int = Query(...),
    statement_key: str | None = Query(default=None),
    identity: AuditIdentity = Depends(_PROMOTE),
    db: Session = Depends(get_db),
) -> PromotionResultResponse:
    """
    Incremental. Visits one statement, or every statement of one
    document, and reconciles what the graph holds with what the reviews
    now say.

    `201`, because a promotion run is a thing that happened and this
    created a record of it - even when the run changed nothing, which is
    the common and correct outcome.

    Uses the same rule as a full rebuild, so incremental and full can
    never disagree about what is promotable.
    """

    now = datetime.utcnow()

    try:
        if statement_key is None:
            outcome = knowledge_promotion_service.promote_document(
                _graph(db),
                _semantics(db),
                _entities(db),
                _reviews(db),
                document_id=document_id,
                now=now,
            )
        else:
            outcome = knowledge_promotion_service.promote_statement(
                _graph(db),
                _semantics(db),
                _entities(db),
                _reviews(db),
                document_id=document_id,
                statement_key=statement_key,
                now=now,
            )
    except GraphIntegrityError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    _audit_promotion(db, identity, outcome, document_id, now)

    return _result_of(outcome)


@router.post(
    "/knowledge-graph/rebuilds",
    response_model=RebuildResultResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "The caller may not promote knowledge."},
    },
    summary="Recompute the whole projection from the pipeline and reviews",
)
def create_rebuild(
    document_id: list[int] = Query(
        default=[],
        description=(
            "Documents to rebuild from. Empty rebuilds from every "
            "document that has an interpretation."
        ),
    ),
    identity: AuditIdentity = Depends(_PROMOTE),
    db: Session = Depends(get_db),
) -> RebuildResultResponse:
    """
    Drops the graph and rebuilds it.

    Safe **only** because the graph is derived: everything discarded is
    reproducible from the semantic statements and the reviews. Nothing
    else in this system has an operation like it.

    A rebuild over unchanged sources produces identical content - the
    result's `unchanged` event reports whether it did, which is the
    cheapest possible drift detector.
    """

    now = datetime.utcnow()

    documents = (
        tuple(document_id)
        if document_id
        else _every_interpreted_document(db)
    )

    outcome, generation = knowledge_promotion_service.rebuild(
        _graph(db),
        _semantics(db),
        _entities(db),
        _reviews(db),
        document_ids=documents,
        now=now,
        actor_user_id=identity.user_id,
    )

    audit_service.record_for_identity(
        SqlAlchemyAuditRepository(db),
        identity=identity,
        action=AuditAction.KNOWLEDGE_GRAPH_REBUILT,
        outcome=AuditOutcome.SUCCEEDED,
        resource=AuditResource(
            "knowledge_graph", str(generation.generation_number)
        ),
        now=now,
        detail=(
            f"generation {generation.generation_number}: "
            f"{generation.node_count} nodes, {generation.edge_count} edges"
        ),
    )

    return RebuildResultResponse(
        result=_result_of(outcome),
        generation=GraphGenerationRead.model_validate(generation),
    )


# --- Helpers -------------------------------------------------------------


def _other_node(graph, edge, node_id: str) -> GraphNodeRead | None:
    other_id = (
        edge.object_node_id
        if edge.subject_node_id == node_id
        else edge.subject_node_id
    )

    other = graph.find_node(other_id)

    return None if other is None else GraphNodeRead.of(other)


def _every_interpreted_document(db: Session) -> tuple[int, ...]:
    """
    Every document with a semantic set.

    Read here rather than in the service, because "which documents
    exist?" is a question about persistence rather than about promotion.
    """

    from sqlalchemy import select

    from app.models.engineering_semantics import EngineeringSemanticSetRecord

    return tuple(
        sorted(
            {
                row
                for row in db.scalars(
                    select(EngineeringSemanticSetRecord.document_id)
                ).all()
            }
        )
    )


def _result_of(outcome: PromotionOutcome) -> PromotionResultResponse:
    return PromotionResultResponse(
        promoted=outcome.promoted,
        retired=outcome.retired,
        revalidated=outcome.revalidated,
        failed=outcome.failed,
        events=tuple(_event_of(event) for event in outcome.events),
    )


def _event_of(event: GraphEvent) -> PromotionEventRead:
    return PromotionEventRead(
        event_type=event.event_type.value,
        statement_key=getattr(event, "statement_key", None),
        edge_id=getattr(event, "edge_id", None),
        reason=(
            event.reason.value
            if isinstance(event, KnowledgeHistorical)
            else None
        ),
        refusal=(
            event.refusal if isinstance(event, PromotionFailed) else None
        ),
    )


def _audit_promotion(
    db: Session,
    identity: AuditIdentity,
    outcome: PromotionOutcome,
    document_id: int,
    now: datetime,
) -> None:
    """
    Records a run that **changed something**.

    A promotion that reconciled nothing is the common case - most
    statements are unreviewed most of the time - and an audit entry for
    each would bury the ones that matter.
    """

    changed = [
        event
        for event in outcome.events
        if isinstance(
            event,
            (
                KnowledgePromoted,
                KnowledgeHistorical,
                KnowledgeRevalidated,
                KnowledgeRemoved,
                GraphRebuilt,
            ),
        )
    ]

    if not changed:
        return

    audit_service.record_for_identity(
        SqlAlchemyAuditRepository(db),
        identity=identity,
        action=AuditAction.KNOWLEDGE_PROMOTED,
        outcome=AuditOutcome.SUCCEEDED,
        resource=AuditResource("document", str(document_id)),
        now=now,
        detail=(
            f"promoted={outcome.promoted} retired={outcome.retired} "
            f"revalidated={outcome.revalidated}"
        ),
    )
