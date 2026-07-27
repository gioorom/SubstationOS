"""
Application service for Engineering Response (EPIC 5, Milestone 18).
The **one** seam allowed to import both
``app.application.models.llm_invocation.LLMResponseEnvelope`` (an
application-layer type, produced by the LLM Invocation Runtime,
Milestone 17) and ``app.domain.engineering_response`` (a genuine domain
bounded context) - translating the former into the domain's own
``EngineeringResponseSourceEnvelope`` restatement before delegating to
the pure domain assembler. ``app/domain/engineering_response/**`` itself
never imports ``app.application.**`` (CLAUDE.md's Dependency Rule -
domain depends on nothing beyond other domain modules); this file is
where that one translation happens, and only here. Performs no
persistence and no I/O of any kind - no AI invocation, no second
Anthropic call, no re-derivation of the prompt or context that produced
the supplied envelope.
"""

from __future__ import annotations

from datetime import datetime

from app.application.models.llm_invocation import LLMResponseEnvelope
from app.domain.context_builder.context_builder_models import ContextPackage
from app.domain.engineering_response.engineering_response_assembler import (
    assemble_engineering_response,
)
from app.domain.engineering_response.engineering_response_factory import (
    EngineeringResponseBuildRequestFactory,
)
from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponseBuilderResult,
    EngineeringResponseSourceContent,
    EngineeringResponseSourceEnvelope,
    EngineeringSourceFinishReason,
)
from app.domain.prompt_builder.prompt_builder_models import PromptPackage


def _source_envelope_from_llm_envelope(
    envelope: LLMResponseEnvelope,
) -> EngineeringResponseSourceEnvelope:
    return EngineeringResponseSourceEnvelope(
        provider_id=envelope.provider_id,
        configured_model_identifier=envelope.configured_model_identifier,
        returned_model_identifier=envelope.returned_model_identifier,
        content=tuple(
            EngineeringResponseSourceContent(
                sequence_index=block.sequence_index,
                is_supported_text=block.content_type.value == "text",
                text=block.text,
                provider_block_type=block.provider_block_type,
            )
            for block in envelope.content
        ),
        finish_reason=EngineeringSourceFinishReason(envelope.finish_reason.value),
        request_correlation_id=envelope.request_correlation_id,
        attempt_count=envelope.attempt_count,
        warnings=envelope.warnings,
        input_tokens=envelope.usage.input_tokens,
        output_tokens=envelope.usage.output_tokens,
        runtime_version=envelope.metadata.runtime_version,
        adapter_version=envelope.metadata.adapter_version,
        request_preparation_policy_version=(
            envelope.metadata.request_preparation_policy_version
        ),
    )


def build_engineering_response(
    *,
    project_id: int,
    context_package: ContextPackage,
    prompt_package: PromptPackage,
    llm_response_envelope: LLMResponseEnvelope,
    now: datetime,
) -> EngineeringResponseBuilderResult:
    source = _source_envelope_from_llm_envelope(llm_response_envelope)

    request = EngineeringResponseBuildRequestFactory.create(
        project_id=project_id,
        context_package=context_package,
        prompt_package=prompt_package,
        source=source,
    )

    return assemble_engineering_response(request, now=now)
