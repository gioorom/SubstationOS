"""
Orchestrates the document-lookup (``DETERMINISTIC_RETRIEVAL``) build
pipeline (Milestone 23B.1):

    DocumentRetrievalResult
            |
       Composition           (engineering_response_document_composition.py)
            |
       Statistics            (engineering_response_statistics.py - shared)
            |
       Metadata/Versioning   (this module)
            |
       Validation            (engineering_response_validation.py - shared)
       EngineeringResponseBuilderResult

Deliberately the same four stages, in the same order, as
``engineering_response_assembler.py``: only the Composition input and the
provenance recorded in metadata differ. Statistics and Validation are
literally the same functions, so a document-lookup response is held to
exactly the same structural invariants as an LLM one.

Pure and deterministic: given the same ``DocumentRetrievalResult`` and the
same ``now``, always produces the same result. No I/O, no wall-clock read,
**no AI usage of any kind, and no provider named anywhere.**
"""

from __future__ import annotations

from datetime import datetime

from app.domain.engineering_response.engineering_response_document_composition import (  # noqa: E501
    compose_document_lookup_response,
)
from app.domain.engineering_response.engineering_response_models import (
    EngineeringResponse,
    EngineeringResponseBuilderResult,
    EngineeringResponseDocumentLookupBuildRequest,
    EngineeringResponseMetadata,
    EngineeringResponseOrigin,
    EngineeringResponseVersion,
)
from app.domain.engineering_response.engineering_response_policy import (
    RESPONSE_PACKAGE_VERSION,
)
from app.domain.engineering_response.engineering_response_statistics import (
    build_statistics,
)
from app.domain.engineering_response.engineering_response_validation import (
    validate_response,
)


def build_document_lookup_metadata(
    request: EngineeringResponseDocumentLookupBuildRequest, *, now: datetime
) -> EngineeringResponseMetadata:
    """Every provider and prompt field is ``None``: no provider was
    called, no model was selected, and no prompt or context package
    exists. Reporting them as absent is the honest record; inventing
    placeholder values would make the response indistinguishable from one
    a model produced."""

    return EngineeringResponseMetadata(
        engineering_response_version=(
            request.configuration.engineering_response_version
        ),
        response_policy_version=request.configuration.response_policy.version,
        assembled_at=now,
        project_id=request.project_id,
        provider_id=None,
        configured_model_identifier=None,
        returned_model_identifier=None,
        request_correlation_id=request.request_correlation_id,
        prompt_package_version=None,
        context_assembly_version=None,
        prompt_builder_version=None,
        package_version=RESPONSE_PACKAGE_VERSION,
    )


def build_document_lookup_version(
    request: EngineeringResponseDocumentLookupBuildRequest,
) -> EngineeringResponseVersion:
    """Records the versions of the deterministic capabilities that
    actually produced this answer, exactly as the LLM path records the
    runtime's and prompt builder's."""

    retrieval_metadata = request.retrieval_result.metadata

    return EngineeringResponseVersion(
        engineering_response_version=(
            request.configuration.engineering_response_version
        ),
        response_policy_version=request.configuration.response_policy.version,
        prompt_builder_version=None,
        context_assembly_version=None,
        request_preparation_policy_version=None,
        runtime_version=None,
        package_version=RESPONSE_PACKAGE_VERSION,
        document_retrieval_version=(
            retrieval_metadata.document_retrieval_version
        ),
        document_relevance_policy_version=(
            retrieval_metadata.relevance_policy_version
        ),
    )


def assemble_document_lookup_response(
    request: EngineeringResponseDocumentLookupBuildRequest, *, now: datetime
) -> EngineeringResponseBuilderResult:
    composition = compose_document_lookup_response(request.retrieval_result)
    statistics = build_statistics(composition)
    metadata = build_document_lookup_metadata(request, now=now)
    version = build_document_lookup_version(request)

    response = EngineeringResponse(
        project_id=request.project_id,
        status=composition.status,
        sections=composition.sections,
        summary=composition.summary,
        direct_answer=composition.direct_answer,
        references=composition.references,
        warnings=composition.warnings,
        uncertainties=composition.uncertainties,
        overall_uncertainty=composition.overall_uncertainty,
        metadata=metadata,
        statistics=statistics,
        version=version,
        origin=EngineeringResponseOrigin.DETERMINISTIC_RETRIEVAL,
        document_references=composition.document_references,
    )

    return EngineeringResponseBuilderResult(
        project_id=request.project_id,
        response=response,
        validation=validate_response(response),
    )
