"""
Wire shapes for Governed Context Assembly (EPIC 31.3).

``ContextPackageRead`` is both a **response** (nothing serves it on its
own any more - see below) and, more importantly, the **request** shape
Prompt Builder and Engineering Response accept, so this module owns both
directions: the Pydantic models and the reconstruction back into the
domain.

---

## What EPIC 31.3 changed here

The package's items were ``KnowledgeCandidateRead`` - the legacy
Structured Retrieval shape, carrying a score, a ``GraphEntityId`` and a
``GraphRelationshipType``. They are now ``ContextItemRead``: governed
node and edge identities, the match strategy that explains the item, the
governed provenance that authorises it, and the retrieval outcome it
came from. This module no longer imports ``app.domain.graph_builder`` or
``app.domain.structured_retrieval`` at all.

## Why there is no `/context-builder/build` route any more

The endpoint took a ``KnowledgeCandidateCollection`` - the output of
legacy ``/structured-retrieval/search`` - and assembled a
``ContextPackage`` from it. After this milestone a ``ContextPackage`` is
a **governed** artefact: every item asserts a statement key, a review id
and a reviewer. There is no honest request body for that endpoint any
more, because provenance a caller asserts in a request is not
provenance - accepting one would let any authenticated client mint a
context that *looks* reviewed, which is the ADR-0004 failure three
milestones were spent removing.

Assembling a governed context is what
``POST /projects/{id}/engineering-engine/execute`` does, from retrieval
it ran itself. `governed_context_assembly.md` records the withdrawal.

## Why Prompt Builder and Engineering Response still accept one

Those two take a ``ContextPackageRead`` in the request body and were
already caller-asserted before this milestone. They persist nothing,
write no graph and return a prompt or a response artefact, so a
fabricated body harms only the caller's own answer. They are stage
inspection tools, they are authenticated, and they are documented as
such - the asymmetry with Context Assembly is that assembling context
is the step where "this is governed knowledge" is *claimed*, and that
claim must come from retrieval rather than from a request.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.domain.context_builder.budget_policy import (
    DEFAULT_MAX_LOCATIONS,
)
from app.domain.context_builder.context_builder_models import (
    BudgetCategory,
    BudgetConsumption,
    BudgetPolicy,
    ContextBudget,
    ContextItem,
    ContextItemOrigin,
    ContextMetadata,
    ContextMetadataEntry,
    ContextPackage,
    ContextWarning,
    ContextWarningCategory,
    CoverageCategory,
    CoverageMetric,
    CoverageReport,
    GovernedQuerySummary,
    RetrievalSummary,
)
from app.domain.governed_knowledge_graph.graph_lifecycle import (
    GraphObjectState,
    GraphRetirementReason,
)
from app.domain.governed_knowledge_graph.graph_vocabulary import (
    GraphEdgeKind,
    GraphNodeKind,
)
from app.domain.governed_retrieval.governed_match_policy import (
    precedence_of,
)
from app.domain.governed_retrieval.governed_normalization import (
    normalize_designation,
)
from app.domain.governed_retrieval.governed_retrieval_models import (
    GovernedMatchExplanation,
    GovernedNodeReference,
    GovernedProvenanceView,
    GovernedRelationshipReference,
    GovernedRetrievalItem,
)
from app.domain.governed_retrieval.governed_retrieval_vocabulary import (
    GovernedMatchOutcome,
    GovernedMatchStrategy,
    GovernedQueryType,
    GovernedResultKind,
    RetrievalScope,
)

# --- Governed item ------------------------------------------------------


class GovernedProvenanceRead(BaseModel):
    """
    The full origin of one governed context item.

    Every field is an **identity or a version**, never engineering
    content: the statement, the facts, the entities and the evidence
    stay in the pipeline, which remains their single account.
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
    """Why this item is in the context. A closed strategy vocabulary and
    the governed field that carried it - never a relevance number."""

    strategy: GovernedMatchStrategy
    matched_field: str
    matched_value: str
    normalized_query: str | None

    model_config = ConfigDict(from_attributes=True)


class ContextItemOriginRead(BaseModel):
    """Which governed query produced this item, and how certainly.
    ``matched_before_limit`` is retrieval's own count, so a reader can
    tell a complete answer from a truncated one."""

    query_type: GovernedQueryType
    outcome: GovernedMatchOutcome
    scope: RetrievalScope
    normalized_query: str | None
    matched_before_limit: int

    model_config = ConfigDict(from_attributes=True)


