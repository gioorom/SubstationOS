from __future__ import annotations

from datetime import datetime

from app.domain.context_builder.context_builder_factory import (
    ContextBuildRequestFactory,
)
from app.domain.context_builder.context_builder_models import (
    BudgetCategory,
    ContextWarningCategory,
    CoverageCategory,
)
from app.domain.context_builder.context_package_assembler import (
    assemble_context_package,
)
from app.domain.graph_builder.graph_builder_models import (
    GraphEntityId,
    GraphRelationshipType,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidate,
    KnowledgeCandidateAttribute,
    KnowledgeCandidateCollection,
    KnowledgeCandidateKind,
    KnowledgeCandidateReference,
    KnowledgeCandidateRelationship,
    KnowledgeCandidateScore,
    KnowledgeCandidateScoreComponent,
    ScoreComponentCategory,
)

PROJECT_ID = 7
NOW = datetime(2026, 1, 1, 10, 0, 0)


def _entity_id(entity_type: str, canonical_id: str) -> GraphEntityId:
    return GraphEntityId(
        project_id=PROJECT_ID, entity_type=entity_type, canonical_id=canonical_id
    )


def _entity_candidate(
    canonical_id: str,
    score: float,
    entity_type: str = "CABLE",
    graph_execution_ids: tuple[int, ...] = (1,),
) -> KnowledgeCandidate:
    reference = KnowledgeCandidateReference(
        graph_entity_id=_entity_id(entity_type, canonical_id),
        entity_type=entity_type,
        canonical_id=canonical_id,
    )
    return KnowledgeCandidate(
        candidate_id=f"{PROJECT_ID}:entity:{reference.graph_entity_id.value}",
        project_id=PROJECT_ID,
        candidate_kind=KnowledgeCandidateKind.ENTITY,
        primary_reference=reference,
        matched_attributes=(),
        matched_relationships=(),
        related_entities=(),
        source_fact_ids=(),
        graph_node_ids=(reference.graph_entity_id.value,),
        graph_relationship_ids=(),
        graph_execution_ids=graph_execution_ids,
        score=KnowledgeCandidateScore(
            total=score,
            components=(
                KnowledgeCandidateScoreComponent(
                    category=ScoreComponentCategory.ENTITY_TYPE_MATCH,
                    weight=score,
                    detail=entity_type,
                ),
            ),
        ),
        reasons=(),
        matches=(),
        sort_key=(0.0, 0, "", ""),
    )


def _attribute_candidate(canonical_id: str, score: float) -> KnowledgeCandidate:
    reference = KnowledgeCandidateReference(
        graph_entity_id=_entity_id("CABLE", canonical_id),
        entity_type="CABLE",
        canonical_id=canonical_id,
    )
    return KnowledgeCandidate(
        candidate_id=f"{PROJECT_ID}:attribute:{reference.graph_entity_id.value}:rated_voltage",
        project_id=PROJECT_ID,
        candidate_kind=KnowledgeCandidateKind.ATTRIBUTE,
        primary_reference=reference,
        matched_attributes=(
            KnowledgeCandidateAttribute(name="rated_voltage", value="132kV"),
        ),
        matched_relationships=(),
        related_entities=(),
        source_fact_ids=(),
        graph_node_ids=(reference.graph_entity_id.value,),
        graph_relationship_ids=(),
        graph_execution_ids=(1,),
        score=KnowledgeCandidateScore(
            total=score,
            components=(
                KnowledgeCandidateScoreComponent(
                    category=ScoreComponentCategory.ATTRIBUTE_NAME_MATCH,
                    weight=score,
                    detail="rated_voltage",
                ),
            ),
        ),
        reasons=(),
        matches=(),
        sort_key=(0.0, 0, "", ""),
    )


