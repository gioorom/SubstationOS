from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.context_builder.context_builder_models import (
    BudgetCategory,
    BudgetConsumption,
    BudgetPolicy,
    ContextBudget,
    ContextMetadata,
    ContextMetadataEntry,
    ContextPackage,
    ContextStatistics,
    ContextWarning,
    ContextWarningCategory,
    CoverageCategory,
    CoverageMetric,
    CoverageReport,
    RetrievalSummary,
)
from app.domain.graph_builder.graph_builder_models import (
    GraphEntityId,
    GraphRelationshipType,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidate,
    KnowledgeCandidateAttribute,
    KnowledgeCandidateCollection,
    KnowledgeCandidateReference,
    KnowledgeCandidateRelationship,
    KnowledgeCandidateScore,
    KnowledgeCandidateScoreComponent,
    RetrievalMatch,
    RetrievalReason,
)
from app.schemas.graph_builder import GraphEntityIdRead
from app.schemas.structured_retrieval import (
    KnowledgeCandidateCollectionRead,
    KnowledgeCandidateReferenceRead,
    KnowledgeCandidateRead,
)

# --- Request -----------------------------------------------------------


class ContextMetadataEntryInput(BaseModel):
    key: str
    value: str


class ContextBuildRequestBody(BaseModel):
    """
    A Context Builder build request. ``project_id`` is deliberately
    absent - the path's own ``{project_id}`` is authoritative, matching
    Structured Retrieval's own convention. ``candidates`` is the
    ``KnowledgeCandidateCollection`` a prior call to
    ``/structured-retrieval/search`` returned (its ``candidates`` field)
    - Context Builder never calls Structured Retrieval itself, so the
    caller supplies this collection directly. Every budget field is
    optional; an omitted field falls back to Context Builder's own
    documented default (see ``app.domain.context_builder.budget_policy``).
    """

    candidates: KnowledgeCandidateCollectionRead

    max_candidates: int | None = None
    max_entities: int | None = None
    max_relationships: int | None = None
    max_attributes: int | None = None
    max_metadata_entries: int | None = None
    max_warnings: int | None = None

    metadata_entries: list[ContextMetadataEntryInput] = Field(
        default_factory=list
    )
    retrieval_policy_version: str | None = None


def _entity_id_from_read(entity_id: GraphEntityIdRead) -> GraphEntityId:
    return GraphEntityId(
        project_id=entity_id.project_id,
        entity_type=entity_id.entity_type,
        canonical_id=entity_id.canonical_id,
    )


def _reference_from_read(
    reference: KnowledgeCandidateReferenceRead,
) -> KnowledgeCandidateReference:
    return KnowledgeCandidateReference(
        graph_entity_id=_entity_id_from_read(reference.graph_entity_id),
        entity_type=reference.entity_type,
        canonical_id=reference.canonical_id,
    )


