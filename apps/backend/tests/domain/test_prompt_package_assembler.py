from __future__ import annotations

from datetime import datetime

from app.domain.context_builder.context_builder_models import ContextPackage
from app.domain.prompt_builder.prompt_builder_factory import (
    PromptBuildRequestFactory,
)
from app.domain.prompt_builder.prompt_builder_models import PromptSectionType
from app.domain.prompt_builder.prompt_composition import PROMPT_SECTION_ORDER
from app.domain.prompt_builder.prompt_package_assembler import (
    assemble_prompt_package,
)
from app.services import context_builder_service

from tests._governed_context import (
    asset_item,
    designation_result,
    results_for,
    quantity_item,
    relationship_item,
)

PROJECT_ID = 5
NOW = datetime(2026, 1, 1, 12, 0, 0)


def _entity_id(entity_type: str, canonical_id: str) -> GraphEntityId:
    return GraphEntityId(
        project_id=PROJECT_ID, entity_type=entity_type, canonical_id=canonical_id
    )


def _asset(designation: str):
    """One approved governed asset, designated as an engineer wrote it."""

    return asset_item(
        f"node-{designation.lower()}",
        designation,
        statement_key=f"statement-{designation}",
        project_id=PROJECT_ID,
    )


def _quantity(designation: str, *, value: str = "630 kVA"):
    """One approved governed quantity, reached from its asset by the
    governed relationship that asserted it."""

    return quantity_item(
        subject_node_id=f"node-{designation.lower()}",
        subject_label=designation,
        quantity_node_id=f"node-{value.replace(' ', '').lower()}",
        quantity_label=value,
        edge_id=f"edge-{designation.lower()}",
        statement_key=f"statement-q-{designation}",
        project_id=PROJECT_ID,
    )


def _relationship(subject: str, object_designation: str):
    """One approved governed relationship, both endpoints resolved."""

    return relationship_item(
        subject_node_id=f"node-{subject.lower()}",
        subject_label=subject,
        object_node_id=f"node-{object_designation.lower()}",
        object_label=object_designation,
        edge_id=f"edge-{subject.lower()}-{object_designation.lower()}",
        statement_key=f"statement-r-{subject}",
        project_id=PROJECT_ID,
    )


def _context_package(items, **overrides) -> ContextPackage:
    result = context_builder_service.build_context_package(
        project_id=PROJECT_ID,
        results=results_for(tuple(items), project_id=PROJECT_ID),
        now=NOW,
        **overrides,
    )
    return result.package


def _build(context_package: ContextPackage):
    request = PromptBuildRequestFactory.create(
        project_id=PROJECT_ID, context_package=context_package
    )
    return assemble_prompt_package(request, now=NOW)


def test_sections_follow_the_canonical_deterministic_order():
    package = _context_package((_asset("C-001"),))
    result = _build(package)

    section_types = tuple(s.section_type for s in result.package.sections)
    assert section_types == PROMPT_SECTION_ORDER


def test_full_package_produces_every_section_enabled_when_content_exists():
    candidates = (
        _asset("C-001"),
        _quantity("C-001"),
        _relationship("C-001", "TR-01"),
    )
    package = _context_package(candidates)
    result = _build(package)

    assert len(result.package.sections) == len(PROMPT_SECTION_ORDER)
    # WARNINGS is the only *single-sided* section expected disabled - a
    # full-coverage ContextPackage carries no ContextWarnings. The two
    # comparison sides are always disabled here: only a comparison prompt
    # populates them (Milestone 24.2).
    disabled = [s.section_type for s in result.package.sections if not s.enabled]
    assert disabled == [
        # No reasoning ran for this prompt: DERIVED_REASONING is present
        # and disabled, like the two comparison sides, so every
        # PromptPackage keeps the same shape (EPIC 32.1).
        PromptSectionType.DERIVED_REASONING,
        PromptSectionType.LEFT_KNOWLEDGE,
        PromptSectionType.RIGHT_KNOWLEDGE,
        PromptSectionType.WARNINGS,
    ]


def test_empty_context_package_still_produces_every_section():
    package = _context_package(())
    result = _build(package)

    assert len(result.package.sections) == len(PROMPT_SECTION_ORDER)
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
        _asset(f"C-{i:03d}") for i in range(3)
    )
    package = _context_package(candidates, max_items=1)
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


def test_references_mirror_selected_items():
    candidates = (
        _asset("C-001"),
        _asset("C-002"),
    )
    package = _context_package(candidates)
    result = _build(package)

    assert len(result.package.references) == len(package.selected_items)
    reference_ids = {r.item_id for r in result.package.references}
    candidate_ids = {c.item_id for c in package.selected_items}
    assert reference_ids == candidate_ids


def test_metadata_echoes_context_assembly_version_and_own_versions():
    package = _context_package(())
    result = _build(package)

    metadata = result.package.metadata
    assert metadata.prompt_builder_version == "1.0"
    assert metadata.composition_policy_version == "1.0"
    assert metadata.context_assembly_version == package.metadata.context_assembly_version
    assert metadata.assembled_at == NOW
    assert metadata.package_version == "1.0"


def test_version_matches_metadata_versions():
    package = _context_package(())
    result = _build(package)

    version = result.package.version
    metadata = result.package.metadata
    assert version.prompt_builder_version == metadata.prompt_builder_version
    assert version.composition_policy_version == metadata.composition_policy_version
    assert version.context_assembly_version == metadata.context_assembly_version
    assert version.package_version == metadata.package_version


def test_statistics_are_internally_consistent():
    candidates = (
        _asset("C-001"),
        _quantity("C-001"),
    )
    package = _context_package(candidates)
    result = _build(package)

    statistics = result.package.statistics
    assert statistics.section_count == len(PROMPT_SECTION_ORDER)
    assert (
        statistics.enabled_section_count + statistics.disabled_section_count
        == statistics.section_count
    )
    assert statistics.knowledge_item_count == len(package.selected_items)
    assert statistics.reference_count == len(result.package.references)
    assert statistics.estimated_total_tokens > 0


def test_validation_reports_a_structurally_valid_package():
    package = _context_package((_asset("C-001"),))
    result = _build(package)

    assert result.validation.valid is True
    assert result.validation.errors == ()


def test_assembly_is_deterministic_across_repeated_runs():
    candidates = (
        _asset("C-002"),
        _asset("C-001"),
        _quantity("C-001"),
        _relationship("C-001", "TR-01"),
    )
    package = _context_package(candidates)

    first = _build(package)
    second = _build(package)

    assert first.package == second.package
    assert first.validation == second.validation
