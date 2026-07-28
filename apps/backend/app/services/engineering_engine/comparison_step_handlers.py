"""
Step handlers for the ENGINEERING_COMPARISON workflow (Milestone 24.2) -
the application-layer adapters between the engine and the existing
retrieval, context, prompt and response services.

Like every other handler module, none of these reimplements a service:
each delegates and maps the result into the typed execution context. What
is specific to comparison is only that there are **two** of some things,
and that the two never become one.

**Left and right are never derived from each other.** Each handler reads
the named field it was written for; there is no index, no role lookup and
no ordering convention that a later change could invert. A comparison
reported in the wrong direction is an error, not a wording choice, so the
direction is made impossible to get wrong rather than merely documented.

No prompt text lives here - Prompt Builder owns every comparison
instruction - and no comparison verdict is decided here: the handler asks
Engineering Response to build the answer, and Engineering Response reads
the declared outcome.
"""

from __future__ import annotations

from app.domain.engineering_engine.engineering_engine_models import (
    ComparisonOperandCriteria,
    EngineeringEngineFailureCode,
    WorkflowArtifactKey,
    WorkflowStep,
    WorkflowStepType,
)
from app.domain.context_builder.context_builder_exceptions import (
    ContextBuilderError,
)
from app.domain.engineering_response.engineering_response_exceptions import (
    EngineeringResponseError,
)
from app.domain.prompt_builder.prompt_builder_exceptions import (
    PromptBuilderError,
)
from app.domain.structured_retrieval.structured_retrieval_exceptions import (
    StructuredRetrievalError,
)
from app.domain.structured_retrieval.structured_retrieval_factory import (
    StructuredRetrievalRequestFactory,
)
from app.domain.structured_retrieval.structured_retrieval_models import (
    RetrievalMode,
)
from app.services import (
    context_builder_service,
    engineering_response_service,
    prompt_builder_service,
    structured_retrieval_service,
)
from app.services.engineering_engine.execution_context import (
    WorkflowExecutionContext,
)
from app.services.engineering_engine.step_handler import (
    BaseStepHandler,
    StepHandlerError,
)


def _retrieval_mode(operand: ComparisonOperandCriteria) -> RetrievalMode:
    """The same mode derivation the single-operand handler performs, per
    side - the engine never invents criteria an operand did not carry."""

    if operand.retrieval_canonical_entity_id:
        return RetrievalMode.ENTITY_LOOKUP
    if operand.retrieval_entity_type and operand.retrieval_attribute_name:
        return RetrievalMode.COMBINED
    if operand.retrieval_entity_type:
        return RetrievalMode.ENTITY_TYPE_SEARCH
    if operand.retrieval_attribute_name:
        return RetrievalMode.ATTRIBUTE_SEARCH

    return RetrievalMode.LEXICAL_SEARCH


class BuildComparisonRetrievalRequestsStepHandler(BaseStepHandler):
    """
    Builds **both** operands' retrieval requests in one step.

    One step rather than two because building is pure and deterministic,
    and an operand set that cannot produce a valid request is an invalid
    *request* whichever side it came from - attributing that to "the left
    retrieval" would be misleading. Execution is where the sides genuinely
    diverge, and that is two steps.

    A request missing either operand is rejected here rather than in the
    engine's shared validator: the workflow validates its own inputs, and
    the engine's request validation stays free of workflow-specific rules.
    """

    step_type = WorkflowStepType.BUILD_COMPARISON_RETRIEVAL_REQUESTS

    async def execute(
        self, step: WorkflowStep, context: WorkflowExecutionContext
    ) -> WorkflowExecutionContext:
        request = context.execution_request
        left = request.comparison_left
        right = request.comparison_right

        missing = [
            name
            for name, operand in (("left", left), ("right", right))
            if operand is None
        ]
        if missing:
            raise StepHandlerError(
                EngineeringEngineFailureCode.INVALID_EXECUTION_REQUEST,
                "A comparison requires exactly two operands.",
                detail=(
                    "Missing operand(s): "
                    + ", ".join(missing)
                    + ". A comparison is never run against a single "
                    "subject, and the second is never inferred."
                ),
            )

        return context.with_artifact(
            WorkflowArtifactKey.LEFT_RETRIEVAL_REQUEST,
            self._build(left, request.project_id, "left"),
        ).with_artifact(
            WorkflowArtifactKey.RIGHT_RETRIEVAL_REQUEST,
            self._build(right, request.project_id, "right"),
        )

    @staticmethod
    def _build(
        operand: ComparisonOperandCriteria, project_id: int, side: str
    ):
        try:
            return StructuredRetrievalRequestFactory.create(
                project_id=project_id,
                mode=_retrieval_mode(operand),
                limit=operand.retrieval_limit,
                include_neighborhood=operand.retrieval_include_neighborhood,
                neighborhood_depth=operand.retrieval_neighborhood_depth,
                canonical_entity_id=operand.retrieval_canonical_entity_id,
                entity_type=operand.retrieval_entity_type,
                attribute_name=operand.retrieval_attribute_name,
                lexical_terms=operand.retrieval_lexical_terms,
            )
        except StructuredRetrievalError as error:
            raise StepHandlerError(
                EngineeringEngineFailureCode.INVALID_EXECUTION_REQUEST,
                f"Could not build a valid retrieval request for the {side} "
                "comparison operand.",
                detail=f"{side} operand '{operand.designation}': {error}",
            ) from error


