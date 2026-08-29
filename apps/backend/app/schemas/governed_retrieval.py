"""
Wire models for Governed Structured Retrieval (EPIC 31.2).

Typed all the way down. There is **no generic filter object, no
expression, no property map and no query language** on this contract: a
caller names a designation and a scope, and gets back governed objects
with the reason each one matched and the provenance that authorised it.

Every field is either copied from a governed row or is a closed enum
value, so a response can be read without knowing how the graph is
stored.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.governed_knowledge_graph.graph_lifecycle import (
    GraphObjectState,
    GraphRetirementReason,
)
from app.domain.governed_knowledge_graph.graph_vocabulary import (
    GraphEdgeKind,
    GraphNodeKind,
)
from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    GovernedMatchOutcome,
    GovernedMatchStrategy,
    GovernedQueryType,
    GovernedResultKind,
    RetrievalScope,
)


class GovernedProvenanceRead(BaseModel):
    """
    Where a returned piece of governed knowledge came from.

    Mandatory on every result. An engineer follows ``statement_key`` to
    the semantic statement, ``review_id`` to the judgement that approved
    it, and ``document_id`` to the drawing it was read out of - each of
    which already has its own endpoint.
    """

    statement_key: str
    document_id: int
    content_checksum: str
    review_id: int
    reviewer_user_id: int
    reviewer_display_name: str
    reviewed_at: datetime
    semantic_rule_id: str
    semantic_rule_version: str
    semantic_contract_version: str
    resolution_policy_version: str
    fact_policy_version: str
    semantic_policy_version: str
    support_fingerprint: str
    project_id: int | None

    model_config = ConfigDict(from_attributes=True)


class GovernedNodeReferenceRead(BaseModel):
    node_id: str
    kind: GraphNodeKind
    label: str
    normalized_value: str
    unit: str | None

    model_config = ConfigDict(from_attributes=True)


class GovernedRelationshipReferenceRead(BaseModel):
    edge_id: str
    kind: GraphEdgeKind
    subject: GovernedNodeReferenceRead
    object: GovernedNodeReferenceRead

    model_config = ConfigDict(from_attributes=True)


class GovernedMatchExplanationRead(BaseModel):
    """Why this governed object is in the result - a closed strategy, the
    governed field that carried it, and the value that was compared."""

    strategy: GovernedMatchStrategy
    matched_field: str
    matched_value: str
    normalized_query: str | None

    model_config = ConfigDict(from_attributes=True)


class GovernedRetrievalItemRead(BaseModel):
    """
    One retrieved piece of governed knowledge.

    ``state`` is on every item rather than only on retired ones: a
    reader must be able to tell current knowledge from a record of what
    the platform used to assert without inferring it from the request.
    """

    result_id: str
    kind: GovernedResultKind
    node: GovernedNodeReferenceRead | None
    relationship: GovernedRelationshipReferenceRead | None
    state: GraphObjectState
    retirement_reason: GraphRetirementReason | None
    match: GovernedMatchExplanationRead
    provenance: GovernedProvenanceRead

    model_config = ConfigDict(from_attributes=True)


class GovernedGraphVersionRead(BaseModel):
    generation_number: int | None
    generation_created_at: datetime | None
    promotion_contract_version: str | None

    model_config = ConfigDict(from_attributes=True)


class GovernedRetrievalDiagnosticsRead(BaseModel):
    """
    Deterministic diagnostics - counts, versions and closed enum values.

    ``duration_seconds`` is the one field that varies run to run and is
    deliberately not part of any identity.
    """

    query_type: GovernedQueryType
    scope: RetrievalScope
    normalized_query: str | None
    strategies_attempted: list[GovernedMatchStrategy]
    candidates_examined: int
    matched_count: int
    returned_count: int
    ambiguous: bool
    no_match: bool
    normalization_version: str
    matching_policy_version: str
    graph_version: GovernedGraphVersionRead
    duration_seconds: float | None = None

    model_config = ConfigDict(from_attributes=True)


class GovernedRetrievalResultRead(BaseModel):
    """
    One governed retrieval answer.

    ``outcome`` is computed before the limit is applied, so a truncated
    page can never present several governed answers as one certain one.
    """

    outcome: GovernedMatchOutcome
    items: list[GovernedRetrievalItemRead]
    total_before_limit: int
    applied_limit: int
    diagnostics: GovernedRetrievalDiagnosticsRead
    retrieved_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GovernedAssetRetrievalResponse(BaseModel):
    """
    What one designation resolved to.

    ``assets`` and ``quantities`` are **separate results**, each with its
    own outcome and diagnostics, rather than one merged list: "which
    assets does TR1 name?" and "what is asserted about them?" are
    different questions, and merging them would hide which of the two was
    ambiguous.
    """

    designation: str
    assets: GovernedRetrievalResultRead
    quantities: GovernedRetrievalResultRead | None = None
