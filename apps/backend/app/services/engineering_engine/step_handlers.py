"""
Concrete step handlers for the KNOWLEDGE_QUERY workflow (Milestone 23A) -
the application-layer adapters between the engine and the existing
services.

Every handler here exists for one of three reasons the milestone
accepts: stable engine integration, typed inputs/outputs, or boundary
isolation. **None recreates retrieval, context, prompt, runtime, or
response-building logic** - each delegates to the existing service and
maps its result into the typed execution context. The engine core knows
none of these services; it knows only the ``WorkflowStepHandler``
contract, which lives in ``step_handler.py`` precisely so the core never
has to import this module (or any other workflow's handlers).
"""

from __future__ import annotations

import random
from app.application.models.llm_exceptions import LLMProviderAbstractionError
from app.application.models.llm_invocation import (
    LLMInvocationStatus,
    LLMRuntimeConfiguration,
)
from app.application.models.llm_request import (
    LLMModelSelection,
    LLMProviderSelection,
)
from app.application.services.llm_invocation_service import invoke_llm
from app.application.services.llm_provider_registry import LLMProviderRegistry
from app.domain.context_builder.context_builder_exceptions import (
    ContextBuilderError,
)
from app.domain.engineering_engine.engineering_engine_models import (
    AggregateUpdateDisposition,
    ConversationUpdateProposal,
    EngineeringEngineFailureCode,
    SessionUpdateProposal,
    WorkflowArtifactKey,
    WorkflowStep,
    WorkflowStepType,
)
from app.domain.engineering_engine.engineering_engine_validation import (
    validate_execution_request,
)
from app.domain.engineering_response.engineering_response_exceptions import (
    EngineeringResponseError,
)
from app.domain.prompt_builder.prompt_builder_exceptions import (
    PromptBuilderError,
)
from app.domain.prompt_builder.prompt_builder_models import PromptObjective
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


class ValidateExecutionRequestStepHandler(BaseStepHandler):
    """Re-validates the execution request inside the plan, so the
    validation is recorded as a real, timed, auditable step rather than
    only as a precondition the service checked silently."""

    step_type = WorkflowStepType.VALIDATE_EXECUTION_REQUEST

    async def execute(
        self, step: WorkflowStep, context: WorkflowExecutionContext
    ) -> WorkflowExecutionContext:
        validation = validate_execution_request(context.execution_request)
        if not validation.valid:
            raise StepHandlerError(
                EngineeringEngineFailureCode.INVALID_EXECUTION_REQUEST,
                "The execution request is structurally invalid.",
                detail="; ".join(validation.errors),
            )

        return context


class BuildContextStepHandler(BaseStepHandler):
    """
    Delegates to Governed Context Assembly.

    **Hands over the governed results themselves** (EPIC 31.3). Until
    that milestone this step projected them into the legacy
    ``KnowledgeCandidate`` vocabulary through a temporary adapter; the
    adapter is deleted and Context Assembly now reads
    ``GovernedRetrievalResult`` natively, so the governed identity, the
    match strategy, the mandatory provenance and the per-query ambiguity
    all reach the context without passing through a translation that
    could drop any of them.
    """

    step_type = WorkflowStepType.BUILD_CONTEXT

    async def execute(
        self, step: WorkflowStep, context: WorkflowExecutionContext
    ) -> WorkflowExecutionContext:
        project_id = context.execution_request.project_id

        try:
            result = context_builder_service.build_context_package(
                project_id=project_id,
                results=context.retrieval_result.results,
                now=context.execution_request.executed_at,
            )
        except ContextBuilderError as error:
            raise StepHandlerError(
                EngineeringEngineFailureCode.CONTEXT_BUILD_FAILURE,
                "Context building failed.",
                detail=str(error),
            ) from error

        return context.with_artifact(
            WorkflowArtifactKey.CONTEXT_PACKAGE, result.package
        )


