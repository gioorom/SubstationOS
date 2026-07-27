from __future__ import annotations

from datetime import datetime

import pytest

from app.domain.prompt_builder.prompt_builder_exceptions import (
    InvalidProjectIdError,
    ProjectIdMismatchError,
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
from app.services import context_builder_service, prompt_builder_service

PROJECT_ID = 4
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


def _context_package(count: int, **overrides):
    candidates = tuple(
        _entity_candidate(f"C-{i:03d}", 100.0 - i) for i in range(count)
    )
    collection = KnowledgeCandidateCollection(
        candidates=candidates,
        total_before_limit=count,
        returned_count=count,
        applied_limit=20,
    )
    result = context_builder_service.build_context_package(
        project_id=PROJECT_ID, candidates=collection, now=NOW, **overrides
    )
    return result.package


def test_build_prompt_package_assembles_a_full_package():
    package = _context_package(3)
    result = prompt_builder_service.build_prompt_package(
        project_id=PROJECT_ID, context_package=package, now=NOW
    )
    assert result.project_id == PROJECT_ID
    assert result.package.project_id == PROJECT_ID
    assert result.validation.valid is True


def test_build_prompt_package_on_an_empty_context_package_is_valid():
    package = _context_package(0)
    result = prompt_builder_service.build_prompt_package(
        project_id=PROJECT_ID, context_package=package, now=NOW
    )
    assert result.package.statistics.knowledge_item_count == 0
    assert result.validation.valid is True
    disabled = {s.section_type for s in result.package.sections if not s.enabled}
    assert len(disabled) >= 2  # SELECTED_KNOWLEDGE and EVIDENCE_REFERENCES


def test_build_prompt_package_rejects_an_invalid_project_id():
    package = _context_package(1)
    with pytest.raises(InvalidProjectIdError):
        prompt_builder_service.build_prompt_package(
            project_id=0, context_package=package, now=NOW
        )


def test_build_prompt_package_rejects_a_mismatched_project_id():
    package = _context_package(1)
    with pytest.raises(ProjectIdMismatchError):
        prompt_builder_service.build_prompt_package(
            project_id=PROJECT_ID + 1, context_package=package, now=NOW
        )


def test_build_prompt_package_always_has_nine_sections_regardless_of_budget():
    package = _context_package(5, max_candidates=1)
    result = prompt_builder_service.build_prompt_package(
        project_id=PROJECT_ID, context_package=package, now=NOW
    )
    assert len(result.package.sections) == 9
    assert result.validation.valid is True


def test_build_prompt_package_is_deterministic():
    package = _context_package(4)
    first = prompt_builder_service.build_prompt_package(
        project_id=PROJECT_ID, context_package=package, now=NOW
    )
    second = prompt_builder_service.build_prompt_package(
        project_id=PROJECT_ID, context_package=package, now=NOW
    )
    assert first.package == second.package
