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

Since Milestone 23B.1 this module exposes **one entry point per response
origin**: ``build_engineering_response`` (an LLM invocation produced the
answer) and ``build_document_lookup_response`` (governed repository state
produced it, with no provider involved at all). The second takes a domain
type as input and therefore performs no translation whatsoever.
"""

from __future__ import annotations

from datetime import datetime

from app.application.models.llm_invocation import LLMResponseEnvelope
from app.domain.context_builder.comparison_context_models import (
    ComparisonContextPackage,
)
from app.domain.context_builder.context_builder_models import ContextPackage
from app.domain.engineering_index.document_retrieval_models import (
    DocumentRetrievalResult,
)
from app.domain.engineering_response.engineering_response_assembler import (
    assemble_engineering_response,
)
from app.domain.engineering_response.engineering_response_comparison_assembler import (  # noqa: E501
    assemble_comparison_response,
)
from app.domain.engineering_response.engineering_response_document_assembler import (  # noqa: E501
    assemble_document_lookup_response,
)
from app.domain.engineering_response.engineering_response_document_factory import (  # noqa: E501
    EngineeringResponseDocumentLookupBuildRequestFactory,
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


def build_document_lookup_response(
    *,
    project_id: int,
    document_retrieval_result: DocumentRetrievalResult,
    request_correlation_id: str,
    now: datetime,
) -> EngineeringResponseBuilderResult:
    """
    The ``DETERMINISTIC_RETRIEVAL`` entry point (Milestone 23B.1): builds
    an ``EngineeringResponse`` from an already-executed document lookup.

    Unlike ``build_engineering_response`` this function translates
    nothing - its input is already a domain type, so it takes no
    application-layer dependency at all. It lives here so that "build an
    ``EngineeringResponse``" remains one documented entry point per
    origin, rather than some callers reaching into the domain assembler
    directly and others not.

    No prompt is built, no context package is assembled, and the LLM
    runtime is never invoked.
    """

    request = EngineeringResponseDocumentLookupBuildRequestFactory.create(
        project_id=project_id,
        retrieval_result=document_retrieval_result,
        request_correlation_id=request_correlation_id,
    )

    return assemble_document_lookup_response(request, now=now)


def build_comparison_response(
    *,
    comparison_context: ComparisonContextPackage,
    prompt_package: PromptPackage,
    llm_response_envelope: LLMResponseEnvelope,
    now: datetime,
) -> EngineeringResponseBuilderResult:
    """
    The two-sided entry point (Milestone 24.2). Takes a
    ``ComparisonContextPackage`` rather than a single ``ContextPackage``,
    so both sides' evidence counts reach the assessment and neither is
    silently treated as the whole context.

    Performs the same one translation this module exists for - an
    ``LLMResponseEnvelope`` into the domain's own restatement - and no
    other.
    """

    return assemble_comparison_response(
        comparison=comparison_context,
        prompt_package=prompt_package,
        source=_source_envelope_from_llm_envelope(llm_response_envelope),
        now=now,
    )