def _candidate_from_read(candidate: KnowledgeCandidateRead) -> KnowledgeCandidate:
    """
    Reconstructs a domain ``KnowledgeCandidate`` from the wire shape
    Structured Retrieval's own API returns. ``sort_key`` is deliberately
    not part of ``KnowledgeCandidateRead`` (Structured Retrieval treats
    it as an internal ranking aid never exposed to a caller - see
    ``app/schemas/structured_retrieval.py``), so it is filled here with
    an inert placeholder: Context Builder's own Selection stage
    (``candidate_selection.py``) computes its own deterministic ordering
    key from public fields and never reads this value.
    """

    score = KnowledgeCandidateScore(
        total=candidate.score.total,
        components=tuple(
            KnowledgeCandidateScoreComponent(
                category=component.category,
                weight=component.weight,
                detail=component.detail,
            )
            for component in candidate.score.components
        ),
    )

    return KnowledgeCandidate(
        candidate_id=candidate.candidate_id,
        project_id=candidate.project_id,
        candidate_kind=candidate.candidate_kind,
        primary_reference=(
            _reference_from_read(candidate.primary_reference)
            if candidate.primary_reference is not None
            else None
        ),
        matched_attributes=tuple(
            KnowledgeCandidateAttribute(name=attribute.name, value=attribute.value)
            for attribute in candidate.matched_attributes
        ),
        matched_relationships=tuple(
            KnowledgeCandidateRelationship(
                subject=_reference_from_read(relationship.subject),
                relationship_type=GraphRelationshipType(
                    value=relationship.relationship_type.value
                ),
                object=_reference_from_read(relationship.object),
            )
            for relationship in candidate.matched_relationships
        ),
        related_entities=tuple(
            _reference_from_read(reference)
            for reference in candidate.related_entities
        ),
        source_fact_ids=tuple(candidate.source_fact_ids),
        graph_node_ids=tuple(candidate.graph_node_ids),
        graph_relationship_ids=tuple(candidate.graph_relationship_ids),
        graph_execution_ids=tuple(candidate.graph_execution_ids),
        score=score,
        reasons=tuple(
            RetrievalReason(
                category=reason.category,
                criterion_kind=reason.criterion_kind,
                description=reason.description,
            )
            for reason in candidate.reasons
        ),
        matches=tuple(
            RetrievalMatch(
                criterion_kind=match.criterion_kind,
                criterion_value=match.criterion_value,
            )
            for match in candidate.matches
        ),
        sort_key=(0.0, 0, "", ""),
    )


def collection_from_schema(
    model: KnowledgeCandidateCollectionRead,
) -> KnowledgeCandidateCollection:
    return KnowledgeCandidateCollection(
        candidates=tuple(
            _candidate_from_read(candidate) for candidate in model.candidates
        ),
        total_before_limit=model.total_before_limit,
        returned_count=model.returned_count,
        applied_limit=model.applied_limit,
    )


# --- Response ------------------------------------------------------------
#
# GraphEntityIdRead is imported from app.schemas.graph_builder and
# KnowledgeCandidateRead (with its own nested KnowledgeCandidateReferenceRead
# etc.) from app.schemas.structured_retrieval - Context Builder reuses
# Structured Retrieval's own response shapes for the KnowledgeCandidate
# objects it threads through unchanged, rather than redefining them.


class RetrievalSummaryRead(BaseModel):
    retrieved_candidate_count: int
    total_before_limit: int
    applied_limit: int
    retrieved_entity_count: int
    retrieved_relationship_count: int
    retrieved_attribute_count: int

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
    max_candidates: int
    max_entities: int
    max_relationships: int
    max_attributes: int
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
    candidate_id: str | None

    model_config = ConfigDict(from_attributes=True)


class ContextStatisticsRead(BaseModel):
    selected_candidate_count: int
    discarded_candidate_count: int
    entity_count: int
    relationship_count: int
    attribute_count: int
    coverage_summary: CoverageReportRead
    budget_summary: ContextBudgetRead

    model_config = ConfigDict(from_attributes=True)


class ContextMetadataEntryRead(BaseModel):
    key: str
    value: str

    model_config = ConfigDict(from_attributes=True)


class ContextMetadataRead(BaseModel):
    context_builder_version: str
    assembled_at: datetime
    selection_policy_version: str
    budget_policy_version: str
    retrieval_policy_version: str | None
    entries: list[ContextMetadataEntryRead]

    model_config = ConfigDict(from_attributes=True)


class ContextPackageRead(BaseModel):
    project_id: int
    retrieval_summary: RetrievalSummaryRead
    selected_entities: list[KnowledgeCandidateRead]
    selected_relationships: list[KnowledgeCandidateRead]
    selected_attributes: list[KnowledgeCandidateRead]
    selected_candidates: list[KnowledgeCandidateRead]
    coverage: CoverageReportRead
    statistics: ContextStatisticsRead
    warnings: list[ContextWarningRead]
    budget: ContextBudgetRead
    metadata: ContextMetadataRead

    model_config = ConfigDict(from_attributes=True)