class ContextItemRead(BaseModel):
    """
    One governed result in a context.

    ``provenance`` is **not optional** and has no default, mirroring the
    domain: an item that could not say where it came from cannot be
    serialized any more than it can be constructed.
    """

    item_id: str
    kind: GovernedResultKind
    node: GovernedNodeReferenceRead | None
    relationship: GovernedRelationshipReferenceRead | None
    state: GraphObjectState
    retirement_reason: GraphRetirementReason | None
    match: GovernedMatchExplanationRead
    provenance: GovernedProvenanceRead
    origin: ContextItemOriginRead

    @classmethod
    def from_domain(cls, item: ContextItem) -> "ContextItemRead":
        result = item.result

        return cls(
            item_id=result.result_id,
            kind=result.kind,
            node=(
                None
                if result.node is None
                else GovernedNodeReferenceRead.model_validate(result.node)
            ),
            relationship=(
                None
                if result.relationship is None
                else GovernedRelationshipReferenceRead.model_validate(
                    result.relationship
                )
            ),
            state=result.state,
            retirement_reason=result.retirement_reason,
            match=GovernedMatchExplanationRead.model_validate(result.match),
            provenance=GovernedProvenanceRead.model_validate(
                result.provenance
            ),
            origin=ContextItemOriginRead.model_validate(item.origin),
        )


# --- Package ------------------------------------------------------------


class GovernedQuerySummaryRead(BaseModel):
    query_type: GovernedQueryType
    outcome: GovernedMatchOutcome
    scope: RetrievalScope
    normalized_query: str | None
    matched_before_limit: int
    returned_count: int

    model_config = ConfigDict(from_attributes=True)


class RetrievalSummaryRead(BaseModel):
    retrieved_item_count: int
    total_before_limit: int
    retrieved_asset_count: int
    retrieved_quantity_count: int
    retrieved_relationship_count: int
    queries: list[GovernedQuerySummaryRead]

    model_config = ConfigDict(from_attributes=True)


class BudgetConsumptionRead(BaseModel):
    category: BudgetCategory
    requested: int
    accepted: int
    discarded: int
    limit: int
    utilization: float

    model_config = ConfigDict(from_attributes=True)


class BudgetPolicyRead(BaseModel):
    version: str
    max_items: int
    max_assets: int
    max_quantities: int
    max_relationships: int
    # EPIC 32.2. Defaulted rather than required: an additive budget
    # dimension must not reject a payload written before it existed.
    max_locations: int = DEFAULT_MAX_LOCATIONS
    max_metadata_entries: int
    max_warnings: int

    model_config = ConfigDict(from_attributes=True)


class ContextBudgetRead(BaseModel):
    policy: BudgetPolicyRead
    consumption: list[BudgetConsumptionRead]
    exceeded: bool

    model_config = ConfigDict(from_attributes=True)


class CoverageMetricRead(BaseModel):
    category: CoverageCategory
    selected_count: int
    available_count: int
    ratio: float

    model_config = ConfigDict(from_attributes=True)


class CoverageReportRead(BaseModel):
    metrics: list[CoverageMetricRead]
    overall_completeness: float

    model_config = ConfigDict(from_attributes=True)


class ContextWarningRead(BaseModel):
    category: ContextWarningCategory
    message: str
    item_id: str | None

    model_config = ConfigDict(from_attributes=True)


class ContextStatisticsRead(BaseModel):
    selected_item_count: int
    discarded_item_count: int
    asset_count: int
    quantity_count: int
    relationship_count: int
    coverage_summary: CoverageReportRead
    budget_summary: ContextBudgetRead

    model_config = ConfigDict(from_attributes=True)


class ContextMetadataEntryRead(BaseModel):
    key: str
    value: str

    model_config = ConfigDict(from_attributes=True)


class ContextMetadataRead(BaseModel):
    context_assembly_version: str
    assembled_at: datetime
    selection_policy_version: str
    budget_policy_version: str
    retrieval_normalization_version: str | None
    retrieval_matching_policy_version: str | None
    graph_generation_number: int | None
    entries: list[ContextMetadataEntryRead]

    model_config = ConfigDict(from_attributes=True)