class BuildPromptStepHandler(BaseStepHandler):
    """
    Delegates to the existing Prompt Builder. Serves **every** workflow
    that needs a prompt: the step type it answers to and the
    ``PromptObjective`` it requests are supplied at composition, so a
    workflow wanting a different kind of answer registers this same class
    again rather than duplicating it (Milestone 23B.2).

    The objective is deliberately *not* derived from the intent type or
    the workflow type here - that would put workflow branching inside a
    handler. The composition root states it once, declaratively, next to
    the workflow that wants it.
    """

    def __init__(
        self,
        *,
        step_type: WorkflowStepType = WorkflowStepType.BUILD_PROMPT,
        objective: PromptObjective = PromptObjective.DIRECT_ANSWER,
    ) -> None:
        self.step_type = step_type
        self._objective = objective

    async def execute(
        self, step: WorkflowStep, context: WorkflowExecutionContext
    ) -> WorkflowExecutionContext:
        try:
            result = prompt_builder_service.build_prompt_package(
                project_id=context.execution_request.project_id,
                context_package=context.context_package,
                objective=self._objective,
                # Present only in a workflow that ran the reasoning step;
                # ``None`` everywhere else, and the section is then empty
                # and disabled.
                reasoning=context.reasoning_result,
                now=context.execution_request.executed_at,
            )
        except PromptBuilderError as error:
            raise StepHandlerError(
                EngineeringEngineFailureCode.PROMPT_BUILD_FAILURE,
                "Prompt building failed.",
                detail=str(error),
            ) from error

        return context.with_artifact(
            WorkflowArtifactKey.PROMPT_PACKAGE, result.package
        )


class RuntimeInvocationStepHandler(BaseStepHandler):
    """
    Invokes the existing provider-neutral LLM Runtime. The engine never
    touches a provider SDK, never selects a provider itself, and never
    sees a raw provider exception - the runtime already normalizes every
    provider failure into a typed ``LLMProviderError``, which this
    handler maps to ``RUNTIME_FAILURE``.
    """

    step_type = WorkflowStepType.INVOKE_LLM_RUNTIME

    def __init__(
        self,
        *,
        provider_registry: LLMProviderRegistry,
        runtime_configuration: LLMRuntimeConfiguration,
        credential_present: bool,
        credential_environment_variable_name: str,
        sleeper,
        random_source: random.Random | None = None,
    ) -> None:
        self._provider_registry = provider_registry
        self._runtime_configuration = runtime_configuration
        self._credential_present = credential_present
        self._credential_environment_variable_name = (
            credential_environment_variable_name
        )
        self._sleeper = sleeper
        self._random_source = random_source or random.Random()

    async def execute(
        self, step: WorkflowStep, context: WorkflowExecutionContext
    ) -> WorkflowExecutionContext:
        request = context.execution_request
        correlation_id = (
            request.request_correlation_id
            or f"engine:{request.conversation_id}:{request.turn_id}"
        )

        provider_selection = (
            LLMProviderSelection(provider_id=request.provider_id)
            if request.provider_id
            else None
        )
        model_selection = (
            LLMModelSelection(model_identifier=request.model_identifier)
            if request.model_identifier
            else None
        )

        try:
            result = await invoke_llm(
                registry=self._provider_registry,
                runtime_configuration=self._runtime_configuration,
                credential_present=self._credential_present,
                credential_environment_variable_name=(
                    self._credential_environment_variable_name
                ),
                prompt_package=context.prompt_package,
                project_id=request.project_id,
                provider_selection=provider_selection,
                model_selection=model_selection,
                request_correlation_id=correlation_id,
                clock=lambda: request.executed_at,
                sleeper=self._sleeper,
                random_source=self._random_source,
                now=request.executed_at,
            )
        except LLMProviderAbstractionError as error:
            raise StepHandlerError(
                EngineeringEngineFailureCode.RUNTIME_FAILURE,
                "The LLM runtime rejected the invocation.",
                detail=str(error),
            ) from error

        if (
            result.status is not LLMInvocationStatus.SUCCEEDED
            or result.envelope is None
        ):
            detail = (
                result.terminal_error.category.value
                if result.terminal_error is not None
                else "unknown"
            )
            raise StepHandlerError(
                EngineeringEngineFailureCode.RUNTIME_FAILURE,
                "The LLM runtime did not produce a successful response.",
                detail=detail,
            )

        return context.with_artifact(
            WorkflowArtifactKey.LLM_RESPONSE_ENVELOPE, result.envelope
        )


