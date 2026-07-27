from __future__ import annotations

from datetime import datetime

import pytest

from app.domain.context_builder.context_builder_exceptions import (
    InvalidProjectIdError,
)
from app.domain.graph_builder.graph_builder_models import GraphEntityId
from app.domain.structured_retrieval.structured_retrieval_models import (
    KnowledgeCandidate,
    KnowledgeCandidateCollection,
    KnowledgeCandidateKind,
    KnowledgeCandidateReference,
    KnowledgeCandidateScore,
    KnowledgeCandidateScoreComponent,
    ScoreComponentCategory,
)
from app.services import context_builder_service

PROJECT_ID = 3
NOW = datetime(2026, 1, 1, 9, 0, 0)


def _entity_candidate(canonical_id: str, score: float) -> KnowledgeCandidate:
    entity_id = GraphEntityId(
        project_id=PROJECT_ID, entity_type="CABLE", canonical_id=canonical_id
    )
    reference = KnowledgeCandidateReference(
        graph_entity_id=entity_id, entity_type="CABLE", canonical_id=canonical_id
    )
    return KnowledgeCandidate(
        candidate_id=f"{PROJECT_ID}:entity:{entity_id.value}",
        project_id=PROJECT_ID,
        candidate_kind=KnowledgeCandidateKind.ENTITY,
        primary_reference=reference,
        matched_attributes=(),
        matched_relationships=(),
        related_entities=(),
        source_fact_ids=(),
        graph_node_ids=(entity_id.value,),
        graph_relationship_ids=(),
        graph_execution_ids=(1,),
        score=KnowledgeCandidateScore(
            total=score,
            components=(
                KnowledgeCandidateScoreComponent(
                    category=ScoreComponentCategory.ENTITY_TYPE_MATCH,
                    weight=score,
                    detail="CABLE",
                ),
            ),
        ),
        reasons=(),
        matches=(),
        sort_key=(0.0, 0, "", ""),
    )


def _collection(count: int) -> KnowledgeCandidateCollection:
    candidates = tuple(
        _entity_candidate(f"C-{i:03d}", 100.0 - i) for i in range(count)
    )
    return KnowledgeCandidateCollection(
        candidates=candidates,
        total_before_limit=count,
        returned_count=count,
        applied_limit=20,
    )


def test_build_context_package_assembles_a_full_package_within_budget():
    result = context_builder_service.build_context_package(
        project_id=PROJECT_ID, candidates=_collection(3), now=NOW
    )
    assert result.project_id == PROJECT_ID
    assert result.package.project_id == PROJECT_ID
    assert len(result.package.selected_candidates) == 3
    assert result.package.budget.exceeded is False


def test_build_context_package_reports_budget_overflow():
    result = context_builder_service.build_context_package(
        project_id=PROJECT_ID,
        candidates=_collection(5),
        max_candidates=2,
        now=NOW,
    )
    assert len(result.package.selected_candidates) == 2
    assert result.package.statistics.discarded_candidate_count == 3
    assert result.package.budget.exceeded is True


def test_build_context_package_on_an_empty_collection_is_a_valid_empty_package():
    result = context_builder_service.build_context_package(
        project_id=PROJECT_ID, candidates=_collection(0), now=NOW
    )
    assert result.package.selected_candidates == ()
    assert result.package.statistics.selected_candidate_count == 0
    assert result.package.warnings == ()


def test_build_context_package_on_a_full_collection_selects_everything_within_default_budget():
    result = context_builder_service.build_context_package(
        project_id=PROJECT_ID, candidates=_collection(10), now=NOW
    )
    assert len(result.package.selected_candidates) == 10
    assert result.package.budget.exceeded is False


def test_build_context_package_rejects_an_invalid_project_id():
    with pytest.raises(InvalidProjectIdError):
        context_builder_service.build_context_package(
            project_id=0, candidates=_collection(1), now=NOW
        )


def test_build_context_package_is_deterministic():
    collection = _collection(6)
    first = context_builder_service.build_context_package(
        project_id=PROJECT_ID, candidates=collection, now=NOW
    )
    second = context_builder_service.build_context_package(
        project_id=PROJECT_ID, candidates=collection, now=NOW
    )
    first_ids = [c.candidate_id for c in first.package.selected_candidates]
    second_ids = [c.candidate_id for c in second.package.selected_candidates]
    assert first_ids == second_ids
    assert first.package.coverage == second.package.coverage


def test_build_context_package_echoes_metadata_entries_and_retrieval_policy_version():
    result = context_builder_service.build_context_package(
        project_id=PROJECT_ID,
        candidates=_collection(1),
        metadata_entries=(("mode", "entity_type_search"),),
        retrieval_policy_version="1.0",
        now=NOW,
    )
    assert result.package.metadata.retrieval_policy_version == "1.0"
    assert result.package.metadata.entries[0].key == "mode"
    assert result.package.metadata.entries[0].value == "entity_type_search"