class ContextPackageRead(BaseModel):
    project_id: int
    retrieval_summary: RetrievalSummaryRead
    selected_assets: list[ContextItemRead]
    selected_quantities: list[ContextItemRead]
    selected_relationships: list[ContextItemRead]
    selected_items: list[ContextItemRead]
    coverage: CoverageReportRead
    statistics: ContextStatisticsRead
    warnings: list[ContextWarningRead]
    budget: ContextBudgetRead
    metadata: ContextMetadataRead

    @classmethod
    def from_domain(cls, package: ContextPackage) -> "ContextPackageRead":
        return cls(
            project_id=package.project_id,
            retrieval_summary=RetrievalSummaryRead.model_validate(
                package.retrieval_summary
            ),
            selected_assets=[
                ContextItemRead.from_domain(item)
                for item in package.selected_assets
            ],
            selected_quantities=[
                ContextItemRead.from_domain(item)
                for item in package.selected_quantities
            ],
            selected_relationships=[
                ContextItemRead.from_domain(item)
                for item in package.selected_relationships
            ],
            selected_items=[
                ContextItemRead.from_domain(item)
                for item in package.selected_items
            ],
            coverage=CoverageReportRead.model_validate(package.coverage),
            statistics=ContextStatisticsRead.model_validate(
                package.statistics
            ),
            warnings=[
                ContextWarningRead.model_validate(warning)
                for warning in package.warnings
            ],
            budget=ContextBudgetRead.model_validate(package.budget),
            metadata=ContextMetadataRead.model_validate(package.metadata),
        )


class ContextAssemblyConfigurationRead(BaseModel):
    budget_policy: BudgetPolicyRead
    selection_policy_version: str
    context_assembly_version: str

    model_config = ConfigDict(from_attributes=True)


# --- Reconstruction (Prompt Builder / Engineering Response input) --------


def _node_from_read(
    model: GovernedNodeReferenceRead,
) -> GovernedNodeReference:
    return GovernedNodeReference(
        node_id=model.node_id,
        kind=model.kind,
        label=model.label,
        normalized_value=model.normalized_value,
        unit=model.unit,
    )


def _match_from_read(
    model: GovernedMatchExplanationRead,
) -> GovernedMatchExplanation:
    return GovernedMatchExplanation(
        strategy=model.strategy,
        matched_field=model.matched_field,
        matched_value=model.matched_value,
        normalized_query=model.normalized_query,
    )


def _provenance_from_read(
    model: GovernedProvenanceRead,
) -> GovernedProvenanceView:
    return GovernedProvenanceView(
        statement_key=model.statement_key,
        document_id=model.document_id,
        content_checksum=model.content_checksum,
        review_id=model.review_id,
        reviewer_user_id=model.reviewer_user_id,
        reviewer_display_name=model.reviewer_display_name,
        reviewed_at=model.reviewed_at,
        semantic_rule_id=model.semantic_rule_id,
        semantic_rule_version=model.semantic_rule_version,
        semantic_contract_version=model.semantic_contract_version,
        resolution_policy_version=model.resolution_policy_version,
        fact_policy_version=model.fact_policy_version,
        semantic_policy_version=model.semantic_policy_version,
        support_fingerprint=model.support_fingerprint,
        project_id=model.project_id,
    )


def _sort_key_of(model: ContextItemRead) -> tuple[int, str, str, str]:
    """
    Recomputes the governed ordering key from the fields on the wire.

    ``sort_key`` is deliberately **not** serialized: it is derived, and a
    caller able to send one could reorder a context without changing any
    governed fact. Re-deriving it here from the strategy and the governed
    labels applies exactly the rule ``governed_result_assembly`` applies,
    so a round trip preserves the order rather than trusting it.
    """

    rank = precedence_of(model.match.strategy)

    if model.relationship is not None and model.kind is not (
        GovernedResultKind.ASSET
    ):
        return (
            rank,
            normalize_designation(model.relationship.subject.label),
            (
                ""
                if model.kind is GovernedResultKind.RELATIONSHIP
                and model.node is None
                else normalize_designation(
                    model.relationship.object.label
                )
            ),
            model.relationship.edge_id,
        )

    label = "" if model.node is None else model.node.label
    node_id = "" if model.node is None else model.node.node_id

    return (rank, normalize_designation(label), "", node_id)


def _item_from_read(model: ContextItemRead) -> ContextItem:
    relationship = (
        None
        if model.relationship is None
        else GovernedRelationshipReference(
            edge_id=model.relationship.edge_id,
            kind=model.relationship.kind,
            subject=_node_from_read(model.relationship.subject),
            object=_node_from_read(model.relationship.object),
        )
    )

    result = GovernedRetrievalItem(
        result_id=model.item_id,
        kind=model.kind,
        node=None if model.node is None else _node_from_read(model.node),
        relationship=relationship,
        state=model.state,
        retirement_reason=model.retirement_reason,
        match=_match_from_read(model.match),
        provenance=_provenance_from_read(model.provenance),
        sort_key=_sort_key_of(model),
    )

    return ContextItem(
        result=result,
        origin=ContextItemOrigin(
            query_type=model.origin.query_type,
            outcome=model.origin.outcome,
            scope=model.origin.scope,
            normalized_query=model.origin.normalized_query,
            matched_before_limit=model.origin.matched_before_limit,
        ),
    )