class EngineeringResponseBuildStepHandler(BaseStepHandler):
    """Delegates to the existing Engineering Response service - the one
    seam allowed to translate an ``LLMResponseEnvelope`` into the domain
    (ADR-0015). The engine never rebuilds that translation."""

    step_type = WorkflowStepType.BUILD_ENGINEERING_RESPONSE

    async def execute(
        self, step: WorkflowStep, context: WorkflowExecutionContext
    ) -> WorkflowExecutionContext:
        try:
            result = engineering_response_service.build_engineering_response(
                project_id=context.execution_request.project_id,
                context_package=context.context_package,
                prompt_package=context.prompt_package,
                llm_response_envelope=context.llm_response_envelope,
                now=context.execution_request.executed_at,
                # None for every workflow that does not reason - the
                # response then simply carries no derived conclusion.
                reasoning=context.reasoning_result,
            )
        except EngineeringResponseError as error:
            raise StepHandlerError(
                EngineeringEngineFailureCode.RESPONSE_BUILD_FAILURE,
                "Engineering response building failed.",
                detail=str(error),
            ) from error

        return context.with_artifact(
            WorkflowArtifactKey.ENGINEERING_RESPONSE, result.response
        ).with_artifact(
            WorkflowArtifactKey.ENGINEERING_RESPONSE_VALIDATION,
            result.validation,
        )


class ValidateEngineeringResponseStepHandler(BaseStepHandler):
    """Reuses Engineering Response's *own* self-validation result rather
    than re-deriving it - the engine never second-guesses a downstream
    context's validation."""

    step_type = WorkflowStepType.VALIDATE_ENGINEERING_RESPONSE

    async def execute(
        self, step: WorkflowStep, context: WorkflowExecutionContext
    ) -> WorkflowExecutionContext:
        validation = context.engineering_response_validation
        if not validation.valid:
            raise StepHandlerError(
                EngineeringEngineFailureCode.RESPONSE_VALIDATION_FAILURE,
                "The produced EngineeringResponse failed its own "
                "structural validation.",
                detail="; ".join(validation.errors),
            )

        return context


class PrepareConversationUpdateStepHandler(BaseStepHandler):
    """Produces an explicit *proposal* only - the engine never mutates
    ``Conversation`` (ADR-0020's aggregate update policy)."""

    step_type = WorkflowStepType.PREPARE_CONVERSATION_UPDATE

    async def execute(
        self, step: WorkflowStep, context: WorkflowExecutionContext
    ) -> WorkflowExecutionContext:
        request = context.execution_request

        proposal = ConversationUpdateProposal(
            conversation_id=request.conversation_id,
            turn_id=request.turn_id,
            disposition=AggregateUpdateDisposition.PREPARED,
            description=(
                "Attach the produced EngineeringResponse to this "
                "conversation turn via "
                "conversation_service.attach_response. Not applied by "
                "the engine."
            ),
        )

        return context.with_artifact(
            WorkflowArtifactKey.CONVERSATION_UPDATE_PROPOSAL, proposal
        )


class PrepareSessionUpdateStepHandler(BaseStepHandler):
    """Produces an explicit *proposal* only - the engine never mutates
    ``EngineeringSession``."""

    step_type = WorkflowStepType.PREPARE_SESSION_UPDATE

    async def execute(
        self, step: WorkflowStep, context: WorkflowExecutionContext
    ) -> WorkflowExecutionContext:
        request = context.execution_request

        proposal = SessionUpdateProposal(
            engineering_session_id=request.engineering_session_id,
            disposition=AggregateUpdateDisposition.PREPARED,
            description=(
                "Append the produced EngineeringResponse to this "
                "EngineeringSession via "
                "engineering_session_service.append_response. Not "
                "applied by the engine."
            ),
        )

        return context.with_artifact(
            WorkflowArtifactKey.SESSION_UPDATE_PROPOSAL, proposal
        )
