from __future__ import annotations

from datetime import datetime

from app.domain.context_builder.context_builder_models import ContextPackage
from app.domain.graph_builder.graph_builder_models import (
    GraphEntityId,
    GraphRelationshipType,
)
from app.domain.prompt_builder.prompt_builder_factory import (
    PromptBuildRequestFactory,
)
from app.domain.prompt_builder.prompt_builder_models import PromptSectionType
from app.domain.prompt_builder.prompt_composition import PROMPT_SECTION_ORDER
from app.domain.prompt_builder.prompt_package_assembler import (
    assemble_prompt_package,
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
from app.services import context_builder_service

PROJECT_ID = 5
NOW = datetime(2026, 1, 1, 12, 0, 0)


def _entity_id(entity_type: str, canonical_id: str) -> GraphEntityId:
    return GraphEntityId(
        project_id=PROJECT_ID, entity_type=entity_type, canonical_id=canonical_id
    )


def _entity_candidate(canonical_id: str, score: float) -> KnowledgeCandidate:
    reference = KnowledgeCandidateReference(
        graph_entity_id=_entity_id("CABLE", canonical_id),
        entity_type="CABLE",
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


def _context_package(candidates, **overrides) -> ContextPackage:
    collection = KnowledgeCandidateCollection(
        candidates=candidates,
        total_before_limit=len(candidates),
        returned_count=len(candidates),
        applied_limit=20,
    )
    result = context_builder_service.build_context_package(
        project_id=PROJECT_ID, candidates=collection, now=NOW, **overrides
    )
    return result.package


def _build(context_package: ContextPackage):
    request = PromptBuildRequestFactory.create(
        project_id=PROJECT_ID, context_package=context_package
    )
    return assemble_prompt_package(request, now=NOW)


def test_sections_follow_the_canonical_deterministic_order():
    package = _context_package((_entity_candidate("C-001", 100.0),))
    result = _build(package)

    section_types = tuple(s.section_type for s in result.package.sections)
    assert section_types == PROMPT_SECTION_ORDER


def test_full_package_produces_nine_sections_all_enabled_when_content_exists():
    candidates = (
        _entity_candidate("C-001", 100.0),
        _attribute_candidate("C-001", 40.0),
        _relationship_candidate("C-001", "TR-01", 60.0),
    )
    package = _context_package(candidates)
    result = _build(package)

    assert len(result.package.sections) == 9
    # WARNINGS is the only section expected disabled - a full-coverage
    # ContextPackage carries no ContextWarnings.
    disabled = [s.section_type for s in result.package.sections if not s.enabled]
    assert disabled == [PromptSectionType.WARNINGS]


def test_empty_context_package_still_produces_all_nine_sections():
    package = _context_package(())
    result = _build(package)

    assert len(result.package.sections) == 9
    disabled = {s.section_type for s in result.package.sections if not s.enabled}
    assert PromptSectionType.SELECTED_KNOWLEDGE in disabled
    assert PromptSectionType.EVIDENCE_REFERENCES in disabled
    assert PromptSectionType.WARNINGS in disabled
    # Always-present, policy-driven sections remain enabled regardless
    # of how little knowledge was selected.
    always_enabled = {
        PromptSectionType.SYSTEM_CONTEXT,
        PromptSectionType.ENGINEERING_CONTEXT,
        PromptSectionType.CONSTRAINTS,
        PromptSectionType.FORMATTING_RULES,
        PromptSectionType.EXPECTED_OUTPUT,
        PromptSectionType.METADATA,
    }
    enabled = {s.section_type for s in result.package.sections if s.enabled}
    assert always_enabled <= enabled


def test_warnings_section_reflects_context_package_warnings():
    candidates = tuple(
        _entity_candidate(f"C-{i:03d}", 100.0 - i) for i in range(3)
    )
    package = _context_package(candidates, max_candidates=1)
    assert package.warnings  # budget overflow produced warnings upstream

    result = _build(package)
    warnings_section = next(
        s
        for s in result.package.sections
        if s.section_type is PromptSectionType.WARNINGS
    )
    assert warnings_section.enabled is True
    assert len(warnings_section.content) == len(package.warnings)


def test_constraints_and_instructions_are_always_present_and_fixed():
    package = _context_package(())
    result = _build(package)

    assert len(result.package.constraints) == 5
    assert len(result.package.instructions) == 3
    identifiers = {c.identifier for c in result.package.constraints}
    assert "use_only_supplied_evidence" in identifiers
    assert "do_not_invent_facts" in identifiers


def test_references_mirror_selected_candidates():
    candidates = (
        _entity_candidate("C-001", 100.0),
        _entity_candidate("C-002", 90.0),
    )
    package = _context_package(candidates)
    result = _build(package)

    assert len(result.package.references) == len(package.selected_candidates)
    reference_ids = {r.candidate_id for r in result.package.references}
    candidate_ids = {c.candidate_id for c in package.selected_candidates}
    assert reference_ids == candidate_ids


def test_metadata_echoes_context_builder_version_and_own_versions():
    package = _context_package(())
    result = _build(package)

    metadata = result.package.metadata
    assert metadata.prompt_builder_version == "1.0"
    assert metadata.composition_policy_version == "1.0"
    assert metadata.context_builder_version == package.metadata.context_builder_version
    assert metadata.assembled_at == NOW
    assert metadata.package_version == "1.0"


def test_version_matches_metadata_versions():
    package = _context_package(())
    result = _build(package)

    version = result.package.version
    metadata = result.package.metadata
    assert version.prompt_builder_version == metadata.prompt_builder_version
    assert version.composition_policy_version == metadata.composition_policy_version
    assert version.context_builder_version == metadata.context_builder_version
    assert version.package_version == metadata.package_version


def test_statistics_are_internally_consistent():
    candidates = (
        _entity_candidate("C-001", 100.0),
        _attribute_candidate("C-001", 40.0),
    )
    package = _context_package(candidates)
    result = _build(package)

    statistics = result.package.statistics
    assert statistics.section_count == 9
    assert (
        statistics.enabled_section_count + statistics.disabled_section_count
        == statistics.section_count
    )
    assert statistics.knowledge_item_count == len(package.selected_candidates)
    assert statistics.reference_count == len(result.package.references)
    assert statistics.estimated_total_tokens > 0


def test_validation_reports_a_structurally_valid_package():
    package = _context_package((_entity_candidate("C-001", 100.0),))
    result = _build(package)

    assert result.validation.valid is True
    assert result.validation.errors == ()


def test_assembly_is_deterministic_across_repeated_runs():
    candidates = (
        _entity_candidate("C-002", 90.0),
        _entity_candidate("C-001", 90.0),
        _attribute_candidate("C-001", 40.0),
        _relationship_candidate("C-001", "TR-01", 60.0),
    )
    package = _context_package(candidates)

    first = _build(package)
    second = _build(package)

    assert first.package == second.package
    assert first.validation == second.validation