class ContextSelectionPolicyRead(BaseModel):
    version: str

    model_config = ConfigDict(from_attributes=True)


class ContextBuilderConfigurationRead(BaseModel):
    budget_policy: BudgetPolicyRead
    selection_policy: ContextSelectionPolicyRead
    context_builder_version: str

    model_config = ConfigDict(from_attributes=True)


class ContextBuilderResultRead(BaseModel):
    project_id: int
    configuration: ContextBuilderConfigurationRead
    package: ContextPackageRead

    model_config = ConfigDict(from_attributes=True)


# --- Reconstruction (Prompt Builder's own input shape) --------------------
#
# Prompt Builder's input is a full ContextPackage, not a
# KnowledgeCandidateCollection - app/schemas/prompt_builder.py reuses
# ContextPackageRead as its own request body's context_package field and
# calls context_package_from_schema to reconstruct the domain object,
# the same "reuse the upstream response shape" pattern this module's own
# collection_from_schema already established for Structured Retrieval.


def _budget_policy_from_read(model: BudgetPolicyRead) -> BudgetPolicy:
    return BudgetPolicy(
        version=model.version,
        max_candidates=model.max_candidates,
        max_entities=model.max_entities,
        max_relationships=model.max_relationships,
        max_attributes=model.max_attributes,
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


def _statistics_from_read(model: ContextStatisticsRead) -> ContextStatistics:
    return ContextStatistics(
        selected_candidate_count=model.selected_candidate_count,
        discarded_candidate_count=model.discarded_candidate_count,
        entity_count=model.entity_count,
        relationship_count=model.relationship_count,
        attribute_count=model.attribute_count,
        coverage_summary=_coverage_from_read(model.coverage_summary),
        budget_summary=_budget_from_read(model.budget_summary),
    )


def _metadata_from_read(model: ContextMetadataRead) -> ContextMetadata:
    return ContextMetadata(
        context_builder_version=model.context_builder_version,
        assembled_at=model.assembled_at,
        selection_policy_version=model.selection_policy_version,
        budget_policy_version=model.budget_policy_version,
        retrieval_policy_version=model.retrieval_policy_version,
        entries=tuple(
            ContextMetadataEntry(key=entry.key, value=entry.value)
            for entry in model.entries
        ),
    )


def context_package_from_schema(model: ContextPackageRead) -> ContextPackage:
    return ContextPackage(
        project_id=model.project_id,
        retrieval_summary=RetrievalSummary(
            retrieved_candidate_count=model.retrieval_summary.retrieved_candidate_count,
            total_before_limit=model.retrieval_summary.total_before_limit,
            applied_limit=model.retrieval_summary.applied_limit,
            retrieved_entity_count=model.retrieval_summary.retrieved_entity_count,
            retrieved_relationship_count=model.retrieval_summary.retrieved_relationship_count,
            retrieved_attribute_count=model.retrieval_summary.retrieved_attribute_count,
        ),
        selected_entities=tuple(
            _candidate_from_read(candidate) for candidate in model.selected_entities
        ),
        selected_relationships=tuple(
            _candidate_from_read(candidate)
            for candidate in model.selected_relationships
        ),
        selected_attributes=tuple(
            _candidate_from_read(candidate)
            for candidate in model.selected_attributes
        ),
        selected_candidates=tuple(
            _candidate_from_read(candidate)
            for candidate in model.selected_candidates
        ),
        coverage=_coverage_from_read(model.coverage),
        statistics=_statistics_from_read(model.statistics),
        warnings=tuple(
            ContextWarning(
                category=warning.category,
                message=warning.message,
                candidate_id=warning.candidate_id,
            )
            for warning in model.warnings
        ),
        budget=_budget_from_read(model.budget),
        metadata=_metadata_from_read(model.metadata),
    )