class _ExecuteSideRetrievalStepHandler(BaseStepHandler):
    """Shared body for the two retrieval steps. The *side* is fixed per
    subclass rather than resolved at runtime, so no code path can read one
    side's request and write the other's result."""

    request_key: WorkflowArtifactKey
    result_key: WorkflowArtifactKey
    side: str

    def __init__(self, graph_query_repository) -> None:
        self._repository = graph_query_repository

    async def execute(
        self, step: WorkflowStep, context: WorkflowExecutionContext
    ) -> WorkflowExecutionContext:
        try:
            result = structured_retrieval_service.retrieve(
                self._repository,
                context.get_artifact(self.request_key),
                now=context.execution_request.executed_at,
            )
        except StructuredRetrievalError as error:
            raise StepHandlerError(
                EngineeringEngineFailureCode.RETRIEVAL_FAILURE,
                f"Structured retrieval failed for the {self.side} "
                "comparison operand.",
                detail=str(error),
            ) from error

        return context.with_artifact(self.result_key, result)


class ExecuteLeftRetrievalStepHandler(_ExecuteSideRetrievalStepHandler):
    step_type = WorkflowStepType.EXECUTE_LEFT_RETRIEVAL
    request_key = WorkflowArtifactKey.LEFT_RETRIEVAL_REQUEST
    result_key = WorkflowArtifactKey.LEFT_RETRIEVAL_RESULT
    side = "left"


class ExecuteRightRetrievalStepHandler(_ExecuteSideRetrievalStepHandler):
    step_type = WorkflowStepType.EXECUTE_RIGHT_RETRIEVAL
    request_key = WorkflowArtifactKey.RIGHT_RETRIEVAL_REQUEST
    result_key = WorkflowArtifactKey.RIGHT_RETRIEVAL_RESULT
    side = "right"


class BuildComparisonContextStepHandler(BaseStepHandler):
    """Delegates to the existing Context Builder, once per side, through
    the service's two-sided entry point. It never merges the results - the
    two ``ContextPackage``s stay whole inside the
    ``ComparisonContextPackage``."""

    step_type = WorkflowStepType.BUILD_COMPARISON_CONTEXT

    async def execute(
        self, step: WorkflowStep, context: WorkflowExecutionContext
    ) -> WorkflowExecutionContext:
        request = context.execution_request
        left_result = context.left_retrieval_result
        right_result = context.right_retrieval_result

        try:
            comparison = (
                context_builder_service.build_comparison_context_package(
                    project_id=request.project_id,
                    left_designation=request.comparison_left.designation,
                    left_candidates=left_result.candidates,
                    right_designation=request.comparison_right.designation,
                    right_candidates=right_result.candidates,
                    left_retrieval_policy_version=(
                        left_result.metadata.scoring_policy_version
                    ),
                    right_retrieval_policy_version=(
                        right_result.metadata.scoring_policy_version
                    ),
                    now=request.executed_at,
                )
            )
        except ContextBuilderError as error:
            raise StepHandlerError(
                EngineeringEngineFailureCode.CONTEXT_BUILD_FAILURE,
                "Comparison context building failed.",
                detail=str(error),
            ) from error

        return context.with_artifact(
            WorkflowArtifactKey.COMPARISON_CONTEXT, comparison
        )


class BuildComparisonPromptStepHandler(BaseStepHandler):
    """Delegates to Prompt Builder's two-sided entry point. The objective
    is not a parameter: a two-sided context has no meaningful reading
    under any other one."""

    step_type = WorkflowStepType.BUILD_COMPARISON_PROMPT

    async def execute(
        self, step: WorkflowStep, context: WorkflowExecutionContext
    ) -> WorkflowExecutionContext:
        try:
            result = prompt_builder_service.build_comparison_prompt_package(
                comparison_context=context.comparison_context,
                now=context.execution_request.executed_at,
            )
        except PromptBuilderError as error:
            raise StepHandlerError(
                EngineeringEngineFailureCode.PROMPT_BUILD_FAILURE,
                "Comparison prompt building failed.",
                detail=str(error),
            ) from error

        return context.with_artifact(
            WorkflowArtifactKey.PROMPT_PACKAGE, result.package
        )


class ComparisonResponseBuildStepHandler(BaseStepHandler):
    """
    Delegates to Engineering Response's two-sided entry point, which reads
    the declared comparison outcome and applies the evidence bound.

    The handler decides nothing about the comparison itself: it does not
    read the answer, does not interpret it, and knows none of the outcome
    vocabulary - that belongs to Prompt Builder, which asks for it, and to
    Engineering Response, which reads it back.
    """

    step_type = WorkflowStepType.BUILD_COMPARISON_RESPONSE

    async def execute(
        self, step: WorkflowStep, context: WorkflowExecutionContext
    ) -> WorkflowExecutionContext:
        try:
            result = engineering_response_service.build_comparison_response(
                comparison_context=context.comparison_context,
                prompt_package=context.prompt_package,
                llm_response_envelope=context.llm_response_envelope,
                now=context.execution_request.executed_at,
            )
        except EngineeringResponseError as error:
            raise StepHandlerError(
                EngineeringEngineFailureCode.RESPONSE_BUILD_FAILURE,
                "Comparison response building failed.",
                detail=str(error),
            ) from error

        return context.with_artifact(
            WorkflowArtifactKey.ENGINEERING_RESPONSE, result.response
        ).with_artifact(
            WorkflowArtifactKey.ENGINEERING_RESPONSE_VALIDATION,
            result.validation,
        )
