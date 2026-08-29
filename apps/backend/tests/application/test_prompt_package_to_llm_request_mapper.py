from __future__ import annotations

from datetime import datetime

from app.application.models.llm_request import (
    LLMCapability,
    LLMCapabilityRequirements,
    LLMContentType,
    LLMGenerationParameters,
    LLMMessageRole,
    LLMModelSelection,
    LLMProviderSelection,
)
from app.application.services.prompt_package_to_llm_request_mapper import (
    map_prompt_package_to_llm_request,
)
from app.domain.prompt_builder.prompt_builder_models import PromptSectionType
from app.services import context_builder_service, prompt_builder_service

from tests._governed_context import (
    asset_item,
    designation_result,
    results_for,
)

PROJECT_ID = 9
NOW = datetime(2026, 1, 1, 8, 0, 0)


def _prompt_package(count: int = 2, **context_overrides):
    """A prompt built from a governed context holding ``count`` approved
    assets."""

    context_result = context_builder_service.build_context_package(
        project_id=PROJECT_ID,
        results=results_for(
            tuple(
                asset_item(
                    f"node-c-{index:03d}",
                    f"C-{index:03d}",
                    statement_key=f"statement-{index}",
                    project_id=PROJECT_ID,
                )
                for index in range(count)
            ),
            project_id=PROJECT_ID,
        ),
        now=NOW,
        **context_overrides,
    )

    return prompt_builder_service.build_prompt_package(
        project_id=PROJECT_ID,
        context_package=context_result.package,
        now=NOW,
    ).package


def _map(prompt_package, **overrides):
    defaults = dict(
        provider_selection=LLMProviderSelection(provider_id="anthropic"),
        model_selection=LLMModelSelection(model_identifier="model-x"),
        generation_parameters=LLMGenerationParameters(),
        capability_requirements=LLMCapabilityRequirements(
            required_capabilities=(LLMCapability.TEXT_INPUT,)
        ),
        provider_abstraction_version="1.0",
        request_preparation_policy_version="1.0",
        request_correlation_id="corr-fixed",
        now=NOW,
    )
    defaults.update(overrides)
    return map_prompt_package_to_llm_request(prompt_package, **defaults)


def test_message_order_matches_enabled_section_order():
    package = _prompt_package(3)
    request = _map(package)

    enabled_section_types = [
        s.section_type for s in package.sections if s.enabled
    ]
    mapped_section_types = [
        PromptSectionType(m.section_type) for m in request.messages
    ]
    assert mapped_section_types == enabled_section_types


def test_disabled_sections_are_excluded_from_messages_but_recorded_in_metadata():
    package = _prompt_package(0)
    request = _map(package)

    mapped_section_types = {m.section_type for m in request.messages}
    assert PromptSectionType.SELECTED_KNOWLEDGE.value not in mapped_section_types
    assert PromptSectionType.WARNINGS.value not in mapped_section_types
    assert PromptSectionType.SELECTED_KNOWLEDGE.value in (
        request.metadata.excluded_section_types
    )


def test_evidence_references_section_maps_to_reference_content_type():
    package = _prompt_package(2)
    request = _map(package)

    evidence_message = next(
        m
        for m in request.messages
        if m.section_type == PromptSectionType.EVIDENCE_REFERENCES.value
    )
    assert all(
        block.content_type is LLMContentType.REFERENCE
        for block in evidence_message.content_blocks
    )


def test_instruction_sections_map_to_instruction_role():
    package = _prompt_package(1)
    request = _map(package)

    for section_type in (
        PromptSectionType.SYSTEM_CONTEXT,
        PromptSectionType.CONSTRAINTS,
        PromptSectionType.FORMATTING_RULES,
        PromptSectionType.EXPECTED_OUTPUT,
    ):
        message = next(
            m for m in request.messages if m.section_type == section_type.value
        )
        assert message.role is LLMMessageRole.INSTRUCTION


def test_context_sections_map_to_context_role():
    package = _prompt_package(1)
    request = _map(package)

    engineering_context_message = next(
        m
        for m in request.messages
        if m.section_type == PromptSectionType.ENGINEERING_CONTEXT.value
    )
    assert engineering_context_message.role is LLMMessageRole.CONTEXT


def test_references_are_preserved_from_the_prompt_package():
    package = _prompt_package(2)
    request = _map(package)

    assert request.references == package.references


def test_versions_and_project_scope_are_preserved():
    package = _prompt_package(1)
    request = _map(package)

    assert request.project_id == package.project_id
    assert (
        request.metadata.prompt_builder_version == package.metadata.prompt_builder_version
    )
    assert (
        request.metadata.composition_policy_version
        == package.metadata.composition_policy_version
    )
    assert request.metadata.prompt_package_version == package.metadata.package_version
    assert (
        request.metadata.context_assembly_version == package.metadata.context_assembly_version
    )


def test_mapping_is_deterministic_given_identical_inputs():
    package = _prompt_package(3)
    first = _map(package)
    second = _map(package)
    assert first == second


def test_mapping_differs_only_by_injected_now_and_correlation_id():
    package = _prompt_package(1)
    first = _map(package, now=NOW, request_correlation_id="a")
    second = _map(package, now=NOW, request_correlation_id="a")
    assert first == second

    third = _map(package, now=NOW, request_correlation_id="b")
    assert third != first
    assert third.metadata.request_correlation_id == "b"
