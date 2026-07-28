"""
Step handlers for the DOCUMENT_LOOKUP workflow (Milestone 23B.1) - the
application-layer adapters between the engine and the existing Document
Retrieval capability.

Like every handler in ``step_handlers.py``, none of these recreates
retrieval or response-building logic: each delegates to the existing
service and maps its result into the typed execution context. They live
in their own module purely so that Milestone 23A's handlers stayed
untouched - the engine resolves them through the same
``StepHandlerRegistry`` and knows nothing about either module.

**No LLM anywhere in this file.** There is no provider registry, no
runtime configuration, no credential, and no prompt: a document lookup is
answered entirely from governed repository state.

The handler protocol is ``async`` because the shared
``WorkflowStepHandler`` protocol is (one Milestone 23A handler genuinely
needs it). These three perform no ``await`` of their own - the Engineering
Index port is synchronous, exactly like the Graph Query port the
knowledge-query retrieval handler uses.
"""

from __future__ import annotations

from app.domain.engineering_engine.engineering_engine_models import (
    EngineeringEngineFailureCode,
    WorkflowArtifactKey,
    WorkflowStep,
    WorkflowStepType,
)
from app.domain.engineering_index.document_metadata import (
    DocumentMetadataPort,
)
from app.domain.engineering_index.document_retrieval_factory import (
    DocumentRetrievalRequestFactory,
)
from app.domain.engineering_index.engineering_index_exceptions import (
    EngineeringIndexError,
)
from app.domain.engineering_index.engineering_index_repository import (
    EngineeringIndexRepository,
)
from app.domain.engineering_response.engineering_response_exceptions import (
    EngineeringResponseError,
)
from app.services import (
    document_retrieval_service,
    engineering_response_service,
)
from app.services.engineering_engine.execution_context import (
    WorkflowExecutionContext,
)
from app.services.engineering_engine.step_handler import (
    BaseStepHandler,
    StepHandlerError,
)


class BuildDocumentRetrievalRequestStepHandler(BaseStepHandler):
    """
    Maps the engine's own retrieval configuration onto the existing
    ``DocumentRetrievalRequestFactory`` - never a second request model of
    its own, and never criteria the execution request did not carry.

    The engineering designations to look up come from
    ``retrieval_lexical_terms``, the field the execution request already
    exposes for caller-supplied terms; the engine invents none of them and
    never parses them out of the request text (that would be exactly the
    free-text interpretation the classifier deliberately does not do).
    A request naming no designation at all is an invalid *document
    lookup*, reported as ``INVALID_EXECUTION_REQUEST`` - the workflow
    validates its own inputs, rather than the engine's shared request
    validator growing workflow-specific rules.
    """

    step_type = WorkflowStepType.BUILD_DOCUMENT_RETRIEVAL_REQUEST

    async def execute(
        self, step: WorkflowStep, context: WorkflowExecutionContext
    ) -> WorkflowExecutionContext:
        request = context.execution_request

        if not request.retrieval_lexical_terms:
            raise StepHandlerError(
                EngineeringEngineFailureCode.INVALID_EXECUTION_REQUEST,
                "A document lookup must name at least one engineering "
                "identifier to look up.",
                detail=(
                    "retrieval_lexical_terms is empty; supply the "
                    "designation(s) to find documents for (for example "
                    "'T2', '87T')."
                ),
            )

        try:
            retrieval_request = DocumentRetrievalRequestFactory.create(
                project_id=request.project_id,
                identifiers=request.retrieval_lexical_terms,
                limit=request.retrieval_limit,
            )
        except EngineeringIndexError as error:
            raise StepHandlerError(
                EngineeringEngineFailureCode.INVALID_EXECUTION_REQUEST,
                "Could not build a valid document retrieval request.",
                detail=str(error),
            ) from error

        return context.with_artifact(
            WorkflowArtifactKey.DOCUMENT_RETRIEVAL_REQUEST, retrieval_request
        )


class ExecuteDocumentRetrievalStepHandler(BaseStepHandler):
    """Delegates to the existing ``document_retrieval_service`` through the
    existing ``EngineeringIndexRepository`` and ``DocumentMetadataPort``
    ports. Every Engineering Index error is normalized to
    ``RETRIEVAL_FAILURE``, the same typed code the knowledge-query
    retrieval handler uses - no new failure taxonomy is introduced for
    this workflow."""

    step_type = WorkflowStepType.EXECUTE_DOCUMENT_RETRIEVAL

    def __init__(
        self,
        index_repository: EngineeringIndexRepository,
        document_metadata_port: DocumentMetadataPort,
    ) -> None:
        self._index_repository = index_repository
        self._document_metadata_port = document_metadata_port

    async def execute(
        self, step: WorkflowStep, context: WorkflowExecutionContext
    ) -> WorkflowExecutionContext:
        try:
            result = document_retrieval_service.retrieve_documents(
                self._index_repository,
                self._document_metadata_port,
                context.document_retrieval_request,
                now=context.execution_request.executed_at,
            )
        except EngineeringIndexError as error:
            raise StepHandlerError(
                EngineeringEngineFailureCode.RETRIEVAL_FAILURE,
                "Document retrieval failed.",
                detail=str(error),
            ) from error

        return context.with_artifact(
            WorkflowArtifactKey.DOCUMENT_RETRIEVAL_RESULT, result
        )


class DocumentLookupResponseBuildStepHandler(BaseStepHandler):
    """
    Delegates to the existing Engineering Response service's
    ``DETERMINISTIC_RETRIEVAL`` entry point. The engine never composes an
    ``EngineeringResponse`` itself, and never fabricates a provider,
    model, prompt package or response envelope in order to reuse the LLM
    path - the response honestly records that no provider was involved.

    Finding no matching document is a **successful** execution carrying an
    ``EMPTY`` response that says so, not a failure: the question was
    answered, and the answer is "no indexed document mentions this".
    """

    step_type = WorkflowStepType.BUILD_DOCUMENT_LOOKUP_RESPONSE

    async def execute(
        self, step: WorkflowStep, context: WorkflowExecutionContext
    ) -> WorkflowExecutionContext:
        request = context.execution_request
        correlation_id = (
            request.request_correlation_id
            or f"engine:{request.conversation_id}:{request.turn_id}"
        )

        try:
            result = engineering_response_service.build_document_lookup_response(
                project_id=request.project_id,
                document_retrieval_result=context.document_retrieval_result,
                request_correlation_id=correlation_id,
                now=request.executed_at,
            )
        except EngineeringResponseError as error:
            raise StepHandlerError(
                EngineeringEngineFailureCode.RESPONSE_BUILD_FAILURE,
                "Document lookup response building failed.",
                detail=str(error),
            ) from error

        return context.with_artifact(
            WorkflowArtifactKey.ENGINEERING_RESPONSE, result.response
        ).with_artifact(
            WorkflowArtifactKey.ENGINEERING_RESPONSE_VALIDATION,
            result.validation,
        )
