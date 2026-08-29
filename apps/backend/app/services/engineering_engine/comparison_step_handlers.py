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
from app.services import (
    context_builder_service,
    engineering_response_service,
    prompt_builder_service,
)
from app.services.engineering_engine.execution_context import (
    WorkflowExecutionContext,
)
from app.services.engineering_engine.step_handler import (
    BaseStepHandler,
    StepHandlerError,
)


class BuildComparisonContextStepHandler(BaseStepHandler):
    """
    Delegates to Governed Context Assembly, once per side, through the
    service's two-sided entry point.

    Each side hands over **its own** governed results (EPIC 31.3) - no
    projection, no merge. The two ``ContextPackage``s stay whole inside
    the ``ComparisonContextPackage``, so an ambiguous left subject
    cannot make the right one look ambiguous and neither side's
    provenance can be attributed to the other.
    """

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
                    left_results=left_result.results,
                    right_designation=request.comparison_right.designation,
                    right_results=right_result.results,
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