def _relationship_candidate(
    subject_id: str, object_id: str, score: float
) -> KnowledgeCandidate:
    subject = KnowledgeCandidateReference(
        graph_entity_id=_entity_id("CABLE", subject_id),
        entity_type="CABLE",
        canonical_id=subject_id,
    )
    obj = KnowledgeCandidateReference(
        graph_entity_id=_entity_id("TRANSFORMER", object_id),
        entity_type="TRANSFORMER",
        canonical_id=object_id,
    )
    natural_key = f"{subject.graph_entity_id.value}|FEEDS|{obj.graph_entity_id.value}"
    return KnowledgeCandidate(
        candidate_id=f"{PROJECT_ID}:relationship:{natural_key}",
        project_id=PROJECT_ID,
        candidate_kind=KnowledgeCandidateKind.RELATIONSHIP,
        primary_reference=subject,
        matched_attributes=(),
        matched_relationships=(
            KnowledgeCandidateRelationship(
                subject=subject,
                relationship_type=GraphRelationshipType(value="FEEDS"),
                object=obj,
            ),
        ),
        related_entities=(obj,),
        source_fact_ids=(),
        graph_node_ids=(subject.graph_entity_id.value, obj.graph_entity_id.value),
        graph_relationship_ids=(natural_key,),
        graph_execution_ids=(1,),
        score=KnowledgeCandidateScore(
            total=score,
            components=(
                KnowledgeCandidateScoreComponent(
                    category=ScoreComponentCategory.RELATIONSHIP_TYPE_MATCH,
                    weight=score,
                    detail="FEEDS",
                ),
            ),
        ),
        reasons=(),
        matches=(),
        sort_key=(0.0, 0, "", ""),
    )


def _collection(candidates: tuple[KnowledgeCandidate, ...]) -> KnowledgeCandidateCollection:
    return KnowledgeCandidateCollection(
        candidates=candidates,
        total_before_limit=len(candidates),
        returned_count=len(candidates),
        applied_limit=20,
    )


def _assemble(candidates, **overrides):
    request = ContextBuildRequestFactory.create(
        project_id=PROJECT_ID, candidates=_collection(candidates), **overrides
    )
    return assemble_context_package(request, now=NOW)


def test_full_coverage_when_everything_fits_the_budget():
    candidates = (
        _entity_candidate("C-001", 100.0),
        _attribute_candidate("C-001", 40.0),
        _relationship_candidate("C-001", "TR-01", 60.0),
    )
    package = _assemble(candidates)

    assert package.coverage.overall_completeness == 1.0
    assert all(metric.ratio == 1.0 for metric in package.coverage.metrics)
    assert package.budget.exceeded is False
    assert package.warnings == ()


def test_partial_coverage_when_budget_discards_candidates():
    candidates = tuple(
        _entity_candidate(f"C-{i:03d}", 100.0 - i) for i in range(4)
    )
    package = _assemble(candidates, max_candidates=2, max_entities=2)

    entity_metric = next(
        m
        for m in package.coverage.metrics
        if m.category is CoverageCategory.ENTITY_COVERAGE
    )
    assert entity_metric.selected_count == 2
    assert entity_metric.available_count == 4
    assert entity_metric.ratio == 0.5
    assert package.coverage.overall_completeness < 1.0

    categories = {w.category for w in package.warnings}
    assert ContextWarningCategory.BUDGET_EXCEEDED in categories
    assert ContextWarningCategory.PARTIAL_COVERAGE in categories
    assert ContextWarningCategory.CANDIDATE_DISCARDED in categories


def test_missing_attributes_and_relationships_warnings_when_retrieved_but_not_selected():
    candidates = (
        _entity_candidate("C-001", 100.0),
        _attribute_candidate("C-001", 40.0),
        _relationship_candidate("C-001", "TR-01", 60.0),
    )
    package = _assemble(candidates, max_attributes=0, max_relationships=0)

    categories = {w.category for w in package.warnings}
    assert ContextWarningCategory.MISSING_ATTRIBUTES in categories
    assert ContextWarningCategory.MISSING_RELATIONSHIPS in categories


