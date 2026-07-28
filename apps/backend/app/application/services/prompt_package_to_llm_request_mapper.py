"""
Deterministic mapping: ``PromptPackage`` -> ``LLMRequest`` (EPIC 4,
Milestone 16). Preserves section ordering, enabled/disabled semantics
(only enabled sections become messages; disabled ones are recorded in
``LLMRequestMetadata.excluded_section_types``, never silently dropped),
section identity (``PromptSectionType`` value, echoed on every
message), evidence references, and every upstream version string.
Generates no new engineering fact, performs no retrieval, and performs
no AI-assisted rewriting of any kind - a pure, one-pass transformation
over an already-built ``PromptPackage``.

O(n) in the number of enabled sections and their content lines/
references - a single linear pass, no second scan.
"""

from __future__ import annotations

from datetime import datetime

from app.application.models.llm_request import (
    LLMCapabilityRequirements,
    LLMContentBlock,
    LLMContentType,
    LLMGenerationParameters,
    LLMMessage,
    LLMMessageRole,
    LLMModelSelection,
    LLMProviderSelection,
    LLMRequest,
    LLMRequestMetadata,
    LLMRequestVersion,
)
from app.domain.prompt_builder.prompt_builder_models import (
    PromptPackage,
    PromptSectionType,
)

# Fixed, documented role assignment per PromptSectionType - never
# derived from package content. INSTRUCTION-role sections govern
# behavior (system-level, in Anthropic terms); CONTEXT-role sections
# carry the governed knowledge and supporting detail. No section this
# milestone produces a USER/ASSISTANT/TOOL-role message - Prompt
# Builder does not yet model an actual end-user question or a prior
# conversation turn (see LLMMessageRole's own docstring).
_ROLE_FOR_SECTION: dict[PromptSectionType, LLMMessageRole] = {
    PromptSectionType.SYSTEM_CONTEXT: LLMMessageRole.INSTRUCTION,
    PromptSectionType.CONSTRAINTS: LLMMessageRole.INSTRUCTION,
    PromptSectionType.FORMATTING_RULES: LLMMessageRole.INSTRUCTION,
    PromptSectionType.EXPECTED_OUTPUT: LLMMessageRole.INSTRUCTION,
    PromptSectionType.ENGINEERING_CONTEXT: LLMMessageRole.CONTEXT,
    PromptSectionType.SELECTED_KNOWLEDGE: LLMMessageRole.CONTEXT,
    # The two comparison sides carry evidence, so they are context like
    # any other knowledge section. The mapper does not know what a
    # comparison is - it maps sections to roles, and these two are
    # sections; keeping them distinct is Prompt Builder's concern, and
    # their ordering in the message list follows the canonical section
    # order rather than anything this module decides.
    PromptSectionType.LEFT_KNOWLEDGE: LLMMessageRole.CONTEXT,
    PromptSectionType.RIGHT_KNOWLEDGE: LLMMessageRole.CONTEXT,
    PromptSectionType.EVIDENCE_REFERENCES: LLMMessageRole.CONTEXT,
    PromptSectionType.WARNINGS: LLMMessageRole.CONTEXT,
    PromptSectionType.METADATA: LLMMessageRole.CONTEXT,
}


def _content_type_for_section(section_type: PromptSectionType) -> LLMContentType:
    return (
        LLMContentType.REFERENCE
        if section_type is PromptSectionType.EVIDENCE_REFERENCES
        else LLMContentType.TEXT
    )


def map_prompt_package_to_llm_request(
    prompt_package: PromptPackage,
    *,
    provider_selection: LLMProviderSelection,
    model_selection: LLMModelSelection,
    generation_parameters: LLMGenerationParameters,
    capability_requirements: LLMCapabilityRequirements,
    provider_abstraction_version: str,
    request_preparation_policy_version: str,
    request_correlation_id: str,
    now: datetime,
) -> LLMRequest:
    messages = tuple(
        LLMMessage(
            role=_ROLE_FOR_SECTION[section.section_type],
            section_type=section.section_type.value,
            content_blocks=tuple(
                LLMContentBlock(
                    content_type=_content_type_for_section(section.section_type),
                    text=line,
                )
                for line in section.content
            ),
        )
        for section in prompt_package.sections
        if section.enabled
    )

    excluded_section_types = tuple(
        section.section_type.value
        for section in prompt_package.sections
        if not section.enabled
    )

    metadata = LLMRequestMetadata(
        project_id=prompt_package.project_id,
        context_builder_version=prompt_package.metadata.context_builder_version,
        prompt_builder_version=prompt_package.metadata.prompt_builder_version,
        composition_policy_version=prompt_package.metadata.composition_policy_version,
        prompt_package_version=prompt_package.metadata.package_version,
        provider_abstraction_version=provider_abstraction_version,
        request_preparation_policy_version=request_preparation_policy_version,
        provider_id=provider_selection.provider_id,
        model_identifier=model_selection.model_identifier,
        request_correlation_id=request_correlation_id,
        excluded_section_types=excluded_section_types,
        prepared_at=now,
    )

    return LLMRequest(
        project_id=prompt_package.project_id,
        provider_selection=provider_selection,
        model_selection=model_selection,
        messages=messages,
        references=prompt_package.references,
        generation_parameters=generation_parameters,
        capability_requirements=capability_requirements,
        metadata=metadata,
        version=LLMRequestVersion(
            provider_abstraction_version=provider_abstraction_version,
            request_preparation_policy_version=request_preparation_policy_version,
        ),
    )