def _budget_policy_from_read(model: BudgetPolicyRead) -> BudgetPolicy:
    return BudgetPolicy(
        version=model.version,
        max_items=model.max_items,
        max_assets=model.max_assets,
        max_quantities=model.max_quantities,
        max_relationships=model.max_relationships,
        max_locations=model.max_locations,
        max_metadata_entries=model.max_metadata_entries,
        max_warnings=model.max_warnings,
    )


def _budget_from_read(model: ContextBudgetRead) -> ContextBudget:
    return ContextBudget(
        policy=_budget_policy_from_read(model.policy),
        consumption=tuple(
            BudgetConsumption(
                category=entry.category,
                requested=entry.requested,
                accepted=entry.accepted,
                discarded=entry.discarded,
                limit=entry.limit,
                utilization=entry.utilization,
            )
            for entry in model.consumption
        ),
        exceeded=model.exceeded,
    )


def _coverage_from_read(model: CoverageReportRead) -> CoverageReport:
    return CoverageReport(
        metrics=tuple(
            CoverageMetric(
                category=metric.category,
                selected_count=metric.selected_count,
                available_count=metric.available_count,
                ratio=metric.ratio,
            )
            for metric in model.metrics
        ),
        overall_completeness=model.overall_completeness,
    )


def _statistics_from_read(model: ContextStatisticsRead):
    from app.domain.context_builder.context_builder_models import (
        ContextStatistics,
    )

    return ContextStatistics(
        selected_item_count=model.selected_item_count,
        discarded_item_count=model.discarded_item_count,
        asset_count=model.asset_count,
        quantity_count=model.quantity_count,
        relationship_count=model.relationship_count,
        coverage_summary=_coverage_from_read(model.coverage_summary),
        budget_summary=_budget_from_read(model.budget_summary),
    )


def _metadata_from_read(model: ContextMetadataRead) -> ContextMetadata:
    return ContextMetadata(
        context_assembly_version=model.context_assembly_version,
        assembled_at=model.assembled_at,
        selection_policy_version=model.selection_policy_version,
        budget_policy_version=model.budget_policy_version,
        retrieval_normalization_version=(
            model.retrieval_normalization_version
        ),
        retrieval_matching_policy_version=(
            model.retrieval_matching_policy_version
        ),
        graph_generation_number=model.graph_generation_number,
        entries=tuple(
            ContextMetadataEntry(key=entry.key, value=entry.value)
            for entry in model.entries
        ),
    )


def context_package_from_schema(model: ContextPackageRead) -> ContextPackage:
    return ContextPackage(
        project_id=model.project_id,
        retrieval_summary=RetrievalSummary(
            retrieved_item_count=model.retrieval_summary.retrieved_item_count,
            total_before_limit=model.retrieval_summary.total_before_limit,
            retrieved_asset_count=(
                model.retrieval_summary.retrieved_asset_count
            ),
            retrieved_quantity_count=(
                model.retrieval_summary.retrieved_quantity_count
            ),
            retrieved_relationship_count=(
                model.retrieval_summary.retrieved_relationship_count
            ),
            queries=tuple(
                GovernedQuerySummary(
                    query_type=query.query_type,
                    outcome=query.outcome,
                    scope=query.scope,
                    normalized_query=query.normalized_query,
                    matched_before_limit=query.matched_before_limit,
                    returned_count=query.returned_count,
                )
                for query in model.retrieval_summary.queries
            ),
        ),
        selected_assets=tuple(
            _item_from_read(item) for item in model.selected_assets
        ),
        selected_quantities=tuple(
            _item_from_read(item) for item in model.selected_quantities
        ),
        selected_relationships=tuple(
            _item_from_read(item) for item in model.selected_relationships
        ),
        selected_items=tuple(
            _item_from_read(item) for item in model.selected_items
        ),
        coverage=_coverage_from_read(model.coverage),
        statistics=_statistics_from_read(model.statistics),
        warnings=tuple(
            ContextWarning(
                category=warning.category,
                message=warning.message,
                item_id=warning.item_id,
            )
            for warning in model.warnings
        ),
        budget=_budget_from_read(model.budget),
        metadata=_metadata_from_read(model.metadata),
    )


__all__ = [
    "ContextAssemblyConfigurationRead",
    "ContextItemRead",
    "ContextPackageRead",
    "context_package_from_schema",
]