def test_no_missing_attribute_or_relationship_warning_when_none_were_ever_retrieved():
    candidates = (_entity_candidate("C-001", 100.0),)
    package = _assemble(candidates)

    categories = {w.category for w in package.warnings}
    assert ContextWarningCategory.MISSING_ATTRIBUTES not in categories
    assert ContextWarningCategory.MISSING_RELATIONSHIPS not in categories


def test_missing_provenance_warning_when_no_graph_execution_id():
    candidates = (
        _entity_candidate("C-001", 100.0, graph_execution_ids=()),
    )
    package = _assemble(candidates)

    provenance_warnings = [
        w
        for w in package.warnings
        if w.category is ContextWarningCategory.MISSING_PROVENANCE
    ]
    assert len(provenance_warnings) == 1
    assert provenance_warnings[0].candidate_id == "7:entity:7:CABLE:C-001"


def test_empty_candidate_collection_produces_an_empty_but_valid_package():
    package = _assemble(())

    assert package.selected_candidates == ()
    assert package.selected_entities == ()
    assert package.statistics.selected_candidate_count == 0
    assert package.coverage.overall_completeness == 1.0
    assert package.budget.exceeded is False
    # Nothing was retrieved, so "missing" warnings would be noise, not
    # signal - Context Builder must not warn about data that was never
    # offered to it in the first place.
    assert package.warnings == ()


def test_metadata_reflects_configuration_and_now():
    package = _assemble((), retrieval_policy_version="1.0")
    assert package.metadata.assembled_at == NOW
    assert package.metadata.context_builder_version == "1.0"
    assert package.metadata.selection_policy_version == "1.0"
    assert package.metadata.budget_policy_version == "1.0"
    assert package.metadata.retrieval_policy_version == "1.0"


def test_metadata_entries_are_carried_and_budget_capped():
    entries = tuple((f"key-{i}", f"value-{i}") for i in range(5))
    package = _assemble((), metadata_entries=entries, max_metadata_entries=2)

    assert len(package.metadata.entries) == 2
    metadata_consumption = next(
        c
        for c in package.budget.consumption
        if c.category is BudgetCategory.METADATA_ENTRIES
    )
    assert metadata_consumption.requested == 5
    assert metadata_consumption.accepted == 2
    assert metadata_consumption.discarded == 3


def test_warnings_are_truncated_to_the_warning_budget():
    candidates = tuple(
        _entity_candidate(f"C-{i:03d}", 100.0 - i) for i in range(10)
    )
    package = _assemble(
        candidates, max_candidates=1, max_entities=1, max_warnings=2
    )

    assert len(package.warnings) == 2
    warnings_consumption = next(
        c
        for c in package.budget.consumption
        if c.category is BudgetCategory.WARNINGS
    )
    assert warnings_consumption.accepted == 2
    assert warnings_consumption.discarded > 0


def test_statistics_summarize_selection_coverage_and_budget():
    candidates = (
        _entity_candidate("C-001", 100.0),
        _entity_candidate("C-002", 90.0),
        _attribute_candidate("C-001", 40.0),
    )
    package = _assemble(candidates, max_candidates=2)

    stats = package.statistics
    assert stats.selected_candidate_count == 2
    assert stats.discarded_candidate_count == 1
    assert stats.entity_count == 2
    assert stats.attribute_count == 0
    assert stats.coverage_summary is package.coverage
    assert stats.budget_summary is package.budget


def test_assembly_is_deterministic_across_repeated_runs():
    candidates = (
        _entity_candidate("C-002", 90.0),
        _entity_candidate("C-001", 90.0),
        _attribute_candidate("C-001", 40.0),
        _relationship_candidate("C-001", "TR-01", 60.0),
    )
    first = _assemble(candidates)
    second = _assemble(candidates)

    first_ids = [c.candidate_id for c in first.selected_candidates]
    second_ids = [c.candidate_id for c in second.selected_candidates]
    assert first_ids == second_ids
    assert first.coverage == second.coverage
